# AI Agent as First-Class Identity & NHI Menu Promotion — Design Spec

**Goal:** Recognize AI Agents as a distinct identity class in Telos (not just another NHI type), with a dedicated scanner, dedicated page, and dedicated governance. In the same change, promote the NHI menu from a sub-item of *Identity Operations* to a top-level sidebar item, matching the rising importance of both NHI and AI Agent threats in the LLM era.

**Status:** Approved design — ready for implementation planning.

**Tech stack:** FastAPI, SQLAlchemy 2, Alembic, paramiko (existing), React 18 + TypeScript + Ant Design 5, i18next.

---

## Scope (in / out)

**In scope:**

- New `ai_agent_scanner` service module (peer to `ssh_scanner`, `nhi_analyzer`).
- One additional SSH probe per asset during the existing scan flow, batched into a single shell script with a 5s hard timeout.
- New `ai_agents` SQLAlchemy table + Alembic migration `024_ai_agents.py`.
- New FastAPI router `/api/v1/ai-agents` with list / detail / scan-trigger / stats endpoints.
- New `AIAgentsPage` and `AIAgentDetailPage` React components, peer to `NHIDashboard`.
- New top-level menu items: **NHI 非人类身份** (promoted out of `identity-ops`) and **AI Agent 管理** (new). Placed in the B slot — after `AI 智能分析`, before `资产管理`.
- 8-rule additive risk scoring with level thresholds.
- Realtime monitor detector for newly-discovered and newly-dormant AI Agents.
- API-key fingerprinting (sha256[:16]) — full key never persisted.
- ~30 new i18n keys in both `en-US.json` and `zh-CN.json`.
- Backend (unit + integration) and frontend (Vitest + Playwright) tests.

**Out of scope (later sub-projects):**

- Cloud API discovery channel (Anthropic Console, OpenAI Dashboard, LangSmith). The detection layer is designed to accept a `discovery_source = "api_discovery"` value, but the API integration itself ships in a follow-up sub-project.
- AI Agent policy engine and enforcement (peer to `NHIPolicy`).
- AI Agent activity timeline beyond `last_invocation_at`.
- AI Agent ownership workflow (claim/transfer) beyond a v1 "认领 owner" button that sets `owner_user` to the current user.
- AI Agent graph view (force-graph integration).
- Renaming the `identity-ops` menu to a more general "Identity" umbrella.
- NHI lifecycle/rotation tracking.

---

## 1. Architecture

```
            ┌─────────────────────────────────────────────┐
            │              Frontend (React)               │
            │  /nhi        ← existing NHI page            │
            │  /ai-agents  ← new page (list + detail)     │
            └──────────────────┬──────────────────────────┘
                               │ REST
            ┌──────────────────▼──────────────────────────┐
            │           FastAPI (existing)                │
            │  /api/v1/nhi        (existing)              │
            │  /api/v1/ai-agents  ← new router            │
            └──────────────────┬──────────────────────────┘
                               │
        ┌──────────────────────┼──────────────────────┐
        ▼                      ▼                      ▼
 ssh_scanner (extended)   ai_agent_scanner       sync_all
 + collect_ai_signals()   (new, peer module)     (NHI upsert)
        │                      │                      │
        ▼                      ▼                      ▼
 AccountSnapshot.raw_info  AIAgent table       NHIIdentity table
 (+ ai_agent_signals key)  (new, sibling)      (existing, unchanged)
                               │
                               ▼
                       Alert/Playbook
                       (shared layer)
```

**Key shape decisions:**

- **Siblings, not subtypes.** AI Agent is its own first-class entity, not a value of `NHIIdentity.nhi_type`. The `AIAgent.nhi_identity_id` FK is **one-way optional**: an AI Agent may point at an NHI (when a Unix account exists), but the NHI tables are untouched. A cloud-only LangChain agent has `nhi_identity_id = NULL`.
- **Shared operational layer.** Alerts, playbooks, audit log, and credential-findings plumbing are reused. Risk signals flow through the same `Alert` table; the existing `alert_manager` broadcasts the new alert types without modification.
- **NHI menu promotion is purely a frontend change.** No backend changes are required to lift `/nhi` to a top-level menu item.

---

## 2. Components

**Backend — new files:**

