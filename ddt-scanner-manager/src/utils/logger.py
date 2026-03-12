"""Application logging setup."""

import logging
import logging.handlers
from pathlib import Path

from src.config import LOGS_DIR, APP_NAME


def setup_logging() -> logging.Logger:
    """Configure and return the application logger (idempotent).

    Safe to call multiple times — handlers are added only once.

    Returns:
        Configured logger instance.
    """
    logger = logging.getLogger(APP_NAME)

    # Idempotency guard: skip if handlers are already attached
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)

    # File handler with rotation (max 5MB, keep 3 backups)
    log_file = LOGS_DIR / "app.log"
    file_handler = logging.handlers.RotatingFileHandler(
        log_file, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)

    # Formatter
    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger


def get_logger(name: str) -> logging.Logger:
    """Get a child logger.

    Args:
        name: Logger name (will be prefixed with APP_NAME).

    Returns:
        Child logger instance.
    """
    return logging.getLogger(f"{APP_NAME}.{name}")
