"""Tests for backend.services.nhi_analyzer alert generation."""
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


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    engine.dispose()


def _make_credential(session):
    from backend.models.assets import AuthType
    c = models.Credential(
        name="test-cred", auth_type=AuthType.password, username="root",
    )
    session.add(c); session.commit()
    return c


def _make_asset(session, ip="10.0.0.1"):
    cred = _make_credential(session)
    a = models.Asset(
        ip=ip, asset_code=f"ASM-{ip}", hostname="h", asset_category="server",
        os_type="linux", status="online", port=22, credential_id=cred.id,
    )
    session.add(a); session.commit()
    return a


def _make_snapshot(session, asset, username, is_admin, snap_time, uid_sid="1000"):
    from backend.models.scanning import ScanJob
    job = ScanJob(asset_id=asset.id)
    session.add(job); session.commit()
    s = models.AccountSnapshot(
        asset_id=asset.id, job_id=job.id, username=username, uid_sid=uid_sid,
        is_admin=is_admin, account_status="active", home_dir="/home/x", shell="/bin/bash",
        snapshot_time=snap_time,
    )
    session.add(s); session.commit()
    return s


def _make_nhi(session, snapshot, asset, is_admin=False, has_nopasswd=False, risk_signals=None):
    n = models.NHIIdentity(
        snapshot_id=snapshot.id, asset_id=asset.id, nhi_type="service", nhi_level="low",
        username=snapshot.username, uid_sid=snapshot.uid_sid, hostname=asset.asset_code,
        ip_address=asset.ip, is_admin=is_admin,
        has_nopasswd_sudo=has_nopasswd, credential_types=[], risk_signals=risk_signals or [],
        first_seen_at=snapshot.snapshot_time, last_seen_at=snapshot.snapshot_time, is_active=True,
    )
    session.add(n); session.commit()
    return n


class TestPrivilegeEscalationAlert:
    def test_escalation_fires(self, db_session):
        from backend.services.nhi_analyzer import NHIAnalyzer
        asset = _make_asset(db_session)
        now = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
        prior = _make_snapshot(db_session, asset, "deploy", is_admin=False, snap_time=now - timedelta(days=2))
        current = _make_snapshot(db_session, asset, "deploy", is_admin=True, snap_time=now)
        # Pre-populate the privilege_escalation risk_signal (as _detect_risk_signals would)
        escalation_signal = {
            "type": "privilege_escalation",
            "detail": "deploy escalated to admin (was non-admin in prior snapshot)",
            "severity": "critical",
            "evidence": f"prior.is_admin=False → current.is_admin=True on {asset.asset_code}",
        }
        nhi = _make_nhi(db_session, current, asset, is_admin=True, risk_signals=[escalation_signal])

        analyzer = NHIAnalyzer(db_session)
        analyzer.generate_alerts()

        alert = db_session.query(models.NHIAlert).filter(
            models.NHIAlert.nhi_id == nhi.id,
            models.NHIAlert.alert_type == "privilege_escalation",
        ).first()
        assert alert is not None
        assert alert.level == "critical"
        assert alert.title_key == "nhi.alert.privilege_escalation.title"
        assert alert.title_params == {
            "username": "deploy", "asset_code": asset.asset_code,
        }
        # risk_signal should still be present (set by test, not stripped by generate_alerts)
        db_session.refresh(nhi)
        assert any(s.get("type") == "privilege_escalation" for s in nhi.risk_signals)

    def test_no_escalation_when_already_admin(self, db_session):
        from backend.services.nhi_analyzer import NHIAnalyzer
        asset = _make_asset(db_session)
        now = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
        prior = _make_snapshot(db_session, asset, "deploy", is_admin=True, snap_time=now - timedelta(days=2))
        current = _make_snapshot(db_session, asset, "deploy", is_admin=True, snap_time=now)
        _make_nhi(db_session, current, asset, is_admin=True)

        analyzer = NHIAnalyzer(db_session)
        analyzer.generate_alerts()

        assert db_session.query(models.NHIAlert).filter(
            models.NHIAlert.alert_type == "privilege_escalation"
        ).count() == 0

    def test_no_escalation_when_deescalated(self, db_session):
        from backend.services.nhi_analyzer import NHIAnalyzer
        asset = _make_asset(db_session)
        now = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
        prior = _make_snapshot(db_session, asset, "deploy", is_admin=True, snap_time=now - timedelta(days=2))
        current = _make_snapshot(db_session, asset, "deploy", is_admin=False, snap_time=now)
        _make_nhi(db_session, current, asset, is_admin=False)

        analyzer = NHIAnalyzer(db_session)
        analyzer.generate_alerts()

        assert db_session.query(models.NHIAlert).filter(
            models.NHIAlert.alert_type == "privilege_escalation"
        ).count() == 0


