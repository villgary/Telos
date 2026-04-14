import re
from datetime import datetime, timedelta
from typing import Optional, List, Any
from pydantic import BaseModel, EmailStr, Field, field_validator
from backend.models import UserRole, OSType, AssetStatus, AuthType, ScanJobStatus, DiffType, RiskLevel, AlertChannel, AlertLevel, AssetCategory, DBType, NetworkVendor, IoTType, SubTypeKind, AssetRelationType, LLMProvider


# ─────────────── Auth ───────────────

# ── Shared password strength checker (used by Pydantic validators) ──
_PASSWORD_SPECIAL_PATTERN = r"[!@#$%^&*(),.?\":{}|<>_+\-/\[\] ]"


def _check_password_strength(password: str, *, field_name: str = "") -> None:
    """Raise ValueError if password doesn't meet strength requirements."""
    errors = []
    if len(password) < 8:
        errors.append("至少8个字符")
    if not re.search(r"[A-Z]", password):
        errors.append("至少包含一个大写字母")
    if not re.search(r"[a-z]", password):
        errors.append("至少包含一个小写字母")
    if not re.search(r"\d", password):
        errors.append("至少包含一个数字")
    if not re.search(_PASSWORD_SPECIAL_PATTERN, password):
        errors.append("至少包含一个特殊字符")
    if errors:
        prefix = f"{field_name}不符合安全要求: " if field_name else "密码不符合安全要求: "
        raise ValueError(prefix + "; ".join(errors))


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


class RefreshRequest(BaseModel):
    refresh_token: str


class RefreshResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class UserResponse(BaseModel):
    id: int
    username: str
    role: UserRole
    email: Optional[str]
    is_active: bool
    is_password_changed: bool
    created_at: datetime

    class Config:
        from_attributes = True


class UserCreate(BaseModel):
    username: str = Field(..., min_length=2, max_length=64)
    password: str = Field(..., min_length=8)
    role: UserRole = UserRole.operator
    email: Optional[str] = None

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        _check_password_strength(v)
        return v


class UserUpdate(BaseModel):
    role: Optional[UserRole] = None
    email: Optional[str] = None
    is_active: Optional[bool] = None
    password: Optional[str] = Field(None, min_length=8)

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if v is None:
            return v
        _check_password_strength(v)
        return v


class PasswordChange(BaseModel):
    old_password: str
    new_password: str = Field(..., min_length=8)

    @field_validator("new_password")
    @classmethod
    def new_password_strength(cls, v: str) -> str:
        _check_password_strength(v, field_name="新密码")
        return v


# ─────────────── Credential ───────────────

class CredentialBase(BaseModel):
    name: str = Field(..., max_length=128)
    auth_type: AuthType
    username: str = Field(..., max_length=128)
    password: Optional[str] = None  # only used when creating/updating
    private_key: Optional[str] = None  # only used when auth_type=ssh_key
    passphrase: Optional[str] = None


class CredentialCreate(CredentialBase):
    pass


class CredentialUpdate(BaseModel):
    name: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    private_key: Optional[str] = None
    passphrase: Optional[str] = None


class CredentialResponse(BaseModel):
    id: int
    name: str
    auth_type: AuthType
    username: str
    has_password: bool
    has_private_key: bool
    created_by: Optional[int]
    created_at: datetime

    class Config:
        from_attributes = True

    @classmethod
    def from_orm_full(cls, cred):
        return cls(
            id=cred.id,
            name=cred.name,
            auth_type=cred.auth_type,
            username=cred.username,
            has_password=cred.password_enc is not None,
            has_private_key=cred.private_key_enc is not None,
            created_by=cred.created_by,
            created_at=cred.created_at,
        )


# ─────────────── Asset Category ───────────────

