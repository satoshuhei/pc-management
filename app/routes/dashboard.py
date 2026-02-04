from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request

from app.utils import consume_flash

router = APIRouter()


@router.get("/dashboard")
async def dashboard(request: Request) -> Any:
    flashes = consume_flash(request.session)
    return request.app.state.templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "flashes": flashes,
        },
    )
