"""
Account Security Knowledge Base — CVE + MITRE ATT&CK + Security Best Practices.
"""

from typing import Optional

# ── MITRE ATT&CK — Account / Privilege Relevant Tactics ────────────────────────

ATTACK_TACTICS = [
    {
        "id": "T1078",
        "name": "Valid Accounts / 合法账号",
        "name_en": "Valid Accounts",
        "sub": "T1078.003",
        "description": "攻击者使用合法账号（本地账号或域账号）获取系统访问权限，是最常见的初始访问方式之一。",
        "description_en": "Adversaries use legitimate accounts (local or domain) to gain system access — one of the most common initial access vectors.",
        "platforms": ["Linux", "Windows", "macOS", "Cloud"],
        "indicators": ["异常时段登录", "罕见主机登录", "凭据重用"],
        "indicators_en": ["Off-hours login", "Login from rare hosts", "Credential reuse"],
        "detection": "监控异常账号登录，检测特权账号的异常访问模式，关联 SIEM 日志",
        "detection_en": "Monitor abnormal logins, detect privilege account anomalous access patterns, correlate SIEM logs",
        "mitigation": "禁用不必要的账号，定期审查特权账号，启用 MFA",
        "mitigation_en": "Disable unnecessary accounts, regularly review privileged accounts, enable MFA",
        "related_cves": ["CVE-2021-3156", "CVE-2016-6664"],
    },
    {
        "id": "T1021",
        "name": "Remote Services / 远程服务",
        "name_en": "Remote Services",
        "sub": "T1021.004",
        "description": "攻击者通过 SSH、RDP、VNC 等远程服务横向移动到其他主机。",
        "description_en": "Adversaries use SSH, RDP, VNC and other remote services to laterally move to other hosts.",
        "platforms": ["Linux", "Windows"],
        "indicators": ["跨主机 SSH 连接", "RDP 会话异常", "SSH 密钥滥用"],
        "indicators_en": ["Cross-host SSH connections", "RDP session anomalies", "SSH key abuse"],
        "detection": "检测异常时段跨资产登录，监控 SSH 密钥使用，分析 RDP 跳转路径",
        "detection_en": "Detect off-hours cross-asset logins, monitor SSH key usage, analyze RDP jump paths",
        "mitigation": "限制 SSH 密钥分发，禁用密码登录，启用双因子认证",
        "mitigation_en": "Limit SSH key distribution, disable password login, enable 2FA",
        "related_cves": [],
    },
    {
        "id": "T1068",
        "name": "Exploitation for Privilege Escalation / 权限提升利用",
        "name_en": "Exploitation for Privilege Escalation",
        "sub": None,
        "description": "攻击者利用软件漏洞（内核、sudo、服务）获取更高权限。常见利用：sudo 缓冲区溢出、本地提权漏洞。",
        "description_en": "Adversaries exploit software vulnerabilities (kernel, sudo, services) to escalate privileges. Common exploits: sudo buffer overflow, local privilege escalation.",
        "platforms": ["Linux", "Windows", "macOS"],
        "indicators": ["sudo 版本过低", "内核补丁缺失", "服务配置错误"],
        "indicators_en": ["Outdated sudo version", "Missing kernel patches", "Service misconfiguration"],
        "detection": "监控 sudo 版本，检测 SUID 文件变更，审计 CVE 补丁状态",
        "detection_en": "Monitor sudo version, detect SUID file changes, audit CVE patch status",
        "mitigation": "及时打补丁，限制 sudo 权限范围，移除不必要的 SUID 文件",
        "mitigation_en": "Patch promptly, limit sudo scope, remove unnecessary SUID files",
        "related_cves": ["CVE-2021-3156", "CVE-2022-0847"],
    },
    {
        "id": "T1059",
        "name": "Command and Scripting Interpreter / 命令和脚本解释器",
        "name_en": "Command and Scripting Interpreter",
        "sub": "T1059.004",
        "description": "攻击者通过 SSH 在远程主机上执行命令，建立远程 shell 会话。",
        "description_en": "Adversaries execute commands on remote hosts via SSH, establishing remote shell sessions.",
        "platforms": ["Linux", "Windows"],
        "indicators": ["SSH 远程命令执行", "非交互式 shell", "base64 编码命令"],
        "indicators_en": ["SSH remote command execution", "Non-interactive shell", "Base64-encoded commands"],
        "detection": "监控 SSH 远程命令参数，检测可疑的 bash/python 调用",
        "detection_en": "Monitor SSH remote command parameters, detect suspicious bash/python invocations",
        "mitigation": "限制 SSH command，禁用远程解释器，使用 privilege separation",
        "mitigation_en": "Restrict SSH commands, disable remote interpreters, use privilege separation",
        "related_cves": [],
    },
    {
        "id": "T1098",
        "name": "Account Manipulation / 账号操控",
        "name_en": "Account Manipulation",
        "sub": None,
        "description": "攻击者添加、修改、删除账号以维持持久化访问。包括添加后门账号、修改 sudoers、克隆账号。",
        "description_en": "Adversaries add, modify, or delete accounts to maintain persistence. Includes adding backdoor accounts, modifying sudoers, cloning accounts.",
        "platforms": ["Linux", "Windows", "Cloud"],
        "indicators": ["新增特权账号", "sudoers 文件变更", "账号创建时间异常"],
        "indicators_en": ["New privileged accounts", "sudoers file changes", "Abnormal account creation times"],
        "detection": "审计 /etc/passwd、/etc/shadow、sudoers 变更，监控新增账号事件",
        "detection_en": "Audit /etc/passwd, /etc/shadow, sudoers changes, monitor new account events",
        "mitigation": "启用账号变更告警，限制 sudo 权限，审计所有账号创建",
        "mitigation_en": "Enable account change alerts, limit sudo permissions, audit all account creation",
        "related_cves": [],
    },
    {
        "id": "T1556",
        "name": "Modify Authentication Process / 修改认证流程",
        "name_en": "Modify Authentication Process",
        "sub": "T1556.003",
        "description": "攻击者修改 PAM 配置或认证服务，以截获凭据或绕过认证。常见于 Linux 系统。",
        "description_en": "Adversaries modify PAM configuration or authentication services to intercept credentials or bypass authentication. Common on Linux systems.",
        "platforms": ["Linux"],
        "indicators": ["PAM 配置变更", "shadow-utils 变更", "auth.log 异常条目"],
        "indicators_en": ["PAM configuration changes", "shadow-utils changes", "Abnormal auth.log entries"],
        "detection": "监控 /etc/pam.d/ 文件变更，审计 PAM 模块加载",
        "detection_en": "Monitor /etc/pam.d/ file changes, audit PAM module loading",
        "mitigation": "锁定 PAM 配置文件，使用 file integrity monitoring",
        "mitigation_en": "Lock PAM config files, use file integrity monitoring",
        "related_cves": [],
    },
    {
        "id": "T1548",
        "name": "Abuse Elevation Control Mechanism / 滥用权限控制机制",
        "name_en": "Abuse Elevation Control Mechanism",
        "sub": "T1548.003",
        "description": "攻击者通过 sudo、服务配置错误或 Capabilities 劫持获取 root 权限。",
        "description_en": "Adversaries gain root access via sudo misconfiguration, service flaws, or Capabilities hijacking.",
        "platforms": ["Linux"],
        "indicators": ["sudo 配置错误（NOPASSWD）", "SUID root 文件过多", "Capabilities 滥用"],
        "indicators_en": ["sudo misconfiguration (NOPASSWD)", "Excessive SUID root files", "Capabilities abuse"],
        "detection": "审计 sudoers 配置，监控 SUID 文件变更，检测 Capabilities 异常",
        "detection_en": "Audit sudoers configuration, monitor SUID file changes, detect Capabilities anomalies",
        "mitigation": "最小化 sudo 权限，避免 NOPASSWD，移除不必要的 SUID",
        "mitigation_en": "Principle of least privilege for sudo, avoid NOPASSWD, remove unnecessary SUID",
        "related_cves": [],
    },
    {
        "id": "T1110",
        "name": "Brute Force / 暴力破解",
        "name_en": "Brute Force",
        "sub": "T1110.001",
        "description": "攻击者对 SSH、数据库等服务的账号进行暴力猜解，常配合密码喷洒（password spraying）使用。",
        "description_en": "Adversaries brute-force credentials for SSH, databases and other services, often combined with password spraying.",
        "platforms": ["Linux", "Windows", "Database"],
        "indicators": ["大量登录失败", "罕见账号登录尝试", "登录来源 IP 异常"],
        "indicators_en": ["High volume of login failures", "Login attempts with rare accounts", "Abnormal source IPs"],
        "detection": "监控登录失败率，设置账户锁定阈值，分析暴力猜解模式",
        "detection_en": "Monitor login failure rates, set account lockout thresholds, analyze brute force patterns",
        "mitigation": "禁用密码登录（使用密钥），启用双因子，限制登录来源 IP",
        "mitigation_en": "Disable password login (use keys), enable 2FA, restrict source IPs",
        "related_cves": [],
    },
    {
        "id": "T1005",
        "name": "Data from Local System / 本地系统数据",
        "name_en": "Data from Local System",
        "sub": None,
        "description": "攻击者获取本地系统数据，包括 /etc/passwd（账号枚举）、SSH 密钥、凭据缓存。",
        "description_en": "Adversaries harvest local system data: /etc/passwd (account enumeration), SSH keys, credential caches.",
        "platforms": ["Linux", "Windows"],
        "indicators": ["/etc/passwd 大量读取", "SSH 私钥文件访问", "凭据缓存文件读取"],
        "indicators_en": ["/etc/passwd bulk reads", "SSH private key file access", "Credential cache file reads"],
        "detection": "监控敏感文件访问，审计 ls 和 cat 命令行为",
        "detection_en": "Monitor sensitive file access, audit ls and cat command behavior",
        "mitigation": "限制敏感文件权限，禁用凭据缓存，使用 SSH agent forwarding 替代",
        "mitigation_en": "Restrict sensitive file permissions, disable credential caching, use SSH agent forwarding instead",
        "related_cves": [],
    },
    {
        "id": "T1087",
        "name": "Account Discovery / 账号发现",
        "name_en": "Account Discovery",
        "sub": "T1087.001",
        "description": "攻击者在受控主机上枚举本地账号，获取系统用户列表以寻找持久化目标。",
        "description_en": "Adversaries enumerate local accounts on compromised hosts to find persistence targets.",
        "platforms": ["Linux", "Windows"],
        "indicators": ["大量 whoami/id 命令", "/etc/passwd 读取", "net user /domain 查询"],
        "indicators_en": ["Bulk whoami/id commands", "/etc/passwd reads", "net user /domain queries"],
        "detection": "监控账号发现命令，分析命令执行上下文",
        "detection_en": "Monitor account discovery commands, analyze command execution context",
        "mitigation": "限制谁能执行账号枚举命令，启用命令日志",
        "mitigation_en": "Restrict who can run account enumeration commands, enable command logging",
        "related_cves": [],
    },
]


