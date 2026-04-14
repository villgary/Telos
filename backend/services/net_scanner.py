"""
Network device account scanner.
Supports Cisco IOS/IOS-XE/NX-OS, H3C Comware, Huawei VRP.
Extracts accounts from running-config and vendor-specific commands via SSH.
"""

import re
import time
import logging
from typing import List, Tuple, Optional, Dict
from dataclasses import dataclass, field
from datetime import datetime

import paramiko

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────
#  Shared dataclasses (re-used across scanners)
# ──────────────────────────────────────────

from backend.services.ssh_scanner import AccountInfo, ConnectionResult


# ──────────────────────────────────────────
#  Vendor command definitions
# ──────────────────────────────────────────

@dataclass
class VendorCommands:
    name: str
    list_users: str          # show all configured users
    list_online: str         # show currently logged-in users
    privilege_cmd: str        # show current privilege level
    config_users: str        # extract username lines from running-config
    enter_enable: str        # command to enter enable/privileged mode
    page_disable: str        # disable pagination (optional)


CISCO_COMMANDS = VendorCommands(
    name="cisco",
    list_users="show users",
    list_online="show users",
    privilege_cmd="show privilege",
    config_users="show running-config | include ^username",
    enter_enable="enable",
    page_disable="terminal length 0",
)

H3C_COMMANDS = VendorCommands(
    name="h3c",
    list_users="display local-user",
    list_online="display users",
    privilege_cmd="display user",
    config_users="display current-configuration | include local-user",
    enter_enable="super",
    page_disable="screen-length disable",
)

HUAWEI_COMMANDS = VendorCommands(
    name="huawei",
    list_users="display local-user",
    list_online="display users",
    privilege_cmd="display user",
    config_users="display current-configuration | include local-user",
    enter_enable="super",
    page_disable="screen-length 0",
)

# Generic fallback — works on any device with a CLI
GENERIC_COMMANDS = VendorCommands(
    name="generic",
    list_users="show users",
    list_online="who",
    privilege_cmd="id",
    config_users="show running-config | include username",
    enter_enable="enable",
    page_disable="terminal length 0",
)


# ──────────────────────────────────────────
#  Privilege level mappings
# ──────────────────────────────────────────

CISCO_PRIVILEGE_THRESHOLD = 15   # level 15 = full admin
H3C_HUAWEI_THRESHOLD = 3         # level 3 = admin equivalent


def _is_admin(privilege_level: int, vendor: str) -> bool:
    if vendor == "cisco":
        return privilege_level >= CISCO_PRIVILEGE_THRESHOLD
    if vendor in ("h3c", "huawei"):
        return privilege_level >= H3C_HUAWEI_THRESHOLD
    return privilege_level >= 3


# ──────────────────────────────────────────
#  Helpers
# ──────────────────────────────────────────

def _run_cmd(client: paramiko.SSHClient, cmd: str, timeout: int = 10) -> Tuple[str, str, int]:
    """Execute a command via SSH, return (stdout, stderr, exit_code)."""
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    exit_code = stdout.channel.recv_exit_status()
    out = stdout.read().decode("utf-8", errors="replace").strip()
    err = stderr.read().decode("utf-8", errors="replace").strip()
    return out, err, exit_code


def _detect_vendor(client: paramiko.SSHClient, timeout: int = 5) -> VendorCommands:
    """
    Detect network device vendor from SSH session banner or initial prompt.
    Returns the appropriate VendorCommands.
    """
    # Try reading the SSH banner
    transport = client.get_transport()
    if transport:
        banner = transport.remote_version
        banner_lower = banner.lower()
        if "cisco" in banner_lower or "ios" in banner_lower:
            logger.debug("Vendor detected from banner: Cisco")
            return CISCO_COMMANDS
        if "h3c" in banner_lower or "comware" in banner_lower:
            logger.debug("Vendor detected from banner: H3C")
            return H3C_COMMANDS
        if "huawei" in banner_lower or "vrp" in banner_lower:
            logger.debug("Vendor detected from banner: Huawei")
            return HUAWEI_COMMANDS

    # Try reading the initial CLI prompt by sending an empty line
    stdin, stdout, stderr = client.exec_command("\n", timeout=timeout)
    time.sleep(1)
    # Read whatever is available
    transport = client.get_transport()
    if transport:
        banner = transport.remote_version
        banner_lower = banner.lower()
        if "cisco" in banner_lower or "ios" in banner_lower:
            return CISCO_COMMANDS
        if "huawei" in banner_lower or "vrp" in banner_lower:
            return HUAWEI_COMMANDS
        if "h3c" in banner_lower or "comware" in banner_lower:
            return H3C_COMMANDS

    # Try prompt pattern matching from output
    for _ in range(3):
        stdin, stdout, stderr = client.exec_command("\n", timeout=timeout)
        time.sleep(0.5)
        output = stdout.read().decode("utf-8", errors="replace")
        if output:
            break

    output_lower = output.lower()
    if "cisco" in output_lower or "ios-xe" in output_lower or "nx-os" in output_lower:
        return CISCO_COMMANDS
    if "huawei" in output_lower or "vrp" in output_lower:
        return HUAWEI_COMMANDS
    if "h3c" in output_lower or "comware" in output_lower:
        return H3C_COMMANDS

    # Default to Cisco-style commands (most widely compatible)
    logger.debug("Vendor not detected, using generic commands")
    return GENERIC_COMMANDS


