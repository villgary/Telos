"""
backend.schemas — Pydantic request/response models (package).

This file exists for backward compatibility only.
All actual schema definitions have moved to backend/schemas/
"""

# Re-export everything so that existing imports such as
# "from backend.schemas import UserResponse" continue to work.
from backend.schemas import (
    # Shared
    _check_password_strength,
    _PASSWORD_SPECIAL_PATTERN,
    RELATION_TYPE_LABELS,
    # Auth
    LoginRequest, TokenResponse, RefreshRequest, RefreshResponse,
    UserResponse, UserCreate, UserUpdate, PasswordChange,
    # Credentials
    CredentialBase, CredentialCreate, CredentialUpdate, CredentialResponse,
    # Assets
    AssetCategoryDefCreate, AssetCategoryDefUpdate, AssetCategoryDefResponse,
    AssetCategoryTreeResponse,
    AssetGroupCreate, AssetGroupUpdate, AssetGroupResponse,
    AssetBase, AssetCreate, AssetUpdate, AssetResponse,
    AssetRelationshipCreate, AssetRelationshipUpdate,
    AccountSummaryItem, AssetSummary,
    AssetRelationshipResponse, HierarchyNode,
    # Scanning
    ScanJobResponse, ScanJobDetail,
    SnapshotResponse, SnapshotOwnerAssign, SnapshotOwnerResponse,
    DiffRequest, DiffItem, DiffResponse,
    ScanScheduleCreate, ScanScheduleUpdate, ScanScheduleResponse,
    # Dashboard
    CategoryCount, RecentJobStat, DashboardStats,
    AuditLogResponse,
    # Alerts
    AlertConfigCreate, AlertConfigUpdate, AlertConfigResponse,
    AlertResponse, AlertListResponse,
    # AI
    LLMConfigCreate, LLMConfigUpdate, LLMConfigResponse,
    AIReportRequest, AIReportResponse,
    ExecutiveMetrics,
    # Risk
    RiskFactorItem, RiskFactorSimple,
    PropagationNode,
    AssetRiskProfileResponse,
    RiskOverviewItem,
    RiskHotspotEntry, RiskHotspotItem, RiskHotspotResponse,
    AccountRiskScoreResponse,
    # Compliance
    ComplianceFrameworkResponse,
    ComplianceEvidenceItem, ComplianceCheckResultItem,
    ComplianceCheckResponse,
    ComplianceRunResponse,
    ComplianceFrameworkDashboard, ComplianceDashboardResponse,
    ComplianceResultResponse,
    # Identities
    IdentityAccountItem,
    HumanIdentityResponse, HumanIdentitySummary,
    IdentityLinkRequest, IdentitySuggestion,
    # Lifecycle
    LifecycleConfigResponse, LifecycleConfigUpdate,
    LifecycleStatusItem, LifecycleDashboard,
    # PAM
    PAMIntegrationCreate, PAMIntegrationUpdate, PAMIntegrationResponse,
    PAMSyncedAccountItem, PAMComparisonItem,
    # Review
    ReviewScheduleCreate, ReviewScheduleUpdate, ReviewScheduleResponse,
    ReviewReportResponse,
    # KB
    KBEntryCreate, KBEntryUpdate, KBEntryResponse,
    # Threat
    ThreatSignalItem, ThreatLayerSignals,
    ThreatGraphNode, ThreatGraphEdge, ThreatGraphData,
    IdentityThreatAnalysisResponse, IdentityThreatAnalysisListItem,
    ThreatAccountSignalResponse,
    AnalyzeRequest, AnalyzeResponse,
    # NHI
    NHITypeLiteral, NHILevelLiteral,
    NHIIdentityResponse, NHIInventoryResponse,
    NHIAlertResponse, NHIDashboardResponse, NHIPolicyResponse,
)
