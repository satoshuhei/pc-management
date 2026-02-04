from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.db import get_db
from app.models import PcPlan, PlanStatus
from app.plan_rules import PlanValidationError, validate_plan_integrity
from app.utils import add_flash, consume_flash

router = APIRouter()


def _parse_date(value: str | None) -> date | None:
    if value is None:
        return None
    text = value.strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def _parse_required_int(value: str | None) -> int:
    if value is None:
        return 0
    text = value.strip()
    if not text or not text.isdigit():
        return 0
    number = int(text)
    return number if number > 0 else 0

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


def _render_plan_form(
    request: Request,
    *,
    plan: PcPlan,
    action: str,
    title: str,
):
    flashes = consume_flash(request.session)
    return request.app.state.templates.TemplateResponse(
        request,
        "plan_form.html",
        {
            "flashes": flashes,
            "plan": plan,
            "action": action,
            "title": title,
            "statuses": [status.value for status in PlanStatus],
        },
    )


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


@router.get("/plans/new")
async def plan_new(request: Request):
    plan = PcPlan(
        entity_type="ASSET",
        entity_id=0,
        title="",
        planned_date=None,
        planned_owner=None,
        plan_status=PlanStatus.PLANNED,
        actual_date=None,
        actual_owner=None,
        result_note=None,
        created_by=request.session.get("user_id") or "system",
    )
    return _render_plan_form(
        request,
        plan=plan,
        action="/plans",
        title="予定登録",
    )


@router.post("/plans")
async def plan_create(
    request: Request,
    entity_type: str = Form("ASSET"),
    entity_id: str = Form(""),
    title: str = Form(""),
    planned_date: str | None = Form(None),
    planned_owner: str | None = Form(None),
    plan_status: str = Form("PLANNED"),
    actual_date: str | None = Form(None),
    actual_owner: str | None = Form(None),
    result_note: str | None = Form(None),
    db: Session = Depends(get_db),
):
    plan = PcPlan(
        entity_type=entity_type.strip() or "ASSET",
        entity_id=_parse_required_int(entity_id),
        title=title,
        planned_date=_parse_date(planned_date),
        planned_owner=planned_owner,
        plan_status=PlanStatus(plan_status),
        actual_date=_parse_date(actual_date),
        actual_owner=actual_owner,
        result_note=result_note,
        created_by=request.session.get("user_id") or "system",
    )
    try:
        validate_plan_integrity(
            title=plan.title,
            plan_status=plan.plan_status,
            actual_date=plan.actual_date,
            actual_owner=plan.actual_owner,
        )
    except PlanValidationError as exc:
        add_flash(request.session, "error", str(exc))
        return _render_plan_form(
            request,
            plan=plan,
            action="/plans",
            title="予定登録",
        )

    if plan.entity_id == 0:
        add_flash(request.session, "error", "対象IDを入力してください。")
        return _render_plan_form(
            request,
            plan=plan,
            action="/plans",
            title="予定登録",
        )

    db.add(plan)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        add_flash(request.session, "error", "予定の登録に失敗しました。")
        return _render_plan_form(
            request,
            plan=plan,
            action="/plans",
            title="予定登録",
        )

    add_flash(request.session, "success", "予定を登録しました。")
    return RedirectResponse(url=f"/plans/{plan.id}", status_code=303)


@router.get("/plans/{plan_id}/edit")
async def plan_edit(request: Request, plan_id: int, db: Session = Depends(get_db)):
    plan = db.query(PcPlan).filter(PcPlan.id == plan_id).first()
    if plan is None:
        add_flash(request.session, "error", "対象の予定が見つかりません。")
        return RedirectResponse(url="/plans/overdue", status_code=303)
    return _render_plan_form(
        request,
        plan=plan,
        action=f"/plans/{plan_id}/edit",
        title="予定編集",
    )


@router.post("/plans/{plan_id}/edit")
async def plan_update(
    request: Request,
    plan_id: int,
    entity_type: str = Form("ASSET"),
    entity_id: str = Form(""),
    title: str = Form(""),
    planned_date: str | None = Form(None),
    planned_owner: str | None = Form(None),
    plan_status: str = Form("PLANNED"),
    actual_date: str | None = Form(None),
    actual_owner: str | None = Form(None),
    result_note: str | None = Form(None),
    db: Session = Depends(get_db),
):
    plan = db.query(PcPlan).filter(PcPlan.id == plan_id).first()
    if plan is None:
        add_flash(request.session, "error", "対象の予定が見つかりません。")
        return RedirectResponse(url="/plans/overdue", status_code=303)

    plan.entity_type = entity_type.strip() or "ASSET"
    plan.entity_id = _parse_required_int(entity_id)
    plan.title = title
    plan.planned_date = _parse_date(planned_date)
    plan.planned_owner = planned_owner
    plan.plan_status = PlanStatus(plan_status)
    plan.actual_date = _parse_date(actual_date)
    plan.actual_owner = actual_owner
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
        return _render_plan_form(
            request,
            plan=plan,
            action=f"/plans/{plan_id}/edit",
            title="予定編集",
        )

    if plan.entity_id == 0:
        add_flash(request.session, "error", "対象IDを入力してください。")
        return _render_plan_form(
            request,
            plan=plan,
            action=f"/plans/{plan_id}/edit",
            title="予定編集",
        )

    plan.updated_at = datetime.now(timezone.utc)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        add_flash(request.session, "error", "予定の更新に失敗しました。")
        return _render_plan_form(
            request,
            plan=plan,
            action=f"/plans/{plan_id}/edit",
            title="予定編集",
        )

    add_flash(request.session, "success", "予定を更新しました。")
    return RedirectResponse(url=f"/plans/{plan.id}", status_code=303)


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


@router.post("/plans/{plan_id}/delete")
async def plan_delete(request: Request, plan_id: int, db: Session = Depends(get_db)):
    plan = db.query(PcPlan).filter(PcPlan.id == plan_id).first()
    if plan is None:
        add_flash(request.session, "error", "対象の予定が見つかりません。")
        return RedirectResponse(url="/plans/overdue", status_code=303)

    db.delete(plan)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        add_flash(request.session, "error", "予定を削除できませんでした。")
        return RedirectResponse(url=f"/plans/{plan_id}", status_code=303)

    add_flash(request.session, "success", "予定を削除しました。")
    return RedirectResponse(url="/plans/overdue", status_code=303)
