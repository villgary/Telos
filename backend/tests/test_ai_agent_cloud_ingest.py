"""Ingest RawAgent rows from cloud discovery into the ai_agents table.

Verifies:
- asset_id is NULL on cloud agents
- framework = 'cloud_<provider>'
- discovery_source = 'api_discovery'
- dedup: re-ingest updates the same row, not duplicate
- 2 new risk rules fire: single-agent-connection + code_exec, and
  cross-connection key reuse
"""
import os
import sys
from datetime import datetime
from unittest.mock import MagicMock

os.environ.setdefault("ACCOUNTSCAN_MASTER_KEY", "test_master_key_0123456789abcdef01234567")
os.environ.setdefault("ACCOUNTSCAN_JWT_SECRET", "test_jwt_secret_0123456789abcdef0123456")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database import Base
from backend import models
from backend.services import crypto
from backend.services.cloud_discovery import RawAgent
from backend.services.ai_agent_scanner import ingest_cloud_agents


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    s = Session()
    yield s
    s.close()


def _make_user(db):
    u = models.User(username="alice", email="a@b", password_hash="x",
                    role=models.UserRole.admin)
    db.add(u); db.commit(); db.refresh(u)
    return u


def _make_connection(db, user, name="acme", provider="anthropic", api_key="sk-test"):
    enc = crypto.encrypt(api_key)
    c = models.CloudConnection(
        name=name, provider=provider, encrypted_api_key=enc,
        api_key_fingerprint=crypto.fingerprint(api_key) or "0" * 16,
        created_by_user_id=user.id,
    )
    db.add(c); db.commit(); db.refresh(c)
    return c


def test_ingest_writes_aiagent_with_cloud_metadata(db):
    user = _make_user(db)
    conn = _make_connection(db, user)
    raws = [
        RawAgent(provider="anthropic", project_label="Prod",
                 agent_name="acme / Prod / k1",
                 api_key_fingerprint="1234567890abcdef"),
    ]
    agents = ingest_cloud_agents(db, conn, raws)
    assert len(agents) == 1
    a = agents[0]
    assert a.framework == "cloud_anthropic"
    assert a.discovery_source == "api_discovery"
    assert a.asset_id is None
    assert a.connection_id == conn.id
    assert a.api_key_fingerprint == "1234567890abcdef"


def test_ingest_dedup_updates_existing_row(db):
    user = _make_user(db)
    conn = _make_connection(db, user)
    raws = [RawAgent(provider="anthropic", project_label="Prod",
                     agent_name="acme / Prod / k1",
                     api_key_fingerprint="1234567890abcdef")]

    first = ingest_cloud_agents(db, conn, raws)
    assert len(first) == 1
    first_id = first[0].id

    second = ingest_cloud_agents(db, conn, raws)
    assert len(second) == 1
    assert second[0].id == first_id  # same row, updated, not new

    rows = db.query(models.AIAgent).filter(
        models.AIAgent.framework == "cloud_anthropic").all()
    assert len(rows) == 1


def test_single_agent_connection_with_code_exec_adds_risk(db):
    user = _make_user(db)
    conn = _make_connection(db, user)
    raws = [RawAgent(provider="anthropic", project_label="Prod",
                     agent_name="acme / Prod / k1",
                     api_key_fingerprint="1234567890abcdef",
                     capabilities={"filesystem": False, "network": False,
                                   "code_exec": True, "tool_count": 0})]
    agents = ingest_cloud_agents(db, conn, raws)
    rule_names = {s["signal"] for s in agents[0].risk_signals}
    assert "single_agent_code_exec" in rule_names
    assert agents[0].risk_score >= 10


def test_cross_connection_key_reuse_adds_risk(db):
    user = _make_user(db)
    conn1 = _make_connection(db, user, name="c1", api_key="sk-1")
    conn2 = _make_connection(db, user, name="c2", api_key="sk-2")

    # Same fingerprint appears under both connections
    shared_fp = "abcdef1234567890"
    ingest_cloud_agents(db, conn1, [
        RawAgent(provider="anthropic", project_label="P1",
                 agent_name="c1 / P1 / k1", api_key_fingerprint=shared_fp),
    ])
    agents2 = ingest_cloud_agents(db, conn2, [
        RawAgent(provider="anthropic", project_label="P2",
                 agent_name="c2 / P2 / k1", api_key_fingerprint=shared_fp),
    ])

    rule_names = {s["signal"] for s in agents2[0].risk_signals}
    assert "cross_connection_key_reuse" in rule_names
