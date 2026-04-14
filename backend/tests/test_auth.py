"""
Tests for backend.auth (password hashing, JWT, validation).
"""

import pytest
import sys
import os
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

os.environ.setdefault("ACCOUNTSCAN_MASTER_KEY", "test_master_key_0123456789abcdef01234567")
os.environ.setdefault("ACCOUNTSCAN_JWT_SECRET", "test_jwt_secret_0123456789abcdef0123456")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("JWT_EXPIRE_MINUTES", "15")
os.environ.setdefault("REFRESH_TOKEN_EXPIRE_DAYS", "7")

for mod in list(sys.modules):
    if mod.startswith("backend"):
        del sys.modules[mod]

from backend import auth


class TestPasswordHashing:
    """bcrypt 密码哈希测试"""

    def test_hash_password_produces_bcrypt_hash(self):
        h = auth.hash_password("Test123!")
        assert h.startswith("$2")  # bcrypt 格式前缀
        assert len(h) == 60

    def test_hash_password_different_each_time(self):
        """bcrypt 每次哈希不同（随机 salt）"""
        h1 = auth.hash_password("SamePass!")
        h2 = auth.hash_password("SamePass!")
        assert h1 != h2

    def test_verify_password_correct(self):
        pw = "MySecurePass123!"
        h = auth.hash_password(pw)
        assert auth.verify_password(pw, h) is True

    def test_verify_password_incorrect(self):
        h = auth.hash_password("CorrectPass!")
        assert auth.verify_password("WrongPass!", h) is False


class TestJWTTokens:
    """JWT 访问令牌测试"""

    def test_create_access_token(self):
        token = auth.create_access_token({"sub": "testuser"})
        assert isinstance(token, str)
        assert len(token) > 0

    def test_access_token_can_be_decoded(self):
        token = auth.create_access_token({"sub": "alice"})
        payload = auth.jwt.decode(
            token, auth._JWT_SECRET, algorithms=[auth.ALGORITHM]
        )
        assert payload["sub"] == "alice"
        assert "exp" in payload

    def test_access_token_custom_expiry(self):
        delta = timedelta(minutes=60)
        token = auth.create_access_token({"sub": "bob"}, expires_delta=delta)
        payload = auth.jwt.decode(
            token, auth._JWT_SECRET, algorithms=[auth.ALGORITHM]
        )
        # exp 应在约 60 分钟后
        exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        now = datetime.now(timezone.utc)
        diff = exp - now
        assert 59 * 60 <= diff.total_seconds() <= 61 * 60

    def test_token_with_different_secret_fails(self):
        token = auth.create_access_token({"sub": "charlie"})
        with pytest.raises(Exception):
            auth.jwt.decode(token, "wrong_secret_key_xxxx", algorithms=[auth.ALGORITHM])


class TestPasswordStrength:
    """密码强度校验测试"""

    def _assert_valid(self, password: str):
        # 不抛异常即为通过
        auth.validate_password_strength(password)

    def _assert_invalid(self, password: str):
        with pytest.raises(ValueError) as exc_info:
            auth.validate_password_strength(password)
        assert "密码不符合安全要求" in str(exc_info.value)

    def test_valid_password(self):
        self._assert_valid("GoodPass1!")  # 8+ chars, upper, lower, digit, special

    def test_too_short(self):
        self._assert_invalid("Ab1!")  # 少于 8 字符

    def test_missing_uppercase(self):
        self._assert_invalid("lowercase1!")

    def test_missing_lowercase(self):
        self._assert_invalid("UPPERCASE1!")

    def test_missing_digit(self):
        self._assert_invalid("NoDigits!@#")

    def test_missing_special_char(self):
        self._assert_invalid("NoSpecial123")

    def test_boundary_8_chars(self):
        self._assert_valid("Pass123!")  # 刚好 8 字符

    def test_chinese_characters_in_password(self):
        # 密码含中文也是合法的
        self._assert_valid("密码Pass1!")  # 中文也算字符


class TestHashToken:
    """token 哈希测试"""

    def test_hash_token_is_deterministic(self):
        t = "my_refresh_token_abc123"
        h1 = auth._hash_token(t)
        h2 = auth._hash_token(t)
        assert h1 == h2

    def test_hash_token_not_reversible(self):
        t = "secret_token"
        h = auth._hash_token(t)
        assert h != t
        assert len(h) == 64  # SHA-256 hex


class TestGetClientIP:
    """IP 提取测试"""

    def test_direct_client_ip(self):
        class FakeHeaders:
            def get(self, name):
                return None

        class FakeRequest:
            client = None
            headers = FakeHeaders()

        # client=None 的情况
        ip = auth.get_client_ip(FakeRequest())
        assert ip == "unknown"

    def test_forwarded_header(self):
        class FakeRequest:
            class Headers:
                @staticmethod
                def get(name):
                    if name == "X-Forwarded-For":
                        return "10.0.0.1, 192.168.1.1"
                    return None

            headers = Headers()
            client = None

        ip = auth.get_client_ip(FakeRequest())
        assert ip == "10.0.0.1"

    def test_no_forwarded_header(self):
        class FakeRequest:
            class Client:
                host = "127.0.0.1"

            client = Client()

            class Headers:
                @staticmethod
                def get(name):
                    return None

            headers = Headers()

        ip = auth.get_client_ip(FakeRequest())
        assert ip == "127.0.0.1"
