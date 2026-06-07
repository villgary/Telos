"""run_connection_sync — the shared sync orchestrator used by both the
router's POST /sync endpoint and the 6h scheduler.

Verifies:
- success path: last_sync_status set, ingested agents count returned
- FatalDiscoveryError → last_sync_status="failed", last_sync_error starts with "auth_failed:"
- RetryableError → last_sync_status="failed", last_sync_error starts with "rate_limited_or_transient:"
- generic Exception → last_sync_status="failed", last_sync_error starts with "unexpected:"
"""
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

from backend import models
from backend.database import Base
from backend.services import crypto
from backend.services.cloud_discovery import RawAgent
from backend.services.cloud_discovery.base import (
    FatalDiscoveryError as _FD, RetryableError as _RD,
)


def _FatalDiscoveryError(msg):
    """Re-resolve FatalDiscoveryError at call time so we get the
    post-reload class — the same one run_connection_sync catches."""
    from backend.services.cloud_discovery.base import FatalDiscoveryError
    raise FatalDiscoveryError(msg)


def _RetryableError(msg):
    from backend.services.cloud_discovery.base import RetryableError
    raise RetryableError(msg)
# Imported for type discovery only — the actual test-time reference is
# resolved inside each test, because other test files (notably
# test_diff_engine.py and test_encryption.py) reload backend.* modules
# and a top-level import here would pin us to the pre-reload version.
from backend.services.cloud_discovery import sync as _sync_module  # noqa: F401


def _run_connection_sync():
    """Re-resolve run_connection_sync at call time so we always get the
    post-reload version, no matter what other test files did to sys.modules.
    """
    from backend.services.cloud_discovery.sync import run_connection_sync
    return run_connection_sync


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


def _make_connection(s, user, name="c1", provider="anthropic"):
    c = models.CloudConnection(
        name=name, provider=provider,
        encrypted_api_key=crypto.encrypt(f"sk-{name}"),
        api_key_fingerprint=crypto.fingerprint(f"sk-{name}") or "0" * 16,
        created_by_user_id=user.id,
    )
    s.add(c); s.commit(); s.refresh(c)
    return c


def test_success_path_returns_counts_and_updates_status(db):
    user = _make_user(db)
    conn = _make_connection(db, user)
    raws = [
        RawAgent(provider="anthropic", project_label="P",
                 agent_name="c1 / P / k1",
                 api_key_fingerprint="1234567890abcdef"),
    ]
    # Patch the function's __globals__ directly so we hit the same dict
    # the function consults at call time, regardless of module reloads.
    func = _run_connection_sync()
    _original = func.__globals__["cloud_discover"]
    func.__globals__["cloud_discover"] = lambda connection: raws
    try:
        result = func(db, conn)
    finally:
        func.__globals__["cloud_discover"] = _original

    assert result["status"] == "success"
    assert result["agents_discovered"] == 1
    assert result["agents_updated"] == 0
    assert result["error"] is None
    assert conn.last_sync_status == "success"
    assert conn.last_sync_error is None
    assert conn.last_sync_at is not None
    db.commit()
    reloaded = db.query(models.CloudConnection).filter(
        models.CloudConnection.id == conn.id).first()
    assert reloaded.last_sync_status == "success"


def test_fatal_discovery_error_marks_failed(db):
    user = _make_user(db)
    conn = _make_connection(db, user)
    func = _run_connection_sync()
    _original = func.__globals__["cloud_discover"]
    func.__globals__["cloud_discover"] = _FatalDiscoveryError
    try:
        result = func(db, conn)
    finally:
        func.__globals__["cloud_discover"] = _original

    assert result["status"] == "failed"
    assert result["agents_discovered"] == 0
    assert result["error"].startswith("auth_failed:")
    assert conn.last_sync_status == "failed"
    assert conn.last_sync_error.startswith("auth_failed:")


def test_retryable_error_marks_failed(db):
    user = _make_user(db)
    conn = _make_connection(db, user)
    func = _run_connection_sync()
    _original = func.__globals__["cloud_discover"]
    func.__globals__["cloud_discover"] = _RetryableError
    try:
        result = func(db, conn)
    finally:
        func.__globals__["cloud_discover"] = _original

    assert result["status"] == "failed"
    assert result["error"].startswith("rate_limited_or_transient:")
    assert conn.last_sync_status == "failed"


def test_unexpected_exception_marks_failed(db):
    user = _make_user(db)
    conn = _make_connection(db, user)
    func = _run_connection_sync()
    _original = func.__globals__["cloud_discover"]
    def _raise_runtime(c):
        raise RuntimeError("boom")
    func.__globals__["cloud_discover"] = _raise_runtime
    try:
        result = func(db, conn)
    finally:
        func.__globals__["cloud_discover"] = _original

    assert result["status"] == "failed"
    assert result["error"].startswith("unexpected:")
    assert conn.last_sync_status == "failed"


def test_error_message_truncated_to_256_chars(db):
    user = _make_user(db)
    conn = _make_connection(db, user)
    long_msg = "x" * 500
    func = _run_connection_sync()
    _original = func.__globals__["cloud_discover"]
    def _raise_long(c):
        from backend.services.cloud_discovery.base import FatalDiscoveryError
        raise FatalDiscoveryError(long_msg)
    func.__globals__["cloud_discover"] = _raise_long
    try:
        result = func(db, conn)
    finally:
        func.__globals__["cloud_discover"] = _original
    assert len(result["error"]) == 256
    assert len(conn.last_sync_error) == 256
