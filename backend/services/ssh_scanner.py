"""
SSH scanner service using Paramiko.
Collects account information from Linux assets via SSH.
Supports multiple distributions with layered fallback strategy.
Enhanced with: SSH key audit, Sudoers depth audit, credential file scan.
"""

import re
import io
import os
from datetime import datetime
from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Set, Dict

import paramiko
from paramiko import SSHClient, AutoAddPolicy, AuthenticationException


# ───────────────────────────────────────────────
#  Distro-specific admin group names
# ───────────────────────────────────────────────
_DISTRO_ADMIN_GROUPS: Dict[str, List[str]] = {
    "debian":     ["sudo", "admin"],
    "ubuntu":     ["sudo", "admin"],
    "linuxmint":  ["sudo"],
    "pop":        ["sudo"],
    "elementary": ["sudo"],
    "rhel":       ["wheel"],
    "centos":     ["wheel"],
    "rocky":      ["wheel"],
    "almalinux":  ["wheel"],
    "fedora":     ["wheel"],
    "suse":       ["wheel", "trusted"],
    "opensuse":   ["wheel", "trusted"],
    "leap":       ["wheel", "trusted"],
    "alpine":     ["wheel", "sudo"],
    "arch":       ["wheel", "sudo"],
    "manjaro":    ["wheel", "sudo"],
    "gentoo":     ["wheel", "sudo"],
    "freebsd":    ["wheel"],
    "default":    ["sudo", "wheel", "admin", "trusted"],
}

# Paths to scan for leaked credentials (relative to root /)
_LEAK_SCAN_PATHS = [
    "/home/*/.ssh/*.pem",
    "/home/*/.ssh/*_rsa",
    "/home/*/.ssh/id_*",
    "/home/*/.aws/credentials",
    "/home/*/.aws/config",
    "/home/*/.kube/config",
    "/home/*/.git-credentials",
    "/home/*/.netrc",
    "/home/*/.config/gcloud/*.json",
    "/root/.ssh/*.pem",
    "/root/.ssh/authorized_keys",
    "/root/.aws/credentials",
    "/root/.kube/config",
    "/tmp/*.pem",
    "/tmp/id_*",
    "/opt/*/credentials*.json",
    "/opt/*/config*.yaml",
    "/opt/*/config*.yml",
    "/etc/ssh/sshd_config",
    "/etc/ssh/ssh_config",
]


# ───────────────────────────────────────────────
#  Dataclasses
# ───────────────────────────────────────────────

@dataclass
class AccountInfo:
    username: str
    uid_sid: str
    is_admin: bool
    account_status: str  # enabled / disabled / locked / no_password / unknown
    home_dir: str
    shell: str
    groups: List[str] = field(default_factory=list)
    sudo_config: Optional[dict] = field(default_factory=None)
    last_login: Optional[datetime] = field(default=None)
    raw_info: dict = field(default_factory=dict)


@dataclass
class ConnectionResult:
    success: bool
    error: Optional[str] = None
    status: str = "offline"


@dataclass
class CredentialFinding:
    path: str
    file_type: str          # e.g. "ssh_key", "aws_creds", "kube_config"
    owner: Optional[str]   # username who owns the file
    permissions: str       # e.g. "-rw-------"
    warning: str            # human-readable warning message
    risk: str               # "critical" / "warning" / "info"


# ───────────────────────────────────────────────
#  Helpers
# ───────────────────────────────────────────────

def _run_cmd(client: SSHClient, cmd: str, timeout: int = 30) -> Tuple[str, str, int]:
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    return (
        stdout.read().decode("utf-8", errors="replace").strip(),
        stderr.read().decode("utf-8", errors="replace").strip(),
        stdout.channel.recv_exit_status(),
    )


def _detect_distro(client: SSHClient) -> str:
    """Detect Linux distribution from /etc/os-release."""
    out, _, rc = _run_cmd(client, "cat /etc/os-release 2>/dev/null || cat /etc/redhat-release 2>/dev/null || uname -s")
    if rc != 0 or not out:
        return "default"
    content = out.lower()
    m = re.search(r"^ID\s*=\s*\"?(\\w+)\"?", content, re.MULTILINE)
    if m:
        distro = m.group(1).strip()
        if distro in _DISTRO_ADMIN_GROUPS:
            return distro
        if "ubuntu" in distro: return "ubuntu"
        if "debian" in distro: return "debian"
        if "centos" in distro or "rhel" in distro or "rocky" in distro or "alma" in distro: return "rhel"
        if "suse" in distro or "opensuse" in distro or "leap" in distro: return "suse"
        if "alpine" in distro: return "alpine"
        if "arch" in distro or "manjaro" in distro: return "arch"
        if "freebsd" in distro: return "freebsd"
    if "ubuntu" in content: return "ubuntu"
    if "debian" in content: return "debian"
    if "centos" in content or "rocky" in content or "rhel" in content: return "rhel"
    if "suse" in content or "opensuse" in content: return "suse"
    if "alpine" in content: return "alpine"
    if "arch" in content or "manjaro" in content: return "arch"
    if "freebsd" in content: return "freebsd"
    return "default"


