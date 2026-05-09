"""
Events Service.

CRUD for church events with hybrid search:
- SQL filtering by date (only future events)
- Semantic search via pgvector (fuzzy name matching)
- Auto-cleanup of past events
"""

from datetime import date, datetime, timedelta

from loguru import logger
from sqlalchemy import text, select, delete

from app.core.database import async_session, engine
from app.models.models import Event
from app.services.rag_service import generate_embedding

EMBEDDING_DIMENSIONS = 1536


async def setup_events_pgvector():
    """Add embedding column to events table if it doesn't exist."""
    async with engine.begin() as conn:
        await conn.execute(text("""
            DO $$
            BEGIN
                IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'events')
                   AND NOT EXISTS (SELECT 1 FROM information_schema.columns
                                   WHERE table_name = 'events' AND column_name = 'embedding')
                THEN
                    ALTER TABLE events ADD COLUMN embedding vector(1536);
                END IF;
            END $$;
        """))
    logger.info("Events pgvector column ready")


async def add_event(
    name: str,
    event_date: date,
    start_time: str = "",
    end_time: str = "",
    location: str = "",
    description: str = "",
    created_by: str = "",
) -> Event | None:
    """Create a new event with embedding for semantic search."""
    try:
        # Generate embedding from name + description for fuzzy matching
        search_text = f"{name} {description}".strip()
        embedding = await generate_embedding(search_text)
        embedding_str = "[" + ",".join(str(x) for x in embedding) + "]" if embedding else None

        async with async_session() as db:
            if embedding_str:
                result = await db.execute(
                    text("""
                        INSERT INTO events (id, name, description, event_date, start_time, end_time, 
                                           location, created_by, is_active, embedding, created_at)
                        VALUES (gen_random_uuid(), :name, :description, :event_date, :start_time, 
                                :end_time, :location, :created_by, true, :embedding::vector, now())
                        RETURNING id
                    """),
                    {
                        "name": name,
                        "description": description or "",
                        "event_date": event_date,
                        "start_time": start_time,
                        "end_time": end_time,
                        "location": location,
                        "created_by": created_by,
                        "embedding": embedding_str,
                    },
                )
            else:
                result = await db.execute(
                    text("""
                        INSERT INTO events (id, name, description, event_date, start_time, end_time,
                                           location, created_by, is_active, created_at)
                        VALUES (gen_random_uuid(), :name, :description, :event_date, :start_time,
                                :end_time, :location, :created_by, true, now())
                        RETURNING id
                    """),
                    {
                        "name": name,
                        "description": description or "",
                        "event_date": event_date,
                        "start_time": start_time,
                        "end_time": end_time,
                        "location": location,
                        "created_by": created_by,
                    },
                )
            await db.commit()
            event_id = result.scalar()
            logger.info(f"Event created: {name} on {event_date} (id: {event_id})")
            return event_id

    except Exception as e:
        logger.error(f"Error creating event: {e}")
        return None


async def remove_event(name: str) -> bool:
    """Remove event by name (case-insensitive partial match)."""
    try:
        async with async_session() as db:
            result = await db.execute(
                text("""
                    DELETE FROM events 
                    WHERE LOWER(name) LIKE LOWER(:pattern) AND is_active = true
                    RETURNING id
                """),
                {"pattern": f"%{name}%"},
            )
            await db.commit()
            deleted = result.fetchall()
            if deleted:
                logger.info(f"Removed {len(deleted)} event(s) matching '{name}'")
                return True
            logger.warning(f"No events found matching '{name}'")
            return False
    except Exception as e:
        logger.error(f"Error removing event: {e}")
        return False


async def list_future_events(days_ahead: int = 90) -> list[dict]:
    """List all future events within the given window."""
    try:
        today = date.today()
        limit_date = today + timedelta(days=days_ahead)

        async with async_session() as db:
            result = await db.execute(
                text("""
                    SELECT name, description, event_date, start_time, end_time, location
                    FROM events
                    WHERE is_active = true AND event_date >= :today AND event_date <= :limit
                    ORDER BY event_date ASC
                """),
                {"today": today, "limit": limit_date},
            )
            rows = result.fetchall()

        return [
            {
                "name": r.name,
                "description": r.description,
                "date": r.event_date.strftime("%d/%m/%Y"),
                "start_time": r.start_time or "",
                "end_time": r.end_time or "",
                "location": r.location or "",
            }
            for r in rows
        ]
    except Exception as e:
        logger.error(f"Error listing events: {e}")
        return []