# ── CVE Database ───────────────────────────────────────────────────────────────

DATABASE_CVES = [
    {
        "cve": "CVE-2021-3156",
        "product": "sudo",
        "severity": "critical",
        "cvss": 7.8,
        "description": "Sudo 堆缓冲区溢出漏洞，本地用户可无需密码提权至 root。影响 sudo <= 1.9.5p2。",
        "description_en": "Sudo heap buffer overflow — local users can escalate to root without a password. Affects sudo <= 1.9.5p2.",
        "exploitability": "本地提权，无需认证",
        "exploitability_en": "Local privilege escalation, no authentication required",
        "affected_versions": "sudo 1.8.2 - 1.9.5.p1",
        "remediation": "升级 sudo 至 1.9.5p2 或更高版本；检查 /etc/sudoers 是否允许恶意配置",
        "remediation_en": "Upgrade sudo to 1.9.5p2 or higher; check /etc/sudoers for malicious configurations",
        "mitre": "T1068",
        "detection_hints": ["sudo 版本 < 1.9.5p2", "sudoers 配置包含危险规则"],
        "detection_hints_en": ["sudo version < 1.9.5p2", "sudoers config contains dangerous rules"],
    },
    {
        "cve": "CVE-2016-6664",
        "product": "MySQL",
        "severity": "critical",
        "cvss": 9.0,
        "description": "MySQL Oracle 官方版本存在远程/本地提权漏洞，可通过 SQL 注入或本地访问执行任意代码。",
        "description_en": "MySQL remote/local privilege escalation via SQL injection or local access to execute arbitrary code.",
        "exploitability": "远程（需 SQL 注入）或本地",
        "exploitability_en": "Remote (via SQL injection) or local",
        "affected_versions": "MySQL 5.5.x, 5.6.x, 5.7.x (< 5.7.15)",
        "remediation": "升级 MySQL 至 5.7.15 或 8.0+，限制 SQL 注入风险",
        "remediation_en": "Upgrade MySQL to 5.7.15 or 8.0+, limit SQL injection risk",
        "mitre": "T1078.003",
        "detection_hints": ["MySQL root 账号无密码或弱密码", "存在 MySQL 远程访问"],
        "detection_hints_en": ["MySQL root account has no password or weak password", "MySQL remote access enabled"],
    },
    {
        "cve": "CVE-2012-2122",
        "product": "MySQL",
        "severity": "high",
        "cvss": 6.9,
        "description": "MySQL 认证绕过漏洞，在特定条件下可随机概率登录任意账号。",
        "description_en": "MySQL authentication bypass — under specific conditions attackers can log in as any account with random probability.",
        "exploitability": "远程，无需认证",
        "exploitability_en": "Remote, no authentication required",
        "affected_versions": "MySQL 5.1.x - 5.5.x",
        "remediation": "升级 MySQL 至 5.5.24+，设置强 root 密码",
        "remediation_en": "Upgrade MySQL to 5.5.24+, set strong root password",
        "mitre": "T1078.003",
        "detection_hints": ["MySQL < 5.5.24", "root 无密码或弱密码"],
        "detection_hints_en": ["MySQL < 5.5.24", "root has no password or weak password"],
    },
    {
        "cve": "CVE-2022-0847",
        "product": "Linux Kernel",
        "severity": "high",
        "cvss": 7.8,
        "description": "Linux 内核脏管道（Dirty Pipe）漏洞，普通用户可提权至 root。影响 kernel 5.8+。",
        "description_en": "Linux kernel Dirty Pipe — unprivileged users can escalate to root. Affects kernel 5.8+.",
        "exploitability": "本地，需普通用户账号",
        "exploitability_en": "Local, requires regular user account",
        "affected_versions": "Linux kernel 5.8 - 5.17",
        "remediation": "升级内核至 5.16.11、5.15.25 或 5.17.3+",
        "remediation_en": "Upgrade kernel to 5.16.11, 5.15.25, or 5.17.3+",
        "mitre": "T1068",
        "detection_hints": ["内核版本 < 5.16.11", "存在特权服务账号"],
        "detection_hints_en": ["Kernel version < 5.16.11", "Privileged service accounts exist"],
    },
    {
        "cve": "CVE-2021-4034",
        "product": "polkit (pkexec)",
        "severity": "high",
        "cvss": 7.8,
        "description": "Polkit pkexec 本地提权漏洞，任何本地用户可获得 root 权限。影响所有主流 Linux 发行版。",
        "description_en": "Polkit pkexec local privilege escalation — any local user can gain root. Affects all major Linux distributions.",
        "exploitability": "本地，需普通用户账号",
        "exploitability_en": "Local, requires regular user account",
        "affected_versions": "polkit 0-120 版本",
        "remediation": "升级 polkit 至最新版本；暂时 chmod 000 /usr/bin/pkexec（生产慎用）",
        "remediation_en": "Upgrade polkit to latest version; temporarily chmod 000 /usr/bin/pkexec (use caution in production)",
        "mitre": "T1068",
        "detection_hints": ["polkit 版本过低", "存在未打补丁的 Linux 主机"],
        "detection_hints_en": ["polkit version outdated", "Unpatched Linux hosts present"],
    },
    {
        "cve": "CVE-2019-5736",
        "product": "Docker / runc",
        "severity": "critical",
        "cvss": 8.6,
        "description": "Docker 容器逃逸漏洞，容器内攻击者可通过覆盖 host 上的 runc 二进制获得 root 权限。",
        "description_en": "Docker container escape — attacker in a container can overwrite the host runc binary to gain root on the host.",
        "exploitability": "容器内，需容器写入权限",
        "exploitability_en": "Inside container, requires container write permission",
        "affected_versions": "Docker < 18.09.2, runc < 1.0.0-rc6",
        "remediation": "升级 Docker 至 18.09.2+，使用只读 rootfs，限制容器特权模式",
        "remediation_en": "Upgrade Docker to 18.09.2+, use read-only rootfs, disable privileged container mode",
        "mitre": "T1611",
        "detection_hints": ["容器以特权模式运行", "runC 版本 < 1.0.0-rc6"],
        "detection_hints_en": ["Container running in privileged mode", "runC version < 1.0.0-rc6"],
    },
    {
        "cve": "CVE-2019-10149",
        "product": "Exim",
        "severity": "critical",
        "cvss": 9.8,
        "description": "Exim 邮件服务器远程命令执行漏洞，未经认证的攻击者可在 root 权限下执行任意命令。",
        "description_en": "Exim mail server remote command execution — unauthenticated attackers can execute arbitrary commands as root.",
        "exploitability": "远程，无需认证",
        "exploitability_en": "Remote, no authentication required",
        "affected_versions": "Exim 4.87 - 4.91",
        "remediation": "升级 Exim 至 4.92+，禁用 VRFY/EXPN 命令",
        "remediation_en": "Upgrade Exim to 4.92+, disable VRFY/EXPN commands",
        "mitre": "T1021.004",
        "detection_hints": ["Exim 版本 < 4.92", "root@localhost 账号存在"],
        "detection_hints_en": ["Exim version < 4.92", "root@localhost account exists"],
    },
    {
        "cve": "CVE-2020-1472",
        "product": "Windows / Netlogon",
        "severity": "critical",
        "cvss": 10.0,
        "description": "Netlogon 特权提升漏洞（ZeroLogon），攻击者可获取域管理员权限。",
        "description_en": "Netlogon privilege elevation (ZeroLogon) — attackers can obtain domain administrator privileges.",
        "exploitability": "网络，需域账号或无认证",
        "exploitability_en": "Network, requires domain account or no auth",
        "affected_versions": "Windows Server 2008 R2 - 2019",
        "remediation": "安装 MS17-010 补丁，启用 Netlogon 强制模式",
        "remediation_en": "Apply MS17-010 patch, enable Netlogon enforcement mode",
        "mitre": "T1068",
        "detection_hints": ["Windows Server 未打 MS17-010", "域管理员账号权限过高"],
        "detection_hints_en": ["Windows Server missing MS17-010", "Domain admin accounts have excessive permissions"],
    },
    {
        "cve": "CVE-2023-32629",
        "product": "Ubuntu Linux",
        "severity": "high",
        "cvss": 7.8,
        "description": "Ubuntu 特定的内核本地提权漏洞，与 snapd 配置错误有关。",
        "description_en": "Ubuntu-specific kernel local privilege escalation related to snapd misconfiguration.",
        "exploitability": "本地，需普通用户账号",
        "exploitability_en": "Local, requires regular user account",
        "affected_versions": "Ubuntu 22.04, 23.04",
        "remediation": "升级内核至修复版本，审查 snap 配置",
        "remediation_en": "Upgrade kernel to fixed version, review snap configuration",
        "mitre": "T1068",
        "detection_hints": ["Ubuntu 内核版本过低", "snapd 服务运行"],
        "detection_hints_en": ["Ubuntu kernel version outdated", "snapd service running"],
    },
    {
        "cve": "CVE-2024-1709",
        "product": "ConnectWise ScreenConnect",
        "severity": "critical",
        "cvss": 10.0,
        "description": "远程桌面管理工具身份绕过漏洞，未授权攻击者可创建管理员账号。",
        "description_en": "Remote desktop management tool authentication bypass — unauthenticated attackers can create admin accounts.",
        "exploitability": "远程，无需认证",
        "exploitability_en": "Remote, no authentication required",
        "affected_versions": "ScreenConnect < 23.9.7",
        "remediation": "升级至 23.9.7+ 或 24.x 版本",
        "remediation_en": "Upgrade to 23.9.7+ or 24.x",
        "mitre": "T1078",
        "detection_hints": ["ScreenConnect 版本过低", "存在 ScreenConnect 服务账号"],
        "detection_hints_en": ["ScreenConnect version outdated", "ScreenConnect service accounts exist"],
    },
]


