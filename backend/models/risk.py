"""Risk and UEBA ORM models."""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON, Text
from sqlalchemy.orm import relationship

from backend.models._db import Base


class AssetRiskProfile(Base):
    __tablename__ = "asset_risk_profiles"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    asset_id = Column(Integer, ForeignKey("assets.id"), unique=True, nullable=False)
    risk_score = Column(Integer, default=0)
    risk_level = Column(String(16), default="low")
    risk_factors = Column(JSON, default=list)
    affected_children = Column(Integer, default=0)
    propagation_path = Column(JSON, nullable=True)
    computed_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    asset = relationship("Asset", backref="risk_profile")


class AccountRiskScore(Base):
    __tablename__ = "account_risk_scores"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    snapshot_id = Column(Integer, ForeignKey("account_snapshots.id"), nullable=False, unique=True)
    risk_score = Column(Integer, default=0, nullable=False)
    risk_level = Column(String(16), nullable=False, default="low")
    risk_factors = Column(JSON, default=list, nullable=False)
    identity_id = Column(Integer, ForeignKey("human_identities.id"), nullable=True)
    cross_asset_count = Column(Integer, default=0)
    computed_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    snapshot = relationship("AccountSnapshot")
    identity = relationship("HumanIdentity")


class AccountBehaviorEvent(Base):
    __tablename__ = "account_behavior_events"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    event_type = Column(String(32), nullable=False, index=True)
    severity = Column(String(16), nullable=False, default="medium")
    username = Column(String(128), nullable=False, index=True)
    asset_code = Column(String(32), nullable=True)
    asset_ip = Column(String(45), nullable=True)
    description = Column(Text, nullable=True)
    description_key = Column(String(64), nullable=True)
    description_params = Column(JSON, nullable=True)
    snapshot_id = Column(Integer, ForeignKey("account_snapshots.id"), nullable=True)
    detected_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    snapshot = relationship("AccountSnapshot")
