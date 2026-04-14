"""Scanning-related ORM models."""
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, Enum,
    ForeignKey, Text, JSON,
)
from sqlalchemy.orm import relationship

from backend.models._db import Base
from backend.models._enums import TriggerType, ScanJobStatus, DiffType, RiskLevel, DiffStatus


class ScanJob(Base):
    __tablename__ = "scan_jobs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    asset_id = Column(Integer, ForeignKey("assets.id"), nullable=False)
    trigger_type = Column(Enum(TriggerType), default=TriggerType.manual, nullable=False)
    status = Column(Enum(ScanJobStatus), default=ScanJobStatus.pending, nullable=False)
    success_count = Column(Integer, default=0)
    failed_count = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    finished_at = Column(DateTime, nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    creator = relationship("User", back_populates="scan_jobs", foreign_keys=[created_by])
    snapshots = relationship("AccountSnapshot", back_populates="job")


class AccountSnapshot(Base):
    __tablename__ = "account_snapshots"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    asset_id = Column(Integer, ForeignKey("assets.id"), nullable=False)
    job_id = Column(Integer, ForeignKey("scan_jobs.id"), nullable=False)
    username = Column(String(128), nullable=False, index=True)
    uid_sid = Column(String(256), nullable=False)
    is_admin = Column(Boolean, default=False, nullable=False)
    account_status = Column(String(32), nullable=True)
    home_dir = Column(String(512), nullable=True)
    shell = Column(String(128), nullable=True)
    groups = Column(JSON, default=list)
    sudo_config = Column(JSON, nullable=True)
    last_login = Column(DateTime, nullable=True)
    raw_info = Column(JSON, nullable=True)
    snapshot_time = Column(DateTime, nullable=False)
    is_baseline = Column(Boolean, default=False, nullable=False)
    deleted_at = Column(DateTime, nullable=True)
    owner_identity_id = Column(Integer, ForeignKey("human_identities.id"), nullable=True)
    owner_email = Column(String(256), nullable=True)
    owner_name = Column(String(128), nullable=True)

    asset = relationship("Asset", back_populates="snapshots")
    job = relationship("ScanJob", back_populates="snapshots")
    owner = relationship("HumanIdentity")


class DiffResult(Base):
    __tablename__ = "diff_results"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    base_job_id = Column(Integer, ForeignKey("scan_jobs.id"), nullable=False)
    compare_job_id = Column(Integer, ForeignKey("scan_jobs.id"), nullable=False)
    diff_type = Column(Enum(DiffType), nullable=False)
    risk_level = Column(Enum(RiskLevel), nullable=False)
    username = Column(String(128), nullable=False)
    snapshot_a_id = Column(Integer, ForeignKey("account_snapshots.id"), nullable=True)
    snapshot_b_id = Column(Integer, ForeignKey("account_snapshots.id"), nullable=True)
    status = Column(Enum(DiffStatus), default=DiffStatus.pending, nullable=False)
    reviewed_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    reviewer = relationship("User", foreign_keys=[reviewed_by])
    snapshot_a = relationship("AccountSnapshot", foreign_keys=[snapshot_a_id], lazy="noload")
    snapshot_b = relationship("AccountSnapshot", foreign_keys=[snapshot_b_id], lazy="noload")


class ScanSchedule(Base):
    __tablename__ = "scan_schedules"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(128), nullable=False)
    asset_id = Column(Integer, ForeignKey("assets.id"), nullable=False)
    cron_expr = Column(String(64), nullable=False)
    enabled = Column(Boolean, default=True, nullable=False)
    next_run_at = Column(DateTime, nullable=True)
    last_run_at = Column(DateTime, nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    creator = relationship("User", foreign_keys=[created_by])
    asset = relationship("Asset")
