"""Compliance, policy, and OPA/Rego ORM models."""
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime,
    ForeignKey, Text, JSON, UniqueConstraint,
)
from sqlalchemy.orm import relationship

from backend.models._db import Base


class ComplianceFramework(Base):
    __tablename__ = "compliance_frameworks"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    slug = Column(String(32), unique=True, nullable=False)
    name = Column(String(64), nullable=False)
    description = Column(Text, nullable=True)
    version = Column(String(16), nullable=False, default="1.0")
    enabled = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    checks = relationship("ComplianceCheck", back_populates="framework", cascade="all, delete-orphan")
    runs = relationship("ComplianceRun", back_populates="framework", cascade="all, delete-orphan")


class ComplianceCheck(Base):
    __tablename__ = "compliance_checks"
    __table_args__ = (UniqueConstraint("framework_id", "check_key", name="uq_fw_check_key"),)

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    framework_id = Column(Integer, ForeignKey("compliance_frameworks.id"), nullable=False)
    check_key = Column(String(64), nullable=False)
    title = Column(String(256), nullable=False)
    description = Column(Text, nullable=True)
    severity = Column(String(16), nullable=False, default="medium")
    applies_to = Column(String(128), nullable=False, default="server,database,network,iot")
    parameters = Column(JSON, nullable=True)
    enabled = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    framework = relationship("ComplianceFramework", back_populates="checks")


class ComplianceRun(Base):
    __tablename__ = "compliance_runs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    framework_id = Column(Integer, ForeignKey("compliance_frameworks.id"), nullable=False)
    trigger_type = Column(String(16), nullable=False, default="manual")
    status = Column(String(16), nullable=False, default="running")
    total = Column(Integer, default=0)
    passed = Column(Integer, default=0)
    failed = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    finished_at = Column(DateTime, nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)

    framework = relationship("ComplianceFramework", back_populates="runs")
    creator = relationship("User", foreign_keys=[created_by])
    results = relationship("ComplianceResult", back_populates="run", cascade="all, delete-orphan")


class ComplianceResult(Base):
    __tablename__ = "compliance_results"
    __table_args__ = (UniqueConstraint("run_id", "check_id", name="uq_run_check"),)

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    run_id = Column(Integer, ForeignKey("compliance_runs.id"), nullable=False)
    framework_id = Column(Integer, ForeignKey("compliance_frameworks.id"), nullable=False)
    check_id = Column(Integer, ForeignKey("compliance_checks.id"), nullable=False)
    asset_id = Column(Integer, ForeignKey("assets.id"), nullable=False)
    status = Column(String(8), nullable=False)
    evidence = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)
    evaluated_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    run = relationship("ComplianceRun", back_populates="results")
    framework = relationship("ComplianceFramework")
    check = relationship("ComplianceCheck")
    asset = relationship("Asset")


class SecurityPolicy(Base):
    __tablename__ = "security_policies"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(128), nullable=False)
    description = Column(Text, nullable=True)
    name_key = Column(String(128), nullable=True)
    description_key = Column(String(128), nullable=True)
    category = Column(String(32), nullable=True)
    severity = Column(String(16), nullable=False, default="high")
    rego_code = Column(Text, nullable=False)
    enabled = Column(Boolean, default=True, nullable=False)
    is_built_in = Column(Boolean, default=False, nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    creator = relationship("User")
    evaluation_results = relationship("PolicyEvaluationResult", back_populates="policy", cascade="all, delete-orphan")


class PolicyEvaluationResult(Base):
    __tablename__ = "policy_evaluation_results"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    policy_id = Column(Integer, ForeignKey("security_policies.id"), nullable=False)
    snapshot_id = Column(Integer, ForeignKey("account_snapshots.id"), nullable=False)
    passed = Column(Boolean, nullable=False)
    message = Column(Text, nullable=True)
    evaluated_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    policy = relationship("SecurityPolicy", back_populates="evaluation_results")
    snapshot = relationship("AccountSnapshot")
