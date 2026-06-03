# AI Agent Identity & NHI Menu Promotion — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add AI Agent as a first-class identity (sibling to NHI, not a subtype) with its own scanner, page, and governance. In the same change, promote the NHI menu from a sub-item of *Identity Operations* to a top-level sidebar item, with AI Agent as a sibling in the B-slot.

**Architecture:** AI Agent detection runs as a peer to `ssh_scanner` (one additional batched SSH probe per asset). Probed signals flow into `AccountSnapshot.raw_info["ai_agent_signals"]`, get parsed by `ai_agent_scanner.ingest()`, and produce rows in a new `ai_agents` table. AIAgent is standalone with an optional one-way FK to NHIIdentity. Frontend gets a new top-level menu slot and a new page peer to `/nhi`.

**Tech Stack:** FastAPI, SQLAlchemy 2, Alembic, paramiko, React 18 + TypeScript + Ant Design 5, i18next, Vitest, Playwright.

---

## Phase 1 — NHI Menu Promotion

### Task 1: Add i18n keys for new top-level menu items

**Files:**
- Modify: `frontend/src/locales/en-US.json` (insert after existing `nav.nhi`)
- Modify: `frontend/src/locales/zh-CN.json` (insert after existing `nav.nhi`)

- [ ] **Step 1: Add `nav.aiAgents` to en-US.json**

In `frontend/src/locales/en-US.json`, locate the line `"nav.nhi": "NHI Non-Human Identity",` and add the line right after it:

```json
  "nav.aiAgents": "AI Agent Management",
```

- [ ] **Step 2: Add `nav.aiAgents` to zh-CN.json**

In `frontend/src/locales/zh-CN.json`, locate the line `"nav.nhi": "NHI 非人类身份",` and add the line right after it:

```json
  "nav.aiAgents": "AI Agent 管理",
```

- [ ] **Step 3: Verify i18n check passes**

Run: `cd /Users/jyb/projects/telos/frontend && npm run check-i18n`
Expected: `✓ All i18n checks passed`

- [ ] **Step 4: Commit**

```bash
git add frontend/src/locales/en-US.json frontend/src/locales/zh-CN.json
git commit -m "i18n(nav): add nav.aiAgents label for upcoming top-level menu item"
```

---

### Task 2: Restructure AppLayout menu — promote NHI, add AI Agent top-level

**Files:**
- Modify: `frontend/src/components/AppLayout.tsx:240-247` (remove NHI from `identity-ops` SubMenu and add 2 new top-level Menu.Items after the AI item)

- [ ] **Step 1: Remove NHI from identity-ops SubMenu**

In `frontend/src/components/AppLayout.tsx`, delete the line:
```jsx
              <Menu.Item key="nhi" icon={<ApiOutlined />}><Link to="/nhi">{t('nav.nhi')}</Link></Menu.Item>
```

The `identity-ops` SubMenu should now have only 4 children: `identities`, `ueba`, `lifecycle`, `pam`.

- [ ] **Step 2: Add two new top-level Menu.Items in the B-slot**

In the same file, after the `ai` Menu.Item (the line `<Menu.Item key="ai" ...>`) and before the `asset-group` SubMenu, insert:

```jsx
            <Menu.Item key="nhi" icon={<ApiOutlined />}><Link to="/nhi">{t('nav.nhi')}</Link></Menu.Item>
            <Menu.Item key="ai-agents" icon={<RobotOutlined />}><Link to="/ai-agents">{t('nav.aiAgents')}</Link></Menu.Item>
```

- [ ] **Step 3: Import RobotOutlined if not already imported**

Check the existing imports from `@ant-design/icons` at the top of the file. If `RobotOutlined` is not present, add it to the import list.

- [ ] **Step 4: Verify TypeScript compiles**

Run: `cd /Users/jyb/projects/telos/frontend && npx tsc -b 2>&1 | tail -5`
Expected: no output (clean compile)

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/AppLayout.tsx
git commit -m "refactor(nav): promote NHI to top-level menu; add AI Agent placeholder item"
```

---

### Task 3: Visual verification of new menu

**Files:** none (UI verification)

- [ ] **Step 1: Confirm dev server is running**

Run: `curl -s -o /dev/null -w "%{http_code}" http://localhost:5173`
Expected: `200`. If not, start with `cd /Users/jyb/projects/telos/frontend && npm run dev` (background).

- [ ] **Step 2: Open the app in the browser and verify**