| File | Responsibility |
|---|---|
| `backend/services/ai_agent_scanner.py` | Probe parser, dedupe, risk scoring, AIAgent upsert |
| `backend/routers/ai_agents.py` | REST: list / detail / scan-trigger / stats |
| `backend/alembic/versions/024_ai_agents.py` | New table migration |

**Backend — modified:**

| File | Change |
|---|---|
| `backend/models.py` | Add `AIAgent` SQLAlchemy model |
| `backend/schemas.py` | `AIAgentCreate`, `AIAgentResponse`, `AIAgentDetailResponse`, `AIAgentStatsResponse` |
| `backend/services/ssh_scanner.py` | Call `collect_ai_signals(ssh_client)`; attach result to `AccountSnapshot.raw_info["ai_agent_signals"]` |
| `backend/services/realtime_monitor.py` | Add `_detect_new_ai_agents` and `_detect_dormant_ai_agents` |
| `backend/main.py` | Include `ai_agents` router |

**Frontend — new files:**

| File | Responsibility |
|---|---|
| `frontend/src/pages/AIAgentsPage.tsx` | List + tabs (概览 / 清单 / 告警), peer to `NHIDashboard` |
| `frontend/src/pages/AIAgentDetailPage.tsx` | Detail: framework / model / owner / risk signals / credentials |
| `frontend/src/api/ai-agents.ts` | API client (mirrors `nhi.ts` style) |

**Frontend — modified:**

| File | Change |
|---|---|
| `frontend/src/App.tsx` | Add `/ai-agents` and `/ai-agents/:id` routes |
| `frontend/src/components/AppLayout.tsx` | Remove `nhi` from `identity-ops` SubMenu; add 2 new top-level `Menu.Item`s (NHI + AI Agent) in the B slot |
| `frontend/src/locales/en-US.json`, `frontend/src/locales/zh-CN.json` | `nav.aiAgents`, `aiAgent.*` keys (~30 keys total) |

**Tests — new files:**

| File | Coverage |
|---|---|
| `backend/tests/test_ai_agent_scanner.py` | Probe output → signals → AIAgent records |
| `backend/tests/test_ai_agent_risk.py` | Each rule + threshold boundaries (24/25, 49/50, 74/75) |
| `backend/tests/test_ai_agent_dedup.py` | Same agent on 2 assets = 2 AIAgent rows; same agent re-scanned on same asset = 1 row (update) |
| `backend/tests/test_ai_agent_fingerprint.py` | Same key → same fingerprint, key value never persisted |
| `backend/tests/test_ai_agents_router.py` | API list/detail/scan/stats, filter by framework/risk/owner |
| `backend/tests/test_realtime_monitor_ai.py` | New-agent + dormant detectors |
| `backend/tests/test_migration_024.py` | Up + down with SQLite (peer to `test_migration_023`) |
| `frontend/src/pages/__tests__/AIAgentsPage.test.tsx` | Render, tab switch, scan button |
| `frontend/src/pages/__tests__/AIAgentDetailPage.test.tsx` | All 5 sections render, owner-null shows 认领 button |
| `frontend/src/api/__tests__/ai-agents.test.ts` | Request shape, error mapping |
| `frontend/src/locales/__tests__/i18n-keys.test.ts` | Every `aiAgent.*` key in en-US exists in zh-CN and vice versa |

---

## 3. Data Model

```python
class AIAgent(Base):
    __tablename__ = "ai_agents"

    id                  = Column(Integer, primary_key=True)
    agent_name          = Column(String(128), nullable=False, index=True)
    framework           = Column(String(32))      # langchain|autogen|crewai|claude_code|openai_assistant|custom|unknown
    model               = Column(String(64), nullable=True)
    owner_team          = Column(String(64), nullable=True, index=True)
    owner_user          = Column(String(64), nullable=True)
    api_key_fingerprint = Column(String(16), nullable=True)   # sha256[:16], never the key
    api_key_location    = Column(String(256), nullable=True)
    capabilities        = Column(JSON)            # {filesystem: bool, network: bool, code_exec: bool, tool_count: int}
    last_invocation_at  = Column(DateTime, nullable=True)
    last_seen_at        = Column(DateTime, nullable=False)
    discovered_at       = Column(DateTime, nullable=False)
    discovery_source    = Column(String(16))      # ssh_scan | api_discovery | manual
    asset_id            = Column(Integer, ForeignKey("assets.id"), nullable=True, index=True)
    nhi_identity_id     = Column(Integer, ForeignKey("nhi_identities.id"), nullable=True, index=True)
    risk_level          = Column(String(16))      # low|medium|high|critical
    risk_score          = Column(Integer)
    risk_signals        = Column(JSON)            # list of {signal, weight, evidence}
    status              = Column(String(16))      # active|dormant|deprecated|blocked
    created_at          = Column(DateTime)
    updated_at          = Column(DateTime)
```

