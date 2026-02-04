from __future__ import annotations

from typing import Iterable


REQUEST_STATUSES: set[str] = {"RQ", "OP", "RP"}
ASSET_STATUSES: set[str] = {"INV", "READY", "USE", "RET", "IT", "DIS", "AUD", "LOST"}


REQUEST_ALLOWED: set[tuple[str, str]] = {
    ("NR", "RQ"),
    ("RQ", "OP"),
    ("OP", "RP"),
}

ASSET_ALLOWED: set[tuple[str, str]] = {
    ("INV", "READY"),
    ("READY", "USE"),
    ("USE", "RET"),
    ("RET", "INV"),
    ("RET", "IT"),
    ("RET", "DIS"),
    ("IT", "READY"),
}

ASSET_AUDIT_ALLOWED_FROM: set[str] = {"INV", "READY", "USE", "RET", "IT", "DIS", "LOST"}
ASSET_AUDIT_ALLOWED_TO: set[str] = {"USE", "INV", "RET", "IT", "DIS", "LOST"}
ASSET_LOST_RECOVERY: set[tuple[str, str]] = {
    ("LOST", "USE"),
    ("LOST", "RET"),
    ("LOST", "IT"),
    ("LOST", "DIS"),
}
ASSET_CREATE_ALLOWED_TO: set[str] = {"INV", "USE", "RET", "IT", "DIS", "LOST"}


def _normalize_status(value: str | None) -> str:
    return "NR" if value in (None, "", "NR") else value


def is_allowed_request_transition(from_status: str | None, to_status: str) -> bool:
    normalized_from = _normalize_status(from_status)
    if to_status not in REQUEST_STATUSES:
        return False
    return (normalized_from, to_status) in REQUEST_ALLOWED


def is_allowed_asset_transition(from_status: str | None, to_status: str) -> bool:
    normalized_from = _normalize_status(from_status)
    if to_status not in ASSET_STATUSES:
        return False

    if normalized_from == "NR":
        return to_status in ASSET_CREATE_ALLOWED_TO

    if (normalized_from, to_status) in ASSET_ALLOWED:
        return True

    if normalized_from in ASSET_AUDIT_ALLOWED_FROM and to_status == "AUD":
        return True

    if normalized_from == "AUD" and to_status in ASSET_AUDIT_ALLOWED_TO:
        return True

    if (normalized_from, to_status) in ASSET_LOST_RECOVERY:
        return True

    return False


def list_allowed_request_targets(from_status: str | None) -> list[str]:
    normalized_from = _normalize_status(from_status)
    return sorted({to_status for f, to_status in REQUEST_ALLOWED if f == normalized_from})


def list_allowed_asset_targets(from_status: str | None) -> list[str]:
    normalized_from = _normalize_status(from_status)
    allowed: set[str] = set()

    if normalized_from == "NR":
        allowed.update(ASSET_CREATE_ALLOWED_TO)
        return sorted(allowed)

    for f, to_status in ASSET_ALLOWED:
        if f == normalized_from:
            allowed.add(to_status)

    if normalized_from in ASSET_AUDIT_ALLOWED_FROM:
        allowed.add("AUD")

    if normalized_from == "AUD":
        allowed.update(ASSET_AUDIT_ALLOWED_TO)

    for f, to_status in ASSET_LOST_RECOVERY:
        if f == normalized_from:
            allowed.add(to_status)

    return sorted(allowed)
