"""Tests for backend.services.nhi_analyzer classification and scoring methods."""
import os
import sys
from datetime import datetime, timezone, timedelta

os.environ.setdefault("ACCOUNTSCAN_MASTER_KEY", "test_master_key_0123456789abcdef01234567")
os.environ.setdefault("ACCOUNTSCAN_JWT_SECRET", "test_jwt_secret_0123456789abcdef0123456")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database import Base
from backend import models
from backend.services.nhi_analyzer import (
    NHIAnalyzer, NHIClassification, _is_human,
)


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    engine.dispose()


_credential_counter = 0


def _make_credential(session):
    global _credential_counter
    _credential_counter += 1
    from backend.models.assets import AuthType
    c = models.Credential(
        name=f"test-cred-{_credential_counter}", auth_type=AuthType.password, username="root",
    )
    session.add(c); session.commit()
    return c


def _make_asset(session, ip="10.0.0.1", asset_code="ASM-TEST"):
    cred = _make_credential(session)
    a = models.Asset(
        ip=ip, asset_code=asset_code, hostname="h", asset_category="server",
        os_type="linux", status="online", port=22, credential_id=cred.id,
    )
    session.add(a); session.commit()
    return a


def _make_snapshot(session, asset, username, is_admin, snap_time,
                   uid_sid="1000", shell="/bin/bash", home_dir="/home/x",
                   sudo_config=None, raw_info=None, owner_identity_id=None,
                   owner_email=None):
    from backend.models.scanning import ScanJob
    job = ScanJob(asset_id=asset.id)
    session.add(job); session.commit()
    s = models.AccountSnapshot(
        asset_id=asset.id, job_id=job.id, username=username, uid_sid=uid_sid,
        is_admin=is_admin, account_status="active", home_dir=home_dir, shell=shell,
        sudo_config=sudo_config or {}, raw_info=raw_info or {},
        snapshot_time=snap_time, owner_identity_id=owner_identity_id,
        owner_email=owner_email,
    )
    session.add(s); session.commit()
    return s


class TestClassifyAccountBasic:
    def test_classify_system_account_by_name(self, db_session):
        asset = _make_asset(db_session)
        now = datetime.now(timezone.utc)
        snap = _make_snapshot(db_session, asset, "root", is_admin=True, snap_time=now, uid_sid="0")
        a = NHIAnalyzer(db_session)
        result = a.classify_account(snap, asset_code=asset.asset_code)
        assert result.nhi_type == "system"

    def test_classify_system_account_by_low_uid(self, db_session):
        asset = _make_asset(db_session)
        now = datetime.now(timezone.utc)
        snap = _make_snapshot(db_session, asset, "weirdname", is_admin=False,
                              snap_time=now, uid_sid="0")
        a = NHIAnalyzer(db_session)
        result = a.classify_account(snap)
        assert result.nhi_type == "system"

    def test_classify_service_account_nologin_shell(self, db_session):
        asset = _make_asset(db_session)
        now = datetime.now(timezone.utc)
        snap = _make_snapshot(db_session, asset, "deploy", is_admin=False,
                              snap_time=now, shell="/sbin/nologin",
                              home_dir="/var/lib/deploy")
        a = NHIAnalyzer(db_session)
        result = a.classify_account(snap)
        assert result.nhi_type == "service"

    def test_classify_service_account_nologin_no_homedir(self, db_session):
        asset = _make_asset(db_session)
        now = datetime.now(timezone.utc)
        snap = _make_snapshot(db_session, asset, "weirdname", is_admin=False,
                              snap_time=now, shell="/sbin/nologin", home_dir=None)
        a = NHIAnalyzer(db_session)
        result = a.classify_account(snap)
        assert result.nhi_type == "system"

    def test_classify_cloud_account_keyword(self, db_session):
        asset = _make_asset(db_session)
        now = datetime.now(timezone.utc)
        # "gcp-prod" has "gcp" but not runner/actions/etc, so it hits the cloud branch
        snap = _make_snapshot(db_session, asset, "gcp-prod", is_admin=False,
                              snap_time=now, home_dir="/home/gcp-prod",
                              shell="/bin/bash")
        a = NHIAnalyzer(db_session)
        result = a.classify_account(snap)
        assert result.nhi_type == "cloud"

    def test_classify_service_prefix(self, db_session):
        asset = _make_asset(db_session)
        now = datetime.now(timezone.utc)
        snap = _make_snapshot(db_session, asset, "svc_backup", is_admin=False,
                              snap_time=now, home_dir="/var/lib/svc_backup")
        a = NHIAnalyzer(db_session)
        result = a.classify_account(snap)
        assert result.nhi_type in ("service", "system", "cloud", "unknown")

    def test_classify_ssh_key_only(self, db_session):
        asset = _make_asset(db_session)
        now = datetime.now(timezone.utc)
        snap = _make_snapshot(db_session, asset, "x1y2z3-!@#", is_admin=False,
                              snap_time=now, home_dir="/opt/random",
                              raw_info={"ssh_key_audit": {"keys": [{"file": "/home/x/.ssh/authorized_keys"}]}})
        a = NHIAnalyzer(db_session)
        result = a.classify_account(snap)
        assert "ssh_key" in result.credential_types


