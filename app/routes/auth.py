from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User
from app.security import verify_passcode
from app.utils import add_flash, consume_flash

router = APIRouter()
logger = logging.getLogger("auth")


@router.get("/login")
async def login_view(request: Request) -> Any:
    flashes = consume_flash(request.session)
    return request.app.state.templates.TemplateResponse(
        request,
        "login.html",
        {"flashes": flashes},
    )


@router.post("/login")
async def login_action(
    request: Request,
    user_id: str = Form(...),
    passcode: str = Form(...),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    trimmed_user_id = user_id.strip()
    trimmed_passcode = passcode.strip()

    if not trimmed_user_id or len(trimmed_user_id) > 64:
        add_flash(request.session, "error", "ユーザIDを確認してください。")
        return RedirectResponse(url="/login", status_code=303)

    if not trimmed_passcode or len(trimmed_passcode) > 128:
        add_flash(request.session, "error", "パスコードを確認してください。")
        return RedirectResponse(url="/login", status_code=303)

    user = db.query(User).filter(User.user_id == trimmed_user_id).first()
    if user is None:
        logger.info("login failed user_id=%s reason=not_found", trimmed_user_id)
        add_flash(request.session, "error", "ユーザIDまたはパスコードが違います。")
        return RedirectResponse(url="/login", status_code=303)

    if not user.is_active:
        logger.info("login failed user_id=%s reason=inactive", trimmed_user_id)
        add_flash(request.session, "warning", "このユーザは無効です。管理者に連絡してください。")
        return RedirectResponse(url="/login", status_code=303)

    if not verify_passcode(trimmed_passcode, user.passcode_hash):
        logger.info("login failed user_id=%s reason=invalid_passcode", trimmed_user_id)
        add_flash(request.session, "error", "ユーザIDまたはパスコードが違います。")
        return RedirectResponse(url="/login", status_code=303)

    request.session["user_id"] = user.user_id
    request.session["display_name"] = user.display_name
    request.session["role"] = user.role.value

    logger.info("login success user_id=%s", trimmed_user_id)
    add_flash(request.session, "success", "ログインしました。ダッシュボードへ進んでください。")
    return RedirectResponse(url="/dashboard", status_code=303)


@router.post("/logout")
async def logout(request: Request) -> RedirectResponse:
    request.session.clear()
    add_flash(request.session, "success", "ログアウトしました。もう一度ログインしてください。")
    return RedirectResponse(url="/login", status_code=303)
