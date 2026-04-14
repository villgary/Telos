"""Review reminder Pydantic schemas."""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class ReviewScheduleCreate(BaseModel):
    name: str = Field(..., max_length=128)
    period: str = Field("monthly", max_length=16)
    day_of_month: int = Field(1, ge=1, le=28)
    alert_channels: Optional[dict] = None
    enabled: bool = True


class ReviewScheduleUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=128)
    period: Optional[str] = None
    day_of_month: Optional[int] = Field(None, ge=1, le=28)
    alert_channels: Optional[dict] = None
    enabled: Optional[bool] = None


class ReviewScheduleResponse(BaseModel):
    id: int
    name: str
    period: str
    day_of_month: int
    alert_channels: Optional[dict]
    enabled: bool
    next_run_at: Optional[datetime]
    created_by: Optional[int]
    created_at: datetime

    model_config = {"from_attributes": True, "extra": "forbid"}


class ReviewReportResponse(BaseModel):
    id: int
    schedule_id: int
    period: str
    period_start: datetime
    period_end: datetime
    status: str
    reviewed_by: Optional[int]
    reviewed_at: Optional[datetime]
    notes: Optional[str] = Field(None, max_length=1024)
    content_summary: Optional[dict]
    created_at: datetime
    schedule_name: Optional[str] = None
    reviewer_name: Optional[str] = Field(None, max_length=128)

    model_config = {"from_attributes": True, "extra": "forbid"}