class AssetCategoryDefCreate(BaseModel):
    slug: str = Field(..., max_length=32, description="唯一标识，如 'server'/'database'/'custom-app'")
    name: str = Field(..., max_length=64)
    description: Optional[str] = Field(None, max_length=256)
    icon: Optional[str] = Field(None, max_length=32, description="Antd 图标名，如 'CloudServerOutlined'")
    sub_type_kind: str = Field("none", max_length=64, description="子类型标识，如 'os'/'database'，可自定义")
    parent_id: Optional[int] = Field(None, description="父品类 ID，留空为顶级品类")


class AssetCategoryDefUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=64)
    description: Optional[str] = None
    icon: Optional[str] = Field(None, max_length=32)
    sub_type_kind: Optional[str] = Field(None, max_length=64)
    parent_id: Optional[int] = Field(None)


class AssetCategoryDefResponse(BaseModel):
    id: int
    slug: str
    name: str
    name_i18n_key: Optional[str] = None  # e.g. "category.server" → frontend uses t()
    description: Optional[str]
    icon: Optional[str]
    sub_type_kind: str
    parent_id: Optional[int]

    class Config:
        from_attributes = True


class AssetCategoryTreeResponse(BaseModel):
    id: int
    slug: str
    name: str
    name_i18n_key: Optional[str] = None
    sub_type_kind: str
    children: List["AssetCategoryTreeResponse"] = []

    class Config:
        from_attributes = True


# ─────────────── Asset Group ───────────────

class AssetGroupCreate(BaseModel):
    name: str = Field(..., max_length=128)
    description: Optional[str] = Field(None, max_length=512)
    color: str = Field("#1890ff", max_length=8)


class AssetGroupUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=128)
    description: Optional[str] = None
    color: Optional[str] = Field(None, max_length=8)


class AssetGroupResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    color: str
    created_by: Optional[int]
    created_at: datetime

    class Config:
        from_attributes = True


# ─────────────── Asset ───────────────

class AssetBase(BaseModel):
    ip: str = Field(..., max_length=45)
    hostname: Optional[str] = None
    asset_category: Optional[AssetCategory] = None
    asset_category_def_id: Optional[int] = None
    # Exact category slug selected in the UI (for custom categories)
    category_slug: Optional[str] = Field(None, max_length=64)
    os_type: Optional[OSType] = None
    db_type: Optional[DBType] = None
    network_type: Optional[NetworkVendor] = None
    iot_type: Optional[IoTType] = None
    group_id: Optional[int] = None
    port: int = 22
    credential_id: int


class AssetCreate(AssetBase):
    pass


class AssetUpdate(BaseModel):
    ip: Optional[str] = None
    hostname: Optional[str] = None
    asset_category: Optional[AssetCategory] = None
    asset_category_def_id: Optional[int] = None
    category_slug: Optional[str] = Field(None, max_length=64)
    os_type: Optional[OSType] = None
    db_type: Optional[DBType] = None
    network_type: Optional[NetworkVendor] = None
    iot_type: Optional[IoTType] = None
    group_id: Optional[int] = None
    port: Optional[int] = None
    credential_id: Optional[int] = None


class AssetResponse(BaseModel):
    id: int
    asset_code: str
    ip: str
    hostname: Optional[str]
    asset_category: AssetCategory
    asset_category_def_id: Optional[int]
    category_slug: Optional[str] = Field(None, max_length=64)
    os_type: Optional[OSType]
    db_type: Optional[DBType]
    network_type: Optional[NetworkVendor]
    iot_type: Optional[IoTType]
    group_id: Optional[int]
    port: int
    status: AssetStatus
    last_scan_at: Optional[datetime]
    last_scan_job_id: Optional[int]
    credential_id: int
    created_by: Optional[int]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ─────────────── Asset Relationship ───────────────

RELATION_TYPE_LABELS: dict[str, str] = {
    "hosts_vm": "承载虚拟机",
    "hosts_container": "承载容器",
    "runs_service": "运行服务",
    "network_peer": "网络互联",
    "belongs_to": "归属关系",
}


class AssetRelationshipCreate(BaseModel):
    parent_id: int = Field(..., description="父资产 ID")
    child_id: int = Field(..., description="子资产 ID")
    relation_type: AssetRelationType
    description: Optional[str] = Field(None, max_length=256)