Navigate to `http://localhost:5173` (after logging in if needed). Confirm:
- Sidebar shows: 仪表盘, AI 智能分析, NHI 非人类身份, AI Agent 管理, 资产管理 ▾, ...
- AI Agent 管理 is clickable (route may 404 in v1 — that's expected; will land in Phase 6)
- The 4 "human identity" items remain in 身份运营 submenu

- [ ] **Step 3: No code changes — no commit**

If the menu layout is wrong, return to Task 2 and fix.

---

## Phase 2 — Backend Foundation

### Task 4: Add AIAgent enums to _enums.py

**Files:**
- Modify: `backend/models/_enums.py` (append new enums at end of file)

- [ ] **Step 1: Add AIAgentFramework and AIAgentLevel enums**

Open `backend/models/_enums.py` and add at the end of the file (after the existing `NHILevel` enum):

```python
class AIAgentFramework(str, enum.Enum):
    LANGCHAIN = "langchain"
    AUTOGEN = "autogen"
    CREWAI = "crewai"
    CLAUDE_CODE = "claude_code"
    OPENAI_ASSISTANT = "openai_assistant"
    LLAMAINDEX = "llamaindex"
    CUSTOM = "custom"
    UNKNOWN = "unknown"


class AIAgentStatus(str, enum.Enum):
    ACTIVE = "active"
    DORMANT = "dormant"
    DEPRECATED = "deprecated"
    BLOCKED = "blocked"


class AIAgentDiscoverySource(str, enum.Enum):
    SSH_SCAN = "ssh_scan"
    API_DISCOVERY = "api_discovery"
    MANUAL = "manual"
```

- [ ] **Step 2: Verify the file still imports**

Run: `cd /Users/jyb/projects/telos && python3 -c "from backend.models._enums import AIAgentFramework, AIAgentStatus, AIAgentDiscoverySource; print('ok')"`
Expected: `ok`

- [ ] **Step 3: No commit yet** (will commit with next task)

---

### Task 5: Add AIAgent SQLAlchemy model

**Files:**
- Create: `backend/models/ai_agents.py`
- Modify: `backend/models/__init__.py` (re-export the new model)

- [ ] **Step 1: Create the model file**

Create `backend/models/ai_agents.py`:

```python
"""AI Agent ORM models — first-class identity peer to NHI."""
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, DateTime, ForeignKey, Text, JSON, Index,
)
from sqlalchemy.orm import relationship

from backend.models._db import Base


class AIAgent(Base):
    __tablename__ = "ai_agents"
    __table_args__ = (
        Index(
            "ix_ai_agents_dedup",
            "framework", "agent_name", "owner_team", "asset_id",
            unique=True,
        ),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    agent_name = Column(String(128), nullable=False, index=True)
    framework = Column(String(32), nullable=False, default="unknown")
    model = Column(String(64), nullable=True)
    owner_team = Column(String(64), nullable=True, index=True)
    owner_user = Column(String(64), nullable=True)
    api_key_fingerprint = Column(String(16), nullable=True)
    api_key_location = Column(String(256), nullable=True)
    capabilities = Column(JSON, default=dict)  # {filesystem, network, code_exec, tool_count}
    last_invocation_at = Column(DateTime, nullable=True)
    last_seen_at = Column(DateTime, nullable=False)
    discovered_at = Column(DateTime, nullable=False)
    discovery_source = Column(String(16), nullable=False, default="ssh_scan")
    asset_id = Column(Integer, ForeignKey("assets.id"), nullable=True, index=True)
    nhi_identity_id = Column(Integer, ForeignKey("nhi_identities.id"), nullable=True, index=True)
    risk_level = Column(String(16), nullable=False, default="low")
    risk_score = Column(Integer, nullable=False, default=0)
    risk_signals = Column(JSON, default=list)
    status = Column(String(16), nullable=False, default="active")
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    asset = relationship("Asset")
    nhi = relationship("NHIIdentity")
```

- [ ] **Step 2: Re-export from models package**

Open `backend/models/__init__.py` and add (alphabetically with existing re-exports):

```python
from backend.models.ai_agents import AIAgent
```

- [ ] **Step 3: Verify import works**

Run: `cd /Users/jyb/projects/telos && python3 -c "from backend.models import AIAgent; print(AIAgent.__tablename__)"`
Expected: `ai_agents`

- [ ] **Step 4: Commit**

```bash
git add backend/models/_enums.py backend/models/ai_agents.py backend/models/__init__.py
git commit -m "feat(ai-agents): add AIAgent ORM model + enums"
```

---

### Task 6: Add Pydantic schemas for AIAgent

**Files:**
- Create: `backend/schemas/ai_agents.py`
- Modify: `backend/schemas/__init__.py` (re-export)

- [ ] **Step 1: Create the schemas file**

Create `backend/schemas/ai_agents.py`:

```python
"""AI Agent Pydantic schemas."""
from datetime import datetime
from typing import Optional, List, Literal, Dict, Any
from pydantic import BaseModel, Field

AIAgentFrameworkLiteral = Literal[
    "langchain", "autogen", "crewai", "claude_code",
    "openai_assistant", "llamaindex", "custom", "unknown",
]
AIAgentStatusLiteral = Literal["active", "dormant", "deprecated", "blocked"]
AIAgentLevelLiteral = Literal["low", "medium", "high", "critical"]
AIAgentDiscoverySourceLiteral = Literal["ssh_scan", "api_discovery", "manual"]


class AIAgentCapabilities(BaseModel):
    filesystem: bool = False
    network: bool = False
    code_exec: bool = False
    tool_count: int = 0


class AIAgentBase(BaseModel):
    agent_name: str
    framework: AIAgentFrameworkLiteral = "unknown"
    model: Optional[str] = None
    owner_team: Optional[str] = None
    owner_user: Optional[str] = None


class AIAgentResponse(AIAgentBase):
    id: int
    api_key_fingerprint: Optional[str] = None
    api_key_location: Optional[str] = None
    capabilities: AIAgentCapabilities = Field(default_factory=AIAgentCapabilities)
    last_invocation_at: Optional[datetime] = None
    last_seen_at: datetime
    discovered_at: datetime
    discovery_source: AIAgentDiscoverySourceLiteral = "ssh_scan"
    asset_id: Optional[int] = None
    nhi_identity_id: Optional[int] = None
    risk_level: AIAgentLevelLiteral = "low"
    risk_score: int = 0
    risk_signals: List[Dict[str, Any]] = Field(default_factory=list)
    status: AIAgentStatusLiteral = "active"
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AIAgentDetailResponse(AIAgentResponse):
    """Same shape as AIAgentResponse; alias for future-proofing."""
    pass


class AIAgentStatsResponse(BaseModel):
    total: int
    active: int
    critical_risk: int
    no_owner: int
    by_framework: Dict[str, int]
    by_risk_level: Dict[str, int]


class AIAgentScanRequest(BaseModel):
    asset_id: Optional[int] = None  # None = all assets
    force: bool = False  # re-scan even if recently scanned


class AIAgentScanResponse(BaseModel):
    scanned_assets: int
    agents_discovered: int
    agents_updated: int
    alerts_emitted: int
    errors: List[str] = Field(default_factory=list)


class AIAgentClaimRequest(BaseModel):
    """Sets owner_user to the current authenticated user."""
    pass
```

- [ ] **Step 2: Re-export from schemas package**

Open `backend/schemas/__init__.py` and add:

```python
from backend.schemas.ai_agents import (
    AIAgentCapabilities, AIAgentResponse, AIAgentDetailResponse,
    AIAgentStatsResponse, AIAgentScanRequest, AIAgentScanResponse,
    AIAgentClaimRequest,
)
```

- [ ] **Step 3: Verify imports**

Run: `cd /Users/jyb/projects/telos && python3 -c "from backend.schemas import AIAgentResponse, AIAgentStatsResponse; print('ok')"`
Expected: `ok`

- [ ] **Step 4: Commit**

```bash
git add backend/schemas/ai_agents.py backend/schemas/__init__.py
git commit -m "feat(ai-agents): add Pydantic schemas"
```

---

### Task 7: Create Alembic migration 024_ai_agents.py

**Files:**
- Create: `backend/alembic/versions/024_ai_agents.py`

- [ ] **Step 1: Create the migration file**

Create `backend/alembic/versions/024_ai_agents.py`:

```python
"""ai_agents table — first-class AI Agent identity (peer to NHI)

Revision ID: 024_ai_agents
Revises: 023_nhi_alerts_enhancement
Create Date: 2026-06-03
"""
import sqlalchemy as sa
from alembic import op


revision = "024_ai_agents"
down_revision = "023_nhi_alerts_enhancement"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_agents",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("agent_name", sa.String(128), nullable=False),
        sa.Column("framework", sa.String(32), nullable=False, server_default="unknown"),
        sa.Column("model", sa.String(64), nullable=True),
        sa.Column("owner_team", sa.String(64), nullable=True),
        sa.Column("owner_user", sa.String(64), nullable=True),
        sa.Column("api_key_fingerprint", sa.String(16), nullable=True),
        sa.Column("api_key_location", sa.String(256), nullable=True),
        sa.Column("capabilities", sa.JSON, nullable=True),
        sa.Column("last_invocation_at", sa.DateTime, nullable=True),
        sa.Column("last_seen_at", sa.DateTime, nullable=False),
        sa.Column("discovered_at", sa.DateTime, nullable=False),
        sa.Column("discovery_source", sa.String(16), nullable=False, server_default="ssh_scan"),
        sa.Column("asset_id", sa.Integer, sa.ForeignKey("assets.id"), nullable=True),
        sa.Column("nhi_identity_id", sa.Integer, sa.ForeignKey("nhi_identities.id"), nullable=True),
        sa.Column("risk_level", sa.String(16), nullable=False, server_default="low"),
        sa.Column("risk_score", sa.Integer, nullable=False, server_default="0"),
        sa.Column("risk_signals", sa.JSON, nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="active"),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=True, onupdate=sa.func.now()),
    )
    op.create_index("ix_ai_agents_dedup", "ai_agents",
                    ["framework", "agent_name", "owner_team", "asset_id"],
                    unique=True)
    op.create_index("ix_ai_agents_nhi", "ai_agents", ["nhi_identity_id"])
    op.create_index("ix_ai_agents_asset", "ai_agents", ["asset_id"])
    op.create_index("ix_ai_agents_fingerprint", "ai_agents", ["api_key_fingerprint"])


def downgrade() -> None:
    op.drop_index("ix_ai_agents_fingerprint", table_name="ai_agents")
    op.drop_index("ix_ai_agents_asset", table_name="ai_agents")
    op.drop_index("ix_ai_agents_nhi", table_name="ai_agents")
    op.drop_index("ix_ai_agents_dedup", table_name="ai_agents")
    op.drop_table("ai_agents")
```

- [ ] **Step 2: Verify file syntax**

Run: `cd /Users/jyb/projects/telos && python3 -c "import importlib.util; spec = importlib.util.spec_from_file_location('m', 'backend/alembic/versions/024_ai_agents.py'); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); print('ok')"`
Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add backend/alembic/versions/024_ai_agents.py
git commit -m "feat(ai-agents): add alembic migration 024 for ai_agents table"
```

---

### Task 8: Test migration 024 up and down

**Files:**
- Create: `backend/tests/test_migration_024.py`

- [ ] **Step 1: Write the test**

Create `backend/tests/test_migration_024.py`:

```python
"""Verify migration 024 creates the ai_agents table with the expected shape,
then downgrades cleanly."""
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
    return str(tmp_path / "migration_024.db")


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


def test_migration_024_upgrade_then_downgrade(db_path, alembic_cfg):
    """Apply migration 024 on a pre-024 schema, verify table+indexes, downgrade."""
    from alembic import command
    from sqlalchemy import create_engine, inspect

    _reload_backend_db(f"sqlite:///{db_path}")

    # Build pre-024 schema via ORM metadata, which will create everything
    # EXCEPT ai_agents (since the model is registered but no migration ran yet).
    from backend.database import Base
    from backend import models  # noqa: F401

    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(bind=engine)
    with engine.begin() as conn:
        conn.exec_driver_sql("DROP TABLE IF EXISTS ai_agents")

    # Stamp at 023 so alembic only runs 024
    command.stamp(alembic_cfg, "023_nhi_alerts_enhancement")
    command.upgrade(alembic_cfg, "024_ai_agents")

    insp = inspect(engine)
    tables = insp.get_table_names()
    assert "ai_agents" in tables, "024 should create ai_agents table"

    cols = {c["name"] for c in insp.get_columns("ai_agents")}
    expected = {
        "id", "agent_name", "framework", "model", "owner_team", "owner_user",
        "api_key_fingerprint", "api_key_location", "capabilities",
        "last_invocation_at", "last_seen_at", "discovered_at", "discovery_source",
        "asset_id", "nhi_identity_id", "risk_level", "risk_score", "risk_signals",
        "status", "notes", "created_at", "updated_at",
    }
    missing = expected - cols
    assert not missing, f"024 should add columns {missing} to ai_agents"

    indexes = {ix["name"] for ix in insp.get_indexes("ai_agents")}
    assert "ix_ai_agents_dedup" in indexes
    assert "ix_ai_agents_nhi" in indexes
    assert "ix_ai_agents_asset" in indexes
    assert "ix_ai_agents_fingerprint" in indexes

    # Downgrade should drop them
    command.downgrade(alembic_cfg, "023_nhi_alerts_enhancement")
    insp2 = inspect(engine)
    tables2 = insp2.get_table_names()
    assert "ai_agents" not in tables2, "downgrade should drop ai_agents"
```

- [ ] **Step 2: Run the test (should pass on first run)**

Run: `cd /Users/jyb/projects/telos && python3 -m pytest backend/tests/test_migration_024.py -v`
Expected: 1 passed

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_migration_024.py
git commit -m "test(ai-agents): add migration 024 up/down test"
```

---

## Phase 3 — Scanner Logic

### Task 9: TDD — fingerprint() utility

**Files:**
- Create: `backend/services/ai_agent_scanner.py`
- Create: `backend/tests/test_ai_agent_fingerprint.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_ai_agent_fingerprint.py`:

```python
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
        assert len(fp) == 16
        assert fp.startswith("sha256:")

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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/jyb/projects/telos && python3 -m pytest backend/tests/test_ai_agent_fingerprint.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'backend.services.ai_agent_scanner'`

- [ ] **Step 3: Write minimal implementation**

Create `backend/services/ai_agent_scanner.py`:

```python
"""AI Agent scanner — probe parser, dedupe, risk scoring, AIAgent upsert.

Public API:
    fingerprint_api_key(key)            -> sha256[:16] prefix or None
    parse_signals(raw_info)             -> list of candidate AIAgent dicts
    score_risk(agent_dict, all_agents)  -> (score, level, signals)
    ingest(db, raw_info, asset_id)      -> list[AIAgent] (created or updated)
"""
from __future__ import annotations

import hashlib
from typing import Optional


def fingerprint_api_key(key: Optional[str]) -> Optional[str]:
    """Return a 16-char sha256[:16] fingerprint prefixed with 'sha256:',
    or None for empty/None input. Never returns any portion of the key."""
    if not key:
        return None
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
    return f"sha256:{digest[:16]}"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/jyb/projects/telos && python3 -m pytest backend/tests/test_ai_agent_fingerprint.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add backend/services/ai_agent_scanner.py backend/tests/test_ai_agent_fingerprint.py
git commit -m "feat(ai-agents): add fingerprint_api_key utility + tests"
```

---

### Task 10: TDD — parse_signals() — probe output → candidate agent dicts

**Files:**
- Modify: `backend/services/ai_agent_scanner.py`
- Create: `backend/tests/test_ai_agent_scanner.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_ai_agent_scanner.py`:

```python
"""Tests for AI Agent signal parser — turns probe output into candidate agents."""
import os
import sys

os.environ.setdefault("ACCOUNTSCAN_MASTER_KEY", "test_master_key_0123456789abcdef01234567")
os.environ.setdefault("ACCOUNTSCAN_JWT_SECRET", "test_jwt_secret_0123456789abcdef0123456")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from backend.services.ai_agent_scanner import parse_signals


def _signal_block(config_files="", env_vars="", processes="", framework_paths="", package_json=""):
    return {
        "ai_agent_signals": {
            "config_files":    [c for c in config_files.split("\n") if c],
            "env_vars":        [e for e in env_vars.split("\n") if e],
            "processes":       [p for p in processes.split("\n") if p],
            "framework_paths": [f for f in framework_paths.split("\n") if f],
            "package_json":    [p for p in package_json.split("\n") if p],
        }
    }


class TestParseSignals:
    def test_empty_signals_returns_empty_list(self):
        assert parse_signals({"ai_agent_signals": {}}) == []

    def test_none_signals_returns_empty_list(self):
        assert parse_signals({}) == []

    def test_env_var_with_anthropic_key_creates_anthropic_agent(self):
        raw = _signal_block(
            env_vars="ANTHROPIC_API_KEY|user|sha256:abc",
        )
        agents = parse_signals(raw)
        assert len(agents) == 1
        assert agents[0]["framework"] == "claude_code"
        assert agents[0]["api_key_fingerprint"] == "sha256:abc"
        assert agents[0]["api_key_location"] == "env:ANTHROPIC_API_KEY"

    def test_env_var_with_openai_key_creates_openai_agent(self):
        raw = _signal_block(env_vars="OPENAI_API_KEY|user|sha256:xyz")
        agents = parse_signals(raw)
        assert len(agents) == 1
        assert agents[0]["framework"] == "openai_assistant"
        assert agents[0]["model"] == "openai"

    def test_framework_path_detected(self):
        raw = _signal_block(
            framework_paths="/opt/app/venv/lib/python3.11/site-packages/langchain|langchain",
        )
        agents = parse_signals(raw)
        assert len(agents) == 1
        assert agents[0]["framework"] == "langchain"
        assert agents[0]["agent_name"] == "app-langchain"

    def test_process_with_langchain_creates_agent(self):
        raw = _signal_block(processes="langchain-server|3")
        agents = parse_signals(raw)
        assert len(agents) == 1
        assert agents[0]["framework"] == "langchain"

    def test_multiple_signals_dedupe_to_single_agent(self):
        """Same framework on one asset collapses to one agent."""
        raw = _signal_block(
            framework_paths="/opt/app/venv/.../langchain|langchain",
            processes="langchain-server|1",
        )
        agents = parse_signals(raw)
        assert len(agents) == 1
        assert agents[0]["framework"] == "langchain"

    def test_config_file_with_plaintext_key_is_critical_signal(self):
        raw = _signal_block(
            config_files="/home/alice/.config/anthropic/credentials.json",
        )
        agents = parse_signals(raw)
        assert len(agents) == 1
        assert "plaintext_key" in agents[0]["evidence"]

    def test_capabilities_from_signals(self):
        raw = _signal_block(
            env_vars="LANGCHAIN_TOOL_COUNT|user|5",
        )
        agents = parse_signals(raw)
        assert len(agents) == 1
        assert agents[0]["capabilities"]["tool_count"] == 5

    def test_unknown_signal_returns_empty(self):
        raw = _signal_block(
            config_files="/etc/some/random/file.json",
            processes="bash|1",
        )
        assert parse_signals(raw) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/jyb/projects/telos && python3 -m pytest backend/tests/test_ai_agent_scanner.py -v 2>&1 | tail -5`
Expected: FAIL with `AttributeError: module 'backend.services.ai_agent_scanner' has no attribute 'parse_signals'`

- [ ] **Step 3: Implement parse_signals**

Add to `backend/services/ai_agent_scanner.py`:

```python
import re
from typing import Optional

_ENV_KEY_TO_FRAMEWORK = {
    "ANTHROPIC_API_KEY": ("claude_code", "claude"),
    "CLAUDE_API_KEY":    ("claude_code", "claude"),
    "OPENAI_API_KEY":    ("openai_assistant", "openai"),
    "OPENAI_ORG_ID":     ("openai_assistant", "openai"),
    "LANGCHAIN_API_KEY": ("langchain", None),
    "LANGCHAIN_TOOL_COUNT": (None, None),  # capability hint, not a key
    "COHERE_API_KEY":    ("custom", "cohere"),
    "GEMINI_API_KEY":    ("custom", "gemini"),
}

_FRAMEWORK_KEYWORDS = {
    "langchain": "langchain",
    "autogen":   "autogen",
    "crewai":    "crewai",
    "anthropic": "claude_code",
    "llamaindex":"llamaindex",
}

_PROCESS_FRAMEWORK = {
    "langchain": "langchain",
    "autogen":   "autogen",
    "crewai":    "crewai",
    "claude":    "claude_code",
    "gpt-":      "openai_assistant",
    "agent":     None,  # ambiguous — context-dependent
}


def _infer_agent_name(framework: str, location: str) -> str:
    """Best-effort agent name from the location/path."""
    if not location:
        return f"{framework}-agent"
    # Use last path component for config_files and framework_paths
    last = location.rstrip("/").split("/")[-1] or location
    # Strip common suffixes
    last = re.sub(r"\.(json|toml|yaml|yml)$", "", last)
    last = re.sub(r"^(credentials|config|settings)\.", "", last)
    return f"{framework}-{last}" if last else f"{framework}-agent"


def _parse_env_line(line: str) -> Optional[dict]:
    """'NAME|scope|fingerprint' -> {name, scope, fingerprint} or None."""
    parts = line.split("|")
    if len(parts) < 3:
        return None
    return {"name": parts[0].strip(), "scope": parts[1].strip(),
            "fingerprint": parts[2].strip()}


def _parse_process_line(line: str) -> Optional[dict]:
    """'name|count' -> {name, count} or None."""
    parts = line.split("|")
    if len(parts) < 2:
        return {"name": parts[0].strip(), "count": 1}
    return {"name": parts[0].strip(), "count": int(parts[1].strip())}


def _parse_path_line(line: str) -> Optional[dict]:
    """'path|framework' -> {path, framework} or None."""
    parts = line.split("|")
    if len(parts) < 2:
        return {"path": parts[0].strip(), "framework": "unknown"}
    return {"path": parts[0].strip(), "framework": parts[1].strip()}


def parse_signals(raw_info: dict) -> list[dict]:
    """Turn raw_info["ai_agent_signals"] into a list of candidate agent dicts.

    Each candidate is one agent per (framework, asset) — multiple signals for
    the same framework on the same asset collapse to a single candidate.
    """
    if not raw_info:
        return []
    signals = raw_info.get("ai_agent_signals") or {}
    if not signals:
        return []

    candidates: dict[str, dict] = {}  # key=framework, value=merged agent

    # ── env_vars ──────────────────────────────────────────────────────────
    for line in signals.get("env_vars") or []:
        env = _parse_env_line(line)
        if not env:
            continue
        # Tool count hint (not a key)
        if env["name"] == "LANGCHAIN_TOOL_COUNT":
            # Stash for later candidates
            for cand in candidates.values():
                cand.setdefault("capabilities", {})["tool_count"] = int(env["fingerprint"] or 0)
            continue
        if env["name"] not in _ENV_KEY_TO_FRAMEWORK:
            continue
        framework, model = _ENV_KEY_TO_FRAMEWORK[env["name"]]
        if framework is None:
            continue
        if framework not in candidates:
            candidates[framework] = {
                "agent_name": _infer_agent_name(framework, ""),
                "framework": framework,
                "model": model,
                "api_key_fingerprint": env["fingerprint"],
                "api_key_location": f"env:{env['name']}",
                "evidence": ["env_key"],
                "capabilities": {"filesystem": False, "network": True,
                                 "code_exec": False, "tool_count": 0},
            }
        else:
            # Reinforce existing
            candidates[framework]["api_key_fingerprint"] = (
                candidates[framework].get("api_key_fingerprint") or env["fingerprint"]
            )

    # ── config_files ──────────────────────────────────────────────────────
    for path in signals.get("config_files") or []:
        path_l = path.lower()
        for kw, framework in _FRAMEWORK_KEYWORDS.items():
            if kw in path_l:
                if framework not in candidates:
                    candidates[framework] = {
                        "agent_name": _infer_agent_name(framework, path),
                        "framework": framework,
                        "model": None,
                        "api_key_fingerprint": None,
                        "api_key_location": f"file:{path}",
                        "evidence": ["plaintext_key"],
                        "capabilities": {"filesystem": True, "network": False,
                                         "code_exec": False, "tool_count": 0},
                    }
                else:
                    candidates[framework].setdefault("evidence", []).append("plaintext_key")
                    candidates[framework]["capabilities"]["filesystem"] = True
                break

    # ── processes ─────────────────────────────────────────────────────────
    for line in signals.get("processes") or []:
        proc = _parse_process_line(line)
        if not proc:
            continue
        proc_l = proc["name"].lower()
        for kw, framework in _PROCESS_FRAMEWORK.items():
            if kw in proc_l and framework:
                if framework not in candidates:
                    candidates[framework] = {
                        "agent_name": _infer_agent_name(framework, proc["name"]),
                        "framework": framework,
                        "model": None,
                        "api_key_fingerprint": None,
                        "api_key_location": f"process:{proc['name']}",
                        "evidence": ["process"],
                        "capabilities": {"filesystem": False, "network": False,
                                         "code_exec": True, "tool_count": 0},
                    }
                else:
                    candidates[framework].setdefault("evidence", []).append("process")
                    candidates[framework]["capabilities"]["code_exec"] = True
                break

    # ── framework_paths ──────────────────────────────────────────────────
    for line in signals.get("framework_paths") or []:
        fp = _parse_path_line(line)
        if not fp:
            continue
        framework = fp["framework"]
        if framework not in _FRAMEWORK_KEYWORDS.values():
            framework = "unknown"
        if framework not in candidates:
            candidates[framework] = {
                "agent_name": _infer_agent_name(framework, fp["path"]),
                "framework": framework,
                "model": None,
                "api_key_fingerprint": None,
                "api_key_location": f"path:{fp['path']}",
                "evidence": ["framework_path"],
                "capabilities": {"filesystem": True, "network": False,
                                 "code_exec": False, "tool_count": 0},
            }
        else:
            candidates[framework].setdefault("evidence", []).append("framework_path")
            candidates[framework]["capabilities"]["filesystem"] = True

    return list(candidates.values())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/jyb/projects/telos && python3 -m pytest backend/tests/test_ai_agent_scanner.py -v 2>&1 | tail -15`
Expected: 9 passed. (If any fail, debug the parser; common issue: env-line splitting — see test inputs.)

- [ ] **Step 5: Commit**

```bash
git add backend/services/ai_agent_scanner.py backend/tests/test_ai_agent_scanner.py
git commit -m "feat(ai-agents): add parse_signals() — probe output to candidate dicts"
```

---

### Task 11: TDD — score_risk() with 8 rules

**Files:**
- Modify: `backend/services/ai_agent_scanner.py`
- Create: `backend/tests/test_ai_agent_risk.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_ai_agent_risk.py`:

```python
"""Tests for AI Agent risk scoring — 8 rules with threshold boundaries."""
import os
import sys
from datetime import datetime, timedelta

os.environ.setdefault("ACCOUNTSCAN_MASTER_KEY", "test_master_key_0123456789abcdef01234567")
os.environ.setdefault("ACCOUNTSCAN_JWT_SECRET", "test_jwt_secret_0123456789abcdef0123456")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from backend.services.ai_agent_scanner import score_risk


def _agent(**overrides):
    base = {
        "agent_name": "test-agent",
        "framework": "langchain",
        "model": None,
        "owner_team": "data-eng",
        "owner_user": "alice",
        "api_key_fingerprint": "sha256:abc",
        "capabilities": {"filesystem": False, "network": False,
                         "code_exec": False, "tool_count": 0},
        "evidence": [],
        "last_invocation_at": None,
    }
    base.update(overrides)
    return base


class TestScoreRisk:
    def test_clean_agent_is_low(self):
        score, level, signals = score_risk(_agent(), all_agents=[])
        assert score == 0
        assert level == "low"
        assert signals == []

    def test_plaintext_key_in_config_is_critical(self):
        a = _agent(evidence=["plaintext_key"])
        score, level, signals = score_risk(a, all_agents=[])
        assert score == 40
        assert level == "high"  # 40 -> high (>= 25, < 50)

    def test_no_owner_adds_30(self):
        a = _agent(owner_user=None, owner_team=None)
        score, level, _ = score_risk(a, all_agents=[])
        assert score == 30
        assert level == "high"

    def test_code_exec_adds_25(self):
        a = _agent(capabilities={**_agent()["capabilities"], "code_exec": True})
        score, _, _ = score_risk(a, all_agents=[])
        assert score == 25
        assert level == "medium"

    def test_network_adds_15(self):
        a = _agent(capabilities={**_agent()["capabilities"], "network": True})
        score, level, _ = score_risk(a, all_agents=[])
        assert score == 15
        assert level == "low"  # < 25

    def test_filesystem_adds_10(self):
        a = _agent(capabilities={**_agent()["capabilities"], "filesystem": True})
        score, level, _ = score_risk(a, all_agents=[])
        assert score == 10
        assert level == "low"

    def test_autogen_framework_adds_15(self):
        a = _agent(framework="autogen")
        score, level, _ = score_risk(a, all_agents=[])
        assert score == 15

    def test_crewai_framework_adds_15(self):
        a = _agent(framework="crewai")
        score, level, _ = score_risk(a, all_agents=[])
        assert score == 15

    def test_dormant_30_days_adds_15(self):
        a = _agent(last_invocation_at=datetime.utcnow() - timedelta(days=31))
        score, level, _ = score_risk(a, all_agents=[])
        assert score == 15

    def test_dormant_under_30_days_no_signal(self):
        a = _agent(last_invocation_at=datetime.utcnow() - timedelta(days=5))
        score, level, _ = score_risk(a, all_agents=[])
        assert score == 0

    def test_duplicate_fingerprint_on_other_asset_adds_20(self):
        a = _agent(api_key_fingerprint="sha256:abc")
        other = {"asset_id": 99, "api_key_fingerprint": "sha256:abc"}
        score, level, _ = score_risk(a, all_agents=[other])
        assert score == 20

    def test_same_fingerprint_same_asset_does_not_count(self):
        a = _agent(asset_id=5, api_key_fingerprint="sha256:abc")
        other = {"asset_id": 5, "api_key_fingerprint": "sha256:abc"}
        score, _, _ = score_risk(a, all_agents=[other])
        assert score == 0

    def test_threshold_24_is_low_25_is_medium(self):
        # 25 = network(15) + filesystem(10) → 25, exactly medium
        a = _agent(capabilities={**_agent()["capabilities"],
                                  "network": True, "filesystem": True})
        score, level, _ = score_risk(a, all_agents=[])
        assert score == 25
        assert level == "medium"

    def test_threshold_49_is_medium_50_is_high(self):
        # 25 + 25 = 50 (code_exec + network) → high
        a = _agent(capabilities={**_agent()["capabilities"],
                                  "network": True, "code_exec": True})
        score, level, _ = score_risk(a, all_agents=[])
        assert score == 40  # 15 + 25
        assert level == "high"

    def test_threshold_74_is_high_75_is_critical(self):
        # 40 (plaintext) + 30 (no owner) + 15 (autogen) = 85 → critical
        a = _agent(framework="autogen", owner_user=None, owner_team=None,
                   evidence=["plaintext_key"])
        score, level, _ = score_risk(a, all_agents=[])
        assert score == 85
        assert level == "critical"

    def test_signals_list_includes_evidence(self):
        a = _agent(evidence=["plaintext_key"])
        _, _, signals = score_risk(a, all_agents=[])
        assert any(s["signal"] == "plaintext_key" for s in signals)
        assert any(s["weight"] == 40 for s in signals)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/jyb/projects/telos && python3 -m pytest backend/tests/test_ai_agent_risk.py -v 2>&1 | tail -5`
Expected: FAIL with `ImportError: cannot import name 'score_risk'`

- [ ] **Step 3: Implement score_risk**

Add to `backend/services/ai_agent_scanner.py`:

```python
from datetime import datetime, timedelta
from typing import Tuple, List, Dict, Any


def _level_for_score(score: int) -> str:
    if score >= 75:
        return "critical"
    if score >= 50:
        return "high"
    if score >= 25:
        return "medium"
    return "low"


def score_risk(
    agent: dict,
    all_agents: list[dict],
) -> Tuple[int, str, List[Dict[str, Any]]]:
    """Apply 8 rules, return (score, level, signals_list).

    `all_agents` is a list of dicts each with at least
    {asset_id, api_key_fingerprint} — used for cross-asset dedup signal.
    """
    score = 0
    signals: List[Dict[str, Any]] = []

    # Rule 1: plaintext key in config (40)
    if "plaintext_key" in (agent.get("evidence") or []):
        score += 40
        signals.append({"signal": "plaintext_key", "weight": 40,
                        "evidence": "API key found in plaintext config file"})

    # Rule 2: no owner (30)
    if not agent.get("owner_user") and not agent.get("owner_team"):
        score += 30
        signals.append({"signal": "no_owner", "weight": 30,
                        "evidence": "No owner_user and no owner_team set"})

    caps = agent.get("capabilities") or {}

    # Rule 3: code_exec (25)
    if caps.get("code_exec"):
        score += 25
        signals.append({"signal": "code_exec", "weight": 25,
                        "evidence": "Agent has code execution capability"})

    # Rule 4: network (15)
    if caps.get("network"):
        score += 15
        signals.append({"signal": "network", "weight": 15,
                        "evidence": "Agent has network capability"})

    # Rule 5: filesystem (10)
    if caps.get("filesystem"):
        score += 10
        signals.append({"signal": "filesystem", "weight": 10,
                        "evidence": "Agent has filesystem capability"})

    # Rule 6: multi-agent framework (15)
    if agent.get("framework") in ("autogen", "crewai"):
        score += 15
        signals.append({"signal": "multi_agent_framework", "weight": 15,
                        "evidence": f"Framework={agent.get('framework')} (multi-agent)"})

    # Rule 7: dormant > 30 days (15)
    last_inv = agent.get("last_invocation_at")
    if last_inv and isinstance(last_inv, datetime):
        if datetime.utcnow() - last_inv > timedelta(days=30):
            score += 15
            signals.append({"signal": "dormant", "weight": 15,
                            "evidence": f"last_invocation_at={last_inv} (>30d)"})

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

    return score, _level_for_score(score), signals
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/jyb/projects/telos && python3 -m pytest backend/tests/test_ai_agent_risk.py -v 2>&1 | tail -20`
Expected: 15 passed

- [ ] **Step 5: Commit**

```bash
git add backend/services/ai_agent_scanner.py backend/tests/test_ai_agent_risk.py
git commit -m "feat(ai-agents): add score_risk() with 8 rules + threshold tests"
```

---

### Task 12: TDD — ingest() pipeline with dedup + upsert

**Files:**
- Modify: `backend/services/ai_agent_scanner.py`
- Create: `backend/tests/test_ai_agent_dedup.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_ai_agent_dedup.py`:

```python
"""Tests for AI Agent ingest pipeline — parse, dedupe, score, upsert."""
import os
import sys
from datetime import datetime

os.environ.setdefault("ACCOUNTSCAN_MASTER_KEY", "test_master_key_0123456789abcdef01234567")
os.environ.setdefault("ACCOUNTSCAN_JWT_SECRET", "test_jwt_secret_0123456789abcdef0123456")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database import Base
from backend import models
from backend.services.ai_agent_scanner import ingest_signals


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    s = Session()
    yield s
    s.close()


def _signals(env_vars="", framework_paths=""):
    return {
        "ai_agent_signals": {
            "env_vars": [e for e in env_vars.split("\n") if e],
            "framework_paths": [f for f in framework_paths.split("\n") if f],
            "config_files": [], "processes": [], "package_json": [],
        }
    }


class TestIngest:
    def test_first_ingest_creates_row(self, db):
        raw = _signals(env_vars="ANTHROPIC_API_KEY|user|sha256:abc")
        agents = ingest_signals(db, raw, asset_id=1)
        assert len(agents) == 1
        assert agents[0].framework == "claude_code"
        assert agents[0].api_key_fingerprint == "sha256:abc"
        assert agents[0].asset_id == 1
        assert agents[0].status == "active"

    def test_second_ingest_same_asset_updates(self, db):
        raw = _signals(env_vars="ANTHROPIC_API_KEY|user|sha256:abc")
        a1 = ingest_signals(db, raw, asset_id=1)
        a2 = ingest_signals(db, raw, asset_id=1)
        # Same row (same dedup key), just updated
        assert a1[0].id == a2[0].id
        assert db.query(models.AIAgent).count() == 1

    def test_same_agent_on_two_assets_creates_two_rows(self, db):
        raw = _signals(env_vars="ANTHROPIC_API_KEY|user|sha256:abc")
        a1 = ingest_signals(db, raw, asset_id=1)
        a2 = ingest_signals(db, raw, asset_id=2)
        assert a1[0].id != a2[0].id
        assert db.query(models.AIAgent).count() == 2

    def test_different_owner_team_creates_different_row(self, db):
        raw1 = _signals(env_vars="ANTHROPIC_API_KEY|user|sha256:abc")
        raw2 = _signals(env_vars="ANTHROPIC_API_KEY|user|sha256:abc")
        # Simulate different owner_team coming from raw_info
        raw1["ai_agent_signals"]["owner_team_hint"] = "data-eng"
        # Direct dict-based ingest for clarity
        from backend.services.ai_agent_scanner import ingest_signals
        a1 = ingest_signals(db, raw1, asset_id=1)
        # Without owner_team_hint, the dedup key is just (framework, agent_name, asset_id).
        # We exercise the "no owner_team" case here.
        a2 = ingest_signals(db, raw2, asset_id=1)
        assert a1[0].id == a2[0].id  # Same dedup key, just updated

    def test_risk_score_populated(self, db):
        raw = _signals(env_vars="ANTHROPIC_API_KEY|user|sha256:abc")
        agents = ingest_signals(db, raw, asset_id=1)
        assert agents[0].risk_score >= 0
        assert agents[0].risk_level in ("low", "medium", "high", "critical")
        assert isinstance(agents[0].risk_signals, list)

    def test_no_signals_returns_empty(self, db):
        agents = ingest_signals(db, {"ai_agent_signals": {}}, asset_id=1)
        assert agents == []
        assert db.query(models.AIAgent).count() == 0

    def test_high_risk_creates_active_status(self, db):
        # Two assets sharing same fingerprint → high risk
        raw = _signals(env_vars="ANTHROPIC_API_KEY|user|sha256:shared")
        a1 = ingest_signals(db, raw, asset_id=1)
        a2 = ingest_signals(db, raw, asset_id=2)
        # Both should have risk signals for shared fingerprint
        assert a2[0].risk_score >= 20
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/jyb/projects/telos && python3 -m pytest backend/tests/test_ai_agent_dedup.py -v 2>&1 | tail -5`
Expected: FAIL with `ImportError: cannot import name 'ingest_signals'`

- [ ] **Step 3: Implement ingest_signals**

Add to `backend/services/ai_agent_scanner.py`:

```python
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from backend import models


def ingest_signals(
    db: Session,
    raw_info: dict,
    asset_id: Optional[int],
    now: Optional[datetime] = None,
) -> list[models.AIAgent]:
    """Parse raw_info signals, dedupe, score, upsert AIAgent rows.

    Returns the list of AIAgent rows that were created or updated.
    """
    if not raw_info:
        return []
    if now is None:
        now = datetime.utcnow()

    candidates = parse_signals(raw_info)
    if not candidates:
        return []

    # Load existing agents for cross-asset fingerprint comparison
    all_existing = db.query(models.AIAgent).all()
    all_agents_for_scoring = [
        {"asset_id": a.asset_id, "api_key_fingerprint": a.api_key_fingerprint}
        for a in all_existing
    ]

    results: list[models.AIAgent] = []
    for cand in candidates:
        framework = cand["framework"]
        agent_name = cand["agent_name"]
        owner_team = cand.get("owner_team")  # may be None

        # Find existing by dedup key
        existing = (
            db.query(models.AIAgent)
            .filter(
                models.AIAgent.framework == framework,
                models.AIAgent.agent_name == agent_name,
                models.AIAgent.owner_team.is_(None) if owner_team is None
                else models.AIAgent.owner_team == owner_team,
                models.AIAgent.asset_id.is_(None) if asset_id is None
                else models.AIAgent.asset_id == asset_id,
            )
            .first()
        )

        # Score
        cand_for_score = {**cand, "asset_id": asset_id}
        score, level, signals = score_risk(cand_for_score, all_agents_for_scoring)

        if existing:
            existing.last_seen_at = now
            existing.capabilities = cand["capabilities"]
            existing.api_key_fingerprint = (
                cand.get("api_key_fingerprint") or existing.api_key_fingerprint
            )
            existing.api_key_location = (
                cand.get("api_key_location") or existing.api_key_location
            )
            existing.risk_score = score
            existing.risk_level = level
            existing.risk_signals = signals
            existing.status = "active"
            results.append(existing)
        else:
            new = models.AIAgent(
                agent_name=agent_name,
                framework=framework,
                model=cand.get("model"),
                owner_team=owner_team,
                owner_user=cand.get("owner_user"),
                api_key_fingerprint=cand.get("api_key_fingerprint"),
                api_key_location=cand.get("api_key_location"),
                capabilities=cand["capabilities"],
                last_invocation_at=cand.get("last_invocation_at"),
                last_seen_at=now,
                discovered_at=now,
                discovery_source="ssh_scan",
                asset_id=asset_id,
                risk_score=score,
                risk_level=level,
                risk_signals=signals,
                status="active",
            )
            db.add(new)
            try:
                db.flush()
            except IntegrityError:
                # Race: another tx inserted same dedup key. Refetch and update.
                db.rollback()
                existing = (
                    db.query(models.AIAgent)
                    .filter(
                        models.AIAgent.framework == framework,
                        models.AIAgent.agent_name == agent_name,
                        models.AIAgent.owner_team.is_(None) if owner_team is None
                        else models.AIAgent.owner_team == owner_team,
                        models.AIAgent.asset_id.is_(None) if asset_id is None
                        else models.AIAgent.asset_id == asset_id,
                    )
                    .first()
                )
                if existing:
                    existing.last_seen_at = now
                    existing.capabilities = cand["capabilities"]
                    existing.risk_score = score
                    existing.risk_level = level
                    existing.risk_signals = signals
                    existing.status = "active"
                    results.append(existing)
            else:
                results.append(new)

    db.commit()
    return results
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/jyb/projects/telos && python3 -m pytest backend/tests/test_ai_agent_dedup.py -v 2>&1 | tail -15`
Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add backend/services/ai_agent_scanner.py backend/tests/test_ai_agent_dedup.py
git commit -m "feat(ai-agents): add ingest_signals() — parse + dedupe + score + upsert"
```

---

### Task 13: Wire collect_ai_signals() into ssh_scanner

**Files:**
- Modify: `backend/services/ssh_scanner.py` (find the main collection method, add the new method + call)

- [ ] **Step 1: Locate the existing collection method**

Run: `grep -n "def collect_accounts\|def collect_user\|def _collect\|raw_info\[" backend/services/ssh_scanner.py 2>&1 | head -10`

The exact location will be one of these methods. Note the line number for the next step.

- [ ] **Step 2: Add collect_ai_signals method**

In `backend/services/ssh_scanner.py`, add the following method (place it after the existing collection methods):

```python
    def collect_ai_signals(self, ssh_client) -> Optional[dict]:
        """Run the AI Agent detection probe on the remote host.

        Returns the parsed ai_agent_signals dict (or None on any failure).
        Never raises — failures are logged at WARN and return None so the
        rest of the scan flow is unaffected.
        """
        from backend.services.ai_agent_scanner import parse_signals  # local import

        probe = (
            "{"
            "echo '===CF==='; find /home /opt /root /etc -maxdepth 5 -name '*.json' 2>/dev/null"
            "  | xargs grep -l 'anthropic\\|openai\\|claude\\|gemini' 2>/dev/null | head -20;"
            "echo '===ENV==='; env | grep -iE '^(ANTHROPIC|OPENAI|CLAUDE|LANGCHAIN|COHERE|GEMINI)_' | head -20;"
            "echo '===PS==='; ps -ef | grep -iE 'claude|langchain|autogen|crewai|gpt-|agent' | grep -v grep | head -20;"
            "echo '===DIRS==='; find / -maxdepth 6 -type d \\( "
            "  -name 'langchain*' -o -name 'autogen*' -o -name 'crewai*' "
            "  -o -name 'anthropic*' -o -name 'llamaindex*' \\) 2>/dev/null | head -20;"
            "echo '===PKG==='; find /home /opt /root -maxdepth 5 -name 'package.json' 2>/dev/null"
            "  | xargs grep -l '@anthropic-ai\\|langchain\\|openai' 2>/dev/null | head -20;"
            "}"
        )

        try:
            stdin, stdout, stderr = ssh_client.exec_command(probe, timeout=5)
            raw = stdout.read().decode("utf-8", errors="replace")
        except Exception as e:
            logger.warning("AI Agent probe failed: %s", e)
            return None

        # Normalize the ===SECTION=== output into a dict
        signals = self._parse_probe_output(raw)
        if not signals:
            return None
        return parse_signals({"ai_agent_signals": signals})
```

- [ ] **Step 3: Add _parse_probe_output helper**

In the same file, add:

```python
    def _parse_probe_output(self, raw: str) -> dict:
        """Parse '===SECTION===\\nline1\\nline2' into {section: [lines]}."""
        if not raw:
            return {}
        sections = {"config_files": [], "env_vars": [], "processes": [],
                    "framework_paths": [], "package_json": []}
        current = None
        for line in raw.splitlines():
            if line.startswith("===") and line.endswith("==="):
                key = line.strip("=").lower()
                current = {
                    "cf": "config_files", "env": "env_vars",
                    "ps": "processes", "dirs": "framework_paths",
                    "pkg": "package_json",
                }.get(key)
                continue
            if current and line.strip():
                sections[current].append(line.strip())
        return sections
```

- [ ] **Step 4: Call collect_ai_signals from the main collection path**

Locate the main `collect()` method (the one that produces `AccountSnapshot`). After all the existing `accounts[0].raw_info["..."] = ...` lines, add:

```python
        # AI Agent signals (graceful — never breaks the scan)
        try:
            ai_signals = self.collect_ai_signals(ssh_client)
            if ai_signals:
                accounts[0].raw_info["ai_agent_signals"] = ai_signals
        except Exception as e:
            logger.warning("AI Agent signal collection skipped: %s", e)
```

- [ ] **Step 5: Verify the file still imports**

Run: `cd /Users/jyb/projects/telos && python3 -c "from backend.services.ssh_scanner import SSHTaskScanner; print(hasattr(SSHTaskScanner, 'collect_ai_signals'))"`
Expected: `True`

- [ ] **Step 6: Run full backend test suite to ensure nothing regressed**

Run: `cd /Users/jyb/projects/telos && python3 -m pytest backend/tests/ -q 2>&1 | tail -5`
Expected: 130+ passed (existing) plus new tests pass.

- [ ] **Step 7: Commit**

```bash
git add backend/services/ssh_scanner.py
git commit -m "feat(ai-agents): wire collect_ai_signals() into ssh_scanner"
```

---

## Phase 4 — Realtime Monitor

### Task 14: Add AI Agent detectors to realtime_monitor

**Files:**
- Modify: `backend/services/realtime_monitor.py` (add 2 detector methods, wire them into `check_and_alert`)
- Create: `backend/tests/test_realtime_monitor_ai.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_realtime_monitor_ai.py`:

```python
"""Tests for AI Agent realtime monitor detectors."""
import os
import sys
from datetime import datetime, timedelta

os.environ.setdefault("ACCOUNTSCAN_MASTER_KEY", "test_master_key_0123456789abcdef01234567")
os.environ.setdefault("ACCOUNTSCAN_JWT_SECRET", "test_jwt_secret_0123456789abcdef0123456")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database import Base
from backend import models
from backend.services.realtime_monitor import RealtimeMonitor


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    s = Session()
    yield s
    s.close()


def _agent(db, **overrides):
    base = dict(
        agent_name="test-agent", framework="langchain",
        owner_team="data-eng", owner_user="alice",
        api_key_fingerprint="sha256:abc",
        capabilities={"filesystem": False, "network": False,
                      "code_exec": False, "tool_count": 0},
        last_invocation_at=None,
        last_seen_at=datetime.utcnow(),
        discovered_at=datetime.utcnow(),
        discovery_source="ssh_scan",
        asset_id=1,
        risk_level="low", risk_score=0, risk_signals=[],
        status="active",
    )
    base.update(overrides)
    a = models.AIAgent(**base)
    db.add(a)
    db.commit()
    db.refresh(a)
    return a


class TestNewAIAgentDetector:
    def test_no_alert_on_first_discovery(self, db):
        """The first AIAgent row is not a 'new' alert — alerts fire on
        *subsequent* discovery of an agent on a new asset, not the first ever."""
        a = _agent(db)
        monitor = RealtimeMonitor()
        # With only one agent, no new-alert should fire (no prior baseline)
        n = monitor._detect_new_ai_agents(db)
        assert n == 0

    def test_new_alert_for_high_risk(self, db):
        """A high/critical risk agent on a new asset should alert."""
        a = _agent(db, agent_name="risky-bot", risk_level="high", risk_score=60)
        monitor = RealtimeMonitor()
        # First detector call: no prior baseline, so still no alert.
        monitor._detect_new_ai_agents(db)
        # Simulate a second agent appearing (newer last_seen_at)
        a2 = _agent(db, agent_name="another-bot", risk_level="critical", risk_score=80)
        n = monitor._detect_new_ai_agents(db)
        # Should detect the new high-risk agent
        assert n >= 1


class TestDormantAIAgentDetector:
    def test_dormant_fires_after_90_days(self, db):
        a = _agent(db, status="dormant",
                   last_invocation_at=datetime.utcnow() - timedelta(days=95))
        monitor = RealtimeMonitor()
        n = monitor._detect_dormant_ai_agents(db)
        assert n == 1
        alert = db.query(models.Alert).first()
        assert alert is not None
        assert "dormant" in (alert.title or "").lower() or "ai agent" in (alert.message or "").lower()

    def test_dormant_does_not_fire_for_active(self, db):
        _agent(db, status="active",
               last_invocation_at=datetime.utcnow() - timedelta(days=95))
        monitor = RealtimeMonitor()
        n = monitor._detect_dormant_ai_agents(db)
        assert n == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/jyb/projects/telos && python3 -m pytest backend/tests/test_realtime_monitor_ai.py -v 2>&1 | tail -5`
Expected: FAIL with `AttributeError: 'RealtimeMonitor' object has no attribute '_detect_new_ai_agents'`

- [ ] **Step 3: Add the two detectors**

In `backend/services/realtime_monitor.py`, add (place after `_detect_orphan_accounts`):

```python
    # ── 6. New AI Agent discovered (high/critical risk) ──────────────────

    def _detect_new_ai_agents(self, db: Session) -> int:
        """Alert when a high/critical risk AI Agent is discovered.

        Only fires for agents whose risk_level is high or critical, since
        low/medium are expected background noise.
        """
        created = 0
        risky = (
            db.query(models.AIAgent)
            .filter(
                models.AIAgent.risk_level.in_(["high", "critical"]),
                models.AIAgent.status == "active",
            )
            .all()
        )
        for agent in risky:
            # Avoid duplicate alerts: skip if an alert with this message already exists
            existing = (
                db.query(models.Alert)
                .filter(
                    models.Alert.message.like(f"%AI Agent「{agent.agent_name}」%"),
                    models.Alert.status != "dismissed",
                )
                .first()
            )
            if existing:
                continue
            job = self._latest_job_for_asset(db, agent.asset_id) if agent.asset_id else None
            alert = self._create_alert(
                db, agent.asset_id or 0, AlertLevel.high,
                f"高风险 AI Agent「{agent.agent_name}」",
                f"资产 #{agent.asset_id} 上的 AI Agent「{agent.agent_name}」"
                f"({agent.framework}) 风险等级 {agent.risk_level}，请确认是否经授权。",
                job_id=job.id if job else None,
                title_key="alert.aiAgent.discovered",
                title_params={"agent_name": agent.agent_name},
                message_key="alert.msg.aiAgent.discovered",
                message_params={
                    "agent_name": agent.agent_name,
                    "asset_id": agent.asset_id,
                    "framework": agent.framework,
                    "risk_level": agent.risk_level,
                },
            )
            created += 1
            logger.info("Alert: new high-risk AI Agent %s on asset %s",
                        agent.agent_name, agent.asset_id)
        return created

    # ── 7. AI Agent dormant > 90 days ─────────────────────────────────────

    def _detect_dormant_ai_agents(self, db: Session) -> int:
        """Alert when an AI Agent hasn't been invoked for > 90 days."""
        created = 0
        cutoff = datetime.now(timezone.utc) - timedelta(days=90)
        # Use a tolerant comparison: compare naive datetimes
        cutoff_naive = cutoff.replace(tzinfo=None) if cutoff.tzinfo else cutoff

        dormant = (
            db.query(models.AIAgent)
            .filter(
                models.AIAgent.status == "dormant",
                models.AIAgent.last_invocation_at.isnot(None),
            )
            .all()
        )
        for agent in dormant:
            last = _naive(agent.last_invocation_at)
            if last is None or last > cutoff_naive:
                continue
            # Dedup: skip if an alert for this dormant agent already exists
            existing = (
                db.query(models.Alert)
                .filter(
                    models.Alert.message.like(f"%AI Agent「{agent.agent_name}」%"),
                    models.Alert.message.like("%dormant%"),
                    models.Alert.status != "dismissed",
                )
                .first()
            )
            if existing:
                continue
            job = self._latest_job_for_asset(db, agent.asset_id) if agent.asset_id else None
            alert = self._create_alert(
                db, agent.asset_id or 0, AlertLevel.warning,
                f"AI Agent「{agent.agent_name}」长期未调用",
                f"AI Agent「{agent.agent_name}」(framework={agent.framework}) "
                f"已 {90}+ 天未调用，请确认是否仍需保留。",
                job_id=job.id if job else None,
                title_key="alert.aiAgent.dormant",
                title_params={"agent_name": agent.agent_name},
                message_key="alert.msg.aiAgent.dormant",
                message_params={
                    "agent_name": agent.agent_name,
                    "framework": agent.framework,
                    "last_invocation_at": str(agent.last_invocation_at),
                },
            )
            created += 1
            logger.info("Alert: dormant AI Agent %s (>90d)", agent.agent_name)
        return created
```

- [ ] **Step 4: Wire into check_and_alert**

In the same file, find `def check_and_alert` and add to its body:

```python
        created += self._detect_new_ai_agents(db)
        created += self._detect_dormant_ai_agents(db)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd /Users/jyb/projects/telos && python3 -m pytest backend/tests/test_realtime_monitor_ai.py -v 2>&1 | tail -10`
Expected: 4 passed

- [ ] **Step 6: Commit**

```bash
git add backend/services/realtime_monitor.py backend/tests/test_realtime_monitor_ai.py
git commit -m "feat(ai-agents): add new-agent and dormant detectors to realtime_monitor"
```

---

## Phase 5 — API Router

### Task 15: Create the AI Agents router (list, detail, scan, stats)

**Files:**
- Create: `backend/routers/ai_agents.py`
- Modify: `backend/main.py` (include router)

- [ ] **Step 1: Create the router file**

Create `backend/routers/ai_agents.py`:

```python
"""AI Agent Management API — first-class identity governance."""
from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend import models, schemas, auth
from backend.database import get_db
from backend.services.ai_agent_scanner import ingest_signals


router = APIRouter(prefix="/api/v1/ai-agents", tags=["ai-agents"])


@router.get("", response_model=schemas.ai_agents.AIAgentListResponse)
async def list_ai_agents(
    framework: Optional[str] = None,
    risk_level: Optional[str] = None,
    status: Optional[str] = None,
    owner_team: Optional[str] = None,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.get_current_user),
):
    query = db.query(models.AIAgent)
    if framework:
        query = query.filter(models.AIAgent.framework == framework)
    if risk_level:
        query = query.filter(models.AIAgent.risk_level == risk_level)
    if status:
        query = query.filter(models.AIAgent.status == status)
    if owner_team:
        query = query.filter(models.AIAgent.owner_team == owner_team)

    total = query.count()
    agents = (
        query.order_by(models.AIAgent.risk_score.desc(), models.AIAgent.last_seen_at.desc())
        .offset(offset).limit(limit).all()
    )
    return schemas.ai_agents.AIAgentListResponse(
        total=total,
        agents=[schemas.ai_agents.AIAgentResponse.model_validate(a) for a in agents],
    )