**Relationship decisions:**

- `nhi_identity_id` is **one-way optional**. AI Agent → NHI when an underlying Unix account exists. NHI tables are unchanged.
- `api_key_fingerprint` stores only the first 16 chars of the key's sha256, sufficient to detect "same key across multiple agents" without persisting the secret. A unit test asserts no key substring is ever present in any persisted column.
- The dedup key for ingest is `(framework, agent_name, owner_team, asset_id)`. The same logical agent running on three hosts produces **three** `AIAgent` rows in v1, one per asset. Cross-asset aggregation (treating three rows as one logical agent) is a v2 concern and explicitly out of scope for this spec.

**Discovery signals (raw, not normalized into a table) live in `AccountSnapshot.raw_info["ai_agent_signals"]`:**

```json
{
  "ai_agent_signals": {
    "config_files":    [{"path": "/home/alice/.config/anthropic/credentials.json"}],
    "env_vars":        [{"name": "ANTHROPIC_API_KEY", "scope": "user", "fingerprint": "sha256:abc123…"}],
    "processes":       [{"name": "langchain-server", "count": 3}],
    "framework_paths": [{"path": "/opt/myapp/venv/.../langchain", "framework": "langchain"}]
  }
}
```

---

## 4. Frontend

**New top-level sidebar (B-slot placement):**

```
🏠 仪表盘
🛡 AI 智能分析
⚡ NHI 非人类身份       ← promoted from identity-ops submenu
🤖 AI Agent 管理       ← new
☁ 资产管理 ▾
📋 扫描作业 ▾
🛡 安全运营 ▾
👥 身份运营 ▾ (身份融合 · 行为分析 · 生命周期 · 堡垒机集成)
🛡 合规策略 ▾
⚙ 系统 ▾
```

**`/ai-agents` page (peer to `/nhi`):**

- Header: `🤖 AI Agent 管理` + subtitle `发现·分类·风险评估·治理` + `[ 扫描 AI Agent ]` button
- 4 stat cards: `AI Agent 总数` · `活跃 Agent` · `严重风险` · `无主 Agent`
- 3 tabs: `概览` / `清单` / `告警`
  - 概览: 框架分布饼图, 风险等级柱状图, 拥有方分布, Top 10 高危 Agent
  - 清单: table with columns `Agent名 | 框架 | 模型 | 拥有方 | 风险 | 能力 | 状态`
  - 告警: peer to NHI alert page (shared `AlertResponse` schema)

**`/ai-agents/:id` detail page:**

- Header: agent name + framework Tag + risk Badge + `认领 owner` button (visible when `owner_user IS NULL`)
- Section 1 — 基本信息: 框架, 模型, 拥有方/团队, 最后调用, 最后发现
- Section 2 — 能力: chips for filesystem / network / code_exec / tool count
- Section 3 — 凭据: fingerprint only (`sha256:abc123…`), location, **never the key**
- Section 4 — 风险信号: list of `{signal, weight, evidence}`
- Section 5 — 关联: 资产 (if any) + NHI (if any) — link to detail pages

**Routes** (`App.tsx`): `<Route path="/ai-agents" element={<AIAgentsPage />} />` and `<Route path="/ai-agents/:id" element={<AIAgentDetailPage />} />`. No guards beyond existing auth.

**i18n additions** (both locales): `nav.aiAgents`, `aiAgent.title`, `aiAgent.subtitle`, `aiAgent.scan`, `aiAgent.framework.*`, `aiAgent.capability.*`, `aiAgent.detail.*`, etc. (~30 keys)

---

## 5. Scan & Ingest Flow

**One SSH round-trip per asset.** The existing `ssh_scanner` already collects users / sudo / credentials. We add **one** additional batched shell command that runs in parallel with existing collection (5s hard timeout). Output is base64'd and parsed server-side.

