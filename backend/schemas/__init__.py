"""
backend.schemas — Pydantic request/response models organized by domain.

Re-exports everything from the old monolithic schemas.py for backward compatibility.
"""

# ── Shared utilities ──────────────────────────────────────────────────
from backend.schemas._shared import _check_password_strength, _PASSWORD_SPECIAL_PATTERN, RELATION_TYPE_LABELS

# ── Auth schemas ────────────────────────────────────────────────────
from backend.schemas.auth import (
    LoginRequest, TokenResponse, RefreshRequest, RefreshResponse,
    UserResponse, UserCreate, UserUpdate, PasswordChange,
)

# ── Credential schemas ────────────────────────────────────────────────
from backend.schemas.credentials import (
    CredentialBase, CredentialCreate, CredentialUpdate, CredentialResponse,
)

# ── Asset schemas ────────────────────────────────────────────────────
from backend.schemas.assets import (
    AssetCategoryDefCreate, AssetCategoryDefUpdate, AssetCategoryDefResponse,
    AssetCategoryTreeResponse,
    AssetGroupCreate, AssetGroupUpdate, AssetGroupResponse,
    AssetBase, AssetCreate, AssetUpdate, AssetResponse,
    AssetRelationshipCreate, AssetRelationshipUpdate,
    AccountSummaryItem, AssetSummary,
    AssetRelationshipResponse, HierarchyNode,
)

# ── Scanning schemas ──────────────────────────────────────────────────
from backend.schemas.scanning import (
    ScanJobResponse, ScanJobDetail,
    SnapshotResponse, SnapshotOwnerAssign, SnapshotOwnerResponse,
    DiffRequest, DiffItem, DiffResponse,
    ScanScheduleCreate, ScanScheduleUpdate, ScanScheduleResponse,
)

# ── Dashboard / audit schemas ─────────────────────────────────────────
from backend.schemas.dashboard import (
    CategoryCount, RecentJobStat, DashboardStats,
    AuditLogResponse,
)

# ── Alert schemas ────────────────────────────────────────────────────
from backend.schemas.alerts import (
    AlertConfigCreate, AlertConfigUpdate, AlertConfigResponse,
    AlertResponse, AlertListResponse,
)

# ── AI / LLM schemas ─────────────────────────────────────────────────
from backend.schemas.ai import (
    LLMConfigCreate, LLMConfigUpdate, LLMConfigResponse,
    AIReportRequest, AIReportResponse,
    ExecutiveMetrics,
)

# ── Risk schemas ─────────────────────────────────────────────────────
from backend.schemas.risk import (
    RiskFactorItem, RiskFactorSimple,
    PropagationNode,
    AssetRiskProfileResponse,
    RiskOverviewItem,
    RiskHotspotEntry, RiskHotspotItem, RiskHotspotResponse,
    AccountRiskScoreResponse,
)

# ── Compliance schemas ────────────────────────────────────────────────
from backend.schemas.compliance import (
    ComplianceFrameworkResponse,
    ComplianceEvidenceItem, ComplianceCheckResultItem,
    ComplianceCheckResponse,
    ComplianceRunResponse,
    ComplianceFrameworkDashboard, ComplianceDashboardResponse,
    ComplianceResultResponse,
)

# ── Identity schemas ─────────────────────────────────────────────────
from backend.schemas.identities import (
    IdentityAccountItem,
    HumanIdentityResponse, HumanIdentitySummary,
    IdentityLinkRequest, IdentitySuggestion,
)

# ── Lifecycle schemas ────────────────────────────────────────────────
from backend.schemas.lifecycle import (
    LifecycleConfigResponse, LifecycleConfigUpdate,
    LifecycleStatusItem, LifecycleDashboard,
)

# ── PAM schemas ──────────────────────────────────────────────────────
from backend.schemas.pam import (
    PAMIntegrationCreate, PAMIntegrationUpdate, PAMIntegrationResponse,
    PAMSyncedAccountItem, PAMComparisonItem,
)

# ── Review schemas ────────────────────────────────────────────────────
from backend.schemas.review import (
    ReviewScheduleCreate, ReviewScheduleUpdate, ReviewScheduleResponse,
    ReviewReportResponse,
)

# ── Knowledge base schemas ───────────────────────────────────────────
from backend.schemas.kb import (
    KBEntryCreate, KBEntryUpdate, KBEntryResponse,
)

# ── Threat analysis schemas ──────────────────────────────────────────
from backend.schemas.threat import (
    ThreatSignalItem, ThreatLayerSignals,
    ThreatGraphNode, ThreatGraphEdge, ThreatGraphData,
    IdentityThreatAnalysisResponse, IdentityThreatAnalysisListItem,
    ThreatAccountSignalResponse,
    AnalyzeRequest, AnalyzeResponse,
)

# ── NHI schemas ──────────────────────────────────────────────────────
from backend.schemas.nhi import (
    NHITypeLiteral, NHILevelLiteral,
    NHIIdentityResponse, NHIInventoryResponse,
    NHIAlertResponse, NHIDashboardResponse, NHIPolicyResponse,
)
