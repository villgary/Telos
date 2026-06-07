# NHI Detection & Alerts — Design Spec

> **Sub-project 1 of 4 in the NHI capabilities roadmap.** Future sub-projects: lifecycle & rotation tracking, policy engine & enforcement, graph & ownership map.

**Goal:** Replace the current minimal NHI alert system (2 hardcoded-Chinese alert types) with a richer, i18n-aware system that detects four specific NHI risk conditions, including the first cross-asset correlation.

**Status:** Approved design — ready for implementation planning.

**Tech stack:** FastAPI, SQLAlchemy 2, Alembic, React 18, TypeScript, Ant Design 5, i18next.

---

## Scope (in / out)

**In scope:**
- 4 new alert types: `privilege_escalation`, `nopasswd_sudo`, `credential_leak`, `cross_asset_spread`
- Existing `risk_alert` and `no_owner` get i18n keys (no behavioral change)
- i18n key+params pattern for all NHI alerts (matches existing UEBA / playbook pattern)
- New `NHIPolicy` fields for per-policy rule configuration
- Cluster alert model for `cross_asset_spread` (one alert per `(nhi_type, username)`)
- Frontend: i18n title rendering, alert type filter, asset_count column for cluster alerts
- Alembic migration 023
- Backend + frontend tests

**Out of scope (later sub-projects):**
- NHI lifecycle (active/dormant/departed)
- Real credential rotation tracking
- NHI↔NHI / NHI↔Human relationship graph
- Force-graph visualization
- NHI behavioral baseline (UEBA for NHIs)
- AI-assisted NHI analysis
- Policy editor UI (NHIPolicy remains API-driven in this sub-project)

---

## 1. Architecture & Data Flow

**Entry point:** `NHIAnalyzer.sync_all()` (existing) — extended. Triggered by the manual sync button in the UI; intended to be called from the post-scan pipeline (`_execute_scan` `finally` block) once the next feature is added.

**Flow per sync:**
1. `sync_all()` — existing: classify + upsert `NHIIdentity` rows
2. `generate_alerts()` — extended in this sub-project:
   - For each `NHIIdentity`:
     - `privilege_escalation` (compare against prior `AccountSnapshot` for same `(asset_id, username)`)
     - `nopasswd_sudo` (if `has_nopasswd_sudo` and no existing `new` alert)
     - `credential_leak` (if `risk_signals` contains a critical `credential_leak`)
     - `risk_alert` (existing, now with i18n keys)
     - `no_owner` (existing, now with i18n keys)
   - Cluster query: group NHIs by `(nhi_type, username)`, find clusters matching policy thresholds, upsert cluster alerts
3. Single `db.commit()` at end

**Privilege escalation:** queries `AccountSnapshot` history for the same `(asset_id, username)`; uses the most recent prior `is_admin` to detect a `False → True` flip.

**Cluster dedup:** one alert per `(cluster_key, alert_type='cross_asset_spread', status='new')`. If a new cluster is detected and an existing alert is in `new` state, update it (`asset_count`, `updated_at`, `message_params`). If existing is `acknowledged` or `resolved`, leave it and create a new alert (operators have triaged; a new instance is a new event).

**File organization:** `nhi_analyzer.py` grows from ~485 to ~700 lines. Internal section banners (already present) keep it navigable. The 4 alert types are documented in a docstring at the top of `generate_alerts()`.

---

## 2. Data Model Changes

Single Alembic migration `023_nhi_alerts_enhancement.py`.

### `NHIAlert`

| Field | Change | Why |
|---|---|---|
| `nhi_id` | `nullable=True` (was NOT NULL) | Cluster alerts span multiple NHIs |
| `cluster_key` | NEW `String(192)`, nullable, **indexed** with `(alert_type, status)` | Dedup key for cluster alerts; format `f"{nhi_type}:{username}"`; sized to fit `String(32) + ":" + String(128)` worst case |
| `nhi_username` | NEW `String(128)`, nullable, denormalized | Cluster alerts need a displayable username; no JOIN needed |
| `nhi_type` | NEW `String(32)`, nullable, denormalized | Same reason |
| `asset_count` | NEW `Integer`, nullable | For `cross_asset_spread` |
| `updated_at` | NEW `DateTime`, default `now()` | Track cluster alert refreshes |

