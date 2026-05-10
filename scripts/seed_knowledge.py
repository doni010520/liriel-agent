"""
Seed the knowledge base with church content.

Run: python -m scripts.seed_knowledge

Wipes the table first (destructive). For idempotent boot-time seeding
the app uses `rag_service.seed_if_empty()` automatically; only run this
script when you want a full re-seed.
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text

from app.core.database import engine, Base
from app.models.models import KnowledgeBase  # noqa
from app.services.knowledge_data import KNOWLEDGE_ENTRIES
from app.services.rag_service import add_knowledge, setup_pgvector
from loguru import logger


async def main():
    """Wipe and reseed all knowledge entries."""
    logger.info("Setting up pgvector...")

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    await setup_pgvector()

    logger.info(f"Wiping and seeding {len(KNOWLEDGE_ENTRIES)} knowledge entries...")

    async with engine.begin() as conn:
        await conn.execute(text("DELETE FROM knowledge_base"))

    success = 0
    for category, title, content in KNOWLEDGE_ENTRIES:
        if await add_knowledge(category, title, content):
            success += 1
        else:
            logger.error(f"Failed: {title}")

    logger.info(f"Seeded {success}/{len(KNOWLEDGE_ENTRIES)} entries successfully")


if __name__ == "__main__":
    asyncio.run(main())
