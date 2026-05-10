"""
Conversation Orchestrator.

Full message flow:
1. Webhook → parse message
2. Check if admin command → execute directly
3. If media → process (transcribe, analyze, extract)
4. Resolve quoted messages
5. Buffer in Redis
6. When buffer expires:
   a. Build contact context
   b. Search events
   c. Search RAG knowledge base
   d. Generate GPT response
   e. Extract and process notifications
   f. Save and send response
"""

import asyncio
from datetime import date, datetime, timezone, timedelta
from uuid import UUID

from loguru import logger
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import async_session
from app.models.models import Contact, Conversation, Message
from app.services.admin_commands import parse_admin_command, parse_self_serve_command
from app.services.buffer import (
    add_to_buffer,
    get_buffered_messages,
    acquire_processing_lock,
    release_processing_lock,
    set_typing_indicator,
    clear_typing_indicator,
)
from app.services.contact_updater import extract_cadastro, update_contact_from_cadastro
from app.services.events_service import (
    search_events,
    list_future_events,
    list_recent_past_editions,
    format_events_context,
    format_past_events_context,
)
from app.services.media_processor import media_processor
from app.services.notification_service import extract_notifications, process_notifications
from app.services.openai_service import generate_response, summarize_conversation
from app.services.rag_service import search_knowledge, build_rag_context
from app.services.uazapi import uazapi

settings = get_settings()

MEDIA_TYPES = {"audio", "image", "document", "video", "sticker", "location", "contact"}

# Trigger a rolling summary when this many new messages have accumulated
# beyond the live history window since the last summary update.
SUMMARY_REFRESH_INTERVAL = 10

# Conversations idle for longer than this are archived and a fresh one is opened
# on the next interaction (preserves contact data, drops stale chat context).
CONVERSATION_INACTIVITY_DAYS = 30


async def handle_incoming_message(parsed: dict):
    """Main entry point called by the webhook endpoint."""
    phone = parsed["phone"]
    body = parsed["body"]
    msg_type = parsed["type"]

    # ── Step -1: Self-serve commands (reset / wipe own data) ────
    if body:
        self_serve_response = await parse_self_serve_command(body, phone)
        if self_serve_response is not None:
            await uazapi.send_text(phone, self_serve_response)
            return

    # ── Step 0: Check if admin command ─────────────────────────
    async with async_session() as db:
        contact = await _get_contact(db, phone)
        if contact and contact.is_admin and body:
            admin_response = await parse_admin_command(body, phone)
            if admin_response:
                await uazapi.send_text(phone, admin_response)
                return

    # ── Step 1: Process media if needed ────────────────────────
    if msg_type in MEDIA_TYPES:
        logger.info(f"Media message ({msg_type}) from {phone}, processing...")
        processed_text = await media_processor.process(parsed)
        if processed_text:
            if body:
                parsed["body"] = f"{body}\n\n{processed_text}"
            else:
                parsed["body"] = processed_text
            parsed["type"] = "text"
        else:
            if not body:
                return

    # ── Step 2: Resolve quoted message context ─────────────────
    quoted_id = parsed.get("quoted_id", "")
    if quoted_id:
        quoted_context = await _resolve_quoted_message(quoted_id, parsed)
        if quoted_context:
            parsed["body"] = f"{quoted_context}\n\n{parsed['body']}"

    # ── Step 3: Skip empty messages ────────────────────────────
    if not parsed["body"]:
        return

    # ── Step 4: Buffer and schedule ────────────────────────────
    await add_to_buffer(phone, parsed)
    asyncio.create_task(_schedule_processing(phone))


async def _schedule_processing(phone: str):
    await asyncio.sleep(settings.buffer_delay_seconds)
    if not await acquire_processing_lock(phone):
        return
    try:
        await _process_buffered_messages(phone)
    except Exception as e:
        logger.error(f"Error processing messages for {phone}: {e}")
    finally:
        await release_processing_lock(phone)
        await clear_typing_indicator(phone)


