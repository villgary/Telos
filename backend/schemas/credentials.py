"""Credential Pydantic schemas."""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field

from backend.models._enums import AuthType


class CredentialBase(BaseModel):
    name: str = Field(..., max_length=128)
    auth_type: AuthType
    username: str = Field(..., max_length=128)
    password: Optional[str] = None
    private_key: Optional[str] = None
    passphrase: Optional[str] = None


class CredentialCreate(CredentialBase):
    pass


class CredentialUpdate(BaseModel):
    name: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    private_key: Optional[str] = None
    passphrase: Optional[str] = None


class CredentialResponse(BaseModel):
    id: int
    name: str
    auth_type: AuthType
    username: str
    has_password: bool
    has_private_key: bool
    created_by: Optional[int]
    created_at: datetime

    model_config = {"from_attributes": True, "extra": "forbid"}

    @classmethod
    def from_orm_full(cls, cred):
        return cls(
            id=cred.id,
            name=cred.name,
            auth_type=cred.auth_type,
            username=cred.username,
            has_password=cred.password_enc is not None,
            has_private_key=cred.private_key_enc is not None,
            created_by=cred.created_by,
            created_at=cred.created_at,
        )
