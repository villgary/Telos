import enum
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, Enum,
    ForeignKey, Text, JSON, UniqueConstraint
)
from sqlalchemy.orm import relationship, backref
from backend.database import Base


class UserRole(str, enum.Enum):
    admin = "admin"
    operator = "operator"
    viewer = "viewer"


class SubTypeKind(str, enum.Enum):
    """What kind of sub-type a category uses."""
    none = "none"        # no sub-type
    os = "os"            # OSType (linux/windows)
    database = "database"  # DBType (mysql/postgresql/...)
    network = "network"    # NetworkVendor (cisco/h3c/huawei)
    iot = "iot"            # IoTType (camera/nvr/sensor/...)


class AssetCategoryDef(Base):
    """Dynamic asset category definitions (name, icon, sub-type kind).

    The slug field must match a valid AssetCategory enum value.
    This table holds display metadata (name, icon) and scanner routing hints.
    """
    __tablename__ = "asset_category_defs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    slug = Column(String(32), unique=True, nullable=False, index=True)
    name = Column(String(64), nullable=False)
    description = Column(String(256), nullable=True)
    icon = Column(String(32), nullable=True)          # antd icon name
    sub_type_kind = Column(String(64), nullable=False, default="none")
    parent_id = Column(Integer, ForeignKey("asset_category_defs.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relations
    assets = relationship("Asset", back_populates="category_def")
    parent = relationship("AssetCategoryDef", remote_side=[id], backref="children")


class AssetCategory(str, enum.Enum):
    server = "server"      # OS-level assets (Linux/Windows)
    database = "database"  # Database assets (MySQL/PostgreSQL/Redis/MongoDB/MSSQL)
    network = "network"    # Network devices (Cisco/H3C/Huawei switches/routers)
    iot = "iot"            # IoT devices (cameras, sensors, etc.)


class OSType(str, enum.Enum):
    linux = "linux"
    windows = "windows"


class DBType(str, enum.Enum):
    mysql = "mysql"
    postgresql = "postgresql"
    redis = "redis"
    mongodb = "mongodb"
    mssql = "mssql"
    oracle = "oracle"


class NetworkVendor(str, enum.Enum):
    cisco = "cisco"     # Cisco IOS / IOS-XE / NX-OS
    h3c = "h3c"         # H3C Comware
    huawei = "huawei"   # Huawei VRP
    generic = "generic"  # Unknown vendor — use generic commands


class IoTType(str, enum.Enum):
    camera = "camera"     # IP camera (RTSP / ONVIF / HTTP)
    nvr = "nvr"           # Network Video Recorder
    dvr = "dvr"           # Digital Video Recorder
    sensor = "sensor"     # Environmental / industrial sensor
    gateway = "gateway"   # IoT gateway / hub
    other = "other"


class LLMProvider(str, enum.Enum):
    openai = "openai"
    anthropic = "anthropic"
    ollama = "ollama"           # local
    minimax = "minimax"         # MiniMax M2/M2.5/M2.7
    deepseek = "deepseek"       # DeepSeek
    zhipu = "zhipu"             # 智谱 GLM


class AssetRelationType(str, enum.Enum):
    """Relationship type between two assets."""
    hosts_vm = "hosts_vm"           # Physical machine hosts a VM
    hosts_container = "hosts_container"  # Physical/VM hosts Docker containers
    runs_service = "runs_service"    # OS runs DB / middleware service
    network_peer = "network_peer"    # Network device uplink/downlink
    belongs_to = "belongs_to"       # Asset belongs to a parent (e.g. rack, room)


class AssetStatus(str, enum.Enum):
    untested = "untested"
    online = "online"
    offline = "offline"
    auth_failed = "auth_failed"


class AuthType(str, enum.Enum):
    password = "password"
    ssh_key = "ssh_key"


class ScanJobStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    success = "success"
    partial_success = "partial_success"
    failed = "failed"
    cancelled = "cancelled"


class TriggerType(str, enum.Enum):
    manual = "manual"
    scheduled = "scheduled"


class DiffType(str, enum.Enum):
    added = "added"
    removed = "removed"
    escalated = "escalated"
    deactivated = "deactivated"
    modified = "modified"


class RiskLevel(str, enum.Enum):
    critical = "critical"
    warning = "warning"
    info = "info"


class DiffStatus(str, enum.Enum):
    pending = "pending"
    confirmed_safe = "confirmed_safe"
    confirmed_threat = "confirmed_threat"


class AlertChannel(str, enum.Enum):
    email = "email"
    in_app = "in_app"


class AlertLevel(str, enum.Enum):
    critical = "critical"
    high = "high"
    warning = "warning"
    info = "info"


# ──────────────────────────────────────────
#  Tables
# ──────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    username = Column(String(64), unique=True, nullable=False, index=True)
    password_hash = Column(String(256), nullable=False)
    role = Column(Enum(UserRole), default=UserRole.operator, nullable=False)
    email = Column(String(128), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    is_password_changed = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relations
    created_assets = relationship("Asset", back_populates="creator", foreign_keys="Asset.created_by")
    created_credentials = relationship("Credential", back_populates="creator", foreign_keys="Credential.created_by")
    scan_jobs = relationship("ScanJob", back_populates="creator", foreign_keys="ScanJob.created_by")
    audit_logs = relationship("AuditLog", back_populates="user")


class Credential(Base):
    __tablename__ = "credentials"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(128), unique=True, nullable=False)
    auth_type = Column(Enum(AuthType), nullable=False)
    username = Column(String(128), nullable=False)
    # AES-256-GCM encrypted blobs (stored as base64-like hex strings)
    password_enc = Column(Text, nullable=True)   # only for auth_type=password
    private_key_enc = Column(Text, nullable=True)  # only for auth_type=ssh_key
    passphrase_enc = Column(Text, nullable=True)    # SSH key passphrase
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relations
    creator = relationship("User", back_populates="created_credentials", foreign_keys=[created_by])
    assets = relationship("Asset", back_populates="credential")


class AssetGroup(Base):
    __tablename__ = "asset_groups"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(128), unique=True, nullable=False)
    description = Column(String(512), nullable=True)
    color = Column(String(8), default="#1890ff", nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relations
    creator = relationship("User", foreign_keys=[created_by])
    assets = relationship("Asset", back_populates="asset_group")


class Asset(Base):
    __tablename__ = "assets"
    __table_args__ = (UniqueConstraint("ip", "port", name="uq_asset_ip_port"),)

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    asset_code = Column(String(12), unique=True, nullable=False)  # e.g. ASM-00001
    ip = Column(String(45), nullable=False, index=True)
    hostname = Column(String(255), nullable=True)
    asset_category = Column(Enum(AssetCategory), nullable=False, default=AssetCategory.server)
    # server assets: use os_type
    os_type = Column(Enum(OSType), nullable=True)
    # database assets: use db_type
    db_type = Column(Enum(DBType), nullable=True)
    # network assets: use network_type
    network_type = Column(Enum(NetworkVendor), nullable=True)
    # IoT assets: use iot_type
    iot_type = Column(Enum(IoTType), nullable=True)
    # asset grouping
    group_id = Column(Integer, ForeignKey("asset_groups.id"), nullable=True)
    port = Column(Integer, default=22)
    # Links to AssetCategoryDef for display metadata; enum still used for scanner routing
    asset_category_def_id = Column(Integer, ForeignKey("asset_category_defs.id"), nullable=True)
    # Exact category slug selected by user (for custom categories not in AssetCategory enum)
    category_slug = Column(String(64), nullable=True)
    status = Column(Enum(AssetStatus), default=AssetStatus.untested, nullable=False)
    last_scan_at = Column(DateTime, nullable=True)
    last_scan_job_id = Column(Integer, ForeignKey("scan_jobs.id"), nullable=True)
    credential_id = Column(Integer, ForeignKey("credentials.id"), nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relations
    creator = relationship("User", back_populates="created_assets", foreign_keys=[created_by])
    credential = relationship("Credential", back_populates="assets")
    asset_group = relationship("AssetGroup", back_populates="assets")
    category_def = relationship("AssetCategoryDef", back_populates="assets")
    # Hierarchical relationships — use string refs since AssetRelationship is defined later
    children = relationship(
        "AssetRelationship",
        foreign_keys="AssetRelationship.child_id",
        back_populates="parent",
        cascade="all, delete-orphan",
        viewonly=True,
    )
    parents = relationship(
        "AssetRelationship",
        foreign_keys="AssetRelationship.parent_id",
        back_populates="child",
        cascade="all, delete-orphan",
        viewonly=True,
    )
    scan_jobs = relationship(
        "ScanJob",
        backref=backref("asset", uselist=False),
        foreign_keys="ScanJob.asset_id",
        viewonly=True,
    )
    snapshots = relationship("AccountSnapshot", back_populates="asset")


class ScanJob(Base):
    __tablename__ = "scan_jobs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    asset_id = Column(Integer, ForeignKey("assets.id"), nullable=False)
    trigger_type = Column(Enum(TriggerType), default=TriggerType.manual, nullable=False)
    status = Column(Enum(ScanJobStatus), default=ScanJobStatus.pending, nullable=False)
    success_count = Column(Integer, default=0)
    failed_count = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    finished_at = Column(DateTime, nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relations
    creator = relationship("User", back_populates="scan_jobs", foreign_keys=[created_by])
    snapshots = relationship("AccountSnapshot", back_populates="job")


class AccountSnapshot(Base):
    __tablename__ = "account_snapshots"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    asset_id = Column(Integer, ForeignKey("assets.id"), nullable=False)
    job_id = Column(Integer, ForeignKey("scan_jobs.id"), nullable=False)
    username = Column(String(128), nullable=False, index=True)
    uid_sid = Column(String(256), nullable=False)
    is_admin = Column(Boolean, default=False, nullable=False)
    account_status = Column(String(32), nullable=True)  # enabled/disabled/locked
    home_dir = Column(String(512), nullable=True)
    shell = Column(String(128), nullable=True)
    groups = Column(JSON, default=list)
    sudo_config = Column(JSON, nullable=True)
    last_login = Column(DateTime, nullable=True)
    raw_info = Column(JSON, nullable=True)
    snapshot_time = Column(DateTime, nullable=False)
    is_baseline = Column(Boolean, default=False, nullable=False)
    deleted_at = Column(DateTime, nullable=True)
    # ── Ownership ──────────────────────────────────────────────────────────────
    owner_identity_id = Column(Integer, ForeignKey("human_identities.id"), nullable=True)
    owner_email       = Column(String(256), nullable=True)
    owner_name        = Column(String(128), nullable=True)

    # Relations
    asset = relationship("Asset", back_populates="snapshots")
    job = relationship("ScanJob", back_populates="snapshots")
    owner = relationship("HumanIdentity")


class DiffResult(Base):
    __tablename__ = "diff_results"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    base_job_id = Column(Integer, ForeignKey("scan_jobs.id"), nullable=False)
    compare_job_id = Column(Integer, ForeignKey("scan_jobs.id"), nullable=False)
    diff_type = Column(Enum(DiffType), nullable=False)
    risk_level = Column(Enum(RiskLevel), nullable=False)
    username = Column(String(128), nullable=False)
    snapshot_a_id = Column(Integer, ForeignKey("account_snapshots.id"), nullable=True)
    snapshot_b_id = Column(Integer, ForeignKey("account_snapshots.id"), nullable=True)
    status = Column(Enum(DiffStatus), default=DiffStatus.pending, nullable=False)
    reviewed_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relations
    reviewer = relationship("User", foreign_keys=[reviewed_by])
    snapshot_a = relationship("AccountSnapshot", foreign_keys=[snapshot_a_id], lazy="noload")
    snapshot_b = relationship("AccountSnapshot", foreign_keys=[snapshot_b_id], lazy="noload")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    action = Column(String(64), nullable=False, index=True)
    target_type = Column(String(32), nullable=True)
    target_id = Column(Integer, nullable=True)
    detail = Column(JSON, nullable=True)
    ip_address = Column(String(45), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relations
    user = relationship("User", back_populates="audit_logs")


class ScanSchedule(Base):
    __tablename__ = "scan_schedules"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(128), nullable=False)
    asset_id = Column(Integer, ForeignKey("assets.id"), nullable=False)
    cron_expr = Column(String(64), nullable=False)  # 5-field cron: min hour dom mon dow
    enabled = Column(Boolean, default=True, nullable=False)
    next_run_at = Column(DateTime, nullable=True)
    last_run_at = Column(DateTime, nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relations
    creator = relationship("User", foreign_keys=[created_by])
    asset = relationship("Asset")


class AlertConfig(Base):
    __tablename__ = "alert_configs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(128), nullable=False)
    channel = Column(Enum(AlertChannel), nullable=False)
    enabled = Column(Boolean, default=True, nullable=False)
    # email settings (JSON): {"smtp_host":"...", "smtp_port":587, "from_addr":"...","to_addrs":["..."]}
    settings = Column(JSON, nullable=True)
    # 触发条件: 订阅哪些资产/告警级别
    asset_ids = Column(JSON, default=list)  # 空=全部资产
    risk_levels = Column(JSON, default=list)  # 空=全部级别 ["critical","warning"]
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relations
    creator = relationship("User", foreign_keys=[created_by])
    alerts = relationship("Alert")


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    config_id = Column(Integer, ForeignKey("alert_configs.id"), nullable=True)
    asset_id = Column(Integer, ForeignKey("assets.id"), nullable=False)
    job_id = Column(Integer, ForeignKey("scan_jobs.id"), nullable=True)
    diff_item_id = Column(Integer, ForeignKey("diff_results.id"), nullable=True)
    level = Column(Enum(AlertLevel), nullable=False)
    title = Column(String(256), nullable=False)
    message = Column(Text, nullable=False)
    title_key = Column(String(64), nullable=True)
    title_params = Column(JSON, nullable=True)
    message_key = Column(String(64), nullable=True)
    message_params = Column(JSON, nullable=True)
    is_read = Column(Boolean, default=False, nullable=False)
    status = Column(String(16), default="new", nullable=False)  # new / acknowledged / dismissed / responded
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    # 归属人路由：告警优先通知账号责任人
    target_identity_id = Column(Integer, ForeignKey("human_identities.id"), nullable=True)

    # Relations
    config = relationship("AlertConfig", foreign_keys=[config_id], overlaps="alerts")
    asset = relationship("Asset")
    job = relationship("ScanJob", foreign_keys=[job_id])
    diff_result = relationship("DiffResult", foreign_keys=[diff_item_id])
    target_identity = relationship("HumanIdentity", foreign_keys=[target_identity_id])


# ─── Review Playbooks ─────────────────────────────────────────────────────────────────

class ReviewPlaybook(Base):
    """
    Automated remediation playbook definition.

    Steps are JSON: [{"action": "disable_account", "target": "snapshot"},
                      {"action": "notify_owner", "target": "identity"}]
    """
    __tablename__ = "review_playbooks"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(128), nullable=False)
    description = Column(Text, nullable=True)
    name_key = Column(String(128), nullable=True)        # i18n key for built-in playbooks
    description_key = Column(String(128), nullable=True)  # i18n key for built-in playbooks
    trigger_type = Column(String(32), nullable=False)   # alert / schedule / manual
    trigger_filter = Column(JSON, default=dict)          # {"level": "critical", "type": "nopasswd_sudo"}
    steps = Column(JSON, default=list)                   # list of step dicts
    approval_required = Column(Boolean, default=True)
    enabled = Column(Boolean, default=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relations
    creator = relationship("User", foreign_keys=[created_by])
    executions = relationship("PlaybookExecution", back_populates="playbook")


class PlaybookExecution(Base):
    """
    Record of a single playbook execution instance.
    """
    __tablename__ = "playbook_executions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    playbook_id = Column(Integer, ForeignKey("review_playbooks.id"), nullable=False)
    snapshot_id = Column(Integer, ForeignKey("account_snapshots.id"), nullable=False)
    status = Column(String(24), nullable=False, default="pending_approval")
        # pending_approval / approved / executing / done / rejected / failed
    steps_status = Column(JSON, default=list)   # [{"step": 0, "status": "done", "result": "..."}]
    result = Column(Text, nullable=True)
    triggered_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    approved_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    approved_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relations
    playbook = relationship("ReviewPlaybook", back_populates="executions")
    snapshot = relationship("AccountSnapshot")
    trigger_user = relationship("User", foreign_keys=[triggered_by])
    approver = relationship("User", foreign_keys=[approved_by])


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    # SHA-256 hash of the actual token (never store raw token)
    token_hash = Column(String(64), unique=True, nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    revoked = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    ip_address = Column(String(45), nullable=True)

    # Relations
    user = relationship("User")


class AssetRelationship(Base):
    __tablename__ = "asset_relationships"
    __table_args__ = (
        UniqueConstraint("parent_id", "child_id", name="uq_rel_parent_child"),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    parent_id = Column(Integer, ForeignKey("assets.id", ondelete="CASCADE"), nullable=False)
    child_id = Column(Integer, ForeignKey("assets.id", ondelete="CASCADE"), nullable=False)
    relation_type = Column(Enum(AssetRelationType), nullable=False)
    description = Column(String(256), nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relations
    parent = relationship("Asset", foreign_keys=[parent_id], backref="child_relations")
    child = relationship("Asset", foreign_keys=[child_id], backref="parent_relations")
    creator = relationship("User", foreign_keys=[created_by])


class LLMConfig(Base):
    """Global LLM provider configuration."""
    __tablename__ = "llm_configs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    provider = Column(Enum(LLMProvider), nullable=False)
    api_key_enc = Column(Text, nullable=True)      # encrypted
    base_url = Column(String(256), nullable=True)  # for ollama / custom endpoint
    model = Column(String(64), nullable=False, default="gpt-4o-mini")
    enabled = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class AssetRiskProfile(Base):
    """
    Per-asset risk profile with propagation.
    risk_score: final propagated score (0-100)
    risk_factors: [{factor, score, description, target}]
    propagation_path: [{asset_code, ip, risk_score, relation, is_entry_point}]
    """
    __tablename__ = "asset_risk_profiles"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    asset_id = Column(Integer, ForeignKey("assets.id"), unique=True, nullable=False)
    risk_score = Column(Integer, default=0)          # 0-100
    risk_level = Column(String(16), default="low")   # low/medium/high/critical
    risk_factors = Column(JSON, default=list)         # [{factor, score, description, target}]
    affected_children = Column(Integer, default=0)   # downstream affected count
    propagation_path = Column(JSON, nullable=True)  # propagation chain nodes
    computed_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    asset = relationship("Asset", backref="risk_profile")


# ─────────────── Compliance ────────────────────────────────────────────────────

class ComplianceFramework(Base):
    """Compliance framework definition (SOC2, ISO27001, 等保2.0)."""
    __tablename__ = "compliance_frameworks"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    slug = Column(String(32), unique=True, nullable=False)
    name = Column(String(64), nullable=False)
    description = Column(Text, nullable=True)
    version = Column(String(16), nullable=False, default="1.0")
    enabled = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    checks = relationship("ComplianceCheck", back_populates="framework", cascade="all, delete-orphan")
    runs = relationship("ComplianceRun", back_populates="framework", cascade="all, delete-orphan")


class ComplianceCheck(Base):
    """
    A single compliance check within a framework.
    check_key: identifies which Python function evaluates this check
    applies_to: comma-sep asset categories this check applies to (e.g. "server,database")
    parameters: JSON dict of threshold/override values
    """
    __tablename__ = "compliance_checks"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    framework_id = Column(Integer, ForeignKey("compliance_frameworks.id"), nullable=False)
    check_key = Column(String(64), nullable=False)
    title = Column(String(256), nullable=False)
    description = Column(Text, nullable=True)
    severity = Column(String(16), nullable=False, default="medium")  # critical/high/medium/low
    applies_to = Column(String(128), nullable=False, default="server,database,network,iot")
    parameters = Column(JSON, nullable=True)  # threshold overrides
    enabled = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    framework = relationship("ComplianceFramework", back_populates="checks")

    __table_args__ = (
        UniqueConstraint("framework_id", "check_key", name="uq_fw_check_key"),
    )


class ComplianceRun(Base):
    """One execution of a compliance framework evaluation."""
    __tablename__ = "compliance_runs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    framework_id = Column(Integer, ForeignKey("compliance_frameworks.id"), nullable=False)
    trigger_type = Column(String(16), nullable=False, default="manual")  # manual/scheduled/api
    status = Column(String(16), nullable=False, default="running")    # running/completed/failed
    total = Column(Integer, default=0)
    passed = Column(Integer, default=0)
    failed = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    finished_at = Column(DateTime, nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)

    framework = relationship("ComplianceFramework", back_populates="runs")
    creator = relationship("User", foreign_keys=[created_by])
    results = relationship("ComplianceResult", back_populates="run", cascade="all, delete-orphan")


class ComplianceResult(Base):
    """
    Result of one check against one asset within a run.
    status: pass / fail / error
    evidence: [{asset_code, ip, username, description}]
    """
    __tablename__ = "compliance_results"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    run_id = Column(Integer, ForeignKey("compliance_runs.id"), nullable=False)
    framework_id = Column(Integer, ForeignKey("compliance_frameworks.id"), nullable=False)
    check_id = Column(Integer, ForeignKey("compliance_checks.id"), nullable=False)
    asset_id = Column(Integer, ForeignKey("assets.id"), nullable=False)
    status = Column(String(8), nullable=False)  # pass / fail / error
    evidence = Column(JSON, nullable=True)       # [{asset_code, ip, username, description}]
    error_message = Column(Text, nullable=True)
    evaluated_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    run = relationship("ComplianceRun", back_populates="results")
    framework = relationship("ComplianceFramework")
    check = relationship("ComplianceCheck")
    asset = relationship("Asset")

    __table_args__ = (
        UniqueConstraint("run_id", "check_id", name="uq_run_check"),
    )


# ─────────────── Identity Fusion ───────────────────────────────────────────────

class HumanIdentity(Base):
    """
    A natural-person identity inferred from cross-asset account matching.
    Groups accounts by UID, username, or manual linking.
    """
    __tablename__ = "human_identities"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    display_name = Column(String(128), nullable=True)   # e.g. "zhangsan"
    email = Column(String(256), nullable=True)
    primary_asset_id = Column(Integer, ForeignKey("assets.id"), nullable=True)
    confidence = Column(Integer, default=0)             # 0-100
    source = Column(String(16), default="auto")         # auto / manual
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    accounts = relationship("IdentityAccount", back_populates="identity", cascade="all, delete-orphan")
    primary_asset = relationship("Asset")


class IdentityAccount(Base):
    """
    Links a natural-person identity to a specific account snapshot.
    """
    __tablename__ = "identity_accounts"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    identity_id = Column(Integer, ForeignKey("human_identities.id"), nullable=False)
    snapshot_id = Column(Integer, ForeignKey("account_snapshots.id"), nullable=False)
    asset_id = Column(Integer, ForeignKey("assets.id"), nullable=False)
    match_type = Column(String(16), nullable=False)     # uid / username / email / manual
    match_confidence = Column(Integer, default=0)       # 0-100
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    identity = relationship("HumanIdentity", back_populates="accounts")
    snapshot = relationship("AccountSnapshot")
    asset = relationship("Asset")

    __table_args__ = (
        UniqueConstraint("identity_id", "snapshot_id", name="uq_identity_snapshot"),
    )


# ─────────────── Account Lifecycle ──────────────────────────────────────────────

class LifecycleStatus(str, enum.Enum):
    active = "active"        # last login within active_days
    dormant = "dormant"      # last login between active and dormant
    departed = "departed"    # last login >= dormant_days or account deleted
    unknown = "unknown"      # never logged in


class AccountLifecycleConfig(Base):
    """
    Configurable thresholds for account lifecycle state machine.
    A record with category_slug='global' is the global default.
    Category-specific records override the global defaults.
    """
    __tablename__ = "account_lifecycle_configs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    category_slug = Column(String(32), unique=True, nullable=False, default="global")
    active_days = Column(Integer, nullable=False, default=30)
    dormant_days = Column(Integer, nullable=False, default=90)
    auto_alert = Column(Boolean, nullable=False, default=True)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class AccountLifecycleStatus(Base):
    """
    Computed lifecycle status for each account snapshot.
    Computed in batch after each scan.
    """
    __tablename__ = "account_lifecycle_statuses"

    id = Column(Integer, primary_key=True, autoincrement=True)
    snapshot_id = Column(Integer, ForeignKey("account_snapshots.id"), unique=True, nullable=False)
    lifecycle_status = Column(String(16), nullable=False, default="unknown")
    previous_status = Column(String(16), nullable=True)
    changed_at = Column(DateTime, nullable=True)
    alert_sent = Column(Boolean, nullable=False, default=False)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    snapshot = relationship("AccountSnapshot")


# ─────────────── PAM Integration ─────────────────────────────────────────────────

class PAMIntegration(Base):
    """Read-only integration with PAM/Bastion systems."""
    __tablename__ = "pam_integrations"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(128), nullable=False)
    provider = Column(String(32), nullable=False)
    config = Column(JSON, nullable=True)
    status = Column(String(16), default="active")
    last_sync_at = Column(DateTime, nullable=True)
    last_error = Column(Text, nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    created_user = relationship("User")
    synced_accounts = relationship("PAMSyncedAccount", back_populates="integration", cascade="all, delete-orphan")


class PAMSyncedAccount(Base):
    """Accounts synced from PAM system."""
    __tablename__ = "pam_synced_accounts"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    integration_id = Column(Integer, ForeignKey("pam_integrations.id"), nullable=False)
    asset_id = Column(Integer, ForeignKey("assets.id"), nullable=True)
    account_name = Column(String(128), nullable=False)
    account_type = Column(String(32), nullable=False)
    pam_status = Column(String(16), nullable=False)
    last_used = Column(DateTime, nullable=True)
    matched_snapshot_id = Column(Integer, ForeignKey("account_snapshots.id"), nullable=True)
    match_confidence = Column(Integer, default=0)
    synced_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    integration = relationship("PAMIntegration", back_populates="synced_accounts")
    asset = relationship("Asset")
    snapshot = relationship("AccountSnapshot")


# ─────────────── Review Reminders ────────────────────────────────────────────────

class ReviewSchedule(Base):
    """Scheduled periodic account review reminders."""
    __tablename__ = "review_schedules"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(128), nullable=False)
    period = Column(String(16), nullable=False)   # monthly / quarterly
    day_of_month = Column(Integer, default=1)    # 1-28
    alert_channels = Column(JSON, nullable=True)   # {"email": [...], "webhook": "..."}
    enabled = Column(Boolean, default=True, nullable=False)
    next_run_at = Column(DateTime, nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    created_user = relationship("User")
    reports = relationship("ReviewReport", back_populates="schedule", cascade="all, delete-orphan")


class ReviewReport(Base):
    """Generated account review report."""
    __tablename__ = "review_reports"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    schedule_id = Column(Integer, ForeignKey("review_schedules.id"), nullable=False)
    period = Column(String(16), nullable=False)
    period_start = Column(DateTime, nullable=False)
    period_end = Column(DateTime, nullable=False)
    status = Column(String(16), default="pending_review")  # draft / pending_review / approved / dismissed
    reviewed_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    notes = Column(Text, nullable=True)
    content_summary = Column(JSON, nullable=True)  # {"dormant_accounts": [...], "departed_accounts": [...], ...}
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    schedule = relationship("ReviewSchedule", back_populates="reports")
    reviewer = relationship("User")


# ─────────────── Account Risk Score ────────────────────────────────────────────────

class AccountRiskScore(Base):
    """Per-account risk score computed from login activity, privilege, and identity fusion."""
    __tablename__ = "account_risk_scores"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    snapshot_id = Column(Integer, ForeignKey("account_snapshots.id"), nullable=False, unique=True)
    risk_score = Column(Integer, default=0, nullable=False)   # 0-100
    risk_level = Column(String(16), nullable=False, default="low")  # critical/high/medium/low
    risk_factors = Column(JSON, default=list, nullable=False)  # [{"factor": "...", "score": N}]
    identity_id = Column(Integer, ForeignKey("human_identities.id"), nullable=True)
    cross_asset_count = Column(Integer, default=0)
    computed_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    snapshot = relationship("AccountSnapshot")
    identity = relationship("HumanIdentity")


# ─────────────── OPA/Rego Policy Engine ───────────────────────────────────────────

class SecurityPolicy(Base):
    """
    Rego-based security policy stored in DB.
    Evaluated against account snapshots to detect policy violations.
    """
    __tablename__ = "security_policies"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(128), nullable=False)
    description = Column(Text, nullable=True)
    name_key = Column(String(128), nullable=True)           # i18n key for built-in policies
    description_key = Column(String(128), nullable=True)     # i18n key for built-in policies
    category = Column(String(32), nullable=True)  # e.g. "privilege", "lifecycle", "compliance"
    severity = Column(String(16), nullable=False, default="high")  # critical / high / medium / low
    rego_code = Column(Text, nullable=False)   # Rego policy code
    enabled = Column(Boolean, default=True, nullable=False)
    is_built_in = Column(Boolean, default=False, nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    creator = relationship("User")
    evaluation_results = relationship("PolicyEvaluationResult", back_populates="policy", cascade="all, delete-orphan")


class PolicyEvaluationResult(Base):
    """
    Result of evaluating a SecurityPolicy against an AccountSnapshot.
    """
    __tablename__ = "policy_evaluation_results"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    policy_id = Column(Integer, ForeignKey("security_policies.id"), nullable=False)
    snapshot_id = Column(Integer, ForeignKey("account_snapshots.id"), nullable=False)
    passed = Column(Boolean, nullable=False)
    message = Column(Text, nullable=True)
    evaluated_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    policy = relationship("SecurityPolicy", back_populates="evaluation_results")
    snapshot = relationship("AccountSnapshot")
# ─────────────── UEBA ────────────────────────────────────────────────────────────────

class AccountBehaviorEvent(Base):
    """
    Detected account behavior anomalies (UEBA events).
    Computed by services/ueba_service.py on each scan completion or on-demand.
    """
    __tablename__ = "account_behavior_events"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    event_type = Column(String(32), nullable=False, index=True)
    # event_type values: dormant_to_active, went_dormant, new_privileged_account,
    #   privileged_no_login, privilege_escalation, cross_asset_awakening
    severity = Column(String(16), nullable=False, default="medium")  # critical / high / medium / low
    username = Column(String(128), nullable=False, index=True)
    asset_code = Column(String(32), nullable=True)
    asset_ip = Column(String(45), nullable=True)
    description = Column(Text, nullable=True)
    description_key = Column(String(64), nullable=True)
    description_params = Column(JSON, nullable=True)
    snapshot_id = Column(Integer, ForeignKey("account_snapshots.id"), nullable=True)
    detected_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    snapshot = relationship("AccountSnapshot")


# ─────────────── Knowledge Base Admin ───────────────────────────────────────────

class KBEntry(Base):
    """
    Custom KB entries added by admins via the UI.
    Coexists with the static built-in KB data in kb_data.py.
    """
    __tablename__ = "kb_entries"

    id             = Column(Integer, primary_key=True, autoincrement=True)
    entry_type     = Column(String(16), nullable=False, index=True)  # mitre / cve / practice
    title          = Column(String(256), nullable=False)
    title_en       = Column(String(256), nullable=True)
    description    = Column(Text, nullable=True)
    description_en = Column(Text, nullable=True)
    extra_data      = Column("extra_data", JSON, default=dict, nullable=False)
    enabled        = Column(Boolean, default=True, nullable=False)
    created_by     = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at     = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at     = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    creator = relationship("User")


# ─────────────── Identity Threat Analysis ─────────────────────────────────────────

class IdentityThreatAnalysis(Base):
    """
    Results of the Identity Threat Cognitive Analysis Engine (五层分析).
    One record per analysis run. Contains scores and signals for all 5 layers.
    """
    __tablename__ = "identity_threat_analyses"

    id                     = Column(Integer, primary_key=True, autoincrement=True)
    analysis_type          = Column(String(32), nullable=False)   # full / targeted
    scope                  = Column(String(32), nullable=False)   # global / asset / identity
    scope_id               = Column(Integer, nullable=True)        # nullable for global

    # Five-layer scores (0-100)
    semiotic_score         = Column(Integer, nullable=False, default=0)
    causal_score           = Column(Integer, nullable=False, default=0)
    ontological_score      = Column(Integer, nullable=False, default=0)
    cognitive_score        = Column(Integer, nullable=False, default=0)
    anthropological_score  = Column(Integer, nullable=False, default=0)

    # Overall
    overall_score          = Column(Integer, nullable=False, default=0)
    overall_level          = Column(String(16), nullable=False)   # critical / high / medium / low

    # Five-layer signal details (JSON)
    semiotic_signals       = Column(JSON, default=list)
    causal_signals         = Column(JSON, default=list)
    ontological_signals    = Column(JSON, default=list)
    cognitive_signals      = Column(JSON, default=list)
    anthropological_signals= Column(JSON, default=list)

    # Threat graph snapshot
    threat_graph           = Column(JSON, default=dict)   # {nodes: [], edges: []}

    # LLM-generated natural language report
    llm_report             = Column(Text, nullable=True)

    # Metadata
    analyzed_count         = Column(Integer, default=0)
    duration_ms            = Column(Integer, nullable=True)
    model_used             = Column(String(64), nullable=True)
    created_by             = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at             = Column(DateTime, default=datetime.utcnow, nullable=False)

    creator = relationship("User")


class ThreatAccountSignal(Base):
    """
    Per-account signal明细 from the five-layer analysis.
    Linked to an IdentityThreatAnalysis run.
    """
    __tablename__ = "threat_account_signals"

    id                    = Column(Integer, primary_key=True, autoincrement=True)
    analysis_id           = Column(Integer, ForeignKey("identity_threat_analyses.id"), nullable=False)
    snapshot_id           = Column(Integer, ForeignKey("account_snapshots.id"), nullable=True)
    username              = Column(String(128), nullable=False)
    asset_id              = Column(Integer, nullable=False)
    asset_code            = Column(String(32), nullable=True)

    # Five-layer flags (JSON lists of signal objects)
    semiotic_flags        = Column(JSON, default=list)
    causal_flags          = Column(JSON, default=list)
    ontological_flags     = Column(JSON, default=list)
    cognitive_flags       = Column(JSON, default=list)
    anthropological_flags = Column(JSON, default=list)

    # Account-level risk
    account_score         = Column(Integer, default=0)
    account_level         = Column(String(16), default="low")   # critical / high / medium / low

    created_at            = Column(DateTime, default=datetime.utcnow, nullable=False)

    analysis = relationship("IdentityThreatAnalysis")


# ─────────────── NHI Module ────────────────────────────────────────────────────

class NHIType(str, enum.Enum):
    """Non-human identity type taxonomy."""
    SERVICE_ACCOUNT = "service"       # Application service account (nologin shell)
    SYSTEM_ACCOUNT = "system"        # OS system account (root/daemon/bin)
    CLOUD_IDENTITY = "cloud"        # AWS IAM Role / Azure SP / GCP SA
    WORKLOAD = "workload"           # K8s SA / 容器身份
    CI_CD_PIPELINE = "cicd"         # GitHub Actions / Jenkins
    APPLICATION = "application"      # OAuth App / SaaS App
    API_KEY = "apikey"              # Bare API key / PAT
    UNKNOWN = "unknown"


class NHILevel(str, enum.Enum):
    """NHI risk severity level."""
    CRITICAL = "critical"   # NOPASSWD sudo / shared SSH key across assets
    HIGH = "high"          # Privileged service account / long-lived token
    MEDIUM = "medium"     # Normal service account
    LOW = "low"           # System account (no risk)


class NHIIdentity(Base):
    """
    Non-human identity registry — one record per unique NHI discovered.
    """
    __tablename__ = "nhi_identities"

    id                = Column(Integer, primary_key=True, autoincrement=True)
    # Source reference: links to account_snapshot if discovered from a scan
    snapshot_id       = Column(Integer, ForeignKey("account_snapshots.id"), nullable=True)
    asset_id          = Column(Integer, ForeignKey("assets.id"), nullable=True)
    # Classification
    nhi_type          = Column(String(32), nullable=False, default="unknown")  # NHIType
    nhi_level         = Column(String(16), nullable=False, default="low")      # NHILevel
    # Identity attributes
    username          = Column(String(128), nullable=False, index=True)
    uid_sid           = Column(String(256), nullable=True)
    hostname          = Column(String(256), nullable=True)
    ip_address        = Column(String(64), nullable=True)
    is_admin          = Column(Boolean, default=False)
    # Credential summary (derived from raw_info scan data)
    credential_types  = Column(JSON, default=list)   # ["ssh_key", "password", "token", "cert"]
    has_nopasswd_sudo = Column(Boolean, default=False)
    # Risk
    risk_score        = Column(Integer, default=0)   # 0-100
    risk_signals      = Column(JSON, default=list)    # List of risk signal objects
    # Ownership
    owner_identity_id = Column(Integer, ForeignKey("human_identities.id"), nullable=True)
    owner_email       = Column(String(256), nullable=True)
    owner_name        = Column(String(128), nullable=True)
    # Lifecycle
    first_seen_at     = Column(DateTime, nullable=True)
    last_seen_at     = Column(DateTime, nullable=True)
    last_rotated_at   = Column(DateTime, nullable=True)  # Last credential rotation
    rotation_due_days = Column(Integer, nullable=True)  # Days until rotation due (null = N/A)
    # Status
    is_active         = Column(Boolean, default=True)
    is_monitored      = Column(Boolean, default=False)
    notes             = Column(Text, nullable=True)
    created_at        = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at        = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    snapshot   = relationship("AccountSnapshot")
    asset      = relationship("Asset")
    owner      = relationship("HumanIdentity")


class NHIAlert(Base):
    """
    NHI-specific alerts — generated by realtime monitor or scheduled analysis.
    """
    __tablename__ = "nhi_alerts"

    id                = Column(Integer, primary_key=True, autoincrement=True)
    nhi_id            = Column(Integer, ForeignKey("nhi_identities.id"), nullable=False)
    alert_type        = Column(String(64), nullable=False)  # rotation_due / no_owner / privilege_escalation / credential_leak
    level             = Column(String(16), nullable=False)  # critical / high / medium / warning
    title             = Column(String(256), nullable=False)
    message           = Column(Text, nullable=False)
    title_key         = Column(String(64), nullable=True)
    title_params      = Column(JSON, nullable=True)
    message_key       = Column(String(64), nullable=True)
    message_params    = Column(JSON, nullable=True)
    is_read           = Column(Boolean, default=False)
    status            = Column(String(16), default="new")  # new / acknowledged / resolved / dismissed
    resolved_at       = Column(DateTime, nullable=True)
    resolved_by       = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at        = Column(DateTime, default=datetime.utcnow, nullable=False)

    nhi         = relationship("NHIIdentity")
    resolver    = relationship("User")


class NHIPolicy(Base):
    """
    NHI governance policies — defines rotation cycles, monitoring rules, etc.
    """
    __tablename__ = "nhi_policies"

    id                = Column(Integer, primary_key=True, autoincrement=True)
    name             = Column(String(128), nullable=False, unique=True)
    description      = Column(Text, nullable=True)
    nhi_type          = Column(String(32), nullable=True)     # Apply to specific type, null = all
    severity_filter   = Column(String(16), nullable=True)     # Apply to specific level
    rotation_days     = Column(Integer, nullable=True)        # Required rotation cycle
    alert_threshold_days = Column(Integer, nullable=True)     # Days before rotation due to alert
    require_owner     = Column(Boolean, default=True)
    require_monitoring= Column(Boolean, default=False)
    enabled           = Column(Boolean, default=True)
    created_by       = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at        = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at        = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    creator = relationship("User")
