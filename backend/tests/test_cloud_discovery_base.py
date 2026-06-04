"""Retry-with-backoff, HTTP-status mapping, and dispatch behavior of cloud_discovery.base."""
import os
import sys
from unittest.mock import MagicMock, patch

os.environ.setdefault("ACCOUNTSCAN_MASTER_KEY", "test_master_key_0123456789abcdef01234567")
os.environ.setdefault("ACCOUNTSCAN_JWT_SECRET", "test_jwt_secret_0123456789abcdef0123456")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import httpx
import pytest

from backend.services.cloud_discovery import base
from backend.services.cloud_discovery.base import (
    CloudDiscoveryBase, RetryableError, FatalDiscoveryError,
)
from backend.services import crypto


def _make_response(status_code: int, json_data=None):
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.json.return_value = json_data if json_data is not None else {}
    return resp


def _make_connection():
    return MagicMock(
        id=1, name="test-conn", provider="anthropic",
        encrypted_api_key="ignored", api_key_fingerprint="deadbeef" * 2,
    )


class _FakeConnection:
    def __init__(self, provider="anthropic"):
        self.provider = provider
        # Use a real ciphertext so CloudDiscoveryBase.__init__'s decrypt() succeeds;
        # the dispatch tests patch .run, but __init__ runs before that.
        self.encrypted_api_key = crypto.encrypt("ignored")
        self.api_key_fingerprint = "deadbeef" * 2  # 16 chars
        self.id = 1
        self.name = "test-conn"


def test_dispatch_anthropic_returns_raw_agents(monkeypatch):
    from backend.services.cloud_discovery import discover
    fake = _FakeConnection(provider="anthropic")
    monkeypatch.setattr(
        "backend.services.cloud_discovery.anthropic.AnthropicDiscovery.run",
        lambda self: [base.RawAgent(provider="anthropic", project_label="p",
                                     agent_name="test-conn / p / 12345678",
                                     api_key_fingerprint="1234567890abcdef")],
    )
    out = discover(fake)
    assert len(out) == 1
    assert out[0].provider == "anthropic"


def test_dispatch_openai_returns_raw_agents(monkeypatch):
    from backend.services.cloud_discovery import discover
    fake = _FakeConnection(provider="openai")
    monkeypatch.setattr(
        "backend.services.cloud_discovery.openai.OpenAIDiscovery.run",
        lambda self: [base.RawAgent(provider="openai", project_label="proj",
                                     agent_name="test-conn / proj / abcdef12",
                                     api_key_fingerprint="abcdef1234567890")],
    )
    out = discover(fake)
    assert len(out) == 1
    assert out[0].provider == "openai"


def test_dispatch_unknown_provider_raises():
    from backend.services.cloud_discovery import discover
    fake = _FakeConnection(provider="bogus")
    with pytest.raises(ValueError, match="Unsupported cloud provider"):
        discover(fake)


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
    assert delays == [1.0, 2.0]


def test_retry_with_backoff_gives_up_after_max_attempts(monkeypatch):
    monkeypatch.setattr(base.time, "sleep", lambda s: None)
    with pytest.raises(RetryableError):
        base._retry_with_backoff(lambda: (_ for _ in ()).throw(RetryableError("nope")),
                                  max_attempts=3)


def test_retry_with_backoff_propagates_fatal_immediately(monkeypatch):
    calls = {"n": 0}

    def boom():
        calls["n"] += 1
        raise FatalDiscoveryError("auth_failed: 401")

    monkeypatch.setattr(base.time, "sleep", lambda s: None)
    with pytest.raises(FatalDiscoveryError):
        base._retry_with_backoff(boom, max_attempts=5)
    assert calls["n"] == 1  # no retries on Fatal


def test_http_get_returns_json_on_2xx(monkeypatch):
    monkeypatch.setattr(base.time, "sleep", lambda s: None)
    with patch("backend.services.cloud_discovery.base.httpx.get",
               return_value=_make_response(200, {"ok": True})):
        sub = CloudDiscoveryBase.__new__(CloudDiscoveryBase)
        sub.PROVIDER_NAME = "anthropic"
        sub.BASE_URL = "https://example.test"
        sub._api_key = "k"
        sub._auth_headers = lambda: {}
        out = sub._http_get("/v1/x")
    assert out == {"ok": True}


