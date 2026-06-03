"""Tests for AI Agent API key fingerprinting."""
import os
import sys

os.environ.setdefault("ACCOUNTSCAN_MASTER_KEY", "test_master_key_0123456789abcdef01234567")
os.environ.setdefault("ACCOUNTSCAN_JWT_SECRET", "test_jwt_secret_0123456789abcdef0123456")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from backend.services.ai_agent_scanner import fingerprint_api_key


class TestFingerprint:
    def test_returns_16_char_prefix(self):
        fp = fingerprint_api_key("sk-1234567890abcdef")
        assert fp is not None
        assert fp.startswith("sha256:")
        # "sha256:" (7 chars) + 16 hex chars of digest[:16] = 23 total
        assert len(fp) == 23
        assert len(fp.removeprefix("sha256:")) == 16

    def test_same_key_same_fingerprint(self):
        a = fingerprint_api_key("sk-1234567890abcdef")
        b = fingerprint_api_key("sk-1234567890abcdef")
        assert a == b

    def test_different_keys_different_fingerprints(self):
        a = fingerprint_api_key("sk-1234567890abcdef")
        b = fingerprint_api_key("sk-9876543210fedcba")
        assert a != b

    def test_empty_string_returns_none(self):
        assert fingerprint_api_key("") is None

    def test_none_returns_none(self):
        assert fingerprint_api_key(None) is None

    def test_fingerprint_does_not_contain_original_key(self):
        """The fingerprint must never leak any portion of the original key."""
        key = "sk-supersecretvalue"
        fp = fingerprint_api_key(key)
        assert "supersecret" not in (fp or "")
        assert "sk-" not in (fp or "")
