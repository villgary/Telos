# AI Agent Cloud Discovery — Operator Guide

> **Audience**: Security operators and admins who manage AI Agent cloud integrations in Telos.
> **Scope**: Anthropic Console and OpenAI Dashboard discovery.

This guide covers day-to-end operation: how the discovery sources work, how to add / rotate / remove them, what the scheduler does, and how to read the audit log.

A *source* is one configured connection to a cloud provider. Each source is an independent entry; you can have multiple Anthropic sources (different orgs) or mix Anthropic and OpenAI. Removing a source does **not** delete the agents that were discovered from it.

---

## 1. Overview

The Cloud Agent Discovery feature lets Telos discover AI agents in your cloud provider accounts without installing agents on every host. You give Telos an **Admin API key** for Anthropic Console or OpenAI Dashboard; Telos calls the provider's API to enumerate organisations, projects, and API keys, then ingests the discovered agents into the same `ai_agents` table that host-based scanning uses.

| Provider | API base | Key shape |
|----------|----------|-----------|
| Anthropic | `https://api.anthropic.com` | `sk-ant-admin-...` |
| OpenAI | `https://api.openai.com` | `sk-admin-...` |

The plaintext key is **never** stored. It is encrypted with AES-256-GCM (`ACCOUNTSCAN_MASTER_KEY`) at rest, and only a 16-character fingerprint is shown in the UI for identification.

> **Note**: This feature is about *discovering* agents, not *calling* the provider. The LLM key for Telos's own AI features lives in **System Settings → AI Model** and is unrelated to the sources configured here.

---

## 2. Adding a source

Only an admin can add a source.

1. Navigate to **AI Agent Management → Cloud Agent Discovery**.
2. Click **Add Source**.
3. Fill in:
   - **Name** — a friendly identifier (e.g. `acme-prod`). Must be unique.
   - **Provider** — `Anthropic Console` or `OpenAI Dashboard`.
   - **API Key** — paste the Admin key. The field is a password input and the value is never echoed back.
4. Click **Add Source**.

The first **sync** runs only when you click **Sync Now** or when the 6h scheduler fires. Adding a source does **not** trigger an immediate sync.

---

## 3. Rotating a key

You should rotate provider keys on the same cadence as any other privileged credential.

1. In the sources table, click **Rotate Key** on the row.
2. Paste the new key.
3. Click **Rotate** in the dialog.

The old key is replaced atomically. Existing agents discovered under the old key keep their `connection_id` and `api_key_fingerprint`; the fingerprint column is updated to reflect the new key on the next sync.

A successful rotation writes an audit row with `action="rotated"` and before/after fingerprints.

---

## 4. Deleting a source

Deletion is **soft for agents**: the `CloudConnection` row is removed, but discovered agents stay in the `ai_agents` table. Their `connection_id` is NULLed out so the FK is preserved.

Click **Delete** on the row and confirm. The agent list will still show those agents, but they no longer have a `connection_id` to re-sync against.

> If you want to remove the discovered agents too, do it from the AI Agents list page after deleting the source.

A successful delete writes an audit row with `action="deleted"` and the source's name / provider / fingerprint in the `before` field.

---

## 5. Manual sync

Click **Sync Now** on a row to trigger an immediate discovery pass. The button shows a spinner and is disabled while a sync is in flight.

**Outcomes:**
- **success** — discovery + ingestion completed; `agents_discovered` and `agents_updated` are returned in the toast.
- **failed** — see the truncated error in the row; the full error is in the audit log's `note` column.
- **already in progress** — returns `409`. Wait for the running sync to finish, or check the audit log for the prior `sync_started` row that did not produce a `sync_finished` (that means the process died mid-sync; rerun manually).

---

## 6. Scheduled sync (6h)

The APScheduler runs `_sync_all_cloud_connections` every 6 hours, fanning out a sync to every source. One source's failure does not block the others.

- A source that already has `last_sync_status = "running"` is **not** double-synced (the per-source 409 protects you here).
- Failed syncs retry on the next 6h tick. There is no exponential backoff for the scheduler — if the failure is persistent (e.g. an expired key), fix the key and click **Sync Now** to validate.
- Each tick writes a `sync_started` and `sync_finished` pair to the audit log, even on failure. A missing `sync_finished` for a `sync_started` indicates a process crash mid-sync; investigate.

---

## 7. Reading the audit log

Click **Audit Log** on a row to open the drawer. The most recent 100 entries are shown, newest first. Each row has:

| Column | Meaning |
|--------|---------|
| Time | UTC timestamp of the action. |
| Action | One of `created`, `renamed`, `rotated`, `deleted`, `sync_started`, `sync_finished`. |
| Note | Free text — used for sync error messages (truncated to 256 chars). |

The `before` and `after` JSON columns are also stored on each row but not rendered in the UI. They contain only the **name** and **fingerprint** — never the plaintext key, never the encrypted blob. If you need to see them for forensics, query `cloud_connection_audit_log` directly.

---

## 8. What does NOT get logged

To be explicit about the security boundary:
- The plaintext API key is never written to the audit log.
- The encrypted blob (`encrypted_api_key`) is never written to the audit log.
- The HTTP request/response bodies from the provider API are never written to the audit log (they may contain the key in the request).

If you suspect a key leak, **rotate the key** in the provider's console immediately. Then audit the `last_sync_error` column for any `auth_failed:` messages that might indicate a key had been working and stopped.

---

## 9. Common issues

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| Sync returns `auth_failed: ...` | Expired or revoked key | Rotate the key in the provider, then rotate it in Telos. |
| Sync returns `rate_limited_or_transient: ...` | Provider rate limit or transient 5xx | Wait for the next 6h tick. If persistent, check the provider's status page. |
| `409 already in progress` | A sync is currently running | Wait. If the in-flight sync never resolves, restart the backend — the next tick will pick it up. |
| Sync reports `0 agents_discovered` after a successful run | The provider has no organisations, projects, or keys matching the Admin key's scope | Verify the key has the correct workspace / org permissions in the provider's console. |
| `Created` audit row but no `sync_started` for it | The source was added between scheduler ticks and no manual sync has run | Click **Sync Now**. |

---

## 10. Security notes

- The Admin key is the most privileged credential in the provider's IAM. Treat it like a database root password.
- Only the `admin` role can see, add, edit, rotate, or delete sources. Operators with the `operator` or `viewer` role can list sources and view the audit log, but not modify them.
- The encryption key (`ACCOUNTSCAN_MASTER_KEY`) is the master secret. If it leaks, **all stored cloud keys are compromised simultaneously**. Rotate it via the documented key-rotation procedure (out of scope for this guide; see the admin guide).
- The audit log is append-only. There is no DELETE endpoint for `cloud_connection_audit_log`. If you need to prune it, do so directly in the database with a DBA's approval.
