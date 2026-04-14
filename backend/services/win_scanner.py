"""
Windows account scanner via SMB/SAMR (port 445) + WinRM (port 5985).
SAMR enumerates accounts; WinRM fetches last-login timestamps via Get-LocalUser/Get-ADUser.
"""

import warnings
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from backend.services.ssh_scanner import AccountInfo, ConnectionResult

# Well-known Windows RIDs for actual admin/privileged accounts
# 500 = Administrator (real admin), 544 = Administrators local group
# Excludes: 501 Guest, 502 Krbtgt, 503 DefaultAccount, 504 WDAGUtilityAccount
#           505+, 545-552 = Users/Guests/PowerUsers groups (not individual admins)
ADMIN_RIDS = {500, 544}


def _parse_wmi_date(date_str: str) -> Optional[datetime]:
    """Parse WMI /Date(...) format to datetime (UTC)."""
    if not date_str:
        return None
    m = re.search(r"/Date\((\d+)\)/", date_str)
    if not m:
        return None
    ms = int(m.group(1))
    try:
        return datetime.fromtimestamp(ms / 1000.0, tz=timezone.utc)
    except (ValueError, OSError):
        return None


def _fetch_last_logins_via_winrm(
    ip: str,
    username: str,
    password: str,
    timeout: int = 120,
) -> Dict[str, datetime]:
    """
    Fetch last-login timestamps via WinRM (HTTP/NTLM).
    Returns dict: username -> last_login datetime (UTC).
    Falls back gracefully if WinRM is unavailable.
    """
    result: Dict[str, datetime] = {}
    try:
        import winrm
    except ImportError:
        return result

    try:
        sess = winrm.Session(
            f"http://{ip}:5985/wsman",
            auth=(username, password),
            transport="ntlm",
        )
        # Fetch extended fields: LastLogon, PasswordLastSet, PasswordNeverExpires, Enabled
        ps_cmd = (
            "Get-LocalUser | Select-Object Name, LastLogon, PasswordLastSet, "
            "PasswordNeverExpires, Enabled, Description | ConvertTo-Json -Compress"
        )
        r = sess.run_ps(ps_cmd)
        if r.status_code == 0 and r.std_out:
            import json
            try:
                data = json.loads(r.std_out.decode("utf-8", errors="ignore"))
                if isinstance(data, dict):
                    data = [data]
                for entry in data:
                    name = entry.get("Name") or ""
                    ts = _parse_wmi_date(entry.get("LastLogon") or "")
                    if ts:
                        result[name] = ts
            except (json.JSONDecodeError, TypeError):
                pass
    except Exception:
        pass

    return result


def scan_asset(
    ip: str,
    port: int,
    username: str,
    password: Optional[str] = None,
    timeout: int = 120,
) -> Tuple[ConnectionResult, List[AccountInfo]]:
    """
    Scan a Windows asset via SMB/SAMR (Security Account Manager Remote)
    and WinRM (last-login timestamps via Get-LocalUser / Get-ADUser).

    Returns:
        (ConnectionResult, List[AccountInfo])
    """
    warnings.filterwarnings("ignore")

    # ── Step 1: SMB/SAMR — enumerate accounts ────────────────────────────────
    try:
        import socket
        from impacket.dcerpc.v5 import samr, transport

        socket.setdefaulttimeout(timeout)

        rpctransport = transport.SMBTransport(
            ip, 445,
            filename=r"\samr",
            username=username,
            password=password or "",
        )

        dce = rpctransport.get_dce_rpc()
        dce.connect()
        dce.bind(samr.MSRPC_UUID_SAMR)

        server_resp = samr.hSamrConnect(dce, r"\x00")
        server_handle = server_resp["ServerHandle"]

        enum_resp = samr.hSamrEnumerateDomainsInSamServer(dce, server_handle)
        domains = enum_resp["Buffer"]["Buffer"]

        all_users: List[AccountInfo] = []

        for domain in domains:
            domain_name = domain["Name"]
            if domain_name == "Builtin":
                continue

            lookup_resp = samr.hSamrLookupDomainInSamServer(dce, server_handle, domain_name)
            domain_id = lookup_resp["DomainId"]
            domain_sid = domain_id.formatCanonical()

            open_resp = samr.hSamrOpenDomain(
                dce, server_handle, samr.MAXIMUM_ALLOWED, domain_id
            )
            domain_handle = open_resp["DomainHandle"]

            try:
                enum_users = samr.hSamrEnumerateUsersInDomain(dce, domain_handle)
                users = enum_users["Buffer"]["Buffer"]
            except Exception:
                users = []

            for user in users:
                name = user["Name"]
                rid = user["RelativeId"]
                is_admin = rid in ADMIN_RIDS
                uid_sid = f"{domain_sid}-{rid}"

                user_flags = getattr(user, "UserAccountControl", None)
                account_status = "enabled"
                if user_flags is not None:
                    if user_flags & 0x0001:
                        account_status = "disabled"
                    elif user_flags & 0x0040:
                        account_status = "locked"

                all_users.append(AccountInfo(
                    username=name,
                    uid_sid=uid_sid,
                    is_admin=is_admin,
                    account_status=account_status,
                    home_dir="",
                    shell="PowerShell",
                    groups=[],
                    sudo_config={"is_builtin_admin": rid == 500} if is_admin else None,
                    last_login=None,   # filled below via WinRM
                    raw_info={
                        "domain": domain_name,
                        "rid": rid,
                        "is_builtin_admin": rid == 500,
                        "is_well_known_rid": rid in ADMIN_RIDS,
                    },
                ))

            samr.hSamrCloseHandle(dce, domain_handle)

        samr.hSamrCloseHandle(dce, server_handle)
        dce.disconnect()

    except Exception as e:
        err_str = str(e)
        if "STATUS_LOGON_FAILURE" in err_str or "LOGON_FAILURE" in err_str:
            return (ConnectionResult(success=False, error=f"认证失败: {err_str}", status="auth_failed"), [])
        return (ConnectionResult(success=False, error=f"扫描失败: {err_str}", status="offline"), [])

    # ── Step 2: WinRM — fetch last-login timestamps ────────────────────────
    # Exclude the scan credential itself: its "last login" would be the scan time
    if password:
        last_logins = _fetch_last_logins_via_winrm(ip, username, password, timeout)
        # Remove the scan credential from results so its scan-time login doesn't pollute data
        last_logins.pop(username, None)
        if last_logins:
            by_name: Dict[str, datetime] = last_logins
            for user in all_users:
                user.last_login = by_name.get(user.username)

    return (ConnectionResult(success=True, status="online"), all_users)

