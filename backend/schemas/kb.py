"""Knowledge base Pydantic schemas."""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class KBEntryCreate(BaseModel):
    entry_type: str
    title: str
    title_en: Optional[str] = Field(None, max_length=256)
    description: Optional[str] = Field(None, max_length=2048)
    description_en: Optional[str] = Field(None, max_length=2048)
    extra_data: dict = {}

    model_config = {"from_attributes": True, "extra": "forbid"}


class KBEntryUpdate(BaseModel):
    title: Optional[str] = None
    title_en: Optional[str] = None
    description: Optional[str] = None
    description_en: Optional[str] = None
    extra_data: Optional[dict] = None
    enabled: Optional[bool] = None


class KBEntryResponse(BaseModel):
    id: int
    entry_type: str
    title: str
    title_en: Optional[str] = None
    description: Optional[str] = None
    description_en: Optional[str] = None
    extra_data: dict = {}
    enabled: bool = True
    created_by: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True, "extra": "forbid"}
