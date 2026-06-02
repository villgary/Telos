"""Non-human identity (NHI) ORM models."""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, JSON
from sqlalchemy.orm import relationship

from backend.models._db import Base


class NHIIdentity(Base):
    __tablename__ = "nhi_identities"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    snapshot_id = Column(Integer, ForeignKey("account_snapshots.id"), nullable=True)
    asset_id = Column(Integer, ForeignKey("assets.id"), nullable=True)
    nhi_type = Column(String(32), nullable=False, default="unknown")
    nhi_level = Column(String(16), nullable=False, default="low")
    username = Column(String(128), nullable=False, index=True)
    uid_sid = Column(String(256), nullable=True)
    hostname = Column(String(256), nullable=True)
    ip_address = Column(String(64), nullable=True)
    is_admin = Column(Boolean, default=False)
    credential_types = Column(JSON, default=list)
    has_nopasswd_sudo = Column(Boolean, default=False)
    risk_score = Column(Integer, default=0)
    risk_signals = Column(JSON, default=list)
    owner_identity_id = Column(Integer, ForeignKey("human_identities.id"), nullable=True)
    owner_email = Column(String(256), nullable=True)
    owner_name = Column(String(128), nullable=True)
    first_seen_at = Column(DateTime, nullable=True)
    last_seen_at = Column(DateTime, nullable=True)
    last_rotated_at = Column(DateTime, nullable=True)
    rotation_due_days = Column(Integer, nullable=True)
    is_active = Column(Boolean, default=True)
    is_monitored = Column(Boolean, default=False)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    snapshot = relationship("AccountSnapshot")
    asset = relationship("Asset")
    owner = relationship("HumanIdentity")


class NHIAlert(Base):
    __tablename__ = "nhi_alerts"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    nhi_id = Column(Integer, ForeignKey("nhi_identities.id"), nullable=True)
    # cluster_key is String(192) to fit worst-case f"{nhi_type}:{username}" = 32+1+128 chars
    cluster_key = Column(String(192), nullable=True, index=True)
    nhi_username = Column(String(128), nullable=True)
    nhi_type = Column(String(32), nullable=True)
    asset_count = Column(Integer, nullable=True)
    alert_type = Column(String(64), nullable=False)
    level = Column(String(16), nullable=False)
    title = Column(String(256), nullable=False)
    message = Column(Text, nullable=False)
    title_key = Column(String(64), nullable=True)
    title_params = Column(JSON, nullable=True)
    message_key = Column(String(64), nullable=True)
    message_params = Column(JSON, nullable=True)
    is_read = Column(Boolean, default=False)
    status = Column(String(16), default="new")
    resolved_at = Column(DateTime, nullable=True)
    resolved_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    nhi = relationship("NHIIdentity")
    resolver = relationship("User")


class NHIPolicy(Base):
    __tablename__ = "nhi_policies"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(128), nullable=False, unique=True)
    description = Column(Text, nullable=True)
    nhi_type = Column(String(32), nullable=True)
    severity_filter = Column(String(16), nullable=True)
    rotation_days = Column(Integer, nullable=True)
    alert_threshold_days = Column(Integer, nullable=True)
    require_owner = Column(Boolean, default=True)
    require_monitoring = Column(Boolean, default=False)
    enabled_alert_types = Column(JSON, default=lambda: [
        "privilege_escalation", "nopasswd_sudo", "credential_leak", "cross_asset_spread",
    ])
    cross_asset_threshold = Column(Integer, default=3)
    cross_asset_window_days = Column(Integer, default=7)
    enabled = Column(Boolean, default=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
