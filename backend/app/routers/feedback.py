from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Feedback
from app.schemas import FeedbackRequest, FeedbackResponse

router = APIRouter(prefix="/api", tags=["feedback"])


@router.post("/feedback", response_model=FeedbackResponse)
async def feedback(req: FeedbackRequest, db: Session = Depends(get_db)):
    fb = Feedback(
        exhibit_id=req.exhibit_id,
        type=req.type,
        proposed_floor_id=req.proposed_floor_id,
        content=req.content,
        user_heading=req.heading,
        status="pending",
    )
    db.add(fb)
    db.flush()
    return FeedbackResponse(ok=True)
