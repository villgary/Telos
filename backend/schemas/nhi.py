"""Non-human identity (NHI) Pydantic schemas."""
from datetime import datetime
from typing import Optional, List, Literal
from pydantic import BaseModel, Field, field_validator

NHITypeLiteral = Literal["service", "system", "cloud", "workload", "cicd", "application", "apikey", "ai_agent", "unknown"]
NHILevelLiteral = Literal["critical", "high", "medium", "low"]
NHIAlertTypeLiteral = Literal[
    "privilege_escalation", "nopasswd_sudo", "credential_leak",
    "cross_asset_spread", "risk_alert", "no_owner",
]

ALLOWED_ALERT_TYPES = {
    "privilege_escalation", "nopasswd_sudo", "credential_leak",
    "cross_asset_spread", "risk_alert", "no_owner",
}


def _validate_alert_types_list(v: Optional[List[str]]) -> Optional[List[str]]:
    if v is None:
        return v
    for item in v:
        if item not in ALLOWED_ALERT_TYPES:
            raise ValueError(f"Unknown alert type: {item!r}. Allowed: {sorted(ALLOWED_ALERT_TYPES)}")
    return v


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
    nhi_id: Optional[int]
    cluster_key: Optional[str] = None
    nhi_username: Optional[str] = None
    nhi_type: Optional[str] = None
    asset_count: Optional[int] = None
    alert_type: str
    level: str
    title: str
    message: Optional[str]
    is_read: bool
    status: str
    resolved_at: Optional[datetime]
    created_at: datetime
    updated_at: Optional[datetime] = None

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


class NHIPolicyBase(BaseModel):
    name: str
    description: Optional[str] = None
    nhi_type: Optional[str] = None
    severity_filter: Optional[str] = None
    rotation_days: Optional[int] = None
    alert_threshold_days: Optional[int] = None
    require_owner: bool = True
    require_monitoring: bool = False
    enabled_alert_types: Optional[List[str]] = None
    cross_asset_threshold: Optional[int] = Field(default=None, ge=2, le=100)
    cross_asset_window_days: Optional[int] = Field(default=None, ge=1, le=365)
    enabled: bool = True

    _v_alert_types = field_validator("enabled_alert_types")(_validate_alert_types_list)


class NHIPolicyCreate(NHIPolicyBase):
    pass


class NHIPolicyUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    nhi_type: Optional[str] = None
    severity_filter: Optional[str] = None
    rotation_days: Optional[int] = None
    alert_threshold_days: Optional[int] = None
    require_owner: Optional[bool] = None
    require_monitoring: Optional[bool] = None
    enabled_alert_types: Optional[List[str]] = None
    cross_asset_threshold: Optional[int] = Field(default=None, ge=2, le=100)
    cross_asset_window_days: Optional[int] = Field(default=None, ge=1, le=365)
    enabled: Optional[bool] = None

    _v_alert_types = field_validator("enabled_alert_types")(_validate_alert_types_list)


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
    enabled_alert_types: Optional[List[str]] = None
    cross_asset_threshold: Optional[int] = None
    cross_asset_window_days: Optional[int] = None
    enabled: bool
    created_at: datetime

    model_config = {"from_attributes": True}
