"""Alert and review ORM models."""
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, Enum,
    ForeignKey, Text, JSON,
)
from sqlalchemy.orm import relationship

from backend.models._db import Base
from backend.models._enums import AlertChannel, AlertLevel


class AlertConfig(Base):
    __tablename__ = "alert_configs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(128), nullable=False)
    channel = Column(Enum(AlertChannel), nullable=False)
    enabled = Column(Boolean, default=True, nullable=False)
    settings = Column(JSON, nullable=True)
    asset_ids = Column(JSON, default=list)
    risk_levels = Column(JSON, default=list)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    creator = relationship("User", foreign_keys=[created_by])
    alerts = relationship("Alert")


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    config_id = Column(Integer, ForeignKey("alert_configs.id"), nullable=True)
    asset_id = Column(Integer, ForeignKey("assets.id"), nullable=False)
    job_id = Column(Integer, ForeignKey("scan_jobs.id"), nullable=True)
    diff_item_id = Column(Integer, ForeignKey("diff_results.id"), nullable=True)
    level = Column(Enum(AlertLevel), nullable=False)
    title = Column(String(256), nullable=False)
    message = Column(Text, nullable=False)
    title_key = Column(String(64), nullable=True)
    title_params = Column(JSON, nullable=True)
    message_key = Column(String(64), nullable=True)
    message_params = Column(JSON, nullable=True)
    is_read = Column(Boolean, default=False, nullable=False)
    status = Column(String(16), default="new", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    target_identity_id = Column(Integer, ForeignKey("human_identities.id"), nullable=True)

    config = relationship("AlertConfig", foreign_keys=[config_id], overlaps="alerts")
    asset = relationship("Asset")
    job = relationship("ScanJob", foreign_keys=[job_id])
    diff_result = relationship("DiffResult", foreign_keys=[diff_item_id])
    target_identity = relationship("HumanIdentity", foreign_keys=[target_identity_id])


class ReviewPlaybook(Base):
    __tablename__ = "review_playbooks"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(128), nullable=False)
    description = Column(Text, nullable=True)
    name_key = Column(String(128), nullable=True)
    description_key = Column(String(128), nullable=True)
    trigger_type = Column(String(32), nullable=False)
    trigger_filter = Column(JSON, default=dict)
    steps = Column(JSON, default=list)
    approval_required = Column(Boolean, default=True)
    enabled = Column(Boolean, default=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    creator = relationship("User", foreign_keys=[created_by])
    executions = relationship("PlaybookExecution", back_populates="playbook")


class PlaybookExecution(Base):
    __tablename__ = "playbook_executions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    playbook_id = Column(Integer, ForeignKey("review_playbooks.id"), nullable=False)
    snapshot_id = Column(Integer, ForeignKey("account_snapshots.id"), nullable=False)
    status = Column(String(24), nullable=False, default="pending_approval")
    steps_status = Column(JSON, default=list)
    result = Column(Text, nullable=True)
    triggered_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    approved_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    approved_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    playbook = relationship("ReviewPlaybook", back_populates="executions")
    snapshot = relationship("AccountSnapshot")
    trigger_user = relationship("User", foreign_keys=[triggered_by])
    approver = relationship("User", foreign_keys=[approved_by])


class ReviewSchedule(Base):
    __tablename__ = "review_schedules"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(128), nullable=False)
    period = Column(String(16), nullable=False)
    day_of_month = Column(Integer, default=1)
    alert_channels = Column(JSON, nullable=True)
    enabled = Column(Boolean, default=True, nullable=False)
    next_run_at = Column(DateTime, nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    created_user = relationship("User")
    reports = relationship("ReviewReport", back_populates="schedule", cascade="all, delete-orphan")


class ReviewReport(Base):
    __tablename__ = "review_reports"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    schedule_id = Column(Integer, ForeignKey("review_schedules.id"), nullable=False)
    period = Column(String(16), nullable=False)
    period_start = Column(DateTime, nullable=False)
    period_end = Column(DateTime, nullable=False)
    status = Column(String(16), default="pending_review")
    reviewed_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    notes = Column(Text, nullable=True)
    content_summary = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    schedule = relationship("ReviewSchedule", back_populates="reports")
    reviewer = relationship("User")
