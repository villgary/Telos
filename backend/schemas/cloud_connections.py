"""Pydantic schemas for the cloud connection management API."""
from datetime import datetime
from typing import Optional, List, Literal, Dict, Any
from pydantic import BaseModel, Field


CloudProviderLiteral = Literal["anthropic", "openai"]
CloudSyncStatusLiteral = Literal["success", "partial", "failed", "running"]
CloudAuditActionLiteral = Literal[
    "created", "renamed", "rotated", "deleted", "sync_started", "sync_finished",
]


class CloudConnectionCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=64)
    provider: CloudProviderLiteral
    api_key: str = Field(..., min_length=1, max_length=512)


class CloudConnectionUpdate(BaseModel):
    """PATCH — name only. To replace the key, call /rotate."""
    name: str = Field(..., min_length=1, max_length=64)


class CloudConnectionRotate(BaseModel):
    api_key: str = Field(..., min_length=1, max_length=512)


class CloudConnectionResponse(BaseModel):
    id: int
    name: str
    provider: CloudProviderLiteral
    api_key_fingerprint: str
    last_sync_at: Optional[datetime] = None
    last_sync_started_at: Optional[datetime] = None
    last_sync_status: Optional[CloudSyncStatusLiteral] = None
    last_sync_error: Optional[str] = None
    created_by_user_id: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CloudConnectionListResponse(BaseModel):
    total: int
    connections: List[CloudConnectionResponse]


class CloudConnectionSyncResponse(BaseModel):
    connection_id: int
    status: CloudSyncStatusLiteral
    agents_discovered: int
    agents_updated: int
    error: Optional[str] = None


class CloudConnectionAuditEntry(BaseModel):
    id: int
    connection_id: Optional[int] = None
    actor_user_id: Optional[int] = None
    action: CloudAuditActionLiteral
    status: Optional[str] = None
    before: Optional[Dict[str, Any]] = None
    after: Optional[Dict[str, Any]] = None
    note: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class CloudConnectionAuditListResponse(BaseModel):
    total: int
    entries: List[CloudConnectionAuditEntry]
