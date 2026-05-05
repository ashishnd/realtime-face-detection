import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ROIDetectionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    session_id: uuid.UUID
    frame_number: int
    x_min: int
    y_min: int
    x_max: int
    y_max: int
    confidence: float | None
    frame_width: int
    frame_height: int
    created_at: datetime


class ROIListResponse(BaseModel):
    items: list[ROIDetectionRead]
    latest: ROIDetectionRead | None = None


class IngestAckMessage(BaseModel):
    frame_number: int
    detected: bool
    x_min: int | None = None
    y_min: int | None = None
    x_max: int | None = None
    y_max: int | None = None
    confidence: float | None = None
    error: str | None = Field(default=None, description="Non-fatal processing error, if any")
