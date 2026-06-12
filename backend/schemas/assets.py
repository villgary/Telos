"""Asset-related Pydantic schemas."""
import ipaddress
from datetime import datetime
from typing import Optional, List, Any, TYPE_CHECKING
from pydantic import BaseModel, Field, field_validator

from backend.models._enums import AssetCategory, AssetRelationType, AssetStatus, DirectoryType, CloudProviderType, SubTypeKind

if TYPE_CHECKING:
    from backend.schemas.assets import AssetSummary


class AssetCategoryDefCreate(BaseModel):
    slug: str = Field(..., max_length=32)
    name: str = Field(..., max_length=64)
    description: Optional[str] = Field(None, max_length=256)
    icon: Optional[str] = Field(None, max_length=32)
    sub_type_kind: str = Field("none", max_length=64)
    parent_id: Optional[int] = None


class AssetCategoryDefUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=64)
    description: Optional[str] = None
    icon: Optional[str] = Field(None, max_length=32)
    sub_type_kind: Optional[str] = Field(None, max_length=64)
    parent_id: Optional[int] = None


class AssetCategoryDefResponse(BaseModel):
    id: int
    slug: str
    name: str
    name_i18n_key: Optional[str] = None
    description: Optional[str]
    icon: Optional[str]
    sub_type_kind: str
    parent_id: Optional[int]

    model_config = {"from_attributes": True, "extra": "forbid"}


class AssetCategoryTreeResponse(BaseModel):
    id: int
    slug: str
    name: str
    name_i18n_key: Optional[str] = None
    sub_type_kind: str
    children: List["AssetCategoryTreeResponse"] = []

    model_config = {"from_attributes": True, "extra": "forbid"}


class SubTypeDefCreate(BaseModel):
    slug: str = Field(..., max_length=32)
    name: str = Field(..., max_length=64)
    description: Optional[str] = Field(None, max_length=256)
    sub_type_kind: SubTypeKind = Field(...)
    icon: Optional[str] = Field(None, max_length=32)
    color: Optional[str] = Field(None, max_length=8)
    sort_order: int = 0


class SubTypeDefUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=64)
    description: Optional[str] = None
    icon: Optional[str] = None
    color: Optional[str] = Field(None, max_length=8)
    sort_order: Optional[int] = None


class SubTypeDefResponse(BaseModel):
    id: int
    slug: str
    name: str
    description: Optional[str]
    sub_type_kind: str
    icon: Optional[str]
    color: Optional[str]
    sort_order: int
    created_at: datetime

    model_config = {"from_attributes": True, "extra": "forbid"}


class AssetGroupCreate(BaseModel):
    name: str = Field(..., max_length=128)
    description: Optional[str] = Field(None, max_length=512)
    color: str = Field("#1890ff", max_length=8)


class AssetGroupUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=128)
    description: Optional[str] = None
    color: Optional[str] = Field(None, max_length=8)


class AssetGroupResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    color: str
    created_by: Optional[int]
    created_at: datetime

    model_config = {"from_attributes": True, "extra": "forbid"}


class AssetBase(BaseModel):
    ip: str = Field(..., max_length=45)
    hostname: Optional[str] = Field(None, max_length=256)
    asset_category: Optional[AssetCategory] = None
    asset_category_def_id: Optional[int] = None
    category_slug: Optional[str] = Field(None, max_length=64)
    os_type: Optional[str] = Field(None, max_length=64)
    db_type: Optional[str] = Field(None, max_length=64)
    network_type: Optional[str] = Field(None, max_length=64)
    iot_type: Optional[str] = Field(None, max_length=64)
    directory_type: Optional[DirectoryType] = None
    cloud_provider_type: Optional[CloudProviderType] = None
    cloud_region: Optional[str] = Field(None, max_length=32)
    base_dn: Optional[str] = Field(None, max_length=256)
    use_ssl: bool = True
    group_id: Optional[int] = None
    port: int = Field(22, ge=1, le=65535, description="TCP/UDP port 1-65535")
    credential_id: int

    @field_validator("ip")
    @classmethod
    def _validate_ip(cls, v: str) -> str:
        """Reject malformed IPs early. Accepts IPv4 and IPv6."""
        if not v or not v.strip():
            raise ValueError("IP address is required")
        try:
            ipaddress.ip_address(v.strip())
        except ValueError:
            raise ValueError(f"'{v}' is not a valid IPv4 or IPv6 address")
        return v.strip()

    @field_validator("hostname")
    @classmethod
    def _validate_hostname(cls, v: Optional[str]) -> Optional[str]:
        """Reject obvious garbage: spaces, slashes, control chars. The
        full DNS spec is more permissive, but for a single host label
        this is enough to catch typos like '192.168 1.8'."""
        if v is None:
            return v
        v = v.strip()
        if not v:
            return None
        if any(c in v for c in " \t\r\n/"):
            raise ValueError(
                f"hostname '{v}' contains spaces or slashes; "
                "leave blank or use a single label"
            )
        return v


