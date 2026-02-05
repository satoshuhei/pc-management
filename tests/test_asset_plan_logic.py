from datetime import date, timedelta

from app.models import PcPlan, PlanStatus
from app.routes.assets import _has_overdue_plan, _has_today_plan, _select_next_plans


def _plan(
    plan_id: int,
    planned_date: date | None,
    status: PlanStatus,
    owner: str | None = None,
):
    return PcPlan(
        id=plan_id,
        entity_type="ASSET",
        entity_id=1,
        title=f"plan-{plan_id}",
        planned_date=planned_date,
        planned_owner=owner,
        plan_status=status,
        actual_date=None,
        actual_owner=None,
        result_note=None,
        created_by="tester",
    )


def test_select_next_plan_uses_min_date_and_ignores_null():
    today = date.today()
    plans = [
        _plan(1, None, PlanStatus.PLANNED),
        _plan(2, today + timedelta(days=2), PlanStatus.PLANNED),
        _plan(3, today + timedelta(days=1), PlanStatus.DONE),
        _plan(4, today, PlanStatus.PLANNED),
        _plan(5, today + timedelta(days=3), PlanStatus.PLANNED),
        _plan(6, today + timedelta(days=4), PlanStatus.PLANNED),
    ]
    selected = _select_next_plans(plans, limit=3)
    assert [plan.id for plan in selected] == [4, 2, 5]


def test_overdue_and_today_flags():
    today = date.today()
    plans = [
        _plan(1, today - timedelta(days=1), PlanStatus.PLANNED),
        _plan(2, today, PlanStatus.PLANNED),
        _plan(3, today + timedelta(days=1), PlanStatus.PLANNED),
    ]
    assert _has_overdue_plan(plans, today) is True
    assert _has_today_plan(plans, today) is True
