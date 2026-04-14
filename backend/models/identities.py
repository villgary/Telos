"""Identity, lifecycle, and PAM-related ORM models."""
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, Enum,
    ForeignKey, Text, JSON, UniqueConstraint,
)
from sqlalchemy.orm import relationship

from backend.models._db import Base
from backend.models._enums import LifecycleStatus


class HumanIdentity(Base):
    __tablename__ = "human_identities"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    display_name = Column(String(128), nullable=True)
    email = Column(String(256), nullable=True)
    primary_asset_id = Column(Integer, ForeignKey("assets.id"), nullable=True)
    confidence = Column(Integer, default=0)
    source = Column(String(16), default="auto")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    accounts = relationship("IdentityAccount", back_populates="identity", cascade="all, delete-orphan")
    primary_asset = relationship("Asset")


class IdentityAccount(Base):
    __tablename__ = "identity_accounts"
    __table_args__ = (UniqueConstraint("identity_id", "snapshot_id", name="uq_identity_snapshot"),)

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    identity_id = Column(Integer, ForeignKey("human_identities.id"), nullable=False)
    snapshot_id = Column(Integer, ForeignKey("account_snapshots.id"), nullable=False)
    asset_id = Column(Integer, ForeignKey("assets.id"), nullable=False)
    match_type = Column(String(16), nullable=False)
    match_confidence = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    identity = relationship("HumanIdentity", back_populates="accounts")
    snapshot = relationship("AccountSnapshot")
    asset = relationship("Asset")


class AccountLifecycleConfig(Base):
    __tablename__ = "account_lifecycle_configs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    category_slug = Column(String(32), unique=True, nullable=False, default="global")
    active_days = Column(Integer, nullable=False, default=30)
    dormant_days = Column(Integer, nullable=False, default=90)
    auto_alert = Column(Boolean, nullable=False, default=True)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class AccountLifecycleStatus(Base):
    __tablename__ = "account_lifecycle_statuses"

    id = Column(Integer, primary_key=True, autoincrement=True)
    snapshot_id = Column(Integer, ForeignKey("account_snapshots.id"), unique=True, nullable=False)
    lifecycle_status = Column(String(16), nullable=False, default="unknown")
    previous_status = Column(String(16), nullable=True)
    changed_at = Column(DateTime, nullable=True)
    alert_sent = Column(Boolean, nullable=False, default=False)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    snapshot = relationship("AccountSnapshot")


class PAMIntegration(Base):
    __tablename__ = "pam_integrations"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(128), nullable=False)
    provider = Column(String(32), nullable=False)
    config = Column(JSON, nullable=True)
    status = Column(String(16), default="active")
    last_sync_at = Column(DateTime, nullable=True)
    last_error = Column(Text, nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    created_user = relationship("User")
    synced_accounts = relationship("PAMSyncedAccount", back_populates="integration", cascade="all, delete-orphan")


class PAMSyncedAccount(Base):
    __tablename__ = "pam_synced_accounts"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    integration_id = Column(Integer, ForeignKey("pam_integrations.id"), nullable=False)
    asset_id = Column(Integer, ForeignKey("assets.id"), nullable=True)
    account_name = Column(String(128), nullable=False)
    account_type = Column(String(32), nullable=False)
    pam_status = Column(String(16), nullable=False)
    last_used = Column(DateTime, nullable=True)
    matched_snapshot_id = Column(Integer, ForeignKey("account_snapshots.id"), nullable=True)
    match_confidence = Column(Integer, default=0)
    synced_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    integration = relationship("PAMIntegration", back_populates="synced_accounts")
    asset = relationship("Asset")
    snapshot = relationship("AccountSnapshot")
