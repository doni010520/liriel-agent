"""
RAG Service — Knowledge Base Search.

Uses OpenAI text-embedding-3-small + PostgreSQL pgvector
for semantic search over church content (doctrines, membership, events, etc.)
"""

from openai import AsyncOpenAI
from loguru import logger
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import async_session, engine

settings = get_settings()
openai_client = AsyncOpenAI(api_key=settings.openai_api_key)

EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSIONS = 1536


async def seed_if_empty() -> int:
    """Seed the knowledge base on startup ONLY if it's empty.

    Idempotent: skips silently if any rows exist. Returns the number
    of entries inserted (0 if already seeded).
    """
    from app.services.knowledge_data import KNOWLEDGE_ENTRIES

    async with async_session() as session:
        result = await session.execute(text("SELECT COUNT(*) FROM knowledge_base"))
        count = result.scalar() or 0

    if count > 0:
        logger.info(f"Knowledge base already seeded ({count} entries) — skipping")
        return 0

    logger.info(f"Knowledge base empty — seeding {len(KNOWLEDGE_ENTRIES)} entries...")
    inserted = 0
    for category, title, content in KNOWLEDGE_ENTRIES:
        if await add_knowledge(category, title, content):
            inserted += 1
    logger.info(f"Knowledge base seeded ({inserted}/{len(KNOWLEDGE_ENTRIES)} entries)")
    return inserted


async def setup_pgvector():
    """Create pgvector extension and embedding column if they don't exist.
    Called on app startup.
    """
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        # Add embedding column if table exists but column doesn't
        await conn.execute(text("""
            DO $$
            BEGIN
                IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'knowledge_base')
                   AND NOT EXISTS (SELECT 1 FROM information_schema.columns 
                                   WHERE table_name = 'knowledge_base' AND column_name = 'embedding')
                THEN
                    ALTER TABLE knowledge_base ADD COLUMN embedding vector(1536);
                END IF;
            END $$;
        """))
        # Create index for fast similarity search
        await conn.execute(text("""
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'ix_knowledge_embedding')
                THEN
                    CREATE INDEX ix_knowledge_embedding ON knowledge_base 
                    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 10);
                END IF;
            EXCEPTION WHEN OTHERS THEN
                -- IVFFlat needs sufficient rows; skip if too few
                NULL;
            END $$;
        """))
    logger.info("pgvector extension and knowledge_base embedding column ready")


async def generate_embedding(text_input: str) -> list[float]:
    """Generate embedding vector for a text using OpenAI."""
    try:
        response = await openai_client.embeddings.create(
            model=EMBEDDING_MODEL,
            input=text_input,
        )
        return response.data[0].embedding
    except Exception as e:
        logger.error(f"Embedding generation error: {e}")
        return []


async def add_knowledge(
    category: str,
    title: str,
    content: str,
    db: AsyncSession | None = None,
) -> bool:
    """Add a knowledge entry with its embedding vector."""
    try:
        embedding = await generate_embedding(f"{title}\n{content}")
        if not embedding:
            logger.error(f"Failed to generate embedding for: {title}")
            return False

        embedding_str = "[" + ",".join(str(x) for x in embedding) + "]"

        async with (db or async_session()) as session:
            await session.execute(
                text("""
                    INSERT INTO knowledge_base (id, category, title, content, embedding, is_active, created_at, updated_at)
                    VALUES (gen_random_uuid(), :category, :title, :content, :embedding::vector, true, now(), now())
                """),
                {
                    "category": category,
                    "title": title,
                    "content": content,
                    "embedding": embedding_str,
                },
            )
            await session.commit()

        logger.info(f"Knowledge added: [{category}] {title}")
        return True

    except Exception as e:
        logger.error(f"Error adding knowledge: {e}")
        return False


async def search_knowledge(
    query: str,
    limit: int = 3,
    category: str | None = None,
) -> list[dict]:
    """Search knowledge base using semantic similarity.

    Args:
        query: User's question (in their own words)
        limit: Max results to return
        category: Optional filter by category

    Returns:
        List of {title, content, category, similarity} dicts
    """
    try:
        embedding = await generate_embedding(query)
        if not embedding:
            return []

        embedding_str = "[" + ",".join(str(x) for x in embedding) + "]"

        # Build query with optional category filter
        category_filter = "AND category = :category" if category else ""

        sql = text(f"""
            SELECT title, content, category,
                   1 - (embedding <=> :embedding::vector) as similarity
            FROM knowledge_base
            WHERE is_active = true {category_filter}
            ORDER BY embedding <=> :embedding::vector
            LIMIT :limit
        """)

        params = {"embedding": embedding_str, "limit": limit}
        if category:
            params["category"] = category

        async with async_session() as session:
            result = await session.execute(sql, params)
            rows = result.fetchall()

        results = []
        for row in rows:
            similarity = float(row.similarity)
            # Only include results with reasonable similarity
            if similarity > 0.3:
                results.append({
                    "title": row.title,
                    "content": row.content,
                    "category": row.category,
                    "similarity": similarity,
                })

        logger.debug(
            f"RAG search '{query[:50]}...' → {len(results)} results "
            f"(best: {results[0]['similarity']:.2f})" if results else
            f"RAG search '{query[:50]}...' → 0 results"
        )
        return results

    except Exception as e:
        logger.error(f"RAG search error: {e}")
        return []


def build_rag_context(results: list[dict]) -> str:
    """Format RAG results into context string for the system prompt."""
    if not results:
        return ""

    parts = []
    for r in results:
        parts.append(f"[{r['category'].upper()}] {r['title']}\n{r['content']}")

    return "\n\n---\n\n".join(parts)
