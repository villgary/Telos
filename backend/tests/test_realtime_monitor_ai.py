"""Tests for AI Agent realtime monitor detectors."""
import os
import sys
from datetime import datetime, timedelta

os.environ.setdefault("ACCOUNTSCAN_MASTER_KEY", "test_master_key_0123456789abcdef01234567")
os.environ.setdefault("ACCOUNTSCAN_JWT_SECRET", "test_jwt_secret_0123456789abcdef0123456")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database import Base
from backend import models
from backend.services.realtime_monitor import RealtimeMonitor


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    s = Session()
    yield s
    s.close()


def _agent(db, **overrides):
    base = dict(
        agent_name="test-agent", framework="langchain",
        owner_team="data-eng", owner_user="alice",
        api_key_fingerprint="sha256:abc",
        capabilities={"filesystem": False, "network": False,
                      "code_exec": False, "tool_count": 0},
        last_invocation_at=None,
        last_seen_at=datetime.utcnow(),
        discovered_at=datetime.utcnow(),
        discovery_source="ssh_scan",
        asset_id=1,
        risk_level="low", risk_score=0, risk_signals=[],
        status="active",
    )
    base.update(overrides)
    a = models.AIAgent(**base)
    db.add(a)
    db.commit()
    db.refresh(a)
    return a


class TestNewAIAgentDetector:
    def test_no_alert_on_first_discovery(self, db):
        """The first AIAgent row is not a 'new' alert — alerts fire on
        *subsequent* discovery of an agent on a new asset, not the first ever."""
        a = _agent(db)
        monitor = RealtimeMonitor()
        # With only one agent, no new-alert should fire (no prior baseline)
        n = monitor._detect_new_ai_agents(db)
        assert n == 0

    def test_new_alert_for_high_risk(self, db):
        """A high/critical risk agent on a new asset should alert."""
        a = _agent(db, agent_name="risky-bot", risk_level="high", risk_score=60)
        monitor = RealtimeMonitor()
        # First detector call: no prior baseline, so still no alert.
        monitor._detect_new_ai_agents(db)
        # Simulate a second agent appearing (newer last_seen_at)
        a2 = _agent(db, agent_name="another-bot", risk_level="critical", risk_score=80)
        n = monitor._detect_new_ai_agents(db)
        # Should detect the new high-risk agent
        assert n >= 1


class TestDormantAIAgentDetector:
    def test_dormant_fires_after_90_days(self, db):
        a = _agent(db, status="dormant",
                   last_invocation_at=datetime.utcnow() - timedelta(days=95))
        monitor = RealtimeMonitor()
        n = monitor._detect_dormant_ai_agents(db)
        assert n == 1
        alert = db.query(models.Alert).first()
        assert alert is not None
        assert "dormant" in (alert.title or "").lower() or "ai agent" in (alert.message or "").lower()

    def test_dormant_does_not_fire_for_active(self, db):
        _agent(db, status="active",
               last_invocation_at=datetime.utcnow() - timedelta(days=95))
        monitor = RealtimeMonitor()
        n = monitor._detect_dormant_ai_agents(db)
        assert n == 0
