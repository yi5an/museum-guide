from pydantic import BaseModel


# === 请求 schemas ===


class LocateRequest(BaseModel):
    lat: float
    lng: float


class RecognizeRequest(BaseModel):
    museum_id: int | None = None
    floor_id: int | None = None
    image: str  # base64 编码
    heading: float | None = None


class NarrateRequest(BaseModel):
    exhibit_id: int
    lang: str = "zh"
    chat_history: list[dict] | None = None


class ChatRequest(BaseModel):
    exhibit_id: int
    lang: str = "zh"
    message: str
    chat_history: list[dict] | None = None


class FeedbackRequest(BaseModel):
    exhibit_id: int | None = None
    type: str  # wrong_pos / wrong_info / supplement
    proposed_floor_id: int | None = None
    content: str | None = None
    heading: float | None = None


# === 响应 schemas ===


class LocateResponse(BaseModel):
    museum_id: int | None
    name: str | None
    is_inside: bool


class FloorOut(BaseModel):
    id: int
    level: int
    name: str
    floor_plan_url: str | None
    sort_order: int


class ExhibitOut(BaseModel):
    id: int
    name: str
    category: str | None
    dynasty: str | None
    floor_id: int | None
    plan_x: float | None = None
    plan_y: float | None = None
    has_narration: bool


class ExhibitListResponse(BaseModel):
    floor_id: int | None
    total: int
    exhibits: list[ExhibitOut]


class RouteOut(BaseModel):
    id: int
    title: str
    theme: str
    duration_min: int
    exhibit_order: list[int]


class MuseumDetailResponse(BaseModel):
    id: int
    name: str
    name_i18n: dict
    city: str
    country: str
    description: str | None
    cover_image_url: str | None = None
    floors: list[FloorOut]
    routes: list[RouteOut]
    exhibit_count: int


class MuseumListItem(BaseModel):
    id: int
    name: str
    city: str
    description: str | None
    exhibit_count: int
    cover_image_url: str | None = None


class MuseumListResponse(BaseModel):
    total: int
    museums: list[MuseumListItem]


class Candidate(BaseModel):
    exhibit_id: int | None
    name: str
    confidence: float


class RecognizeResponse(BaseModel):
    candidates: list[Candidate]
    best_match: Candidate | None
    best_confidence: float


class NarrationContentBlock(BaseModel):
    type: str  # text / image
    section: str | None = None
    text: str | None = None
    image_id: int | None = None
    caption: str | None = None


class NarrationContent(BaseModel):
    blocks: list[NarrationContentBlock]


class NarrateResponse(BaseModel):
    tier: int  # 1=官方 2=AI生成 3=引导
    content: NarrationContent
    source_label: str
    audio_url: str | None = None


class ChatResponse(BaseModel):
    reply: str


class FeedbackResponse(BaseModel):
    ok: bool
