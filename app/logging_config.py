from __future__ import annotations

import logging
from logging.config import dictConfig
from pathlib import Path

from app.config import get_settings


def setup_logging() -> None:
    settings = get_settings()
    log_dir = Path("logs")
    log_dir.mkdir(parents=True, exist_ok=True)

    dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": {
                    "format": "%(asctime)s %(levelname)s %(name)s %(message)s",
                }
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "default",
                },
                "file": {
                    "class": "logging.handlers.RotatingFileHandler",
                    "formatter": "default",
                    "filename": str(log_dir / "app.log"),
                    "maxBytes": 5 * 1024 * 1024,
                    "backupCount": 5,
                    "encoding": "utf-8",
                },
            },
            "root": {
                "handlers": ["console", "file"],
                "level": settings.log_level,
            },
        }
    )

    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