def _probe_privilege_level(client: SSHClient) -> dict:
    caps = {
        "can_read_shadow": False,
        "can_read_sudoers": False,
        "can_read_etc_sudoers_d": False,
        "can_run_sudo_l": False,
        "has_root": False,
        "can_read_other_users": False,
    }
    _, _, rc = _run_cmd(client, "cat /etc/shadow >/dev/null 2>&1")
    if rc == 0: caps["can_read_shadow"] = caps["has_root"] = True
    _, _, rc = _run_cmd(client, "cat /etc/sudoers >/dev/null 2>&1")
    if rc == 0: caps["can_read_sudoers"] = True
    _, _, rc = _run_cmd(client, "ls /etc/sudoers.d/ >/dev/null 2>&1")
    if rc == 0: caps["can_read_etc_sudoers_d"] = True
    out, _, rc = _run_cmd(client, "sudo -l 2>/dev/null || true")
    if rc == 0 and out: caps["can_run_sudo_l"] = True
    out, _, rc = _run_cmd(client, "id -u")
    if rc == 0 and out.strip() == "0": caps["has_root"] = True
    return caps


# ───────────────────────────────────────────────
#  Passwd / Shadow parsing
# ───────────────────────────────────────────────

def _parse_passwd(passwd_output: str) -> List[dict]:
    accounts = []
    for line in passwd_output.splitlines():
        if not line or line.startswith("#"):
            continue
        parts = line.split(":")
        if len(parts) < 7:
            continue
        accounts.append({
            "username": parts[0],
            "uid": parts[2],
            "gid": parts[3],
            "gecos": parts[4],
            "home": parts[5],
            "shell": parts[6],
        })
    return accounts


def _parse_shadow(shadow_output: str, usernames: set) -> dict:
    states = {}
    for line in shadow_output.splitlines():
        if not line or line.startswith("#"):
            continue
        parts = line.split(":")
        if len(parts) < 2:
            continue
        username, hash_field = parts[0], parts[1]
        if username not in usernames:
            continue
        if hash_field in ("*", "!"):
            status_val = "disabled"
        elif hash_field.startswith("!"):
            status_val = "locked"
        elif hash_field == "":
            status_val = "no_password"
        else:
            status_val = "enabled"
        states[username] = {
            "status": status_val,
            "hash_redacted": True,
            "last_changed": parts[2] if len(parts) > 2 else None,
            "max_days": parts[4] if len(parts) > 4 else None,
            "warn_days": parts[5] if len(parts) > 5 else None,
        }
    return states


# ───────────────────────────────────────────────
#  SSH Key Audit
# ───────────────────────────────────────────────

