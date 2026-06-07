"""Credential management — verify round-trip encryption of password, private
key, and the new api_token auth type."""
import os
import sys

os.environ.setdefault("ACCOUNTSCAN_MASTER_KEY", "test_master_key_0123456789abcdef01234567")
os.environ.setdefault("ACCOUNTSCAN_JWT_SECRET", "test_jwt_secret_0123456789abcdef0123456")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.database import Base, get_db
from backend import models, auth
from backend.main import app
from backend.services import crypto
from backend.models._enums import AuthType


@pytest.fixture
def client():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    app.dependency_overrides.clear()
    app.dependency_overrides[get_db] = lambda: Session()

    admin = models.User(username="alice", email="a@b", password_hash="x",
                        role=models.UserRole.admin)
    s = Session()
    s.add(admin); s.commit()

    def _user():
        return admin
    app.dependency_overrides[auth.get_current_user] = _user
    app.dependency_overrides[auth.require_admin] = _user

    yield TestClient(app), Session
    app.dependency_overrides.clear()


def test_create_password_credential_encrypts_at_rest(client):
    c, _ = client
    r = c.post("/api/v1/credentials", json={
        "name": "prod-ssh",
        "auth_type": "password",
        "username": "root",
        "password": "sk-not-a-real-key-1234",
    })
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["name"] == "prod-ssh"
    assert data["auth_type"] == "password"
    assert data["has_password"] is True
    assert data["has_private_key"] is False
    assert data["has_api_token"] is False
    # Plaintext must never appear in any response field
    for field in ("name", "username", "auth_type"):
        assert "sk-not" not in str(data.get(field) or ""), f"plaintext leaked in {field}"


def test_create_api_token_credential_encrypts_at_rest(client):
    """The new auth type — used for HTTP-based scanners (Nessus, Qualys, future)."""
    c, _ = client
    r = c.post("/api/v1/credentials", json={
        "name": "nessus-prod",
        "auth_type": "api_token",
        "username": "nessus-user",
        "api_token": "sk-nessus-super-secret-token-1234567890",
    })
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["name"] == "nessus-prod"
    assert data["auth_type"] == "api_token"
    assert data["has_api_token"] is True
    assert data["has_password"] is False
    assert data["has_private_key"] is False
    # Plaintext token must never appear in any response field
    full_body = r.text
    assert "sk-nessus-super-secret-token" not in full_body, "plaintext token leaked in response"


def test_create_api_token_rejects_empty_token(client):
    c, _ = client
    r = c.post("/api/v1/credentials", json={
        "name": "empty-token",
        "auth_type": "api_token",
        "username": "u",
        "api_token": "",
    })
    assert r.status_code == 400
    assert "token" in r.json()["detail"].lower()


def test_auth_type_enum_supports_three_values():
    assert {a.value for a in AuthType} == {"password", "ssh_key", "api_token"}


def test_create_ssh_key_credential_still_works(client):
    """Regression — adding api_token must not break the existing ssh_key path."""
    c, _ = client
    r = c.post("/api/v1/credentials", json={
        "name": "ops-ssh-key",
        "auth_type": "ssh_key",
        "username": "ops",
        "private_key": "-----BEGIN RSA PRIVATE KEY-----\nfake\n-----END RSA PRIVATE KEY-----",
    })
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["auth_type"] == "ssh_key"
    assert data["has_private_key"] is True
    assert data["has_password"] is False
    assert data["has_api_token"] is False
    assert "BEGIN RSA PRIVATE KEY" not in r.text