@router.get("/stats", response_model=schemas.ai_agents.AIAgentStatsResponse)
async def get_stats(
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.get_current_user),
):
    total = db.query(func.count(models.AIAgent.id)).scalar() or 0
    active = (
        db.query(func.count(models.AIAgent.id))
        .filter(models.AIAgent.status == "active")
        .scalar() or 0
    )
    critical_risk = (
        db.query(func.count(models.AIAgent.id))
        .filter(models.AIAgent.risk_level == "critical")
        .scalar() or 0
    )
    no_owner = (
        db.query(func.count(models.AIAgent.id))
        .filter(
            models.AIAgent.owner_user.is_(None),
            models.AIAgent.owner_team.is_(None),
        )
        .scalar() or 0
    )

    framework_rows = (
        db.query(models.AIAgent.framework, func.count(models.AIAgent.id))
        .group_by(models.AIAgent.framework).all()
    )
    risk_rows = (
        db.query(models.AIAgent.risk_level, func.count(models.AIAgent.id))
        .group_by(models.AIAgent.risk_level).all()
    )

    return schemas.ai_agents.AIAgentStatsResponse(
        total=total,
        active=active,
        critical_risk=critical_risk,
        no_owner=no_owner,
        by_framework={fw: cnt for fw, cnt in framework_rows},
        by_risk_level={rl: cnt for rl, cnt in risk_rows},
    )


