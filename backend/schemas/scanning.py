"""Scanning-related Pydantic schemas."""
from datetime import datetime
from typing import Optional, List, Any, TYPE_CHECKING
from pydantic import BaseModel, Field

from backend.models._enums import ScanJobStatus, DiffType, RiskLevel

if TYPE_CHECKING:
    from backend.schemas.scanning import SnapshotResponse


class ScanJobResponse(BaseModel):
    id: int
    asset_id: int
    asset_ip: Optional[str] = None
    trigger_type: str
    status: ScanJobStatus
    success_count: int
    failed_count: int
    error_message: Optional[str]
    started_at: datetime
    finished_at: Optional[datetime]
    created_by: Optional[int]
    created_at: datetime

    model_config = {"from_attributes": True, "extra": "forbid"}


class ScanJobDetail(ScanJobResponse):
    asset_ip: str
    snapshots: List["SnapshotResponse"] = []


class SnapshotResponse(BaseModel):
    id: int
    asset_id: int
    job_id: int
    username: str
    uid_sid: str
    is_admin: bool
    account_status: Optional[str]
    home_dir: Optional[str]
    shell: Optional[str]
    groups: List[Any]
    last_login: Optional[datetime]
    snapshot_time: datetime
    is_baseline: bool = False
    owner_identity_id: Optional[int] = None
    owner_email: Optional[str] = None
    owner_name: Optional[str] = Field(None, max_length=128)

    model_config = {"from_attributes": True, "extra": "forbid"}


class SnapshotOwnerAssign(BaseModel):
    owner_email: Optional[str] = Field(None, max_length=128)
    owner_name: Optional[str] = Field(None, max_length=128)


class SnapshotOwnerResponse(BaseModel):
    snapshot_id: int
    username: str
    asset_id: int
    owner_identity_id: Optional[int] = None
    owner_email: Optional[str] = Field(None, max_length=128)
    owner_name: Optional[str] = Field(None, max_length=128)


class DiffRequest(BaseModel):
    base_job_id: int
    compare_job_id: int


class DiffItem(BaseModel):
    diff_type: DiffType
    risk_level: RiskLevel
    username: str
    uid_sid: str
    field_changes: Optional[dict] = None


class DiffResponse(BaseModel):
    base_job_id: int
    compare_job_id: int
    items: List[DiffItem]
    summary: dict


class ScanScheduleCreate(BaseModel):
    name: str = Field(..., max_length=128)
    asset_id: int
    cron_expr: str = Field(...)


class ScanScheduleUpdate(BaseModel):
    name: Optional[str] = None
    cron_expr: Optional[str] = None
    enabled: Optional[bool] = None


class ScanScheduleResponse(BaseModel):
    id: int
    name: str
    asset_id: int
    cron_expr: str
    enabled: bool
    next_run_at: Optional[datetime]
    last_run_at: Optional[datetime]
    created_by: Optional[int]
    created_at: datetime

    model_config = {"from_attributes": True, "extra": "forbid"}


DiffResponse.model_rebuild()
ScanJobDetail.model_rebuild()