Existing `title_key` / `title_params` / `message_key` / `message_params` columns stay — we just populate them for new alerts. Existing Chinese `title` / `message` strings stay as a fallback for legacy rows.

### `NHIPolicy`

| Field | Type | Default | Used by |
|---|---|---|---|
| `enabled_alert_types` | JSON `list[str]` | `["privilege_escalation","nopasswd_sudo","credential_leak","cross_asset_spread"]` | All 4 alert types |
| `cross_asset_threshold` | Integer | 3 | `cross_asset_spread` |
| `cross_asset_window_days` | Integer | 7 | `cross_asset_spread` |

JSON list for enable flags (rather than 4 booleans) so future alert types only need a string added — no schema migration. Pydantic schema validates the list against `Literal[...]`.

### `NHIIdentity`

No schema change. Privilege-escalation detection is computed at alert-generation time by querying prior `AccountSnapshot` rows for the same `(asset_id, username)`. The escalation is also appended to the existing `risk_signals` JSON column.

### Migration safety

- Making `nhi_id` nullable is non-breaking on both SQLite and PostgreSQL
- New columns on `NHIPolicy` use `server_default`
- Composite index `(cluster_key, alert_type, status)` uses `CREATE INDEX IF NOT EXISTS`
- Existing rows untouched

### Seed

`main.py` gains a `_seed_default_nhi_policies(db)` helper called from lifespan, creating a single global policy with `nhi_type=NULL` and the default thresholds if `NHIPolicy` is empty. Existing 6 default playbooks are unchanged.

---

## 3. Alert Engine Logic

### Single-NHI alerts (3 types)

All three iterate `NHIIdentity` rows and dedup by `(nhi_id, alert_type, status='new')`. If existing alert is `acknowledged` or `resolved`, a new alert is created — a new occurrence is a new event.

**`privilege_escalation`** — new detection (not currently a risk signal):
- For each NHI, query the most recent prior `AccountSnapshot` for the same `(asset_id, username)` with `snapshot_time < current.snapshot_time` and `snapshot_time IS NOT NULL` and `deleted_at IS NULL`
- Trigger: `prior.is_admin == False` and `current.is_admin == True`
- On trigger: append a `privilege_escalation` entry to `NHIIdentity.risk_signals` AND fire an alert
- Title key: `nhi.alert.privilege_escalation.title`
- Message params: `{username, asset_code, prior_snapshot_time}`

**`nopasswd_sudo`** — signal already detected; we just need to fire the alert:
- Trigger: `NHIIdentity.has_nopasswd_sudo == True`
- Title key: `nhi.alert.nopasswd_sudo.title`
- Message params: `{username, asset_code}`

**`credential_leak`** — signal already detected; just fire the alert:
- Trigger: any `risk_signals[i]` where `type == 'credential_leak'` and `severity == 'critical'`
- Title key: `nhi.alert.credential_leak.title`
- Message params: `{username, file_count}`

### Cluster alert: `cross_asset_spread`

Run after the single-NHI loop.