# ── Security Best Practices ────────────────────────────────────────────────────

SECURITY_PRACTICES = [
    {
        "category": "特权管理",
        "category_en": "Privilege Management",
        "title": "root 账号禁止远程登录",
        "title_en": "Prohibit root remote login",
        "principle": "SSH 禁用 root 登录可防止暴力猜解和凭证泄露攻击，是 CIS Linux Benchmark 的基本要求。",
        "principle_en": "Disabling root SSH login prevents brute-force and credential leakage attacks. A core CIS Linux Benchmark requirement.",
        "mitre_ref": "T1021.004",
        "standard": "CIS Linux Benchmark v3.0 — 5.3.2",
        "implementation": "编辑 /etc/ssh/sshd_config：PermitRootLogin no，Restart sshd",
        "implementation_en": "Edit /etc/ssh/sshd_config: PermitRootLogin no, then restart sshd",
        "verification": "grep '^PermitRootLogin' /etc/ssh/sshd_config",
        "risk_if_missing": "攻击者可直接用 root 暴力猜解密码，一旦成功即获完全控制权",
        "risk_if_missing_en": "Attackers can brute-force root directly — a successful guess grants full system control",
    },
    {
        "category": "特权管理",
        "category_en": "Privilege Management",
        "title": "禁止 NOPASSWD sudo 配置",
        "title_en": "Prohibit NOPASSWD sudo configuration",
        "principle": "NOPASSWD 允许特定账号免密提权，攻击者获取普通账号后可立即提权到 root。",
        "principle_en": "NOPASSWD allows passwordless privilege escalation — an attacker with a regular account can immediately become root.",
        "mitre_ref": "T1548.003",
        "standard": "CIS Linux Benchmark v3.0 — 5.3.3",
        "implementation": "审查 /etc/sudoers，移除所有 NOPASSWD 规则，使用密码保护的 sudo",
        "implementation_en": "Audit /etc/sudoers, remove all NOPASSWD rules, use password-protected sudo",
        "verification": "grep -r 'NOPASSWD' /etc/sudoers /etc/sudoers.d/",
        "risk_if_missing": "普通账号泄露 → 立即 root，无认证壁垒",
        "risk_if_missing_en": "Compromised regular account → instant root, no authentication barrier",
    },
    {
        "category": "特权管理",
        "category_en": "Privilege Management",
        "title": "禁止 UID 0 非 root 账号",
        "title_en": "Prohibit non-root UID 0 accounts",
        "principle": "UID 0 即 root 权限，任何 UID=0 的账号都具有完全系统控制权。",
        "principle_en": "UID 0 means root privileges. Any account with UID=0 has complete system control.",
        "mitre_ref": "T1068",
        "standard": "CIS Linux Benchmark v3.0 — 5.4.1",
        "implementation": "检查 /etc/passwd：awk -F: '($3 == 0) {print}' /etc/passwd，确保只有 root",
        "implementation_en": "Check /etc/passwd: awk -F: '($3 == 0) {print}' /etc/passwd — ensure only root",
        "verification": "getent passwd 0 | grep -v '^root:'",
        "risk_if_missing": "非 root UID 0 账号拥有完整 root 权限，绕过审计和监控",
        "risk_if_missing_en": "Non-root UID 0 accounts have full root access, bypassing auditing and monitoring",
    },
    {
        "category": "账号命名",
        "category_en": "Account Naming",
        "title": "禁止通用共享账号名",
        "title_en": "Prohibit generic shared account names",
        "principle": "admin/root/test/guest 等通用名是攻击者首要目标，易被凭证填充和暴力猜解利用。",
        "principle_en": "admin/root/test/guest are primary attacker targets, easily exploited via credential stuffing and brute force.",
        "mitre_ref": "T1078",
        "standard": "CIS Critical Security Controls — 16",
        "implementation": "命名规范要求包含部门/用途标识，如 it_admin_zhangsan",
        "implementation_en": "Naming convention must include department/usage identifier, e.g. it_admin_zhangsan",
        "verification": "awk -F: '{print $1}' /etc/passwd | grep -E '^(admin|root|test|guest|backup|daemon)$'",
        "risk_if_missing": "攻击者用常见账号名+弱密码可轻松登录，且无法追溯到具体人员",
        "risk_if_missing_en": "Attackers can login with common names + weak passwords with no individual accountability",
    },
    {
        "category": "账号命名",
        "category_en": "Account Naming",
        "title": "禁止共享账号",
        "title_en": "Prohibit shared accounts",
        "principle": "共享账号无法追溯操作责任人，违反最小权限原则。",
        "principle_en": "Shared accounts cannot trace operations to individuals and violate the principle of least privilege.",
        "mitre_ref": "T1078",
        "standard": "ISO 27001 — A.9.2.3",
        "implementation": "为每个自然人分配独立账号，服务账号需登记用途和负责人",
        "implementation_en": "Assign each person a unique account; service accounts must register purpose and owner",
        "verification": "同一账号在多个不同来源 IP 使用",
        "risk_if_missing": "无法审计操作人，合规违规，无法在人员离职时精确回收权限",
        "risk_if_missing_en": "No audit trail for operators, compliance violation, cannot precisely revoke access on departure",
    },
    {
        "category": "生命周期",
        "category_en": "Lifecycle",
        "title": "休眠账号必须禁用",
        "title_en": "Dormant accounts must be disabled",
        "principle": "长期不活跃账号被攻击者利用风险极高（无人在意/监控），离职账号同理。",
        "principle_en": "Long-inactive accounts face extreme risk of exploitation (no monitoring) — same for departed employee accounts.",
        "mitre_ref": "T1078",
        "standard": "ISO 27001 — A.9.2.5；SOC2 CC6.3",
        "implementation": "lastlogin > 30天 → 标记为休眠，> 90天 → 禁用；员工离职时立即禁用账号",
        "implementation_en": "lastlogin > 30 days → mark dormant, > 90 days → disable; disable immediately on employee departure",
        "verification": "getent passwd | check lastlogin in /var/log/lastlog; chage -l <username>",
        "risk_if_missing": "休眠离职账号可被攻击者接管，作为持久化入口",
        "risk_if_missing_en": "Dormant/departed accounts can be taken over by attackers as a persistence entry point",
    },
    {
        "category": "生命周期",
        "category_en": "Lifecycle",
        "title": "服务账号权限最小化",
        "title_en": "Service account least privilege",
        "principle": "服务账号（如 mysql、postgres、www-data）若拥有 sudo 权限，一旦被攻破将导致全面沦陷。",
        "principle_en": "Service accounts (mysql, postgres, www-data) with sudo privileges can lead to full compromise if breached.",
        "mitre_ref": "T1548.003",
        "standard": "CIS Linux Benchmark v3.0 — 5.2.6",
        "implementation": "审查服务账号的组成员资格和 sudoers 权限，仅授予最小必要权限",
        "implementation_en": "Audit service account group membership and sudoers permissions — grant only minimum necessary",
        "verification": "getent group sudo; getent group wheel; sudo -l -U <service_account>",
        "risk_if_missing": "服务账号被攻破 → 提权至 root → 横向移动",
        "risk_if_missing_en": "Service account compromised → privilege escalation to root → lateral movement",
    },
    {
        "category": "访问控制",
        "category_en": "Access Control",
        "title": "SSH 禁用密码认证，强制密钥登录",
        "title_en": "SSH: disable password auth, enforce key-based login",
        "principle": "密码认证易被暴力猜解，SSH 公钥认证更安全且可审计。",
        "principle_en": "Password authentication is vulnerable to brute-force; SSH public key auth is more secure and auditable.",
        "mitre_ref": "T1021.004",
        "standard": "CIS Linux Benchmark v3.0 — 5.3.10",
        "implementation": "/etc/ssh/sshd_config: PasswordAuthentication no, PubkeyAuthentication yes",
        "implementation_en": "/etc/ssh/sshd_config: PasswordAuthentication no, PubkeyAuthentication yes",
        "verification": "grep '^PasswordAuthentication' /etc/ssh/sshd_config",
        "risk_if_missing": "SSH 暴力猜解成为主要攻击面，常见服务账号易被猜解",
        "risk_if_missing_en": "SSH brute-force becomes the primary attack surface; common service accounts easily guessed",
    },
    {
        "category": "访问控制",
        "category_en": "Access Control",
        "title": "禁止特权账号使用公网 IP 直接访问",
        "title_en": "Prohibit privileged accounts from direct public IP access",
        "principle": "特权账号从公网直接 SSH 登录是极高风险暴露面。",
        "principle_en": "Direct SSH login for privileged accounts from the public internet is an extremely high-risk exposure.",
        "mitre_ref": "T1021.004",
        "standard": "CIS Linux Benchmark v3.0",
        "implementation": "通过跳板机/JumpServer 访问；配置 /etc/hosts.allow 和 /etc/hosts.deny",
        "implementation_en": "Access via jump server/Bastion host; configure /etc/hosts.allow and /etc/hosts.deny",
        "verification": "审计防火墙规则，确保无 0.0.0.0/0 到 22 端口的规则指向特权账号主机",
        "risk_if_missing": "公网暴露特权账号登录面，攻击者可从互联网直接暴力猜解",
        "risk_if_missing_en": "Public exposure of privileged account login surface — attackers can brute-force from the internet",
    },
    {
        "category": "审计",
        "category_en": "Auditing",
        "title": "账号变更必须审计记录",
        "title_en": "All account changes must be audited",
        "principle": "所有账号创建/修改/删除操作必须记录，用于事后溯源和合规审查。",
        "principle_en": "All account create/modify/delete operations must be logged for forensic traceability and compliance review.",
        "mitre_ref": "T1087",
        "standard": "ISO 27001 — A.12.4；SOC2 CC7.2",
        "implementation": "启用 auth.log/secure 日志，配置 auditd 规则监控 /etc/passwd、/etc/shadow、/etc/sudoers",
        "implementation_en": "Enable auth.log/secure logging, configure auditd rules: -w /etc/passwd -p wa -k identity -w /etc/shadow -p wa -k identity",
        "verification": "auditd 规则: -w /etc/passwd -p wa -k identity -w /etc/shadow -p wa -k identity",
        "risk_if_missing": "攻击者添加后门账号后无法被发现，无法通过合规审计",
        "risk_if_missing_en": "Backdoor accounts added by attackers go undetected, compliance audits fail",
    },
    {
        "category": "访问控制",
        "category_en": "Access Control",
        "title": "高风险服务账号定期轮换",
        "title_en": "Rotate high-risk service account credentials regularly",
        "principle": "数据库 root、备份账号等高风险凭据长期不更换，泄露后影响持续存在。",
        "principle_en": "Database root, backup accounts and other high-risk credentials that are never rotated continue to pose risk after any leak.",
        "mitre_ref": "T1098",
        "standard": "CIS Critical Security Controls — 16",
        "implementation": "MySQL/PostgreSQL root 密码每 90 天轮换，使用 secrets management 工具存储",
        "implementation_en": "Rotate MySQL/PostgreSQL root passwords every 90 days; use secrets management tools",
        "verification": "检查密码最后修改时间：SELECT User, host, Password_Last_Changed FROM mysql.user",
        "risk_if_missing": "长期密码泄露导致历史数据持续暴露，无法感知何时泄露",
        "risk_if_missing_en": "Long-term password leaks expose historical data indefinitely with no leak awareness",
    },
    {
        "category": "特权管理",
        "category_en": "Privilege Management",
        "title": "数据库 DBA 账号与系统账号分离",
        "title_en": "Separate database DBA accounts from OS accounts",
        "principle": "数据库 root 与 OS root 混用会扩大攻击面，一旦一面被破直接导致另一面沦陷。",
        "principle_en": "Mixing database root with OS root widens the attack surface — compromising one directly compromises the other.",
        "mitre_ref": "T1078.003",
        "standard": "等保 2.0 — 7.1.4 三权分立",
        "implementation": "数据库使用独立 DBA 账号（如 dba_zhangsan），OS 使用普通账号+sudo",
        "implementation_en": "Use dedicated DBA accounts (e.g. dba_zhangsan) for databases; regular OS accounts + sudo for system access",
        "verification": "检查 mysql.user 是否存在 root@'%'；检查 postgres pg_hba.conf 是否允许 trust 认证",
        "risk_if_missing": "数据库账号泄露 → OS root 权限；OS 账号泄露 → 数据库控制权",
        "risk_if_missing_en": "Database account leak → OS root; OS account leak → database control",
    },
]


