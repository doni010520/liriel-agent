"""
Liriel Agent - WhatsApp AI Assistant
FastAPI application entry point.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from loguru import logger

from app.api.admin import router as admin_router
from app.api.health import router as health_router
from app.api.webhook import router as webhook_router
from app.core.config import get_settings
from app.core.database import engine, Base, apply_schema_migrations
from app.core.logging import setup_logging
from app.core.redis import close_redis
from app.models.models import Contact, Conversation, Message, KnowledgeBase, Event, NotificationLog  # noqa
from app.services.admin_commands import bootstrap_admins
from app.services.rag_service import setup_pgvector, seed_if_empty
from app.services.events_service import (
    setup_events_pgvector,
    cleanup_past_events,
    seed_sample_events_if_empty,
)


settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    setup_logging()
    logger.info("🚀 Liriel Agent starting...")

    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Patch existing tables with new columns (idempotent)
    await apply_schema_migrations()

    # Setup pgvector for knowledge base and events
    await setup_pgvector()
    await setup_events_pgvector()

    # Seed knowledge base on first boot (idempotent — no-op if already seeded)
    await seed_if_empty()

    # Seed sample events on first boot (idempotent — no-op if any future event exists)
    await seed_sample_events_if_empty()

    # Promote configured admin phone numbers (idempotent)
    await bootstrap_admins()

    # Cleanup past events
    await cleanup_past_events()

    logger.info("✅ Database, pgvector, events ready")
    logger.info(f"📡 Webhook: POST /webhook/uazapi")
    logger.info(f"🔧 Admin panel: GET /admin/panel")
    logger.info(f"🤖 Model: {settings.openai_model}")

    yield

    # Shutdown
    logger.info("Shutting down...")
    await close_redis()
    await engine.dispose()
    logger.info("👋 Liriel Agent stopped")


app = FastAPI(
    title="Liriel Agent",
    description="WhatsApp AI Assistant powered by GPT",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.app_env != "production" else None,
    redoc_url=None,
)

# Routes
app.include_router(health_router)
app.include_router(webhook_router)
app.include_router(admin_router)


@app.get("/")
async def root():
    return {"agent": "Liriel", "status": "running"}
