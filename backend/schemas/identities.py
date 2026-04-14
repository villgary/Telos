"""Identity fusion Pydantic schemas."""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class IdentityAccountItem(BaseModel):
    id: int
    snapshot_id: int
    asset_id: int
    asset_code: str
    ip: str
    hostname: Optional[str] = Field(None, max_length=256)
    username: str
    uid_sid: str
    is_admin: bool
    account_status: Optional[str]
    last_login: Optional[datetime]
    match_type: str
    match_confidence: int

    model_config = {"from_attributes": True, "extra": "forbid"}


class HumanIdentityResponse(BaseModel):
    id: int
    display_name: Optional[str] = Field(None, max_length=256)
    email: Optional[str] = Field(None, max_length=128)
    confidence: int
    source: str
    account_count: int
    admin_count: int
    asset_count: int
    max_risk_score: int
    latest_login: Optional[datetime]
    accounts: list[IdentityAccountItem]

    model_config = {"from_attributes": True, "extra": "forbid"}


class HumanIdentitySummary(BaseModel):
    id: int
    display_name: Optional[str] = Field(None, max_length=256)
    confidence: int
    source: str
    account_count: int
    admin_count: int
    asset_count: int
    max_risk_score: int
    latest_login: Optional[datetime]

    model_config = {"from_attributes": True, "extra": "forbid"}


class IdentityLinkRequest(BaseModel):
    identity_id: int
    snapshot_id: int
    match_type: str = "manual"
    match_confidence: int = 100


class IdentitySuggestion(BaseModel):
    snapshot_id: int
    asset_code: str
    ip: str
    username: str
    uid_sid: str
    is_admin: bool
    match_reason: str
    candidate_identities: list[int]
