"""Alert Pydantic schemas."""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field

from backend.models._enums import AlertChannel, AlertLevel


class AlertConfigCreate(BaseModel):
    name: str = Field(..., max_length=128)
    channel: AlertChannel
    enabled: bool = True
    settings: Optional[dict] = None
    asset_ids: List[int] = []
    risk_levels: List[str] = []


class AlertConfigUpdate(BaseModel):
    name: Optional[str] = None
    enabled: Optional[bool] = None
    settings: Optional[dict] = None
    asset_ids: Optional[List[int]] = None
    risk_levels: Optional[List[str]] = None


class AlertConfigResponse(BaseModel):
    id: int
    name: str
    channel: AlertChannel
    enabled: bool
    settings: Optional[dict]
    asset_ids: List[int]
    risk_levels: List[str]
    created_by: Optional[int]
    created_at: datetime

    model_config = {"from_attributes": True, "extra": "forbid"}


class AlertResponse(BaseModel):
    id: int
    config_id: Optional[int]
    asset_id: int
    job_id: Optional[int]
    level: AlertLevel
    title: str
    message: str
    title_key: Optional[str] = None
    title_params: Optional[dict] = None
    message_key: Optional[str] = None
    message_params: Optional[dict] = None
    is_read: bool
    status: str = "new"
    created_at: datetime

    model_config = {"from_attributes": True, "extra": "forbid"}


class AlertListResponse(BaseModel):
    total: int
    unread_count: int
    alerts: List[AlertResponse]