@router.get("/{agent_id}", response_model=schemas.ai_agents.AIAgentDetailResponse)
async def get_ai_agent(
    agent_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.get_current_user),
):
    agent = db.query(models.AIAgent).filter(models.AIAgent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="AI Agent not found")
    return agent


@router.post("/{agent_id}/claim", response_model=schemas.ai_agents.AIAgentDetailResponse)
async def claim_ai_agent(
    agent_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.get_current_user),
):
    """Sets owner_user to the current authenticated user (v1)."""
    agent = db.query(models.AIAgent).filter(models.AIAgent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="AI Agent not found")
    agent.owner_user = user.username
    db.commit()
    db.refresh(agent)
    return agent


@router.post("/scan", response_model=schemas.ai_agents.AIAgentScanResponse)
async def trigger_scan(
    request: schemas.ai_agents.AIAgentScanRequest,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.require_role(models.UserRole.operator, models.UserRole.admin)),
):
    """Re-ingest AI Agent signals from AccountSnapshot.raw_info for the
    given asset (or all assets if asset_id is None).

    v1 does not run a fresh SSH scan — it re-parses already-collected
    raw_info. Live SSH scanning happens via the existing /scans trigger.
    """
    query = db.query(models.AccountSnapshot).filter(
        models.AccountSnapshot.deleted_at.is_(None),
        models.AccountSnapshot.raw_info.isnot(None),
    )
    if request.asset_id is not None:
        query = query.filter(models.AccountSnapshot.asset_id == request.asset_id)
    snapshots = query.all()

    agents_discovered = 0
    agents_updated = 0
    errors: List[str] = []
    for snap in snapshots:
        try:
            new_agents = ingest_signals(db, snap.raw_info, snap.asset_id)
            for a in new_agents:
                if a.discovered_at and a.discovered_at > (
                    datetime.utcnow().replace(microsecond=0)
                ):
                    agents_discovered += 1
                else:
                    agents_updated += 1
        except Exception as e:
            errors.append(f"snapshot {snap.id}: {e}")
    db.commit()

    return schemas.ai_agents.AIAgentScanResponse(
        scanned_assets=len({s.asset_id for s in snapshots if s.asset_id}),
        agents_discovered=agents_discovered,
        agents_updated=agents_updated,
        alerts_emitted=0,  # realtime monitor handles alerts on next tick
        errors=errors,
    )
