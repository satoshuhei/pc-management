from datetime import date

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import PcPlan, PlanStatus
from app.utils import consume_flash

router = APIRouter()

@router.get("/plans/overdue")
async def plans_overdue(request: Request, db: Session = Depends(get_db)):
    flashes = consume_flash(request.session)
    today = date.today()
    plans = (
        db.query(PcPlan)
        .filter(PcPlan.plan_status == PlanStatus.PLANNED)
        .filter(PcPlan.planned_date.isnot(None))
        .filter(PcPlan.planned_date < today)
        .order_by(PcPlan.planned_date.asc(), PcPlan.id.desc())
        .limit(200)
        .all()
    )
    return request.app.state.templates.TemplateResponse(
        request,
        "plans_overdue.html",
        {
            "flashes": flashes,
            "plans": plans,
            "today": today,
        },
    )