async def search_events(query: str, days_ahead: int = 120) -> list[dict]:
    """Hybrid search: semantic similarity + date filter.

    Finds events even when the user uses approximate names.
    """
    try:
        today = date.today()
        limit_date = today + timedelta(days=days_ahead)

        embedding = await generate_embedding(query)
        if not embedding:
            # Fallback to simple text search
            return await _text_search_events(query, today, limit_date)

        embedding_str = "[" + ",".join(str(x) for x in embedding) + "]"

        async with async_session() as db:
            result = await db.execute(
                text("""
                    SELECT name, description, event_date, start_time, end_time, location,
                           1 - (embedding <=> :embedding::vector) as similarity
                    FROM events
                    WHERE is_active = true 
                      AND event_date >= :today 
                      AND event_date <= :limit
                      AND embedding IS NOT NULL
                    ORDER BY embedding <=> :embedding::vector
                    LIMIT 5
                """),
                {
                    "embedding": embedding_str,
                    "today": today,
                    "limit": limit_date,
                },
            )
            rows = result.fetchall()

        results = []
        for r in rows:
            similarity = float(r.similarity)
            if similarity > 0.25:  # Lower threshold for events
                results.append({
                    "name": r.name,
                    "description": r.description,
                    "date": r.event_date.strftime("%d/%m/%Y"),
                    "start_time": r.start_time or "",
                    "end_time": r.end_time or "",
                    "location": r.location or "",
                    "similarity": similarity,
                })

        # If semantic search found nothing, try text search
        if not results:
            results = await _text_search_events(query, today, limit_date)

        logger.debug(f"Event search '{query}' → {len(results)} results")
        return results

    except Exception as e:
        logger.error(f"Event search error: {e}")
        return []


async def _text_search_events(
    query: str, start: date, end: date
) -> list[dict]:
    """Fallback text search for events."""
    try:
        async with async_session() as db:
            result = await db.execute(
                text("""
                    SELECT name, description, event_date, start_time, end_time, location
                    FROM events
                    WHERE is_active = true
                      AND event_date >= :start AND event_date <= :end
                      AND (LOWER(name) LIKE LOWER(:pattern) 
                           OR LOWER(description) LIKE LOWER(:pattern))
                    ORDER BY event_date ASC
                    LIMIT 5
                """),
                {"start": start, "end": end, "pattern": f"%{query}%"},
            )
            rows = result.fetchall()

        return [
            {
                "name": r.name,
                "description": r.description,
                "date": r.event_date.strftime("%d/%m/%Y"),
                "start_time": r.start_time or "",
                "end_time": r.end_time or "",
                "location": r.location or "",
            }
            for r in rows
        ]
    except Exception as e:
        logger.error(f"Text search events error: {e}")
        return []


async def cleanup_past_events():
    """Remove events that have already passed. Run daily."""
    try:
        yesterday = date.today() - timedelta(days=1)
        async with async_session() as db:
            result = await db.execute(
                text("""
                    DELETE FROM events WHERE event_date < :yesterday
                    RETURNING id
                """),
                {"yesterday": yesterday},
            )
            await db.commit()
            deleted = result.fetchall()
            if deleted:
                logger.info(f"Cleaned up {len(deleted)} past event(s)")
    except Exception as e:
        logger.error(f"Event cleanup error: {e}")


def format_events_context(events: list[dict]) -> str:
    """Format events for injection into the system prompt."""
    if not events:
        return "Nenhum evento cadastrado no momento."

    lines = []
    for e in events:
        time_str = ""
        if e["start_time"]:
            time_str = f", {e['start_time']}"
            if e["end_time"]:
                time_str += f" às {e['end_time']}"

        loc_str = f", {e['location']}" if e["location"] else ""
        desc_str = f" — {e['description']}" if e.get("description") else ""

        lines.append(f"- {e['name']}: {e['date']}{time_str}{loc_str}{desc_str}")

    return "\n".join(lines)
