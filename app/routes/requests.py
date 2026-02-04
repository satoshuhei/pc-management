from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.db import get_db
from app.models import PcRequest, PcStatusHistory, RequestStatus
from app.status_rules import list_allowed_request_targets
from app.transition_service import TransitionError, apply_request_transition
from app.utils import add_flash, consume_flash
from app.validation import ValidationError, validate_request_integrity

router = APIRouter()


def _parse_optional_int(value: str | None) -> int | None:
    if value is None:
        return None
    text = value.strip()
    if not text:
        return None
    if not text.isdigit():
        return None
    number = int(text)
    return number if number > 0 else None

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


def _render_request_form(
    request: Request,
    *,
    request_item: PcRequest,
    action: str,
    title: str,
):
    flashes = consume_flash(request.session)
    return request.app.state.templates.TemplateResponse(
        request,
        "request_form.html",
        {
            "flashes": flashes,
            "request_item": request_item,
            "action": action,
            "title": title,
        },
    )


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


@router.get("/requests/new")
async def request_new(request: Request):
    req = PcRequest(status=RequestStatus.RQ, requester=None, note=None, asset_id=None)
    return _render_request_form(
        request,
        request_item=req,
        action="/requests",
        title="要求登録",
    )


@router.post("/requests")
async def request_create(
    request: Request,
    requester: str | None = Form(None),
    note: str | None = Form(None),
    asset_id: str | None = Form(None),
    db: Session = Depends(get_db),
):
    try:
        validate_request_integrity(requester=requester, note=note)
    except ValidationError as exc:
        add_flash(request.session, "error", str(exc))
        draft = PcRequest(
            status=RequestStatus.RQ,
            requester=requester,
            note=note,
            asset_id=None,
        )
        return _render_request_form(
            request,
            request_item=draft,
            action="/requests",
            title="要求登録",
        )

    asset_id_value = _parse_optional_int(asset_id)
    req = PcRequest(
        status=RequestStatus.RQ,
        requester=requester.strip() if requester else None,
        note=note.strip() if note else None,
        asset_id=asset_id_value,
    )
    db.add(req)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        add_flash(request.session, "error", "資産IDを確認してください。")
        return _render_request_form(
            request,
            request_item=req,
            action="/requests",
            title="要求登録",
        )

    add_flash(request.session, "success", "要求を登録しました。")
    return RedirectResponse(url=f"/requests/{req.id}", status_code=303)


@router.get("/requests/{request_id}/edit")
async def request_edit(request: Request, request_id: int, db: Session = Depends(get_db)):
    req = db.query(PcRequest).filter(PcRequest.id == request_id).first()
    if req is None:
        add_flash(request.session, "error", "対象の要求が見つかりません。")
        return RedirectResponse(url="/requests", status_code=303)
    return _render_request_form(
        request,
        request_item=req,
        action=f"/requests/{request_id}/edit",
        title="要求編集",
    )


@router.post("/requests/{request_id}/edit")
async def request_update(
    request: Request,
    request_id: int,
    requester: str | None = Form(None),
    note: str | None = Form(None),
    asset_id: str | None = Form(None),
    db: Session = Depends(get_db),
):
    req = db.query(PcRequest).filter(PcRequest.id == request_id).first()
    if req is None:
        add_flash(request.session, "error", "対象の要求が見つかりません。")
        return RedirectResponse(url="/requests", status_code=303)

    try:
        validate_request_integrity(requester=requester, note=note)
    except ValidationError as exc:
        add_flash(request.session, "error", str(exc))
        req.requester = requester
        req.note = note
        req.asset_id = None
        return _render_request_form(
            request,
            request_item=req,
            action=f"/requests/{request_id}/edit",
            title="要求編集",
        )

    asset_id_value = _parse_optional_int(asset_id)
    req.requester = requester.strip() if requester else None
    req.note = note.strip() if note else None
    req.asset_id = asset_id_value
    req.updated_at = datetime.now(timezone.utc)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        add_flash(request.session, "error", "資産IDを確認してください。")
        return _render_request_form(
            request,
            request_item=req,
            action=f"/requests/{request_id}/edit",
            title="要求編集",
        )

    add_flash(request.session, "success", "要求を更新しました。")
    return RedirectResponse(url=f"/requests/{req.id}", status_code=303)


@router.get("/requests/{request_id}")
async def request_detail(request: Request, request_id: int, db: Session = Depends(get_db)):
    req = db.query(PcRequest).filter(PcRequest.id == request_id).first()
    if req is None:
        add_flash(request.session, "error", "対象の要求が見つかりません。")
        return RedirectResponse(url="/requests", status_code=303)

    history = (
        db.query(PcStatusHistory)
        .filter(PcStatusHistory.entity_type == "REQUEST")
        .filter(PcStatusHistory.entity_id == request_id)
        .order_by(PcStatusHistory.changed_at.desc())
        .all()
    )

    flashes = consume_flash(request.session)
    return request.app.state.templates.TemplateResponse(
        request,
        "request_detail.html",
        {
            "flashes": flashes,
            "request_item": req,
            "history": history,
        },
    )


@router.post("/requests/{request_id}/delete")
async def request_delete(request: Request, request_id: int, db: Session = Depends(get_db)):
    req = db.query(PcRequest).filter(PcRequest.id == request_id).first()
    if req is None:
        add_flash(request.session, "error", "対象の要求が見つかりません。")
        return RedirectResponse(url="/requests", status_code=303)

    db.delete(req)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        add_flash(request.session, "error", "関連データがあるため削除できません。")
        return RedirectResponse(url=f"/requests/{request_id}", status_code=303)

    add_flash(request.session, "success", "要求を削除しました。")
    return RedirectResponse(url="/requests", status_code=303)
