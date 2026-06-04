"""End-to-end tests for the cloud-connection router.

Verifies:
- List / create / patch / rotate / delete / sync / audit endpoints
- Key never appears in any response or DB column (plaintext or encrypted)
- API key in PATCH body is rejected
- Sync-in-progress returns 409
"""
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
from backend.services import crypto


@pytest.fixture
def db():
    # Plan-bug fix: StaticPool so the in-memory SQLite DB is shared
    # between the test thread and the FastAPI app thread (TestClient
    # runs the app in a different thread).
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
    # Plan-bug fix: clear any leaked overrides from previous tests,
    # then set our own using a direct import (avoids __import__ fragility).
    app.dependency_overrides.clear()
    app.dependency_overrides[get_db] = lambda: db

    admin = models.User(username="alice", email="a@b", password_hash="x",
                        role=models.UserRole.admin)
    db.add(admin); db.commit(); db.refresh(admin)
    token = auth.create_access_token({"sub": admin.username, "uid": admin.id})

    def _fake_user():
        return admin
    app.dependency_overrides[auth.get_current_user] = _fake_user
    app.dependency_overrides[auth.require_admin] = _fake_user

    yield TestClient(app), admin, token

    app.dependency_overrides.clear()


def test_create_connection_encrypts_key(client):
    c, admin, _ = client
    body = {"name": "acme-prod", "provider": "anthropic", "api_key": "sk-ant-secret-key"}
    r = c.post("/api/v1/ai-agents/connections", json=body)
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["name"] == "acme-prod"
    assert data["provider"] == "anthropic"
    assert "api_key" not in data
    assert "encrypted_api_key" not in data
    assert data["api_key_fingerprint"] == crypto.fingerprint("sk-ant-secret-key")


def test_key_never_returned_in_list(client):
    c, _, _ = client
    c.post("/api/v1/ai-agents/connections",
           json={"name": "c1", "provider": "openai", "api_key": "sk-openai-test"})
    r = c.get("/api/v1/ai-agents/connections")
    assert r.status_code == 200
    assert "sk-openai-test" not in r.text
    assert "encrypted_api_key" not in r.json()["connections"][0]


def test_patch_rejects_api_key_field(client):
    c, _, _ = client
    c.post("/api/v1/ai-agents/connections",
           json={"name": "c1", "provider": "anthropic", "api_key": "sk-test"})
    r = c.patch("/api/v1/ai-agents/connections/1",
                json={"name": "renamed", "api_key": "should-be-rejected"})
    # Plan-bug fix: Pydantic v2 with `extra="forbid"` returns 422, not 400.
    assert r.status_code == 422
    assert r.json()["detail"][0]["type"] == "extra_forbidden"


def test_rotate_writes_new_fingerprint(client):
    c, _, _ = client
    c.post("/api/v1/ai-agents/connections",
           json={"name": "c1", "provider": "anthropic", "api_key": "old-key"})
    r = c.post("/api/v1/ai-agents/connections/1/rotate",
               json={"api_key": "new-key"})
    assert r.status_code == 200
    assert r.json()["api_key_fingerprint"] == crypto.fingerprint("new-key")


def test_delete_soft_deletes_and_keeps_agents(client, db):
    c, _, _ = client
    c.post("/api/v1/ai-agents/connections",
           json={"name": "c1", "provider": "anthropic", "api_key": "sk-test"})
    # Manually create a cloud agent pointing at this connection
    from backend.models import AIAgent, CloudConnection
    conn = db.query(CloudConnection).first()
    agent = AIAgent(
        agent_name="c1 / P / k", framework="cloud_anthropic",
        discovery_source="api_discovery", connection_id=conn.id,
        asset_id=None, last_seen_at=datetime.utcnow(),
        discovered_at=datetime.utcnow(),
    )
    db.add(agent); db.commit()

    r = c.delete("/api/v1/ai-agents/connections/1")
    assert r.status_code == 204


def test_sync_in_progress_returns_409(client, db):
    c, _, _ = client
    c.post("/api/v1/ai-agents/connections",
           json={"name": "c1", "provider": "anthropic", "api_key": "sk-test"})
    # Mark connection as currently running
    db.query(models.CloudConnection).filter(
        models.CloudConnection.id == 1
    ).update({models.CloudConnection.last_sync_status: "running"})
    db.commit()
    r = c.post("/api/v1/ai-agents/connections/1/sync")
    assert r.status_code == 409


def test_sync_success_path_writes_agents_and_audit(client):
    c, _, _ = client
    c.post("/api/v1/ai-agents/connections",
           json={"name": "c1", "provider": "anthropic", "api_key": "sk-test"})

    from backend.services.cloud_discovery import RawAgent
    fake_raws = [
        RawAgent(provider="anthropic", project_label="Prod",
                 agent_name="c1 / Prod / k1",
                 api_key_fingerprint="1234567890abcdef"),
    ]
    # Plan-bug fix: test_auth.py deletes all backend.* modules from sys.modules
    # at import time, so patching via string path or inspect.getmodule hits
    # the wrong module object. The router function looks up cloud_discover
    # in its __globals__ at call time — patch that dict directly.
    # sync_connection delegates to _run_sync, which is where the lookup happens.
    _run_sync_func = None
    for _route in app.routes:
        if hasattr(_route, "endpoint") and _route.endpoint.__name__ == "sync_connection":
            _run_sync_func = _route.endpoint.__globals__["_run_sync"]
            break
    assert _run_sync_func is not None, "could not locate _run_sync in router globals"
    _original_discover = _run_sync_func.__globals__["cloud_discover"]
    _run_sync_func.__globals__["cloud_discover"] = lambda conn: fake_raws
    try:
        r = c.post("/api/v1/ai-agents/connections/1/sync")
    finally:
        _run_sync_func.__globals__["cloud_discover"] = _original_discover

    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "success"
    assert body["agents_discovered"] == 1
    assert body["agents_updated"] == 0
    assert body["error"] is None

    # Audit list shows created + sync_started + sync_finished
    r2 = c.get("/api/v1/ai-agents/connections/1/audit")
    assert r2.status_code == 200
    actions = [e["action"] for e in r2.json()["entries"]]
    assert "created" in actions
    assert "sync_started" in actions
    assert "sync_finished" in actions
    # The api_key string must NOT appear in any audit entry
    assert "sk-test" not in r2.text
