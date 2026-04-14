"""PAM integration Pydantic schemas."""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class PAMIntegrationCreate(BaseModel):
    name: str = Field(..., max_length=128)
    provider: str = Field(..., max_length=32)
    config: Optional[dict] = None


class PAMIntegrationUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=128)
    config: Optional[dict] = None
    status: Optional[str] = None


class PAMIntegrationResponse(BaseModel):
    id: int
    name: str
    provider: str
    status: str
    last_sync_at: Optional[datetime]
    last_error: Optional[str]
    created_by: Optional[int]
    created_at: datetime
    account_count: int = 0

    model_config = {"from_attributes": True, "extra": "forbid"}


class PAMSyncedAccountItem(BaseModel):
    id: int
    integration_id: int
    account_name: str
    account_type: str
    pam_status: str
    last_used: Optional[datetime]
    matched_asset_code: Optional[str]
    matched_asset_ip: Optional[str]
    matched_username: Optional[str]
    is_admin: bool
    match_confidence: int
    comparison_result: str

    model_config = {"from_attributes": True, "extra": "forbid"}


class PAMComparisonItem(BaseModel):
    integration_name: str
    integration_id: int
    account_name: str
    account_type: str
    pam_status: str
    last_used: Optional[datetime]
    asset_code: Optional[str]
    asset_ip: Optional[str]
    is_admin: bool
    result: str
    result_label: str