```python
# Step 1: collect all enabled policies with cross_asset_spread in their list
spread_policies = [
    p for p in db.query(NHIPolicy).filter(NHIPolicy.enabled == True).all()
    if 'cross_asset_spread' in (p.enabled_alert_types or [])
]

# Step 2: gather candidates from ALL policies' windows (union)
candidates_q = db.query(NHIIdentity).filter(
    NHIIdentity.is_active == True,
    NHIIdentity.asset_id.isnot(None),
)
all_candidates = candidates_q.all()  # small set; per-asset scan

# Step 3: for each cluster, find the most-permissive matching policy
clusters = defaultdict(set)  # (nhi_type, username) -> set[asset_id]
cluster_policy = {}  # (nhi_type, username) -> NHIPolicy (most permissive)
for nhi in all_candidates:
    cluster_key = (nhi.nhi_type, nhi.username)
    clusters[cluster_key].add(nhi.asset_id)
    # pick the matching policy with the smallest threshold
    matching = [
        p for p in spread_policies
        if p.nhi_type is None or p.nhi_type == nhi.nhi_type
    ]
    if not matching:
        continue
    most_permissive = min(matching, key=lambda p: p.cross_asset_threshold)
    if cluster_key not in cluster_policy:
        cluster_policy[cluster_key] = most_permissive
    else:
        current = cluster_policy[cluster_key]
        if most_permissive.cross_asset_threshold < current.cross_asset_threshold:
            cluster_policy[cluster_key] = most_permissive

# Step 4: fire (or update) one alert per cluster whose size meets its policy
for (nhi_type, username), asset_ids in clusters.items():
    policy = cluster_policy.get((nhi_type, username))
    if policy is None:
        continue
    if len(asset_ids) < policy.cross_asset_threshold:
        continue
    # Respect window: only count assets seen within the policy's window
    window_cutoff = now() - timedelta(days=policy.cross_asset_window_days)
    recent_asset_ids = {
        n.asset_id for n in all_candidates
        if n.nhi_type == nhi_type
        and n.username == username
        and n.last_seen_at is not None
        and n.last_seen_at >= window_cutoff
    }
    if len(recent_asset_ids) < policy.cross_asset_threshold:
        continue
    cluster_key = f"{nhi_type}:{username}"
    existing = db.query(NHIAlert).filter(
        NHIAlert.cluster_key == cluster_key,
        NHIAlert.alert_type == 'cross_asset_spread',
        NHIAlert.status == 'new',
    ).first()
    if existing:
        existing.asset_count = len(recent_asset_ids)
        existing.updated_at = now()
        existing.message_params = {
            'username': username, 'asset_count': len(recent_asset_ids),
            'window_days': policy.cross_asset_window_days,
        }
    else:
        db.add(NHIAlert(
            nhi_id=None,
            cluster_key=cluster_key,
            nhi_username=username,
            nhi_type=nhi_type,
            asset_count=len(recent_asset_ids),
            alert_type='cross_asset_spread',
            level='warning',
            title_key='nhi.alert.cross_asset_spread.title',
            message_key='nhi.alert.cross_asset_spread.message',
            title_params={'username': username, 'asset_count': len(recent_asset_ids)},
            message_params={
                'username': username, 'asset_count': len(recent_asset_ids),
                'window_days': policy.cross_asset_window_days,
            },
        ))
```

Policy matching: a policy is selected for a cluster if `policy.nhi_type is None` (global) or `policy.nhi_type == cluster's nhi_type`. When multiple policies match, the most permissive (smallest `cross_asset_threshold`) is used — operationally rare, documented behavior. One alert per cluster regardless of how many policies match.

### Existing alerts — i18n upgrade

`risk_alert` and `no_owner` in `generate_alerts()` now also populate `title_key`, `title_params`, `message_key`, `message_params`. Hardcoded Chinese `title` / `message` stay as fallback. The frontend prefers the i18n key when present.

`risk_alert` continues to fire when `nhi_level in ('critical', 'high')`. The 4 new alert types fire on specific signals regardless of overall level — complementary, not replacement.

---

## 4. i18n Strategy

Follows the existing UEBA / playbook alert pattern. 12 new keys per locale file, grouped under `nhi.alert.*`:

| Key | EN value |
|---|---|
| `nhi.alert.privilege_escalation.title` | `Privilege escalation: {username}` |
| `nhi.alert.privilege_escalation.message` | `{username} escalated to admin on {asset_code} (was non-admin in prior snapshot)` |
| `nhi.alert.nopasswd_sudo.title` | `NOPASSWD sudo: {username}` |
| `nhi.alert.nopasswd_sudo.message` | `Account {username} has NOPASSWD sudo on {asset_code}` |
| `nhi.alert.credential_leak.title` | `Credential leak: {username}` |
| `nhi.alert.credential_leak.message` | `Account {username} has {file_count} critical credential findings` |
| `nhi.alert.cross_asset_spread.title` | `Cross-asset spread: {username}` |
| `nhi.alert.cross_asset_spread.message` | `Same NHI seen on {asset_count} assets in the last {window_days} days` |
| `nhi.alert.risk_alert.title` | `NHI risk: {username}` |
| `nhi.alert.risk_alert.message` | `Non-human identity {username} risk level {level}, score {score}` |
| `nhi.alert.no_owner.title` | `NHI unowned: {username}` |
| `nhi.alert.no_owner.message` | `Non-human identity {username} has no owner assigned` |

Plus 6 alert-type-label keys for the frontend filter (`nhi.alert_type.<type>`):

