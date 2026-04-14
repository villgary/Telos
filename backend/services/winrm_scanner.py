"""
Windows WinRM scanner service.
Collects account information from Windows assets via WinRM + PowerShell.
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Tuple

import winrm

from backend.services.ssh_scanner import AccountInfo, ConnectionResult


def _run_ps(client: winrm.Session, script: str, timeout: int = 60) -> Tuple[str, int]:
    """Execute a PowerShell script, return (stdout, exit_code)."""
    try:
        response = client.run_ps(script, timeout_seconds=timeout)
        return (
            response.std_out.decode("utf-8", errors="replace").strip(),
            response.status_code,
        )
    except Exception as e:
        return (str(e), 1)


def _parse_local_users(output: str) -> List[dict]:
    """Parse Get-LocalUser JSON output."""
    users = []
    # Try JSON format first
    try:
        data = json.loads(output)
        if isinstance(data, list):
            return data
    except (json.JSONDecodeError, ValueError):
        pass

    # Fallback: parse line-by-line CSV-like format
    for line in output.splitlines():
        if not line.strip() or line.startswith("---"):
            continue
        parts = line.split()
        if len(parts) >= 3:
            users.append({
                "Name": parts[0],
                "Enabled": parts[1],
                "SID": parts[2] if len(parts) > 2 else "Unknown",
            })
    return users


def _parse_admin_members(output: str) -> set:
    """Parse Get-LocalGroupMember output, return set of admin usernames."""
    admins = set()
    for line in output.splitlines():
        if not line.strip() or line.startswith("---"):
            continue
        # Format: DOMAIN\\Username or Username
        parts = line.strip().split("\\")
        username = parts[-1].strip()
        if username and username not in ("", "The"):
            admins.add(username.lower())
    return admins


def scan_asset(
    ip: str,
    port: int,
    username: str,
    password: Optional[str] = None,
    timeout: int = 120,
) -> Tuple[ConnectionResult, List[AccountInfo]]:
    """
    Main entry point: scan a Windows asset via WinRM.

    Returns:
        (ConnectionResult, List[AccountInfo])
    """
    # Determine protocol
    if port == 5986:
        transport = "ssl"
        endpoint = f"https://{ip}:{port}/wsman"
    else:
        transport = "ntlm"
        endpoint = f"http://{ip}:{port}/wsman"

    try:
        session = winrm.Session(
            endpoint,
            auth=(username, password or ""),
            transport=transport,
            server_cert_validation="ignore",
        )
        # Test connection with a simple command
        _, rc = _run_ps(session, "echo ok", timeout=15)
        if rc != 0:
            return (ConnectionResult(success=False, error="WinRM 连接测试失败", status="offline"), [])
    except Exception as e:
        return (ConnectionResult(success=False, error=str(e), status="offline"), [])

    try:
        # ── Collect local users ──────────────────────
        users_script = (
            "Get-LocalUser | "
            "Select-Object Name, Enabled, SID, "
            "PasswordRequired, PasswordExpired, "
            "LastLogon, UserMayChangePassword | "
            "ConvertTo-Json -Compress"
        )
        users_out, rc_users = _run_ps(session, users_script, timeout=timeout)
        local_users = _parse_local_users(users_out) if rc_users == 0 else []

        # ── Collect Administrators group members ─────
        admins_script = (
            "Get-LocalGroupMember -Group 'Administrators' | "
            "Select-Object Name | ConvertTo-Json -Compress"
        )
        admins_out, rc_admins = _run_ps(session, admins_script, timeout=timeout)
        admin_members = _parse_admin_members(admins_out) if rc_admins == 0 else set()

        # Also check Remote Desktop Users and Power Users
        for group in ("Remote Desktop Users", "Power Users"):
            group_script = (
                f"Get-LocalGroupMember -Group '{group}' | "
                f"Select-Object Name | ConvertTo-Json -Compress"
            )
            group_out, _ = _run_ps(session, group_script, timeout=timeout)
            admin_members |= _parse_admin_members(group_out)

        # ── Collect detailed info per user ──────────
        accounts: List[AccountInfo] = []
        for user in local_users:
            name = user.get("Name", "").strip()
            if not name:
                continue

            sid = user.get("SID", "Unknown")
            enabled_raw = str(user.get("Enabled", True)).lower()
            enabled = enabled_raw in ("true", "yes", "1")

            # Determine account status
            if not enabled:
                account_status = "disabled"
            else:
                pw_expired = str(user.get("PasswordExpired", False)).lower()
                account_status = "enabled" if pw_expired != "true" else "locked"

            # Determine is_admin
            is_admin = name.lower() in admin_members

            # Last logon
            last_login_str = user.get("LastLogon")
            last_login = None
            if last_login_str and last_login_str not in ("", "Never", "N/A"):
                try:
                    # Handle ISO format from PowerShell JSON
                    last_login = datetime.fromisoformat(last_login_str.replace("Z", "+00:00"))
                except (ValueError, TypeError):
                    try:
                        last_login = datetime.strptime(last_login_str, "%m/%d/%Y %I:%M:%S %p")
                    except ValueError:
                        pass

            accounts.append(AccountInfo(
                username=name,
                uid_sid=sid,
                is_admin=is_admin,
                account_status=account_status,
                home_dir="",
                shell="PowerShell",
                groups=[],
                sudo_config={"is_local_admin": is_admin} if is_admin else None,
                last_login=last_login,
                raw_info={
                    "password_required": user.get("PasswordRequired"),
                    "password_expired": user.get("PasswordExpired"),
                    "last_logon_raw": last_login_str,
                    "enabled": enabled,
                },
            ))

        return (ConnectionResult(success=True, status="online"), accounts)

    except Exception as e:
        return (ConnectionResult(success=False, error=str(e), status="offline"), [])
