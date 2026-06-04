"""AI Agent ORM models — first-class identity peer to NHI."""
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, DateTime, ForeignKey, Text, JSON, Index,
)
from sqlalchemy.orm import relationship

from backend.models._db import Base


class AIAgent(Base):
    __tablename__ = "ai_agents"
    __table_args__ = (
        Index(
            "ix_ai_agents_dedup",
            "framework", "agent_name", "owner_team", "asset_id",
            unique=True,
        ),
        Index("ix_ai_agents_connection", "connection_id"),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    agent_name = Column(String(128), nullable=False, index=True)
    framework = Column(String(32), nullable=False, default="unknown")
    model = Column(String(64), nullable=True)
    owner_team = Column(String(64), nullable=True, index=True)
    owner_user = Column(String(64), nullable=True)
    api_key_fingerprint = Column(String(16), nullable=True)
    api_key_location = Column(String(256), nullable=True)
    capabilities = Column(JSON, default=dict)  # {filesystem, network, code_exec, tool_count}
    last_invocation_at = Column(DateTime, nullable=True)
    last_seen_at = Column(DateTime, nullable=False)
    discovered_at = Column(DateTime, nullable=False)
    discovery_source = Column(String(16), nullable=False, default="ssh_scan")
    asset_id = Column(Integer, ForeignKey("assets.id"), nullable=True, index=True)
    nhi_identity_id = Column(Integer, ForeignKey("nhi_identities.id"), nullable=True, index=True)
    risk_level = Column(String(16), nullable=False, default="low")
    risk_score = Column(Integer, nullable=False, default=0)
    risk_signals = Column(JSON, default=list)
    status = Column(String(16), nullable=False, default="active")
    notes = Column(Text, nullable=True)
    connection_id = Column(
        Integer,
        ForeignKey("cloud_connections.id", ondelete="SET NULL"),
        nullable=True,
    )

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    asset = relationship("Asset")
    nhi = relationship("NHIIdentity")
    connection = relationship("CloudConnection", back_populates="agents")
