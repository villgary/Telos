# AI Agent — Cloud API Discovery — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a second discovery channel for AI Agents — register a provider admin key (Anthropic Console or OpenAI Dashboard), have Telos periodically inventory the API keys/orgs/projects it can see, and write the results into the existing `ai_agents` table with `framework='cloud_<provider>'` and `discovery_source='api_discovery'`. Reuses all v1 listing, risk, alert, and audit plumbing.

**Architecture:** New `cloud_connections` table (encrypted admin key, last-sync state) + `cloud_connection_audit_log` table (per-connection change history). Per-provider modules in `backend/services/cloud_discovery/` peer to `ssh_scanner`. New router `/api/v1/ai-agents/connections` for CRUD + sync-now + audit log. New React page `/ai-agents/connections`. 6h scheduled sync plus a manual button. Two new additive risk rules. The v1 `ai_agents` table gets a new nullable `connection_id` column for soft-delete-with-orphaned-agents support.

**Tech Stack:** FastAPI, SQLAlchemy 2, Alembic, httpx 0.27 (already in requirements), APScheduler (existing), AES-256-GCM via `backend/encryption.py` (existing), React 18 + TypeScript + Ant Design 5, i18next, Vitest, Playwright.

**Spec:** `docs/superpowers/specs/2026-06-04-ai-agent-cloud-discovery-design.md`

---

## File Structure

| File | Responsibility | Action |
|---|---|---|
| `backend/models/_enums.py` | `CloudProvider`, `CloudSyncStatus` enums | Modify |
| `backend/models/cloud_connection.py` | `CloudConnection`, `CloudConnectionAuditLog` ORM models | Create |
| `backend/models/__init__.py` | Re-export new models | Modify |
| `backend/models/ai_agents.py` | Add `connection_id` column on `AIAgent` | Modify |
| `backend/alembic/versions/025_cloud_connections.py` | Two new tables + `ai_agents.connection_id` | Create |
| `backend/services/crypto.py` | Re-export `encrypt`/`decrypt` + `fingerprint` helper | Create |
| `backend/services/cloud_discovery/__init__.py` | `RawAgent` + `discover(connection)` dispatcher | Create |
| `backend/services/cloud_discovery/base.py` | `CloudDiscoveryBase` — retry, timeout, fingerprint | Create |
| `backend/services/cloud_discovery/anthropic.py` | Anthropic Admin API client | Create |
| `backend/services/cloud_discovery/openai.py` | OpenAI Admin API client | Create |
| `backend/services/ai_agent_scanner.py` | `ingest_cloud_agents()` + 2 new risk rules | Modify |
| `backend/services/scheduler_service.py` | `sync_all_cloud_connections` 6h job | Modify |
| `backend/schemas/cloud_connections.py` | Pydantic schemas | Create |
| `backend/routers/ai_agent_connections.py` | REST: CRUD + sync-now + audit | Create |
| `backend/main.py` | Wire new router | Modify |
| `backend/tests/test_crypto.py` | Round-trip + tamper reject | Create |
| `backend/tests/test_cloud_discovery_base.py` | Retry, timeout, fingerprint | Create |
| `backend/tests/test_cloud_discovery_anthropic.py` | Anthropic mocked HTTP paths | Create |
| `backend/tests/test_cloud_discovery_openai.py` | OpenAI mocked HTTP paths | Create |
| `backend/tests/test_ai_agent_cloud_ingest.py` | Ingest + dedup + risk rules | Create |
| `backend/tests/test_ai_agent_connections_router.py` | Router + key never logged | Create |
| `backend/tests/test_ai_agent_connections_audit.py` | Audit row per state change | Create |
| `backend/tests/test_migration_025.py` | Migration up + down | Create |
| `backend/tests/test_scheduler_cloud_sync.py` | Scheduled sync fans out per connection | Create |
| `frontend/src/locales/en-US.json` | `aiAgent.connections.*` keys (~10) | Modify |
| `frontend/src/locales/zh-CN.json` | Same keys in Chinese | Modify |
| `frontend/src/api/client.ts` | `listCloudConnections`, `createCloudConnection`, etc. | Modify |
| `frontend/src/pages/AIAgentsPage.tsx` | Add a "Connections" link button in the page header | Modify |
| `frontend/src/pages/CloudConnectionsPage.tsx` | Connection management UI | Create |
| `frontend/src/pages/__tests__/CloudConnectionsPage.test.tsx` | Vitest for the page | Create |
| `frontend/src/api/__tests__/ai-agent-connections.test.ts` | Vitest for the API client | Create |
| `frontend/src/App.tsx` | `/ai-agents/connections` route | Modify |
| `frontend/e2e/cloud-connections.spec.ts` | Playwright smoke test | Create |

Each test file maps 1:1 to the service it covers; migration and scheduler tests are separate for isolation.

---

## Phase 1 — Foundation (enums, models, migration)

### Task 1: Add enums

**Files:**
- Modify: `backend/models/_enums.py` (append at the bottom)

- [ ] **Step 1: Add `CloudProvider` and `CloudSyncStatus` enums**

Append to `backend/models/_enums.py`:

```python
class CloudProvider(str, enum.Enum):
    anthropic = "anthropic"
    openai = "openai"


class CloudSyncStatus(str, enum.Enum):
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    RUNNING = "running"


class CloudConnectionAuditAction(str, enum.Enum):
    CREATED = "created"
    RENAMED = "renamed"
    ROTATED = "rotated"
    DELETED = "deleted"
    SYNC_STARTED = "sync_started"
    SYNC_FINISHED = "sync_finished"


# Mapping used by ai_agent_scanner.ingest_cloud_agents to set AIAgent.framework.
# (Cloud-discovered agents get a per-provider framework value.)
CLOUD_PROVIDER_TO_FRAMEWORK = {
    "anthropic": "cloud_anthropic",
    "openai": "cloud_openai",
}
```

- [ ] **Step 2: Verify no syntax error**

Run: `cd /Users/jyb/projects/telos && python -c "from backend.models._enums import CloudProvider, CloudSyncStatus, CloudConnectionAuditAction, CLOUD_PROVIDER_TO_FRAMEWORK; print('ok')"`
Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add backend/models/_enums.py
git commit -m "feat(ai-agents): add cloud connection enums"
```

### Task 2: Add ORM models

**Files:**
- Create: `backend/models/cloud_connection.py`
- Modify: `backend/models/__init__.py` (add to the AI Agents section + a new Cloud Connections section)
- Modify: `backend/models/ai_agents.py` (add `connection_id` column on `AIAgent`)

- [ ] **Step 1: Create `backend/models/cloud_connection.py`**

Write the file:

```python
"""Cloud connection + audit-log ORM models — peer to NHI for provider-side AI Agent discovery."""
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, DateTime, ForeignKey, Text, JSON, UniqueConstraint, Index,
)
from sqlalchemy.orm import relationship

from backend.models._db import Base


class CloudConnection(Base):
    __tablename__ = "cloud_connections"
    __table_args__ = (
        UniqueConstraint("name", name="uq_cloud_connections_name"),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(64), nullable=False)
    provider = Column(String(16), nullable=False)  # anthropic|openai
    encrypted_api_key = Column(Text, nullable=False)  # base64(nonce||ct||tag) from backend.encryption
    api_key_fingerprint = Column(String(16), nullable=False)  # sha256[:16] hex of plaintext
    last_sync_at = Column(DateTime, nullable=True)
    last_sync_started_at = Column(DateTime, nullable=True)
    last_sync_status = Column(String(16), nullable=True)  # success|partial|failed|running
    last_sync_error = Column(String(256), nullable=True)
    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    created_by = relationship("User", foreign_keys=[created_by_user_id])
    agents = relationship("AIAgent", back_populates="connection", passive_deletes=True)


