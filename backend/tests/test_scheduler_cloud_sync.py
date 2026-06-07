"""The scheduler's sync_all_cloud_connections job fans out per connection
and one failure does not block the others."""
import os
import sys

os.environ.setdefault("ACCOUNTSCAN_MASTER_KEY", "test_master_key_0123456789abcdef01234567")
os.environ.setdefault("ACCOUNTSCAN_JWT_SECRET", "test_jwt_secret_0123456789abcdef0123456")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from unittest.mock import patch

from backend import models
from backend.database import Base
from backend.services import crypto


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestSession = sessionmaker(bind=engine)
    s = TestSession()
    yield s
    s.close()


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
    from backend.services import scheduler_service as sched

    user = _make_user(db)
    _make_connection(db, user, "c1")
    _make_connection(db, user, "c2")

    # The function creates a session via SessionLocal() and closes it
    # in `finally`; bind to the same in-memory engine so the fixture's
    # session still sees writes.
    SchedSession = sessionmaker(bind=db.get_bind())
    with patch("backend.services.cloud_discovery.sync.cloud_discover", return_value=[]), \
         patch.object(sched, "SessionLocal", SchedSession):
        sched._sync_all_cloud_connections()

    for c in db.query(models.CloudConnection).all():
        assert c.last_sync_status in ("success", "partial", "failed")


def test_one_failure_does_not_block_others(db):
    from backend.services import scheduler_service as sched
    from backend.services.cloud_discovery import RawAgent
    from backend.services.cloud_discovery.base import RetryableError

    user = _make_user(db)
    _make_connection(db, user, "ok-conn")
    _make_connection(db, user, "bad-conn")

    def fake_discover(conn):
        if conn.name == "bad-conn":
            raise RetryableError("rate_limited")
        return [RawAgent(provider="anthropic", project_label="P",
                         agent_name=f"{conn.name} / P / k1",
                         api_key_fingerprint="1234567890abcdef")]

    SchedSession = sessionmaker(bind=db.get_bind())
    with patch("backend.services.cloud_discovery.sync.cloud_discover",
               side_effect=fake_discover), \
         patch.object(sched, "SessionLocal", SchedSession):
        sched._sync_all_cloud_connections()  # must not raise

    ok = db.query(models.CloudConnection).filter(
        models.CloudConnection.name == "ok-conn").first()
    bad = db.query(models.CloudConnection).filter(
        models.CloudConnection.name == "bad-conn").first()
    assert ok.last_sync_status in ("success", "partial")
    assert bad.last_sync_status == "failed"
