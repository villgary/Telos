"""
backend.models — ORM models organized by domain.

Re-exports everything from the old monolithic models.py so that
existing imports (from backend.models import User) continue to work.
The actual class definitions live in the submodules below.
"""

# ── Enums ────────────────────────────────────────────────────────────────
from backend.models._enums import (
    UserRole,
    SubTypeKind,
    AssetCategory,
    OSType,
    DBType,
    NetworkVendor,
    IoTType,
    LLMProvider,
    AssetRelationType,
    AssetStatus,
    AuthType,
    ScanJobStatus,
    TriggerType,
    DiffType,
    RiskLevel,
    DiffStatus,
    AlertChannel,
    AlertLevel,
    LifecycleStatus,
    NHIType,
    NHILevel,
)

# ── Auth models ───────────────────────────────────────────────────────
from backend.models.auth import User, RefreshToken, AuditLog

# ── Asset models ──────────────────────────────────────────────────────
from backend.models.assets import (
    AssetCategoryDef,
    Credential,
    AssetGroup,
    Asset,
    AssetRelationship,
)

# ── Scanning models ──────────────────────────────────────────────────
from backend.models.scanning import (
    ScanJob,
    AccountSnapshot,
    DiffResult,
    ScanSchedule,
)

# ── Alert / review models ─────────────────────────────────────────────
from backend.models.alerts import (
    AlertConfig,
    Alert,
    ReviewPlaybook,
    PlaybookExecution,
    ReviewSchedule,
    ReviewReport,
)

# ── Identity / lifecycle / PAM models ─────────────────────────────────
from backend.models.identities import (
    HumanIdentity,
    IdentityAccount,
    AccountLifecycleConfig,
    AccountLifecycleStatus,
    PAMIntegration,
    PAMSyncedAccount,
)

# ── Risk / UEBA models ────────────────────────────────────────────────
from backend.models.risk import (
    AssetRiskProfile,
    AccountRiskScore,
    AccountBehaviorEvent,
)

# ── Compliance / policy models ─────────────────────────────────────────
from backend.models.compliance import (
    ComplianceFramework,
    ComplianceCheck,
    ComplianceRun,
    ComplianceResult,
    SecurityPolicy,
    PolicyEvaluationResult,
)

# ── Advanced models (LLM, KB, threat analysis) ───────────────────────
from backend.models.advanced import (
    LLMConfig,
    KBEntry,
    IdentityThreatAnalysis,
    ThreatAccountSignal,
)

# ── NHI models ────────────────────────────────────────────────────────
from backend.models.nhi import (
    NHIIdentity,
    NHIAlert,
    NHIPolicy,
)