```bash
# inline heredoc — runs on the remote host, no script deployment required
{
  echo "===CF==="; find /home /opt /root /etc -maxdepth 5 -name "*.json" 2>/dev/null \
    | xargs grep -l "anthropic\|openai\|claude\|gemini" 2>/dev/null | head -20
  echo "===ENV==="; env | grep -iE "^(ANTHROPIC|OPENAI|CLAUDE|LANGCHAIN|COHERE|GEMINI)_" | head -20
  echo "===PS==="; ps -ef | grep -iE "claude|langchain|autogen|crewai|gpt-|agent" | grep -v grep | head -20
  echo "===DIRS==="; find / -maxdepth 6 -type d \
    \( -name "langchain*" -o -name "autogen*" -o -name "crewai*" -o -name "anthropic*" -o -name "llamaindex*" \) 2>/dev/null | head -20
  echo "===PKG==="; find /home /opt /root -maxdepth 5 -name "package.json" 2>/dev/null \
    | xargs grep -l "@anthropic-ai\|langchain\|openai" 2>/dev/null | head -20
} | base64 -w0
```

**Server-side pipeline:**

```
ssh_scanner.collect(asset_id)
  ├── (existing) users / sudo / credentials  → AccountSnapshot
  └── collect_ai_signals()                   → raw_info["ai_agent_signals"]  (JSON)
                                                       │
                                                       ▼
                                   ai_agent_scanner.ingest(raw_info, asset_id)
                                                       │
                              ┌────────────────────────┼────────────────────────┐
                              ▼                        ▼                        ▼
                        dedupe by               risk score               upsert AIAgent
                        (framework,             (rules, §5)              (or update if exists)
                         agent_name,
                         owner_team)
                                                       │
                                                       ▼
                                       if risk >= high AND new →
                                         emit Alert via existing alert_manager
                                         (playbooks matched via existing
                                          realtime_monitor)
```

**Risk rules (8, additive):**

| Signal | Weight | Level contribution |
|---|---|---|
| API key in plaintext config file | 40 | critical |
| No owner_user AND no owner_team | 30 | high |
| `code_exec` capability | 25 | high |
| `network` capability | 15 | medium |
| `filesystem` capability | 10 | medium |
| Framework = `autogen` / `crewai` (multi-agent) | 15 | medium |
| `last_invocation_at` > 30 days ago | 15 | medium |
| Same `api_key_fingerprint` appears on > 1 asset | 20 | high |

**Score thresholds:** 0–24 low, 25–49 medium, 50–74 high, 75+ critical.

**Lifecycle:** When the scanner no longer finds an agent across two consecutive scans, its `status` flips to `dormant`. If dormant > 90 days, an alert fires (existing playbook matches).

---

## 6. Error Handling

| Failure | Behavior |
|---|---|
| SSH auth fail / host unreachable | `collect_ai_signals()` returns `None`; rest of scan continues; NHI data unaffected |
| Probe times out (>5s) | Kill channel, ingest partial output (whatever arrived in first 5s) |
| `base64 -d` / parse error | Log at WARN, set `ai_agent_signals = None`; do not fail the snapshot |
| Permission denied on `/home/*` | Expected — `find` already silences stderr |
| Dedup unique-constraint race | Catch `IntegrityError`, refetch by `(framework, name, team)`, update instead |
| Go microservice unavailable (v2 API channel only) | Fall back to direct API calls from Python, same fallback pattern as `go_analysis_engine.py` |
| API key discovered in env var | Fingerprint + location only — **never** persist the key value (covered by `test_ai_agent_fingerprint.py`) |

---

## 7. Testing Plan

**Backend** (pytest):

- `test_ai_agent_scanner.py` — fixture-based probe output → signals → AIAgent records
- `test_ai_agent_risk.py` — each rule independently + threshold boundaries (24/25, 49/50, 74/75)
- `test_ai_agent_dedup.py` — same agent on 2 assets = 2 AIAgent rows; same agent re-scanned on same asset = 1 row (update)
- `test_ai_agent_fingerprint.py` — same key → same fingerprint, asserts full key never appears in any persisted column
- `test_ai_agents_router.py` — API: list, detail, scan trigger, stats, filters by framework / risk / owner
- `test_realtime_monitor_ai.py` — new-agent detector, dormant detector
- `test_migration_024.py` — up + down with SQLite (peer to `test_migration_023`)

