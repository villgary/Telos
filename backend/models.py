"""
backend.models — ORM models (package).

This file exists for backward compatibility only.
All actual model definitions have moved to backend/models/
"""

# Re-export everything from the models package so that existing imports
# such as "from backend.models import User" continue to work.
from backend.models import (
    # Enums
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
    # Auth models
    User,
    RefreshToken,
    AuditLog,
    # Asset models
    AssetCategoryDef,
    Credential,
    AssetGroup,
    Asset,
    AssetRelationship,
    # Scanning models
    ScanJob,
    AccountSnapshot,
    DiffResult,
    ScanSchedule,
    # Alert / review models
    AlertConfig,
    Alert,
    ReviewPlaybook,
    PlaybookExecution,
    ReviewSchedule,
    ReviewReport,
    # Identity / lifecycle / PAM models
    HumanIdentity,
    IdentityAccount,
    AccountLifecycleConfig,
    AccountLifecycleStatus,
    PAMIntegration,
    PAMSyncedAccount,
    # Risk / UEBA models
    AssetRiskProfile,
    AccountRiskScore,
    AccountBehaviorEvent,
    # Compliance / policy models
    ComplianceFramework,
    ComplianceCheck,
    ComplianceRun,
    ComplianceResult,
    SecurityPolicy,
    PolicyEvaluationResult,
    # Advanced models
    LLMConfig,
    KBEntry,
    IdentityThreatAnalysis,
    ThreatAccountSignal,
    # NHI models
    NHIIdentity,
    NHIAlert,
    NHIPolicy,
)