def _audit_ssh_keys(client: SSHClient, homes: dict) -> dict:
    """
    Audit authorized_keys for all users.
    Returns {username: {keys: [...], warnings: [...]}}
    """
    result = {}
    VALID_KEY_TYPES = {"ssh-rsa", "ssh-ed25519", "ecdsa-sha2-nistp256", "ssh-dss"}

    for uname, home in homes.items():
        if not home or home in ("/nonexistent", "/var/lib/empty", "/sbin/nologin", "/usr/sbin/nologin", "/bin/false"):
            continue
        result[uname] = {"keys": [], "warnings": [], "ca_config": None}

        for keyfile in (".ssh/authorized_keys", ".ssh/authorized_keys2"):
            out, _, rc = _run_cmd(client, f"cat {home}/{keyfile} 2>/dev/null || true")
            if rc != 0 or not out.strip():
                continue

            for line in out.strip().splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue

                # Parse: type base64-comment
                parts = line.split(None, 2)
                if len(parts) < 2:
                    result[uname]["warnings"].append(f"{keyfile}: 无法解析的行")
                    continue

                key_type = parts[0]
                key_data = parts[1]
                key_comment = parts[2] if len(parts) > 2 else ""

                # Get real fingerprint via ssh-keygen
                fp_out, _, fp_rc = _run_cmd(client,
                    f"echo '{key_data}' | base64 -d 2>/dev/null | ssh-keygen -lf - 2>/dev/null || true")
                fingerprint = fp_out.split()[0] if fp_rc == 0 and fp_out else key_data[:30] + "..."

                key_info = {
                    "type": key_type,
                    "fingerprint": fingerprint,
                    "comment": key_comment,
                    "file": keyfile,
                    "has_passphrase": None,  # cannot detect from public key alone
                    "key_bits": None,
                }

                # Try to detect passphrase requirement via ssh-keygen -y (prompts for passphrase)
                # Don't actually decrypt — just check if key is encrypted by trying to read it
                key_bits_out, _, _ = _run_cmd(client,
                    f"ssh-keygen -yf {home}/{keyfile} 2>&1 | head -1 || true")
                if "encrypted" in key_bits_out.lower() or "passphrase" in key_bits_out.lower():
                    key_info["has_passphrase"] = False  # can't determine, key not accessible
                elif key_bits_out:
                    key_info["key_bits"] = key_bits_out.strip()

                result[uname]["keys"].append(key_info)

                # Warnings
                if key_type not in VALID_KEY_TYPES:
                    result[uname]["warnings"].append(
                        f"{keyfile}: 非标准密钥类型 '{key_type}'"
                    )

    # Check SSH CA config
    sshd_out, _, _ = _run_cmd(client, "grep -E 'TrustedUserCAKeys|RevokedKeys|CertificateFile' /etc/ssh/sshd_config 2>/dev/null || true")
    if sshd_out.strip():
        ca_lines = [l.strip() for l in sshd_out.strip().splitlines() if l.strip() and not l.strip().startswith("#")]
        if ca_lines:
            result["_ssh_ca_config"] = {
                "raw": ca_lines,
                "has_ca_keys": any("TrustedUserCAKeys" in l for l in ca_lines),
                "has_revoked": any("RevokedKeys" in l for l in ca_lines),
            }

    return result


def _check_sudo_l(client: SSHClient) -> dict:
    """
    Run 'sudo -l' to get current user's sudo permissions.
    Returns parsed sudo -l output.
    """
    sudo_l_out, _, rc = _run_cmd(client, "sudo -l 2>/dev/null || true")
    if rc != 0 or not sudo_l_out.strip():
        return {}

    rules = []
    current_user = ""
    for line in sudo_l_out.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        # First non-blank line is usually the user info
        if not current_user and "(" in line:
            m = re.search(r"^User (\S+)", line)
            if m:
                current_user = m.group(1)
        # Parse NOPASSWD / PASSWD lines
        m = re.match(r".*?(NOPASSWD|PASSWD):\s*(.+)$", line, re.IGNORECASE)
        if m:
            password_req = m.group(1).upper() == "PASSWD"  # False = NOPASSWD
            commands = m.group(2).strip()
            rules.append({
                "password_required": password_req,
                "commands": commands,
                "all_commands": commands in ("ALL", "(ALL)", "(ALL:ALL)", "(ALL:ALL) ALL"),
            })

    return {
        "user": current_user,
        "rules": rules,
        "raw": sudo_l_out[:500],
    }


