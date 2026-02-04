from __future__ import annotations

import logging

from app.status_rules import is_allowed_asset_transition, is_allowed_request_transition


logger = logging.getLogger("transition")


class TransitionError(ValueError):
    pass


def apply_request_transition(
    *,
    from_status: str | None,
    to_status: str,
    actor: str,
) -> None:
    allowed = is_allowed_request_transition(from_status, to_status)
    if allowed:
        logger.info(
            "request transition from=%s to=%s actor=%s result=allowed",
            from_status,
            to_status,
            actor,
        )
        return

    logger.warning(
        "request transition from=%s to=%s actor=%s result=denied",
        from_status,
        to_status,
        actor,
    )
    raise TransitionError("要求の状態遷移が許可されていません。")


def apply_asset_transition(
    *,
    from_status: str | None,
    to_status: str,
    actor: str,
) -> None:
    allowed = is_allowed_asset_transition(from_status, to_status)
    if allowed:
        logger.info(
            "asset transition from=%s to=%s actor=%s result=allowed",
            from_status,
            to_status,
            actor,
        )
        return

    logger.warning(
        "asset transition from=%s to=%s actor=%s result=denied",
        from_status,
        to_status,
        actor,
    )
    raise TransitionError("資産の状態遷移が許可されていません。")
