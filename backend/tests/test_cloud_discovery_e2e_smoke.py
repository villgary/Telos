"""End-to-end smoke test against a live backend running on the configured URL.

Exercises the full create → audit-log flow over real HTTP. Skipped if
ACCOUNTSCAN_E2E_URL is not set, so it doesn't break the regular pytest
run that uses an in-memory SQLite.

Run: ACCOUNTSCAN_E2E_URL=http://127.0.0.1:8000 \
     ACCOUNTSCAN_E2E_USER=admin ACCOUNTSCAN_E2E_PASS=Admin123! \
     python -m pytest backend/tests/test_cloud_discovery_e2e_smoke.py -v
"""
import os
import sys
import time
import uuid

import pytest
import requests


URL = os.environ.get("ACCOUNTSCAN_E2E_URL")
USER = os.environ.get("ACCOUNTSCAN_E2E_USER", "admin")
PASS = os.environ.get("ACCOUNTSCAN_E2E_PASS", "Admin123!")


pytestmark = pytest.mark.skipif(
    not URL, reason="ACCOUNTSCAN_E2E_URL not set; live backend smoke test skipped"
)


@pytest.fixture(scope="module")
def auth_token():
    """Log in to the live backend and cache the JWT for the test module."""
    r = requests.post(
        f"{URL}/api/v1/auth/login",
        data={"username": USER, "password": PASS},
        timeout=10,
    )
    r.raise_for_status()
    return r.json()["access_token"]


@pytest.fixture
def client(auth_token):
    s = requests.Session()
    s.headers["Authorization"] = f"Bearer {auth_token}"
    s.headers["Content-Type"] = "application/json"
    s.base_url = URL
    return s


def test_create_then_audit(client):
    conn_name = f"smoke-{uuid.uuid4().hex[:8]}"

    # Create
    r = client.post(f"{client.base_url}/api/v1/ai-agents/connections", json={
        "name": conn_name, "provider": "anthropic", "api_key": "sk-smoke-not-real",
    })
    assert r.status_code == 201, r.text
    created = r.json()
    assert created["name"] == conn_name
    assert created["provider"] == "anthropic"
    assert "api_key" not in created
    assert "encrypted_api_key" not in created
    assert created["api_key_fingerprint"]  # non-empty
    conn_id = created["id"]

    try:
        # List shows the new connection
        r = client.get(f"{client.base_url}/api/v1/ai-agents/connections")
        assert r.status_code == 200
        names = [c["name"] for c in r.json()["connections"]]
        assert conn_name in names

        # Audit log has the "created" entry
        r = client.get(f"{client.base_url}/api/v1/ai-agents/connections/{conn_id}/audit")
        assert r.status_code == 200
        entries = r.json()["entries"]
        actions = [e["action"] for e in entries]
        assert "created" in actions
        # No plaintext key in any audit entry
        for e in entries:
            for k in ("before", "after", "note"):
                v = e.get(k) or ""
                assert "sk-smoke-not-real" not in str(v), f"key leaked in {k}"

        # Rename
        new_name = conn_name + "-r"
        r = client.patch(f"{client.base_url}/api/v1/ai-agents/connections/{conn_id}",
                         json={"name": new_name})
        assert r.status_code == 200
        assert r.json()["name"] == new_name

        # Audit now also has "renamed"
        r = client.get(f"{client.base_url}/api/v1/ai-agents/connections/{conn_id}/audit")
        assert "renamed" in [e["action"] for e in r.json()["entries"]]
    finally:
        # Clean up — delete the connection
        r = client.delete(f"{client.base_url}/api/v1/ai-agents/connections/{conn_id}")
        assert r.status_code == 204


def test_patch_rejects_unknown_field(client):
    """Pydantic extra='forbid' on CloudConnectionUpdate should reject api_key."""
    # Need a connection to PATCH against — create + clean up
    conn_name = f"smoke-patch-{uuid.uuid4().hex[:8]}"
    r = client.post(f"{client.base_url}/api/v1/ai-agents/connections", json={
        "name": conn_name, "provider": "openai", "api_key": "sk-smoke-not-real",
    })
    assert r.status_code == 201, r.text
    conn_id = r.json()["id"]
    try:
        r = client.patch(f"{client.base_url}/api/v1/ai-agents/connections/{conn_id}",
                         json={"name": "x", "api_key": "should-be-rejected"})
        assert r.status_code == 422
        assert r.json()["detail"][0]["type"] == "extra_forbidden"
    finally:
        client.delete(f"{client.base_url}/api/v1/ai-agents/connections/{conn_id}")
