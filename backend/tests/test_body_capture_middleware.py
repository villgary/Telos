"""
Tests for backend.middleware.body_capture.BodyCaptureMiddleware.

Uses Starlette's TestClient for a real end-to-end test of the middleware.
"""

import pytest
import sys
import os
from typing import Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

os.environ.setdefault("ACCOUNTSCAN_MASTER_KEY", "test_master_key_0123456789abcdef01234567")
os.environ.setdefault("ACCOUNTSCAN_JWT_SECRET", "test_jwt_secret_0123456789abcdef0123456")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("JWT_EXPIRE_MINUTES", "15")
os.environ.setdefault("REFRESH_TOKEN_EXPIRE_DAYS", "7")

from starlette.testclient import TestClient
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.middleware import Middleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from backend.middleware.body_capture import BodyCaptureMiddleware


# ── Minimal app that echoes request.state._body_json ──────────────

captured_body: Optional[dict] = None


async def echo_body(request: Request):
    """Endpoint that reads what BodyCaptureMiddleware stored."""
    global captured_body
    captured_body = getattr(request.state, "_body_json", None)
    return JSONResponse({"body_json": captured_body})


app = Starlette(
    routes=[Route("/echo", echo_body, methods=["GET", "POST", "PUT", "PATCH", "DELETE"])],
    middleware=[Middleware(BodyCaptureMiddleware)],
)


class TestBodyCaptureMiddleware:
    client = TestClient(app, raise_server_exceptions=False)

    def test_get_request_sets_body_json_to_none(self):
        """GET 请求不应有 body"""
        global captured_body
        captured_body = None
        resp = self.client.get("/echo")
        assert resp.status_code == 200
        assert resp.json()["body_json"] is None

    def test_delete_request_sets_body_json_to_none(self):
        global captured_body
        captured_body = None
        resp = self.client.delete("/echo")
        assert resp.status_code == 200
        assert resp.json()["body_json"] is None

    def test_post_with_json_body(self):
        global captured_body
        captured_body = None
        payload = {"username": "alice", "email": "alice@example.com"}
        resp = self.client.post("/echo", json=payload)
        assert resp.status_code == 200
        assert resp.json()["body_json"] == payload

    def test_post_with_empty_body(self):
        global captured_body
        captured_body = None
        resp = self.client.post("/echo", content=b"")
        assert resp.status_code == 200
        assert resp.json()["body_json"] is None

    def test_post_with_non_json_body(self):
        """plain text body 应降级为 None（不 crash）"""
        global captured_body
        captured_body = None
        resp = self.client.post("/echo", content=b"hello world", headers={"Content-Type": "text/plain"})
        assert resp.status_code == 200
        # body 无法解析为 JSON，降级为 None
        assert resp.json()["body_json"] is None

    def test_put_with_nested_json(self):
        global captured_body
        captured_body = None
        payload = {"user": {"name": "bob", "roles": ["admin", "viewer"]}}
        resp = self.client.put("/echo", json=payload)
        assert resp.status_code == 200
        assert resp.json()["body_json"] == payload

    def test_patch_with_array_json(self):
        global captured_body
        captured_body = None
        payload = ["item1", "item2", "item3"]
        resp = self.client.patch("/echo", json=payload)
        assert resp.status_code == 200
        assert resp.json()["body_json"] == payload

    def test_post_with_special_characters(self):
        """Unicode 和特殊字符应正确解析"""
        global captured_body
        captured_body = None
        payload = {"name": "管理员", "note": "密码🔐密码!"}
        resp = self.client.post("/echo", json=payload)
        assert resp.status_code == 200
        assert resp.json()["body_json"] == payload


class TestParseJson:
    """直接测试 _parse_json 辅助方法"""

    def test_valid_json_bytes(self):
        from backend.middleware.body_capture import BodyCaptureMiddleware
        result = BodyCaptureMiddleware._parse_json(b'{"key": "value"}')
        assert result == {"key": "value"}

    def test_invalid_json_raises(self):
        from backend.middleware.body_capture import BodyCaptureMiddleware
        with pytest.raises(Exception):  # json.JSONDecodeError
            BodyCaptureMiddleware._parse_json(b"not json at all")