def _parse_sudoers_full(client: SSHClient) -> dict:
    """
    Deep parse of /etc/sudoers and /etc/sudoers.d/*.
    Returns {username: {rules: [...], warnings: [...]}}
    """
    all_content = []
    for path in ["/etc/sudoers"] + [f"/etc/sudoers.d/{f}" for f in
            _run_cmd(client, "ls /etc/sudoers.d/ 2>/dev/null || true")[0].splitlines()]:
        out, _, rc = _run_cmd(client, f"cat {path} 2>/dev/null || true")
        if rc == 0 and out.strip():
            all_content.append((path, out))

    users_sudo: Dict[str, dict] = {}
    for path, content in all_content:
        for line in content.splitlines():
            line_stripped = line.strip()
            if not line_stripped or line_stripped.startswith("#"):
                continue

            # Skip includes
            if line_stripped.startswith("@include") or line_stripped.startswith("#include"):
                continue

            # Skip Defaults
            if re.match(r"^Defaults\b", line_stripped):
                continue

            # Pattern: USER  HOST=(RUNAS)  TAGS: COMMANDS
            # e.g.: alice  ALL=(ALL:ALL)  ALL
            # e.g.: bob    ALL=(root) NOPASSWD: /usr/bin/systemctl restart nginx
            m = re.match(
                r"^(\S+)\s+(\S+)\s*=\s*(\([^)]+\))?\s*(NOPASSWD|PASSWD)?:?\s*(.*)$",
                line_stripped, re.IGNORECASE
            )
            if m:
                user = m.group(1)
                runas = m.group(3) or ""
                tag = (m.group(4) or "").upper()
                commands = m.group(5) or "ALL"
                nopasswd = tag == "NOPASSWD"

                user_entry = users_sudo.setdefault(user, {"rules": [], "warnings": []})
                user_entry["rules"].append({
                    "hosts": m.group(2),
                    "runas": runas,
                    "nopasswd": nopasswd,
                    "all_commands": commands.strip().upper() in ("ALL", "(ALL)", "(ALL:ALL)"),
                    "commands": commands,
                    "source": path,
                })
                if nopasswd and commands.strip().upper() == "ALL":
                    user_entry["warnings"].append(f"无密码 sudo ALL: {user} ← 高危")

    return users_sudo


# ───────────────────────────────────────────────
#  Credential File Scanner
# ───────────────────────────────────────────────

def _scan_credential_files(client: SSHClient) -> List[CredentialFinding]:
    """
    Scan filesystem for leaked credential files.
    Only reads metadata (path, owner, perms) — does NOT read file contents.
    """
    findings: List[CredentialFinding] = []

    # 1. SSH private keys (world-readable or owner-writeable)
    for pattern in [
        "/home/*/.ssh/*.pem",
        "/home/*/.ssh/id_*",
        "/root/.ssh/*.pem",
        "/root/.ssh/id_*",
        "/tmp/*.pem",
        "/tmp/id_*",
    ]:
        out, _, rc = _run_cmd(client,
            f"find {pattern} -type f 2>/dev/null || true")
        if rc != 0 or not out.strip():
            continue
        for path in out.strip().splitlines():
            perms, owner, *_ = _run_cmd(client, f"stat -c '%a %U' '{path}' 2>/dev/null || echo ''")
            if not perms:
                continue
            is_world_readable = any(p in perms for p in ["4", "6", "7"])  # r-- or rw- or rwx
            finding = CredentialFinding(
                path=path,
                file_type="ssh_private_key",
                owner=owner or None,
                permissions=perms,
                warning=(
                    "SSH 私钥文件 — 私钥泄露可直接登录任何关联服务器"
                    + ("（文件权限过松，所有人可读）" if is_world_readable else "（检查是否必要）")
                ),
                risk="critical" if is_world_readable else "warning",
            )
            findings.append(finding)

    # 2. AWS credentials
    for pattern in ["/home/*/.aws/credentials", "/root/.aws/credentials"]:
        out, _, rc = _run_cmd(client,
            f"find {pattern} -type f 2>/dev/null || true")
        if rc != 0 or not out.strip():
            continue
        for path in out.strip().splitlines():
            perms, owner, *_ = _run_cmd(client, f"stat -c '%a %U' '{path}' 2>/dev/null || echo ''")
            is_world = any(p in perms for p in ["4", "6", "7"])
            findings.append(CredentialFinding(
                path=path,
                file_type="aws_credentials",
                owner=owner or None,
                permissions=perms,
                warning="AWS 凭据文件（Access Key / Secret Key）— 泄露可直接接管云资源"
                        + ("（所有人可读！）" if is_world else ""),
                risk="critical",
            ))

    # 3. Kubernetes kubeconfig
    for pattern in ["/home/*/.kube/config", "/root/.kube/config"]:
        out, _, rc = _run_cmd(client,
            f"find {pattern} -type f 2>/dev/null || true")
        if rc != 0 or not out.strip():
            continue
        for path in out.strip().splitlines():
            perms, owner, *_ = _run_cmd(client, f"stat -c '%a %U' '{path}' 2>/dev/null || echo ''")
            is_world = any(p in perms for p in ["4", "6", "7"])
            findings.append(CredentialFinding(
                path=path,
                file_type="kubeconfig",
                owner=owner or None,
                permissions=perms,
                warning="Kubernetes kubeconfig — 泄露可接管整个集群"
                        + ("（权限过松）" if is_world else ""),
                risk="critical",
            ))

    # 4. Google Cloud service account keys
    out, _, rc = _run_cmd(client,
        "find /home /root -name '*.json' -path '*/gcloud/*' -o -name '*.json' -path '*/service_account*' 2>/dev/null | head -20")
    if rc == 0 and out.strip():
        for path in out.strip().splitlines()[:10]:
            findings.append(CredentialFinding(
                path=path,
                file_type="gcp_service_account_key",
                owner=None,
                permissions="",
                warning="GCP Service Account JSON Key — 泄露可直接调用云 API",
                risk="critical",
            ))

    # 5. authorized_keys with suspicious patterns (external keys)
    out, _, rc = _run_cmd(client,
        "grep -rh 'imported\|external\|from github\|from gitlab' /home/*/.ssh/authorized_keys /root/.ssh/authorized_keys 2>/dev/null || true")
    if out.strip():
        findings.append(CredentialFinding(
            path="/home/*/.ssh/authorized_keys (external keys found)",
            file_type="suspicious_authorized_keys",
            owner=None,
            permissions="",
            warning=f"authorized_keys 包含外部导入的密钥（可能为第三方访问通道）：{out[:200]}",
            risk="warning",
        ))

    # 6. SSH config files (check for permissive settings)
    out, _, rc = _run_cmd(client,
        "grep -rh 'StrictHostKeyChecking=no\\|PasswordAuthentication yes\\|PermitRootLogin yes\\|PubkeyAuthentication no' "
        "/etc/ssh/ssh_config /etc/ssh/sshd_config 2>/dev/null | grep -v '^#' || true")
    if out.strip():
        findings.append(CredentialFinding(
            path="/etc/ssh/sshd_config",
            file_type="sshd_config_warning",
            owner=None,
            permissions="",
            warning=f"sshd_config 存在不安全配置：{out[:200]}",
            risk="warning",
        ))

    # 7. .netrc files (legacy cleartext credential storage)
    out, _, rc = _run_cmd(client,
        "find /home /root -name '.netrc' -type f 2>/dev/null || true")
    if rc == 0 and out.strip():
        for path in out.strip().splitlines():
            findings.append(CredentialFinding(
                path=path,
                file_type="netrc",
                owner=None,
                permissions="",
                warning=".netrc 文件（明文存储 FTP/HTTP 凭据）— 建议迁移到安全凭据管理器",
                risk="warning",
            ))

    # 8. Git credentials
    out, _, rc = _run_cmd(client,
        "find /home /root -name '.git-credentials' -o -name '.gitconfig' 2>/dev/null | head -10")
    if rc == 0 and out.strip():
        for path in out.strip().splitlines():
            findings.append(CredentialFinding(
                path=path,
                file_type="git_credentials",
                owner=None,
                permissions="",
                warning="Git 凭据文件 — 泄露可能暴露代码仓库访问权限",
                risk="warning",
            ))

    return findings