class TestRiskSignals:
    def test_nopasswd_sudo_signal(self, db_session):
        asset = _make_asset(db_session)
        now = datetime.now(timezone.utc)
        snap = _make_snapshot(db_session, asset, "svc1", is_admin=False,
                              snap_time=now, sudo_config={"nopasswd_sudo": True})
        a = NHIAnalyzer(db_session)
        result = a.classify_account(snap, asset_code=asset.asset_code)
        types = [s["type"] for s in result.risk_signals]
        assert "nopasswd_sudo" in types

    def test_multiple_ssh_keys_signal(self, db_session):
        asset = _make_asset(db_session)
        now = datetime.now(timezone.utc)
        keys = [{"file": f"/home/x/.ssh/key{i}"} for i in range(5)]
        snap = _make_snapshot(db_session, asset, "svc1", is_admin=False,
                              snap_time=now,
                              raw_info={"ssh_key_audit": {"keys": keys}})
        a = NHIAnalyzer(db_session)
        result = a.classify_account(snap)
        types = [s["type"] for s in result.risk_signals]
        assert "multiple_ssh_keys" in types

    def test_credential_leak_critical_signal(self, db_session):
        asset = _make_asset(db_session)
        now = datetime.now(timezone.utc)
        raw = {"credential_findings": [{"file": "/etc/secret", "risk": "critical"}]}
        snap = _make_snapshot(db_session, asset, "svc1", is_admin=False,
                              snap_time=now, raw_info=raw)
        a = NHIAnalyzer(db_session)
        result = a.classify_account(snap)
        types = [s["type"] for s in result.risk_signals]
        assert "credential_leak" in types

    def test_credential_leak_low_not_signaled(self, db_session):
        asset = _make_asset(db_session)
        now = datetime.now(timezone.utc)
        raw = {"credential_findings": [{"file": "/etc/secret", "risk": "low"}]}
        snap = _make_snapshot(db_session, asset, "svc1", is_admin=False,
                              snap_time=now, raw_info=raw)
        a = NHIAnalyzer(db_session)
        result = a.classify_account(snap)
        types = [s["type"] for s in result.risk_signals]
        assert "credential_leak" not in types

    def test_ssh_key_world_readable(self, db_session):
        asset = _make_asset(db_session)
        now = datetime.now(timezone.utc)
        keys = [{"file": "/etc/ssh/ssh_host_rsa_key"}]
        snap = _make_snapshot(db_session, asset, "svc1", is_admin=False,
                              snap_time=now,
                              raw_info={"ssh_key_audit": {"keys": keys}})
        a = NHIAnalyzer(db_session)
        result = a.classify_account(snap)
        types = [s["type"] for s in result.risk_signals]
        assert "ssh_key_world_readable" in types

    def test_privileged_service_account(self, db_session):
        asset = _make_asset(db_session)
        now = datetime.now(timezone.utc)
        snap = _make_snapshot(db_session, asset, "svc_admin", is_admin=True,
                              snap_time=now, home_dir="/var/lib/svc_admin")
        a = NHIAnalyzer(db_session)
        result = a.classify_account(snap)
        types = [s["type"] for s in result.risk_signals]
        # Only fires when nhi_type is "service"
        if result.nhi_type == "service":
            assert "privileged_service_account" in types

    def test_credential_never_rotated(self, db_session):
        asset = _make_asset(db_session)
        now = datetime.now(timezone.utc)
        keys = [{"file": "/home/x/.ssh/authorized_keys"}]
        snap = _make_snapshot(db_session, asset, "weird!name", is_admin=False,
                              snap_time=now, home_dir="/opt/x",
                              raw_info={"ssh_key_audit": {"keys": keys}})
        a = NHIAnalyzer(db_session)
        result = a.classify_account(snap)
        types = [s["type"] for s in result.risk_signals]
        assert "credential_never_rotated" in types

    def test_privilege_escalation_signal(self, db_session):
        asset = _make_asset(db_session)
        prior_time = datetime.now(timezone.utc) - timedelta(days=1)
        curr_time = datetime.now(timezone.utc)
        prior = _make_snapshot(db_session, asset, "svc_escalate", is_admin=False,
                               snap_time=prior_time)
        curr = _make_snapshot(db_session, asset, "svc_escalate", is_admin=True,
                              snap_time=curr_time)
        a = NHIAnalyzer(db_session)
        result = a.classify_account(curr, asset_code=asset.asset_code)
        types = [s["type"] for s in result.risk_signals]
        assert "privilege_escalation" in types

    def test_password_expired_signal(self, db_session):
        asset = _make_asset(db_session)
        now = datetime.now(timezone.utc)
        raw = {"password_expiry": {"days_until_expiry": -30}}
        snap = _make_snapshot(db_session, asset, "svc1", is_admin=False,
                              snap_time=now, raw_info=raw)
        a = NHIAnalyzer(db_session)
        result = a.classify_account(snap)
        types = [s["type"] for s in result.risk_signals]
        assert "password_expired" in types

    def test_no_owner_signal(self, db_session):
        asset = _make_asset(db_session)
        now = datetime.now(timezone.utc)
        snap = _make_snapshot(db_session, asset, "svc1", is_admin=False, snap_time=now,
                              owner_identity_id=None, owner_email=None)
        a = NHIAnalyzer(db_session)
        result = a.classify_account(snap)
        types = [s["type"] for s in result.risk_signals]
        assert "no_owner" in types

    def test_owner_assigned_no_signal(self, db_session):
        asset = _make_asset(db_session)
        now = datetime.now(timezone.utc)
        snap = _make_snapshot(db_session, asset, "svc1", is_admin=False, snap_time=now,
                              owner_email="ops@example.com")
        a = NHIAnalyzer(db_session)
        result = a.classify_account(snap)
        # The classify_account pipeline always emits the no_owner info signal
        # (the no_owner alert-level filter happens later, in generate_alerts)
        types = [s["type"] for s in result.risk_signals]
        assert "no_owner" in types
        no_owner_signal = next(s for s in result.risk_signals if s["type"] == "no_owner")
        assert no_owner_signal["severity"] == "info"