class AssetRelationshipUpdate(BaseModel):
    relation_type: Optional[AssetRelationType] = None
    description: Optional[str] = Field(None, max_length=256)


class AccountSummaryItem(BaseModel):
    """Lightweight account info for hierarchy display."""
    id: int
    username: str
    is_admin: bool
    account_status: Optional[str]
    last_login: Optional[datetime]

    class Config:
        from_attributes = True


class AssetSummary(BaseModel):
    id: int
    asset_code: str
    ip: str
    hostname: Optional[str]
    asset_category: AssetCategory
    # Snapshot stats from latest scan
    account_count: int = 0
    admin_count: int = 0
    latest_accounts: list[AccountSummaryItem] = []

    class Config:
        from_attributes = True


class AssetRelationshipResponse(BaseModel):
    id: int
    parent_id: int
    child_id: int
    relation_type: AssetRelationType
    description: Optional[str]
    created_by: Optional[int]
    created_at: datetime
    parent: AssetSummary
    child: AssetSummary

    class Config:
        from_attributes = True


class HierarchyNode(BaseModel):
    asset: AssetSummary
    relation_type: Optional[str] = None  # relation from this node to its parent
    children: list["HierarchyNode"] = []


HierarchyNode.model_rebuild()


# ─────────────── Scan Job ───────────────

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

    class Config:
        from_attributes = True


class ScanJobDetail(ScanJobResponse):
    asset_ip: str
    snapshots: List["SnapshotResponse"] = []


# ─────────────── Snapshot ───────────────

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
    owner_name: Optional[str] = None

    class Config:
        from_attributes = True


class SnapshotOwnerAssign(BaseModel):
    """Request body to assign an owner to a snapshot."""
    owner_email: Optional[str] = None
    owner_name: Optional[str] = None


class SnapshotOwnerResponse(BaseModel):
    """Owner info for a snapshot."""
    snapshot_id: int
    username: str
    asset_id: int
    owner_identity_id: Optional[int] = None
    owner_email: Optional[str] = None
    owner_name: Optional[str] = None


# ─────────────── Diff ───────────────

class DiffRequest(BaseModel):
    base_job_id: int
    compare_job_id: int


class DiffItem(BaseModel):
    diff_type: DiffType
    risk_level: RiskLevel
    username: str
    uid_sid: str
    field_changes: Optional[dict] = None  # {field: (old_val, new_val)}


class DiffResponse(BaseModel):
    base_job_id: int
    compare_job_id: int
    items: List[DiffItem]
    summary: dict  # {added: n, removed: n, escalated: n, ...}


# ─────────────── Dashboard ───────────────

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
    recent_added_accounts: int  # last 24h
    assets_by_category: list[CategoryCount]
    recent_jobs: list[RecentJobStat]


# ─────────────── Audit Log ───────────────

class AuditLogResponse(BaseModel):
    id: int
    user_id: Optional[int]
    action: str
    target_type: Optional[str]
    target_id: Optional[int]
    detail: Optional[dict]
    ip_address: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


# ─────────────── Scan Schedule ───────────────

class ScanScheduleCreate(BaseModel):
    name: str = Field(..., max_length=128)
    asset_id: int
    cron_expr: str = Field(..., description="5-field cron: min hour dom mon dow, e.g. '0 3 * * *' = 3am daily")


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

    class Config:
        from_attributes = True


# ─────────────── Alert Config ───────────────

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

    class Config:
        from_attributes = True


# ─────────────── Alert ───────────────

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

    class Config:
        from_attributes = True


class AlertListResponse(BaseModel):
    total: int
    unread_count: int
    alerts: List[AlertResponse]


# ─────────────── LLM Config ───────────────

class LLMConfigCreate(BaseModel):
    provider: LLMProvider = LLMProvider.openai
    api_key: Optional[str] = Field(None, max_length=256)
    base_url: Optional[str] = Field(None, max_length=256)
    model: str = Field("gpt-4o-mini", max_length=64)
    enabled: bool = False