# ───────────────────────────────────────────────
#  lastlog parsing
# ───────────────────────────────────────────────

def _parse_lastlog(lastlog_output: str) -> dict:
    result = {}
    for line in lastlog_output.splitlines():
        parts = line.split()
        if len(parts) >= 3:
            username = parts[0]
            date_str = " ".join(parts[-2:])
            for fmt in ("%b %d %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%a %b %d %H:%M:%S %Y"):
                try:
                    dt = datetime.strptime(date_str, fmt)
                    result[username] = dt.isoformat()
                    break
                except ValueError:
                    continue
    return result


# ───────────────────────────────────────────────
#  Group membership
# ───────────────────────────────────────────────

def _get_admin_groups_for_distro(client: SSHClient, distro: str) -> Tuple[Set[str], Set[str]]:
    """
    Get admin group membership and NOPASSWD sudo users.
    Returns (admin_members, nopasswd_users).
    """
    admin_members: Set[str] = set()
    nopasswd_users: Set[str] = set()
    groups_to_check = _DISTRO_ADMIN_GROUPS.get(distro, _DISTRO_ADMIN_GROUPS["default"])

    passwd_out, _, _ = _run_cmd(client, "cat /etc/passwd")
    usernames = []
    for line in passwd_out.splitlines():
        if not line or line.startswith("#"):
            continue
        parts = line.split(":")
        if len(parts) >= 3:
            uid = parts[2]
            if uid.isdigit() and int(uid) < 100 and uid != "0":
                continue
            usernames.append(parts[0])

    for uname in usernames:
        out, _, rc = _run_cmd(client, f"id -nG {uname} 2>/dev/null || true")
        if rc == 0 and out.strip():
            for gid_name in out.strip().split():
                if gid_name in groups_to_check:
                    admin_members.add(uname)
                    break

    group_out, _, _ = _run_cmd(client, "cat /etc/group")
    for line in group_out.splitlines():
        if not line or line.startswith("#"):
            continue
        parts = line.split(":")
        if len(parts) < 4:
            continue
        group_name = parts[0]
        if group_name in groups_to_check:
            members = parts[3].split(",")
            for m in members:
                if m.strip():
                    admin_members.add(m.strip())

    # Parse sudoers (full audit)
    users_sudo = _parse_sudoers_full(client)
    for user, entry in users_sudo.items():
        for rule in entry.get("rules", []):
            if rule["nopasswd"] and rule["all_commands"]:
                nopasswd_users.add(user)

    # sudo -l current user
    sudo_l = _check_sudo_l(client)
    for rule in sudo_l.get("rules", []):
        if rule["nopasswd"] and rule["all_commands"] and sudo_l.get("user"):
            nopasswd_users.add(sudo_l["user"])

    return admin_members, nopasswd_users


