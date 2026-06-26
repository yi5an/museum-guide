from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Museum(Base):
    __tablename__ = "museums"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    name_i18n: Mapped[dict] = mapped_column(JSON, default=dict)
    city: Mapped[str] = mapped_column(String(100))
    country: Mapped[str] = mapped_column(String(100))
    lat: Mapped[float] = mapped_column(Float)
    lng: Mapped[float] = mapped_column(Float)
    geo_fence: Mapped[list] = mapped_column(JSON, default=list)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    cover_image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)
    # 采集系统预留：来源、内容指纹、采集时间（增量比对用，老数据为 NULL）
    source_ref: Mapped[str | None] = mapped_column(String(500), nullable=True)
    content_hash: Mapped[str | None] = mapped_column(String(100), nullable=True)
    fetched_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    floors: Mapped[list["Floor"]] = relationship(back_populates="museum")
    exhibits: Mapped[list["Exhibit"]] = relationship(back_populates="museum")
    routes: Mapped[list["Route"]] = relationship(back_populates="museum")


class Floor(Base):
    __tablename__ = "floors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    museum_id: Mapped[int] = mapped_column(ForeignKey("museums.id"))
    level: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(100))
    floor_plan_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    museum: Mapped["Museum"] = relationship(back_populates="floors")
    exhibits: Mapped[list["Exhibit"]] = relationship(back_populates="floor")


class Exhibit(Base):
    __tablename__ = "exhibits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    museum_id: Mapped[int] = mapped_column(ForeignKey("museums.id"))
    floor_id: Mapped[int | None] = mapped_column(ForeignKey("floors.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(200))
    name_i18n: Mapped[dict] = mapped_column(JSON, default=dict)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    dynasty: Mapped[str | None] = mapped_column(String(100), nullable=True)
    location_hint: Mapped[str | None] = mapped_column(String(200), nullable=True)
    plan_x: Mapped[float | None] = mapped_column(Float, nullable=True)
    plan_y: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="active")
    source: Mapped[str] = mapped_column(String(30), default="official")
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)
    # 采集系统预留：来源、内容指纹、采集时间（增量比对用，老数据为 NULL）
    source_ref: Mapped[str | None] = mapped_column(String(500), nullable=True)
    content_hash: Mapped[str | None] = mapped_column(String(100), nullable=True)
    fetched_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    museum: Mapped["Museum"] = relationship(back_populates="exhibits")
    floor: Mapped["Floor | None"] = relationship(back_populates="exhibits")
    images: Mapped[list["ExhibitImage"]] = relationship(back_populates="exhibit")
    narrations: Mapped[list["Narration"]] = relationship(back_populates="exhibit")


class ExhibitImage(Base):
    __tablename__ = "exhibit_images"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    exhibit_id: Mapped[int] = mapped_column(ForeignKey("exhibits.id"))
    image_url: Mapped[str] = mapped_column(String(500))
    source: Mapped[str] = mapped_column(String(30), default="official")
    is_primary: Mapped[bool] = mapped_column(default=False)
    # embedding 字段第一版不启用 pgvector，预留位置。
    # 采集系统预留：来源、内容指纹、采集时间（增量比对用，老数据为 NULL）
    source_ref: Mapped[str | None] = mapped_column(String(500), nullable=True)
    content_hash: Mapped[str | None] = mapped_column(String(100), nullable=True)
    fetched_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    exhibit: Mapped["Exhibit"] = relationship(back_populates="images")


class Narration(Base):
    __tablename__ = "narrations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    exhibit_id: Mapped[int] = mapped_column(ForeignKey("exhibits.id"))
    lang: Mapped[str] = mapped_column(String(10))
    content: Mapped[dict[str, Any]] = mapped_column(JSON)
    tier: Mapped[int] = mapped_column(Integer, default=1)
    source_label: Mapped[str] = mapped_column(String(100), default="官方")
    source_ref: Mapped[str | None] = mapped_column(String(500), nullable=True)
    audio_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # 采集系统预留：来源、内容指纹、采集时间（增量比对用，老数据为 NULL）
    source_ref: Mapped[str | None] = mapped_column(String(500), nullable=True)
    content_hash: Mapped[str | None] = mapped_column(String(100), nullable=True)
    fetched_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    exhibit: Mapped["Exhibit"] = relationship(back_populates="narrations")


class Route(Base):
    __tablename__ = "routes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    museum_id: Mapped[int] = mapped_column(ForeignKey("museums.id"))
    title: Mapped[str] = mapped_column(String(200))
    title_i18n: Mapped[dict] = mapped_column(JSON, default=dict)
    theme: Mapped[str] = mapped_column(String(50))
    duration_min: Mapped[int] = mapped_column(Integer)
    exhibit_order: Mapped[list] = mapped_column(JSON, default=list)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    museum: Mapped["Museum"] = relationship(back_populates="routes")


class Feedback(Base):
    __tablename__ = "feedbacks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    exhibit_id: Mapped[int | None] = mapped_column(ForeignKey("exhibits.id"), nullable=True)
    type: Mapped[str] = mapped_column(String(30))
    proposed_floor_id: Mapped[int | None] = mapped_column(ForeignKey("floors.id"), nullable=True)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    user_heading: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="pending")
    report_count: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    exhibit_id: Mapped[int] = mapped_column(ForeignKey("exhibits.id"))
    lang: Mapped[str] = mapped_column(String(10))
    messages: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)


class CollectJob(Base):
    """采集任务：一次「某博物馆 + 某来源」的采集运行。进度页核心数据源。"""

    __tablename__ = "collect_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    museum_id: Mapped[int | None] = mapped_column(ForeignKey("museums.id"), nullable=True)
    source: Mapped[str] = mapped_column(String(30))  # wiki_list / wiki / baike / official / images
    stage: Mapped[str] = mapped_column(String(30), default="running")  # running/succeeded/failed/partial/canceled
    total: Mapped[int] = mapped_column(Integer, default=0)
    done: Mapped[int] = mapped_column(Integer, default=0)
    failed: Mapped[int] = mapped_column(Integer, default=0)
    log: Mapped[list] = mapped_column(JSON, default=list)  # 最近 N 条错误/跳过
    started_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    museum: Mapped["Museum | None"] = relationship()
    items: Mapped[list["CollectItem"]] = relationship(back_populates="job")


class CollectItem(Base):
    """采集明细：任务内逐条采集对象的状态记录。"""

    __tablename__ = "collect_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("collect_jobs.id"))
    source_ref: Mapped[str | None] = mapped_column(String(500), nullable=True)  # 来源页 URL
    name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    stage: Mapped[str] = mapped_column(String(30), default="pending")  # pending/fetched/parsed/saved/skipped/failed
    target_type: Mapped[str | None] = mapped_column(String(30), nullable=True)  # museum/exhibit/image
    target_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    content_hash: Mapped[str | None] = mapped_column(String(100), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    job: Mapped["CollectJob"] = relationship(back_populates="items")