# ── Language-aware entry helpers ───────────────────────────────────────────────

def _localize_tactic(entry: dict, lang: str = "zh") -> dict:
    if lang == "en":
        result = {k: v for k, v in entry.items() if not k.endswith("_en")}
        result["name"] = entry.get("name_en", entry["name"])
        result["description"] = entry.get("description_en", entry["description"])
        result["indicators"] = entry.get("indicators_en", entry.get("indicators", []))
        result["detection"] = entry.get("detection_en", entry["detection"])
        result["mitigation"] = entry.get("mitigation_en", entry["mitigation"])
    else:
        result = {k: v for k, v in entry.items() if not k.endswith("_en")}
    return result


def _localize_cve(entry: dict, lang: str = "zh") -> dict:
    if lang == "en":
        result = {k: v for k, v in entry.items() if not k.endswith("_en")}
        result["description"] = entry.get("description_en", entry["description"])
        result["exploitability"] = entry.get("exploitability_en", entry["exploitability"])
        result["remediation"] = entry.get("remediation_en", entry["remediation"])
        result["detection_hints"] = entry.get("detection_hints_en", entry.get("detection_hints", []))
    else:
        result = {k: v for k, v in entry.items() if not k.endswith("_en")}
    return result


def _localize_practice(entry: dict, lang: str = "zh") -> dict:
    if lang == "en":
        result = {k: v for k, v in entry.items() if not k.endswith("_en")}
        result["category"] = entry.get("category_en", entry["category"])
        result["title"] = entry.get("title_en", entry["title"])
        result["principle"] = entry.get("principle_en", entry["principle"])
        result["implementation"] = entry.get("implementation_en", entry["implementation"])
        result["risk_if_missing"] = entry.get("risk_if_missing_en", entry["risk_if_missing"])
    else:
        result = {k: v for k, v in entry.items() if not k.endswith("_en")}
    return result