**Frontend** (Vitest):

- `pages/__tests__/AIAgentsPage.test.tsx` — render, tab switch, scan button fires
- `pages/__tests__/AIAgentDetailPage.test.tsx` — all 5 sections render, owner-null shows 认领 button
- `api/__tests__/ai-agents.test.ts` — request shape, error mapping
- `locales/__tests__/i18n-keys.test.ts` — every `aiAgent.*` key in en-US exists in zh-CN and vice versa

**E2E** (Playwright):

- Login → navigate to `/ai-agents` → see empty state → trigger scan → see agents appear → click into detail → see all 5 sections

**Coverage target:** 85%+ for `ai_agent_scanner.py` and `ai_agents_router.py` (the new code paths).

---

## 8. Migration Plan

Alembic migration `024_ai_agents.py`:

```python
def upgrade():
    op.create_table(
        "ai_agents",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("agent_name", sa.String(128), nullable=False, index=True),
        sa.Column("framework", sa.String(32)),
        sa.Column("model", sa.String(64), nullable=True),
        sa.Column("owner_team", sa.String(64), nullable=True, index=True),
        sa.Column("owner_user", sa.String(64), nullable=True),
        sa.Column("api_key_fingerprint", sa.String(16), nullable=True),
        sa.Column("api_key_location", sa.String(256), nullable=True),
        sa.Column("capabilities", sa.JSON),
        sa.Column("last_invocation_at", sa.DateTime, nullable=True),
        sa.Column("last_seen_at", sa.DateTime, nullable=False),
        sa.Column("discovered_at", sa.DateTime, nullable=False),
        sa.Column("discovery_source", sa.String(16)),
        sa.Column("asset_id", sa.Integer, sa.ForeignKey("assets.id"), nullable=True),
        sa.Column("nhi_identity_id", sa.Integer, sa.ForeignKey("nhi_identities.id"), nullable=True),
        sa.Column("risk_level", sa.String(16)),
        sa.Column("risk_score", sa.Integer),
        sa.Column("risk_signals", sa.JSON),
        sa.Column("status", sa.String(16)),
        sa.Column("created_at", sa.DateTime),
        sa.Column("updated_at", sa.DateTime),
    )
    op.create_index("ix_ai_agents_dedup", "ai_agents",
                    ["framework", "agent_name", "owner_team", "asset_id"],
                    unique=True)
    op.create_index("ix_ai_agents_nhi", "ai_agents", ["nhi_identity_id"])
    op.create_index("ix_ai_agents_asset", "ai_agents", ["asset_id"])
    op.create_index("ix_ai_agents_fingerprint", "ai_agents", ["api_key_fingerprint"])

def downgrade():
    op.drop_index("ix_ai_agents_fingerprint", table_name="ai_agents")
    op.drop_index("ix_ai_agents_asset", table_name="ai_agents")
    op.drop_index("ix_ai_agents_nhi", table_name="ai_agents")
    op.drop_index("ix_ai_agents_dedup", table_name="ai_agents")
    op.drop_table("ai_agents")
```

SQLite-specific branch (peer to migration 023) for the index-on-column pattern: pre-drop the index before dropping any column on SQLite if needed in downgrade.

---

## 9. Out-of-scope hooks (for the v2 sub-project)

The following are **designed for, but not built in v1**:

- `discovery_source = "api_discovery"` — already a valid enum value; the API integration (Anthropic Console, OpenAI Dashboard, LangSmith) lands in a follow-up sub-project.
- AIAgent graph view — `nhi_identity_id` and `asset_id` FKs are in place; the force-graph component can join these without schema changes.
- AI Agent policy engine — `risk_signals` JSON is shaped so a future `AIAgentPolicy` can match on individual signals.
- Ownership claim workflow — the v1 button just sets `owner_user` to the current authenticated user; full claim/transfer with approval routing ships later.

---

## 10. Out of scope (restated)

Reaffirming what's deferred to keep v1 focused:

- Cloud API discovery channel (Anthropic Console, OpenAI Dashboard, LangSmith)
- AI Agent policy engine and enforcement
- AI Agent activity timeline beyond `last_invocation_at`
- AI Agent ownership claim/transfer workflow
- AI Agent graph view (force-graph integration)
- Renaming the `identity-ops` menu to a more general "Identity" umbrella
- NHI lifecycle/rotation tracking
