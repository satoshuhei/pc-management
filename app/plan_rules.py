from __future__ import annotations

from datetime import date
from typing import Iterable

from app.models import PlanStatus


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
        raise PlanValidationError("タイトルは必須です。入力してください。")

    status_value = plan_status.value if isinstance(plan_status, PlanStatus) else plan_status

    if status_value == PlanStatus.DONE.value:
        if actual_date is None:
            raise PlanValidationError("完了時は実績日を入力してください。")
    elif status_value in (PlanStatus.PLANNED.value, PlanStatus.CANCELLED.value):
        if actual_date is not None or actual_owner:
            raise PlanValidationError("未完了の予定では実績情報を入力しないでください。")
