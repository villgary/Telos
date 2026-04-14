"""AI/LLM Pydantic schemas."""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field

from backend.models._enums import LLMProvider


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
    api_key_set: bool
    base_url: Optional[str]
    model: str
    enabled: bool
    created_at: datetime

    model_config = {"from_attributes": True, "extra": "forbid"}


class AIReportRequest(BaseModel):
    asset_id: Optional[int] = None
    scan_job_id: Optional[int] = None
    report_type: str = Field("threat_analysis")
    lang: Optional[str] = Field("zh-CN")


class AIReportResponse(BaseModel):
    success: bool
    report: Optional[str]
    error: Optional[str] = None


class ExecutiveMetrics(BaseModel):
    risk_score: int = Field(ge=0, le=100)
    risk_level: str
    total_assets: int
    total_accounts: int
    high_risk_accounts: int
    dormant_accounts: int
    unlogin_admin_accounts: int
    compliance_ready: float = Field(ge=0, le=100)
    trends: dict
    ai_summary: Optional[str] = None