class LLMConfigUpdate(BaseModel):
    provider: Optional[LLMProvider] = None
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    model: Optional[str] = None
    enabled: Optional[bool] = None


class LLMConfigResponse(BaseModel):
    id: int
    provider: LLMProvider
    api_key_set: bool  # True if key is configured (never expose the key itself)
    base_url: Optional[str]
    model: str
    enabled: bool
    created_at: datetime

    class Config:
        from_attributes = True


# ─────────────── AI Report ───────────────

class AIReportRequest(BaseModel):
    asset_id: Optional[int] = None
    scan_job_id: Optional[int] = None
    report_type: str = Field("threat_analysis", description="threat_analysis | compliance | summary")
    lang: Optional[str] = Field("zh-CN", description="zh-CN | en-US")


class AIReportResponse(BaseModel):
    success: bool
    report: Optional[str]  # Markdown text
    error: Optional[str] = None


# ─────────────── Executive Dashboard ───────────────

class ExecutiveMetrics(BaseModel):
    risk_score: int = Field(ge=0, le=100, description="Overall risk score 0-100")
    risk_level: str  # low / medium / high / critical
    total_assets: int
    total_accounts: int
    high_risk_accounts: int
    dormant_accounts: int  # 90+ days no login
    unlogin_admin_accounts: int
    compliance_ready: float = Field(ge=0, le=100, description="Compliance readiness %")
    trends: dict  # {period: "7d", account_change: +3, high_risk_change: -1}
    ai_summary: Optional[str] = None


# ─────────────── Risk Propagation ───────────────

class RiskFactorItem(BaseModel):
    factor: str
    score: int
    description: Optional[str] = None
    target: Optional[str] = None  # username or asset_code


class PropagationNode(BaseModel):
    asset_code: str
    ip: str
    hostname: Optional[str] = None
    risk_score: int
    relation: Optional[str] = None  # relation from parent to this node
    is_entry_point: bool = False   # True if this is the high-risk leaf


class AssetRiskProfileResponse(BaseModel):
    asset: AssetSummary
    risk_score: int
    risk_level: str
    risk_factors: list[RiskFactorItem]
    affected_children_count: int
    propagation_path: list[PropagationNode]
    computed_at: datetime

    class Config:
        from_attributes = True


class RiskOverviewItem(BaseModel):
    asset_id: int
    asset_code: str
    ip: str
    hostname: Optional[str] = None
    risk_score: int
    risk_level: str
    affected_children_count: int

    class Config:
        from_attributes = True


class RiskHotspotEntry(BaseModel):
    asset_code: str
    ip: str
    hostname: Optional[str] = None
    risk_score: int


class RiskHotspotResponse(BaseModel):
    hotspots: list["RiskHotspotItem"]


class RiskHotspotItem(BaseModel):
    entry_asset: RiskHotspotEntry
    root_asset: dict
    max_risk_score: int
    path: list[str]
    risk_description: str
    chain_length: int
    nodes: list["PropagationNode"]


# ─────────────── Compliance ────────────────────────────────────────────────────

class ComplianceFrameworkResponse(BaseModel):
    id: int
    slug: str
    name: str
    description: Optional[str]
    version: str
    enabled: bool
    created_at: datetime

    class Config:
        from_attributes = True


class ComplianceEvidenceItem(BaseModel):
    asset_code: str
    ip: str
    hostname: Optional[str] = None
    username: Optional[str] = None
    description: str
    description_key: Optional[str] = None


class ComplianceCheckResultItem(BaseModel):
    """Latest result for one check (most recent run)."""
    check_key: str
    title: str
    description: Optional[str]
    title_key: Optional[str] = None
    description_key: Optional[str] = None
    severity: str
    status: str  # pass / fail / error / never_run
    failed_count: int
    passed_count: int
    evidence: list[ComplianceEvidenceItem] = []


