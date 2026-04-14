"""
Tests for backend.encryption (AES-256-GCM encrypt/decrypt).
"""

import pytest
import base64
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

os.environ.setdefault("ACCOUNTSCAN_MASTER_KEY", "test_master_key_0123456789abcdef01234567")
os.environ.setdefault("ACCOUNTSCAN_JWT_SECRET", "test_jwt_secret_0123456789abcdef0123456")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("JWT_EXPIRE_MINUTES", "15")
os.environ.setdefault("REFRESH_TOKEN_EXPIRE_DAYS", "7")

for mod in list(sys.modules):
    if mod.startswith("backend"):
        del sys.modules[mod]

from backend import encryption


class TestEncryptDecrypt:
    """加密/解密 round-trip 测试"""

    def test_encrypt_decrypt_roundtrip(self):
        plaintext = "Hello, World! 你好世界！"
        ciphertext = encryption.encrypt(plaintext)
        assert ciphertext != plaintext
        decrypted = encryption.decrypt(ciphertext)
        assert decrypted == plaintext

    def test_encrypt_produces_base64(self):
        ct = encryption.encrypt("secret data")
        # 应该是合法 base64
        decoded = base64.b64decode(ct)
        assert len(decoded) > 16  # nonce(12) + 密文 + tag(16)

    def test_encrypt_produces_unique_ciphertext(self):
        """相同明文每次加密产生不同密文（随机 nonce）"""
        p1 = encryption.encrypt("same text")
        p2 = encryption.encrypt("same text")
        assert p1 != p2

    def test_decrypt_raises_on_tampered_ciphertext(self):
        ct = encryption.encrypt("sensitive")
        decoded = base64.b64decode(ct)
        # 翻转最后一个字节（篡改密文）
        tampered = bytearray(decoded)
        tampered[-1] ^= 0xFF
        tampered_b64 = base64.b64encode(bytes(tampered)).decode()
        with pytest.raises(Exception):  # cryptography.exceptions.InvalidTag
            encryption.decrypt(tampered_b64)

    def test_decrypt_raises_on_wrong_key(self):
        """用不同密钥无法解密"""
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM

        # 手动生成一个用不同 key 加密的密文
        import secrets

        key = secrets.token_bytes(32)
        aesgcm = AESGCM(key)
        nonce = secrets.token_bytes(12)
        ct = aesgcm.encrypt(nonce, b"test", None)
        combined_b64 = base64.b64encode(nonce + ct).decode()

        with pytest.raises(Exception):  # InvalidTag
            encryption.decrypt(combined_b64)

    def test_empty_string(self):
        assert encryption.decrypt(encryption.encrypt("")) == ""

    def test_unicode_string(self):
        plaintext = "密码🔐密码123!@#"
        assert encryption.decrypt(encryption.encrypt(plaintext)) == plaintext

    def test_very_long_string(self):
        plaintext = "A" * 100_000
        assert encryption.decrypt(encryption.encrypt(plaintext)) == plaintext
