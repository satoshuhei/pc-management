from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import PcAsset
from app.utils import add_flash, consume_flash

router = APIRouter()

@router.get("/assets")
async def assets(
    request: Request,
    status: str | None = None,
    asset_tag: str | None = None,
    location: str | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(PcAsset)
    if status:
        query = query.filter(PcAsset.status == status)
    if asset_tag:
        query = query.filter(PcAsset.asset_tag.contains(asset_tag))
    if location:
        query = query.filter(PcAsset.location.contains(location))

    if status or asset_tag or location:
        add_flash(request.session, "success", "検索条件を適用しました。")

    flashes = consume_flash(request.session)
    assets = query.order_by(PcAsset.id.desc()).limit(200).all()
    return request.app.state.templates.TemplateResponse(
        request,
        "assets.html",
        {
            "flashes": flashes,
            "assets": assets,
            "filters": {
                "status": status or "",
                "asset_tag": asset_tag or "",
                "location": location or "",
            },
        },
    )