class TestNopasswdSudoAlert:
    def test_nopasswd_sudo_alert(self, db_session):
        from backend.services.nhi_analyzer import NHIAnalyzer
        asset = _make_asset(db_session)
        now = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
        snap = _make_snapshot(db_session, asset, "deploy", is_admin=True, snap_time=now)
        nhi = _make_nhi(db_session, snap, asset, is_admin=True, has_nopasswd=True)

        NHIAnalyzer(db_session).generate_alerts()

        alert = db_session.query(models.NHIAlert).filter(
            models.NHIAlert.nhi_id == nhi.id,
            models.NHIAlert.alert_type == "nopasswd_sudo",
        ).first()
        assert alert is not None
        assert alert.level == "critical"
        assert alert.title_key == "nhi.alert.nopasswd_sudo.title"

    def test_nopasswd_sudo_dedup(self, db_session):
        from backend.services.nhi_analyzer import NHIAnalyzer
        asset = _make_asset(db_session)
        now = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
        snap = _make_snapshot(db_session, asset, "deploy", is_admin=True, snap_time=now)
        nhi = _make_nhi(db_session, snap, asset, is_admin=True, has_nopasswd=True)

        analyzer = NHIAnalyzer(db_session)
        analyzer.generate_alerts()
        analyzer.generate_alerts()  # second run

        count = db_session.query(models.NHIAlert).filter(
            models.NHIAlert.nhi_id == nhi.id,
            models.NHIAlert.alert_type == "nopasswd_sudo",
        ).count()
        assert count == 1


class TestCredentialLeakAlert:
    def test_credential_leak_alert(self, db_session):
        from backend.services.nhi_analyzer import NHIAnalyzer
        asset = _make_asset(db_session)
        now = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
        snap = _make_snapshot(db_session, asset, "deploy", is_admin=False, snap_time=now)
        leak_signals = [{
            "type": "credential_leak", "severity": "critical",
            "detail": "x", "evidence": "/home/deploy/.aws/credentials",
        }]
        nhi = _make_nhi(db_session, snap, asset, is_admin=False, risk_signals=leak_signals)

        NHIAnalyzer(db_session).generate_alerts()

        alert = db_session.query(models.NHIAlert).filter(
            models.NHIAlert.nhi_id == nhi.id,
            models.NHIAlert.alert_type == "credential_leak",
        ).first()
        assert alert is not None
        assert alert.title_key == "nhi.alert.credential_leak.title"
        assert alert.message_params["file_count"] == 1

    def test_no_alert_for_non_critical_credential_signal(self, db_session):
        from backend.services.nhi_analyzer import NHIAnalyzer
        asset = _make_asset(db_session)
        now = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
        snap = _make_snapshot(db_session, asset, "deploy", is_admin=False, snap_time=now)
        # medium-severity leak — should NOT fire credential_leak alert
        signals = [{
            "type": "credential_leak", "severity": "medium",
            "detail": "x", "evidence": "/tmp/x",
        }]
        _make_nhi(db_session, snap, asset, is_admin=False, risk_signals=signals)

        NHIAnalyzer(db_session).generate_alerts()

        assert db_session.query(models.NHIAlert).filter(
            models.NHIAlert.alert_type == "credential_leak"
        ).count() == 0
