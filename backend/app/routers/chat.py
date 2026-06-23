from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Exhibit
from app.schemas import ChatRequest, ChatResponse
from app.services.model_router import model_router

router = APIRouter(prefix="/api", tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest, db: Session = Depends(get_db)):
    exhibit = db.get(Exhibit, req.exhibit_id)
    exhibit_info = {
        "name": exhibit.name if exhibit else "",
        "category": exhibit.category if exhibit else "",
        "dynasty": exhibit.dynasty if exhibit else "",
    }
    reply = await model_router.chat(
        exhibit_info=exhibit_info,
        message=req.message,
        lang=req.lang,
        chat_history=req.chat_history or [],
    )
    return ChatResponse(reply=reply)
