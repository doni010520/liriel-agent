"""
Message Buffer Service using Redis.

When a user sends multiple messages in sequence (common on WhatsApp),
we buffer them and wait for a pause before processing. This avoids
generating multiple GPT responses for fragmented messages.

Flow:
1. Message arrives → add to Redis list for that phone
2. Set/reset a processing timer key with TTL = BUFFER_DELAY_SECONDS
3. A background task checks for expired timers and processes the batch
"""

import asyncio
import json
import time

from loguru import logger

from app.core.config import get_settings
from app.core.redis import get_redis

settings = get_settings()

BUFFER_PREFIX = "liriel:buffer:"
TIMER_PREFIX = "liriel:timer:"
LOCK_PREFIX = "liriel:lock:"


async def add_to_buffer(phone: str, message: dict) -> int:
    """Add a message to the phone's buffer and reset the timer.

    Args:
        phone: WhatsApp phone number
        message: Dict with body, type, push_name, etc.

    Returns:
        Number of messages currently in buffer
    """
    r = await get_redis()
    buffer_key = f"{BUFFER_PREFIX}{phone}"
    timer_key = f"{TIMER_PREFIX}{phone}"

    # Add message to list
    msg_json = json.dumps(message, ensure_ascii=False)
    count = await r.rpush(buffer_key, msg_json)

    # Set buffer expiry (auto-cleanup if processing fails)
    await r.expire(buffer_key, 300)  # 5 min safety TTL

    # Reset the processing timer
    await r.set(timer_key, str(time.time()), ex=settings.buffer_delay_seconds)

    logger.debug(
        f"Buffer [{phone}]: {count} message(s), "
        f"timer reset to {settings.buffer_delay_seconds}s"
    )
    return count


async def get_buffered_messages(phone: str) -> list[dict]:
    """Retrieve and clear all buffered messages for a phone.

    Returns:
        List of message dicts
    """
    r = await get_redis()
    buffer_key = f"{BUFFER_PREFIX}{phone}"

    # Get all messages
    raw_messages = await r.lrange(buffer_key, 0, -1)

    # Clear buffer
    await r.delete(buffer_key)

    messages = []
    for raw in raw_messages:
        try:
            messages.append(json.loads(raw))
        except json.JSONDecodeError:
            logger.warning(f"Invalid JSON in buffer: {raw}")

    return messages


async def is_buffer_ready(phone: str) -> bool:
    """Check if the buffer timer has expired (user stopped typing).

    Returns True if timer expired and messages are waiting.
    """
    r = await get_redis()
    timer_key = f"{TIMER_PREFIX}{phone}"
    buffer_key = f"{BUFFER_PREFIX}{phone}"

    # Timer still active = user might still be typing
    timer_exists = await r.exists(timer_key)
    if timer_exists:
        return False

    # Check if there are messages to process
    buffer_len = await r.llen(buffer_key)
    return buffer_len > 0


async def acquire_processing_lock(phone: str, ttl: int = 60) -> bool:
    """Acquire a lock to prevent duplicate processing.

    Returns True if lock acquired, False if already locked.
    """
    r = await get_redis()
    lock_key = f"{LOCK_PREFIX}{phone}"
    acquired = await r.set(lock_key, "1", nx=True, ex=ttl)
    return bool(acquired)


async def release_processing_lock(phone: str):
    """Release the processing lock."""
    r = await get_redis()
    lock_key = f"{LOCK_PREFIX}{phone}"
    await r.delete(lock_key)


async def get_pending_phones() -> list[str]:
    """Get all phones with expired timers (ready to process).

    Scans for buffer keys that exist without a corresponding timer.
    """
    r = await get_redis()
    ready = []

    # Scan for buffer keys
    cursor = 0
    while True:
        cursor, keys = await r.scan(cursor, match=f"{BUFFER_PREFIX}*", count=100)
        for key in keys:
            phone = key.replace(BUFFER_PREFIX, "")
            if await is_buffer_ready(phone):
                ready.append(phone)

        if cursor == 0:
            break

    return ready


async def set_typing_indicator(phone: str):
    """Mark that we're 'typing' a response (prevents re-processing)."""
    r = await get_redis()
    await r.set(f"liriel:typing:{phone}", "1", ex=120)


async def is_typing(phone: str) -> bool:
    """Check if we're already generating a response for this phone."""
    r = await get_redis()
    return bool(await r.exists(f"liriel:typing:{phone}"))


async def clear_typing_indicator(phone: str):
    """Clear typing indicator."""
    r = await get_redis()
    await r.delete(f"liriel:typing:{phone}")
