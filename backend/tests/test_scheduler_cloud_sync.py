"""The scheduler's sync_all_cloud_connections job fans out per connection
and one failure does not block the others."""
import importlib
import os
import sys
from unittest.mock import patch

os.environ.setdefault("ACCOUNTSCAN_MASTER_KEY", "test_master_key_0123456789abcdef01234567")
os.environ.setdefault("ACCOUNTSCAN_JWT_SECRET", "test_jwt_secret_0123456789abcdef0123456")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend import models
from backend.services import crypto


@pytest.fixture
def db():
    # The function under test uses `SessionLocal` from `backend.database`
    # and `models.CloudConnection` from `backend.models`. Prior tests
    # (e.g. migration_025) reload `backend.database` with a file-based URL
    # and drop `backend.models` from sys.modules, so any module-level
    # imports captured at test collection time are stale. We must:
    #   1. Reset the CURRENT `backend.database` engine in sys.modules to
    #      a fresh in-memory StaticPool so the function's
    #      `from backend.database import SessionLocal` resolves to a
    #      sessionmaker bound to the same engine as the test session.
    #   2. Re-import `backend.models` so the current `Base.metadata` has
    #      the table definitions.
    #   3. Re-import `backend.services.scheduler_service` so its module-
    #      level `models` reference points to the fresh models module.
    from sqlalchemy.pool import StaticPool
    os.environ["DATABASE_URL"] = "sqlite:///:memory:"
    fresh_engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    _current_db = sys.modules["backend.database"]
    _current_db.engine = fresh_engine
    _current_db.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=fresh_engine)
    _current_db.DATABASE_URL = "sqlite:///:memory:"
    importlib.import_module("backend.models")
    reloaded_sched = importlib.import_module("backend.services.scheduler_service")
    current_base = _current_db.Base
    current_base.metadata.drop_all(bind=fresh_engine)
    current_base.metadata.create_all(bind=fresh_engine)
    s = _current_db.SessionLocal()
    yield s
    s.close()
    sys.modules["backend.services.scheduler_service"] = reloaded_sched
    current_base.metadata.drop_all(bind=fresh_engine)


def _make_user(s):
    u = models.User(username="alice", email="a@b", password_hash="x",
                    role=models.UserRole.admin)
    s.add(u); s.commit(); s.refresh(u)
    return u


def _make_connection(s, user, name, provider="anthropic"):
    c = models.CloudConnection(
        name=name, provider=provider,
        encrypted_api_key=crypto.encrypt(f"sk-{name}"),
        api_key_fingerprint=crypto.fingerprint(f"sk-{name}") or "0" * 16,
        created_by_user_id=user.id,
    )
    s.add(c); s.commit(); s.refresh(c)
    return c


def test_fans_out_per_connection(db):
    # Use the reloaded module from sys.modules (set by the fixture)
    # so the function's models reference is current.
    sched = sys.modules["backend.services.scheduler_service"]
    user = _make_user(db)
    _make_connection(db, user, "c1")
    _make_connection(db, user, "c2")

    with patch("backend.services.scheduler_service.cloud_discover",
               return_value=[]):
        sched._sync_all_cloud_connections()

    s2 = create_engine("sqlite:///:memory:")
    # Re-query from a fresh session
    from backend.database import SessionLocal
    from backend import models as m
    rows = db.query(m.CloudConnection).all()
    # last_sync_status should be set to success on each
    for c in rows:
        assert c.last_sync_status in ("success", "partial", "failed")


def test_one_failure_does_not_block_others(db):
    from backend.services.cloud_discovery import RawAgent
    sched = sys.modules["backend.services.scheduler_service"]
    user = _make_user(db)
    _make_connection(db, user, "ok-conn")
    _make_connection(db, user, "bad-conn")

    def fake_discover(conn):
        if conn.name == "bad-conn":
            from backend.services.cloud_discovery.base import RetryableError
            raise RetryableError("rate_limited")
        return [RawAgent(provider="anthropic", project_label="P",
                         agent_name=f"{conn.name} / P / k1",
                         api_key_fingerprint="1234567890abcdef")]

    with patch("backend.services.scheduler_service.cloud_discover",
               side_effect=fake_discover):
        sched._sync_all_cloud_connections()  # must not raise

    ok = db.query(models.CloudConnection).filter(
        models.CloudConnection.name == "ok-conn").first()
    bad = db.query(models.CloudConnection).filter(
        models.CloudConnection.name == "bad-conn").first()
    assert ok.last_sync_status in ("success", "partial")
    assert bad.last_sync_status == "failed"
