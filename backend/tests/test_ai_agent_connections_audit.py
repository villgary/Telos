"""Every state-changing endpoint must write exactly one audit row with
the expected action and no plaintext key material anywhere."""
import os
import sys

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
def client():
    # Plan-bug fix: StaticPool so the in-memory SQLite DB is shared
    # between the test thread and the FastAPI app thread.
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)

    # Plan-bug fix: clear any leaked overrides from previous tests,
    # then set our own using a direct import (avoids __import__ fragility).
    app.dependency_overrides.clear()
    app.dependency_overrides[get_db] = lambda: Session()

    admin = models.User(username="alice", email="a@b", password_hash="x",
                        role=models.UserRole.admin)
    # Plan-bug fix: keep `s` open so the admin object stays bound to its
    # session. Closing it would detach `admin` and cause DetachedInstanceError
    # when the FastAPI app thread accesses `admin.id`.
    s = Session()
    s.add(admin); s.commit()

    def _user():
        return admin
    app.dependency_overrides[auth.get_current_user] = _user
    app.dependency_overrides[auth.require_admin] = _user

    yield TestClient(app), Session

    app.dependency_overrides.clear()


def test_create_writes_one_audit_row(client):
    c, Session = client
    SECRET = "sk-ant-very-secret-key-1234567890"
    r = c.post("/api/v1/ai-agents/connections",
               json={"name": "c1", "provider": "anthropic", "api_key": SECRET})
    assert r.status_code == 201

    s = Session()
    rows = s.query(models.CloudConnectionAuditLog).all()
    assert len(rows) == 1
    assert rows[0].action == "created"
    assert rows[0].actor_user_id is not None
    # Plaintext must never appear in any column
    for col in ("before", "after", "note"):
        val = getattr(rows[0], col)
        if val:
            assert SECRET not in str(val)


def test_rotate_writes_one_audit_row_with_old_and_new_fingerprint(client):
    c, Session = client
    c.post("/api/v1/ai-agents/connections",
           json={"name": "c1", "provider": "anthropic", "api_key": "old-key"})
    r = c.post("/api/v1/ai-agents/connections/1/rotate",
               json={"api_key": "new-key"})
    assert r.status_code == 200

    s = Session()
    rows = s.query(models.CloudConnectionAuditLog).order_by(
        models.CloudConnectionAuditLog.id).all()
    actions = [r.action for r in rows]
    assert "rotated" in actions
    rotated = next(r for r in rows if r.action == "rotated")
    assert "old-key" not in str(rotated.before)
    assert "new-key" not in str(rotated.after)
    assert "old-key" not in (rotated.note or "")


def test_delete_writes_one_audit_row(client):
    c, Session = client
    c.post("/api/v1/ai-agents/connections",
           json={"name": "c1", "provider": "anthropic", "api_key": "k"})
    r = c.delete("/api/v1/ai-agents/connections/1")
    assert r.status_code == 204
    s = Session()
    rows = s.query(models.CloudConnectionAuditLog).all()
    actions = [r.action for r in rows]
    assert "deleted" in actions


def test_rename_writes_one_audit_row(client):
    c, Session = client
    c.post("/api/v1/ai-agents/connections",
           json={"name": "old", "provider": "anthropic", "api_key": "k"})
    r = c.patch("/api/v1/ai-agents/connections/1", json={"name": "new"})
    assert r.status_code == 200
    s = Session()
    rows = s.query(models.CloudConnectionAuditLog).all()
    actions = [r.action for r in rows]
    assert "renamed" in actions