# ── Utility Functions ───────────────────────────────────────────────────────────

def search_kb(query: str, limit: int = 10, lang: str = "zh",
              db=None) -> list[dict]:
    query_lower = query.lower()
    results: list[tuple[int, dict]] = []

    for entry in ATTACK_TACTICS:
        score = _score_entry(entry, query_lower)
        if score > 0:
            results.append((score, {"type": "mitre", **_localize_tactic(entry, lang)}))

    for entry in DATABASE_CVES:
        score = _score_entry(entry, query_lower)
        if score > 0:
            results.append((score, {"type": "cve", **_localize_cve(entry, lang)}))

    for entry in SECURITY_PRACTICES:
        score = _score_entry(entry, query_lower)
        if score > 0:
            results.append((score, {"type": "practice", **_localize_practice(entry, lang)}))

    # Merge DB entries
    if db is not None:
        from backend.models import KBEntry
        db_entries = db.query(KBEntry).filter(
            KBEntry.enabled == True,  # noqa: E712
        ).all()
        for entry in db_entries:
            title = entry.title_en if lang == "en" and entry.title_en else entry.title
            desc = entry.description_en if lang == "en" and entry.description_en else entry.description
            search_text = f"{title} {desc} {str(entry.extra_data)}".lower()
            score = 0
            for word in query_lower.split():
                if word in search_text:
                    score += 3
            if score > 0:
                result_dict = {
                    "type": entry.entry_type,
                    "id": entry.id,
                    "name": title,
                    "title": title,
                    "description": desc,
                    **dict(entry.extra_data or {}),
                }
                results.append((score, result_dict))

    results.sort(key=lambda x: x[0], reverse=True)
    return [_s for _, _s in results[:limit]]