| Key | EN value | zh-CN value |
|---|---|---|
| `nhi.alert_type.privilege_escalation` | `Privilege escalation` | `权限提升` |
| `nhi.alert_type.nopasswd_sudo` | `NOPASSWD sudo` | `免密sudo` |
| `nhi.alert_type.credential_leak` | `Credential leak` | `凭据泄露` |
| `nhi.alert_type.cross_asset_spread` | `Cross-asset spread` | `跨资产扩散` |
| `nhi.alert_type.risk_alert` | `Risk alert` | `风险告警` |
| `nhi.alert_type.no_owner` | `No owner` | `无Owner` |

The prebuild i18n-parity script catches missing keys. Legacy alert rows are not migrated; the frontend falls back to `alert.title` when `title_key` is null.

---

## 5. Frontend Changes

All in `frontend/src/pages/NHIDashboard.tsx` plus locale files. No new components, no routing changes.

**1. i18n-aware title rendering:**
```tsx
const renderAlertTitle = (a: NHIAlert) =>
  a.title_key ? t(a.title_key, a.title_params ?? {}) : a.title
```
Used in the alerts tab `title` column and in the dashboard's recent-alerts list (if shown).

**2. Alert type filter** in the alerts tab. New `Select` filter parallel to the existing type/level filter in the inventory tab. Maps to `listNHIAlerts({ alert_type, ... })` once the API supports it.

**3. `asset_count` column for cluster alerts.** When `alert.cluster_key` is set (cluster alert), show `asset_count` in a new column. The listNHIAlerts response includes this field.

**4. i18n keys for alert type labels.** Replace the existing hardcoded `map` in the alerts tab title column with `t('nhi.alert_type.' + v) || v`.

**5. API client additions** in `frontend/src/api/client.ts`:
- `NHIAlert` interface gets optional `title_key`, `title_params`, `message_key`, `message_params`, `cluster_key`, `asset_count`
- `listNHIAlerts` params add `alert_type` filter

---

## 6. Testing Strategy

### Backend — `backend/tests/test_nhi_alerts.py` (new file)

| Test | Verifies |
|---|---|
| `test_privilege_escalation_fires` | 2 snapshots, prior `is_admin=False`, current `is_admin=True` → 1 alert with `alert_type='privilege_escalation'`, `level='critical'`, `title_key='nhi.alert.privilege_escalation.title'` |
| `test_privilege_escalation_no_fire_when_already_admin` | Prior was already admin → no alert |
| `test_nopasswd_sudo_alert` | NHI with `has_nopasswd_sudo=True` → 1 alert |
| `test_credential_leak_alert` | NHI with `risk_signals` containing critical `credential_leak` → 1 alert |
| `test_cross_asset_spread_cluster_alert` | 3 NHIs for same `(nhi_type, username)` on 3 distinct assets → 1 cluster alert with `asset_count=3`, `nhi_id=None`, `cluster_key='service:deploy'` |
| `test_cross_asset_spread_below_threshold` | 2 NHIs, threshold=3 → no alert |
| `test_cross_asset_spread_dedup_existing_new` | Cluster alert exists in `new` state → call sync again, alert updated (not duplicated), `asset_count` refreshed |
| `test_cross_asset_spread_window_respected` | 3 NHIs but `last_seen_at` outside window → no alert |
| `test_policy_nhi_type_filter` | Policy with `nhi_type='cloud'` only fires for cloud NHIs |
| `test_i18n_keys_populated` | Every new alert has `title_key`, `message_key`, `title_params`, `message_params` non-null |
| `test_legacy_alerts_unaffected` | Existing Chinese-only alerts still readable; `title_key` is null on them |

### Migration — `backend/tests/test_migrations.py` (extend existing)

| Test | Verifies |
|---|---|
| `test_migration_023_nhi_alert_cluster_key` | After upgrade, `NHIAlert.nhi_id` is nullable, `cluster_key` column exists, composite index exists |

### Frontend — `frontend/e2e/nhi-alerts.spec.ts` (new file)

Smoke-level only.

| Test | Verifies |
|---|---|
| `test_nhi_alerts_tab_loads` | Navigate to `/nhi`, click Alerts tab, table renders rows |
| `test_nhi_alert_type_filter` | Select alert type filter, table updates |

### Out of test scope

- Scheduler integration (out of scope — sync is manual)
- Visual chart rendering (covered by snapshot, not behavior)
- NHI volume / performance testing (low hundreds per asset expected)

---

## 7. Error Handling & Edge Cases

