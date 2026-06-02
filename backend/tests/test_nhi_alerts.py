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


class TestExistingAlertsI18n:
    def test_risk_alert_has_i18n_keys(self, db_session):
        from backend.services.nhi_analyzer import NHIAnalyzer
        asset = _make_asset(db_session)
        now = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
        snap = _make_snapshot(db_session, asset, "deploy", is_admin=True, snap_time=now)
        nhi = models.NHIIdentity(
            snapshot_id=snap.id, asset_id=asset.id, nhi_type="service", nhi_level="critical",
            username=snap.username, uid_sid=snap.uid_sid, hostname=asset.asset_code,
            ip_address=asset.ip, is_admin=True, has_nopasswd_sudo=False,
            credential_types=[], risk_signals=[], risk_score=80,
            first_seen_at=now, last_seen_at=now, is_active=True,
        )
        db_session.add(nhi); db_session.commit()

        NHIAnalyzer(db_session).generate_alerts()

        alert = db_session.query(models.NHIAlert).filter(
            models.NHIAlert.alert_type == "risk_alert"
        ).first()
        assert alert is not None
        assert alert.title_key == "nhi.alert.risk_alert.title"
        assert alert.title_params == {"username": "deploy", "level": "critical", "score": 80}
        # Chinese fallback still present
        assert "deploy" in alert.title

    def test_no_owner_alert_has_i18n_keys(self, db_session):
        from backend.services.nhi_analyzer import NHIAnalyzer
        asset = _make_asset(db_session)
        now = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
        snap = _make_snapshot(db_session, asset, "deploy", is_admin=False, snap_time=now)
        _make_nhi(db_session, snap, asset, is_admin=False)

        NHIAnalyzer(db_session).generate_alerts()

        alert = db_session.query(models.NHIAlert).filter(
            models.NHIAlert.alert_type == "no_owner"
        ).first()
        assert alert is not None
        assert alert.title_key == "nhi.alert.no_owner.title"
        assert alert.title_params == {"username": "deploy"}


