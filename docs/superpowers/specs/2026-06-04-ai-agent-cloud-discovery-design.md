# AI Agent — Cloud API Discovery Channel — Design Spec

**Goal:** Add a second discovery channel for AI Agents: instead of (or in addition to) SSH-based host scanning, allow an admin to register a provider admin key (Anthropic Console or OpenAI Dashboard) and have Telos periodically inventory the API keys, orgs, and projects that the key can see. Discovered agents are written into the existing `ai_agents` table with `framework = 'cloud_<provider>'` and `discovery_source = 'api_discovery'`, reusing all of v1's listing, risk, alert, and audit plumbing.

**Status:** Approved design — ready for implementation planning.

**Tech stack:** FastAPI, SQLAlchemy 2, Alembic, httpx (new), APScheduler (existing, hooks in `scheduler_service`), AES-256-GCM via `ACCOUNTSCAN_MASTER_KEY` (existing), React 18 + TypeScript + Ant Design 5, i18next.

---

## Scope (in / out)

**In scope (v2):**

- Two providers: **Anthropic Console** and **OpenAI Dashboard**. Inventory-only — list orgs, list projects (Anthropic) or projects (OpenAI), and for each project list its API keys (with fingerprint only).
- New `cloud_connections` table holding the encrypted admin key, per-connection metadata, and last-sync state.
- New `cloud_connection_audit_log` table recording every change to a connection (create, update, rotate, delete, sync-trigger).
- Per-provider discovery modules in `backend/services/cloud_discovery/` (peer to `ssh_scanner`).
- New FastAPI router `/api/v1/ai-agents/connections` (CRUD + sync-now).
- New React page `/ai-agents/connections` for managing connections (list, add, edit-name-only, delete, sync-now).
- 6-hour scheduled sync (background) plus a manual "Sync Now" button per connection.
- 2 risk rules added (reused from v1 scoring shape, additive): connection is the only AI Agent source, admin key has high blast radius, dormant cloud agent.
- ~10 new i18n keys in both locales.
- Backend (unit + integration + migration) and frontend (Vitest) tests.

**Out of scope (deferred to later sub-projects):**

- Other cloud providers (Google Vertex, Azure OpenAI, AWS Bedrock, LangSmith, Hugging Face).
- Per-key usage / cost data, rate-limit data, last-invocation telemetry from the provider.
- Cross-provider key reuse detection (would require normalizing the v1 fingerprint scheme).
- Webhook-based push discovery (provider → Telos). v2 is poll-only.
- Connection sharing / RBAC (only the creating user can see / edit; admins see all).
- Automatic key rotation.
- Re-encrypting keys on master-key rotation (key rotation support is a platform concern; we just re-encrypt on read if we ever change the master key).

---

## 1. Architecture

```
            ┌─────────────────────────────────────────────┐
            │              Frontend (React)               │
            │  /ai-agents             (existing)          │
            │  /ai-agents/connections (new sub-page)      │
            └──────────────────┬──────────────────────────┘
                               │ REST
            ┌──────────────────▼──────────────────────────┐
            │           FastAPI (existing)                │
            │  /api/v1/ai-agents              (existing)  │
            │  /api/v1/ai-agents/connections  ← new       │
            └──────────────────┬──────────────────────────┘
                               │
            ┌──────────────────┼──────────────────────────┐
            ▼                  ▼                        ▼
      cloud_discovery/   ai_agent_scanner         scheduler_service
      ┌──────────┐        (v1, unchanged)         (existing)
      │ base.py  │
      │ anthropic│ ──┐
      │ openai   │   │  list orgs / projects / keys
      └──────────┘   │  (httpx, per-provider)
                     ▼
                CloudConnection row
                (encrypted admin key,
                 last_sync state)
                     │
                     ▼
                ai_agents table
                (framework = 'cloud_<provider>',
                 discovery_source = 'api_discovery',
                 asset_id = NULL,
                 agent_name = '{conn.name} / {project} / {key-fp[:8]}')

                     │
        ┌────────────┼────────────┐
        ▼                         ▼
   Alert (existing,         cloud_connection_audit_log
   reused — high-risk      (new — per-connection
   agent discovered)         change history)
```

**Key shape decisions:**

