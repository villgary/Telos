"""Dashboard and audit Pydantic schemas."""
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel


class CategoryCount(BaseModel):
    category: str
    count: int


class RecentJobStat(BaseModel):
    id: int
    asset_id: int
    status: str
    success_count: int
    failed_count: int
    started_at: datetime


class DashboardStats(BaseModel):
    total_assets: int
    online_assets: int
    offline_assets: int
    auth_failed_assets: int
    total_snapshots: int
    total_jobs: int
    recent_added_accounts: int
    assets_by_category: list[CategoryCount]
    recent_jobs: list[RecentJobStat]


class AuditLogResponse(BaseModel):
    id: int
    user_id: Optional[int]
    action: str
    target_type: Optional[str]
    target_id: Optional[int]
    detail: Optional[dict]
    ip_address: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True, "extra": "forbid"}
