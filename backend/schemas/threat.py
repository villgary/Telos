"""Identity threat analysis Pydantic schemas."""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


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
    hostname: Optional[str] = Field(None, max_length=256)
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

    model_config = {"from_attributes": True, "extra": "forbid", "protected_namespaces": ()}


class IdentityThreatAnalysisListItem(BaseModel):
    id: int
    analysis_type: str
    scope: str
    scope_id: Optional[int]
    scope_label: Optional[str] = None
    overall_score: int
    overall_level: str
    analyzed_count: int
    duration_ms: Optional[int]
    created_by: Optional[int]
    created_at: datetime

    model_config = {"from_attributes": True, "extra": "forbid"}


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

    model_config = {"from_attributes": True, "extra": "forbid"}


class AnalyzeRequest(BaseModel):
    scope: str = "global"
    scope_id: Optional[int] = None
    lang: str = "zh"


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

    model_config = {"from_attributes": True, "extra": "forbid"}
