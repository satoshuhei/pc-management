from __future__ import annotations

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo


FLASH_KEY = "flashes"
JST = ZoneInfo("Asia/Tokyo")


def add_flash(session: dict[str, Any], level: str, message: str) -> None:
    flashes = session.get(FLASH_KEY, [])
    flashes.insert(0, {"level": level, "message": message})
    session[FLASH_KEY] = flashes


def consume_flash(session: dict[str, Any]) -> list[dict[str, str]]:
    flashes = session.get(FLASH_KEY, [])
    session[FLASH_KEY] = []
    return flashes


def to_jst(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=JST)
    return dt.astimezone(JST)


def format_jst(dt: datetime | None, fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    jst_dt = to_jst(dt)
    if jst_dt is None:
        return ""
    return jst_dt.strftime(fmt)
