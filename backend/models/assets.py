"""Asset-related ORM models."""
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, Enum,
    ForeignKey, Text, JSON, UniqueConstraint,
)
from sqlalchemy.orm import relationship, backref

from backend.models._db import Base
from backend.models._enums import (
    AssetCategory, OSType, DBType, NetworkVendor, IoTType,
    AuthType, AssetStatus, AssetRelationType,
)


class AssetCategoryDef(Base):
    __tablename__ = "asset_category_defs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    slug = Column(String(32), unique=True, nullable=False, index=True)
    name = Column(String(64), nullable=False)
    description = Column(String(256), nullable=True)
    icon = Column(String(32), nullable=True)
    sub_type_kind = Column(String(64), nullable=False, default="none")
    parent_id = Column(Integer, ForeignKey("asset_category_defs.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    assets = relationship("Asset", back_populates="category_def")
    parent = relationship("AssetCategoryDef", remote_side=[id], backref="children")


class Credential(Base):
    __tablename__ = "credentials"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(128), unique=True, nullable=False)
    auth_type = Column(Enum(AuthType), nullable=False)
    username = Column(String(128), nullable=False)
    password_enc = Column(Text, nullable=True)
    private_key_enc = Column(Text, nullable=True)
    passphrase_enc = Column(Text, nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    creator = relationship("User", back_populates="created_credentials", foreign_keys=[created_by])
    assets = relationship("Asset", back_populates="credential")


class AssetGroup(Base):
    __tablename__ = "asset_groups"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(128), unique=True, nullable=False)
    description = Column(String(512), nullable=True)
    color = Column(String(8), default="#1890ff", nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    creator = relationship("User", foreign_keys=[created_by])
    assets = relationship("Asset", back_populates="asset_group")


class Asset(Base):
    __tablename__ = "assets"
    __table_args__ = (UniqueConstraint("ip", "port", name="uq_asset_ip_port"),)

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    asset_code = Column(String(12), unique=True, nullable=False)
    ip = Column(String(45), nullable=False, index=True)
    hostname = Column(String(255), nullable=True)
    asset_category = Column(Enum(AssetCategory), nullable=False, default=AssetCategory.server)
    os_type = Column(Enum(OSType), nullable=True)
    db_type = Column(Enum(DBType), nullable=True)
    network_type = Column(Enum(NetworkVendor), nullable=True)
    iot_type = Column(Enum(IoTType), nullable=True)
    group_id = Column(Integer, ForeignKey("asset_groups.id"), nullable=True)
    port = Column(Integer, default=22)
    asset_category_def_id = Column(Integer, ForeignKey("asset_category_defs.id"), nullable=True)
    category_slug = Column(String(64), nullable=True)
    status = Column(Enum(AssetStatus), default=AssetStatus.untested, nullable=False)
    last_scan_at = Column(DateTime, nullable=True)
    last_scan_job_id = Column(Integer, ForeignKey("scan_jobs.id"), nullable=True)
    credential_id = Column(Integer, ForeignKey("credentials.id"), nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    creator = relationship("User", back_populates="created_assets", foreign_keys=[created_by])
    credential = relationship("Credential", back_populates="assets")
    asset_group = relationship("AssetGroup", back_populates="assets")
    category_def = relationship("AssetCategoryDef", back_populates="assets")
    children = relationship(
        "AssetRelationship",
        foreign_keys="AssetRelationship.child_id",
        back_populates="parent",
        cascade="all, delete-orphan",
        viewonly=True,
    )
    parents = relationship(
        "AssetRelationship",
        foreign_keys="AssetRelationship.parent_id",
        back_populates="child",
        cascade="all, delete-orphan",
        viewonly=True,
    )
    scan_jobs = relationship(
        "ScanJob",
        backref=backref("asset", uselist=False),
        foreign_keys="ScanJob.asset_id",
        viewonly=True,
    )
    snapshots = relationship("AccountSnapshot", back_populates="asset")


class AssetRelationship(Base):
    __tablename__ = "asset_relationships"
    __table_args__ = (UniqueConstraint("parent_id", "child_id", name="uq_rel_parent_child"),)

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    parent_id = Column(Integer, ForeignKey("assets.id", ondelete="CASCADE"), nullable=False)
    child_id = Column(Integer, ForeignKey("assets.id", ondelete="CASCADE"), nullable=False)
    relation_type = Column(Enum(AssetRelationType), nullable=False)
    description = Column(String(256), nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    parent = relationship("Asset", foreign_keys=[parent_id], backref="child_relations")
    child = relationship("Asset", foreign_keys=[child_id], backref="parent_relations")
    creator = relationship("User", foreign_keys=[created_by])