def _try_enable(client: paramiko.SSHClient, password: str, vendor: VendorCommands,
                timeout: int = 10) -> Tuple[bool, int]:
    """
    Attempt to enter privileged/enable mode.
    Returns (enable_success, privilege_level).
    """
    # First check current privilege level
    out, _, _ = _run_cmd(client, vendor.privilege_cmd, timeout=timeout)

    # Parse privilege level from output
    priv_level = _parse_privilege_level(out, vendor.name)

    if priv_level >= (15 if vendor.name == "cisco" else 3):
        # Already at admin level
        return True, priv_level

    # Try to enter enable mode
    if vendor.name in ("h3c", "huawei"):
        # Huawei/H3C: 'super' command
        cmd = vendor.enter_enable
    else:
        # Cisco: 'enable' command
        cmd = vendor.enter_enable

    # Send enable command
    channel = client.invoke_shell()
    channel.settimeout(timeout)

    # Clear any existing output
    time.sleep(0.3)
    if channel.recv_ready():
        channel.recv(8192)

    channel.send(cmd + "\n")
    time.sleep(0.8)

    output = ""
    while channel.recv_ready():
        output += channel.recv(4096).decode("utf-8", errors="replace")
        time.sleep(0.2)

    channel.close()

    # Check if password was requested
    if "password" in output.lower():
        # Send password
        channel2 = client.invoke_shell()
        channel2.settimeout(timeout)
        time.sleep(0.3)
        if channel2.recv_ready():
            channel2.recv(8192)
        channel2.send(password + "\n")
        time.sleep(1.0)
        output2 = ""
        while channel2.recv_ready():
            output2 += channel2.recv(4096).decode("utf-8", errors="replace")
            time.sleep(0.2)
        channel2.close()

        priv_level = _parse_privilege_level(output2, vendor.name)
        return priv_level >= (15 if vendor.name == "cisco" else 3), priv_level

    # Check current privilege after enable attempt
    out2, _, _ = _run_cmd(client, vendor.privilege_cmd, timeout=timeout)
    priv_level = _parse_privilege_level(out2, vendor.name)
    return priv_level >= (15 if vendor.name == "cisco" else 3), priv_level


def _parse_privilege_level(output: str, vendor: str) -> int:
    """Extract privilege level number from command output."""
    output_lower = output.lower()

    # Cisco: "Current privilege level is 15"
    m = re.search(r"privilege\s+(?:level\s+)?is\s+(\d+)", output_lower)
    if m:
        return int(m.group(1))

    # Cisco shorthand in prompt: (#) for admin, (>) for user
    if "#" in output:
        return 15
    if ">" in output and "#" not in output:
        return 1

    # H3C/Huawei: "Current user level is 3"
    m = re.search(r"level\s+(?:is\s+)?(\d+)", output_lower)
    if m:
        return int(m.group(1))

    # H3C/Huawei prompt: # = admin
    lines = output.split("\n")
    for line in lines[-3:]:   # check last few lines
        if ">" not in line and "#" in line:
            return 15
        if ">" in line and "#" not in line:
            return 1

    return 1  # default to user level


def _parse_cisco_users(output: str) -> List[Dict]:
    """
    Parse 'show users' output from Cisco devices.
    Format:
      Line       User       Host(s)              Idle   Location
      0 con 0    admin      idle                 00:00:00
     *2 vty 0    testuser   192.168.1.10        00:05:23 192.168.1.10
    """
    users = []
    for line in output.split("\n"):
        line = line.strip()
        # Look for lines with username patterns
        m = re.search(r"(?:con|vty|syscon)\s+\d+\s+(\S+)", line)
        if m:
            username = m.group(1)
            if username and username not in ("", "idle", "Username"):
                users.append({"username": username, "online": True})
    return users


