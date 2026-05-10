from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings

settings = get_settings()

engine = create_async_engine(
    settings.database_url,
    echo=settings.app_env == "development",
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    pool_recycle=3600,
)

async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()


async def apply_schema_migrations() -> None:
    """Idempotent ALTER patches for tables created on older app versions.

    `Base.metadata.create_all` only creates missing tables — it does not
    add columns to existing ones. New columns added to models live here.
    """
    async with engine.begin() as conn:
        await conn.execute(text(
            "ALTER TABLE conversations "
            "ADD COLUMN IF NOT EXISTS summary TEXT, "
            "ADD COLUMN IF NOT EXISTS summary_message_count INTEGER NOT NULL DEFAULT 0"
        ))
