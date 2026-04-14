"""
Go-based SSH scanner service (telos scanner).

Calls the Go scanner HTTP API running at GO_SCANNER_URL (default: http://localhost:8081).
Uses a task queue: enqueue a scan task, poll until done, map results back to Python types.
"""

import os
import time
import uuid
from datetime import datetime
from typing import List, Optional, Tuple

import requests

from backend.services.ssh_scanner import AccountInfo, ConnectionResult


def scan_asset(
    ip: str,
    port: int,
    username: str,
    password: Optional[str] = None,
    private_key: Optional[str] = None,
    passphrase: Optional[str] = None,
    timeout: int = 120,
) -> Tuple[ConnectionResult, List[AccountInfo]]:
    """
    Scan a Linux asset via the Go scanner HTTP API.

    Args:
        ip, port, username: asset connection info
        password: SSH password (if auth_type == password)
        private_key: SSH private key PEM content (if auth_type == ssh_key)
        passphrase: private key passphrase
        timeout: overall timeout in seconds (used as scan timeout + poll timeout)

    Returns:
        (ConnectionResult, List[AccountInfo]) — same interface as ssh_scanner.scan_asset
    """
    base_url = os.environ.get("GO_SCANNER_URL", "http://localhost:8081")
    task_id = str(uuid.uuid4())

    # ── 1. Enqueue scan task ─────────────────────────────────────────────
    task_payload = {
        "task_id": task_id,
        "callback_url": "",          # no callback, we'll poll
        "assets": [{
            "asset_id": 0,
            "ip": ip,
            "port": port,
            "username": username,
            "password": password or "",
            "private_key": private_key or "",
            "passphrase": passphrase or "",
            "os_type": "linux",
        }],
        "concurrency": 1,
        "timeout_sec": timeout,
    }

    try:
        resp = requests.post(
            f"{base_url}/api/v1/scan-tasks",
            json=task_payload,
            timeout=30,
        )
        if resp.status_code != 200:
            return _error_conn(f"Go scanner HTTP {resp.status_code}: {resp.text[:200]}")
    except requests.exceptions.Timeout:
        return _error_conn(f"Go scanner connect timeout after {timeout}s")
    except requests.exceptions.ConnectionError as e:
        raise ConnectionError(f"Cannot connect to Go scanner at {base_url}: {e}") from e
    except Exception as e:
        return _error_conn(f"Go scanner request error: {e}")

    # ── 2. Poll until done ────────────────────────────────────────────────
    poll_timeout = timeout + 30          # extra margin for queue processing
    poll_interval = 2                     # seconds between polls
    elapsed = 0

    while elapsed < poll_timeout:
        time.sleep(poll_interval)
        elapsed += poll_interval

        try:
            status_resp = requests.get(
                f"{base_url}/api/v1/scan-tasks/{task_id}/status",
                timeout=10,
            )
            if status_resp.status_code == 404:
                # Task not found yet — keep polling
                continue
            if status_resp.status_code != 200:
                continue
        except Exception:
            continue

        data = status_resp.json()
        status = data.get("status", "")

        if status == "done":
            result = data.get("result")
            if not result:
                return _error_conn("Go scanner returned empty result")

            results = result.get("results", [])
            if not results:
                return _error_conn("Go scanner returned no results")

            scan_result = results[0]
            return _map_result(scan_result)

        elif status == "error":
            return _error_conn(f"Go scanner task error: {data.get('error', 'unknown')}")

        # "pending" — keep polling

    return _error_conn(f"Go scanner timeout after {poll_timeout}s (task still pending)")


def _error_conn(error: str) -> Tuple[ConnectionResult, List[AccountInfo]]:
    return ConnectionResult(success=False, error=error, status="error"), []


def _map_result(go_result: dict) -> Tuple[ConnectionResult, List[AccountInfo]]:
    """Map Go ScanResult → Python (ConnectionResult, List[AccountInfo])."""
    conn = ConnectionResult(
        success=go_result.get("success", False),
        error=go_result.get("error") or None,
        status=go_result.get("status", "offline"),
    )

    accounts: List[AccountInfo] = []
    for acct in go_result.get("accounts", []):
        last_login: Optional[datetime] = None
        raw_ll: Optional[str] = acct.get("last_login")
        if raw_ll:
            try:
                last_login = datetime.fromisoformat(raw_ll.replace("Z", "+00:00"))
            except Exception:
                pass

        accounts.append(AccountInfo(
            username=acct.get("username", ""),
            uid_sid=acct.get("uid_sid", ""),
            is_admin=acct.get("is_admin", False),
            account_status=acct.get("account_status", "unknown"),
            home_dir=acct.get("home_dir", ""),
            shell=acct.get("shell", ""),
            groups=acct.get("groups", []),
            sudo_config=acct.get("sudo_config") or {},
            last_login=last_login,
            raw_info=acct.get("raw_info") or {},
        ))

    return conn, accounts
