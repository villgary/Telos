"""Non-human identity (NHI) Pydantic schemas."""
from datetime import datetime
from typing import Optional, List, Literal
from pydantic import BaseModel

NHITypeLiteral = Literal["service", "system", "cloud", "workload", "cicd", "application", "apikey", "unknown"]
NHILevelLiteral = Literal["critical", "high", "medium", "low"]


class NHIIdentityResponse(BaseModel):
    id: int
    snapshot_id: Optional[int]
    asset_id: Optional[int]
    nhi_type: NHITypeLiteral
    nhi_level: NHILevelLiteral
    username: str
    uid_sid: Optional[str]
    hostname: Optional[str]
    ip_address: Optional[str]
    is_admin: bool
    credential_types: list[str]
    has_nopasswd_sudo: bool
    risk_score: int
    risk_signals: list[dict]
    owner_identity_id: Optional[int]
    owner_email: Optional[str]
    owner_name: Optional[str]
    first_seen_at: Optional[datetime]
    last_seen_at: Optional[datetime]
    last_rotated_at: Optional[datetime]
    rotation_due_days: Optional[int]
    is_active: bool
    is_monitored: bool
    notes: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class NHIInventoryResponse(BaseModel):
    items: list[NHIIdentityResponse]
    total: int
    type_breakdown: dict[str, int]
    level_breakdown: dict[str, int]


class NHIAlertResponse(BaseModel):
    id: int
    nhi_id: int
    alert_type: str
    level: str
    title: str
    message: Optional[str]
    is_read: bool
    status: str
    resolved_at: Optional[datetime]
    created_at: datetime
    nhi_username: Optional[str] = None
    nhi_type: Optional[str] = None
    asset_code: Optional[str] = None

    model_config = {"from_attributes": True}


class NHIDashboardResponse(BaseModel):
    total_nhi: int
    total_human: int
    nhi_ratio: float
    by_type: dict[str, int]
    by_level: dict[str, int]
    critical_count: int
    high_count: int
    no_owner_count: int
    rotation_due_count: int
    has_nopasswd_count: int
    top_risks: list[NHIIdentityResponse]
    recent_alerts: list[NHIAlertResponse]


class NHIPolicyResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    nhi_type: Optional[str]
    severity_filter: Optional[str]
    rotation_days: Optional[int]
    alert_threshold_days: Optional[int]
    require_owner: bool
    require_monitoring: bool
    enabled: bool
    created_at: datetime

    model_config = {"from_attributes": True}
