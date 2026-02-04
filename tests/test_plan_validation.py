from datetime import date

import pytest

from app.models import PlanStatus
from app.plan_rules import PlanValidationError, validate_plan_integrity


def test_plan_done_requires_actual_date():
    with pytest.raises(PlanValidationError):
        validate_plan_integrity(
            title="作業完了",
            plan_status=PlanStatus.DONE,
            actual_date=None,
            actual_owner="担当A",
        )


def test_plan_done_allows_actual_date():
    validate_plan_integrity(
        title="作業完了",
        plan_status=PlanStatus.DONE,
        actual_date=date.today(),
        actual_owner="担当A",
    )


def test_plan_planned_rejects_actuals():
    with pytest.raises(PlanValidationError):
        validate_plan_integrity(
            title="予定",
            plan_status=PlanStatus.PLANNED,
            actual_date=date.today(),
            actual_owner="担当A",
        )


def test_plan_cancelled_rejects_actuals():
    with pytest.raises(PlanValidationError):
        validate_plan_integrity(
            title="中止",
            plan_status=PlanStatus.CANCELLED,
            actual_date=date.today(),
            actual_owner=None,
        )


def test_plan_title_required():
    with pytest.raises(PlanValidationError):
        validate_plan_integrity(
            title=" ",
            plan_status=PlanStatus.PLANNED,
            actual_date=None,
            actual_owner=None,
        )