class TestCrossAssetSpreadAlert:
    def _setup_default_policy(self, db_session, threshold=3, window=7, nhi_type=None,
                                enabled_alert_types=None):
        p = models.NHIPolicy(
            name="default", enabled=True, nhi_type=nhi_type,
            enabled_alert_types=enabled_alert_types or [
                "privilege_escalation", "nopasswd_sudo", "credential_leak", "cross_asset_spread",
            ],
            cross_asset_threshold=threshold, cross_asset_window_days=window,
        )
        db_session.add(p); db_session.commit()
        return p

    def test_cluster_alert_fires(self, db_session):
        from backend.services.nhi_analyzer import NHIAnalyzer
        now = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
        # 3 assets, same (nhi_type, username)
        nhis = []
        for ip in ["10.0.0.1", "10.0.0.2", "10.0.0.3"]:
            asset = _make_asset(db_session, ip=ip)
            snap = _make_snapshot(db_session, asset, "deploy", is_admin=False, snap_time=now)
            nhi = _make_nhi(db_session, snap, asset, is_admin=False)
            nhis.append(nhi)
        self._setup_default_policy(db_session)

        NHIAnalyzer(db_session).generate_alerts()

        alert = db_session.query(models.NHIAlert).filter(
            models.NHIAlert.alert_type == "cross_asset_spread"
        ).first()
        assert alert is not None
        assert alert.nhi_id is None
        assert alert.cluster_key == "service:deploy"
        assert alert.nhi_username == "deploy"
        assert alert.nhi_type == "service"
        assert alert.asset_count == 3
        assert alert.title_key == "nhi.alert.cross_asset_spread.title"
        assert alert.title_params == {"username": "deploy", "asset_count": 3}

    def test_cluster_alert_below_threshold(self, db_session):
        from backend.services.nhi_analyzer import NHIAnalyzer
        now = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
        for ip in ["10.0.0.1", "10.0.0.2"]:
            asset = _make_asset(db_session, ip=ip)
            snap = _make_snapshot(db_session, asset, "deploy", is_admin=False, snap_time=now)
            _make_nhi(db_session, snap, asset, is_admin=False)
        self._setup_default_policy(db_session, threshold=3)

        NHIAnalyzer(db_session).generate_alerts()

        assert db_session.query(models.NHIAlert).filter(
            models.NHIAlert.alert_type == "cross_asset_spread"
        ).count() == 0

    def test_cluster_alert_dedup(self, db_session):
        from backend.services.nhi_analyzer import NHIAnalyzer
        now = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
        for ip in ["10.0.0.1", "10.0.0.2", "10.0.0.3"]:
            asset = _make_asset(db_session, ip=ip)
            snap = _make_snapshot(db_session, asset, "deploy", is_admin=False, snap_time=now)
            _make_nhi(db_session, snap, asset, is_admin=False)
        self._setup_default_policy(db_session)

        analyzer = NHIAnalyzer(db_session)
        analyzer.generate_alerts()
        analyzer.generate_alerts()  # second run

        assert db_session.query(models.NHIAlert).filter(
            models.NHIAlert.alert_type == "cross_asset_spread"
        ).count() == 1

    def test_cluster_alert_window_respected(self, db_session):
        from backend.services.nhi_analyzer import NHIAnalyzer
        now = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
        # 3 assets, but one is older than the window
        for i, ip in enumerate(["10.0.0.1", "10.0.0.2", "10.0.0.3"]):
            asset = _make_asset(db_session, ip=ip)
            snap = _make_snapshot(db_session, asset, "deploy", is_admin=False, snap_time=now)
            last_seen = now - timedelta(days=20) if i == 2 else now
            nhi = _make_nhi(db_session, snap, asset, is_admin=False)
            nhi.last_seen_at = last_seen
        db_session.commit()
        self._setup_default_policy(db_session, window=7)

        NHIAnalyzer(db_session).generate_alerts()

        # 1 cluster alert exists but asset_count is 2 (one filtered out)
        alerts = db_session.query(models.NHIAlert).filter(
            models.NHIAlert.alert_type == "cross_asset_spread"
        ).all()
        assert len(alerts) == 0  # below threshold of 3 in window

    def test_cluster_alert_policy_nhi_type_filter(self, db_session):
        from backend.services.nhi_analyzer import NHIAnalyzer
        now = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
        # 3 service NHIs, 3 cloud NHIs — policy only applies to cloud
        for ip in ["10.0.0.1", "10.0.0.2", "10.0.0.3"]:
            asset = _make_asset(db_session, ip=ip)
            s_snap = _make_snapshot(db_session, asset, "deploy", is_admin=False, snap_time=now)
            n_svc = _make_nhi(db_session, s_snap, asset, is_admin=False)
            n_svc.nhi_type = "service"
            c_snap = _make_snapshot(db_session, asset, "cloud-role", is_admin=False, snap_time=now)
            n_cloud = models.NHIIdentity(
                snapshot_id=c_snap.id, asset_id=asset.id, nhi_type="cloud", nhi_level="low",
                username="cloud-role", uid_sid=c_snap.uid_sid, hostname=asset.asset_code,
                ip_address=asset.ip, is_admin=False, has_nopasswd_sudo=False,
                credential_types=[], risk_signals=[],
                first_seen_at=now, last_seen_at=now, is_active=True,
            )
            db_session.add(n_cloud)
        db_session.commit()
        self._setup_default_policy(db_session, nhi_type="cloud")

        NHIAnalyzer(db_session).generate_alerts()

        alerts = db_session.query(models.NHIAlert).filter(
            models.NHIAlert.alert_type == "cross_asset_spread"
        ).all()
        # Only the cloud cluster fires
        assert len(alerts) == 1
        assert alerts[0].nhi_type == "cloud"
        assert alerts[0].nhi_username == "cloud-role"

    def test_most_permissive_policy_wins(self, db_session):
        from backend.services.nhi_analyzer import NHIAnalyzer
        now = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
        # 3 assets — only the most permissive (smallest threshold) policy should fire
        for ip in ["10.0.0.1", "10.0.0.2", "10.0.0.3"]:
            asset = _make_asset(db_session, ip=ip)
            snap = _make_snapshot(db_session, asset, "deploy", is_admin=False, snap_time=now)
            _make_nhi(db_session, snap, asset, is_admin=False)
        # Two policies, both nhi_type=None (global): one with threshold=3, one with threshold=5
        for th in [3, 5]:
            db_session.add(models.NHIPolicy(
                name=f"policy-{th}", enabled=True, nhi_type=None,
                enabled_alert_types=["cross_asset_spread"],
                cross_asset_threshold=th, cross_asset_window_days=7,
            ))
        db_session.commit()

        NHIAnalyzer(db_session).generate_alerts()

        # 3 assets >= both thresholds; but we should only fire ONE alert per cluster
        count = db_session.query(models.NHIAlert).filter(
            models.NHIAlert.alert_type == "cross_asset_spread"
        ).count()
        assert count == 1
