"""Compliance Pydantic schemas."""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class ComplianceFrameworkResponse(BaseModel):
    id: int
    slug: str
    name: str
    description: Optional[str] = Field(None, max_length=512)
    version: str
    enabled: bool
    created_at: datetime

    model_config = {"from_attributes": True, "extra": "forbid"}


class ComplianceEvidenceItem(BaseModel):
    asset_code: str
    ip: str
    hostname: Optional[str] = Field(None, max_length=256)
    username: Optional[str] = Field(None, max_length=128)
    description: str
    description_key: Optional[str] = None


class ComplianceCheckResultItem(BaseModel):
    check_key: str
    title: str
    description: Optional[str] = Field(None, max_length=1024)
    title_key: Optional[str] = None
    description_key: Optional[str] = None
    severity: str
    status: str
    failed_count: int
    passed_count: int
    evidence: list[ComplianceEvidenceItem] = []


class ComplianceCheckResponse(BaseModel):
    id: int
    framework_id: int
    check_key: str
    title: str
    description: Optional[str] = Field(None, max_length=1024)
    severity: str
    applies_to: str
    enabled: bool
    latest_result: Optional[ComplianceCheckResultItem] = None

    model_config = {"from_attributes": True, "extra": "forbid"}


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
    error_message: Optional[str] = Field(None, max_length=1024)
    started_at: datetime
    finished_at: Optional[datetime]
    created_by: Optional[int]

    model_config = {"from_attributes": True, "extra": "forbid"}


class ComplianceFrameworkDashboard(BaseModel):
    slug: str
    name: str
    description: Optional[str] = Field(None, max_length=512)
    name_key: Optional[str] = None
    description_key: Optional[str] = None
    score: int
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
    hostname: Optional[str] = Field(None, max_length=256)
    status: str
    evidence: Optional[list[dict]]
    evaluated_at: datetime

    model_config = {"from_attributes": True, "extra": "forbid"}
