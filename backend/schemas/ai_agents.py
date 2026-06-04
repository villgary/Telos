"""AI Agent Pydantic schemas."""
from datetime import datetime
from typing import Optional, List, Literal, Dict, Any
from pydantic import BaseModel, Field

AIAgentFrameworkLiteral = Literal[
    "langchain", "autogen", "crewai", "claude_code",
    "openai_assistant", "llamaindex", "custom", "unknown",
]
AIAgentStatusLiteral = Literal["active", "dormant", "deprecated", "blocked"]
AIAgentLevelLiteral = Literal["low", "medium", "high", "critical"]
AIAgentDiscoverySourceLiteral = Literal["ssh_scan", "api_discovery", "manual"]


class AIAgentCapabilities(BaseModel):
    filesystem: bool = False
    network: bool = False
    code_exec: bool = False
    tool_count: int = 0


class AIAgentBase(BaseModel):
    agent_name: str
    framework: AIAgentFrameworkLiteral = "unknown"
    model: Optional[str] = None
    owner_team: Optional[str] = None
    owner_user: Optional[str] = None


class AIAgentResponse(AIAgentBase):
    id: int
    api_key_fingerprint: Optional[str] = None
    api_key_location: Optional[str] = None
    capabilities: AIAgentCapabilities = Field(default_factory=AIAgentCapabilities)
    last_invocation_at: Optional[datetime] = None
    last_seen_at: datetime
    discovered_at: datetime
    discovery_source: AIAgentDiscoverySourceLiteral = "ssh_scan"
    asset_id: Optional[int] = None
    nhi_identity_id: Optional[int] = None
    risk_level: AIAgentLevelLiteral = "low"
    risk_score: int = 0
    risk_signals: List[Dict[str, Any]] = Field(default_factory=list)
    status: AIAgentStatusLiteral = "active"
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AIAgentDetailResponse(AIAgentResponse):
    """Same shape as AIAgentResponse; alias for future-proofing."""
    pass


class AIAgentStatsResponse(BaseModel):
    total: int
    active: int
    critical_risk: int
    no_owner: int
    by_framework: Dict[str, int]
    by_risk_level: Dict[str, int]


class AIAgentScanRequest(BaseModel):
    asset_id: Optional[int] = None  # None = all assets
    force: bool = False  # re-scan even if recently scanned


class AIAgentScanResponse(BaseModel):
    scanned_assets: int
    agents_discovered: int
    agents_updated: int
    alerts_emitted: int
    errors: List[str] = Field(default_factory=list)


class AIAgentClaimRequest(BaseModel):
    """Sets owner_user to the current authenticated user."""
    pass


class AIAgentListResponse(BaseModel):
    total: int
    agents: List[AIAgentResponse]
