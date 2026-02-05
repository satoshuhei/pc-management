from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import RedirectResponse
from sqlalchemy import or_
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.db import get_db
from app.models import (
    ASSET_STATUS_LABELS,
    PLAN_STATUS_LABELS,
    AssetStatus,
    PcAsset,
    PcPlan,
    PcStatusHistory,
    PlanStatus,
)
from app.plan_rules import PlanValidationError, validate_plan_integrity
from app.status_rules import list_allowed_asset_targets
from app.transition_service import TransitionError, apply_asset_transition
from app.utils import add_flash, consume_flash
from app.validation import ValidationError, validate_asset_integrity

router = APIRouter()

def _build_assets_context(
    request: Request,
    db: Session,
    status: str | None,
    asset_keyword: str | None,
    location: str | None,
    current_user: str | None,
    planned_owner: str | None,
    overdue_only: bool,
    today_only: bool,
    next_plan_limit: int,
):
    query = db.query(PcAsset)
    if status:
        query = query.filter(PcAsset.status == status)
    if asset_keyword:
        query = query.filter(
            or_(
                PcAsset.asset_tag.contains(asset_keyword),
                PcAsset.serial_no.contains(asset_keyword),
            )
        )
    if location:
        query = query.filter(PcAsset.location.contains(location))
    if current_user:
        query = query.filter(PcAsset.current_user.contains(current_user))

    assets = query.order_by(PcAsset.id.desc()).limit(200).all()

    asset_ids = [asset.id for asset in assets]
    plans_by_asset: dict[int, list[PcPlan]] = {asset_id: [] for asset_id in asset_ids}
    if asset_ids:
        plans = (
            db.query(PcPlan)
            .filter(PcPlan.entity_type == "ASSET")
            .filter(PcPlan.entity_id.in_(asset_ids))
            .all()
        )
        for plan in plans:
            plans_by_asset.setdefault(plan.entity_id, []).append(plan)

    today = date.today()
    next_plans: dict[int, list[PcPlan]] = {}
    overdue_flags: dict[int, bool] = {}
    today_flags: dict[int, bool] = {}

    for asset_id, plans in plans_by_asset.items():
        next_plans[asset_id] = _select_next_plans(plans, limit=next_plan_limit)
        overdue_flags[asset_id] = _has_overdue_plan(plans, today)
        today_flags[asset_id] = _has_today_plan(plans, today)

    filtered_assets: list[PcAsset] = []
    for asset in assets:
        plans = plans_by_asset.get(asset.id, [])
        if planned_owner:
            if not _matches_planned_owner(plans, planned_owner):
                continue
        if overdue_only and not overdue_flags.get(asset.id, False):
            continue
        if today_only and not today_flags.get(asset.id, False):
            continue
        filtered_assets.append(asset)

    if filtered_assets is not assets:
        asset_ids = [asset.id for asset in filtered_assets]
        next_plans = {asset_id: next_plans.get(asset_id, []) for asset_id in asset_ids}
        overdue_flags = {asset_id: overdue_flags.get(asset_id, False) for asset_id in asset_ids}
        today_flags = {asset_id: today_flags.get(asset_id, False) for asset_id in asset_ids}

    filter_summary = _build_filter_summary(
        status=status,
        asset_keyword=asset_keyword,
        location=location,
        current_user=current_user,
        planned_owner=planned_owner,
        overdue_only=overdue_only,
        today_only=today_only,
        next_plan_limit=next_plan_limit,
    )

    return {
        "assets": filtered_assets,
        "next_plans": next_plans,
        "overdue_flags": overdue_flags,
        "today_flags": today_flags,
        "today": today,
        "filters": {
            "status": status or "",
            "asset_keyword": asset_keyword or "",
            "location": location or "",
            "current_user": current_user or "",
            "planned_owner": planned_owner or "",
            "overdue_only": overdue_only,
            "today_only": today_only,
            "next_plan_limit": next_plan_limit,
        },
        "filter_summary": filter_summary,
    }


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


