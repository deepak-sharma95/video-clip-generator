"""
ClipGenius - Logging Configuration
====================================
Uses loguru for beautiful, structured logging with file + console output.
"""

import sys
from pathlib import Path
from loguru import logger

from backend.config import Config


def setup_logger() -> None:
    """
    Configure the application logger.
    
    - Console output: coloured, human-readable
    - File output: structured, rotated daily, kept for 7 days
    """
    # Remove default loguru handler
    logger.remove()

    # Console handler — colourful output with rich formatting
    logger.add(
        sys.stderr,
        level=Config.LOG_LEVEL,
        format=(
            "<green>{time:HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
            "<level>{message}</level>"
        ),
        colorize=True,
    )

    # File handler — detailed logs for debugging
    log_dir = Config.PROJECT_ROOT / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    logger.add(
        str(log_dir / "clipgenius_{time:YYYY-MM-DD}.log"),
        level="DEBUG",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} | {message}",
        rotation="1 day",
        retention="7 days",
        compression="zip",
    )

    logger.info(f"Logger initialised — level={Config.LOG_LEVEL}")


# Export the configured logger for use across the application
__all__ = ["logger", "setup_logger"]
