from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import PcAsset, PcStatusHistory
from app.status_rules import list_allowed_asset_targets
from app.transition_service import TransitionError, apply_asset_transition
from app.utils import add_flash, consume_flash

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
            {"flashes": flashes, **context},
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