def _select_next_plans(plans: list[PcPlan], *, limit: int = 3) -> list[PcPlan]:
    candidates = [
        plan
        for plan in plans
        if plan.plan_status == PlanStatus.PLANNED and plan.planned_date is not None
    ]
    if not candidates:
        return []
    ordered = sorted(candidates, key=lambda plan: (plan.planned_date, plan.id or 0))
    return ordered[:limit]


def _has_overdue_plan(plans: list[PcPlan], today: date) -> bool:
    return any(
        plan.plan_status == PlanStatus.PLANNED
        and plan.planned_date is not None
        and plan.planned_date < today
        for plan in plans
    )


def _has_today_plan(plans: list[PcPlan], today: date) -> bool:
    return any(
        plan.plan_status == PlanStatus.PLANNED
        and plan.planned_date is not None
        and plan.planned_date == today
        for plan in plans
    )


def _matches_planned_owner(plans: list[PcPlan], planned_owner: str) -> bool:
    target = planned_owner.strip()
    if not target:
        return True
    return any(target in (plan.planned_owner or "") for plan in plans)


def _build_filter_summary(
    *,
    status: str | None,
    asset_keyword: str | None,
    location: str | None,
    current_user: str | None,
    planned_owner: str | None,
    overdue_only: bool,
    today_only: bool,
    next_plan_limit: int,
) -> list[str]:
    summary: list[str] = []
    if status:
        summary.append(f"状態={status}")
    if asset_keyword:
        summary.append(f"資産番号/シリアル={asset_keyword}")
    if current_user:
        summary.append(f"利用者={current_user}")
    if location:
        summary.append(f"拠点={location}")
    if planned_owner:
        summary.append(f"予定担当={planned_owner}")
    if overdue_only:
        summary.append("期限超過のみ")
    if today_only:
        summary.append("今日の予定のみ")
    summary.append(f"次予定{next_plan_limit}件")
    return summary


def _render_asset_form(
    request: Request,
    *,
    asset: PcAsset | None,
    action: str,
    title: str,
):
    flashes = consume_flash(request.session)
    return request.app.state.templates.TemplateResponse(
        request,
        "asset_form.html",
        {
            "flashes": flashes,
            "asset": asset,
            "action": action,
            "title": title,
            "statuses": [status.value for status in AssetStatus],
        },
    )


@router.get("/assets")
async def assets(
    request: Request,
    status: str | None = None,
    asset_keyword: str | None = None,
    location: str | None = None,
    current_user: str | None = None,
    planned_owner: str | None = None,
    overdue_only: bool = False,
    today_only: bool = False,
    next_plan_limit: int = 1,
    db: Session = Depends(get_db),
):
    safe_limit = max(1, min(3, next_plan_limit))
    if status or asset_keyword or location or current_user or planned_owner or overdue_only or today_only or next_plan_limit:
        add_flash(request.session, "success", "検索条件を適用しました。")

    flashes = consume_flash(request.session)
    context = _build_assets_context(
        request,
        db,
        status,
        asset_keyword,
        location,
        current_user,
        planned_owner,
        overdue_only,
        today_only,
        safe_limit,
    )
    return request.app.state.templates.TemplateResponse(
        request,
        "assets.html",
        {
            "flashes": flashes,
            **context,
            "status_labels": ASSET_STATUS_LABELS,
        },
    )


