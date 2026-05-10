"""
Admin Command Parser.

Parses admin commands from WhatsApp messages for event management,
plus self-serve commands any user can run on their own data.
"""

import re
from datetime import datetime, date

from loguru import logger
from sqlalchemy import delete, select

from app.core.config import get_settings
from app.core.database import async_session
from app.core.redis import get_redis
from app.models.models import Contact, Conversation, Message, NotificationLog
from app.services.events_service import add_event, remove_event, list_future_events


# ── Admin bootstrap (runs at lifespan startup) ─────────────

async def bootstrap_admins() -> None:
    """Ensure phones listed in settings.admin_phones are flagged is_admin=True.

    Creates the Contact row if it doesn't exist yet so the user can issue
    admin commands even before they've sent their first message.
    """
    phones = get_settings().admin_phone_list
    if not phones:
        return

    async with async_session() as db:
        for phone in phones:
            contact = (await db.execute(
                select(Contact).where(Contact.phone == phone)
            )).scalar_one_or_none()
            if contact is None:
                db.add(Contact(phone=phone, is_admin=True))
                logger.info(f"Bootstrapped admin contact: {phone}")
            elif not contact.is_admin:
                contact.is_admin = True
                logger.info(f"Promoted existing contact to admin: {phone}")
        await db.commit()


# ── Self-serve commands (any user, on their own data) ──────

# Match with or without the "Liriel," prefix and trailing punctuation.
RESET_PATTERN = re.compile(
    r"(?i)^(liriel\s*,?\s+)?resetar\s+conversa\s*[.!]?$"
)
WIPE_PATTERN = re.compile(
    r"(?i)^(liriel\s*,?\s+)?apagar\s+meus\s+dados\s*[.!]?$"
)

_REDIS_KEYS = [
    "liriel:buffer:{phone}",
    "liriel:timer:{phone}",
    "liriel:lock:{phone}",
    "liriel:typing:{phone}",
]


async def _clear_redis_state(phone: str) -> None:
    r = await get_redis()
    keys = [k.format(phone=phone) for k in _REDIS_KEYS]
    await r.delete(*keys)


async def parse_self_serve_command(message: str, phone: str) -> str | None:
    """Self-serve commands available to any user. Operates only on their own data.

    Returns response text if a command matched, None otherwise.
    """
    msg = message.strip()

    if RESET_PATTERN.match(msg):
        return await _reset_user_conversation(phone)

    if WIPE_PATTERN.match(msg):
        return await _wipe_user_data(phone)

    return None


async def _reset_user_conversation(phone: str) -> str:
    """Archive any active conversation; preserve the contact and their data."""
    async with async_session() as db:
        contact = (await db.execute(
            select(Contact).where(Contact.phone == phone)
        )).scalar_one_or_none()

        if not contact:
            await _clear_redis_state(phone)
            return "Você ainda não tem conversa registrada por aqui 😊 Pode mandar uma mensagem que a gente começa do zero 💜"

        active = (await db.execute(
            select(Conversation).where(
                Conversation.contact_id == contact.id,
                Conversation.is_active == True,
            )
        )).scalars().all()

        archived = 0
        for conv in active:
            conv.is_active = False
            archived += 1
        await db.commit()

    await _clear_redis_state(phone)
    logger.info(f"Self-serve reset for {phone} ({archived} conversations archived)")
    return (
        "Pronto, esqueci o que a gente conversou 💜\n\n"
        "Manda uma nova mensagem que a gente começa do zero. Seus dados de cadastro foram mantidos 😊"
    )


async def _wipe_user_data(phone: str) -> str:
    """Delete contact + all related data (messages, conversations, notifications)."""
    async with async_session() as db:
        contact = (await db.execute(
            select(Contact).where(Contact.phone == phone)
        )).scalar_one_or_none()

        if not contact:
            await _clear_redis_state(phone)
            return "Você não tinha nada cadastrado por aqui ainda 😊 Pode mandar uma mensagem quando quiser 💜"

        # Delete in FK-safe order: messages → conversations → notifications → contact
        conv_ids = (await db.execute(
            select(Conversation.id).where(Conversation.contact_id == contact.id)
        )).scalars().all()

        if conv_ids:
            await db.execute(
                delete(Message).where(Message.conversation_id.in_(conv_ids))
            )
            await db.execute(
                delete(Conversation).where(Conversation.id.in_(conv_ids))
            )

        await db.execute(
            delete(NotificationLog).where(NotificationLog.contact_phone == phone)
        )
        await db.execute(delete(Contact).where(Contact.id == contact.id))
        await db.commit()

    await _clear_redis_state(phone)
    logger.info(f"Self-serve wipe for {phone} (contact + {len(conv_ids)} conversations deleted)")
    return (
        "Apaguei tudo. Da próxima vez que você mandar mensagem, vou te receber como nova pessoa 💜"
    )


