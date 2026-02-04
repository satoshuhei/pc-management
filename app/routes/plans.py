from datetime import date

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import PcPlan, PlanStatus
from app.utils import add_flash, consume_flash

router = APIRouter()

@router.get("/plans/overdue")
async def plans_overdue(
    request: Request,
    planned_owner: str | None = None,
    title: str | None = None,
    db: Session = Depends(get_db),
):
    flashes = consume_flash(request.session)
    today = date.today()
    query = (
        db.query(PcPlan)
        .filter(PcPlan.plan_status == PlanStatus.PLANNED)
        .filter(PcPlan.planned_date.isnot(None))
        .filter(PcPlan.planned_date < today)
    )
    if planned_owner:
        query = query.filter(PcPlan.planned_owner.contains(planned_owner))
    if title:
        query = query.filter(PcPlan.title.contains(title))

    if planned_owner or title:
        add_flash(request.session, "success", "検索条件を適用しました。")

    flashes = consume_flash(request.session)
    plans = query.order_by(PcPlan.planned_date.asc(), PcPlan.id.desc()).limit(200).all()
    return request.app.state.templates.TemplateResponse(
        request,
        "plans_overdue.html",
        {
            "flashes": flashes,
            "plans": plans,
            "today": today,
            "filters": {
                "planned_owner": planned_owner or "",
                "title": title or "",
            },
        },
    )