# ───────────────────────────────────────────────
#  Remote auth detection
# ───────────────────────────────────────────────

def _detect_remote_auth(client: SSHClient) -> dict:
    info = {"type": "local", "detail": None}
    nsswitch_out, _, _ = _run_cmd(client, "cat /etc/nsswitch.conf 2>/dev/null || true")
    if not nsswitch_out:
        return info
    passwd_line = re.search(r"^passwd:\s*(.+)$", nsswitch_out, re.MULTILINE)
    group_line = re.search(r"^group:\s*(.+)$", nsswitch_out, re.MULTILINE)
    passwd_sources = passwd_line.group(1).split() if passwd_line else []
    group_sources = group_line.group(1).split() if group_line else []
    if "ldap" in passwd_sources or "ldap" in group_sources:
        info = {"type": "ldap", "detail": "LDAP 认证（nsswitch.conf）"}
    elif "nis" in passwd_sources or "nis" in group_sources:
        info = {"type": "nis", "detail": "NIS 认证（nsswitch.conf）"}
    pam_out, _, _ = _run_cmd(client, "grep -r 'pam_ldap\\|pam_sss' /etc/pam.d/ 2>/dev/null || true")
    if pam_out.strip():
        info = {"type": "ldap", "detail": "LDAP/SSS 认证（PAM）"}
    return info


# ───────────────────────────────────────────────
#  Main entry point
# ───────────────────────────────────────────────