async def _process_buffered_messages(phone: str):
    messages = await get_buffered_messages(phone)
    if not messages:
        return

    await set_typing_indicator(phone)

    combined_text = "\n".join(msg["body"] for msg in messages if msg.get("body"))
    if not combined_text.strip():
        return

    push_name = next(
        (msg.get("push_name") for msg in messages if msg.get("push_name")), None
    )

    logger.info(f"Processing {len(messages)} message(s) from {phone}")

    async with async_session() as db:
        contact = await _get_or_create_contact(db, phone, push_name)
        conversation = await _get_or_create_conversation(db, contact.id)

        if not conversation.is_ai_enabled:
            return

        # Save user message
        wa_msg_id = next(
            (msg.get("message_id") for msg in reversed(messages) if msg.get("message_id")),
            None,
        )
        user_msg = Message(
            conversation_id=conversation.id,
            role="user",
            content=combined_text,
            message_type="text",
            whatsapp_message_id=wa_msg_id,
        )
        db.add(user_msg)
        await db.commit()

        # ── Build all contexts ─────────────────────────────────

        # Contact context
        contact_context = _build_contact_context(contact)

        # Events context (future agenda + history of past editions)
        events = await list_future_events(days_ahead=60)
        events_context = format_events_context(events)

        past_editions = await list_recent_past_editions(months_back=18, limit=15)
        past_events_context = format_past_events_context(past_editions)

        # RAG context
        rag_results = await search_knowledge(combined_text, limit=3)
        rag_context = build_rag_context(rag_results)

        # Build history (includes rolling summary when present)
        history = await _build_history(db, conversation)

        # ── Generate response ──────────────────────────────────
        reply, tokens = await generate_response(
            history, combined_text,
            contact_context=contact_context,
            events_context=events_context,
            past_events_context=past_events_context,
            rag_context=rag_context,
        )

        # ── Extract tags from response ──────────────────────────
        # 1. Extract cadastro tags (contact updates)
        reply_after_cadastro, cadastro_fields = extract_cadastro(reply)

        # 2. Extract notification tags
        clean_reply, notifications = extract_notifications(reply_after_cadastro)

        # 3. Update contact if cadastro data found
        if cadastro_fields:
            await update_contact_from_cadastro(db, phone, cadastro_fields)

        # Save assistant response (clean, without tags)
        assistant_msg = Message(
            conversation_id=conversation.id,
            role="assistant",
            content=clean_reply,
            message_type="text",
            token_count=tokens,
        )
        db.add(assistant_msg)
        await db.commit()

        # Send clean response (without notification tags)
        send_result = await _send_response(phone, clean_reply)

        # Save whatsapp message ID
        if send_result and send_result.get("messageid"):
            assistant_msg.whatsapp_message_id = send_result["messageid"]
            await db.commit()

        # Process notifications in background
        if notifications:
            asyncio.create_task(
                process_notifications(notifications, phone, contact.name)
            )

        # Refresh rolling summary in background when enough new messages
        # have accumulated beyond the live history window
        asyncio.create_task(_update_summary_if_needed(conversation.id))


def _build_contact_context(contact: Contact) -> str:
    """Build contact context string for prompt injection."""
    parts = []

    if contact.name:
        parts.append(f"Nome: {contact.name}")
    if contact.status:
        parts.append(f"Vínculo: {contact.status}")
    if contact.birthday:
        parts.append(f"Aniversário: {contact.birthday.strftime('%d/%m')}")
    if contact.neighborhood:
        parts.append(f"Bairro: {contact.neighborhood}")
    if contact.how_found:
        parts.append(f"Como conheceu: {contact.how_found}")

    return "\n".join(parts) if parts else ""


SPLIT_MARKER = "<NEXT>"
MAX_CHUNK = 4000


def _split_into_bubbles(text: str) -> list[str]:
    """Split LLM response into WhatsApp bubbles.

    Primary split: <NEXT> markers emitted by the model.
    Fallback safety: any bubble exceeding MAX_CHUNK is paragraph-split.
    """
    raw_parts = [p.strip() for p in text.split(SPLIT_MARKER)]
    raw_parts = [p for p in raw_parts if p]

    bubbles: list[str] = []
    for part in raw_parts:
        if len(part) <= MAX_CHUNK:
            bubbles.append(part)
            continue
        current = ""
        for paragraph in part.split("\n"):
            if len(current) + len(paragraph) + 1 > MAX_CHUNK:
                if current:
                    bubbles.append(current.strip())
                current = paragraph
            else:
                current += "\n" + paragraph if current else paragraph
        if current.strip():
            bubbles.append(current.strip())
    return bubbles


def _typing_delay_seconds(chunk: str) -> float:
    """Simulate human typing time before the next bubble.

    ~40ms per char, clamped to [0.8s, 3.0s].
    """
    return min(3.0, max(0.8, len(chunk) * 0.04))


async def _send_response(phone: str, text: str) -> dict | None:
    bubbles = _split_into_bubbles(text)
    if not bubbles:
        return None

    last_result = None
    for i, bubble in enumerate(bubbles):
        if i > 0:
            await asyncio.sleep(_typing_delay_seconds(bubble))
        last_result = await uazapi.send_text(phone, bubble)
    return last_result


async def _get_contact(db: AsyncSession, phone: str) -> Contact | None:
    result = await db.execute(select(Contact).where(Contact.phone == phone))
    return result.scalar_one_or_none()


async def _get_or_create_contact(
    db: AsyncSession, phone: str, push_name: str | None = None
) -> Contact:
    contact = await _get_contact(db, phone)
    if contact:
        if push_name and push_name != contact.push_name:
            contact.push_name = push_name
            await db.commit()
        return contact

    contact = Contact(phone=phone, push_name=push_name)
    db.add(contact)
    await db.commit()
    await db.refresh(contact)
    logger.info(f"New contact: {phone} ({push_name})")
    return contact