def test_http_get_401_raises_fatal(monkeypatch):
    monkeypatch.setattr(base.time, "sleep", lambda s: None)
    with patch("backend.services.cloud_discovery.base.httpx.get",
               return_value=_make_response(401)):
        sub = CloudDiscoveryBase.__new__(CloudDiscoveryBase)
        sub.PROVIDER_NAME = "anthropic"
        sub.BASE_URL = "https://example.test"
        sub._api_key = "k"
        sub._auth_headers = lambda: {}
        with pytest.raises(FatalDiscoveryError, match="auth_failed: 401"):
            sub._http_get("/v1/x")


def test_http_get_403_raises_fatal(monkeypatch):
    monkeypatch.setattr(base.time, "sleep", lambda s: None)
    with patch("backend.services.cloud_discovery.base.httpx.get",
               return_value=_make_response(403)):
        sub = CloudDiscoveryBase.__new__(CloudDiscoveryBase)
        sub.PROVIDER_NAME = "anthropic"
        sub.BASE_URL = "https://example.test"
        sub._api_key = "k"
        sub._auth_headers = lambda: {}
        with pytest.raises(FatalDiscoveryError, match="auth_failed: 403"):
            sub._http_get("/v1/x")


def test_http_get_429_raises_retryable(monkeypatch):
    monkeypatch.setattr(base.time, "sleep", lambda s: None)
    with patch("backend.services.cloud_discovery.base.httpx.get",
               return_value=_make_response(429)):
        sub = CloudDiscoveryBase.__new__(CloudDiscoveryBase)
        sub.PROVIDER_NAME = "anthropic"
        sub.BASE_URL = "https://example.test"
        sub._api_key = "k"
        sub._auth_headers = lambda: {}
        with pytest.raises(RetryableError, match="rate_limited"):
            sub._http_get("/v1/x")


def test_http_get_5xx_raises_retryable(monkeypatch):
    monkeypatch.setattr(base.time, "sleep", lambda s: None)
    with patch("backend.services.cloud_discovery.base.httpx.get",
               return_value=_make_response(503)):
        sub = CloudDiscoveryBase.__new__(CloudDiscoveryBase)
        sub.PROVIDER_NAME = "anthropic"
        sub.BASE_URL = "https://example.test"
        sub._api_key = "k"
        sub._auth_headers = lambda: {}
        with pytest.raises(RetryableError, match="server_error: 503"):
            sub._http_get("/v1/x")


def test_http_get_other_4xx_raises_fatal(monkeypatch):
    monkeypatch.setattr(base.time, "sleep", lambda s: None)
    with patch("backend.services.cloud_discovery.base.httpx.get",
               return_value=_make_response(404)):
        sub = CloudDiscoveryBase.__new__(CloudDiscoveryBase)
        sub.PROVIDER_NAME = "anthropic"
        sub.BASE_URL = "https://example.test"
        sub._api_key = "k"
        sub._auth_headers = lambda: {}
        with pytest.raises(FatalDiscoveryError, match="http_error: 404"):
            sub._http_get("/v1/x")


def test_http_get_timeout_raises_retryable(monkeypatch):
    monkeypatch.setattr(base.time, "sleep", lambda s: None)
    with patch("backend.services.cloud_discovery.base.httpx.get",
               side_effect=httpx.TimeoutException("read timeout")):
        sub = CloudDiscoveryBase.__new__(CloudDiscoveryBase)
        sub.PROVIDER_NAME = "anthropic"
        sub.BASE_URL = "https://example.test"
        sub._api_key = "k"
        sub._auth_headers = lambda: {}
        with pytest.raises(RetryableError, match="timeout"):
            sub._http_get("/v1/x")


def test_http_get_network_error_raises_retryable(monkeypatch):
    monkeypatch.setattr(base.time, "sleep", lambda s: None)
    with patch("backend.services.cloud_discovery.base.httpx.get",
               side_effect=httpx.ConnectError("connection refused")):
        sub = CloudDiscoveryBase.__new__(CloudDiscoveryBase)
        sub.PROVIDER_NAME = "anthropic"
        sub.BASE_URL = "https://example.test"
        sub._api_key = "k"
        sub._auth_headers = lambda: {}
        with pytest.raises(RetryableError, match="network"):
            sub._http_get("/v1/x")
