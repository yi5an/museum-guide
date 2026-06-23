"""分层降级讲解服务。

Tier 1：查库里指定语言的讲解（找不到该语言则退回中文）。
Tier 2：调 AI 生成并回流入库（下次同展品同语言命中，不再调 AI）。
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Exhibit, Narration
from app.services.model_router import model_router


class NarrationService:
    def get_narration(self, db: Session, exhibit_id: int, lang: str) -> dict | None:
        """Tier 1：查库里讲解。找不到指定语言则退回中文。都没有返回 None。"""
        for try_lang in [lang, "zh"]:
            narration = db.scalar(
                select(Narration).where(
                    Narration.exhibit_id == exhibit_id,
                    Narration.lang == try_lang,
                )
            )
            if narration:
                return {
                    "tier": narration.tier,
                    "content": narration.content,
                    "source_label": narration.source_label,
                    "audio_url": narration.audio_url,
                }
        return None

    async def get_or_generate_narration(
        self, db: Session, exhibit_id: int, lang: str
    ) -> dict:
        """分层降级：先查库（Tier 1），没有则 AI 生成（Tier 2）并回流入库。"""
        existing = self.get_narration(db, exhibit_id, lang)
        if existing:
            return existing

        # Tier 2：调 AI 生成
        exhibit = db.get(Exhibit, exhibit_id)
        if not exhibit:
            raise ValueError(f"Exhibit {exhibit_id} not found")

        exhibit_info = {
            "name": exhibit.name,
            "category": exhibit.category,
            "dynasty": exhibit.dynasty,
            "museum_id": exhibit.museum_id,
        }
        content = await model_router.generate_narration(exhibit_info, lang)

        # 回流入库（tier=2）
        narration = Narration(
            exhibit_id=exhibit_id,
            lang=lang,
            content=content,
            tier=2,
            source_label="AI 推测，仅供参考",
        )
        db.add(narration)
        db.flush()

        return {
            "tier": 2,
            "content": content,
            "source_label": "AI 推测，仅供参考",
            "audio_url": None,
        }


narration_service = NarrationService()
