"""Auth-related Pydantic schemas."""
import re
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, field_validator

from backend.models._enums import UserRole
from backend.schemas._shared import _check_password_strength


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class RefreshRequest(BaseModel):
    refresh_token: str


class RefreshResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class UserResponse(BaseModel):
    id: int
    username: str
    role: UserRole
    email: Optional[str]
    is_active: bool
    is_password_changed: bool
    created_at: datetime

    model_config = {"from_attributes": True, "extra": "forbid"}


class UserCreate(BaseModel):
    username: str = Field(..., min_length=2, max_length=64)
    password: str = Field(..., min_length=8)
    role: UserRole = UserRole.operator
    email: Optional[str] = None

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        _check_password_strength(v)
        return v


class UserUpdate(BaseModel):
    role: Optional[UserRole] = None
    email: Optional[str] = None
    is_active: Optional[bool] = None
    password: Optional[str] = Field(None, min_length=8)

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if v is None:
            return v
        _check_password_strength(v)
        return v


class PasswordChange(BaseModel):
    old_password: str
    new_password: str = Field(..., min_length=8)

    @field_validator("new_password")
    @classmethod
    def new_password_strength(cls, v: str) -> str:
        _check_password_strength(v, field_name="新密码")
        return v
