"""Risk assessment Pydantic schemas."""
from __future__ import annotations
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field

from backend.schemas.assets import AssetSummary


class RiskFactorItem(BaseModel):
    factor: str
    score: int
    description: Optional[str] = None
    target: Optional[str] = None


class RiskFactorSimple(BaseModel):
    factor: str
    score: int


class PropagationNode(BaseModel):
    asset_code: str
    ip: str
    hostname: Optional[str] = Field(None, max_length=256)
    risk_score: int
    relation: Optional[str] = None
    is_entry_point: bool = False


class AssetRiskProfileResponse(BaseModel):
    asset: "AssetSummary"
    risk_score: int
    risk_level: str
    risk_factors: list[RiskFactorItem]
    affected_children_count: int
    propagation_path: list[PropagationNode]
    computed_at: datetime

    model_config = {"from_attributes": True, "extra": "forbid"}


class RiskOverviewItem(BaseModel):
    asset_id: int
    asset_code: str
    ip: str
    hostname: Optional[str] = Field(None, max_length=256)
    risk_score: int
    risk_level: str
    affected_children_count: int

    model_config = {"from_attributes": True, "extra": "forbid"}


class RiskHotspotEntry(BaseModel):
    asset_code: str
    ip: str
    hostname: Optional[str] = Field(None, max_length=256)
    risk_score: int


class RiskHotspotItem(BaseModel):
    entry_asset: RiskHotspotEntry
    root_asset: dict
    max_risk_score: int
    path: list[str]
    risk_description: str
    chain_length: int
    nodes: list[PropagationNode]


class RiskHotspotResponse(BaseModel):
    hotspots: list[RiskHotspotItem]


class AccountRiskScoreResponse(BaseModel):
    id: int
    snapshot_id: int
    risk_score: int
    risk_level: str
    risk_factors: list[RiskFactorSimple]
    identity_id: Optional[int] = None
    cross_asset_count: int = 0
    computed_at: datetime
    username: Optional[str] = None
    asset_code: Optional[str] = None
    asset_ip: Optional[str] = None
    is_admin: bool = False
    last_login: Optional[datetime] = None
    owner_identity_id: Optional[int] = None
    owner_email: Optional[str] = Field(None, max_length=128)
    owner_name: Optional[str] = Field(None, max_length=128)

    model_config = {"from_attributes": True, "extra": "forbid"}