# ── Admin commands ─────────────────────────────────────────


async def parse_admin_command(message: str, admin_phone: str) -> str | None:
    """Parse and execute admin commands.

    Returns response text if it was a command, None if not a command.
    """
    msg = message.strip()

    # Check if it starts with "Liriel," (case-insensitive)
    if not re.match(r"(?i)^liriel\s*,", msg):
        return None

    # Remove the "Liriel," prefix
    command_text = re.sub(r"(?i)^liriel\s*,\s*", "", msg).strip()

    # ── Add event ──
    add_match = re.match(r"(?i)adicionar evento\s*:\s*(.+)", command_text)
    if add_match:
        return await _handle_add_event(add_match.group(1).strip(), admin_phone)

    # ── Remove event ──
    remove_match = re.match(r"(?i)remover evento\s*:\s*(.+)", command_text)
    if remove_match:
        return await _handle_remove_event(remove_match.group(1).strip())

    # ── List events ──
    if re.match(r"(?i)listar eventos", command_text):
        return await _handle_list_events()

    return None


async def _handle_add_event(raw: str, admin_phone: str) -> str:
    """Parse: Nome, DD/MM/YYYY, HHh às HHh, Local, Descrição"""
    parts = [p.strip() for p in raw.split(",")]

    if len(parts) < 2:
        return (
            "Formato: Liriel, adicionar evento: Nome, DD/MM/YYYY, "
            "HHh às HHh, Local, Descrição"
        )

    name = parts[0]

    # Parse date
    event_date = _parse_date(parts[1])
    if not event_date:
        return f"Data inválida: '{parts[1]}'. Use o formato DD/MM/YYYY."

    # Parse times (optional)
    start_time = ""
    end_time = ""
    if len(parts) >= 3:
        time_str = parts[2]
        time_parts = re.split(r"\s+(?:às|a|até|-)\s+", time_str, maxsplit=1)
        start_time = time_parts[0].strip()
        if len(time_parts) > 1:
            end_time = time_parts[1].strip()

    # Location (optional)
    location = parts[3] if len(parts) >= 4 else ""

    # Description (optional, everything after location)
    description = ", ".join(parts[4:]) if len(parts) >= 5 else ""

    result = await add_event(
        name=name,
        event_date=event_date,
        start_time=start_time,
        end_time=end_time,
        location=location,
        description=description,
        created_by=admin_phone,
    )

    if result:
        time_display = start_time
        if end_time:
            time_display += f" às {end_time}"

        response = f"Evento cadastrado com sucesso! ✅\n\n*{name}*\n📅 {parts[1]}"
        if time_display:
            response += f", {time_display}"
        if location:
            response += f"\n📍 {location}"
        if description:
            response += f"\n📝 {description}"
        return response
    else:
        return "Ocorreu um erro ao cadastrar o evento. Tente novamente."


async def _handle_remove_event(name: str) -> str:
    """Remove event by name."""
    success = await remove_event(name)
    if success:
        return f"Evento *{name}* removido com sucesso! ✅"
    else:
        return f"Evento '{name}' não encontrado nos eventos futuros."


async def _handle_list_events() -> str:
    """List all future events."""
    events = await list_future_events(days_ahead=180)
    if not events:
        return "Nenhum evento futuro cadastrado no momento."

    lines = ["📅 *Eventos futuros:*\n"]
    for e in events:
        line = f"• *{e['name']}* — {e['date']}"
        if e["start_time"]:
            line += f", {e['start_time']}"
            if e["end_time"]:
                line += f" às {e['end_time']}"
        if e["location"]:
            line += f" — {e['location']}"
        lines.append(line)

    return "\n".join(lines)


def _parse_date(text: str) -> date | None:
    """Parse various date formats."""
    text = text.strip()
    formats = ["%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%d/%m/%y"]

    for fmt in formats:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue

    return None