class AssetCreate(AssetBase):
    pass


class AssetUpdate(BaseModel):
    ip: Optional[str] = None
    hostname: Optional[str] = None
    asset_category: Optional[AssetCategory] = None
    asset_category_def_id: Optional[int] = None
    category_slug: Optional[str] = Field(None, max_length=64)
    os_type: Optional[str] = Field(None, max_length=64)
    db_type: Optional[str] = Field(None, max_length=64)
    network_type: Optional[str] = Field(None, max_length=64)
    iot_type: Optional[str] = Field(None, max_length=64)
    directory_type: Optional[DirectoryType] = None
    cloud_provider_type: Optional[CloudProviderType] = None
    cloud_region: Optional[str] = Field(None, max_length=32)
    base_dn: Optional[str] = Field(None, max_length=256)
    use_ssl: Optional[bool] = None
    group_id: Optional[int] = None
    port: Optional[int] = None
    credential_id: Optional[int] = None


class AssetResponse(BaseModel):
    id: int
    asset_code: str
    ip: str
    hostname: Optional[str] = Field(None, max_length=256)
    asset_category: AssetCategory
    asset_category_def_id: Optional[int]
    category_slug: Optional[str] = Field(None, max_length=64)
    os_type: Optional[str]
    db_type: Optional[str]
    network_type: Optional[str]
    iot_type: Optional[str]
    directory_type: Optional[DirectoryType]
    cloud_provider_type: Optional[CloudProviderType]
    cloud_region: Optional[str]
    base_dn: Optional[str]
    use_ssl: bool
    group_id: Optional[int]
    port: int
    status: AssetStatus
    last_scan_at: Optional[datetime]
    last_scan_job_id: Optional[int]
    credential_id: int
    created_by: Optional[int]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True, "extra": "forbid"}


class AssetRelationshipCreate(BaseModel):
    parent_id: int
    child_id: int
    relation_type: AssetRelationType
    description: Optional[str] = Field(None, max_length=256)


class AssetRelationshipUpdate(BaseModel):
    relation_type: Optional[AssetRelationType] = None
    description: Optional[str] = Field(None, max_length=256)


class AccountSummaryItem(BaseModel):
    id: int
    username: str
    is_admin: bool
    account_status: Optional[str]
    last_login: Optional[datetime]

    model_config = {"from_attributes": True, "extra": "forbid"}


class AssetSummary(BaseModel):
    id: int
    asset_code: str
    ip: str
    hostname: Optional[str] = Field(None, max_length=256)
    asset_category: AssetCategory
    account_count: int = 0
    admin_count: int = 0
    latest_accounts: list = []

    model_config = {"from_attributes": True, "extra": "forbid"}


class AssetRelationshipResponse(BaseModel):
    id: int
    parent_id: int
    child_id: int
    relation_type: AssetRelationType
    description: Optional[str]
    created_by: Optional[int]
    created_at: datetime
    parent: AssetSummary
    child: AssetSummary

    model_config = {"from_attributes": True, "extra": "forbid"}


class HierarchyNode(BaseModel):
    asset: AssetSummary
    relation_type: Optional[str] = None
    children: list = []


HierarchyNode.model_rebuild()