def _score_entry(entry: dict, query: str) -> int:
    score = 0
    fields = [
        entry.get("description", ""), entry.get("description_en", ""),
        entry.get("title", ""), entry.get("title_en", ""),
        entry.get("name", ""), entry.get("name_en", ""),
        entry.get("product", ""), entry.get("cve", ""),
        entry.get("category", ""), entry.get("category_en", ""),
        entry.get("principle", ""), entry.get("principle_en", ""),
        str(entry.get("platforms", [])),
        str(entry.get("indicators", [])), str(entry.get("indicators_en", [])),
    ]
    for field in fields:
        field_lower = field.lower()
        for word in query.split():
            if word in field_lower:
                score += 3
        if query in field_lower:
            score += 5
    return score


def get_kb_stats(db=None) -> dict:
    stats = {
        "mitre_count": len(ATTACK_TACTICS),
        "cve_count": len(DATABASE_CVES),
        "practice_count": len(SECURITY_PRACTICES),
        "total": len(ATTACK_TACTICS) + len(DATABASE_CVES) + len(SECURITY_PRACTICES),
    }
    if db is not None:
        from backend.models import KBEntry
        stats["custom_mitre_count"] = db.query(KBEntry).filter(
            KBEntry.entry_type == "mitre", KBEntry.enabled == True  # noqa: E712
        ).count()
        stats["custom_cve_count"] = db.query(KBEntry).filter(
            KBEntry.entry_type == "cve", KBEntry.enabled == True  # noqa: E712
        ).count()
        stats["custom_practice_count"] = db.query(KBEntry).filter(
            KBEntry.entry_type == "practice", KBEntry.enabled == True  # noqa: E712
        ).count()
        stats["total"] += (stats["custom_mitre_count"] + stats["custom_cve_count"] + stats["custom_practice_count"])
    return stats


