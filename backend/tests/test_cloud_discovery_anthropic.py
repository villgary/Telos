"""Anthropic Admin API discovery — mocked HTTP."""
import os
import sys
from unittest.mock import patch, MagicMock

os.environ.setdefault("ACCOUNTSCAN_MASTER_KEY", "test_master_key_0123456789abcdef01234567")
os.environ.setdefault("ACCOUNTSCAN_JWT_SECRET", "test_jwt_secret_0123456789abcdef0123456")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import pytest

from backend.services.cloud_discovery.anthropic import AnthropicDiscovery
from backend.services.cloud_discovery.base import FatalDiscoveryError, RetryableError
from backend.services import crypto


def _make_connection(name="acme-prod", provider="anthropic"):
    # NOTE: `name` is reserved by MagicMock for the repr, so we set it as a
    # real attribute after construction so `connection.name` is a string.
    m = MagicMock(
        id=1, provider=provider,
        encrypted_api_key=crypto.encrypt("sk-ant-admin-test"),
        api_key_fingerprint=crypto.fingerprint("sk-ant-admin-test"),
    )
    m.name = name
    return m


def test_happy_path_produces_one_raw_agent_per_project_key():
    conn = _make_connection()
    # 2 projects: proj-1 has 2 keys, proj-2 has 1 key → 3 agents
    responses = {
        "/v1/organizations": {"data": [{"id": "org-1", "name": "Acme"}], "has_more": False},
        "/v1/organizations/org-1/projects": {
            "data": [{"id": "proj-1", "name": "Prod"}, {"id": "proj-2", "name": "Staging"}],
            "has_more": False,
        },
        "/v1/organizations/org-1/projects/proj-1/api_keys": {
            "data": [{"id": "key-1", "name": "k1"}, {"id": "key-2", "name": "k2"}],
            "has_more": False,
        },
        "/v1/organizations/org-1/projects/proj-2/api_keys": {
            "data": [{"id": "key-3", "name": "k3"}],
            "has_more": False,
        },
    }

    def fake_get(self, path, params=None):
        if path not in responses:
            raise AssertionError(f"unexpected path: {path}")
        return responses[path]

    with patch.object(AnthropicDiscovery, "_http_get", new=fake_get):
        agents = AnthropicDiscovery(conn).run()

    assert len(agents) == 3  # 2 in prod + 1 in staging
    assert all(a.provider == "anthropic" for a in agents)
    assert {a.project_label for a in agents} == {"Prod", "Staging"}
    assert {a.agent_name for a in agents} == {
        "acme-prod / Prod / k1",
        "acme-prod / Prod / k2",
        "acme-prod / Staging / k3",
    }


def test_401_raises_fatal_discovery_error():
    conn = _make_connection()
    with patch.object(AnthropicDiscovery, "_http_get",
                      side_effect=FatalDiscoveryError("auth_failed: 401")):
        with pytest.raises(FatalDiscoveryError):
            AnthropicDiscovery(conn).run()


def test_429_retries_then_raises_retryable_error():
    conn = _make_connection()
    with patch.object(AnthropicDiscovery, "_http_get",
                      side_effect=RetryableError("rate_limited")):
        with patch("backend.services.cloud_discovery.base.time.sleep", lambda s: None):
            with pytest.raises(RetryableError):
                AnthropicDiscovery(conn).run()
