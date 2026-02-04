from __future__ import annotations

from datetime import date
from typing import Iterable

import logging

from app.models import PlanStatus


logger = logging.getLogger("plan")


class PlanValidationError(ValueError):
    pass


def validate_plan_integrity(
    *,
    title: str | None,
    plan_status: PlanStatus | str,
    actual_date: date | None,
    actual_owner: str | None,
) -> None:
    normalized_title = (title or "").strip()
    if not normalized_title:
        logger.warning("plan validation failed reason=title_required")
        raise PlanValidationError("タイトルは必須です。入力してください。")

    status_value = plan_status.value if isinstance(plan_status, PlanStatus) else plan_status

    if status_value == PlanStatus.DONE.value:
        if actual_date is None:
            logger.warning("plan validation failed status=%s reason=actual_date_required", status_value)
            raise PlanValidationError("完了時は実績日を入力してください。")
    elif status_value in (PlanStatus.PLANNED.value, PlanStatus.CANCELLED.value):
        if actual_date is not None or actual_owner:
            logger.warning("plan validation failed status=%s reason=actuals_not_allowed", status_value)
            raise PlanValidationError("未完了の予定では実績情報を入力しないでください。")

    logger.info("plan validation ok status=%s", status_value)