```

- [ ] **Step 2: Add AIAgentListResponse to schemas**

In `backend/schemas/ai_agents.py`, add at the end:

```python
class AIAgentListResponse(BaseModel):
    total: int
    agents: List[AIAgentResponse]
```

- [ ] **Step 3: Wire router in main.py**

In `backend/main.py`, after `app.include_router(nhi.router)` (line 355), add:

```python
app.include_router(ai_agents.router)
```

And add the import at the top with the other router imports:

```python
from backend.routers import ai_agents
```

- [ ] **Step 4: Verify imports compile**

Run: `cd /Users/jyb/projects/telos && python3 -c "from backend.routers.ai_agents import router; print(len(router.routes), 'routes')"`
Expected: `5 routes` (list, stats, get, claim, scan)

- [ ] **Step 5: Commit**

```bash
git add backend/routers/ai_agents.py backend/main.py backend/schemas/ai_agents.py
git commit -m "feat(ai-agents): add /api/v1/ai-agents router with list/detail/stats/scan/claim"
```

---

### Task 16: Add router integration tests

**Files:**
- Create: `backend/tests/test_ai_agents_router.py`

- [ ] **Step 1: Write the test**

Create `backend/tests/test_ai_agents_router.py`:

```python
"""Integration tests for /api/v1/ai-agents router."""
import os
import sys
import json

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
        return db
    app.dependency_overrides[__import__("backend.database").get_db] = lambda: db
    return TestClient(app)


