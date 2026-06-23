from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas import (
    NarrateRequest,
    NarrateResponse,
    NarrationContent,
    NarrationContentBlock,
)
from app.services.narration import narration_service

router = APIRouter(prefix="/api", tags=["narrate"])


@router.post("/narrate", response_model=NarrateResponse)
async def narrate(req: NarrateRequest, db: Session = Depends(get_db)):
    result = await narration_service.get_or_generate_narration(db, req.exhibit_id, req.lang)
    blocks = [
        NarrationContentBlock(**b)
        for b in (result["content"].get("blocks") or [])
    ]
    return NarrateResponse(
        tier=result["tier"],
        content=NarrationContent(blocks=blocks),
        source_label=result["source_label"],
        audio_url=result.get("audio_url"),
    )
