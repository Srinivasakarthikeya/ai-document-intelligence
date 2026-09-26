from datetime import datetime, timezone
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, PlainSerializer


def _iso_utc(d: datetime) -> str:
    # SQLite drops tzinfo; everything is stored as UTC, so re-attach it on the way out.
    return (d if d.tzinfo else d.replace(tzinfo=timezone.utc)).isoformat()


UTCDateTime = Annotated[datetime, PlainSerializer(_iso_utc, return_type=str)]


class EventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    stage: str
    message: str
    duration_ms: int | None
    created_at: UTCDateTime


class DocumentSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    filename: str
    status: str
    doc_type: str | None
    type_confidence: float | None
    size_bytes: int | None = None
    created_at: UTCDateTime
    updated_at: UTCDateTime


class UploadResult(DocumentSummary):
    duplicate: bool = False


class DocumentDetail(DocumentSummary):
    mime_type: str
    ocr_method: str | None
    raw_text: str | None
    fields: dict | None
    validation: list | None
    error: str | None
    processing_ms: int | None
    reviewed_at: UTCDateTime | None
    events: list[EventOut]


class DocumentPage(BaseModel):
    items: list[DocumentSummary]
    total: int
    limit: int
    offset: int


class FieldUpdate(BaseModel):
    fields: dict[str, Any]


class Stats(BaseModel):
    total: int
    by_status: dict[str, int]
    by_type: dict[str, int]
    avg_processing_ms: int | None
