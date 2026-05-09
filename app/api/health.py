"""
Health check and admin endpoints.
"""

from fastapi import APIRouter
from loguru import logger

from app.core.database import engine
from app.core.redis import get_redis
from app.schemas.schemas import HealthResponse

router = APIRouter(tags=["admin"])


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Check health of all services."""
    db_status = "ok"
    redis_status = "ok"

    # Check database
    try:
        async with engine.connect() as conn:
            await conn.execute(__import__("sqlalchemy").text("SELECT 1"))
    except Exception as e:
        db_status = f"error: {e}"
        logger.error(f"Health check DB error: {e}")

    # Check Redis
    try:
        r = await get_redis()
        await r.ping()
    except Exception as e:
        redis_status = f"error: {e}"
        logger.error(f"Health check Redis error: {e}")

    status = "healthy" if db_status == "ok" and redis_status == "ok" else "degraded"

    return HealthResponse(
        status=status,
        database=db_status,
        redis=redis_status,
    )