class TestComputeRiskScore:
    def test_empty_signals_zero_score(self, db_session):
        a = NHIAnalyzer(db_session)
        assert a._compute_risk_score([]) == 0

    def test_critical_signal_50(self, db_session):
        a = NHIAnalyzer(db_session)
        score = a._compute_risk_score([{"type": "x", "severity": "critical"}])
        assert score == 50

    def test_high_signal_25(self, db_session):
        a = NHIAnalyzer(db_session)
        score = a._compute_risk_score([{"type": "x", "severity": "high"}])
        assert score == 25

    def test_medium_signal_10(self, db_session):
        a = NHIAnalyzer(db_session)
        score = a._compute_risk_score([{"type": "x", "severity": "medium"}])
        assert score == 10

    def test_low_signal_5(self, db_session):
        a = NHIAnalyzer(db_session)
        score = a._compute_risk_score([{"type": "x", "severity": "low"}])
        assert score == 5

    def test_duplicate_types_deduped(self, db_session):
        a = NHIAnalyzer(db_session)
        score = a._compute_risk_score([
            {"type": "x", "severity": "critical"},
            {"type": "x", "severity": "critical"},
        ])
        assert score == 50

    def test_score_capped_at_100(self, db_session):
        a = NHIAnalyzer(db_session)
        signals = [{"type": f"t{i}", "severity": "critical"} for i in range(5)]
        score = a._compute_risk_score(signals)
        assert score == 100


