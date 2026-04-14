"""Account lifecycle Pydantic schemas."""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class LifecycleConfigResponse(BaseModel):
    id: int
    category_slug: str = Field(..., max_length=64)
    active_days: int
    dormant_days: int
    auto_alert: bool

    model_config = {"from_attributes": True, "extra": "forbid"}


class LifecycleConfigUpdate(BaseModel):
    active_days: Optional[int] = Field(None, ge=1, le=365)
    dormant_days: Optional[int] = Field(None, ge=1, le=365)
    auto_alert: Optional[bool] = None


class LifecycleStatusItem(BaseModel):
    snapshot_id: int
    asset_id: int
    asset_code: str
    ip: str
    hostname: Optional[str] = Field(None, max_length=256)
    username: str
    uid_sid: str
    is_admin: bool
    lifecycle_status: str
    previous_status: Optional[str]
    last_login: Optional[datetime]
    changed_at: Optional[datetime]
    category: str


class LifecycleDashboard(BaseModel):
    total: int
    active: int
    dormant: int
    departed: int
    unknown: int
    threshold_active: int
    threshold_dormant: int