def build_rag_context(system_context: Optional[dict] = None, lang: str = "zh", db=None) -> str:
    if lang == "en":
        header_tactics = "=== MITRE ATT&CK Tactics & Techniques ==="
        header_cve = "=== CVE Database ==="
        header_practice = "=== Security Best Practices ==="
        header_context = "=== Current System Context ==="
        L = lambda k: {
            "desc": "Description", "platform": "Platform", "detect": "Detection",
            "mitigate": "Mitigation", "affect": "Affects", "fix": "Fix",
            "cat": "Category", "principle": "Principle", "standard": "Standard",
            "implement": "Implementation", "account": "Account", "uid": "UID",
            "admin": "Admin", "asset": "Asset", "os": "OS", "risk": "Risk Factors",
        }[k]

        lines = [header_tactics]
        for t in ATTACK_TACTICS:
            tid = f"{t['id']}{'.'+t['sub'] if t['sub'] else ''}"
            lines.append(
                f"[{tid}] {t.get('name_en', t['name'])}\n"
                f"  {L('desc')}: {t.get('description_en', t['description'])}\n"
                f"  {L('platform')}: {', '.join(t['platforms'])}\n"
                f"  {L('detect')}: {t.get('detection_en', t['detection'])}\n"
                f"  {L('mitigate')}: {t.get('mitigation_en', t['mitigation'])}\n"
            )
        lines.append(f"\n{header_cve}")
        for c in DATABASE_CVES:
            lines.append(
                f"[{c['cve']}] {c['product']} ({c['severity']}/CVSS {c['cvss']})\n"
                f"  {L('desc')}: {c.get('description_en', c['description'])}\n"
                f"  {L('affect')}: {c['affected_versions']}\n"
                f"  {L('fix')}: {c.get('remediation_en', c['remediation'])}\n"
            )
        lines.append(f"\n{header_practice}")
        for p in SECURITY_PRACTICES:
            lines.append(
                f"[{p.get('category_en', p['category'])}] {p.get('title_en', p['title'])}\n"
                f"  {L('principle')}: {p.get('principle_en', p['principle'])}\n"
                f"  {L('standard')}: {p['standard']}\n"
                f"  {L('implement')}: {p.get('implementation_en', p['implementation'])}\n"
            )
    else:
        lines = ["=== MITRE ATT&CK 战术与技术 ==="]
        for t in ATTACK_TACTICS:
            tid = f"{t['id']}{'.'+t['sub'] if t['sub'] else ''}"
            lines.append(
                f"[{tid}] {t['name']}\n"
                f"  描述: {t['description']}\n"
                f"  平台: {', '.join(t['platforms'])}\n"
                f"  检测: {t['detection']}\n"
                f"  缓解: {t['mitigation']}\n"
            )
        lines.append("\n=== CVE 数据库 ===")
        for c in DATABASE_CVES:
            lines.append(
                f"[{c['cve']}] {c['product']} ({c['severity']}/CVSS {c['cvss']})\n"
                f"  描述: {c['description']}\n"
                f"  影响: {c['affected_versions']}\n"
                f"  修复: {c['remediation']}\n"
            )
        lines.append("\n=== 安全最佳实践 ===")
        for p in SECURITY_PRACTICES:
            lines.append(
                f"[{p['category']}] {p['title']}\n"
                f"  原则: {p['principle']}\n"
                f"  标准: {p['standard']}\n"
                f"  实施: {p['implementation']}\n"
            )
        header_context = "=== 当前系统上下文 ==="
        L = lambda k: {
            "desc": "描述", "platform": "平台", "detect": "检测",
            "mitigate": "缓解", "affect": "影响", "fix": "修复",
            "cat": "类别", "principle": "原则", "standard": "标准",
            "implement": "实施", "account": "账号", "uid": "UID",
            "admin": "管理员", "asset": "资产", "os": "OS", "risk": "风险因子",
        }[k]

    if system_context:
        lines.append(f"\n{header_context}")
        if system_context.get("account"):
            a = system_context["account"]
            lines.append(
                f"  {L('account')}: {a.get('username')} / {L('uid')} {a.get('uid_sid')} / "
                f"{L('admin')}: {a.get('is_admin')} / Shell: {a.get('shell')}"
            )
        if system_context.get("asset"):
            asset = system_context["asset"]
            lines.append(
                f"  {L('asset')}: {asset.get('asset_code')} / {asset.get('ip')} / "
                f"{L('os')}: {asset.get('os_type')}"
            )
        if system_context.get("risk_factors"):
            lines.append(f"  {L('risk')}: {', '.join(system_context['risk_factors'])}")

    # Append custom DB entries
    if db is not None:
        from backend.models import KBEntry
        custom_entries = db.query(KBEntry).filter(KBEntry.enabled == True).all()  # noqa: E712
        if custom_entries:
            if lang == "en":
                lines.append("\n=== Custom Knowledge Base Entries ===")
                for e in custom_entries:
                    title = e.title_en or e.title
                    desc = e.description_en or e.description or ""
                    lines.append(f"[{e.entry_type.upper()}] {title}\n  {desc}")
            else:
                lines.append("\n=== 自定义知识库条目 ===")
                for e in custom_entries:
                    lines.append(f"[{e.entry_type}] {e.title}\n  {e.description or ''}")

    return "\n".join(lines)
