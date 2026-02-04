from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import PcAsset
from app.utils import consume_flash

router = APIRouter()

@router.get("/assets")
async def assets(request: Request, db: Session = Depends(get_db)):
    flashes = consume_flash(request.session)
    assets = (
        db.query(PcAsset)
        .order_by(PcAsset.id.desc())
        .limit(200)
        .all()
    )
    return request.app.state.templates.TemplateResponse(
        request,
        "assets.html",
        {
            "flashes": flashes,
            "assets": assets,
        },
    )