- **Reuse the v1 AIAgent table.** No new agent-shaped table — cloud-discovered agents live alongside SSH-discovered ones, distinguished only by `framework` and `discovery_source`. This means the v1 list page, detail page, and stats all show cloud agents with zero frontend changes.
- **Asset is NULL for cloud agents.** There is no host. The v1 dedup key `(framework, agent_name, owner_team, asset_id)` does **not** collapse on `asset_id IS NULL` — standard SQL treats NULLs as distinct in unique constraints, so re-syncs would duplicate rows. `ingest_cloud_agents` therefore does an explicit "find existing by `(framework, agent_name) WHERE asset_id IS NULL`" lookup before the upsert. (A future DB-level fix — partial unique index — is out of scope for v2.)
- **Synthetic `agent_name`** — `"{connection.name} / {project_label} / {key_fingerprint[:8]}"`. Stable per sync, so re-syncs update, not insert. The full 16-char fingerprint is stored in the existing `api_key_fingerprint` column.
- **Per-provider modules** rather than a single dispatcher. Each provider is a small class implementing a `discover(connection) -> list[RawAgent]` interface, peer to the way `ssh_scanner` is one module per protocol family.
- **Encryption is opaque to the rest of the system.** `CloudConnection.encrypted_api_key` is a base64 string holding the AES-256-GCM ciphertext (nonce + ct + tag), encrypted with the same `ACCOUNTSCAN_MASTER_KEY` used elsewhere. Only the `cloud_discovery` modules ever decrypt.

---

## 2. Components

**Backend — new files:**

| File | Responsibility |
|---|---|
| `backend/models/cloud_connection.py` | `CloudConnection` and `CloudConnectionAuditLog` SQLAlchemy models |
| `backend/schemas/cloud_connections.py` | Pydantic schemas: `CloudConnectionCreate`, `CloudConnectionUpdate`, `CloudConnectionResponse`, `CloudConnectionTestResult`, `CloudConnectionAuditEntry` |
| `backend/services/cloud_discovery/__init__.py` | Module exports + shared `RawAgent` dataclass + dispatcher `discover(connection)` |
| `backend/services/cloud_discovery/base.py` | `CloudDiscoveryBase` abstract base — common retry / timeout / fingerprint helpers |
| `backend/services/cloud_discovery/anthropic.py` | `AnthropicDiscovery` — calls Anthropic Admin API |
| `backend/services/cloud_discovery/openai.py` | `OpenAIDiscovery` — calls OpenAI Admin API |
| `backend/services/crypto.py` | Tiny wrapper that re-exports the existing `backend/encryption.py` `encrypt` / `decrypt` plus a `fingerprint(plaintext) -> str` helper; the cloud-discovery code imports from here so test coverage has a single seam |
| `backend/routers/ai_agent_connections.py` | REST: list / create / update / delete / sync-now / audit-log |
| `backend/alembic/versions/025_cloud_connections.py` | Two new tables + indexes |

**Backend — modified:**

| File | Change |
|---|---|
| `backend/models/__init__.py` | Re-export `CloudConnection`, `CloudConnectionAuditLog` |
| `backend/models/_enums.py` | Add `CloudProvider = Literal["anthropic", "openai"]` and `CLOUD_FRAMEWORK = {"anthropic": "cloud_anthropic", "openai": "cloud_openai"}` (a plain dict) |
| `backend/schemas/ai_agents.py` | Confirm `AIAgentDiscoverySourceLiteral` already includes `"api_discovery"` (it does — v1) |
| `backend/services/ai_agent_scanner.py` | Add `ingest_cloud_agents(connection, raw_agents)` that writes/updates `AIAgent` rows from the new channel; reused upsert path |
| `backend/services/scheduler_service.py` | Add job `sync_all_cloud_connections`, every 6h; same pattern as existing scheduled tasks |
| `backend/main.py` | Include `ai_agent_connections` router |

**Frontend — new files:**

| File | Responsibility |
|---|---|
| `frontend/src/pages/CloudConnectionsPage.tsx` | List of connections + add/edit/delete/sync-now, mounted at `/ai-agents/connections` |
| `frontend/src/api/ai-agent-connections.ts` | API client (mirrors `ai-agents.ts` style) |
| `frontend/src/pages/__tests__/CloudConnectionsPage.test.tsx` | Render, add dialog validation, sync-now disabled states |
| `frontend/src/api/__tests__/ai-agent-connections.test.ts` | Request shape, error mapping |

**Frontend — modified:**

| File | Change |
|---|---|
| `frontend/src/pages/AIAgentsPage.tsx` | Add a secondary tab bar (or a top "Connections" link) routing to `/ai-agents/connections` |
| `frontend/src/App.tsx` | Add `/ai-agents/connections` route |
| `frontend/src/locales/en-US.json`, `frontend/src/locales/zh-CN.json` | `aiAgent.connections.*` keys (~10 keys: title, add, edit, delete, syncNow, lastSync, status.*, provider.*, auditLog) |