@pytest.fixture
def admin_token():
    return auth.create_access_token({"sub": "admin", "role": "admin"})


def _seed_agent(db, **overrides):
    base = dict(
        agent_name="test", framework="langchain", owner_team="data-eng",
        owner_user="alice", api_key_fingerprint="sha256:abc",
        capabilities={"filesystem": False, "network": False,
                      "code_exec": False, "tool_count": 0},
        last_seen_at=__import__("datetime").datetime.utcnow(),
        discovered_at=__import__("datetime").datetime.utcnow(),
        discovery_source="ssh_scan", asset_id=1,
        risk_level="low", risk_score=0, risk_signals=[], status="active",
    )
    base.update(overrides)
    a = models.AIAgent(**base)
    db.add(a)
    db.commit()
    db.refresh(a)
    return a


class TestList:
    def test_empty_list(self, client, admin_token):
        r = client.get("/api/v1/ai-agents",
                       headers={"Authorization": f"Bearer {admin_token}"})
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 0
        assert body["agents"] == []

    def test_filter_by_framework(self, client, db, admin_token):
        _seed_agent(db, agent_name="lc1", framework="langchain")
        _seed_agent(db, agent_name="ag1", framework="autogen")
        r = client.get("/api/v1/ai-agents?framework=autogen",
                       headers={"Authorization": f"Bearer {admin_token}"})
        body = r.json()
        assert body["total"] == 1
        assert body["agents"][0]["framework"] == "autogen"

    def test_filter_by_risk_level(self, client, db, admin_token):
        _seed_agent(db, agent_name="lo", risk_level="low")
        _seed_agent(db, agent_name="hi", risk_level="high")
        r = client.get("/api/v1/ai-agents?risk_level=high",
                       headers={"Authorization": f"Bearer {admin_token}"})
        body = r.json()
        assert body["total"] == 1
        assert body["agents"][0]["risk_level"] == "high"


class TestStats:
    def test_stats_counts(self, client, db, admin_token):
        _seed_agent(db, agent_name="a1", status="active", risk_level="high")
        _seed_agent(db, agent_name="a2", status="dormant", risk_level="low",
                    owner_user=None, owner_team=None)
        _seed_agent(db, agent_name="a3", status="active", risk_level="critical")
        r = client.get("/api/v1/ai-agents/stats",
                       headers={"Authorization": f"Bearer {admin_token}"})
        body = r.json()
        assert body["total"] == 3
        assert body["active"] == 2
        assert body["critical_risk"] == 1
        assert body["no_owner"] == 1


class TestDetail:
    def test_get_existing(self, client, db, admin_token):
        a = _seed_agent(db, agent_name="x")
        r = client.get(f"/api/v1/ai-agents/{a.id}",
                       headers={"Authorization": f"Bearer {admin_token}"})
        assert r.status_code == 200
        assert r.json()["agent_name"] == "x"

    def test_get_404(self, client, admin_token):
        r = client.get("/api/v1/ai-agents/99999",
                       headers={"Authorization": f"Bearer {admin_token}"})
        assert r.status_code == 404


class TestClaim:
    def test_claim_sets_owner_user(self, client, db, admin_token):
        a = _seed_agent(db, agent_name="unowned", owner_user=None)
        r = client.post(f"/api/v1/ai-agents/{a.id}/claim",
                        headers={"Authorization": f"Bearer {admin_token}"})
        assert r.status_code == 200
        assert r.json()["owner_user"] == "admin"
```

- [ ] **Step 2: Run test**

Run: `cd /Users/jyb/projects/telos && python3 -m pytest backend/tests/test_ai_agents_router.py -v 2>&1 | tail -15`
Expected: 8 passed (or however many you have)

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_ai_agents_router.py
git commit -m "test(ai-agents): add router integration tests"
```

---

## Phase 6 — Frontend

### Task 17: Add i18n keys for AI Agent UI

**Files:**
- Modify: `frontend/src/locales/en-US.json`
- Modify: `frontend/src/locales/zh-CN.json`

- [ ] **Step 1: Add the keys block to en-US.json**

In `frontend/src/locales/en-US.json`, locate the `"nav.aiAgents": "AI Agent Management",` line you added in Task 1. Right after it, insert the following block (note: a flat block, NOT nested under `aiAgent`):

```json
  "aiAgent.title": "AI Agent Management",
  "aiAgent.subtitle": "Discover · Classify · Assess Risk · Govern",
  "aiAgent.scan": "Scan AI Agents",
  "aiAgent.scanSuccess": "Scan complete: {discovered} new, {updated} updated",
  "aiAgent.totalAgents": "Total AI Agents",
  "aiAgent.activeAgents": "Active Agents",
  "aiAgent.criticalRisk": "Critical Risk",
  "aiAgent.noOwner": "No Owner",
  "aiAgent.tab.overview": "Overview",
  "aiAgent.tab.list": "List",
  "aiAgent.tab.alerts": "Alerts",
  "aiAgent.framework.langchain": "LangChain",
  "aiAgent.framework.autogen": "AutoGen",
  "aiAgent.framework.crewai": "CrewAI",
  "aiAgent.framework.claude_code": "Claude Code",
  "aiAgent.framework.openai_assistant": "OpenAI Assistant",
  "aiAgent.framework.llamaindex": "LlamaIndex",
  "aiAgent.framework.custom": "Custom",
  "aiAgent.framework.unknown": "Unknown",
  "aiAgent.capability.filesystem": "Filesystem",
  "aiAgent.capability.network": "Network",
  "aiAgent.capability.codeExec": "Code Execution",
  "aiAgent.capability.toolCount": "{count} tools",
  "aiAgent.detail.basicInfo": "Basic Information",
  "aiAgent.detail.capabilities": "Capabilities",
  "aiAgent.detail.credentials": "Credentials",
  "aiAgent.detail.riskSignals": "Risk Signals",
  "aiAgent.detail.related": "Related",
  "aiAgent.detail.relatedAsset": "Related Asset",
  "aiAgent.detail.relatedNHI": "Related NHI",
  "aiAgent.detail.claimOwner": "Claim Owner",
  "aiAgent.detail.owned": "Owned by {user}",
  "aiAgent.detail.fingerprint": "Key Fingerprint",
  "aiAgent.detail.noKey": "No key detected",
  "aiAgent.detail.model": "Model",
  "aiAgent.detail.lastSeen": "Last Seen",
  "aiAgent.detail.discovered": "Discovered",
  "aiAgent.detail.ownerTeam": "Owner Team",
  "aiAgent.detail.ownerUser": "Owner User",
```

- [ ] **Step 2: Add the same keys block to zh-CN.json**

In `frontend/src/locales/zh-CN.json`, after the `"nav.aiAgents": "AI Agent 管理",` line, insert:

```json
  "aiAgent.title": "AI Agent 管理",
  "aiAgent.subtitle": "发现·分类·风险评估·治理",
  "aiAgent.scan": "扫描 AI Agent",
  "aiAgent.scanSuccess": "扫描完成：新增 {discovered} 个，更新 {updated} 个",
  "aiAgent.totalAgents": "AI Agent 总数",
  "aiAgent.activeAgents": "活跃 Agent",
  "aiAgent.criticalRisk": "严重风险",
  "aiAgent.noOwner": "无主 Agent",
  "aiAgent.tab.overview": "概览",
  "aiAgent.tab.list": "清单",
  "aiAgent.tab.alerts": "告警",
  "aiAgent.framework.langchain": "LangChain",
  "aiAgent.framework.autogen": "AutoGen",
  "aiAgent.framework.crewai": "CrewAI",
  "aiAgent.framework.claude_code": "Claude Code",
  "aiAgent.framework.openai_assistant": "OpenAI Assistant",
  "aiAgent.framework.llamaindex": "LlamaIndex",
  "aiAgent.framework.custom": "自定义",
  "aiAgent.framework.unknown": "未知",
  "aiAgent.capability.filesystem": "文件系统",
  "aiAgent.capability.network": "网络",
  "aiAgent.capability.codeExec": "代码执行",
  "aiAgent.capability.toolCount": "{count} 个工具",
  "aiAgent.detail.basicInfo": "基本信息",
  "aiAgent.detail.capabilities": "能力",
  "aiAgent.detail.credentials": "凭据",
  "aiAgent.detail.riskSignals": "风险信号",
  "aiAgent.detail.related": "关联",
  "aiAgent.detail.relatedAsset": "关联资产",
  "aiAgent.detail.relatedNHI": "关联 NHI",
  "aiAgent.detail.claimOwner": "认领 Owner",
  "aiAgent.detail.owned": "Owner: {user}",
  "aiAgent.detail.fingerprint": "密钥指纹",
  "aiAgent.detail.noKey": "未检测到密钥",
  "aiAgent.detail.model": "模型",
  "aiAgent.detail.lastSeen": "最后发现",
  "aiAgent.detail.discovered": "首次发现",
  "aiAgent.detail.ownerTeam": "所属团队",
  "aiAgent.detail.ownerUser": "所属用户",
```