class ComplianceCheckResponse(BaseModel):
    id: int
    framework_id: int
    check_key: str
    title: str
    description: Optional[str]
    severity: str
    applies_to: str
    enabled: bool
    latest_result: Optional[ComplianceCheckResultItem] = None

    class Config:
        from_attributes = True


class ComplianceRunResponse(BaseModel):
    id: int
    framework_id: int
    framework_slug: str
    framework_name: str
    trigger_type: str
    status: str
    total: int
    passed: int
    failed: int
    error_message: Optional[str]
    started_at: datetime
    finished_at: Optional[datetime]
    created_by: Optional[int]

    class Config:
        from_attributes = True


class ComplianceFrameworkDashboard(BaseModel):
    """One framework with aggregated score and check list."""
    slug: str
    name: str
    description: Optional[str]
    name_key: Optional[str] = None
    description_key: Optional[str] = None
    score: int          # percentage 0-100
    total: int
    passed: int
    failed: int
    checks: list[ComplianceCheckResultItem]


class ComplianceDashboardResponse(BaseModel):
    frameworks: list[ComplianceFrameworkDashboard]


class ComplianceResultResponse(BaseModel):
    id: int
    run_id: int
    check_id: int
    check_key: str
    check_title: str
    asset_id: int
    asset_code: str
    ip: str
    hostname: Optional[str]
    status: str
    evidence: Optional[list[dict]]
    evaluated_at: datetime

    class Config:
        from_attributes = True


# ─────────────── Identity Fusion ────────────────────────────────────────────────

class IdentityAccountItem(BaseModel):
    id: int
    snapshot_id: int
    asset_id: int
    asset_code: str
    ip: str
    hostname: Optional[str]
    username: str
    uid_sid: str
    is_admin: bool
    account_status: Optional[str]
    last_login: Optional[datetime]
    match_type: str
    match_confidence: int

    class Config:
        from_attributes = True


class HumanIdentityResponse(BaseModel):
    id: int
    display_name: Optional[str]
    email: Optional[str]
    confidence: int
    source: str
    account_count: int
    admin_count: int
    asset_count: int
    max_risk_score: int
    latest_login: Optional[datetime]
    accounts: list[IdentityAccountItem]

    class Config:
        from_attributes = True


class HumanIdentitySummary(BaseModel):
    id: int
    display_name: Optional[str]
    confidence: int
    source: str
    account_count: int
    admin_count: int
    asset_count: int
    max_risk_score: int
    latest_login: Optional[datetime]

    class Config:
        from_attributes = True


class IdentityLinkRequest(BaseModel):
    identity_id: int
    snapshot_id: int
    match_type: str = "manual"
    match_confidence: int = 100


class IdentitySuggestion(BaseModel):
    snapshot_id: int
    asset_code: str
    ip: str
    username: str
    uid_sid: str
    is_admin: bool
    match_reason: str
    candidate_identities: list[int]  # existing identity IDs that could match


# ─────────────── Account Lifecycle ────────────────────────────────────────────────

class LifecycleConfigResponse(BaseModel):
    id: int
    category_slug: str = Field(..., max_length=64)
    active_days: int
    dormant_days: int
    auto_alert: bool

    class Config:
        from_attributes = True


class LifecycleConfigUpdate(BaseModel):
    active_days: Optional[int] = Field(None, ge=1, le=365)
    dormant_days: Optional[int] = Field(None, ge=1, le=365)
    auto_alert: Optional[bool] = None


class LifecycleStatusItem(BaseModel):
    snapshot_id: int
    asset_id: int
    asset_code: str
    ip: str
    hostname: Optional[str]
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


# ─────────────── PAM Integration ────────────────────────────────────────────────

class PAMIntegrationCreate(BaseModel):
    name: str = Field(..., max_length=128)
    provider: str = Field(..., max_length=32)  # tencent_cloud_bastion / aliyun_bastion / cyberark / custom_api
    config: Optional[dict] = None              # provider-specific config JSON


class PAMIntegrationUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=128)
    config: Optional[dict] = None
    status: Optional[str] = None