**Tests — new files:**

| File | Coverage |
|---|---|
| `backend/tests/test_crypto.py` | Round-trip, tampered ciphertext, key-length validation |
| `backend/tests/test_cloud_discovery_anthropic.py` | Mocked HTTP: happy path, 401, 429 retry, partial response |
| `backend/tests/test_cloud_discovery_openai.py` | Mocked HTTP: happy path, 401, 429 retry, partial response |
| `backend/tests/test_cloud_discovery_base.py` | Retry-with-backoff, timeout, fingerprint helper |
| `backend/tests/test_ai_agent_cloud_ingest.py` | Raw agents → AIAgent rows; dedup via synthetic name; risk rules fire |
| `backend/tests/test_ai_agent_connections_router.py` | List, create (encrypted), update (name only — key write-only), delete, sync-now, audit log endpoint |
| `backend/tests/test_ai_agent_connections_audit.py` | Every state-changing endpoint writes one audit row with `actor_user_id`, `action`, `before`, `after` |
| `backend/tests/test_migration_025.py` | Up + down with SQLite (peer to `test_migration_024`) |
| `backend/tests/test_scheduler_cloud_sync.py` | Scheduler job calls `discover` on each connection and writes results; failures recorded on the connection row |

---

## 3. Data Flow

### 3.1 Manual "Sync Now"

```
User clicks "Sync Now" on /ai-agents/connections
  │
  ▼
POST /api/v1/ai-agents/connections/{id}/sync
  │
  ├─ set connection.last_sync_status = 'running', last_sync_started_at = now
  ├─ audit: action='sync_started', actor=<user>
  │
  ▼
cloud_discovery.discover(connection)
  │  (decrypts key in-memory, dispatches to Anthropic or OpenAI module)
  │
  ▼
List[RawAgent]    ──►  ai_agent_scanner.ingest_cloud_agents(connection, raw_agents)
                              │
                              ▼
                       upsert into ai_agents:
                         framework = 'cloud_<provider>'
                         discovery_source = 'api_discovery'
                         asset_id = NULL
                         agent_name = f"{conn.name} / {project} / {fp[:8]}"
                         api_key_fingerprint = full 16-char fp
                              │
                              ▼
                       (existing v1 path) → risk scoring → alerts (if high/critical)
                              │
                              ▼
  set connection.last_sync_status = 'success' | 'partial' | 'failed',
       last_sync_at = now,
       last_sync_error = <truncated message or null>
  audit: action='sync_finished', actor=<user>, status=...
```

### 3.2 Scheduled sync (every 6h)

The scheduler picks up `sync_all_cloud_connections` every 6h. Same logic as manual sync, except:

- One connection failing does not block the others (each is its own try/except).
- `last_sync_status` is per-connection, never global.
- A failed connection does NOT generate an alert in v2 — it just shows the error on the connection row. (Alerting on failed syncs is a v3 concern; v2 has a single notification point: high-risk agent discovered.)

### 3.3 SSH scan is unchanged

The v1 `ssh_scanner.collect_ai_signals()` path is untouched. A host that has both an SSH-discovered LangChain agent AND is the host of an admin's machine that owns the org's Anthropic key will see **two** `AIAgent` rows — one with `framework='langchain'`, `discovery_source='ssh_scan'`, `asset_id=<host>`; another with `framework='cloud_anthropic'`, `discovery_source='api_discovery'`, `asset_id=NULL`. They are distinct entities (one is a code artifact on a host, the other is a provider-side identity) and the dedup key naturally separates them.

### 3.4 Listing and filtering are unchanged

`GET /api/v1/ai-agents?framework=cloud_anthropic` returns the cloud-discovered agents. `?discovery_source=api_discovery` works the same. The v1 frontend pages render them with no change; the existing `framework` chip styling and `discovery_source` filters already handle the new values.

---

## 4. Error Handling & Audit

