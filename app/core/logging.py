import sys
from loguru import logger
from app.core.config import get_settings


def setup_logging():
    settings = get_settings()

    logger.remove()

    log_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
        "<level>{message}</level>"
    )

    logger.add(
        sys.stdout,
        format=log_format,
        level=settings.log_level,
        colorize=True,
    )

    logger.add(
        "logs/liriel.log",
        rotation="10 MB",
        retention="7 days",
        compression="gz",
        format=log_format,
        level=settings.log_level,
    )

    return logger
