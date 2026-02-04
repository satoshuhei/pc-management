from __future__ import annotations

import logging
import time
from typing import Callable

from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.exc import SQLAlchemyError
from starlette.middleware.sessions import SessionMiddleware

from app.config import get_settings
from app.logging_config import setup_logging
from app.routes import auth as auth_routes
from app.routes import dashboard as dashboard_routes
from app.routes import assets as assets_routes
from app.routes import requests as requests_routes
from app.routes import plans as plans_routes
from app.utils import add_flash, format_jst

setup_logging()
logger = logging.getLogger("app")
settings = get_settings()

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")
app.state.templates = Jinja2Templates(directory="templates")
app.state.templates.env.filters["format_jst"] = format_jst

app.include_router(auth_routes.router)
app.include_router(dashboard_routes.router)
app.include_router(assets_routes.router)
app.include_router(requests_routes.router)
app.include_router(plans_routes.router)


@app.middleware("http")
async def request_logging_middleware(request: Request, call_next: Callable):
    start = time.time()
    response = await call_next(request)
    latency = (time.time() - start) * 1000
    logger.info(
        "request path=%s method=%s status=%s latency_ms=%.1f",
        request.url.path,
        request.method,
        response.status_code,
        latency,
    )
    return response


@app.middleware("http")
async def auth_guard_middleware(request: Request, call_next: Callable):
    path = request.url.path
    if path.startswith("/static") or path in {"/login", "/favicon.ico"}:
        return await call_next(request)

    if request.session.get("user_id"):
        return await call_next(request)

    add_flash(request.session, "warning", "ログインしてください。")
    return RedirectResponse(url="/login", status_code=303)


app.add_middleware(SessionMiddleware, secret_key=settings.secret_key)


@app.get("/")
async def root_redirect():
    return RedirectResponse(url="/dashboard", status_code=303)


@app.exception_handler(SQLAlchemyError)
async def db_exception_handler(request: Request, exc: SQLAlchemyError):
    logger.exception("db error path=%s", request.url.path)
    return PlainTextResponse(
        "DBエラーが発生しました。管理者に連絡してください。",
        status_code=500,
    )


@app.exception_handler(Exception)
async def unexpected_exception_handler(request: Request, exc: Exception):
    logger.exception("unexpected error path=%s", request.url.path)
    return PlainTextResponse(
        "予期しないエラーが発生しました。管理者に連絡してください。",
        status_code=500,
    )
