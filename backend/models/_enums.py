"""
All SQLAlchemy-independent enum definitions.
Re-exported by models/__init__.py and schemas.py imports.
"""
import enum


class UserRole(str, enum.Enum):
    admin = "admin"
    operator = "operator"
    viewer = "viewer"


class SubTypeKind(str, enum.Enum):
    """What kind of sub-type a category uses."""
    none = "none"
    os = "os"
    database = "database"
    network = "network"
    iot = "iot"


class AssetCategory(str, enum.Enum):
    server = "server"
    database = "database"
    network = "network"
    iot = "iot"


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
    cisco = "cisco"
    h3c = "h3c"
    huawei = "huawei"
    generic = "generic"


class IoTType(str, enum.Enum):
    camera = "camera"
    nvr = "nvr"
    dvr = "dvr"
    sensor = "sensor"
    gateway = "gateway"
    other = "other"


class LLMProvider(str, enum.Enum):
    openai = "openai"
    anthropic = "anthropic"
    ollama = "ollama"
    minimax = "minimax"
    deepseek = "deepseek"
    zhipu = "zhipu"


class AssetRelationType(str, enum.Enum):
    hosts_vm = "hosts_vm"
    hosts_container = "hosts_container"
    runs_service = "runs_service"
    network_peer = "network_peer"
    belongs_to = "belongs_to"


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


class LifecycleStatus(str, enum.Enum):
    active = "active"
    dormant = "dormant"
    departed = "departed"
    unknown = "unknown"


class NHIType(str, enum.Enum):
    SERVICE_ACCOUNT = "service"
    SYSTEM_ACCOUNT = "system"
    CLOUD_IDENTITY = "cloud"
    WORKLOAD = "workload"
    CI_CD_PIPELINE = "cicd"
    APPLICATION = "application"
    API_KEY = "apikey"
    UNKNOWN = "unknown"


class NHILevel(str, enum.Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
