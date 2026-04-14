"""Advanced/specialized ORM models: LLM, KB, threat analysis."""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Enum, ForeignKey, Text, JSON
from sqlalchemy.orm import relationship

from backend.models._db import Base
from backend.models._enums import LLMProvider


class LLMConfig(Base):
    __tablename__ = "llm_configs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    provider = Column(Enum(LLMProvider), nullable=False)
    api_key_enc = Column(Text, nullable=True)
    base_url = Column(String(256), nullable=True)
    model = Column(String(64), nullable=False, default="gpt-4o-mini")
    enabled = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class KBEntry(Base):
    __tablename__ = "kb_entries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    entry_type = Column(String(16), nullable=False, index=True)
    title = Column(String(256), nullable=False)
    title_en = Column(String(256), nullable=True)
    description = Column(Text, nullable=True)
    description_en = Column(Text, nullable=True)
    extra_data = Column("extra_data", JSON, default=dict, nullable=False)
    enabled = Column(Boolean, default=True, nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    creator = relationship("User")


class IdentityThreatAnalysis(Base):
    __tablename__ = "identity_threat_analyses"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    analysis_type = Column(String(32), nullable=False)
    scope = Column(String(32), nullable=False)
    scope_id = Column(Integer, nullable=True)

    semiotic_score = Column(Integer, nullable=False, default=0)
    causal_score = Column(Integer, nullable=False, default=0)
    ontological_score = Column(Integer, nullable=False, default=0)
    cognitive_score = Column(Integer, nullable=False, default=0)
    anthropological_score = Column(Integer, nullable=False, default=0)

    overall_score = Column(Integer, nullable=False, default=0)
    overall_level = Column(String(16), nullable=False)

    semiotic_signals = Column(JSON, default=list)
    causal_signals = Column(JSON, default=list)
    ontological_signals = Column(JSON, default=list)
    cognitive_signals = Column(JSON, default=list)
    anthropological_signals = Column(JSON, default=list)

    threat_graph = Column(JSON, default=dict)
    llm_report = Column(Text, nullable=True)

    analyzed_count = Column(Integer, default=0)
    duration_ms = Column(Integer, nullable=True)
    model_used = Column(String(64), nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    creator = relationship("User")


class ThreatAccountSignal(Base):
    __tablename__ = "threat_account_signals"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    analysis_id = Column(Integer, ForeignKey("identity_threat_analyses.id"), nullable=False)
    snapshot_id = Column(Integer, ForeignKey("account_snapshots.id"), nullable=True)
    username = Column(String(128), nullable=False)
    asset_id = Column(Integer, nullable=False)
    asset_code = Column(String(32), nullable=True)

    semiotic_flags = Column(JSON, default=list)
    causal_flags = Column(JSON, default=list)
    ontological_flags = Column(JSON, default=list)
    cognitive_flags = Column(JSON, default=list)
    anthropological_flags = Column(JSON, default=list)

    account_score = Column(Integer, default=0)
    account_level = Column(String(16), default="low")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    analysis = relationship("IdentityThreatAnalysis")