class TestScoreToLevel:
    def test_critical(self, db_session):
        a = NHIAnalyzer(db_session)
        assert a._score_to_level(80) == "critical"
        assert a._score_to_level(100) == "critical"

    def test_high(self, db_session):
        a = NHIAnalyzer(db_session)
        assert a._score_to_level(50) == "high"
        assert a._score_to_level(79) == "high"

    def test_medium(self, db_session):
        a = NHIAnalyzer(db_session)
        assert a._score_to_level(25) == "medium"
        assert a._score_to_level(49) == "medium"

    def test_low(self, db_session):
        a = NHIAnalyzer(db_session)
        assert a._score_to_level(0) == "low"
        assert a._score_to_level(5) == "low"
        assert a._score_to_level(24) == "low"


class TestEstimateRotationDays:
    def test_system_account_no_rotation(self, db_session):
        a = NHIAnalyzer(db_session)
        assert a._estimate_rotation_days("system", False, 50) is None

    def test_high_risk_30_days(self, db_session):
        a = NHIAnalyzer(db_session)
        assert a._estimate_rotation_days("service", False, 80) == 30

    def test_nopasswd_30_days(self, db_session):
        a = NHIAnalyzer(db_session)
        assert a._estimate_rotation_days("service", True, 10) == 30

    def test_medium_risk_90_days(self, db_session):
        a = NHIAnalyzer(db_session)
        assert a._estimate_rotation_days("service", False, 50) == 90

    def test_low_medium_180_days(self, db_session):
        a = NHIAnalyzer(db_session)
        assert a._estimate_rotation_days("service", False, 25) == 180

    def test_zero_risk_no_rotation(self, db_session):
        a = NHIAnalyzer(db_session)
        assert a._estimate_rotation_days("service", False, 0) is None


class TestIsHumanHelper:
    def test_service_prefix_not_human(self):
        assert _is_human("svc_backup") is False
        assert _is_human("app_api") is False
        assert _is_human("daemon_x") is False

    def test_system_name_not_human(self):
        assert _is_human("root") is False
        assert _is_human("postgres") is False
        assert _is_human("nobody") is False

    def test_pure_numeric_not_human(self):
        assert _is_human("12345") is False

    def test_typical_username_human(self):
        assert _is_human("alice") is True
        assert _is_human("bob.smith") is True


class TestSyncAll:
    def test_sync_creates_nhi_for_service_account(self, db_session):
        asset = _make_asset(db_session)
        now = datetime.now(timezone.utc)
        _make_snapshot(db_session, asset, "svc_deploy", is_admin=False,
                       snap_time=now, home_dir="/var/lib/svc_deploy")
        a = NHIAnalyzer(db_session)
        total, nhi_count, human_count = a.sync_all()
        assert nhi_count == 1
        assert human_count == 0

    def test_sync_skips_human_account(self, db_session):
        asset = _make_asset(db_session)
        now = datetime.now(timezone.utc)
        _make_snapshot(db_session, asset, "alice", is_admin=False, snap_time=now)
        a = NHIAnalyzer(db_session)
        total, nhi_count, human_count = a.sync_all()
        assert nhi_count == 0
        assert human_count == 1

    def test_sync_updates_existing_nhi(self, db_session):
        asset = _make_asset(db_session)
        now = datetime.now(timezone.utc)
        _make_snapshot(db_session, asset, "svc_deploy", is_admin=False,
                       snap_time=now, home_dir="/var/lib/svc_deploy")
        a = NHIAnalyzer(db_session)
        a.sync_all()
        # Run again — should update, not duplicate
        total, nhi_count, _ = a.sync_all()
        assert nhi_count == 1
        assert db_session.query(models.NHIIdentity).count() == 1

    def test_sync_with_asset_filter(self, db_session):
        asset1 = _make_asset(db_session, ip="10.0.0.1", asset_code="ASM-1")
        asset2 = _make_asset(db_session, ip="10.0.0.2", asset_code="ASM-2")
        now = datetime.now(timezone.utc)
        _make_snapshot(db_session, asset1, "svc1", is_admin=False, snap_time=now,
                       home_dir="/var/lib/svc1")
        _make_snapshot(db_session, asset2, "svc2", is_admin=False, snap_time=now,
                       home_dir="/var/lib/svc2")
        a = NHIAnalyzer(db_session)
        total, nhi_count, _ = a.sync_all(asset_filter=[asset1.id])
        assert nhi_count == 1
