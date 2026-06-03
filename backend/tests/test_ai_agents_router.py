"""Integration tests for /api/v1/ai-agents router."""
import os
import sys
from datetime import datetime

os.environ.setdefault("ACCOUNTSCAN_MASTER_KEY", "test_master_key_0123456789abcdef01234567")
os.environ.setdefault("ACCOUNTSCAN_JWT_SECRET", "test_jwt_secret_0123456789abcdef0123456")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.database import Base, get_db
from backend import models, auth
from backend.main import app


@pytest.fixture
def db():
    # StaticPool ensures the :memory: SQLite database is shared across
    # the connection the test uses and the one the FastAPI app uses
    # (TestClient runs the app in a different thread).
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    s = Session()
    yield s
    s.close()


@pytest.fixture
def client(db):
    # Seed an admin user so auth.get_current_user can resolve the JWT's `sub`.
    user = models.User(
        username="admin",
        password_hash=auth.hash_password("test-password-1234"),
        role=models.UserRole.admin,
        email="admin@example.com",
        is_active=True,
    )
    db.add(user)
    db.commit()

    app.dependency_overrides[get_db] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def admin_token():
    return auth.create_access_token({"sub": "admin", "role": "admin"})


def _seed_agent(db, **overrides):
    base = dict(
        agent_name="test", framework="langchain", owner_team="data-eng",
        owner_user="alice", api_key_fingerprint="sha256:abc",
        capabilities={"filesystem": False, "network": False,
                      "code_exec": False, "tool_count": 0},
        last_seen_at=datetime.utcnow(),
        discovered_at=datetime.utcnow(),
        discovery_source="ssh_scan", asset_id=1,
        risk_level="low", risk_score=0, risk_signals=[], status="active",
    )
    base.update(overrides)
    a = models.AIAgent(**base)
    db.add(a)
    db.commit()
    db.refresh(a)
    return a


class TestList:
    def test_empty_list(self, client, admin_token):
        r = client.get("/api/v1/ai-agents",
                       headers={"Authorization": f"Bearer {admin_token}"})
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 0
        assert body["agents"] == []

    def test_filter_by_framework(self, client, db, admin_token):
        _seed_agent(db, agent_name="lc1", framework="langchain")
        _seed_agent(db, agent_name="ag1", framework="autogen")
        r = client.get("/api/v1/ai-agents?framework=autogen",
                       headers={"Authorization": f"Bearer {admin_token}"})
        body = r.json()
        assert body["total"] == 1
        assert body["agents"][0]["framework"] == "autogen"

    def test_filter_by_risk_level(self, client, db, admin_token):
        _seed_agent(db, agent_name="lo", risk_level="low")
        _seed_agent(db, agent_name="hi", risk_level="high")
        r = client.get("/api/v1/ai-agents?risk_level=high",
                       headers={"Authorization": f"Bearer {admin_token}"})
        body = r.json()
        assert body["total"] == 1
        assert body["agents"][0]["risk_level"] == "high"


class TestStats:
    def test_stats_counts(self, client, db, admin_token):
        _seed_agent(db, agent_name="a1", status="active", risk_level="high")
        _seed_agent(db, agent_name="a2", status="dormant", risk_level="low",
                    owner_user=None, owner_team=None)
        _seed_agent(db, agent_name="a3", status="active", risk_level="critical")
        r = client.get("/api/v1/ai-agents/stats",
                       headers={"Authorization": f"Bearer {admin_token}"})
        body = r.json()
        assert body["total"] == 3
        assert body["active"] == 2
        assert body["critical_risk"] == 1
        assert body["no_owner"] == 1


class TestDetail:
    def test_get_existing(self, client, db, admin_token):
        a = _seed_agent(db, agent_name="x")
        r = client.get(f"/api/v1/ai-agents/{a.id}",
                       headers={"Authorization": f"Bearer {admin_token}"})
        assert r.status_code == 200
        assert r.json()["agent_name"] == "x"

    def test_get_404(self, client, admin_token):
        r = client.get("/api/v1/ai-agents/99999",
                       headers={"Authorization": f"Bearer {admin_token}"})
        assert r.status_code == 404


class TestClaim:
    def test_claim_sets_owner_user(self, client, db, admin_token):
        a = _seed_agent(db, agent_name="unowned", owner_user=None)
        r = client.post(f"/api/v1/ai-agents/{a.id}/claim",
                        headers={"Authorization": f"Bearer {admin_token}"})
        assert r.status_code == 200
        assert r.json()["owner_user"] == "admin"