class PAMIntegrationResponse(BaseModel):
    id: int
    name: str
    provider: str
    status: str
    last_sync_at: Optional[datetime]
    last_error: Optional[str]
    created_by: Optional[int]
    created_at: datetime
    account_count: int = 0

    class Config:
        from_attributes = True


class PAMSyncedAccountItem(BaseModel):
    id: int
    integration_id: int
    account_name: str
    account_type: str
    pam_status: str
    last_used: Optional[datetime]
    matched_asset_code: Optional[str]
    matched_asset_ip: Optional[str]
    matched_username: Optional[str]
    is_admin: bool
    match_confidence: int
    comparison_result: str  # matched / unmatched_pam / unmatched_ascore / privileged_gap

    class Config:
        from_attributes = True


class PAMComparisonItem(BaseModel):
    integration_name: str
    integration_id: int
    account_name: str
    account_type: str
    pam_status: str
    last_used: Optional[datetime]
    asset_code: Optional[str]
    asset_ip: Optional[str]
    is_admin: bool
    result: str  # compliant / privileged_gap / unmanaged
    result_label: str


# ─────────────── Review Reminders ────────────────────────────────────────────────

class ReviewScheduleCreate(BaseModel):
    name: str = Field(..., max_length=128)
    period: str = Field("monthly", max_length=16)   # monthly / quarterly
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

    class Config:
        from_attributes = True


class ReviewReportResponse(BaseModel):
    id: int
    schedule_id: int
    period: str
    period_start: datetime
    period_end: datetime
    status: str
    reviewed_by: Optional[int]
    reviewed_at: Optional[datetime]
    notes: Optional[str]
    content_summary: Optional[dict]
    created_at: datetime
    schedule_name: Optional[str] = None
    reviewer_name: Optional[str] = None

    class Config:
        from_attributes = True


# ─────────────── Account Risk Score ────────────────────────────────────────────────

class RiskFactorSimple(BaseModel):
    factor: str
    score: int


class AccountRiskScoreResponse(BaseModel):
    id: int
    snapshot_id: int
    risk_score: int
    risk_level: str
    risk_factors: list[RiskFactorSimple]
    identity_id: Optional[int] = None
    cross_asset_count: int = 0
    computed_at: datetime
    # denormalised snapshot info
    username: Optional[str] = None
    asset_code: Optional[str] = None
    asset_ip: Optional[str] = None
    is_admin: bool = False
    last_login: Optional[datetime] = None
    # owner fields
    owner_identity_id: Optional[int] = None
    owner_email: Optional[str] = None
    owner_name: Optional[str] = None

    class Config:
        from_attributes = True


# ── Knowledge Base ─────────────────────────────────────────────────────────────

class KBEntryCreate(BaseModel):
    entry_type: str       # mitre / cve / practice
    title: str
    title_en: Optional[str] = None
    description: Optional[str] = None
    description_en: Optional[str] = None
    extra_data: dict = {}

    class Config:
        from_attributes = True


class KBEntryUpdate(BaseModel):
    title: Optional[str] = None
    title_en: Optional[str] = None
    description: Optional[str] = None
    description_en: Optional[str] = None
    extra_data: Optional[dict] = None
    enabled: Optional[bool] = None

    class Config:
        from_attributes = True


class KBEntryResponse(BaseModel):
    id: int
    entry_type: str
    title: str
    title_en: Optional[str] = None
    description: Optional[str] = None
    description_en: Optional[str] = None
    extra_data: dict = {}
    enabled: bool = True
    created_by: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ─────────────── Identity Threat Analysis ─────────────────────────────────────────

class ThreatSignalItem(BaseModel):
    type: str
    detail: str
    severity: str = "info"
    evidence: Optional[str] = None


class ThreatLayerSignals(BaseModel):
    node_id: Optional[str] = None
    snapshot_id: Optional[int] = None
    username: Optional[str] = None
    asset_code: Optional[str] = None
    signals: list[ThreatSignalItem] = []