def _parse_cisco_config_users(output: str) -> Dict[str, Dict]:
    """
    Parse 'show running-config | include username' from Cisco.
    Format: username <name> privilege <level> secret <hash>
            username <name> secret 5 <hash>
            username <name> privilege <level>
    """
    accounts: Dict[str, Dict] = {}
    for line in output.split("\n"):
        line = line.strip()
        if not line.startswith("username "):
            continue
        parts = line.split()
        if len(parts) < 3:
            continue
        # username <name> ...
        username = parts[1]
        priv_level = 1  # default
        has_secret = False

        i = 2
        while i < len(parts):
            if parts[i] == "privilege":
                try:
                    priv_level = int(parts[i + 1])
                    i += 2
                    continue
                except (IndexError, ValueError):
                    pass
            if parts[i] in ("secret", "password"):
                has_secret = True
                break
            i += 1

        accounts[username] = {
            "username": username,
            "privilege_level": priv_level,
            "enabled": has_secret,
        }
    return accounts


def _parse_h3c_huawei_users(output: str) -> List[Dict]:
    """
    Parse 'display local-user' output from H3C/Huawei.
    Format varies; we look for username lines and STATE/display fields.
    Huawei:
      User-Name  : admin
      STATE       : Active
      Privilege   : 15
      ...
    H3C:
      user name admin
        access-limit disable
        service-type ssh
        state active
        authorization-attribute level 3
    """
    users = []
    current_user = {}

    for line in output.split("\n"):
        stripped = line.strip()

        # Huawei style
        if re.match(r"User-Name\s*[:：]\s*\S+", stripped):
            if current_user:
                users.append(current_user)
            username = stripped.split(":", 1)[-1].strip()
            current_user = {"username": username, "online": False}
        elif current_user and "Privilege" in stripped or "privilege" in stripped:
            m = re.search(r"(\d+)", stripped)
            if m:
                current_user["privilege_level"] = int(m.group(1))
        elif current_user and "STATE" in stripped or "state" in stripped:
            current_user["enabled"] = "active" in stripped.lower()

        # H3C style
        elif re.match(r"user\s+name\s+\S+", stripped):
            if current_user:
                users.append(current_user)
            username = stripped.split()[-1].strip().strip('"')
            current_user = {"username": username, "online": False, "enabled": False}
        elif current_user and "state" in stripped.lower() and "active" in stripped.lower():
            current_user["enabled"] = True
        elif current_user and "authorization-attribute" in stripped.lower():
            m = re.search(r"level\s+(\d+)", stripped.lower())
            if m:
                current_user["privilege_level"] = int(m.group(1))

    if current_user:
        users.append(current_user)

    return users


def _parse_h3c_huawei_config_users(output: str) -> Dict[str, Dict]:
    """
    Parse 'display current-configuration | include local-user' from H3C/Huawei.
    Format: local-user admin
              ...
              authorization-attribute level 3
              service-type ssh
    """
    accounts: Dict[str, Dict] = {}
    current_username = None
    current_data = {}

    lines = output.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i].strip()

        # Start of a local-user block
        m = re.match(r"local-user\s+(\S+)", line)
        if m:
            if current_username:
                accounts[current_username] = current_data
            current_username = m.group(1)
            current_data = {"username": current_username, "privilege_level": 0, "enabled": False}
            i += 1
            # Read block indented under this user
            while i < len(lines):
                sub = lines[i].strip()
                if not sub or not lines[i].startswith(" "):
                    break
                sub_lower = sub.lower()
                if "state" in sub_lower and "active" in sub_lower:
                    current_data["enabled"] = True
                m2 = re.search(r"level\s+(\d+)", sub_lower)
                if m2:
                    current_data["privilege_level"] = int(m2.group(1))
                i += 1
            continue
        i += 1

    if current_username:
        accounts[current_username] = current_data

    return accounts


