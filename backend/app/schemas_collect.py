from datetime import datetime

from pydantic import BaseModel


class CollectStartRequest(BaseModel):
    museum_id: int | None = None
    source: str  # baike / wiki / wiki_list / official
    enable_llm_refine: bool = False


class CollectStartResponse(BaseModel):
    job_id: int


class CollectJobOut(BaseModel):
    id: int
    museum_id: int | None
    museum_name: str | None
    source: str
    stage: str
    total: int
    done: int
    failed: int
    started_at: datetime
    finished_at: datetime | None
    error: str | None


class CollectJobListResponse(BaseModel):
    total: int
    jobs: list[CollectJobOut]


class CollectItemOut(BaseModel):
    id: int
    name: str | None
    stage: str
    target_type: str | None
    target_id: int | None
    error: str | None


class CollectJobDetailResponse(BaseModel):
    job: CollectJobOut
    items: list[CollectItemOut]
