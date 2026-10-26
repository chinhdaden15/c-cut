"""Hợp đồng dữ liệu (schema có version) cho project/timeline. Pydantic v2."""
from __future__ import annotations

from typing import Literal, Optional
from pydantic import BaseModel, Field

SCHEMA_VERSION = "0.1.0"

AssetRole = Literal["source", "reference", "project_asset", "font", "sfx", "music"]
Layer = Literal["behind_subject", "front_of_subject", "fullscreen"]


class MediaInfo(BaseModel):
    path: str
    duration: float
    width: int
    height: int
    fps: float
    rotation: int = 0
    hdr: bool = False
    has_audio: bool = True
    size_bytes: int = 0


class TranscriptWord(BaseModel):
    id: str
    text: str
    source_start: float
    source_end: float
    confidence: float = 1.0
    needs_review: bool = False
    sentence_id: int = 0


class Sentence(BaseModel):
    id: int
    text: str
    source_start: float
    source_end: float
    word_ids: list[str]


class EditSegment(BaseModel):
    id: str
    source_in: float
    source_out: float
    keep: bool = True
    reason: str = ""
    confidence: float = 1.0
    order: int = 0
    role: Literal["hook", "body", "cta"] = "body"
    # timeline_in/out (frames) được tính lại bởi timeline.build_mapping
    timeline_in: int = 0
    timeline_out: int = 0


class TextSpan(BaseModel):
    text: str
    font_role: Literal["body", "body_bold", "emphasis", "decorative", "number"] = "body"
    size: int = 64
    color: str = "#FAFAFA"
    dx: float = 0.0          # vị trí tương đối trong nhóm (px, khung 1080)
    dy: float = 0.0
    letter_spacing: float = 0.0
    delay_frames: int = 0    # dùng cho staggered_phrase
    # --- phong cách neon pack ---
    style: Literal["classic", "neon", "outline", "pill", "icon"] = "classic"
    palette: str = "white"
    neon_role: str = "display"   # display | condensed | script | serif | body
    motion: Optional[Literal["pop", "write", "wipe", "slide", "icon", "fade", "words", "float"]] = None
    word_delays: list[int] = []  # motion=words: frame xuất hiện của từng từ (tương đối start nhóm)
    echo: bool = False           # viền rỗng lan ra tại điểm nhấn


class TextGroup(BaseModel):
    id: str
    word_ids: list[str] = []
    semantic_role: str = "keypoint"
    preset: Literal["phrase_slide", "keyword_pop", "staggered_phrase",
                    "behind_head_title", "number_callout", "caption"] = "phrase_slide"
    zone: Literal["above_head", "chest", "lower"] = "chest"
    layer: Layer = "front_of_subject"
    align: Literal["left", "center", "right"] = "center"
    anchor_x: float = 0.5    # tỉ lệ ngang khung
    anchor_y: Optional[float] = None  # None = tính từ anchor đầu/ngực của shot
    spans: list[TextSpan]
    start: int = 0           # frame timeline
    end: int = 0
    hit: int = 0             # frame đạt điểm nhấn
    enter_frames: int = 8
    exit_frames: int = 6
    enabled: bool = True
    sfx: Optional[str] = None  # id SoundEvent liên kết


class VisualAsset(BaseModel):
    id: str
    file: str
    role: AssetRole = "project_asset"
    project_or_location: str = ""
    source: str = ""
    source_type: Literal["user_provided", "official", "render_published", "photo_actual", "unknown"] = "unknown"
    approved: bool = False


class VisualEvent(BaseModel):
    id: str
    asset_id: Optional[str]
    start: int
    end: int
    layer: Layer = "fullscreen"
    illustrates: str = ""
    status: Literal["ready", "missing_asset"] = "missing_asset"
    file: str = ""            # ảnh/video tư liệu thật
    label: str = ""           # tên dự án · địa điểm hiển thị trên thẻ
    source: str = ""          # URL/nguồn gốc
    width: int = 760
    zone: Literal["above_head", "chest", "fullscreen"] = "above_head"
    enter_frames: int = 10
    exit_frames: int = 7
    enabled: bool = True


class SoundEvent(BaseModel):
    id: str
    asset: str               # tên file trong assets/sfx
    linked_event: str
    hit: int                 # frame timeline nơi đỉnh âm phải rơi
    peak_offset_ms: float = 0.0
    gain_db: float = -12.0
    priority: int = 1
    enabled: bool = True


class VideoFxEvent(BaseModel):
    id: str
    type: Literal["zoom", "flash", "highlight"]
    start: int
    end: int
    params: dict = Field(default_factory=dict)
    linked_sound: Optional[str] = None
    enabled: bool = True


class QaIssue(BaseModel):
    id: str
    severity: Literal["info", "warn", "error"]
    timecode: str = ""
    kind: str
    detail: str
    evidence: str = ""
    status: Literal["open", "resolved", "needs_human"] = "open"


class Plan(BaseModel):
    schema_version: str = SCHEMA_VERSION
    planner: str = "heuristic"     # heuristic | claude:<model>
    fps: int = 30
    width: int = 1080
    height: int = 1920
    segments: list[EditSegment] = []
    text_groups: list[TextGroup] = []
    sounds: list[SoundEvent] = []
    fx: list[VideoFxEvent] = []
    visuals: list[VisualEvent] = []
    notes: list[str] = []
    hook_candidates: list[dict] = []
    duration_frames: int = 0
    mg: list[dict] = []          # đoạn Motion Graphics toàn khung (thagent/mg.py)
    speed: float = 1.0           # tăng/giảm tốc cả video lúc xuất (0.8–1.5), giọng giữ cao độ
    hf: list[dict] = []          # lớp HyperFrames (công cụ dựng chung) — thagent/th_hf.py
    mg2: list[dict] = []         # Motion Graphics thế hệ 2 (bố cục + chuyển động, HyperFrames) — thagent/mg2.py
    stage: list[dict] = []       # "sân khấu" quanh / sau lưng nhân vật — thagent/stage.py
    callouts: list[dict] = []    # chữ nổi bật + icon / callout / ảnh kẹp — thagent/callouts.py (app tự đặt, tránh mặt)


class Project(BaseModel):
    id: str
    schema_version: str = SCHEMA_VERSION
    name: str = ""
    source: Optional[MediaInfo] = None
    proxy: Optional[str] = None
    reference: Optional[str] = None
    assets: list[VisualAsset] = []
    status: Literal["created", "uploaded", "analyzed", "rough_cut", "designed",
                    "rendering", "ready", "waiting_input", "failed", "cancelled"] = "created"
    words: list[TranscriptWord] = []
    sentences: list[Sentence] = []
    plan: Optional[Plan] = None
    renders: list[dict] = []
    style: dict = Field(default_factory=dict)