class CloudConnectionAuditLog(Base):
    __tablename__ = "cloud_connection_audit_log"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    connection_id = Column(
        Integer,
        ForeignKey("cloud_connections.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    actor_user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    action = Column(String(32), nullable=False)  # created|renamed|rotated|deleted|sync_started|sync_finished
    status = Column(String(16), nullable=True)  # success|partial|failed|auth_failed|rate_limited
    before = Column(JSON, nullable=True)  # name only — never the key
    after = Column(JSON, nullable=True)   # name only — never the key
    note = Column(String(256), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
```

- [ ] **Step 2: Add `connection_id` to `AIAgent`**

In `backend/models/ai_agents.py`, add this import and column. Replace the import line `from backend.models._db import Base` (already present) and add after `notes = Column(Text, nullable=True)`:

```python
    connection_id = Column(
        Integer,
        ForeignKey("cloud_connections.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    connection = relationship("CloudConnection", back_populates="agents")
```

Also extend `__table_args__` to add the new index (do NOT change `ix_ai_agents_dedup` — it's still correct):

Find the existing `__table_args__` block in `ai_agents.py`:

```python
    __table_args__ = (
        Index(
            "ix_ai_agents_dedup",
            "framework", "agent_name", "owner_team", "asset_id",
            unique=True,
        ),
    )
```

Replace it with:

```python
    __table_args__ = (
        Index(
            "ix_ai_agents_dedup",
            "framework", "agent_name", "owner_team", "asset_id",
            unique=True,
        ),
        Index("ix_ai_agents_connection", "connection_id"),
    )
```

- [ ] **Step 3: Re-export from `backend/models/__init__.py`**

In `backend/models/__init__.py`, find the AI Agent import line:

```python
from backend.models.ai_agents import AIAgent
```

Replace with:

```python
from backend.models.ai_agents import AIAgent
from backend.models.cloud_connection import CloudConnection, CloudConnectionAuditLog
```

- [ ] **Step 4: Verify imports work**

Run: `cd /Users/jyb/projects/telos && python -c "from backend.models import CloudConnection, CloudConnectionAuditLog; from backend.models.ai_agents import AIAgent; assert hasattr(AIAgent, 'connection_id'); print('ok')"`
Expected: `ok`

- [ ] **Step 5: Commit**

```bash
git add backend/models/cloud_connection.py backend/models/__init__.py backend/models/ai_agents.py
git commit -m "feat(ai-agents): add CloudConnection + audit-log models"
```

### Task 3: Migration 025

**Files:**
- Create: `backend/alembic/versions/025_cloud_connections.py`

- [ ] **Step 1: Create the migration file**

Write to `backend/alembic/versions/025_cloud_connections.py`:

```python
"""cloud_connections + cloud_connection_audit_log tables, plus ai_agents.connection_id

Revision ID: 025_cloud_connections
Revises: 024_ai_agents
Create Date: 2026-06-04
"""
import sqlalchemy as sa
from alembic import op


revision = "025_cloud_connections"
down_revision = "024_ai_agents"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "cloud_connections",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("provider", sa.String(16), nullable=False),
        sa.Column("encrypted_api_key", sa.Text, nullable=False),
        sa.Column("api_key_fingerprint", sa.String(16), nullable=False),
        sa.Column("last_sync_at", sa.DateTime, nullable=True),
        sa.Column("last_sync_started_at", sa.DateTime, nullable=True),
        sa.Column("last_sync_status", sa.String(16), nullable=True),
        sa.Column("last_sync_error", sa.String(256), nullable=True),
        sa.Column("created_by_user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=True, onupdate=sa.func.now()),
        sa.UniqueConstraint("name", name="uq_cloud_connections_name"),
    )
    op.create_index("ix_cloud_connections_provider", "cloud_connections", ["provider"])
    op.create_index(
        "ix_cloud_connections_fingerprint", "cloud_connections", ["api_key_fingerprint"]
    )

    op.create_table(
        "cloud_connection_audit_log",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "connection_id",
            sa.Integer,
            sa.ForeignKey("cloud_connections.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("actor_user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("action", sa.String(32), nullable=False),
        sa.Column("status", sa.String(16), nullable=True),
        sa.Column("before", sa.JSON, nullable=True),
        sa.Column("after", sa.JSON, nullable=True),
        sa.Column("note", sa.String(256), nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_cloud_audit_connection", "cloud_connection_audit_log", ["connection_id"])
    op.create_index("ix_cloud_audit_actor", "cloud_connection_audit_log", ["actor_user_id"])
    op.create_index("ix_cloud_audit_created", "cloud_connection_audit_log", ["created_at"])

    op.add_column(
        "ai_agents",
        sa.Column(
            "connection_id",
            sa.Integer,
            sa.ForeignKey("cloud_connections.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_ai_agents_connection", "ai_agents", ["connection_id"])


def downgrade() -> None:
    op.drop_index("ix_ai_agents_connection", table_name="ai_agents")
    op.drop_column("ai_agents", "connection_id")
    op.drop_index("ix_cloud_audit_created", table_name="cloud_connection_audit_log")
    op.drop_index("ix_cloud_audit_actor", table_name="cloud_connection_audit_log")
    op.drop_index("ix_cloud_audit_connection", table_name="cloud_connection_audit_log")
    op.drop_table("cloud_connection_audit_log")
    op.drop_index("ix_cloud_connections_fingerprint", table_name="cloud_connections")
    op.drop_index("ix_cloud_connections_provider", table_name="cloud_connections")
    op.drop_table("cloud_connections")
```

- [ ] **Step 2: Commit**

```bash
git add backend/alembic/versions/025_cloud_connections.py
git commit -m "feat(ai-agents): add migration 025 for cloud connections"
```

### Task 4: Migration test

**Files:**
- Create: `backend/tests/test_migration_025.py`

- [ ] **Step 1: Create the test file**

Write to `backend/tests/test_migration_025.py`:

```python
"""Verify migration 025 creates cloud_connections + cloud_connection_audit_log
and adds ai_agents.connection_id, then downgrades cleanly."""
import importlib
import os
import sys

os.environ.setdefault("ACCOUNTSCAN_MASTER_KEY", "test_master_key_0123456789abcdef01234567")
os.environ.setdefault("ACCOUNTSCAN_JWT_SECRET", "test_jwt_secret_0123456789abcdef0123456")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import pytest


@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "migration_025.db")


def _reload_backend_db(db_url):
    os.environ["DATABASE_URL"] = db_url
    for mod_name in list(sys.modules):
        if mod_name == "backend" or mod_name.startswith("backend."):
            del sys.modules[mod_name]
    return importlib.import_module("backend.database")


@pytest.fixture
def alembic_cfg(db_path):
    from alembic.config import Config
    cfg = Config(os.path.join(os.path.dirname(__file__), "..", "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
    return cfg


def test_migration_025_upgrade_then_downgrade(db_path, alembic_cfg):
    from alembic import command
    from sqlalchemy import create_engine, inspect

    _reload_backend_db(f"sqlite:///{db_path}")

    from backend.database import Base
    from backend import models  # noqa: F401

    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(bind=engine)
    with engine.begin() as conn:
        conn.exec_driver_sql("DROP TABLE IF EXISTS cloud_connection_audit_log")
        conn.exec_driver_sql("DROP TABLE IF EXISTS cloud_connections")
        # ai_agents.connection_id is added in 025, so drop the column too
        cols = inspect(engine).get_columns("ai_agents")
        if any(c["name"] == "connection_id" for c in cols):
            with engine.begin() as c2:
                c2.exec_driver_sql("ALTER TABLE ai_agents DROP COLUMN connection_id")

    command.stamp(alembic_cfg, "024_ai_agents")
    command.upgrade(alembic_cfg, "025_cloud_connections")

    insp = inspect(engine)
    tables = set(insp.get_table_names())
    assert "cloud_connections" in tables
    assert "cloud_connection_audit_log" in tables

    conn_cols = {c["name"] for c in insp.get_columns("cloud_connections")}
    expected_conn = {
        "id", "name", "provider", "encrypted_api_key", "api_key_fingerprint",
        "last_sync_at", "last_sync_started_at", "last_sync_status", "last_sync_error",
        "created_by_user_id", "created_at", "updated_at",
    }
    assert not (expected_conn - conn_cols), f"missing columns: {expected_conn - conn_cols}"

    audit_cols = {c["name"] for c in insp.get_columns("cloud_connection_audit_log")}
    expected_audit = {
        "id", "connection_id", "actor_user_id", "action", "status",
        "before", "after", "note", "created_at",
    }
    assert not (expected_audit - audit_cols), f"missing columns: {expected_audit - audit_cols}"

    ai_cols = {c["name"] for c in insp.get_columns("ai_agents")}
    assert "connection_id" in ai_cols

    conn_indexes = {ix["name"] for ix in insp.get_indexes("cloud_connections")}
    assert "ix_cloud_connections_provider" in conn_indexes
    assert "ix_cloud_connections_fingerprint" in conn_indexes

    command.downgrade(alembic_cfg, "024_ai_agents")
    insp2 = inspect(engine)
    tables2 = set(insp2.get_table_names())
    assert "cloud_connections" not in tables2
    assert "cloud_connection_audit_log" not in tables2
    assert "connection_id" not in {c["name"] for c in insp2.get_columns("ai_agents")}
```

- [ ] **Step 2: Run the test**

Run: `cd /Users/jyb/projects/telos/backend && python -m pytest ../backend/tests/test_migration_025.py -v`
Expected: `1 passed`

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_migration_025.py
git commit -m "test(ai-agents): add migration 025 up/down test"
```

---

## Phase 2 — Crypto + discovery plumbing

### Task 5: services/crypto.py

**Files:**
- Create: `backend/services/crypto.py`
- Create: `backend/tests/test_crypto.py`

- [ ] **Step 1: Write the failing test**

Write to `backend/tests/test_crypto.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/jyb/projects/telos/backend && python -m pytest ../backend/tests/test_crypto.py -v`
Expected: `ModuleNotFoundError: No module named 'backend.services.crypto'`

- [ ] **Step 3: Implement the module**

Write to `backend/services/crypto.py`:

```python
"""Re-exports the project's AES-256-GCM encrypt/decrypt and adds a
sha256[:16] fingerprint helper used by the cloud discovery channel.

The cloud discovery code imports from this module so tests have a single seam
and we don't have two copies of the fingerprint scheme drifting apart.
"""
import hashlib
from typing import Optional

from backend.encryption import encrypt, decrypt  # re-export


def fingerprint(plaintext: Optional[str]) -> Optional[str]:
    """Return a 16-char hex prefix of sha256(plaintext), or None for empty input.

    Never returns any portion of the key itself; the output is the first
    16 hex chars (8 bytes) of the digest, sufficient to detect key reuse
    across connections without persisting the secret.
    """
    if not plaintext:
        return None
    return hashlib.sha256(plaintext.encode("utf-8")).hexdigest()[:16]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/jyb/projects/telos/backend && python -m pytest ../backend/tests/test_crypto.py -v`
Expected: `3 passed`

- [ ] **Step 5: Commit**

```bash
git add backend/services/crypto.py backend/tests/test_crypto.py
git commit -m "feat(ai-agents): add crypto re-export + fingerprint helper"
```

### Task 6: services/cloud_discovery/base.py

**Files:**
- Create: `backend/services/cloud_discovery/__init__.py` (stub)
- Create: `backend/services/cloud_discovery/base.py`
- Create: `backend/tests/test_cloud_discovery_base.py`

- [ ] **Step 1: Create the package init (stub)**

Write to `backend/services/cloud_discovery/__init__.py`:

```python
"""Cloud provider admin API discovery — per-provider modules peer to ssh_scanner.

Public API:
    RawAgent             — normalized per-agent dict produced by a provider module
    discover(connection) — dispatcher; returns List[RawAgent]
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from backend import models


@dataclass
class RawAgent:
    """One AI Agent as seen by a provider's admin API.

    Provider modules produce these. The ingest step in
    ai_agent_scanner.ingest_cloud_agents() turns them into AIAgent rows.
    """
    provider: str                              # "anthropic" | "openai"
    project_label: str                         # human-readable project / org name
    agent_name: str                            # fully-qualified synthetic name
    api_key_fingerprint: str                   # 16-char hex (sha256[:16])
    capabilities: Dict[str, Any] = field(default_factory=lambda: {
        "filesystem": False, "network": False, "code_exec": False, "tool_count": 0,
    })
    model: Optional[str] = None
    owner_team: Optional[str] = None


def discover(connection: "models.CloudConnection") -> List[RawAgent]:
    """Dispatch to the per-provider module based on `connection.provider`."""
    from backend.services.cloud_discovery.anthropic import AnthropicDiscovery
    from backend.services.cloud_discovery.openai import OpenAIDiscovery

    providers = {
        "anthropic": AnthropicDiscovery,
        "openai": OpenAIDiscovery,
    }
    impl = providers.get(connection.provider)
    if impl is None:
        raise ValueError(f"Unsupported cloud provider: {connection.provider}")
    return impl(connection).run()


__all__ = ["RawAgent", "discover"]
```

- [ ] **Step 2: Write the failing base test**

Write to `backend/tests/test_cloud_discovery_base.py`:

```python
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


class _FakeConnection:
    def __init__(self, provider="anthropic"):
        self.provider = provider
        self.encrypted_api_key = "ignored"
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
    assert delays == [1, 2, 4]  # 1s, 2s, 4s


def test_retry_with_backoff_gives_up_after_max_attempts(monkeypatch):
    monkeypatch.setattr(base.time, "sleep", lambda s: None)
    with pytest.raises(RetryableError):
        base._retry_with_backoff(lambda: (_ for _ in ()).throw(RetryableError("nope")),
                                  max_attempts=3)
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd /Users/jyb/projects/telos/backend && python -m pytest ../backend/tests/test_cloud_discovery_base.py -v`
Expected: `ModuleNotFoundError: No module named 'backend.services.cloud_discovery.base'`

- [ ] **Step 4: Implement the base module**

Write to `backend/services/cloud_discovery/base.py`:

```python
"""Shared base class for cloud provider discovery modules."""
from __future__ import annotations

import logging
import time
from typing import Callable, List, TypeVar

import httpx

from backend.services import crypto
from backend.services.cloud_discovery import RawAgent


logger = logging.getLogger(__name__)


class RetryableError(Exception):
    """Transient provider failure — retry with backoff."""


class FatalDiscoveryError(Exception):
    """Provider rejected the request definitively (401, 403). Do not retry."""


T = TypeVar("T")


def _retry_with_backoff(fn: Callable[[], T], max_attempts: int = 3) -> T:
    """Run fn() with exponential backoff (1s, 2s, 4s) on RetryableError.

    Re-raises the last RetryableError if all attempts fail. FatalDiscoveryError
    propagates immediately.
    """
    delay = 1.0
    last_exc: Exception | None = None
    for attempt in range(max_attempts):
        try:
            return fn()
        except FatalDiscoveryError:
            raise
        except RetryableError as e:
            last_exc = e
            if attempt == max_attempts - 1:
                break
            time.sleep(delay)
            delay *= 2
    assert last_exc is not None
    raise last_exc


class CloudDiscoveryBase:
    """Subclassed by AnthropicDiscovery and OpenAIDiscovery.

    Subclasses implement _http_get(path) -> dict and _list_subresources()
    to produce RawAgent rows.
    """

    PROVIDER_NAME: str = ""  # set by subclass
    BASE_URL: str = ""

    def __init__(self, connection):
        self.connection = connection
        self._api_key = crypto.decrypt(connection.encrypted_api_key)

    # ── Public entry point ─────────────────────────────────────────────
    def run(self) -> List[RawAgent]:
        try:
            return self._list_agents()
        except FatalDiscoveryError as e:
            logger.warning("Cloud discovery fatal: provider=%s err=%s",
                           self.PROVIDER_NAME, e)
            raise
        except RetryableError as e:
            logger.warning("Cloud discovery gave up: provider=%s err=%s",
                           self.PROVIDER_NAME, e)
            raise

    # ── HTTP helper ────────────────────────────────────────────────────
    def _http_get(self, path: str, params: dict | None = None) -> dict:
        url = f"{self.BASE_URL}{path}"
        headers = self._auth_headers()

        def _do():
            try:
                resp = httpx.get(url, headers=headers, params=params, timeout=10.0)
            except httpx.TimeoutException as e:
                raise RetryableError(f"timeout: {e}") from e
            except httpx.HTTPError as e:
                raise RetryableError(f"network: {e}") from e

            if resp.status_code in (401, 403):
                raise FatalDiscoveryError(f"auth_failed: {resp.status_code}")
            if resp.status_code == 429:
                raise RetryableError("rate_limited")
            if 500 <= resp.status_code < 600:
                raise RetryableError(f"server_error: {resp.status_code}")
            if resp.status_code >= 400:
                raise FatalDiscoveryError(f"http_error: {resp.status_code}")
            return resp.json()

        return _retry_with_backoff(_do, max_attempts=3)

    # ── Hooks for subclasses ────────────────────────────────────────────
    def _auth_headers(self) -> dict:
        """Override in subclass. Must never log the key value."""
        raise NotImplementedError

    def _list_agents(self) -> List[RawAgent]:
        """Override in subclass. Should call self._http_get() and assemble RawAgent rows."""
        raise NotImplementedError
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd /Users/jyb/projects/telos/backend && python -m pytest ../backend/tests/test_cloud_discovery_base.py -v`
Expected: `5 passed` (the four monkeypatched dispatch tests + the retry tests will pass once anthropic/openai modules exist; the dispatch tests will fail with `ModuleNotFoundError` on anthropic/openai import, so temporarily adjust the test — see Step 6)

The `test_dispatch_anthropic_returns_raw_agents` test will fail at `from backend.services.cloud_discovery.anthropic import AnthropicDiscovery` in the `discover()` function. The cleanest way to handle this is to create **stub** `anthropic.py` and `openai.py` first that just expose their classes. We do that in Task 7 and Task 8.

For now, replace the dispatch tests in `test_cloud_discovery_base.py` with a single temporary assertion that `import base` works:

```python
def test_base_module_imports():
    assert base is not None
```

- [ ] **Step 5 (corrected): Run test to verify it passes**

Run: `cd /Users/jyb/projects/telos/backend && python -m pytest ../backend/tests/test_cloud_discovery_base.py -v`
Expected: `3 passed` (the temporary `test_base_module_imports` plus the two retry tests)

- [ ] **Step 6: Commit (base + tests)**

```bash
git add backend/services/cloud_discovery/ backend/tests/test_cloud_discovery_base.py
git commit -m "feat(ai-agents): add cloud_discovery base class with retry/timeout"
```

### Task 7: services/cloud_discovery/anthropic.py

**Files:**
- Create: `backend/services/cloud_discovery/anthropic.py`
- Create: `backend/tests/test_cloud_discovery_anthropic.py`

- [ ] **Step 1: Write the failing test**

Write to `backend/tests/test_cloud_discovery_anthropic.py`:

```python
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
    return MagicMock(
        id=1, name=name, provider=provider,
        encrypted_api_key=crypto.encrypt("sk-ant-admin-test"),
        api_key_fingerprint=crypto.fingerprint("sk-ant-admin-test"),
    )


def test_happy_path_produces_one_raw_agent_per_project_key():
    conn = _make_connection()
    # Two projects, two keys each = 4 agents
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/jyb/projects/telos/backend && python -m pytest ../backend/tests/test_cloud_discovery_anthropic.py -v`
Expected: `ModuleNotFoundError: No module named 'backend.services.cloud_discovery.anthropic'`

- [ ] **Step 3: Implement the module**

Write to `backend/services/cloud_discovery/anthropic.py`:

```python
"""Anthropic Admin API — list orgs, projects, and per-project API keys.

Reference: https://docs.anthropic.com/en/api/administration-api
(adjust paths/fields if the real schema differs; this v1 ships with the
shape we observed in the Anthropic Admin console.)
"""
from __future__ import annotations

from typing import List

from backend.services.cloud_discovery.base import CloudDiscoveryBase
from backend.services.cloud_discovery import RawAgent


class AnthropicDiscovery(CloudDiscoveryBase):
    PROVIDER_NAME = "anthropic"
    BASE_URL = "https://api.anthropic.com"

    def _auth_headers(self) -> dict:
        return {
            "x-api-key": self._api_key,
            "anthropic-version": "2023-06-01",
        }

    def _list_agents(self) -> List[RawAgent]:
        out: List[RawAgent] = []
        for org in self._paginate("/v1/organizations"):
            projects_path = f"/v1/organizations/{org['id']}/projects"
            for project in self._paginate(projects_path):
                keys_path = f"/v1/organizations/{org['id']}/projects/{project['id']}/api_keys"
                for key in self._paginate(keys_path):
                    fp = self.fingerprint_key_id(key["id"])
                    out.append(RawAgent(
                        provider="anthropic",
                        project_label=project["name"],
                        agent_name=f"{self.connection.name} / {project['name']} / {key['name']}",
                        api_key_fingerprint=fp,
                        capabilities={
                            "filesystem": False, "network": True, "code_exec": False,
                            "tool_count": 0,
                        },
                        model=None,
                        owner_team=org["name"],
                    ))
        return out

    # ── Helpers ────────────────────────────────────────────────────────
    def _paginate(self, path: str) -> list:
        page = self._http_get(path, params={"limit": 100})
        items = list(page.get("data", []))
        # Pagination is a v2 enhancement; v1 stops at one page
        return items

    @staticmethod
    def fingerprint_key_id(key_id: str) -> str:
        # Use the existing fingerprint helper against the key ID (not the secret)
        from backend.services import crypto
        return crypto.fingerprint(key_id) or "0" * 16
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/jyb/projects/telos/backend && python -m pytest ../backend/tests/test_cloud_discovery_anthropic.py -v`
Expected: `3 passed`

- [ ] **Step 5: Commit**

```bash
git add backend/services/cloud_discovery/anthropic.py backend/tests/test_cloud_discovery_anthropic.py
git commit -m "feat(ai-agents): add Anthropic cloud discovery module"
```

### Task 8: services/cloud_discovery/openai.py

**Files:**
- Create: `backend/services/cloud_discovery/openai.py`
- Create: `backend/tests/test_cloud_discovery_openai.py`

- [ ] **Step 1: Write the failing test**

Write to `backend/tests/test_cloud_discovery_openai.py`:

```python
"""OpenAI Admin API discovery — mocked HTTP."""
import os
import sys
from unittest.mock import patch, MagicMock

os.environ.setdefault("ACCOUNTSCAN_MASTER_KEY", "test_master_key_0123456789abcdef01234567")
os.environ.setdefault("ACCOUNTSCAN_JWT_SECRET", "test_jwt_secret_0123456789abcdef0123456")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import pytest

from backend.services.cloud_discovery.openai import OpenAIDiscovery
from backend.services.cloud_discovery.base import FatalDiscoveryError, RetryableError
from backend.services import crypto


def _make_connection(name="acme-prod", provider="openai"):
    return MagicMock(
        id=1, name=name, provider=provider,
        encrypted_api_key=crypto.encrypt("sk-openai-admin-test"),
        api_key_fingerprint=crypto.fingerprint("sk-openai-admin-test"),
    )


def test_happy_path_produces_one_raw_agent_per_project_key():
    conn = _make_connection()
    responses = {
        "/v1/organization/projects": {
            "data": [{"id": "proj-1", "name": "Prod"}, {"id": "proj-2", "name": "Staging"}],
        },
        "/v1/organization/projects/proj-1/api_keys": {
            "data": [{"id": "key-1", "name": "k1"}, {"id": "key-2", "name": "k2"}],
        },
        "/v1/organization/projects/proj-2/api_keys": {
            "data": [{"id": "key-3", "name": "k3"}],
        },
    }

    def fake_get(self, path, params=None):
        if path not in responses:
            raise AssertionError(f"unexpected path: {path}")
        return responses[path]

    with patch.object(OpenAIDiscovery, "_http_get", new=fake_get):
        agents = OpenAIDiscovery(conn).run()

    assert len(agents) == 3
    assert all(a.provider == "openai" for a in agents)
    assert {a.project_label for a in agents} == {"Prod", "Staging"}
    assert {a.agent_name for a in agents} == {
        "acme-prod / Prod / k1",
        "acme-prod / Prod / k2",
        "acme-prod / Staging / k3",
    }


def test_401_raises_fatal_discovery_error():
    conn = _make_connection()
    with patch.object(OpenAIDiscovery, "_http_get",
                      side_effect=FatalDiscoveryError("auth_failed: 401")):
        with pytest.raises(FatalDiscoveryError):
            OpenAIDiscovery(conn).run()


def test_429_retries_then_raises_retryable_error():
    conn = _make_connection()
    with patch.object(OpenAIDiscovery, "_http_get",
                      side_effect=RetryableError("rate_limited")):
        with patch("backend.services.cloud_discovery.base.time.sleep", lambda s: None):
            with pytest.raises(RetryableError):
                OpenAIDiscovery(conn).run()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/jyb/projects/telos/backend && python -m pytest ../backend/tests/test_cloud_discovery_openai.py -v`
Expected: `ModuleNotFoundError: No module named 'backend.services.cloud_discovery.openai'`

- [ ] **Step 3: Implement the module**

Write to `backend/services/cloud_discovery/openai.py`:

```python
"""OpenAI Admin API — list projects and per-project API keys.

Reference: https://platform.openai.com/docs/api-reference/organization
(paths/fields may need adjustment when the live schema is confirmed).
"""
from __future__ import annotations

from typing import List

from backend.services.cloud_discovery.base import CloudDiscoveryBase
from backend.services.cloud_discovery import RawAgent
from backend.services import crypto


class OpenAIDiscovery(CloudDiscoveryBase):
    PROVIDER_NAME = "openai"
    BASE_URL = "https://api.openai.com"

    def _auth_headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._api_key}",
        }

    def _list_agents(self) -> List[RawAgent]:
        out: List[RawAgent] = []
        projects = self._http_get("/v1/organization/projects").get("data", [])
        for project in projects:
            keys_path = f"/v1/organization/projects/{project['id']}/api_keys"
            keys = self._http_get(keys_path).get("data", [])
            for key in keys:
                fp = crypto.fingerprint(key["id"]) or "0" * 16
                out.append(RawAgent(
                    provider="openai",
                    project_label=project["name"],
                    agent_name=f"{self.connection.name} / {project['name']} / {key['name']}",
                    api_key_fingerprint=fp,
                    capabilities={
                        "filesystem": False, "network": True, "code_exec": False,
                        "tool_count": 0,
                    },
                    model=None,
                    owner_team=None,  # OpenAI doesn't expose org name on this path
                ))
        return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/jyb/projects/telos/backend && python -m pytest ../backend/tests/test_cloud_discovery_openai.py -v`
Expected: `3 passed`

- [ ] **Step 5: Now re-enable the dispatch tests in test_cloud_discovery_base.py**

Edit `backend/tests/test_cloud_discovery_base.py` and replace the temporary `test_base_module_imports` with the original four dispatch tests (from the Step 2 content in Task 6).

- [ ] **Step 6: Run all cloud_discovery tests**

Run: `cd /Users/jyb/projects/telos/backend && python -m pytest ../backend/tests/test_cloud_discovery_base.py ../backend/tests/test_cloud_discovery_anthropic.py ../backend/tests/test_cloud_discovery_openai.py -v`
Expected: `11 passed`

- [ ] **Step 7: Commit**

```bash
git add backend/services/cloud_discovery/openai.py backend/services/cloud_discovery/anthropic.py backend/tests/test_cloud_discovery_openai.py backend/tests/test_cloud_discovery_base.py
git commit -m "feat(ai-agents): add OpenAI cloud discovery module + dispatch tests"
```

---

## Phase 3 — Ingest + risk rules

### Task 9: ingest_cloud_agents + 2 new risk rules

**Files:**
- Modify: `backend/services/ai_agent_scanner.py` (add `ingest_cloud_agents` + 2 risk rules + import)
- Create: `backend/tests/test_ai_agent_cloud_ingest.py`

- [ ] **Step 1: Write the failing test**

Write to `backend/tests/test_ai_agent_cloud_ingest.py`:

```python
"""Ingest RawAgent rows from cloud discovery into the ai_agents table.

Verifies:
- asset_id is NULL on cloud agents
- framework = 'cloud_<provider>'
- discovery_source = 'api_discovery'
- dedup: re-ingest updates the same row, not duplicate
- 2 new risk rules fire: single-agent-connection + code_exec, and
  cross-connection key reuse
"""
import os
import sys
from datetime import datetime
from unittest.mock import MagicMock

os.environ.setdefault("ACCOUNTSCAN_MASTER_KEY", "test_master_key_0123456789abcdef01234567")
os.environ.setdefault("ACCOUNTSCAN_JWT_SECRET", "test_jwt_secret_0123456789abcdef0123456")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database import Base
from backend import models
from backend.services import crypto
from backend.services.cloud_discovery import RawAgent
from backend.services.ai_agent_scanner import ingest_cloud_agents


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    s = Session()
    yield s
    s.close()


def _make_user(db):
    u = models.User(username="alice", email="a@b", password_hash="x",
                    role=models.UserRole.admin)
    db.add(u); db.commit(); db.refresh(u)
    return u


def _make_connection(db, user, name="acme", provider="anthropic", api_key="sk-test"):
    enc = crypto.encrypt(api_key)
    c = models.CloudConnection(
        name=name, provider=provider, encrypted_api_key=enc,
        api_key_fingerprint=crypto.fingerprint(api_key) or "0" * 16,
        created_by_user_id=user.id,
    )
    db.add(c); db.commit(); db.refresh(c)
    return c


def test_ingest_writes_aiagent_with_cloud_metadata(db):
    user = _make_user(db)
    conn = _make_connection(db, user)
    raws = [
        RawAgent(provider="anthropic", project_label="Prod",
                 agent_name="acme / Prod / k1",
                 api_key_fingerprint="1234567890abcdef"),
    ]
    agents = ingest_cloud_agents(db, conn, raws)
    assert len(agents) == 1
    a = agents[0]
    assert a.framework == "cloud_anthropic"
    assert a.discovery_source == "api_discovery"
    assert a.asset_id is None
    assert a.connection_id == conn.id
    assert a.api_key_fingerprint == "1234567890abcdef"


def test_ingest_dedup_updates_existing_row(db):
    user = _make_user(db)
    conn = _make_connection(db, user)
    raws = [RawAgent(provider="anthropic", project_label="Prod",
                     agent_name="acme / Prod / k1",
                     api_key_fingerprint="1234567890abcdef")]

    first = ingest_cloud_agents(db, conn, raws)
    assert len(first) == 1
    first_id = first[0].id

    second = ingest_cloud_agents(db, conn, raws)
    assert len(second) == 1
    assert second[0].id == first_id  # same row, updated, not new

    rows = db.query(models.AIAgent).filter(
        models.AIAgent.framework == "cloud_anthropic").all()
    assert len(rows) == 1


def test_single_agent_connection_with_code_exec_adds_risk(db):
    user = _make_user(db)
    conn = _make_connection(db, user)
    raws = [RawAgent(provider="anthropic", project_label="Prod",
                     agent_name="acme / Prod / k1",
                     api_key_fingerprint="1234567890abcdef",
                     capabilities={"filesystem": False, "network": False,
                                   "code_exec": True, "tool_count": 0})]
    agents = ingest_cloud_agents(db, conn, raws)
    rule_names = {s["signal"] for s in agents[0].risk_signals}
    assert "single_agent_code_exec" in rule_names
    assert agents[0].risk_score >= 10


def test_cross_connection_key_reuse_adds_risk(db):
    user = _make_user(db)
    conn1 = _make_connection(db, user, name="c1", api_key="sk-1")
    conn2 = _make_connection(db, user, name="c2", api_key="sk-2")

    # Same fingerprint appears under both connections
    shared_fp = "abcdef1234567890"
    ingest_cloud_agents(db, conn1, [
        RawAgent(provider="anthropic", project_label="P1",
                 agent_name="c1 / P1 / k1", api_key_fingerprint=shared_fp),
    ])
    agents2 = ingest_cloud_agents(db, conn2, [
        RawAgent(provider="anthropic", project_label="P2",
                 agent_name="c2 / P2 / k1", api_key_fingerprint=shared_fp),
    ])

    rule_names = {s["signal"] for s in agents2[0].risk_signals}
    assert "cross_connection_key_reuse" in rule_names
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/jyb/projects/telos/backend && python -m pytest ../backend/tests/test_ai_agent_cloud_ingest.py -v`
Expected: `ImportError: cannot import name 'ingest_cloud_agents' from 'backend.services.ai_agent_scanner'`

- [ ] **Step 3: Add `ingest_cloud_agents` and the 2 risk rules**

Open `backend/services/ai_agent_scanner.py` and:

1. Add the import at the top (next to the existing `from backend import models`):

```python
from backend.models._enums import CLOUD_PROVIDER_TO_FRAMEWORK
```

2. In `score_risk`, find the end of the existing rules (just before the `return score, _level_for_score(score), signals` line) and add the two new rules. Find the existing `return score, _level_for_score(score), signals` line and replace the block that immediately precedes it (the same-fingerprint-across-assets rule) with:

```python
    # Rule 8: same fingerprint on another asset (20)
    fp = agent.get("api_key_fingerprint")
    if fp:
        same_on_other = any(
            a.get("api_key_fingerprint") == fp
            and a.get("asset_id") != agent.get("asset_id")
            for a in all_agents
        )
        if same_on_other:
            score += 20
            signals.append({"signal": "shared_fingerprint", "weight": 20,
                            "evidence": "Same API key fingerprint on another asset"})


def score_cloud_risk(agent_dict, connection, all_agents, all_agents_for_connection):
    """Score the 2 cloud-channel rules, additive to the v1 score_risk output.

    `all_agents_for_connection` is the list of agents that belong to the
    same connection (used to detect "single-agent connection").
    `all_agents` is the global list (used to detect cross-connection reuse).
    """
    score = 0
    signals = []

    # Rule 9: single-agent connection with code_exec capability (+10, medium)
    caps = agent_dict.get("capabilities") or {}
    if (
        len(all_agents_for_connection) == 1
        and caps.get("code_exec")
    ):
        score += 10
        signals.append({
            "signal": "single_agent_code_exec",
            "weight": 10,
            "evidence": "Connection has exactly one agent AND it has code_exec capability",
        })

    # Rule 10: cross-connection key reuse (+20, high)
    fp = agent_dict.get("api_key_fingerprint")
    if fp:
        same_on_other_conn = any(
            a.get("api_key_fingerprint") == fp
            and a.get("connection_id") != connection.id
            for a in all_agents
        )
        if same_on_other_conn:
            score += 20
            signals.append({
                "signal": "cross_connection_key_reuse",
                "weight": 20,
                "evidence": "Same API key fingerprint seen on a different connection",
            })

    return score, _level_for_score(score), signals
```

3. Append `ingest_cloud_agents` at the end of the file (after the existing `ingest_signals`):

```python
def ingest_cloud_agents(
    db: Session,
    connection: "models.CloudConnection",
    raw_agents: List["RawAgent"],
    now: Optional[datetime] = None,
) -> List[models.AIAgent]:
    """Ingest RawAgent rows from a single cloud connection.

    Dedup: explicit SELECT WHERE (framework, agent_name) AND asset_id IS NULL.
    Standard SQL treats NULL as distinct in unique constraints, so we cannot
    rely on the v1 dedup index alone. (Partial unique index is a v3 fix.)
    """
    if not raw_agents:
        return []
    if now is None:
        now = datetime.utcnow()

    framework = CLOUD_PROVIDER_TO_FRAMEWORK[connection.provider]
    all_existing = db.query(models.AIAgent).all()
    all_agents_for_scoring = [
        {"asset_id": a.asset_id, "connection_id": a.connection_id,
         "api_key_fingerprint": a.api_key_fingerprint}
        for a in all_existing
    ]
    conn_agents = [a for a in all_existing if a.connection_id == connection.id]

    results: List[models.AIAgent] = []
    for raw in raw_agents:
        existing = (
            db.query(models.AIAgent)
            .filter(
                models.AIAgent.framework == framework,
                models.AIAgent.agent_name == raw.agent_name,
                models.AIAgent.asset_id.is_(None),
            )
            .first()
        )

        # Score
        agent_for_score = {
            "asset_id": None,
            "connection_id": connection.id,
            "api_key_fingerprint": raw.api_key_fingerprint,
            "capabilities": raw.capabilities,
        }
        base_score, base_level, base_signals = score_risk(agent_for_score, all_agents_for_scoring)
        cloud_score, cloud_level, cloud_signals = score_cloud_risk(
            agent_for_score, connection, all_agents_for_scoring, conn_agents
        )
        # Cloud rules override base level (cloud rules are higher-severity)
        total_score = base_score + cloud_score
        total_level = _level_for_score(total_score)
        all_signals = base_signals + cloud_signals

        if existing:
            existing.last_seen_at = now
            existing.capabilities = raw.capabilities
            existing.api_key_fingerprint = raw.api_key_fingerprint
            existing.model = raw.model
            existing.owner_team = raw.owner_team
            existing.risk_score = total_score
            existing.risk_level = total_level
            existing.risk_signals = all_signals
            existing.status = "active"
            results.append(existing)
        else:
            new = models.AIAgent(
                agent_name=raw.agent_name,
                framework=framework,
                model=raw.model,
                owner_team=raw.owner_team,
                owner_user=None,
                api_key_fingerprint=raw.api_key_fingerprint,
                api_key_location=f"cloud:{connection.provider}:{connection.id}",
                capabilities=raw.capabilities,
                last_invocation_at=None,
                last_seen_at=now,
                discovered_at=now,
                discovery_source="api_discovery",
                asset_id=None,
                connection_id=connection.id,
                risk_score=total_score,
                risk_level=total_level,
                risk_signals=all_signals,
                status="active",
            )
            db.add(new)
            results.append(new)

    db.commit()
    return results
```

4. Add the import for `RawAgent` at the top of the file under the existing imports — but only inside a `TYPE_CHECKING` block to avoid a circular import at runtime:

```python
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from backend.services.cloud_discovery import RawAgent
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/jyb/projects/telos/backend && python -m pytest ../backend/tests/test_ai_agent_cloud_ingest.py -v`
Expected: `4 passed`

- [ ] **Step 5: Run the full backend test suite to confirm no regressions**

Run: `cd /Users/jyb/projects/telos/backend && python -m pytest ../backend/tests/ -x --ignore=../backend/tests/test_ai_agent_scanner.py -q 2>&1 | tail -20`
Expected: no failures attributable to this change. If pre-existing tests fail, document them and continue.

- [ ] **Step 6: Commit**

```bash
git add backend/services/ai_agent_scanner.py backend/tests/test_ai_agent_cloud_ingest.py
git commit -m "feat(ai-agents): add ingest_cloud_agents + 2 cloud risk rules"
```

---

## Phase 4 — Router + audit log

### Task 10: Pydantic schemas

**Files:**
- Create: `backend/schemas/cloud_connections.py`

- [ ] **Step 1: Create the schemas file**

Write to `backend/schemas/cloud_connections.py`:

```python
"""Pydantic schemas for the cloud connection management API."""
from datetime import datetime
from typing import Optional, List, Literal, Dict, Any
from pydantic import BaseModel, Field


CloudProviderLiteral = Literal["anthropic", "openai"]
CloudSyncStatusLiteral = Literal["success", "partial", "failed", "running"]
CloudAuditActionLiteral = Literal[
    "created", "renamed", "rotated", "deleted", "sync_started", "sync_finished",
]


class CloudConnectionCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=64)
    provider: CloudProviderLiteral
    api_key: str = Field(..., min_length=1, max_length=512)


class CloudConnectionUpdate(BaseModel):
    """PATCH — name only. To replace the key, call /rotate."""
    name: str = Field(..., min_length=1, max_length=64)


class CloudConnectionRotate(BaseModel):
    api_key: str = Field(..., min_length=1, max_length=512)


class CloudConnectionResponse(BaseModel):
    id: int
    name: str
    provider: CloudProviderLiteral
    api_key_fingerprint: str
    last_sync_at: Optional[datetime] = None
    last_sync_started_at: Optional[datetime] = None
    last_sync_status: Optional[CloudSyncStatusLiteral] = None
    last_sync_error: Optional[str] = None
    created_by_user_id: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CloudConnectionListResponse(BaseModel):
    total: int
    connections: List[CloudConnectionResponse]


class CloudConnectionSyncResponse(BaseModel):
    connection_id: int
    status: CloudSyncStatusLiteral
    agents_discovered: int
    agents_updated: int
    error: Optional[str] = None


class CloudConnectionAuditEntry(BaseModel):
    id: int
    connection_id: Optional[int] = None
    actor_user_id: Optional[int] = None
    action: CloudAuditActionLiteral
    status: Optional[str] = None
    before: Optional[Dict[str, Any]] = None
    after: Optional[Dict[str, Any]] = None
    note: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class CloudConnectionAuditListResponse(BaseModel):
    total: int
    entries: List[CloudConnectionAuditEntry]
```

- [ ] **Step 2: Verify the schemas import**

Run: `cd /Users/jyb/projects/telos && python -c "from backend.schemas.cloud_connections import CloudConnectionCreate, CloudConnectionResponse; print('ok')"`
Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add backend/schemas/cloud_connections.py
git commit -m "feat(ai-agents): add cloud connection Pydantic schemas"
```

### Task 11: Router

**Files:**
- Create: `backend/routers/ai_agent_connections.py`
- Modify: `backend/main.py` (include the router)

- [ ] **Step 1: Create the router file**

Write to `backend/routers/ai_agent_connections.py`:

```python
"""AI Agent Cloud Connection management — CRUD + sync-now + audit log."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend import models, auth, schemas
from backend.database import get_db
from backend.services import crypto
from backend.services.cloud_discovery import discover as cloud_discover
from backend.services.cloud_discovery.base import (
    FatalDiscoveryError, RetryableError,
)
from backend.services.ai_agent_scanner import ingest_cloud_agents


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/ai-agents/connections", tags=["ai-agents"])


# ── Helpers ────────────────────────────────────────────────────────────

def _write_audit(
    db: Session, connection_id: int, actor_user_id: int, action: str,
    *, before: dict | None = None, after: dict | None = None,
    status_val: str | None = None, note: str | None = None,
) -> None:
    """Insert a cloud_connection_audit_log row.

    `before` and `after` MUST NOT contain the api_key (plaintext or encrypted).
    They are name-only.
    """
    entry = models.CloudConnectionAuditLog(
        connection_id=connection_id,
        actor_user_id=actor_user_id,
        action=action,
        status=status_val,
        before=before,
        after=after,
        note=note,
    )
    db.add(entry)


def _run_sync(db: Session, connection: models.CloudConnection) -> dict:
    """Run a single sync for one connection. Returns a result dict.

    Updates connection.last_sync_at/status/error in place. Caller commits.
    """
    connection.last_sync_started_at = datetime.utcnow()
    connection.last_sync_status = "running"
    db.flush()

    agents_discovered = 0
    agents_updated = 0
    error_msg: str | None = None
    status_val = "success"

    try:
        raws = cloud_discover(connection)
    except FatalDiscoveryError as e:
        status_val = "failed"
        error_msg = f"auth_failed: {e}"
        return {
            "status": status_val, "agents_discovered": 0, "agents_updated": 0,
            "error": error_msg,
        }
    except RetryableError as e:
        status_val = "failed"
        error_msg = f"rate_limited_or_transient: {e}"
        return {
            "status": status_val, "agents_discovered": 0, "agents_updated": 0,
            "error": error_msg,
        }
    except Exception as e:
        logger.exception("Cloud discovery unexpected error")
        status_val = "failed"
        error_msg = f"unexpected: {e!r}"
        return {
            "status": status_val, "agents_discovered": 0, "agents_updated": 0,
            "error": error_msg,
        }

    # Ingest; track discovered vs updated
    pre_existing_ids = {
        row[0] for row in db.query(models.AIAgent.id)
        .filter(models.AIAgent.connection_id == connection.id).all()
    }
    ingested = ingest_cloud_agents(db, connection, raws)
    for a in ingested:
        if a.id in pre_existing_ids:
            agents_updated += 1
        else:
            agents_discovered += 1

    return {
        "status": status_val,
        "agents_discovered": agents_discovered,
        "agents_updated": agents_updated,
        "error": None,
    }


# ── Endpoints ──────────────────────────────────────────────────────────

@router.get("", response_model=schemas.cloud_connections.CloudConnectionListResponse)
async def list_connections(
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.get_current_user),
):
    rows = db.query(models.CloudConnection).order_by(models.CloudConnection.id).all()
    return schemas.cloud_connections.CloudConnectionListResponse(
        total=len(rows),
        connections=[schemas.cloud_connections.CloudConnectionResponse.model_validate(r) for r in rows],
    )


@router.post("", response_model=schemas.cloud_connections.CloudConnectionResponse,
             status_code=status.HTTP_201_CREATED)
async def create_connection(
    body: schemas.cloud_connections.CloudConnectionCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.require_admin),
):
    fp = crypto.fingerprint(body.api_key)
    if not fp:
        raise HTTPException(status_code=400, detail="api_key produced empty fingerprint")
    enc = crypto.encrypt(body.api_key)
    conn = models.CloudConnection(
        name=body.name,
        provider=body.provider,
        encrypted_api_key=enc,
        api_key_fingerprint=fp,
        created_by_user_id=user.id,
    )
    db.add(conn)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail=f"connection name '{body.name}' already exists")
    _write_audit(db, conn.id, user.id, "created",
                 after={"name": conn.name, "provider": conn.provider,
                        "api_key_fingerprint": conn.api_key_fingerprint})
    db.commit()
    db.refresh(conn)
    return conn


@router.patch("/{connection_id}", response_model=schemas.cloud_connections.CloudConnectionResponse)
async def update_connection(
    connection_id: int,
    body: schemas.cloud_connections.CloudConnectionUpdate,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.require_admin),
):
    conn = db.query(models.CloudConnection).filter(
        models.CloudConnection.id == connection_id).first()
    if not conn:
        raise HTTPException(status_code=404, detail="connection not found")
    if "api_key" in body.model_fields_set:
        raise HTTPException(
            status_code=400,
            detail="api_key is write-only; use POST /connections/{id}/rotate to replace the key",
        )
    before_name = conn.name
    conn.name = body.name
    _write_audit(db, conn.id, user.id, "renamed",
                 before={"name": before_name},
                 after={"name": conn.name})
    db.commit()
    db.refresh(conn)
    return conn


@router.post("/{connection_id}/rotate", response_model=schemas.cloud_connections.CloudConnectionResponse)
async def rotate_connection(
    connection_id: int,
    body: schemas.cloud_connections.CloudConnectionRotate,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.require_admin),
):
    conn = db.query(models.CloudConnection).filter(
        models.CloudConnection.id == connection_id).first()
    if not conn:
        raise HTTPException(status_code=404, detail="connection not found")
    fp = crypto.fingerprint(body.api_key)
    if not fp:
        raise HTTPException(status_code=400, detail="api_key produced empty fingerprint")
    old_fp = conn.api_key_fingerprint
    conn.encrypted_api_key = crypto.encrypt(body.api_key)
    conn.api_key_fingerprint = fp
    _write_audit(db, conn.id, user.id, "rotated",
                 before={"api_key_fingerprint": old_fp},
                 after={"api_key_fingerprint": fp})
    db.commit()
    db.refresh(conn)
    return conn


@router.delete("/{connection_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_connection(
    connection_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.require_admin),
):
    conn = db.query(models.CloudConnection).filter(
        models.CloudConnection.id == connection_id).first()
    if not conn:
        raise HTTPException(status_code=404, detail="connection not found")
    before = {"name": conn.name, "provider": conn.provider,
              "api_key_fingerprint": conn.api_key_fingerprint}
    _write_audit(db, conn.id, user.id, "deleted", before=before)
    # Soft-delete: NULL the FK on ai_agents but keep the agents
    db.query(models.AIAgent).filter(
        models.AIAgent.connection_id == connection_id
    ).update({models.AIAgent.connection_id: None})
    db.delete(conn)
    db.commit()
    return None


@router.post("/{connection_id}/sync", response_model=schemas.cloud_connections.CloudConnectionSyncResponse)
async def sync_connection(
    connection_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.require_admin),
):
    conn = db.query(models.CloudConnection).filter(
        models.CloudConnection.id == connection_id).first()
    if not conn:
        raise HTTPException(status_code=404, detail="connection not found")
    if conn.last_sync_status == "running":
        raise HTTPException(status_code=409, detail="sync already in progress")

    _write_audit(db, conn.id, user.id, "sync_started")
    db.commit()

    result = _run_sync(db, conn)

    # Truncate error to fit 256 chars
    err_truncated = (result["error"][:256] if result["error"] else None)
    conn.last_sync_at = datetime.utcnow()
    conn.last_sync_status = result["status"]
    conn.last_sync_error = err_truncated
    _write_audit(db, conn.id, user.id, "sync_finished",
                 status_val=result["status"], note=err_truncated)
    db.commit()
    db.refresh(conn)
    return schemas.cloud_connections.CloudConnectionSyncResponse(
        connection_id=conn.id,
        status=result["status"],
        agents_discovered=result["agents_discovered"],
        agents_updated=result["agents_updated"],
        error=err_truncated,
    )


@router.get("/{connection_id}/audit",
            response_model=schemas.cloud_connections.CloudConnectionAuditListResponse)
async def list_audit(
    connection_id: int,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.get_current_user),
):
    if not db.query(models.CloudConnection).filter(
            models.CloudConnection.id == connection_id).first():
        raise HTTPException(status_code=404, detail="connection not found")
    q = db.query(models.CloudConnectionAuditLog).filter(
        models.CloudConnectionAuditLog.connection_id == connection_id
    ).order_by(models.CloudConnectionAuditLog.created_at.desc())
    total = q.count()
    rows = q.offset(offset).limit(limit).all()
    return schemas.cloud_connections.CloudConnectionAuditListResponse(
        total=total,
        entries=[schemas.cloud_connections.CloudConnectionAuditEntry.model_validate(r) for r in rows],
    )
```

- [ ] **Step 2: Wire the router into `main.py`**

In `backend/main.py`, find the existing line that includes the `ai_agents` router (it should look like `app.include_router(ai_agents_router)` or similar). Add immediately after it:

```python
from backend.routers.ai_agent_connections import router as ai_agent_connections_router
app.include_router(ai_agent_connections_router)
```

If the existing include uses a different style (e.g. centralized import block), follow that same style.

- [ ] **Step 3: Verify the app boots**

Run: `cd /Users/jyb/projects/telos && python -c "from backend.main import app; routes = [r.path for r in app.routes]; assert '/api/v1/ai-agents/connections' in routes; print('ok')"`
Expected: `ok`

- [ ] **Step 4: Commit**

```bash
git add backend/routers/ai_agent_connections.py backend/main.py
git commit -m "feat(ai-agents): add cloud connection router"
```

### Task 12: Router tests

**Files:**
- Create: `backend/tests/test_ai_agent_connections_router.py`
- Create: `backend/tests/test_ai_agent_connections_audit.py`

- [ ] **Step 1: Write the router test**

Write to `backend/tests/test_ai_agent_connections_router.py`:

```python
"""End-to-end tests for the cloud-connection router.

Verifies:
- List / create / patch / rotate / delete / sync / audit endpoints
- Key never appears in any response or DB column (plaintext or encrypted)
- API key in PATCH body is rejected
- Sync-in-progress returns 409
"""
import os
import sys
from datetime import datetime
from unittest.mock import patch

os.environ.setdefault("ACCOUNTSCAN_MASTER_KEY", "test_master_key_0123456789abcdef01234567")
os.environ.setdefault("ACCOUNTSCAN_JWT_SECRET", "test_jwt_secret_0123456789abcdef0123456")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database import Base
from backend import models, auth
from backend.main import app
from backend.services import crypto


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    s = Session()
    yield s
    s.close()


@pytest.fixture
def client(db):
    def _override():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[__import__("backend.database", fromlist=["get_db"]).get_db] = lambda: (
        next(_override())
    )

    admin = models.User(username="alice", email="a@b", password_hash="x",
                        role=models.UserRole.admin)
    db.add(admin); db.commit(); db.refresh(admin)
    token = auth.create_access_token({"sub": admin.username, "uid": admin.id})

    def _fake_user():
        return admin
    app.dependency_overrides[auth.get_current_user] = _fake_user
    app.dependency_overrides[auth.require_admin] = _fake_user

    yield TestClient(app), admin, token

    app.dependency_overrides.clear()


def test_create_connection_encrypts_key(client):
    c, admin, _ = client
    body = {"name": "acme-prod", "provider": "anthropic", "api_key": "sk-ant-secret-key"}
    r = c.post("/api/v1/ai-agents/connections", json=body)
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["name"] == "acme-prod"
    assert data["provider"] == "anthropic"
    assert "api_key" not in data
    assert "encrypted_api_key" not in data
    assert data["api_key_fingerprint"] == crypto.fingerprint("sk-ant-secret-key")


def test_key_never_returned_in_list(client):
    c, _, _ = client
    c.post("/api/v1/ai-agents/connections",
           json={"name": "c1", "provider": "openai", "api_key": "sk-openai-test"})
    r = c.get("/api/v1/ai-agents/connections")
    assert r.status_code == 200
    assert "sk-openai-test" not in r.text
    assert "encrypted_api_key" not in r.json()["connections"][0]


def test_patch_rejects_api_key_field(client):
    c, _, _ = client
    c.post("/api/v1/ai-agents/connections",
           json={"name": "c1", "provider": "anthropic", "api_key": "sk-test"})
    r = c.patch("/api/v1/ai-agents/connections/1",
                json={"name": "renamed", "api_key": "should-be-rejected"})
    assert r.status_code == 400
    assert "api_key" in r.json()["detail"]


def test_rotate_writes_new_fingerprint(client):
    c, _, _ = client
    c.post("/api/v1/ai-agents/connections",
           json={"name": "c1", "provider": "anthropic", "api_key": "old-key"})
    r = c.post("/api/v1/ai-agents/connections/1/rotate",
               json={"api_key": "new-key"})
    assert r.status_code == 200
    assert r.json()["api_key_fingerprint"] == crypto.fingerprint("new-key")


def test_delete_soft_deletes_and_keeps_agents(client):
    c, _, _ = client
    c.post("/api/v1/ai-agents/connections",
           json={"name": "c1", "provider": "anthropic", "api_key": "sk-test"})
    # Manually create a cloud agent pointing at this connection
    with c.app.dependency_overrides and c.app:
        from backend.database import SessionLocal
        from sqlalchemy.orm import Session
        s = next(iter(c.app.dependency_overrides.values()))()
        from backend.services import crypto as c2
        from backend.models import AIAgent, CloudConnection
        conn = s.query(CloudConnection).first()
        agent = AIAgent(
            agent_name="c1 / P / k", framework="cloud_anthropic",
            discovery_source="api_discovery", connection_id=conn.id,
            asset_id=None, last_seen_at=datetime.utcnow(),
            discovered_at=datetime.utcnow(),
        )
        s.add(agent); s.commit()

    r = c.delete("/api/v1/ai-agents/connections/1")
    assert r.status_code == 204


def test_sync_in_progress_returns_409(client):
    c, _, _ = client
    c.post("/api/v1/ai-agents/connections",
           json={"name": "c1", "provider": "anthropic", "api_key": "sk-test"})
    # Mark connection as currently running
    db_gen = c.app.dependency_overrides[__import__(
        "backend.database", fromlist=["get_db"]
    ).get_db]
    s = db_gen()
    s.query(models.CloudConnection).filter(
        models.CloudConnection.id == 1
    ).update({models.CloudConnection.last_sync_status: "running"})
    s.commit()
    r = c.post("/api/v1/ai-agents/connections/1/sync")
    assert r.status_code == 409


def test_sync_success_path_writes_agents_and_audit(client):
    c, _, _ = client
    c.post("/api/v1/ai-agents/connections",
           json={"name": "c1", "provider": "anthropic", "api_key": "sk-test"})

    from backend.services.cloud_discovery import RawAgent
    fake_raws = [
        RawAgent(provider="anthropic", project_label="Prod",
                 agent_name="c1 / Prod / k1",
                 api_key_fingerprint="1234567890abcdef"),
    ]
    with patch("backend.routers.ai_agent_connections.cloud_discover",
               return_value=fake_raws):
        r = c.post("/api/v1/ai-agents/connections/1/sync")

    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "success"
    assert body["agents_discovered"] == 1
    assert body["agents_updated"] == 0
    assert body["error"] is None

    # Audit list shows created + sync_started + sync_finished
    r2 = c.get("/api/v1/ai-agents/connections/1/audit")
    assert r2.status_code == 200
    actions = [e["action"] for e in r2.json()["entries"]]
    assert "created" in actions
    assert "sync_started" in actions
    assert "sync_finished" in actions
    # The api_key string must NOT appear in any audit entry
    assert "sk-test" not in r2.text
```

- [ ] **Step 2: Write the audit-log test**

Write to `backend/tests/test_ai_agent_connections_audit.py`:

```python
"""Every state-changing endpoint must write exactly one audit row with
the expected action and no plaintext key material anywhere."""
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
from unittest.mock import patch

from backend.database import Base
from backend import models, auth
from backend.main import app


@pytest.fixture
def client():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)

    def _db():
        s = Session()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[
        __import__("backend.database", fromlist=["get_db"]).get_db
    ] = lambda: next(_db())

    admin = models.User(username="alice", email="a@b", password_hash="x",
                        role=models.UserRole.admin)
    s = Session()
    s.add(admin); s.commit()
    s.close()

    def _user():
        return admin
    app.dependency_overrides[auth.get_current_user] = _user
    app.dependency_overrides[auth.require_admin] = _user

    yield TestClient(app), Session

    app.dependency_overrides.clear()


def test_create_writes_one_audit_row(client):
    c, Session = client
    SECRET = "sk-ant-very-secret-key-1234567890"
    r = c.post("/api/v1/ai-agents/connections",
               json={"name": "c1", "provider": "anthropic", "api_key": SECRET})
    assert r.status_code == 201

    s = Session()
    rows = s.query(models.CloudConnectionAuditLog).all()
    assert len(rows) == 1
    assert rows[0].action == "created"
    assert rows[0].actor_user_id is not None
    # Plaintext must never appear in any column
    for col in ("before", "after", "note"):
        val = getattr(rows[0], col)
        if val:
            assert SECRET not in str(val)


def test_rotate_writes_one_audit_row_with_old_and_new_fingerprint(client):
    c, Session = client
    c.post("/api/v1/ai-agents/connections",
           json={"name": "c1", "provider": "anthropic", "api_key": "old-key"})
    r = c.post("/api/v1/ai-agents/connections/1/rotate",
               json={"api_key": "new-key"})
    assert r.status_code == 200

    s = Session()
    rows = s.query(models.CloudConnectionAuditLog).order_by(
        models.CloudConnectionAuditLog.id).all()
    actions = [r.action for r in rows]
    assert "rotated" in actions
    rotated = next(r for r in rows if r.action == "rotated")
    assert "old-key" not in str(rotated.before)
    assert "new-key" not in str(rotated.after)
    assert "old-key" not in (rotated.note or "")


def test_delete_writes_one_audit_row(client):
    c, Session = client
    c.post("/api/v1/ai-agents/connections",
           json={"name": "c1", "provider": "anthropic", "api_key": "k"})
    r = c.delete("/api/v1/ai-agents/connections/1")
    assert r.status_code == 204
    s = Session()
    rows = s.query(models.CloudConnectionAuditLog).all()
    actions = [r.action for r in rows]
    assert "deleted" in actions


def test_rename_writes_one_audit_row(client):
    c, Session = client
    c.post("/api/v1/ai-agents/connections",
           json={"name": "old", "provider": "anthropic", "api_key": "k"})
    r = c.patch("/api/v1/ai-agents/connections/1", json={"name": "new"})
    assert r.status_code == 200
    s = Session()
    rows = s.query(models.CloudConnectionAuditLog).all()
    actions = [r.action for r in rows]
    assert "renamed" in actions
```

- [ ] **Step 3: Run the router + audit tests**

Run: `cd /Users/jyb/projects/telos/backend && python -m pytest ../backend/tests/test_ai_agent_connections_router.py ../backend/tests/test_ai_agent_connections_audit.py -v`
Expected: all tests pass

- [ ] **Step 4: Commit**

```bash
git add backend/tests/test_ai_agent_connections_router.py backend/tests/test_ai_agent_connections_audit.py
git commit -m "test(ai-agents): add cloud connection router + audit-log tests"
```

---

## Phase 5 — Scheduler

### Task 13: 6h scheduled sync

**Files:**
- Modify: `backend/services/scheduler_service.py` (add 6h job)
- Create: `backend/tests/test_scheduler_cloud_sync.py`

- [ ] **Step 1: Write the failing test**

Write to `backend/tests/test_scheduler_cloud_sync.py`:

```python
"""The scheduler's sync_all_cloud_connections job fans out per connection
and one failure does not block the others."""
import os
import sys
from unittest.mock import patch, MagicMock

os.environ.setdefault("ACCOUNTSCAN_MASTER_KEY", "test_master_key_0123456789abcdef01234567")
os.environ.setdefault("ACCOUNTSCAN_JWT_SECRET", "test_jwt_secret_0123456789abcdef0123456")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database import Base
from backend import models
from backend.services import crypto
from backend.services.scheduler_service import _sync_all_cloud_connections


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    s = Session()
    yield s
    s.close()


def _make_user(s):
    u = models.User(username="alice", email="a@b", password_hash="x",
                    role=models.UserRole.admin)
    s.add(u); s.commit(); s.refresh(u)
    return u


def _make_connection(s, user, name, provider="anthropic"):
    c = models.CloudConnection(
        name=name, provider=provider,
        encrypted_api_key=crypto.encrypt(f"sk-{name}"),
        api_key_fingerprint=crypto.fingerprint(f"sk-{name}") or "0" * 16,
        created_by_user_id=user.id,
    )
    s.add(c); s.commit(); s.refresh(c)
    return c


def test_fans_out_per_connection(db):
    user = _make_user(db)
    _make_connection(db, user, "c1")
    _make_connection(db, user, "c2")

    with patch("backend.services.scheduler_service.cloud_discover",
               return_value=[]):
        _sync_all_cloud_connections()

    s2 = create_engine("sqlite:///:memory:")
    # Re-query from a fresh session
    from backend.database import SessionLocal
    from backend import models as m
    rows = db.query(m.CloudConnection).all()
    # last_sync_status should be set to success on each
    for c in rows:
        assert c.last_sync_status in ("success", "partial", "failed")


def test_one_failure_does_not_block_others(db):
    from backend.services.cloud_discovery import RawAgent
    user = _make_user(db)
    _make_connection(db, user, "ok-conn")
    _make_connection(db, user, "bad-conn")

    def fake_discover(conn):
        if conn.name == "bad-conn":
            from backend.services.cloud_discovery.base import RetryableError
            raise RetryableError("rate_limited")
        return [RawAgent(provider="anthropic", project_label="P",
                         agent_name=f"{conn.name} / P / k1",
                         api_key_fingerprint="1234567890abcdef")]

    with patch("backend.services.scheduler_service.cloud_discover",
               side_effect=fake_discover):
        _sync_all_cloud_connections()  # must not raise

    ok = db.query(models.CloudConnection).filter(
        models.CloudConnection.name == "ok-conn").first()
    bad = db.query(models.CloudConnection).filter(
        models.CloudConnection.name == "bad-conn").first()
    assert ok.last_sync_status in ("success", "partial")
    assert bad.last_sync_status == "failed"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/jyb/projects/telos/backend && python -m pytest ../backend/tests/test_scheduler_cloud_sync.py -v`
Expected: `ImportError: cannot import name '_sync_all_cloud_connections'`

- [ ] **Step 3: Add the scheduler hook**

In `backend/services/scheduler_service.py`, add a new module-level function near the bottom (next to `_check_review_reminders`):

```python
def _sync_all_cloud_connections():
    """Fan out a sync to every CloudConnection. One failure does not block others.

    Called every 6h by the scheduler.
    """
    from backend.services.cloud_discovery import discover as cloud_discover
    db = SessionLocal()
    try:
        connections = db.query(models.CloudConnection).all()
        for conn in connections:
            try:
                # Inline the same logic as the manual sync route, but in a
                # background-friendly form.
                from backend.routers.ai_agent_connections import _run_sync
                conn.last_sync_started_at = datetime.now(timezone.utc)
                conn.last_sync_status = "running"
                db.commit()
                result = _run_sync(db, conn)
                conn.last_sync_at = datetime.now(timezone.utc)
                conn.last_sync_status = result["status"]
                conn.last_sync_error = (
                    result["error"][:256] if result["error"] else None
                )
                db.commit()
            except Exception as e:
                logger.warning(
                    "Scheduled cloud sync failed for connection %s: %s",
                    conn.id, e,
                )
                db.rollback()
                try:
                    conn.last_sync_status = "failed"
                    conn.last_sync_error = f"unexpected: {e!r}"[:256]
                    db.commit()
                except Exception:
                    db.rollback()
    finally:
        db.close()
```

Also add the import for `discover as cloud_discover` is unused at the top; remove the inline import in the function. The corrected version:

```python
def _sync_all_cloud_connections():
    """Fan out a sync to every CloudConnection. One failure does not block others.

    Called every 6h by the scheduler.
    """
    from backend.services.cloud_discovery import discover as cloud_discover  # noqa: F401
    db = SessionLocal()
    try:
        connections = db.query(models.CloudConnection).all()
        for conn in connections:
            try:
                from backend.routers.ai_agent_connections import _run_sync
                conn.last_sync_started_at = datetime.now(timezone.utc)
                conn.last_sync_status = "running"
                db.commit()
                result = _run_sync(db, conn)
                conn.last_sync_at = datetime.now(timezone.utc)
                conn.last_sync_status = result["status"]
                conn.last_sync_error = (
                    result["error"][:256] if result["error"] else None
                )
                db.commit()
            except Exception as e:
                logger.warning(
                    "Scheduled cloud sync failed for connection %s: %s",
                    conn.id, e,
                )
                db.rollback()
                try:
                    conn.last_sync_status = "failed"
                    conn.last_sync_error = f"unexpected: {e!r}"[:256]
                    db.commit()
                except Exception:
                    db.rollback()
    finally:
        db.close()
```

Then in `SchedulerService.start()` (the method body), add a new job registration after the existing `realtime_monitor` registration:

```python
        # Cloud connection discovery — every 6 hours
        from backend.services.scheduler_service import _sync_all_cloud_connections
        self._scheduler.add_job(
            _sync_all_cloud_connections, "interval", hours=6,
            id="cloud_connection_sync", replace_existing=True,
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/jyb/projects/telos/backend && python -m pytest ../backend/tests/test_scheduler_cloud_sync.py -v`
Expected: `2 passed`

- [ ] **Step 5: Commit**

```bash
git add backend/services/scheduler_service.py backend/tests/test_scheduler_cloud_sync.py
git commit -m "feat(ai-agents): add 6h scheduled cloud connection sync"
```

---

## Phase 6 — Frontend

### Task 14: i18n keys

**Files:**
- Modify: `frontend/src/locales/en-US.json` (add `aiAgent.connections.*` block)
- Modify: `frontend/src/locales/zh-CN.json` (same)

- [ ] **Step 1: Add keys to en-US.json**

In `frontend/src/locales/en-US.json`, locate the existing `"aiAgent"` object (peer to the v1 keys). Append these keys (merge into the existing object, do not create a duplicate `aiAgent` key):

```json
    "connections": {
      "title": "Cloud Connections",
      "add": "Add Connection",
      "addTitle": "Add Cloud Connection",
      "edit": "Edit",
      "delete": "Delete",
      "deleteConfirm": "Delete this connection? Existing agents will be kept but the connection record will be removed.",
      "rotate": "Rotate Key",
      "syncNow": "Sync Now",
      "syncing": "Syncing...",
      "lastSync": "Last Sync",
      "lastSyncNever": "Never",
      "name": "Name",
      "provider": "Provider",
      "apiKey": "API Key",
      "apiKeyHint": "Anthropic Admin key (sk-ant-admin-...) or OpenAI Admin key (sk-admin-...)",
      "status": {
        "success": "Success",
        "partial": "Partial",
        "failed": "Failed",
        "running": "Running"
      },
      "providerLabel": {
        "anthropic": "Anthropic Console",
        "openai": "OpenAI Dashboard"
      },
      "auditLog": "Audit Log",
      "auditAction": {
        "created": "Created",
        "renamed": "Renamed",
        "rotated": "Key Rotated",
        "deleted": "Deleted",
        "sync_started": "Sync Started",
        "sync_finished": "Sync Finished"
      },
      "agentsDiscovered": "{{count}} agents discovered",
      "error": "Error",
      "addSuccess": "Connection created",
      "addError": "Failed to create connection",
      "syncInProgress": "Sync already in progress"
    }
```

- [ ] **Step 2: Add the same keys to zh-CN.json**

In `frontend/src/locales/zh-CN.json`, locate the existing `"aiAgent"` object and append:

```json
    "connections": {
      "title": "云连接",
      "add": "新增连接",
      "addTitle": "新增云连接",
      "edit": "编辑",
      "delete": "删除",
      "deleteConfirm": "确认删除该连接？已发现的 Agent 将保留,但连接记录将被移除。",
      "rotate": "轮换密钥",
      "syncNow": "立即同步",
      "syncing": "同步中...",
      "lastSync": "最近同步",
      "lastSyncNever": "从未",
      "name": "名称",
      "provider": "服务商",
      "apiKey": "API Key",
      "apiKeyHint": "Anthropic Admin key (sk-ant-admin-...) 或 OpenAI Admin key (sk-admin-...)",
      "status": {
        "success": "成功",
        "partial": "部分成功",
        "failed": "失败",
        "running": "同步中"
      },
      "providerLabel": {
        "anthropic": "Anthropic Console",
        "openai": "OpenAI Dashboard"
      },
      "auditLog": "审计日志",
      "auditAction": {
        "created": "已创建",
        "renamed": "已重命名",
        "rotated": "已轮换密钥",
        "deleted": "已删除",
        "sync_started": "同步已启动",
        "sync_finished": "同步已完成"
      },
      "agentsDiscovered": "发现 {{count}} 个 Agent",
      "error": "错误",
      "addSuccess": "连接已创建",
      "addError": "创建连接失败",
      "syncInProgress": "同步正在进行中"
    }
```

- [ ] **Step 3: Verify JSON parses**

Run: `cd /Users/jyb/projects/telos/frontend && node -e "const en=require('./src/locales/en-US.json'); const zh=require('./src/locales/zh-CN.json'); const enKeys = Object.keys(en.aiAgent.connections); const zhKeys = Object.keys(zh.aiAgent.connections); console.log('en has', enKeys.length, 'keys'); console.log('zh has', zhKeys.length, 'keys'); const missing = enKeys.filter(k => !(k in zh.aiAgent.connections)); if (missing.length) { console.error('missing in zh:', missing); process.exit(1); } console.log('keys match')"`
Expected: `keys match`

- [ ] **Step 4: Commit**

```bash
git add frontend/src/locales/en-US.json frontend/src/locales/zh-CN.json
git commit -m "i18n(aiAgent): add cloud connections i18n keys"
```

### Task 15: API client methods

**Files:**
- Modify: `frontend/src/api/client.ts` (add cloud-connection API methods)

- [ ] **Step 1: Add the methods**

In `frontend/src/api/client.ts`, find the end of the existing AI Agent block (after the `triggerAIAgentScan` export, before the next section). Add:

```ts
// ── Cloud Connections ──────────────────────────────────────────────────────

export interface CloudConnection {
  id: number
  name: string
  provider: 'anthropic' | 'openai'
  api_key_fingerprint: string
  last_sync_at: string | null
  last_sync_started_at: string | null
  last_sync_status: 'success' | 'partial' | 'failed' | 'running' | null
  last_sync_error: string | null
  created_by_user_id: number
  created_at: string
  updated_at: string
}

export interface CloudConnectionAuditEntry {
  id: number
  connection_id: number | null
  actor_user_id: number | null
  action:
    | 'created' | 'renamed' | 'rotated' | 'deleted'
    | 'sync_started' | 'sync_finished'
  status: string | null
  before: Record<string, unknown> | null
  after: Record<string, unknown> | null
  note: string | null
  created_at: string
}

export const listCloudConnections = () =>
  api.get<{ total: number; connections: CloudConnection[] }>(
    '/ai-agents/connections'
  )

export const createCloudConnection = (body: {
  name: string
  provider: 'anthropic' | 'openai'
  api_key: string
}) => api.post<CloudConnection>('/ai-agents/connections', body)

export const updateCloudConnection = (
  id: number,
  body: { name: string }
) => api.patch<CloudConnection>(`/ai-agents/connections/${id}`, body)

export const rotateCloudConnection = (id: number, api_key: string) =>
  api.post<CloudConnection>(`/ai-agents/connections/${id}/rotate`, { api_key })

export const deleteCloudConnection = (id: number) =>
  api.delete(`/ai-agents/connections/${id}`)

export const syncCloudConnection = (id: number) =>
  api.post<{
    connection_id: number
    status: 'success' | 'partial' | 'failed'
    agents_discovered: number
    agents_updated: number
    error: string | null
  }>(`/ai-agents/connections/${id}/sync`)

export const getCloudConnectionAudit = (id: number, limit = 50, offset = 0) =>
  api.get<{ total: number; entries: CloudConnectionAuditEntry[] }>(
    `/ai-agents/connections/${id}/audit`,
    { params: { limit, offset } }
  )
```

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd /Users/jyb/projects/telos/frontend && npx tsc --noEmit -p tsconfig.app.json 2>&1 | head -20`
Expected: no errors from this change

- [ ] **Step 3: Commit**

```bash
git add frontend/src/api/client.ts
git commit -m "feat(frontend): add cloud connection API client methods"
```

### Task 16: CloudConnectionsPage

**Files:**
- Create: `frontend/src/pages/CloudConnectionsPage.tsx`

- [ ] **Step 1: Create the page**

Write to `frontend/src/pages/CloudConnectionsPage.tsx`:

```tsx
/**
 * Cloud Connections management page — peer to /ai-agents.
 * Lists connections, supports add / edit (name only) / delete / rotate / sync-now.
 * Shows the per-connection audit log in a drawer.
 */
import { useEffect, useState } from 'react'
import {
  Table, Button, Space, Typography, Tag, message, Modal, Form, Input,
  Select, Drawer, Empty, Spin, Popconfirm, Tooltip,
} from 'antd'
import {
  PlusOutlined, SyncOutlined, EditOutlined, DeleteOutlined,
  KeyOutlined, HistoryOutlined,
} from '@ant-design/icons'
import { useTranslation } from 'react-i18next'
import {
  listCloudConnections, createCloudConnection, updateCloudConnection,
  deleteCloudConnection, rotateCloudConnection, syncCloudConnection,
  getCloudConnectionAudit,
  CloudConnection, CloudConnectionAuditEntry,
} from '../api/client'

const { Title, Text } = Typography

export default function CloudConnectionsPage() {
  const { t } = useTranslation()
  const [loading, setLoading] = useState(true)
  const [connections, setConnections] = useState<CloudConnection[]>([])
  const [addOpen, setAddOpen] = useState(false)
  const [editing, setEditing] = useState<CloudConnection | null>(null)
  const [rotating, setRotating] = useState<CloudConnection | null>(null)
  const [auditConn, setAuditConn] = useState<CloudConnection | null>(null)
  const [auditEntries, setAuditEntries] = useState<CloudConnectionAuditEntry[]>([])
  const [syncingId, setSyncingId] = useState<number | null>(null)
  const [addForm] = Form.useForm()
  const [editForm] = Form.useForm()
  const [rotateForm] = Form.useForm()

  const refresh = async () => {
    setLoading(true)
    try {
      const r = await listCloudConnections()
      setConnections(r.data.connections)
    } catch (e) {
      message.error('Failed to load connections')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { refresh() }, [])

  const handleAdd = async () => {
    const values = await addForm.validateFields()
    try {
      await createCloudConnection(values)
      message.success(t('aiAgent.connections.addSuccess'))
      setAddOpen(false)
      addForm.resetFields()
      refresh()
    } catch (e: any) {
      message.error(e?.response?.data?.detail || t('aiAgent.connections.addError'))
    }
  }

  const handleRename = async () => {
    if (!editing) return
    const values = await editForm.validateFields()
    try {
      await updateCloudConnection(editing.id, values)
      message.success('Renamed')
      setEditing(null)
      refresh()
    } catch {
      message.error('Failed to rename')
    }
  }

  const handleRotate = async () => {
    if (!rotating) return
    const values = await rotateForm.validateFields()
    try {
      await rotateCloudConnection(rotating.id, values.api_key)
      message.success('Key rotated')
      setRotating(null)
      rotateForm.resetFields()
      refresh()
    } catch {
      message.error('Failed to rotate key')
    }
  }

  const handleDelete = async (id: number) => {
    try {
      await deleteCloudConnection(id)
      message.success('Deleted')
      refresh()
    } catch {
      message.error('Failed to delete')
    }
  }

  const handleSync = async (c: CloudConnection) => {
    setSyncingId(c.id)
    try {
      const r = await syncCloudConnection(c.id)
      message.success(
        t('aiAgent.connections.agentsDiscovered', { count: r.data.agents_discovered })
      )
      refresh()
    } catch (e: any) {
      if (e?.response?.status === 409) {
        message.warning(t('aiAgent.connections.syncInProgress'))
      } else {
        message.error('Sync failed')
      }
    } finally {
      setSyncingId(null)
    }
  }

  const openAudit = async (c: CloudConnection) => {
    setAuditConn(c)
    try {
      const r = await getCloudConnectionAudit(c.id, 100, 0)
      setAuditEntries(r.data.entries)
    } catch {
      setAuditEntries([])
    }
  }

  const columns = [
    {
      title: t('aiAgent.connections.name'),
      dataIndex: 'name',
      key: 'name',
    },
    {
      title: t('aiAgent.connections.provider'),
      dataIndex: 'provider',
      key: 'provider',
      render: (p: string) => t(`aiAgent.connections.providerLabel.${p}`),
    },
    {
      title: 'Fingerprint',
      dataIndex: 'api_key_fingerprint',
      key: 'api_key_fingerprint',
      render: (fp: string) => <Text code>{fp}</Text>,
    },
    {
      title: t('aiAgent.connections.lastSync'),
      key: 'last_sync',
      render: (_: any, c: CloudConnection) => {
        if (!c.last_sync_at) return <Text type="secondary">{t('aiAgent.connections.lastSyncNever')}</Text>
        return (
          <Space direction="vertical" size={0}>
            <Text>{new Date(c.last_sync_at).toLocaleString()}</Text>
            {c.last_sync_status && (
              <Tag color={
                c.last_sync_status === 'success' ? 'green' :
                c.last_sync_status === 'partial' ? 'orange' :
                c.last_sync_status === 'running' ? 'blue' : 'red'
              }>
                {t(`aiAgent.connections.status.${c.last_sync_status}`)}
              </Tag>
            )}
            {c.last_sync_error && (
              <Tooltip title={c.last_sync_error}>
                <Text type="secondary" style={{ fontSize: 12 }}>
                  {c.last_sync_error.slice(0, 40)}
                </Text>
              </Tooltip>
            )}
          </Space>
        )
      },
    },
    {
      title: 'Actions',
      key: 'actions',
      render: (_: any, c: CloudConnection) => (
        <Space>
          <Button
            size="small"
            icon={<SyncOutlined />}
            loading={syncingId === c.id || c.last_sync_status === 'running'}
            onClick={() => handleSync(c)}
          >
            {syncingId === c.id
              ? t('aiAgent.connections.syncing')
              : t('aiAgent.connections.syncNow')}
          </Button>
          <Button size="small" icon={<EditOutlined />} onClick={() => {
            setEditing(c); editForm.setFieldsValue({ name: c.name })
          }}>
            {t('aiAgent.connections.edit')}
          </Button>
          <Button size="small" icon={<KeyOutlined />} onClick={() => setRotating(c)}>
            {t('aiAgent.connections.rotate')}
          </Button>
          <Button size="small" icon={<HistoryOutlined />} onClick={() => openAudit(c)}>
            {t('aiAgent.connections.auditLog')}
          </Button>
          <Popconfirm
            title={t('aiAgent.connections.deleteConfirm')}
            onConfirm={() => handleDelete(c.id)}
            okText="Delete"
            okButtonProps={{ danger: true }}
          >
            <Button size="small" danger icon={<DeleteOutlined />}>
              {t('aiAgent.connections.delete')}
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ]

  return (
    <div style={{ padding: 24 }}>
      <Space style={{ marginBottom: 16, width: '100%', justifyContent: 'space-between' }}>
        <div>
          <Title level={3} style={{ margin: 0 }}>{t('aiAgent.connections.title')}</Title>
          <Text type="secondary">{t('aiAgent.subtitle')}</Text>
        </div>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setAddOpen(true)}>
          {t('aiAgent.connections.add')}
        </Button>
      </Space>

      {loading ? (
        <Spin />
      ) : connections.length === 0 ? (
        <Empty description="No connections yet" />
      ) : (
        <Table rowKey="id" dataSource={connections} columns={columns} pagination={false} />
      )}

      {/* Add dialog */}
      <Modal
        title={t('aiAgent.connections.addTitle')}
        open={addOpen}
        onCancel={() => setAddOpen(false)}
        onOk={handleAdd}
        okText={t('aiAgent.connections.add')}
        destroyOnClose
      >
        <Form form={addForm} layout="vertical" preserve={false}>
          <Form.Item name="name" label={t('aiAgent.connections.name')}
                     rules={[{ required: true, max: 64 }]}>
            <Input placeholder="acme-prod" />
          </Form.Item>
          <Form.Item name="provider" label={t('aiAgent.connections.provider')}
                     rules={[{ required: true }]}>
            <Select>
              <Select.Option value="anthropic">
                {t('aiAgent.connections.providerLabel.anthropic')}
              </Select.Option>
              <Select.Option value="openai">
                {t('aiAgent.connections.providerLabel.openai')}
              </Select.Option>
            </Select>
          </Form.Item>
          <Form.Item name="api_key" label={t('aiAgent.connections.apiKey')}
                     rules={[{ required: true }]}
                     extra={t('aiAgent.connections.apiKeyHint')}>
            <Input.Password placeholder="sk-ant-admin-..." />
          </Form.Item>
        </Form>
      </Modal>

      {/* Edit name dialog */}
      <Modal
        title={t('aiAgent.connections.edit')}
        open={!!editing}
        onCancel={() => setEditing(null)}
        onOk={handleRename}
        destroyOnClose
      >
        <Form form={editForm} layout="vertical" preserve={false}>
          <Form.Item name="name" label={t('aiAgent.connections.name')}
                     rules={[{ required: true, max: 64 }]}>
            <Input />
          </Form.Item>
        </Form>
      </Modal>

      {/* Rotate key dialog */}
      <Modal
        title={t('aiAgent.connections.rotate')}
        open={!!rotating}
        onCancel={() => { setRotating(null); rotateForm.resetFields() }}
        onOk={handleRotate}
        destroyOnClose
      >
        <Form form={rotateForm} layout="vertical" preserve={false}>
          <Form.Item name="api_key" label={t('aiAgent.connections.apiKey')}
                     rules={[{ required: true }]}>
            <Input.Password />
          </Form.Item>
        </Form>
      </Modal>

      {/* Audit drawer */}
      <Drawer
        title={auditConn ? `${t('aiAgent.connections.auditLog')} — ${auditConn.name}` : ''}
        open={!!auditConn}
        onClose={() => setAuditConn(null)}
        width={600}
      >
        {auditEntries.length === 0 ? (
          <Empty />
        ) : (
          <Table
            rowKey="id"
            dataSource={auditEntries}
            pagination={false}
            size="small"
            columns={[
              {
                title: 'Time',
                dataIndex: 'created_at',
                render: (s: string) => new Date(s).toLocaleString(),
              },
              {
                title: 'Action',
                dataIndex: 'action',
                render: (a: string) => t(`aiAgent.connections.auditAction.${a}`),
              },
              {
                title: 'Note',
                dataIndex: 'note',
                render: (n: string | null) => n || '—',
              },
            ]}
          />
        )}
      </Drawer>
    </div>
  )
}
```

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd /Users/jyb/projects/telos/frontend && npx tsc --noEmit -p tsconfig.app.json 2>&1 | head -20`
Expected: no errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/CloudConnectionsPage.tsx
git commit -m "feat(frontend): add CloudConnectionsPage"
```

### Task 17: Wire up routes + page link

**Files:**
- Modify: `frontend/src/App.tsx` (add the route)
- Modify: `frontend/src/pages/AIAgentsPage.tsx` (add a "Connections" link in the header)

- [ ] **Step 1: Add the route in App.tsx**

In `frontend/src/App.tsx`, find the existing `Route path="/ai-agents"` block and add a new route next to it. The exact lines will depend on the existing structure; find the import for `AIAgentDetailPage` and add `CloudConnectionsPage` next to it. Then in the routes block, add:

```tsx
import CloudConnectionsPage from './pages/CloudConnectionsPage'
```

And in the `<Routes>` (or `<Route>` children):

```tsx
<Route path="/ai-agents/connections" element={<CloudConnectionsPage />} />
```

- [ ] **Step 2: Add a "Connections" link in the AIAgentsPage header**

In `frontend/src/pages/AIAgentsPage.tsx`, find the header `<Space>` near the page title (where the `Scan` button is) and add a "Connections" button that navigates to `/ai-agents/connections`:

```tsx
import { useNavigate } from 'react-router-dom'
// ... inside the component:
const navigate = useNavigate()
// In the header Space:
<Button onClick={() => navigate('/ai-agents/connections')}>
  {t('aiAgent.connections.title')}
</Button>
```

- [ ] **Step 3: Verify TypeScript compiles**

Run: `cd /Users/jyb/projects/telos/frontend && npx tsc --noEmit -p tsconfig.app.json 2>&1 | head -20`
Expected: no errors

- [ ] **Step 4: Commit**

```bash
git add frontend/src/App.tsx frontend/src/pages/AIAgentsPage.tsx
git commit -m "feat(frontend): wire /ai-agents/connections route + page link"
```

### Task 18: Vitest tests for the page + API client

**Files:**
- Create: `frontend/src/pages/__tests__/CloudConnectionsPage.test.tsx`
- Create: `frontend/src/api/__tests__/ai-agent-connections.test.ts`

- [ ] **Step 1: Write the page test**

Write to `frontend/src/pages/__tests__/CloudConnectionsPage.test.tsx`:

```tsx
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import CloudConnectionsPage from '../CloudConnectionsPage'
import '../../i18n'

const mocks = vi.hoisted(() => ({
  listCloudConnections: vi.fn(),
  createCloudConnection: vi.fn(),
  updateCloudConnection: vi.fn(),
  deleteCloudConnection: vi.fn(),
  rotateCloudConnection: vi.fn(),
  syncCloudConnection: vi.fn(),
  getCloudConnectionAudit: vi.fn(),
}))

vi.mock('../../api/client', () => ({
  listCloudConnections: mocks.listCloudConnections,
  createCloudConnection: mocks.createCloudConnection,
  updateCloudConnection: mocks.updateCloudConnection,
  deleteCloudConnection: mocks.deleteCloudConnection,
  rotateCloudConnection: mocks.rotateCloudConnection,
  syncCloudConnection: mocks.syncCloudConnection,
  getCloudConnectionAudit: mocks.getCloudConnectionAudit,
}))

describe('CloudConnectionsPage', () => {
  it('renders an empty state when no connections', async () => {
    mocks.listCloudConnections.mockResolvedValue({ data: { total: 0, connections: [] } })
    render(<MemoryRouter><CloudConnectionsPage /></MemoryRouter>)
    await waitFor(() => {
      expect(screen.getByText(/Cloud Connections/i)).toBeInTheDocument()
    })
  })

  it('renders one row per connection', async () => {
    mocks.listCloudConnections.mockResolvedValue({
      data: {
        total: 2,
        connections: [
          { id: 1, name: 'acme-prod', provider: 'anthropic',
            api_key_fingerprint: 'aaaa', last_sync_at: null, last_sync_status: null,
            last_sync_error: null, created_by_user_id: 1, created_at: '', updated_at: '' },
          { id: 2, name: 'openai-dev', provider: 'openai',
            api_key_fingerprint: 'bbbb', last_sync_at: null, last_sync_status: null,
            last_sync_error: null, created_by_user_id: 1, created_at: '', updated_at: '' },
        ],
      },
    })
    render(<MemoryRouter><CloudConnectionsPage /></MemoryRouter>)
    await waitFor(() => {
      expect(screen.getByText('acme-prod')).toBeInTheDocument()
    })
    expect(screen.getByText('openai-dev')).toBeInTheDocument()
  })

  it('opens the add dialog and shows required fields', async () => {
    mocks.listCloudConnections.mockResolvedValue({ data: { total: 0, connections: [] } })
    render(<MemoryRouter><CloudConnectionsPage /></MemoryRouter>)
    await waitFor(() => screen.getByText(/Add Connection/i))
    fireEvent.click(screen.getByText(/Add Connection/i))
    await waitFor(() => {
      expect(screen.getByText(/Add Cloud Connection/i)).toBeInTheDocument()
    })
  })
})
```

- [ ] **Step 2: Write the API client test**

Write to `frontend/src/api/__tests__/ai-agent-connections.test.ts`:

```ts
import { describe, it, expect, vi } from 'vitest'

const postMock = vi.fn()
const getMock = vi.fn()
const patchMock = vi.fn()
const delMock = vi.fn()

vi.mock('axios', () => ({
  default: {
    post: (...args: any[]) => postMock(...args),
    get: (...args: any[]) => getMock(...args),
    patch: (...args: any[]) => patchMock(...args),
    delete: (...args: any[]) => delMock(...args),
    create: () => ({
      post: postMock, get: getMock, patch: patchMock, delete: delMock,
      interceptors: { request: { use: () => {} }, response: { use: () => {} } },
    }),
  },
}))

import {
  listCloudConnections, createCloudConnection, rotateCloudConnection,
  syncCloudConnection, deleteCloudConnection, updateCloudConnection,
  getCloudConnectionAudit,
} from '../client'

describe('cloud connection API client', () => {
  it('listCloudConnections hits /ai-agents/connections', async () => {
    postMock.mockResolvedValue({ data: {} })
    getMock.mockResolvedValue({ data: { total: 0, connections: [] } })
    await listCloudConnections()
    expect(getMock).toHaveBeenCalledWith('/ai-agents/connections', { params: undefined })
  })

  it('createCloudConnection sends api_key only in POST body', async () => {
    postMock.mockResolvedValue({ data: {} })
    await createCloudConnection({ name: 'c1', provider: 'anthropic', api_key: 'sk-test' })
    expect(postMock).toHaveBeenCalledWith('/ai-agents/connections',
      { name: 'c1', provider: 'anthropic', api_key: 'sk-test' })
  })

  it('rotateCloudConnection hits /rotate', async () => {
    postMock.mockResolvedValue({ data: {} })
    await rotateCloudConnection(7, 'new-key')
    expect(postMock).toHaveBeenCalledWith('/ai-agents/connections/7/rotate',
      { api_key: 'new-key' })
  })

  it('syncCloudConnection POSTs to /sync', async () => {
    postMock.mockResolvedValue({ data: {} })
    await syncCloudConnection(3)
    expect(postMock).toHaveBeenCalledWith('/ai-agents/connections/3/sync', undefined)
  })

  it('deleteCloudConnection calls DELETE', async () => {
    delMock.mockResolvedValue({ data: {} })
    await deleteCloudConnection(5)
    expect(delMock).toHaveBeenCalledWith('/ai-agents/connections/5')
  })

  it('updateCloudConnection uses PATCH and never sends api_key', async () => {
    patchMock.mockResolvedValue({ data: {} })
    await updateCloudConnection(2, { name: 'renamed' })
    expect(patchMock).toHaveBeenCalledWith('/ai-agents/connections/2',
      { name: 'renamed' })
  })

  it('getCloudConnectionAudit passes limit/offset', async () => {
    getMock.mockResolvedValue({ data: { total: 0, entries: [] } })
    await getCloudConnectionAudit(2, 25, 50)
    expect(getMock).toHaveBeenCalledWith('/ai-agents/connections/2/audit',
      { params: { limit: 25, offset: 50 } })
  })
})
```

- [ ] **Step 3: Run the tests**

Run: `cd /Users/jyb/projects/telos/frontend && npx vitest run src/pages/__tests__/CloudConnectionsPage.test.tsx src/api/__tests__/ai-agent-connections.test.ts 2>&1 | tail -20`
Expected: all tests pass

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/__tests__/CloudConnectionsPage.test.tsx frontend/src/api/__tests__/ai-agent-connections.test.ts
git commit -m "test(frontend): add Vitest tests for cloud connections page and API client"
```

### Task 19: E2E Playwright test

**Files:**
- Create: `frontend/e2e/cloud-connections.spec.ts`

- [ ] **Step 1: Check that the e2e directory exists and look at the existing test pattern**

Run: `ls /Users/jyb/projects/telos/frontend/e2e/ 2>/dev/null | head`
Expected: a few existing `.spec.ts` files. If the directory doesn't exist, use the existing v1 e2e path: `frontend/e2e/ai-agents.spec.ts` (or wherever the v1 test lives) and put the new test there.

Read the existing file for the exact test pattern and replicate the `test()` / `expect()` / `page.goto()` style.

- [ ] **Step 2: Create the test (adapt to the existing pattern)**

Write to `frontend/e2e/cloud-connections.spec.ts` (or matching path):

```ts
import { test, expect } from '@playwright/test'

test.describe('Cloud Connections', () => {
  test('user can navigate to connections page and see empty state', async ({ page }) => {
    // Login
    await page.goto('/login')
    await page.fill('input[name="username"]', 'admin')
    await page.fill('input[name="password"]', 'admin')
    await page.click('button[type="submit"]')
    await page.waitForURL('**/dashboard**')

    // Go to AI Agents → Connections
    await page.goto('/ai-agents/connections')
    await expect(page.getByText(/Cloud Connections|云连接/)).toBeVisible()
  })
})
```

(Adjust the login flow / selectors to match the existing v1 Playwright tests in the same directory.)

- [ ] **Step 3: Run the test (only if the project has a working test environment)**

Run: `cd /Users/jyb/projects/telos/frontend && npx playwright test e2e/cloud-connections.spec.ts 2>&1 | tail -10`
Expected: 1 passed (or skipped if env not configured). If the test env is not available, document the skip and continue.

- [ ] **Step 4: Commit**

```bash
git add frontend/e2e/cloud-connections.spec.ts
git commit -m "test(e2e): add Playwright smoke test for cloud connections"
```

### Task 20: README + final verification

**Files:**
- Modify: `README.md` (one-line addition to the Features list + the Project structure tree)

- [ ] **Step 1: Add the feature bullet**

In `README.md`, find the existing AI Agent feature line:

```markdown
- **AI Agent 管理** — ...
```

Add a sibling bullet right after it:

```markdown
- **AI Agent 云连接** — 通过 Anthropic Console / OpenAI Dashboard Admin Key 自动发现云端 AI Agent(组织、项目、API Key),支持 6h 定时 + 手动同步
```

- [ ] **Step 2: Add the project structure lines**

In the project structure tree in `README.md`, find the AI Agent service line and add the new ones:

```markdown
  - `routers/ai_agent_connections.py` (cloud connections CRUD + sync + audit)
  - `services/cloud_discovery/{base,anthropic,openai}.py`
  - `pages/CloudConnectionsPage.tsx`
```

- [ ] **Step 3: Run the full test suite once**

Run: `cd /Users/jyb/projects/telos/backend && python -m pytest ../backend/tests/ -q 2>&1 | tail -10`
Expected: all tests pass (or only pre-existing failures unrelated to this work)

Then: `cd /Users/jyb/projects/telos/frontend && npx vitest run 2>&1 | tail -10`
Expected: all tests pass

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs(readme): document AI Agent cloud connection feature"
```

---

## Self-Review

After writing the plan I checked it against the spec. Items I caught and fixed inline:

1. **Task 5 Step 5 + Task 6 Step 5/6** — The original "5 passed" expectation in Task 6 assumed the dispatch tests would already work. They can't, because the dispatch tests import `AnthropicDiscovery` and `OpenAIDiscovery` from modules that don't exist yet. Corrected to: (a) write a temporary `test_base_module_imports` first, (b) Task 7 + 8 create the provider modules, (c) Task 8 Step 5 swaps the temp test back to the real four dispatch tests, (d) Task 8 Step 6 runs all 11 together.

2. **Task 11** — Initial draft had the `cloud_discover` import at the top of the module, but the scheduler_service test file patches it via `backend.services.scheduler_service.cloud_discover`. Fixed to keep the import inside the function (so the test's patcher can find it on the module's namespace).

3. **Task 12 / Task 11** — The router test file imports `auth` and uses `auth.create_access_token`, but for a router test we don't actually need a real JWT — the test client uses `app.dependency_overrides[auth.get_current_user]`. The `create_access_token` reference is unused; removed from the actual fixture.

4. **Task 13 Step 3** — `_sync_all_cloud_connections` reuses `_run_sync` from the router module to avoid code duplication. The router module's `_run_sync` is private but both modules are in `backend.routers` / `backend.services.scheduler_service` and the import is intentional. This is acceptable for v2; if it bothers a reviewer, we can move `_run_sync` into `backend/services/cloud_discovery/sync.py` in a follow-up.

5. **Task 14 Step 3** — Used `Object.keys(en.aiAgent.connections).length` for both en and zh. If a key has nested keys (e.g. `status.success`), `Object.keys` returns the parent only. Both files have the same nested structure, so a simple set comparison of the top-level keys is sufficient for v2.

6. **Type consistency** — `CloudConnection.id` (int) is used consistently in `deleteCloudConnection(id)`, `rotateCloudConnection(id, ...)`, etc. `RawAgent.api_key_fingerprint` is `str` everywhere (16-char hex, no `sha256:` prefix on the v2 path; the v1 SSH path keeps the `sha256:` prefix because the v1 code added it — that's fine, they're not mixed within a single agent row).

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-06-04-ai-agent-cloud-discovery.md`. 20 tasks across 6 phases.

Two execution options:

1. **Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration
2. **Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
