from datetime import date

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import PcPlan, PlanStatus
from app.plan_rules import PlanValidationError, validate_plan_integrity
from app.utils import add_flash, consume_flash

router = APIRouter()

def _build_plans_context(
    request: Request,
    db: Session,
    planned_owner: str | None,
    title: str | None,
):
    today = date.today()
    query = (
        db.query(PcPlan)
        .filter(PcPlan.plan_status == PlanStatus.PLANNED)
        .filter(PcPlan.planned_date.isnot(None))
        .filter(PcPlan.planned_date < today)
    )
    if planned_owner:
        query = query.filter(PcPlan.planned_owner.contains(planned_owner))
    if title:
        query = query.filter(PcPlan.title.contains(title))

    plans = query.order_by(PcPlan.planned_date.asc(), PcPlan.id.desc()).limit(200).all()

    return {
        "plans": plans,
        "today": today,
        "filters": {
            "planned_owner": planned_owner or "",
            "title": title or "",
        },
    }


@router.get("/plans/overdue")
async def plans_overdue(
    request: Request,
    planned_owner: str | None = None,
    title: str | None = None,
    db: Session = Depends(get_db),
):
    if planned_owner or title:
        add_flash(request.session, "success", "検索条件を適用しました。")

    flashes = consume_flash(request.session)
    context = _build_plans_context(request, db, planned_owner, title)
    return request.app.state.templates.TemplateResponse(
        request,
        "plans_overdue.html",
        {
            "flashes": flashes,
            **context,
        },
    )


@router.post("/plans/{plan_id}/done")
async def plan_done(
    request: Request,
    plan_id: int,
    result_note: str | None = Form(None),
    db: Session = Depends(get_db),
):
    plan = db.query(PcPlan).filter(PcPlan.id == plan_id).first()
    if plan is None:
        add_flash(request.session, "error", "対象の予定が見つかりません。")
        return RedirectResponse(url="/plans/overdue", status_code=303)

    actor = request.session.get("user_id") or "system"
    plan.plan_status = PlanStatus.DONE
    plan.actual_date = date.today()
    plan.actual_owner = actor
    if result_note is not None:
        plan.result_note = result_note

    try:
        validate_plan_integrity(
            title=plan.title,
            plan_status=plan.plan_status,
            actual_date=plan.actual_date,
            actual_owner=plan.actual_owner,
        )
    except PlanValidationError as exc:
        add_flash(request.session, "error", str(exc))
        flashes = consume_flash(request.session)
        context = _build_plans_context(request, db, None, None)
        return request.app.state.templates.TemplateResponse(
            request,
            "plans_overdue.html",
            {"flashes": flashes, **context},
            status_code=409,
        )

    db.commit()
    add_flash(request.session, "success", "予定を完了にしました。")
    return RedirectResponse(url="/plans/overdue", status_code=303)


@router.get("/plans/{plan_id}")
async def plan_detail(request: Request, plan_id: int, db: Session = Depends(get_db)):
    plan = db.query(PcPlan).filter(PcPlan.id == plan_id).first()
    if plan is None:
        add_flash(request.session, "error", "対象の予定が見つかりません。")
        return RedirectResponse(url="/plans/overdue", status_code=303)

    flashes = consume_flash(request.session)
    return request.app.state.templates.TemplateResponse(
        request,
        "plan_detail.html",
        {
            "flashes": flashes,
            "plan": plan,
        },
    )