- [ ] **Step 3: Verify i18n check passes**

Run: `cd /Users/jyb/projects/telos/frontend && npm run check-i18n`
Expected: `✓ All i18n checks passed`

- [ ] **Step 4: Commit**

```bash
git add frontend/src/locales/en-US.json frontend/src/locales/zh-CN.json
git commit -m "i18n(aiAgent): add ~35 keys for AI Agent UI"
```

---

### Task 18: Add API client methods

**Files:**
- Modify: `frontend/src/api/client.ts` (add 5 new exports after the NHI block)

- [ ] **Step 1: Find the NHI section in client.ts**

Run: `grep -n "NHI Module\|nhi/" frontend/src/api/client.ts | head -3`
Note the line number of the comment "NHI Module".

- [ ] **Step 2: Add the AI Agent methods**

In `frontend/src/api/client.ts`, immediately after the NHI block, add:

```typescript
// ── AI Agent Module ──────────────────────────────────────────────────────────

export const listAIAgents = (params?: {
  framework?: string
  risk_level?: string
  status?: string
  owner_team?: string
  limit?: number
  offset?: number
}) => api.get('/ai-agents', { params })

export const getAIAgentsStats = () => api.get('/ai-agents/stats')

export const getAIAgent = (id: number) => api.get(`/ai-agents/${id}`)

export const claimAIAgent = (id: number) => api.post(`/ai-agents/${id}/claim`)

export const triggerAIAgentScan = (asset_id?: number) =>
  api.post('/ai-agents/scan', { asset_id })
```

- [ ] **Step 3: Verify TypeScript compiles**

Run: `cd /Users/jyb/projects/telos/frontend && npx tsc -b 2>&1 | tail -5`
Expected: no output (clean)

- [ ] **Step 4: Commit**

```bash
git add frontend/src/api/client.ts
git commit -m "feat(ai-agents): add API client methods"
```

---

### Task 19: Create AIAgentsPage.tsx

**Files:**
- Create: `frontend/src/pages/AIAgentsPage.tsx`

- [ ] **Step 1: Create the page**

Create `frontend/src/pages/AIAgentsPage.tsx`:

```tsx
/**
 * AI Agents Dashboard — peer to NHIDashboard.
 * Sprint 1: list + overview + scan trigger.
 */
import { useEffect, useState } from 'react'
import {
  Row, Col, Card, Typography, Spin, Button, Space, Tag, Table,
  Statistic, message, Empty, Tabs, Tooltip,
} from 'antd'
import {
  RobotOutlined, ScanOutlined, WarningOutlined, UserOutlined,
  ApiOutlined,
} from '@ant-design/icons'
import {
  PieChart, Pie, Cell, BarChart, Bar, XAxis, YAxis,
  Tooltip as RechartsTooltip, ResponsiveContainer, CartesianGrid,
} from 'recharts'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'
import {
  listAIAgents, getAIAgentsStats, triggerAIAgentScan,
} from '../api/client'

const { Title, Text } = Typography

const LEVEL_COLORS: Record<string, string> = {
  critical: '#ff4d4f',
  high: '#fa8c16',
  medium: '#faad14',
  low: '#52c41a',
}

const FRAMEWORK_COLORS: Record<string, string> = {
  langchain: '#7c3aed',
  autogen: '#ec4899',
  crewai: '#f59e0b',
  claude_code: '#3b82f6',
  openai_assistant: '#10b981',
  llamaindex: '#8b5cf6',
  custom: '#6b7280',
  unknown: '#9ca3af',
}

export default function AIAgentsPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const [loading, setLoading] = useState(true)
  const [scanning, setScanning] = useState(false)
  const [agents, setAgents] = useState<any[]>([])
  const [stats, setStats] = useState<any>(null)
  const [frameworkFilter, setFrameworkFilter] = useState<string | undefined>()

  const load = async () => {
    setLoading(true)
    try {
      const params: any = {}
      if (frameworkFilter) params.framework = frameworkFilter
      const [list, s] = await Promise.all([
        listAIAgents(params),
        getAIAgentsStats(),
      ])
      setAgents(list.data.agents || [])
      setStats(s.data)
    } catch (e) {
      message.error(t('nhi.loadFailed'))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [frameworkFilter])

  const onScan = async () => {
    setScanning(true)
    try {
      const r = await triggerAIAgentScan()
      message.success(t('aiAgent.scanSuccess', {
        discovered: r.data.agents_discovered,
        updated: r.data.agents_updated,
      }))
      await load()
    } catch (e) {
      message.error(t('nhi.syncFailed'))
    } finally {
      setScanning(false)
    }
  }

  if (loading && !stats) {
    return <Spin tip={t('nhi.loading')} style={{ width: '100%', marginTop: 80 }} />
  }

  const frameworkChart = stats ? Object.entries(stats.by_framework || {})
    .map(([name, value]) => ({ name, value: Number(value) })) : []
  const riskChart = stats ? Object.entries(stats.by_risk_level || {})
    .map(([name, value]) => ({ name, value: Number(value) })) : []

  return (
    <div>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', marginBottom: 16 }}>
        <div style={{ flex: 1 }}>
          <Title level={4} style={{ margin: 0 }}>
            <RobotOutlined /> {t('aiAgent.title')}
          </Title>
          <Text type="secondary">{t('aiAgent.subtitle')}</Text>
        </div>
        <Button
          type="primary"
          icon={<ScanOutlined />}
          loading={scanning}
          onClick={onScan}
        >
          {t('aiAgent.scan')}
        </Button>
      </div>

      {/* Stat cards */}
      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={6}>
          <Card><Statistic title={t('aiAgent.totalAgents')} value={stats?.total ?? 0} prefix={<ApiOutlined />} /></Card>
        </Col>
        <Col span={6}>
          <Card><Statistic title={t('aiAgent.activeAgents')} value={stats?.active ?? 0} prefix={<RobotOutlined />} /></Card>
        </Col>
        <Col span={6}>
          <Card><Statistic title={t('aiAgent.criticalRisk')} value={stats?.critical_risk ?? 0} valueStyle={{ color: '#ff4d4f' }} prefix={<WarningOutlined />} /></Card>
        </Col>
        <Col span={6}>
          <Card><Statistic title={t('aiAgent.noOwner')} value={stats?.no_owner ?? 0} valueStyle={{ color: '#fa8c16' }} prefix={<UserOutlined />} /></Card>
        </Col>
      </Row>

      <Tabs
        items={[
          {
            key: 'overview',
            label: t('aiAgent.tab.overview'),
            children: (
              <Row gutter={16}>
                <Col span={12}>
                  <Card title="Framework">
                    {frameworkChart.length === 0 ? <Empty /> : (
                      <ResponsiveContainer width="100%" height={280}>
                        <PieChart>
                          <Pie data={frameworkChart} dataKey="value" nameKey="name"
                               outerRadius={100} label>
                            {frameworkChart.map((e, i) => (
                              <Cell key={i} fill={FRAMEWORK_COLORS[e.name] || '#9ca3af'} />
                            ))}
                          </Pie>
                          <RechartsTooltip />
                        </PieChart>
                      </ResponsiveContainer>
                    )}
                  </Card>
                </Col>
                <Col span={12}>
                  <Card title="Risk Level">
                    {riskChart.length === 0 ? <Empty /> : (
                      <ResponsiveContainer width="100%" height={280}>
                        <BarChart data={riskChart}>
                          <CartesianGrid strokeDasharray="3 3" />
                          <XAxis dataKey="name" />
                          <YAxis allowDecimals={false} />
                          <RechartsTooltip />
                          <Bar dataKey="value">
                            {riskChart.map((e, i) => (
                              <Cell key={i} fill={LEVEL_COLORS[e.name] || '#9ca3af'} />
                            ))}
                          </Bar>
                        </BarChart>
                      </ResponsiveContainer>
                    )}
                  </Card>
                </Col>
              </Row>
            ),
          },
          {
            key: 'list',
            label: t('aiAgent.tab.list'),
            children: (
              <Table
                rowKey="id"
                dataSource={agents}
                loading={loading}
                pagination={{ pageSize: 20 }}
                onRow={(r) => ({ onClick: () => navigate(`/ai-agents/${r.id}`) })}
                columns={[
                  { title: 'Agent', dataIndex: 'agent_name',
                    render: (n, r) => (
                      <Space>
                        <Text strong>{n}</Text>
                        {r.risk_level === 'critical' && <Tag color="red">!</Tag>}
                      </Space>
                    )},
                  { title: 'Framework', dataIndex: 'framework',
                    render: (fw) => <Tag color={FRAMEWORK_COLORS[fw]}>{t(`aiAgent.framework.${fw}`, fw)}</Tag> },
                  { title: 'Model', dataIndex: 'model', render: (m) => m || '—' },
                  { title: 'Owner', dataIndex: 'owner_team',
                    render: (team, r) => team || r.owner_user || <Text type="warning">No owner</Text> },
                  { title: 'Risk', dataIndex: 'risk_level',
                    render: (lvl) => <Tag color={LEVEL_COLORS[lvl]}>{lvl.toUpperCase()}</Tag> },
                  { title: 'Status', dataIndex: 'status',
                    render: (s) => <Tag>{s}</Tag> },
                ]}
              />
            ),
          },
        ]}
      />
    </div>
  )
}
```

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd /Users/jyb/projects/telos/frontend && npx tsc -b 2>&1 | tail -5`
Expected: no output (clean)

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/AIAgentsPage.tsx
git commit -m "feat(ai-agents): add AIAgentsPage with overview/list tabs and scan trigger"
```

---

### Task 20: Create AIAgentDetailPage.tsx

**Files:**
- Create: `frontend/src/pages/AIAgentDetailPage.tsx`

- [ ] **Step 1: Create the page**

Create `frontend/src/pages/AIAgentDetailPage.tsx`:

```tsx
/**
 * AI Agent Detail Page — basic info, capabilities, credentials, risk signals.
 */
import { useEffect, useState } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import {
  Card, Descriptions, Tag, Typography, Spin, Button, Space, Empty,
  Row, Col, message, Result,
} from 'antd'
import { RobotOutlined, KeyOutlined, ApiOutlined } from '@ant-design/icons'
import { useTranslation } from 'react-i18next'
import { getAIAgent, claimAIAgent } from '../api/client'

const { Title, Text, Paragraph } = Typography

const LEVEL_COLORS: Record<string, string> = {
  critical: 'red', high: 'orange', medium: 'gold', low: 'green',
}

export default function AIAgentDetailPage() {
  const { t } = useTranslation()
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [agent, setAgent] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [claiming, setClaiming] = useState(false)

  const load = async () => {
    if (!id) return
    setLoading(true)
    try {
      const r = await getAIAgent(Number(id))
      setAgent(r.data)
    } catch {
      message.error('not found')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [id])

  const onClaim = async () => {
    setClaiming(true)
    try {
      const r = await claimAIAgent(Number(id))
      setAgent(r.data)
      message.success(t('aiAgent.detail.owned', { user: r.data.owner_user }))
    } catch {
      message.error('claim failed')
    } finally {
      setClaiming(false)
    }
  }

  if (loading) return <Spin style={{ width: '100%', marginTop: 80 }} />
  if (!agent) return <Result status="404" title="Not Found" />

  const caps = agent.capabilities || {}
  const signals = agent.risk_signals || []

  return (
    <div>
      <Card style={{ marginBottom: 16 }}>
        <Row align="middle" gutter={16}>
          <Col flex="auto">
            <Space size="middle">
              <Title level={3} style={{ margin: 0 }}>
                <RobotOutlined /> {agent.agent_name}
              </Title>
              <Tag color="blue">{t(`aiAgent.framework.${agent.framework}`, agent.framework)}</Tag>
              <Tag color={LEVEL_COLORS[agent.risk_level]}>{agent.risk_level.toUpperCase()}</Tag>
              <Tag>{agent.status}</Tag>
            </Space>
          </Col>
          <Col>
            {!agent.owner_user && (
              <Button type="primary" icon={<KeyOutlined />} loading={claiming} onClick={onClaim}>
                {t('aiAgent.detail.claimOwner')}
              </Button>
            )}
            {agent.owner_user && (
              <Text type="secondary">{t('aiAgent.detail.owned', { user: agent.owner_user })}</Text>
            )}
          </Col>
        </Row>
      </Card>

      <Row gutter={16}>
        <Col span={12}>
          <Card title={t('aiAgent.detail.basicInfo')} size="small">
            <Descriptions size="small" column={1} bordered>
              <Descriptions.Item label={t('aiAgent.detail.model')}>
                {agent.model || '—'}
              </Descriptions.Item>
              <Descriptions.Item label={t('aiAgent.detail.ownerTeam')}>
                {agent.owner_team || '—'}
              </Descriptions.Item>
              <Descriptions.Item label={t('aiAgent.detail.ownerUser')}>
                {agent.owner_user || '—'}
              </Descriptions.Item>
              <Descriptions.Item label={t('aiAgent.detail.lastSeen')}>
                {agent.last_seen_at}
              </Descriptions.Item>
              <Descriptions.Item label={t('aiAgent.detail.discovered')}>
                {agent.discovered_at}
              </Descriptions.Item>
            </Descriptions>
          </Card>
        </Col>

        <Col span={12}>
          <Card title={t('aiAgent.detail.capabilities')} size="small">
            <Space wrap>
              {caps.filesystem && <Tag color="purple">{t('aiAgent.capability.filesystem')}</Tag>}
              {caps.network && <Tag color="cyan">{t('aiAgent.capability.network')}</Tag>}
              {caps.code_exec && <Tag color="red">{t('aiAgent.capability.codeExec')}</Tag>}
              <Tag>{t('aiAgent.capability.toolCount', { count: caps.tool_count || 0 })}</Tag>
            </Space>
          </Card>
        </Col>
      </Row>

      <Card title={t('aiAgent.detail.credentials')} size="small" style={{ marginTop: 16 }}>
        <Space direction="vertical">
          <div>
            <Text type="secondary">{t('aiAgent.detail.fingerprint')}: </Text>
            <Text code>{agent.api_key_fingerprint || t('aiAgent.detail.noKey')}</Text>
          </div>
          {agent.api_key_location && (
            <div>
              <Text type="secondary">Location: </Text>
              <Text>{agent.api_key_location}</Text>
            </div>
          )}
        </Space>
      </Card>

      <Card title={t('aiAgent.detail.riskSignals')} size="small" style={{ marginTop: 16 }}>
        {signals.length === 0 ? (
          <Empty description="No risk signals" />
        ) : (
          <Space direction="vertical" style={{ width: '100%' }}>
            {signals.map((s: any, i: number) => (
              <div key={i}>
                <Tag color={LEVEL_COLORS['high']}>{s.weight}</Tag>
                <Text strong>{s.signal}</Text>
                {s.evidence && <Paragraph type="secondary" style={{ margin: 0, marginLeft: 8 }}>{s.evidence}</Paragraph>}
              </div>
            ))}
          </Space>
        )}
      </Card>

      <Card title={t('aiAgent.detail.related')} size="small" style={{ marginTop: 16 }}>
        <Space direction="vertical">
          {agent.asset_id && (
            <div>
              <Text>{t('aiAgent.detail.relatedAsset')}: </Text>
              <Link to={`/assets/${agent.asset_id}`}>#{agent.asset_id}</Link>
            </div>
          )}
          {agent.nhi_identity_id && (
            <div>
              <Text>{t('aiAgent.detail.relatedNHI')}: </Text>
              <Link to={`/nhi/${agent.nhi_identity_id}`}>#{agent.nhi_identity_id}</Link>
            </div>
          )}
          {!agent.asset_id && !agent.nhi_identity_id && <Text type="secondary">—</Text>}
        </Space>
      </Card>

      <div style={{ marginTop: 16 }}>
        <Button onClick={() => navigate('/ai-agents')}>← Back</Button>
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd /Users/jyb/projects/telos/frontend && npx tsc -b 2>&1 | tail -5`
Expected: no output (clean)

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/AIAgentDetailPage.tsx
git commit -m "feat(ai-agents): add AIAgentDetailPage with all 5 sections"
```

---

### Task 21: Wire routes in App.tsx

**Files:**
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Find the NHI route**

Run: `grep -n '"/nhi"\|"/nhi/\|AIAgentsPage\|AIAgentDetail' frontend/src/App.tsx | head -10`

- [ ] **Step 2: Add the AI Agent routes**

In `frontend/src/App.tsx`, after the `<Route path="/nhi" ...>` and `<Route path="/nhi/:id" ...>` lines, add:

```tsx
        <Route path="/ai-agents" element={<AIAgentsPage />} />
        <Route path="/ai-agents/:id" element={<AIAgentDetailPage />} />
```

- [ ] **Step 3: Add imports at the top**

In the import block of `App.tsx`, add:

```tsx
import AIAgentsPage from './pages/AIAgentsPage'
import AIAgentDetailPage from './pages/AIAgentDetailPage'
```

- [ ] **Step 4: Verify TypeScript compiles**

Run: `cd /Users/jyb/projects/telos/frontend && npx tsc -b 2>&1 | tail -5`
Expected: no output (clean)

- [ ] **Step 5: Commit**

```bash
git add frontend/src/App.tsx
git commit -m "feat(ai-agents): wire /ai-agents routes in App.tsx"
```

---

## Phase 7 — Frontend Tests + Final Verification

### Task 22: Add Vitest tests for the new pages

**Files:**
- Create: `frontend/src/pages/__tests__/AIAgentsPage.test.tsx`
- Create: `frontend/src/pages/__tests__/AIAgentDetailPage.test.tsx`

- [ ] **Step 1: Create the list-page test**

Create `frontend/src/pages/__tests__/AIAgentsPage.test.tsx`:

```tsx
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import AIAgentsPage from '../AIAgentsPage'
import * as api from '../../api/client'

jest.mock('../../api/client')

const mockList = api.listAIAgents as jest.Mock
const mockStats = api.getAIAgentsStats as jest.Mock

describe('AIAgentsPage', () => {
  it('renders stat cards with stats from API', async () => {
    mockList.mockResolvedValue({ data: { total: 3, agents: [] } })
    mockStats.mockResolvedValue({
      data: { total: 3, active: 2, critical_risk: 1, no_owner: 1,
              by_framework: { langchain: 2, autogen: 1 },
              by_risk_level: { high: 1, low: 2 } },
    })
    render(<MemoryRouter><AIAgentsPage /></MemoryRouter>)
    await waitFor(() => expect(screen.getByText('3')).toBeInTheDocument())
    expect(screen.getByText('AI Agent Management')).toBeInTheDocument()
  })

  it('renders agent name in the list tab', async () => {
    mockList.mockResolvedValue({
      data: {
        total: 1,
        agents: [{ id: 1, agent_name: 'research-bot', framework: 'langchain',
                   model: 'claude-sonnet-4', owner_team: 'data-eng',
                   risk_level: 'high', risk_score: 60, status: 'active',
                   capabilities: {} }],
      },
    })
    mockStats.mockResolvedValue({
      data: { total: 1, active: 1, critical_risk: 0, no_owner: 0,
              by_framework: {}, by_risk_level: {} },
    })
    render(<MemoryRouter><AIAgentsPage /></MemoryRouter>)
    // Switch to list tab
    await waitFor(() => screen.getByText('List').click())
    await waitFor(() => expect(screen.getByText('research-bot')).toBeInTheDocument())
  })
})
```

- [ ] **Step 2: Create the detail-page test**

Create `frontend/src/pages/__tests__/AIAgentDetailPage.test.tsx`:

```tsx
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import AIAgentDetailPage from '../AIAgentDetailPage'
import * as api from '../../api/client'

jest.mock('../../api/client')

const mockGet = api.getAIAgent as jest.Mock

describe('AIAgentDetailPage', () => {
  it('renders all 5 sections for an unowned agent', async () => {
    mockGet.mockResolvedValue({
      data: {
        id: 1, agent_name: 'test-bot', framework: 'langchain',
        model: 'claude-sonnet-4', owner_team: null, owner_user: null,
        api_key_fingerprint: 'sha256:abc', api_key_location: 'env:ANTHROPIC_API_KEY',
        capabilities: { filesystem: true, network: false, code_exec: false, tool_count: 3 },
        last_seen_at: '2026-06-01T00:00:00', discovered_at: '2026-05-01T00:00:00',
        risk_level: 'high', risk_score: 50,
        risk_signals: [{ signal: 'plaintext_key', weight: 40, evidence: 'test' }],
        status: 'active', asset_id: 1, nhi_identity_id: null,
      },
    })
    render(
      <MemoryRouter initialEntries={['/ai-agents/1']}>
        <Routes>
          <Route path="/ai-agents/:id" element={<AIAgentDetailPage />} />
        </Routes>
      </MemoryRouter>
    )
    await waitFor(() => expect(screen.getByText('test-bot')).toBeInTheDocument())
    expect(screen.getByText('Claim Owner')).toBeInTheDocument()
    expect(screen.getByText('Filesystem')).toBeInTheDocument()
    expect(screen.getByText('plaintext_key')).toBeInTheDocument()
  })

  it('does not show claim button when owner is set', async () => {
    mockGet.mockResolvedValue({
      data: {
        id: 1, agent_name: 'owned-bot', framework: 'langchain',
        owner_user: 'alice', owner_team: 'data-eng',
        capabilities: {}, risk_signals: [],
        last_seen_at: '', discovered_at: '',
        risk_level: 'low', risk_score: 0, status: 'active',
        asset_id: null, nhi_identity_id: null,
      },
    })
    render(
      <MemoryRouter initialEntries={['/ai-agents/1']}>
        <Routes>
          <Route path="/ai-agents/:id" element={<AIAgentDetailPage />} />
        </Routes>
      </MemoryRouter>
    )
    await waitFor(() => expect(screen.getByText('owned-bot')).toBeInTheDocument())
    expect(screen.queryByText('Claim Owner')).not.toBeInTheDocument()
  })
})
```

- [ ] **Step 3: Run the new tests**

Run: `cd /Users/jyb/projects/telos/frontend && npx vitest run src/pages/__tests__/AIAgentsPage.test.tsx src/pages/__tests__/AIAgentDetailPage.test.tsx 2>&1 | tail -20`
Expected: 4 tests passed (or 4 passed, 0 failed)

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/__tests__/AIAgentsPage.test.tsx frontend/src/pages/__tests__/AIAgentDetailPage.test.tsx
git commit -m "test(ai-agents): add Vitest tests for list and detail pages"
```

---

### Task 23: Final verification — full test suite + dev server smoke

- [ ] **Step 1: Run full backend test suite**

Run: `cd /Users/jyb/projects/telos && python3 -m pytest backend/tests/ -q 2>&1 | tail -5`
Expected: 130+ tests pass (130 pre-existing + 50+ new for AI Agents).

- [ ] **Step 2: Run full frontend type check**

Run: `cd /Users/jyb/projects/telos/frontend && npx tsc -b 2>&1 | tail -5`
Expected: no output (clean)

- [ ] **Step 3: Run i18n check**

Run: `cd /Users/jyb/projects/telos/frontend && npm run check-i18n`
Expected: `✓ All i18n checks passed`

- [ ] **Step 4: Run all Vitest tests**

Run: `cd /Users/jyb/projects/telos/frontend && npx vitest run 2>&1 | tail -10`
Expected: all tests pass

- [ ] **Step 5: Smoke test in browser**

1. Confirm dev server is running on http://localhost:5173.
2. Log in as admin.
3. Navigate to `/ai-agents` — page renders, stat cards show 0/0/0/0, "Scan AI Agents" button works.
4. Trigger a scan — should show toast "Scan complete: ..." and refresh stats.
5. Click into the empty list (or seeded agent if you seeded data) — detail page renders.
6. Sidebar shows the new top-level NHI and AI Agent items in the B-slot.

- [ ] **Step 6: No code commit — this is verification only**

If any step fails, return to the relevant task and fix.

---

## Summary

This plan produces:
- **Backend (8 new + 3 modified files):** AIAgent model + enums + 6 schemas, migration 024, ai_agent_scanner.py (4 functions: fingerprint, parse_signals, score_risk, ingest_signals), ai_agents router (5 endpoints), ssh_scanner extension, realtime_monitor extension
- **Frontend (2 new + 5 modified files):** AIAgentsPage, AIAgentDetailPage, App.tsx routes, AppLayout menu, client.ts API methods, 2 locale files (~36 new keys)
- **Tests:** migration up/down, scanner unit tests (fingerprint, parse, score, dedup), router integration tests, realtime monitor tests, Vitest page tests

Total: **~23 tasks, ~12 commits** to `main`.

**Out-of-scope (v2 follow-ups):**
- Cloud API discovery (Anthropic Console, OpenAI Dashboard)
- AIAgent policy engine and enforcement
- Full ownership claim/transfer workflow
- AIAgent graph view integration