class ThreatGraphNode(BaseModel):
    id: str
    snapshot_id: int
    username: str
    uid_sid: str
    asset_id: int
    asset_code: Optional[str]
    ip: Optional[str]
    hostname: Optional[str]
    is_admin: bool
    lifecycle: str
    last_login: Optional[str] = None
    sudo_config: dict = {}
    raw_info: dict = {}
    groups: list[str] = []
    shell: Optional[str] = None
    home_dir: Optional[str] = None
    account_status: str = "unknown"
    identity_id: Optional[int] = None
    account_score: int = 0
    account_level: str = "low"
    nhi_type: Optional[str] = None


class ThreatGraphEdge(BaseModel):
    source: str
    target: str
    edge_type: str
    weight: float


class ThreatGraphData(BaseModel):
    nodes: list[ThreatGraphNode] = []
    edges: list[ThreatGraphEdge] = []


class IdentityThreatAnalysisResponse(BaseModel):
    id: int
    analysis_type: str
    scope: str
    scope_id: Optional[int]
    semiotic_score: int
    causal_score: int
    ontological_score: int
    cognitive_score: int
    anthropological_score: int
    overall_score: int
    overall_level: str
    semiotic_signals: list
    causal_signals: list
    ontological_signals: list
    cognitive_signals: list
    anthropological_signals: list
    threat_graph: ThreatGraphData
    total_nodes: int = 0
    total_edges: int = 0
    total_semiotic: int = 0
    total_causal: int = 0
    total_ontological: int = 0
    total_cognitive: int = 0
    total_anthropological: int = 0
    llm_report: Optional[str]
    analyzed_count: int
    duration_ms: Optional[int]
    model_used: Optional[str]
    created_by: Optional[int]
    created_at: datetime

    class Config:
        from_attributes = True


class IdentityThreatAnalysisListItem(BaseModel):
    id: int
    analysis_type: str
    scope: str
    scope_id: Optional[int]
    scope_label: Optional[str] = None  # asset_code for "asset" scope, identity name for "identity" scope
    overall_score: int
    overall_level: str
    analyzed_count: int
    duration_ms: Optional[int]
    created_by: Optional[int]
    created_at: datetime

    class Config:
        from_attributes = True


class ThreatAccountSignalResponse(BaseModel):
    id: int
    analysis_id: int
    snapshot_id: Optional[int]
    username: str
    asset_id: int
    asset_code: Optional[str]
    semiotic_flags: list
    causal_flags: list
    ontological_flags: list
    cognitive_flags: list
    anthropological_flags: list
    account_score: int
    account_level: str
    created_at: datetime

    class Config:
        from_attributes = True


class AnalyzeRequest(BaseModel):
    scope: str = "global"   # global / asset / identity
    scope_id: Optional[int] = None
    lang: str = "zh"        # zh / en


class AnalyzeResponse(BaseModel):
    id: int
    analysis_type: str
    scope: str
    overall_score: int
    overall_level: str
    analyzed_count: int
    duration_ms: Optional[int]
    llm_report: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


# ─────────────── NHI Module ────────────────────────────────────────────────────

class NHITypeEnum(str):
    SERVICE = "service"
    SYSTEM = "system"
    CLOUD = "cloud"
    WORKLOAD = "workload"
    CI_CD = "cicd"
    APPLICATION = "application"
    API_KEY = "apikey"
    UNKNOWN = "unknown"


class NHILevelEnum(str):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class NHIIdentityResponse(BaseModel):
    id: int
    snapshot_id: Optional[int]
    asset_id: Optional[int]
    nhi_type: str
    nhi_level: str
    username: str
    uid_sid: Optional[str]
    hostname: Optional[str]
    ip_address: Optional[str]
    is_admin: bool
    credential_types: list[str]
    has_nopasswd_sudo: bool
    risk_score: int
    risk_signals: list
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

    class Config:
        from_attributes = True


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

    class Config:
        from_attributes = True


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

    class Config:
        from_attributes = True


# Forward reference resolution
DiffResponse.model_rebuild()
ScanJobDetail.model_rebuild()