@router.post("/assets/{asset_id}/transition")
async def asset_transition(
    request: Request,
    asset_id: int,
    to_status: str = Form(...),
    reason: str | None = Form(None),
    db: Session = Depends(get_db),
):
    asset = db.query(PcAsset).filter(PcAsset.id == asset_id).first()
    if asset is None:
        add_flash(request.session, "error", "対象の資産が見つかりません。")
        return RedirectResponse(url="/assets", status_code=303)

    actor = request.session.get("user_id") or "system"

    from_status = asset.status
    try:
        apply_asset_transition(from_status=from_status, to_status=to_status, actor=actor)
    except TransitionError:
        add_flash(request.session, "error", "状態遷移が許可されていません。")
        flashes = consume_flash(request.session)
        context = _build_assets_context(
            request,
            db,
            None,
            None,
            None,
            None,
            None,
            False,
            False,
            1,
        )
        return request.app.state.templates.TemplateResponse(
            request,
            "assets.html",
            {"flashes": flashes, **context, "status_labels": ASSET_STATUS_LABELS},
            status_code=409,
        )

    asset.status = to_status
    history = PcStatusHistory(
        entity_type="ASSET",
        entity_id=asset.id,
        from_status=from_status,
        to_status=to_status,
        changed_by=actor,
        reason=reason,
    )
    db.add(history)
    db.commit()

    add_flash(request.session, "success", "状態を更新しました。")
    return RedirectResponse(url="/assets", status_code=303)


