"""Retry-with-backoff, timeout, and dispatch behavior of cloud_discovery.base."""
import os
import sys
from datetime import datetime
from unittest.mock import MagicMock

os.environ.setdefault("ACCOUNTSCAN_MASTER_KEY", "test_master_key_0123456789abcdef01234567")
os.environ.setdefault("ACCOUNTSCAN_JWT_SECRET", "test_jwt_secret_0123456789abcdef0123456")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import pytest

from backend.services.cloud_discovery import base
from backend.services.cloud_discovery.base import (
    CloudDiscoveryBase, RetryableError, FatalDiscoveryError,
)


def test_base_module_imports():
    assert base is not None


def test_retry_with_backoff_eventually_succeeds(monkeypatch):
    calls = {"n": 0}

    def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise RetryableError("transient")
        return "ok"

    delays = []
    monkeypatch.setattr(base.time, "sleep", lambda s: delays.append(s))
    result = base._retry_with_backoff(flaky, max_attempts=4)
    assert result == "ok"
    assert calls["n"] == 3
    assert delays == [1, 2, 4]  # 1s, 2s, 4s


def test_retry_with_backoff_gives_up_after_max_attempts(monkeypatch):
    monkeypatch.setattr(base.time, "sleep", lambda s: None)
    with pytest.raises(RetryableError):
        base._retry_with_backoff(lambda: (_ for _ in ()).throw(RetryableError("nope")),
                                  max_attempts=3)
