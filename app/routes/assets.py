from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.db import get_db
from app.models import ASSET_STATUS_LABELS, AssetStatus, PcAsset, PcStatusHistory
from app.status_rules import list_allowed_asset_targets
from app.transition_service import TransitionError, apply_asset_transition
from app.utils import add_flash, consume_flash
from app.validation import ValidationError, validate_asset_integrity

router = APIRouter()

def _build_assets_context(
    request: Request,
    db: Session,
    status: str | None,
    asset_tag: str | None,
    location: str | None,
):
    query = db.query(PcAsset)
    if status:
        query = query.filter(PcAsset.status == status)
    if asset_tag:
        query = query.filter(PcAsset.asset_tag.contains(asset_tag))
    if location:
        query = query.filter(PcAsset.location.contains(location))

    assets = query.order_by(PcAsset.id.desc()).limit(200).all()
    targets = {asset.id: list_allowed_asset_targets(asset.status) for asset in assets}

    return {
        "assets": assets,
        "targets": targets,
        "filters": {
            "status": status or "",
            "asset_tag": asset_tag or "",
            "location": location or "",
        },
    }


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
    asset_tag: str | None = None,
    location: str | None = None,
    db: Session = Depends(get_db),
):
    if status or asset_tag or location:
        add_flash(request.session, "success", "検索条件を適用しました。")

    flashes = consume_flash(request.session)
    context = _build_assets_context(request, db, status, asset_tag, location)
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
        context = _build_assets_context(request, db, None, None, None)
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