@router.post("/assets/{asset_id}/plans")
async def asset_plan_add(
    request: Request,
    asset_id: int,
    title: str = Form(""),
    planned_date: str | None = Form(None),
    planned_owner: str | None = Form(None),
    db: Session = Depends(get_db),
):
    asset = db.query(PcAsset).filter(PcAsset.id == asset_id).first()
    if asset is None:
        add_flash(request.session, "error", "対象の資産が見つかりません。")
        return RedirectResponse(url="/assets", status_code=303)

    planned_date_value = _parse_date(planned_date)
    if planned_date_value is None:
        add_flash(request.session, "error", "❌ 予定日が未入力です。カレンダーで選んでください。")
        return RedirectResponse(url="/assets", status_code=303)

    actor = request.session.get("user_id") or "system"
    plan = PcPlan(
        entity_type="ASSET",
        entity_id=asset_id,
        title=title.strip(),
        planned_date=planned_date_value,
        planned_owner=planned_owner.strip() if planned_owner else None,
        plan_status=PlanStatus.PLANNED,
        actual_date=None,
        actual_owner=None,
        result_note=None,
        created_by=actor,
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
        return RedirectResponse(url="/assets", status_code=303)

    db.add(plan)
    db.commit()
    add_flash(request.session, "success", "予定を追加しました。")
    return RedirectResponse(url="/assets", status_code=303)


@router.post("/assets/{asset_id}/plans/{plan_id}/done")
async def asset_plan_done(
    request: Request,
    asset_id: int,
    plan_id: int,
    actual_date: str | None = Form(None),
    result_note: str | None = Form(None),
    actual_owner: str | None = Form(None),
    db: Session = Depends(get_db),
):
    plan = (
        db.query(PcPlan)
        .filter(PcPlan.id == plan_id)
        .filter(PcPlan.entity_type == "ASSET")
        .filter(PcPlan.entity_id == asset_id)
        .first()
    )
    if plan is None:
        add_flash(request.session, "error", "対象の予定が見つかりません。")
        return RedirectResponse(url="/assets", status_code=303)

    actual_date_value = _parse_date(actual_date)
    if actual_date_value is None:
        add_flash(request.session, "error", "❌ 実績日が未入力です。カレンダーで選んでください。")
        return RedirectResponse(url="/assets", status_code=303)

    actor = request.session.get("user_id") or "system"
    plan.plan_status = PlanStatus.DONE
    plan.actual_date = actual_date_value
    plan.actual_owner = actual_owner.strip() if actual_owner else actor
    if result_note is not None:
        plan.result_note = result_note.strip()

    try:
        validate_plan_integrity(
            title=plan.title,
            plan_status=plan.plan_status,
            actual_date=plan.actual_date,
            actual_owner=plan.actual_owner,
        )
    except PlanValidationError as exc:
        add_flash(request.session, "error", str(exc))
        return RedirectResponse(url="/assets", status_code=303)

    db.commit()
    add_flash(request.session, "success", "次の予定を完了しました。")
    return RedirectResponse(url="/assets", status_code=303)


@router.post("/assets/{asset_id}/plans/{plan_id}/cancel")
async def asset_plan_cancel(
    request: Request,
    asset_id: int,
    plan_id: int,
    db: Session = Depends(get_db),
):
    plan = (
        db.query(PcPlan)
        .filter(PcPlan.id == plan_id)
        .filter(PcPlan.entity_type == "ASSET")
        .filter(PcPlan.entity_id == asset_id)
        .first()
    )
    if plan is None:
        add_flash(request.session, "error", "対象の予定が見つかりません。")
        return RedirectResponse(url=f"/assets/{asset_id}", status_code=303)

    plan.plan_status = PlanStatus.CANCELLED
    plan.actual_date = None
    plan.actual_owner = None
    plan.result_note = None

    try:
        validate_plan_integrity(
            title=plan.title,
            plan_status=plan.plan_status,
            actual_date=plan.actual_date,
            actual_owner=plan.actual_owner,
        )
    except PlanValidationError as exc:
        add_flash(request.session, "error", str(exc))
        return RedirectResponse(url=f"/assets/{asset_id}", status_code=303)

    db.commit()
    add_flash(request.session, "success", "予定を中止しました。")
    return RedirectResponse(url=f"/assets/{asset_id}", status_code=303)


@router.get("/assets/new")
async def asset_new(request: Request):
    asset = PcAsset(
        asset_tag="",
        serial_no=None,
        hostname=None,
        status=AssetStatus.INV,
        current_user=None,
        location=None,
        notes=None,
    )
    return _render_asset_form(
        request,
        asset=asset,
        action="/assets",
        title="資産登録",
    )


@router.post("/assets")
async def asset_create(
    request: Request,
    asset_tag: str = Form(""),
    serial_no: str | None = Form(None),
    hostname: str | None = Form(None),
    status: str = Form("INV"),
    current_user: str | None = Form(None),
    location: str | None = Form(None),
    notes: str | None = Form(None),
    db: Session = Depends(get_db),
):
    try:
        validate_asset_integrity(
            asset_tag=asset_tag,
            hostname=hostname,
            status=status,
            current_user=current_user,
            notes=notes,
        )
    except ValidationError as exc:
        add_flash(request.session, "error", str(exc))
        draft = PcAsset(
            asset_tag=asset_tag,
            serial_no=serial_no,
            hostname=hostname,
            status=AssetStatus(status),
            current_user=current_user,
            location=location,
            notes=notes,
        )
        return _render_asset_form(
            request,
            asset=draft,
            action="/assets",
            title="資産登録",
        )

    asset = PcAsset(
        asset_tag=asset_tag.strip(),
        serial_no=serial_no.strip() if serial_no else None,
        hostname=hostname.strip() if hostname else None,
        status=AssetStatus(status),
        current_user=current_user.strip() if current_user else None,
        location=location.strip() if location else None,
        notes=notes.strip() if notes else None,
    )
    db.add(asset)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        add_flash(request.session, "error", "資産タグまたはシリアルが重複しています。")
        return _render_asset_form(
            request,
            asset=asset,
            action="/assets",
            title="資産登録",
        )

    add_flash(request.session, "success", "資産を登録しました。")
    return RedirectResponse(url=f"/assets/{asset.id}", status_code=303)


@router.get("/assets/{asset_id}/edit")
async def asset_edit(request: Request, asset_id: int, db: Session = Depends(get_db)):
    asset = db.query(PcAsset).filter(PcAsset.id == asset_id).first()
    if asset is None:
        add_flash(request.session, "error", "対象の資産が見つかりません。")
        return RedirectResponse(url="/assets", status_code=303)
    return _render_asset_form(
        request,
        asset=asset,
        action=f"/assets/{asset_id}/edit",
        title="資産編集",
    )


@router.post("/assets/{asset_id}/edit")
async def asset_update(
    request: Request,
    asset_id: int,
    asset_tag: str = Form(""),
    serial_no: str | None = Form(None),
    hostname: str | None = Form(None),
    status: str = Form("INV"),
    current_user: str | None = Form(None),
    location: str | None = Form(None),
    notes: str | None = Form(None),
    db: Session = Depends(get_db),
):
    asset = db.query(PcAsset).filter(PcAsset.id == asset_id).first()
    if asset is None:
        add_flash(request.session, "error", "対象の資産が見つかりません。")
        return RedirectResponse(url="/assets", status_code=303)

    try:
        validate_asset_integrity(
            asset_tag=asset_tag,
            hostname=hostname,
            status=status,
            current_user=current_user,
            notes=notes,
        )
    except ValidationError as exc:
        add_flash(request.session, "error", str(exc))
        asset.asset_tag = asset_tag
        asset.serial_no = serial_no
        asset.hostname = hostname
        asset.status = AssetStatus(status)
        asset.current_user = current_user
        asset.location = location
        asset.notes = notes
        return _render_asset_form(
            request,
            asset=asset,
            action=f"/assets/{asset_id}/edit",
            title="資産編集",
        )

    asset.asset_tag = asset_tag.strip()
    asset.serial_no = serial_no.strip() if serial_no else None
    asset.hostname = hostname.strip() if hostname else None
    asset.status = AssetStatus(status)
    asset.current_user = current_user.strip() if current_user else None
    asset.location = location.strip() if location else None
    asset.notes = notes.strip() if notes else None
    asset.updated_at = datetime.now(timezone.utc)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        add_flash(request.session, "error", "資産タグまたはシリアルが重複しています。")
        return _render_asset_form(
            request,
            asset=asset,
            action=f"/assets/{asset_id}/edit",
            title="資産編集",
        )

    add_flash(request.session, "success", "資産を更新しました。")
    return RedirectResponse(url=f"/assets/{asset.id}", status_code=303)


@router.get("/assets/{asset_id}")
async def asset_detail(request: Request, asset_id: int, db: Session = Depends(get_db)):
    asset = db.query(PcAsset).filter(PcAsset.id == asset_id).first()
    if asset is None:
        add_flash(request.session, "error", "対象の資産が見つかりません。")
        return RedirectResponse(url="/assets", status_code=303)

    targets = list_allowed_asset_targets(asset.status)

    plans = (
        db.query(PcPlan)
        .filter(PcPlan.entity_type == "ASSET")
        .filter(PcPlan.entity_id == asset_id)
        .order_by(PcPlan.planned_date.desc(), PcPlan.id.desc())
        .all()
    )

    history = (
        db.query(PcStatusHistory)
        .filter(PcStatusHistory.entity_type == "ASSET")
        .filter(PcStatusHistory.entity_id == asset_id)
        .order_by(PcStatusHistory.changed_at.desc())
        .all()
    )

    flashes = consume_flash(request.session)
    return request.app.state.templates.TemplateResponse(
        request,
        "asset_detail.html",
        {
            "flashes": flashes,
            "asset": asset,
            "history": history,
            "status_labels": ASSET_STATUS_LABELS,
            "plan_status_labels": PLAN_STATUS_LABELS,
            "plans": plans,
            "targets": targets,
            "today": date.today(),
        },
    )


@router.post("/assets/{asset_id}/delete")
async def asset_delete(request: Request, asset_id: int, db: Session = Depends(get_db)):
    asset = db.query(PcAsset).filter(PcAsset.id == asset_id).first()
    if asset is None:
        add_flash(request.session, "error", "対象の資産が見つかりません。")
        return RedirectResponse(url="/assets", status_code=303)

    db.delete(asset)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        add_flash(request.session, "error", "関連データがあるため削除できません。")
        return RedirectResponse(url=f"/assets/{asset_id}", status_code=303)

    add_flash(request.session, "success", "資産を削除しました。")
    return RedirectResponse(url="/assets", status_code=303)


@router.post("/assets/import")
async def assets_import(
    request: Request,
    file: UploadFile | None = File(None),
):
    if file is None:
        add_flash(request.session, "warning", "インポートするファイルを選択してください。")
    else:
        add_flash(request.session, "warning", "インポート機能は準備中です。")
    return RedirectResponse(url="/assets", status_code=303)