| Failure | Behavior |
|---|---|
| Provider returns 401 (key revoked / wrong) | `last_sync_status='failed'`, `last_sync_error='auth_failed'`. Connection stays active — the user can replace the key. No partial ingest (we trust nothing from an unauthenticated response). |
| Provider returns 429 | Retry with exponential backoff (3 attempts, 1s/2s/4s). If still 429, `last_sync_status='failed'`, `last_sync_error='rate_limited'`. |
| Provider returns 5xx (transient) | Same retry path as 429. |
| Network timeout (>10s per request) | Retry once. On second timeout, mark `partial` if we got ≥1 successful sub-call, else `failed`. |
| Partial response (some sub-calls succeeded) | `last_sync_status='partial'`, `last_sync_error='<list of failed sub-calls>'`. Ingest whatever we got. |
| Encryption edge case: `ACCOUNTSCAN_MASTER_KEY` not set on app startup | App refuses to start (existing pattern — fail fast). Existing `ACCOUNTSCAN_MASTER_KEY` validation already covers this; we just reuse it. |
| Decryption on read fails (tampered ciphertext) | Return 500 with a generic message; never log the ciphertext. Audit row records the attempt. |
| Connection soft-delete: user deletes a connection | Existing cloud agents are **kept** in the `ai_agents` table with `framework='cloud_<provider>'` but a new column `connection_id` is set NULL. The agents remain visible in lists (history) but the connection row no longer exists. The `/api/v1/ai-agents` endpoint gets a new filter `?include_orphaned=true` to toggle this (default `false` to match v1 behavior of "what's currently connected"). |
| Dedup invariant violation | Catch `IntegrityError`, refetch by `(framework, agent_name)`, update instead (same as v1). |
| API key disclosure risk | The key is never logged. `test_crypto.py` asserts the encrypted value never appears in any log line, and `test_ai_agent_connections_audit.py` asserts the audit `before`/`after` payloads never contain plaintext key material. |
| Manual "Sync Now" on a connection that is already `running` | Return 409 with `code='sync_in_progress'`. Frontend disables the button while in-flight. |
| `editing` only allows the name; replacing the key is `rotate` | `PUT /api/v1/ai-agents/connections/{id}` rejects `api_key` in the body. To replace the key, the user calls `POST /api/v1/ai-agents/connections/{id}/rotate` with the new key. This keeps a clean audit trail — name changes don't require a new audit "key_rotated" entry. |

### Audit log (`cloud_connection_audit_log`)

```python
class CloudConnectionAuditLog(Base):
    __tablename__ = "cloud_connection_audit_log"

    id              = Column(Integer, primary_key=True)
    connection_id   = Column(Integer, ForeignKey("cloud_connections.id", ondelete="SET NULL"),
                             nullable=True, index=True)
    actor_user_id   = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    action          = Column(String(32), nullable=False)   # created|renamed|rotated|deleted|sync_started|sync_finished
    status          = Column(String(16), nullable=True)    # success|partial|failed|auth_failed|rate_limited (only on sync_finished)
    before          = Column(JSON, nullable=True)          # prior state — name only, never the key
    after           = Column(JSON, nullable=True)          # new state — name only, never the key
    note            = Column(String(256), nullable=True)   # free-text, e.g. truncated error
    created_at      = Column(DateTime, nullable=False, default=datetime.utcnow)
```

- One row per state-changing endpoint call. `created` and `deleted` get full `before`/`after`. `renamed` and `rotated` get just the changed fields. `sync_started` / `sync_finished` get `note` (truncated error) on failures.
- A new endpoint `GET /api/v1/ai-agents/connections/{id}/audit` returns rows newest-first, paginated. Visible in the connection detail drawer.
- The key (plaintext or encrypted) NEVER appears in any `before`, `after`, or `note` column. A unit test asserts this.

---

## 5. Testing Plan

**Backend** (pytest):

- `test_crypto.py` — round-trip a known string, assert decrypt failure on tampered ciphertext, assert reject on missing/short `ACCOUNTSCAN_MASTER_KEY`.
- `test_cloud_discovery_base.py` — retry-with-backoff, timeout, fingerprint helper (`sha256[:16]`), `RawAgent` dataclass.
- `test_cloud_discovery_anthropic.py` — mocked `httpx` returning canned Anthropic Admin responses (orgs, projects, keys). Assert one `RawAgent` per (project, key) pair, fingerprint stable across re-runs, 401 + 429 + 5xx paths.
- `test_cloud_discovery_openai.py` — same shape as Anthropic, with OpenAI's response schema.
- `test_ai_agent_cloud_ingest.py` — given a `CloudConnection` and a list of `RawAgent`, assert the right `AIAgent` rows are written, dedup works (re-run → update, not insert, via the explicit `(framework, agent_name) WHERE asset_id IS NULL` lookup — not relying on DB unique-constraint behavior), `asset_id=NULL`, `framework='cloud_<provider>'`, `discovery_source='api_discovery'`.
- `test_ai_agent_connections_router.py` — list, create (encrypted on disk), update (name only, key rejected), rotate, delete (soft), sync-now (success / auth_failed / rate_limited / partial).
- `test_ai_agent_connections_audit.py` — every state-changing endpoint writes exactly one audit row with the correct `action`, `actor_user_id`, and never contains plaintext key material.
- `test_migration_025.py` — up + down with SQLite (peer to `test_migration_024`).
- `test_scheduler_cloud_sync.py` — scheduler calls `discover` on each connection; one connection failing does not block the others; `last_sync_status` and `last_sync_error` set correctly per connection.

