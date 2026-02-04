from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import PcRequest
from app.utils import consume_flash

router = APIRouter()

@router.get("/requests")
async def requests_list(request: Request, db: Session = Depends(get_db)):
    flashes = consume_flash(request.session)
    requests = (
        db.query(PcRequest)
        .order_by(PcRequest.id.desc())
        .limit(200)
        .all()
    )
    return request.app.state.templates.TemplateResponse(
        request,
        "requests.html",
        {
            "flashes": flashes,
            "requests": requests,
        },
    )
