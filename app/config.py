from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()

def _get_env(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    return value


@dataclass(frozen=True)
class Settings:
    database_url: str
    secret_key: str
    log_level: str


@lru_cache
def get_settings() -> Settings:
    return Settings(
        database_url=_get_env(
            "DATABASE_URL",
            "mysql+mysqlconnector://pc_user:pc_pass@localhost:3306/pc_management",
        ),
        secret_key=_get_env("SECRET_KEY", "change-this-secret") or "change-this-secret",
        log_level=_get_env("LOG_LEVEL", "INFO") or "INFO",
    )