**Pydantic input validation** (rejects bad input at the API boundary):
- `NHIPolicy.cross_asset_threshold`: `Field(ge=2, le=100)` — at least 2 assets
- `NHIPolicy.cross_asset_window_days`: `Field(ge=1, le=365)`
- `NHIPolicy.enabled_alert_types`: each item must be in the allowed set; schema raises 422 on bad values

**Null `snapshot_time` in `privilege_escalation` prior lookup:**
- `WHERE snapshot_time < :current AND snapshot_time IS NOT NULL`
- If the current snapshot also has null time, skip the check silently (data-quality issue out of scope)

**Cluster alert concurrency:**
- Two `sync_all()` calls in flight: the second's dedup query finds the first's `status='new'` alert and updates `asset_count`. Worst case is stale `asset_count` (last-writer-wins) — acceptable for an ITDR system
- No locking introduced; existing behavior unchanged

**No prior snapshot for `privilege_escalation`:**
- First-seen NHI → no comparison possible → no alert
- Possible follow-up: "first-seen admin" alert, but that's a new alert type — out of scope

**NHI with `asset_id IS NULL` in cluster query:**
- Filter `asset_id IS NOT NULL` — nulls can't be counted in distinct assets

**Deleted snapshots in prior lookup:**
- Filter `deleted_at IS NULL` — standard pattern

**No `NHIPolicy` in DB:**
- Default global policy seeded at startup. If seeding fails, log a warning and continue — `cross_asset_spread` simply doesn't fire, but the other 3 alert types still work (they don't depend on policy)

**Frontend missing i18n key fallback:**
- If `t(title_key)` returns the key, the alert shows the raw key string. Mitigated by the prebuild script catching missing keys. Fail loud at build time, not silently degrade

**In-flight cluster alert when operator resolves it mid-sync:**
- Operator sets `status='resolved'` between detection and insert
- Dedup query filters `status='new'`, doesn't find the resolved alert
- A new alert is created — correct behavior: resolved alerts don't suppress new occurrences

---

## Files Touched

**Backend:**
- `backend/models/nhi.py` — schema additions on `NHIAlert`, `NHIPolicy`
- `backend/services/nhi_analyzer.py` — extended `generate_alerts()`, added `privilege_escalation` signal detection
- `backend/schemas/nhi.py` — new fields on response models, validation on `NHIPolicy` fields
- `backend/routers/nhi.py` — `NHIPolicy` create/list endpoints use new schema
- `backend/main.py` — `_seed_default_nhi_policies()` lifespan helper
- `backend/alembic/versions/023_nhi_alerts_enhancement.py` — new migration
- `backend/tests/test_nhi_alerts.py` — new
- `backend/tests/test_migrations.py` — extend (or new `test_migration_023`)

**Frontend:**
- `frontend/src/pages/NHIDashboard.tsx` — i18n rendering, alert type filter, asset_count column
- `frontend/src/api/client.ts` — extend `NHIAlert` interface, `listNHIAlerts` params
- `frontend/src/locales/en-US.json` — 18 new keys (12 alert strings + 6 alert type labels)
- `frontend/src/locales/zh-CN.json` — 18 new keys
- `frontend/e2e/nhi-alerts.spec.ts` — new

---

## Open Questions

None at design-approval time. Items deferred to later sub-projects (see "Out of scope").

## Acceptance Criteria

1. Running `alembic upgrade head` on a populated DB succeeds without data loss
2. `pytest backend/tests/test_nhi_alerts.py` passes all 11 tests
3. `pytest backend/tests/test_migrations.py` includes and passes `test_migration_023_nhi_alert_cluster_key`
4. Triggering a sync with a known `nopasswd_sudo` NHI produces an alert with `title_key='nhi.alert.nopasswd_sudo.title'`
5. Triggering a sync with 3 NHIs for the same `(nhi_type, username)` on 3 distinct assets produces 1 cluster alert with `asset_count=3`, `nhi_id=None`, `cluster_key` set
6. Running the sync twice in a row does not produce duplicate cluster alerts — the second run updates `asset_count` and `updated_at` on the first
7. `npm run build` succeeds (i18n parity check passes)
8. Playwright E2E `nhi-alerts.spec.ts` passes
9. `pytest --cov` shows >80% line coverage for `nhi_analyzer.py` alert-generation paths
