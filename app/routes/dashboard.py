from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import (
    ASSET_STATUS_LABELS,
    PLAN_STATUS_LABELS,
    REQUEST_STATUS_LABELS,
    AssetStatus,
    PcAsset,
    PcPlan,
    PcRequest,
    PlanStatus,
    RequestStatus,
)
from app.utils import consume_flash

router = APIRouter()


@router.get("/dashboard")
async def dashboard(request: Request, db: Session = Depends(get_db)) -> Any:
    flashes = consume_flash(request.session)
    asset_counts = (
        db.query(PcAsset.status, func.count(PcAsset.id))
        .group_by(PcAsset.status)
        .all()
    )
    request_counts = (
        db.query(PcRequest.status, func.count(PcRequest.id))
        .group_by(PcRequest.status)
        .all()
    )
    plan_counts = (
        db.query(PcPlan.plan_status, func.count(PcPlan.id))
        .group_by(PcPlan.plan_status)
        .all()
    )
    today = date.today()
    overdue_count = (
        db.query(func.count(PcPlan.id))
        .filter(PcPlan.plan_status == PlanStatus.PLANNED)
        .filter(PcPlan.planned_date.isnot(None))
        .filter(PcPlan.planned_date < today)
        .scalar()
    )

    asset_summary = {ASSET_STATUS_LABELS[status.value]: 0 for status in AssetStatus}
    for status, count in asset_counts:
        asset_summary[ASSET_STATUS_LABELS[status.value]] = count

    request_summary = {REQUEST_STATUS_LABELS[status.value]: 0 for status in RequestStatus}
    for status, count in request_counts:
        request_summary[REQUEST_STATUS_LABELS[status.value]] = count

    plan_summary = {PLAN_STATUS_LABELS[status.value]: 0 for status in PlanStatus}
    for status, count in plan_counts:
        plan_summary[PLAN_STATUS_LABELS[status.value]] = count

    return request.app.state.templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "flashes": flashes,
            "asset_summary": asset_summary,
            "request_summary": request_summary,
            "plan_summary": plan_summary,
            "overdue_count": overdue_count,
        },
    )
