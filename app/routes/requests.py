from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import PcRequest
from app.utils import add_flash, consume_flash

router = APIRouter()

@router.get("/requests")
async def requests_list(
    request: Request,
    status: str | None = None,
    requester: str | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(PcRequest)
    if status:
        query = query.filter(PcRequest.status == status)
    if requester:
        query = query.filter(PcRequest.requester.contains(requester))

    if status or requester:
        add_flash(request.session, "success", "検索条件を適用しました。")

    flashes = consume_flash(request.session)
    requests = query.order_by(PcRequest.id.desc()).limit(200).all()
    return request.app.state.templates.TemplateResponse(
        request,
        "requests.html",
        {
            "flashes": flashes,
            "requests": requests,
            "filters": {
                "status": status or "",
                "requester": requester or "",
            },
        },
    )