async def _get_or_create_conversation(
    db: AsyncSession, contact_id
) -> Conversation:
    result = await db.execute(
        select(Conversation).where(
            Conversation.contact_id == contact_id,
            Conversation.is_active == True,
        )
    )
    conversation = result.scalar_one_or_none()

    if conversation:
        # If the previous conversation has been idle for too long, archive it
        # and start a new one. Keeps chat context fresh without losing contact
        # data (which lives on the Contact, not the Conversation).
        last_active = conversation.updated_at
        if last_active is not None:
            now = datetime.now(timezone.utc)
            if last_active.tzinfo is None:
                last_active = last_active.replace(tzinfo=timezone.utc)
            if now - last_active > timedelta(days=CONVERSATION_INACTIVITY_DAYS):
                conversation.is_active = False
                await db.commit()
                logger.info(
                    f"Archived stale conversation {conversation.id} "
                    f"(idle {(now - last_active).days}d), opening fresh one"
                )
                conversation = None

    if conversation:
        return conversation

    conversation = Conversation(contact_id=contact_id)
    db.add(conversation)
    await db.commit()
    await db.refresh(conversation)
    return conversation


async def _build_history(
    db: AsyncSession, conversation: Conversation
) -> list[dict]:
    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation.id)
        .order_by(Message.created_at.desc())
        .limit(settings.max_history_messages)
    )
    messages = result.scalars().all()
    messages.reverse()
    if messages and messages[-1].role == "user":
        messages = messages[:-1]

    history: list[dict] = []
    if conversation.summary:
        history.append({
            "role": "system",
            "content": (
                "Resumo do histórico anterior dessa conversa "
                "(use como contexto, não cite literalmente):\n"
                f"{conversation.summary}"
            ),
        })
    history.extend({"role": msg.role, "content": msg.content} for msg in messages)
    return history


async def _update_summary_if_needed(conversation_id: UUID) -> None:
    """Refresh the rolling summary when enough new messages accumulated.

    Runs in its own DB session so it can be fired-and-forgotten after
    the user response is sent. Summarises everything older than the
    live history window so the model never loses long-running context.
    """
    try:
        async with async_session() as db:
            total = (await db.execute(
                select(func.count(Message.id))
                .where(Message.conversation_id == conversation_id)
            )).scalar() or 0

            if total <= settings.max_history_messages:
                return

            conv = (await db.execute(
                select(Conversation).where(Conversation.id == conversation_id)
            )).scalar_one_or_none()
            if conv is None:
                return

            # Number of messages older than the live window
            old_count = total - settings.max_history_messages
            new_since_last = old_count - (conv.summary_message_count or 0)
            if new_since_last < SUMMARY_REFRESH_INTERVAL:
                return

            # Pull the messages we want to summarize (everything except the
            # last MAX_HISTORY_MESSAGES, in chronological order)
            old_messages = (await db.execute(
                select(Message)
                .where(Message.conversation_id == conversation_id)
                .order_by(Message.created_at.asc())
                .limit(old_count)
            )).scalars().all()

            if not old_messages:
                return

            text_blocks = [
                f"{'Usuário' if m.role == 'user' else 'Liriel'}: {m.content}"
                for m in old_messages
            ]
            history_text = "\n".join(text_blocks)

            new_summary = await summarize_conversation(history_text)
            if not new_summary:
                return

            conv.summary = new_summary
            conv.summary_message_count = old_count
            await db.commit()
            logger.info(
                f"Conversation {conversation_id} summary updated "
                f"({old_count} msgs covered)"
            )
    except Exception as e:
        logger.error(f"Summary update failed for {conversation_id}: {e}")


async def _resolve_quoted_message(quoted_id: str, parsed: dict) -> str | None:
    try:
        async with async_session() as db:
            result = await db.execute(
                select(Message).where(Message.whatsapp_message_id == quoted_id)
            )
            quoted_msg = result.scalar_one_or_none()
            if quoted_msg:
                content = quoted_msg.content
                if len(content) > 500:
                    content = content[:500] + "..."
                role_label = "Liriel" if quoted_msg.role == "assistant" else "Usuário"
                return f"[Em resposta à mensagem de {role_label}: {content}]"

        message_id = parsed.get("message_id", "")
        if message_id:
            quoted_result = await uazapi.download_quoted_media(
                message_id=message_id, return_base64=False
            )
            if quoted_result and quoted_result.get("fileURL"):
                return f"[O usuário respondeu a uma mídia. URL: {quoted_result['fileURL']}]"

        return None
    except Exception as e:
        logger.error(f"Error resolving quoted message: {e}")
        return None