**Frontend** (Vitest):

- `pages/__tests__/CloudConnectionsPage.test.tsx` — render with seeded connections; add dialog requires name + provider + key; sync-now button disabled while in-flight; delete shows confirm dialog.
- `api/__tests__/ai-agent-connections.test.ts` — request shape, error mapping, key never sent in `GET` (only in `POST` / `PUT /rotate`).

**E2E** (Playwright):

- Login → `/ai-agents/connections` → add a connection (with a fake key) → sync → see `last_sync_status` render → click into audit log → see the `created` + `sync_finished` rows.

**Coverage target:** 85%+ for `cloud_discovery/` and `ai_agent_connections_router.py`.

---

## 6. Migration Plan

Alembic migration `025_cloud_connections.py`:

```python
def upgrade():
    op.create_table(
        "cloud_connections",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("provider", sa.String(16), nullable=False),                 # anthropic|openai
        sa.Column("encrypted_api_key", sa.Text, nullable=False),              # base64 nonce+ct+tag
        sa.Column("api_key_fingerprint", sa.String(16), nullable=False),      # sha256[:16] of the plaintext
        sa.Column("last_sync_at", sa.DateTime, nullable=True),
        sa.Column("last_sync_started_at", sa.DateTime, nullable=True),
        sa.Column("last_sync_status", sa.String(16), nullable=True),          # success|partial|failed|running
        sa.Column("last_sync_error", sa.String(256), nullable=True),
        sa.Column("created_by_user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
        sa.UniqueConstraint("name", name="uq_cloud_connections_name"),
    )
    op.create_index("ix_cloud_connections_provider", "cloud_connections", ["provider"])
    op.create_index("ix_cloud_connections_fingerprint", "cloud_connections", ["api_key_fingerprint"])

    op.create_table(
        "cloud_connection_audit_log",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("connection_id", sa.Integer, sa.ForeignKey("cloud_connections.id", ondelete="SET NULL"), nullable=True),
        sa.Column("actor_user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("action", sa.String(32), nullable=False),
        sa.Column("status", sa.String(16), nullable=True),
        sa.Column("before", sa.JSON, nullable=True),
        sa.Column("after", sa.JSON, nullable=True),
        sa.Column("note", sa.String(256), nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )
    op.create_index("ix_cloud_audit_connection", "cloud_connection_audit_log", ["connection_id"])
    op.create_index("ix_cloud_audit_actor", "cloud_connection_audit_log", ["actor_user_id"])
    op.create_index("ix_cloud_audit_created", "cloud_connection_audit_log", ["created_at"])

    # Soft-delete support: keep orphaned cloud agents visible in history
    op.add_column("ai_agents", sa.Column("connection_id", sa.Integer,
                                         sa.ForeignKey("cloud_connections.id", ondelete="SET NULL"),
                                         nullable=True))
    op.create_index("ix_ai_agents_connection", "ai_agents", ["connection_id"])

def downgrade():
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

SQLite-specific branch (peer to migration 024) for the column-drop pattern on downgrade.

---

## 7. Risk Additions (cloud-channel)

Two new rules added to the v1 8-rule additive scoring. Both use the same `{signal, weight, evidence}` shape already persisted in `risk_signals`:

| Signal | Weight | Level contribution |
|---|---|---|
| Cloud agent is the **only** AI Agent from this connection (connection has 1 agent) AND the agent has `code_exec` capability | +10 | medium |
| Cloud agent's `api_key_fingerprint` matches a fingerprint seen on a **different** connection (cross-connection key reuse) | +20 | high |

These are additive to the existing 8 rules. Threshold boundaries (24/25, 49/50, 74/75) are unchanged. Tests assert these rules are scored independently and that the total stays additive.

---

## 8. Out of scope (restated)

Reaffirming what's deferred to keep v2 focused:

- Other cloud providers (Google Vertex, Azure OpenAI, AWS Bedrock, LangSmith, Hugging Face).
- Per-key usage / cost / rate-limit data from the providers.
- Cross-provider key reuse detection.
- Webhook-based push discovery.
- Connection sharing / RBAC.
- Automatic key rotation.
- Master-key rotation (re-encryption on key change).
- Alerting on failed syncs (only the v1 "high-risk agent discovered" alert path is reused).
- A "Connections" stat card on the AIAgentsPage overview tab (visible only via the page link for now).
