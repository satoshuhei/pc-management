from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import PcRequest, PcStatusHistory
from app.status_rules import list_allowed_request_targets
from app.transition_service import TransitionError, apply_request_transition
from app.utils import add_flash, consume_flash

router = APIRouter()

def _build_requests_context(
    request: Request,
    db: Session,
    status: str | None,
    requester: str | None,
):
    query = db.query(PcRequest)
    if status:
        query = query.filter(PcRequest.status == status)
    if requester:
        query = query.filter(PcRequest.requester.contains(requester))

    requests = query.order_by(PcRequest.id.desc()).limit(200).all()
    targets = {req.id: list_allowed_request_targets(req.status) for req in requests}

    return {
        "requests": requests,
        "targets": targets,
        "filters": {
            "status": status or "",
            "requester": requester or "",
        },
    }


@router.get("/requests")
async def requests_list(
    request: Request,
    status: str | None = None,
    requester: str | None = None,
    db: Session = Depends(get_db),
):
    if status or requester:
        add_flash(request.session, "success", "検索条件を適用しました。")

    flashes = consume_flash(request.session)
    context = _build_requests_context(request, db, status, requester)
    return request.app.state.templates.TemplateResponse(
        request,
        "requests.html",
        {
            "flashes": flashes,
            **context,
        },
    )


@router.post("/requests/{request_id}/transition")
async def request_transition(
    request: Request,
    request_id: int,
    to_status: str = Form(...),
    reason: str | None = Form(None),
    db: Session = Depends(get_db),
):
    req = db.query(PcRequest).filter(PcRequest.id == request_id).first()
    if req is None:
        add_flash(request.session, "error", "対象の要求が見つかりません。")
        return RedirectResponse(url="/requests", status_code=303)

    actor = request.session.get("user_id") or "system"

    from_status = req.status
    try:
        apply_request_transition(from_status=from_status, to_status=to_status, actor=actor)
    except TransitionError:
        add_flash(request.session, "error", "状態遷移が許可されていません。")
        flashes = consume_flash(request.session)
        context = _build_requests_context(request, db, None, None)
        return request.app.state.templates.TemplateResponse(
            request,
            "requests.html",
            {"flashes": flashes, **context},
            status_code=409,
        )

    req.status = to_status
    history = PcStatusHistory(
        entity_type="REQUEST",
        entity_id=req.id,
        from_status=from_status,
        to_status=to_status,
        changed_by=actor,
        reason=reason,
    )
    db.add(history)
    db.commit()

    add_flash(request.session, "success", "状態を更新しました。")
    return RedirectResponse(url="/requests", status_code=303)
