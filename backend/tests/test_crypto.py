"""Re-export + fingerprint helper for backend/encryption."""
import hashlib
import os
import sys

os.environ.setdefault("ACCOUNTSCAN_MASTER_KEY", "test_master_key_0123456789abcdef01234567")
os.environ.setdefault("ACCOUNTSCAN_JWT_SECRET", "test_jwt_secret_0123456789abcdef0123456")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from backend.services.crypto import encrypt, decrypt, fingerprint


def test_encrypt_decrypt_round_trip():
    pt = "sk-ant-admin-1234567890"
    ct = encrypt(pt)
    assert ct != pt
    assert decrypt(ct) == pt


def test_fingerprint_is_sha256_prefix():
    pt = "sk-ant-admin-1234567890"
    fp = fingerprint(pt)
    expected = hashlib.sha256(pt.encode()).hexdigest()[:16]
    assert fp == expected
    assert len(fp) == 16
    # Full key must not appear in the fingerprint
    assert "1234567890" not in fp


def test_decrypt_rejects_tampered_ciphertext():
    ct = encrypt("secret")
    tampered = ct[:-2] + ("AA" if ct[-2:] != "AA" else "BB")
    try:
        decrypt(tampered)
    except Exception:
        return
    raise AssertionError("decrypt should raise on tampered ciphertext")
