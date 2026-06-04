"""Cloud connection + audit-log ORM models — peer to NHI for provider-side AI Agent discovery."""
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, DateTime, ForeignKey, Text, JSON, UniqueConstraint, Index,
)
from sqlalchemy.orm import relationship

from backend.models._db import Base


class CloudConnection(Base):
    __tablename__ = "cloud_connections"
    __table_args__ = (
        UniqueConstraint("name", name="uq_cloud_connections_name"),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(64), nullable=False)
    provider = Column(String(16), nullable=False)  # anthropic|openai
    encrypted_api_key = Column(Text, nullable=False)  # base64(nonce||ct||tag) from backend.encryption
    api_key_fingerprint = Column(String(16), nullable=False)  # sha256[:16] hex of plaintext
    last_sync_at = Column(DateTime, nullable=True)
    last_sync_started_at = Column(DateTime, nullable=True)
    last_sync_status = Column(String(16), nullable=True)  # success|partial|failed|running
    last_sync_error = Column(String(256), nullable=True)
    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    created_by = relationship("User", foreign_keys=[created_by_user_id])
    agents = relationship("AIAgent", back_populates="connection", passive_deletes=True)


class CloudConnectionAuditLog(Base):
    __tablename__ = "cloud_connection_audit_log"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    connection_id = Column(
        Integer,
        ForeignKey("cloud_connections.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    actor_user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    action = Column(String(32), nullable=False)  # created|renamed|rotated|deleted|sync_started|sync_finished
    status = Column(String(16), nullable=True)  # success|partial|failed|auth_failed|rate_limited
    before = Column(JSON, nullable=True)  # name only — never the key
    after = Column(JSON, nullable=True)   # name only — never the key
    note = Column(String(256), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
