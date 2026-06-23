from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Exhibit
from app.schemas import Candidate, RecognizeRequest, RecognizeResponse
from app.services.model_router import model_router

router = APIRouter(prefix="/api", tags=["recognize"])


@router.post("/recognize", response_model=RecognizeResponse)
async def recognize(req: RecognizeRequest, db: Session = Depends(get_db)):
    """展物识别：GLM-4V 视觉识别 + 同馆展品库匹配。"""
    # 1. 调 GLM-4V 识别
    vision_result = await model_router.recognize(
        image_base64=req.image,
        museum_id=req.museum_id,
        hint=None,
    )

    raw_name = (vision_result.get("raw_meta") or {}).get("name") or vision_result[
        "best_match"
    ]["name"]
    best_conf = vision_result["best_confidence"]

    # 2. 用识别结果匹配同馆展品库（名字精确/模糊匹配）
    candidates: list[Candidate] = []
    best: Candidate | None = None

    stmt = select(Exhibit).where(
        Exhibit.museum_id == req.museum_id,
        Exhibit.status.in_(["active", "moved"]),
    )
    for exhibit in db.scalars(stmt):
        name_match = (
            exhibit.name == raw_name
            or raw_name in exhibit.name
            or exhibit.name in raw_name
        )
        if name_match:
            c = Candidate(
                exhibit_id=exhibit.id, name=exhibit.name, confidence=best_conf
            )
            candidates.append(c)
            if best is None or c.confidence > best.confidence:
                best = c

    # 3. 库里无匹配 → 用 GLM 原始候选
    if not candidates:
        for c in vision_result["candidates"]:
            candidates.append(Candidate(**c))
        if vision_result.get("best_match"):
            best = Candidate(**vision_result["best_match"])

    candidates.sort(key=lambda c: c.confidence, reverse=True)
    return RecognizeResponse(
        candidates=candidates[:3],
        best_match=best,
        best_confidence=best.confidence if best else best_conf,
    )