# ──────────────────────────────────────────
#  Main scanner
# ──────────────────────────────────────────

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
    Scan a network device (switch/router) for accounts via SSH.

    Args:
        ip: Device IP address
        port: SSH port (default 22)
        username: SSH username
        password: SSH password (or enable password)
        private_key: SSH private key content
        passphrase: Private key passphrase
        timeout: Overall timeout in seconds

    Returns:
        (ConnectionResult, List[AccountInfo])
    """
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        if private_key:
            try:
                key = paramiko.RSAKey.from_private_key(
                    object=__import__("io").StringIO(private_key),
                    password=passphrase,
                )
            except paramiko.SSHException:
                key = paramiko.Ed25519Key.from_private_key(
                    object=__import__("io").StringIO(private_key),
                    password=passphrase,
                )
            client.connect(
                hostname=ip, port=port,
                username=username, pkey=key,
                timeout=timeout, banner_timeout=15,
                auth_timeout=15,
            )
        else:
            client.connect(
                hostname=ip, port=port,
                username=username, password=password,
                timeout=timeout, banner_timeout=15,
                auth_timeout=15,
            )

    except paramiko.AuthenticationException as e:
        logger.warning("Network device auth failed %s:%s — %s", ip, port, e)
        return (ConnectionResult(success=False, error=f"认证失败: {e}", status="auth_failed"), [])

    except (paramiko.SSHException, OSError) as e:
        logger.warning("Network device connect failed %s:%s — %s", ip, port, e)
        return (ConnectionResult(success=False, error=f"连接失败: {e}", status="offline"), [])

    try:
        # Detect vendor
        vendor = _detect_vendor(client)
        logger.info("Network device %s:%s vendor=%s", ip, port, vendor.name)

        # Disable pagination
        _run_cmd(client, vendor.page_disable, timeout=5)

        # Try to elevate privilege
        enable_success, priv_level = _try_enable(client, password or "", vendor, timeout=15)

        accounts: List[AccountInfo] = []
        seen_usernames = set()

        def add_account(username: str, uid_sid_base: str, privilege_level: int,
                       enabled: bool, raw_info: dict):
            if username in seen_usernames:
                return
            seen_usernames.add(username)
            is_admin = _is_admin(privilege_level, vendor.name)
            accounts.append(AccountInfo(
                username=username,
                uid_sid=f"net://{vendor.name}:{username}",
                is_admin=is_admin,
                account_status="enabled" if enabled else "disabled",
                home_dir="",
                shell="",
                groups=[f"privilege_{privilege_level}"],
                sudo_config={
                    "vendor": vendor.name,
                    "privilege_level": privilege_level,
                    "is_admin": is_admin,
                    "enable_mode": enable_success,
                },
                last_login=None,
                raw_info=raw_info,
            ))

        # ── Method 1: Parse running-config username lines ──────────
        config_out, _, _ = _run_cmd(client, vendor.config_users, timeout=15)
        logger.debug("Config users output:\n%s", config_out[:500])

        if vendor.name == "cisco":
            config_accounts = _parse_cisco_config_users(config_out)
        else:
            config_accounts = _parse_h3c_huawei_config_users(config_out)

        for username_str, data in config_accounts.items():
            raw_info = {
                "vendor": vendor.name,
                "source": "running-config",
                "raw_line": config_out,
                "privilege_level": data.get("privilege_level", 1),
                "enabled": data.get("enabled", False),
            }
            add_account(
                username=data["username"],
                uid_sid_base=f"net://{vendor.name}:{data['username']}",
                privilege_level=data.get("privilege_level", 1),
                enabled=data.get("enabled", True),
                raw_info=raw_info,
            )

        # ── Method 2: Parse show users / display local-user ────────
        users_out, _, _ = _run_cmd(client, vendor.list_users, timeout=15)
        logger.debug("List users output:\n%s", users_out[:500])

        online_usernames: List[str] = []
        if vendor.name == "cisco":
            parsed = _parse_cisco_users(users_out)
            online_usernames = [u["username"] for u in parsed if u.get("online")]
        else:
            parsed = _parse_h3c_huawei_users(users_out)
            online_usernames = [u["username"] for u in parsed if u.get("online")]
            # Enrich existing accounts with online status
            for user_data in parsed:
                uname = user_data.get("username", "")
                if uname in config_accounts:
                    # Already added from config
                    continue
                if not uname:
                    continue
                priv_lvl = user_data.get("privilege_level", 1)
                enabled_flag = user_data.get("enabled", True)
                add_account(
                    username=uname,
                    uid_sid_base=f"net://{vendor.name}:{uname}",
                    privilege_level=priv_lvl,
                    enabled=enabled_flag,
                    raw_info={"vendor": vendor.name, "source": "display-users", "online": True},
                )

        if not accounts:
            logger.warning("No accounts found on network device %s:%s", ip, port)
            return (ConnectionResult(
                success=True, status="online",
                error="未发现任何账号（设备可能无本地用户）"
            ), [])

        logger.info("Network device %s:%s found %d accounts (%d admin)",
                    ip, port, len(accounts), sum(1 for a in accounts if a.is_admin))
        return (ConnectionResult(success=True, status="online"), accounts)

    except Exception as e:
        logger.error("Network device scan error %s:%s — %s", ip, port, e)
        return (ConnectionResult(success=False, error=f"扫描失败: {e}", status="offline"), [])

    finally:
        client.close()