def scan_asset(
    ip: str,
    port: int,
    username: str,
    password: Optional[str] = None,
    private_key: Optional[str] = None,
    passphrase: Optional[str] = None,
    timeout: int = 30,
) -> Tuple[ConnectionResult, List[AccountInfo]]:
    """
    Main entry point: scan a Linux asset via SSH.

    Returns:
        (ConnectionResult, List[AccountInfo])

    Each AccountInfo.raw_info additionally contains:
      - ssh_key_audit: SSH authorized_keys analysis with warnings
      - credential_findings: leaked credential file warnings
      - sudoers_audit: full sudoers rule map
      - sudo_l: current user's sudo -l output
    """
    client = SSHClient()
    client.set_missing_host_key_policy(AutoAddPolicy())

    try:
        if private_key:
            key_io = io.StringIO(private_key)
            pkey = paramiko.RSAKey.from_private_key(key_io, password=passphrase) if passphrase \
                else paramiko.RSAKey.from_private_key(key_io)
            client.connect(ip, port=port, username=username, pkey=pkey,
                         timeout=timeout, look_for_keys=False)
        elif password:
            client.connect(ip, port=port, username=username, password=password,
                         timeout=timeout, look_for_keys=False)
        else:
            client.connect(ip, port=port, username=username, timeout=timeout)
    except AuthenticationException:
        return (ConnectionResult(success=False, error="认证失败", status="auth_failed"), [])
    except Exception as e:
        return (ConnectionResult(success=False, error=str(e), status="offline"), [])

    try:
        distro = _detect_distro(client)
        caps = _probe_privilege_level(client)
        remote_auth = _detect_remote_auth(client)

        passwd_out, _, _ = _run_cmd(client, "cat /etc/passwd")
        shadow_out, _, _ = _run_cmd(client, "cat /etc/shadow") if caps["can_read_shadow"] \
            else _run_cmd(client, "cat /etc/shadow 2>/dev/null || true")

        admin_members, nopasswd_users = _get_admin_groups_for_distro(client, distro)
        passwd_accounts = _parse_passwd(passwd_out)
        homes = {a["username"]: a["home"] for a in passwd_accounts}

        # ── Enhanced: SSH Key Audit ────────────────────
        ssh_key_audit = _audit_ssh_keys(client, homes)

        # ── Enhanced: Credential File Scan ────────────
        credential_findings = _scan_credential_files(client)

        # ── Enhanced: Sudoers Full Audit ──────────────
        users_sudo = _parse_sudoers_full(client)
        sudo_l = _check_sudo_l(client)

        # ── SSH CA check ───────────────────────────────
        ssh_ca = ssh_key_audit.pop("_ssh_ca_config", None)

        # lastlog
        lastlog_out, _, _ = _run_cmd(client, "lastlog -b 365 2>/dev/null || lastlog")
        if "unknown" in lastlog_out.lower() or not lastlog_out.strip():
            lastlog_out, _, _ = _run_cmd(client, "lastlog 2>/dev/null || true")
        lastlog_map = _parse_lastlog(lastlog_out)

        # who — currently logged-in users
        who_out, _, _ = _run_cmd(client, "who 2>/dev/null || true")
        who_users: set = set()
        for line in who_out.splitlines():
            parts = line.split()
            if parts:
                who_users.add(parts[0])

        # last — recent login history (last 200 entries, supplements lastlog)
        # Format: username tty from_ip day month dd HH:MM:SS [YYYY] still_running / down
        last_out, _, _ = _run_cmd(client, "last -200 2>/dev/null || true")
        last_login_by_user: dict = {}
        for line in last_out.splitlines():
            line = line.strip()
            if not line or line.startswith("wtmp") or line.startswith("boot"):
                continue
            parts = line.split()
            if len(parts) < 4:
                continue
            u = parts[0]
            if u in ("reboot", "shutdown", "runlevel"):
                continue
            # Format: username tty [from_ip] day month dd HH:MM [duration] [(year)]
            # Local:  [user, tty, tty2,        day, month, dd, HH:MM, ...]
            # Remote: [user, tty, from_ip,     day, month, dd, HH:MM, ...]
            # parts[3] is ALWAYS the day-of-week (Sat/Sun/Mon...). The only variation
            # is whether parts[2] is a tty name or an IP. Skip parts[2] only when
            # it is a dotted-quad IP address (remote session); otherwise keep parts[3].
            skip_2 = len(parts) > 2 and re.match(r"^\d+\.\d+\.\d+\.\d+$", parts[2])
            token_slice = parts[4:12] if skip_2 else parts[3:11]

            ts_parts: list = []
            for p in token_slice:
                if re.match(r"^\d+:\d+:\d+$", p):       # HH:MM:SS
                    ts_parts.append(p)
                    break                               # time found — stop
                elif re.match(r"^\d+:\d+$", p):          # HH:MM
                    ts_parts.append(p)
                    break                               # time found — stop
                elif re.match(r"^\w+$", p):               # day/month abbreviation
                    ts_parts.append(p)
                elif re.match(r"^\d+$", p):              # day number
                    ts_parts.append(p)
                else:
                    break
                # Safety: if we've somehow collected 6 tokens without hitting time, stop
                if len(ts_parts) >= 6:
                    break
            if len(ts_parts) >= 4:
                ts_str = " ".join(ts_parts[:6])
                now = datetime.now()
                for fmt in (
                    "%a %b %d %H:%M:%S %Y",   # with seconds + year
                    "%a %b %d %H:%M %Y",       # HH:MM + explicit year
                    "%a %b %d %H:%M:%S",       # HH:MM:SS no year
                    "%a %b %d %H:%M",           # HH:MM no year (most common)
                ):
                    try:
                        dt = datetime.strptime(ts_str, fmt)
                        # Fix year when not in source (strptime defaults to 1900)
                        if dt.year == 1900:
                            dt = dt.replace(year=now.year)
                            if dt > now:            # e.g. "Apr  4" during March → last year
                                dt = dt.replace(year=now.year - 1)
                        if u not in last_login_by_user:
                            last_login_by_user[u] = dt
                        break
                    except ValueError:
                        continue

        # UID_MIN
        uid_min = 1000
        login_defs_out, _, _ = _run_cmd(client, "grep UID_MIN /etc/login.defs 2>/dev/null || true")
        m = re.search(r"UID_MIN\s+(\d+)", login_defs_out)
        if m:
            uid_min = int(m.group(1))

        shadow_states = _parse_shadow(shadow_out, {a["username"] for a in passwd_accounts})

        # ── Build AccountInfo list ───────────────────
        accounts: List[AccountInfo] = []
        for acct in passwd_accounts:
            uname = acct["username"]
            uid = acct["uid"]

            try:
                uid_int = int(uid)
            except ValueError:
                uid_int = 0
            if uid_int < uid_min and uid_int != 0:
                continue

            is_admin = uname in admin_members or uname in nopasswd_users or uid == "0"
            shadow_info = shadow_states.get(uname, {})
            account_status = shadow_info.get("status", "unknown")
            if account_status == "unknown" and not caps["can_read_shadow"]:
                account_status = "unknown_no_root"

            last_login_str = lastlog_map.get(uname)
            last_login = None
            if last_login_str:
                try:
                    last_login = datetime.fromisoformat(last_login_str)
                except ValueError:
                    pass
            # Fallback: try 'last' command data if lastlog has nothing
            if not last_login and uname in last_login_by_user:
                last_login = last_login_by_user[uname]
            # Mark currently online (from 'who')
            is_online = uname in who_users

            # SSH key audit for this user
            user_key_info = ssh_key_audit.get(uname, {})
            user_keys = user_key_info.get("keys", [])
            key_warnings = user_key_info.get("warnings", [])

            # Sudoers rules for this user
            user_sudo_rules = users_sudo.get(uname, {}).get("rules", [])
            user_sudo_warnings = users_sudo.get(uname, {}).get("warnings", [])

            accounts.append(AccountInfo(
                username=uname,
                uid_sid=uid,
                is_admin=is_admin,
                account_status=account_status,
                home_dir=acct["home"],
                shell=acct["shell"],
                groups=[],
                sudo_config={
                    "in_admin_group": uname in admin_members,
                    "nopasswd_sudo": uname in nopasswd_users,
                    "distro": distro,
                    "sudo_rules": user_sudo_rules,
                    "sudo_warnings": user_sudo_warnings,
                    "sudo_l": sudo_l if sudo_l.get("user") == uname else {},
                },
                last_login=last_login,
                raw_info={
                    "gecos": acct["gecos"],
                    "gid": acct["gid"],
                    "distro": distro,
                    "privilege_level": "root" if caps["has_root"] else ("sudo" if caps["can_run_sudo_l"] else "user"),
                    "shadow_readable": caps["can_read_shadow"],
                    "remote_auth": remote_auth,
                    "account_status_source": "shadow" if shadow_info else "lastlog_fallback",
                    "currently_online": is_online,
                    "last_command_source": "lastlog" if last_login_str else ("last" if last_login else None),

                    # SSH Key Audit
                    "ssh_key_audit": {
                        "keys": user_keys,
                        "warnings": key_warnings,
                        "key_count": len(user_keys),
                        "has_external_keys": any("imported" in w.lower() or "external" in w.lower() for w in key_warnings),
                    },
                    "ssh_ca_config": ssh_ca,

                    # Credential findings (aggregated — attached to every account once)
                    # We attach a summary; full list goes in the first account only
                    "_credential_findings_summary": _summarize_findings(credential_findings),
                    "_credential_findings_count": len(credential_findings),

                    # Sudoers audit
                    "sudoers_audit": {
                        "user_rules": user_sudo_rules,
                        "user_warnings": user_sudo_warnings,
                        "all_users_with_nopasswd_all": [
                            u for u, e in users_sudo.items()
                            if any(r["nopasswd"] and r["all_commands"] for r in e.get("rules", []))
                        ],
                    },
                },
            ))

        # Attach full credential findings to the first account (avoid duplication in DB)
        if accounts and credential_findings:
            accounts[0].raw_info["credential_findings"] = [
                {"path": f.path, "type": f.file_type, "risk": f.risk, "warning": f.warning}
                for f in credential_findings
            ]

        return (ConnectionResult(success=True, status="online"), accounts)

    finally:
        client.close()


def _summarize_findings(findings: List[CredentialFinding]) -> dict:
    critical = [f for f in findings if f.risk == "critical"]
    warning = [f for f in findings if f.risk == "warning"]
    return {
        "total": len(findings),
        "critical": len(critical),
        "warning": len(warning),
        "types": list(set(f.file_type for f in findings)),
    }
