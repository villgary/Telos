"""
MITRE ATT&CK TTP Mapping Service.

Maps internal threat signals to MITRE ATT&CK technique IDs with full
context: rationale, detection opportunities, severity, and confidence.

Reference: https://attack.mitre.org/
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
import logging

logger = logging.getLogger(__name__)


@dataclass
class ATTACKMapping:
    """Single signal → technique mapping."""
    signal_type: str
    attack_ids: list[str]          # all applicable IDs, e.g. ["T1552.004", "T1078.004"]
    primary_id: str                 # canonical display ID
    tactic: str                     # e.g. "TA0006" (Credential Access)
    tactic_label: str              # human-readable, e.g. "Credential Access"
    severity: str                  # critical / high / medium / low
    confidence: float             # 0.0 – 1.0
    rationale: str
    detection_opportunity: str
    remediation: str


# ─── Signal → ATT&CK Registry ─────────────────────────────────────────────────

_SIGNAL_REGISTRY: dict[str, ATTACKMapping] = {}

def _reg(
    signal_type: str,
    attack_ids: list[str],
    primary_id: str,
    tactic: str,
    tactic_label: str,
    severity: str,
    confidence: float,
    rationale: str,
    detection_opportunity: str,
    remediation: str,
) -> None:
    _SIGNAL_REGISTRY[signal_type] = ATTACKMapping(
        signal_type=signal_type,
        attack_ids=attack_ids,
        primary_id=primary_id,
        tactic=tactic,
        tactic_label=tactic_label,
        severity=severity,
        confidence=confidence,
        rationale=rationale,
        detection_opportunity=detection_opportunity,
        remediation=remediation,
    )


# ── Credential Access ──────────────────────────────────────────────────────────

_reg(
    signal_type="ssh_key_reuse",
    attack_ids=["T1552.004", "T1078.004", "T1021.004"],
    primary_id="T1552.004",
    tactic="TA0006",
    tactic_label="Credential Access",
    severity="high",
    confidence=0.95,
    rationale=(
        "Same SSH public-key fingerprint found on multiple assets. The attacker "
        "holding the corresponding private key can authenticate as that account "
        "on all those hosts without any further authentication — equivalent to "
        "credential theft (T1552.004) using a valid SSH credential (T1078.004) "
        "for lateral movement (T1021.004)."
    ),
    detection_opportunity=(
        "sshd logs (auth.log): suspicious same-key authentication from multiple "
        "source IPs within a short window; new authorized_keys entries not "
        "approved via change management."
    ),
    remediation=(
        "Rotate the shared SSH key on all affected assets; "
        "investigate how the private key was duplicated; "
        "implement SSH certificate authority (CA) to prevent key reuse."
    ),
)

_reg(
    signal_type="ssh_private_key_weak_perms",
    attack_ids=["T1552.004"],
    primary_id="T1552.004",
    tactic="TA0006",
    tactic_label="Credential Access",
    severity="critical",
    confidence=0.98,
    rationale=(
        "SSH private key readable by non-owner (mode >0600). Any local user "
        "on the host can steal the private key and authenticate as that account "
        "on any host trusting that key. Textbook T1552.004 Unsecured Credentials."
    ),
    detection_opportunity=(
        "find /home -name id_rsa -o -name id_ed25519 -perm -0040 2>/dev/null; "
        "auditd: -w ~/.ssh -p r -k ssh_key_access."
    ),
    remediation=(
        "Immediately chmod 600 on all world-readable private keys; "
        "run: find ~/.ssh -type f -exec chmod 600 {} \\;"
    ),
)

_reg(
    signal_type="credential_findings_critical",
    attack_ids=["T1003.004", "T1552"],
    primary_id="T1003.004",
    tactic="TA0006",
    tactic_label="Credential Access",
    severity="critical",
    confidence=0.90,
    rationale=(
        "Critical credential finding (e.g. world-readable /etc/shadow, "
        "credential dump artifacts) indicates OS Credential Dumping (T1003.004) "
        "or Unsecured Credentials (T1552) in progress. Attacker may already "
        "have obtained password hashes or plaintext credentials."
    ),
    detection_opportunity=(
        "auditd: -w /etc/shadow -p r -k credential_access; "
        "AIDE/FIM: detect unauthorized reads of shadow file; "
        "SIEM: detection of tools like mimikatz, LAZAGNE on endpoint."
    ),
    remediation=(
        "Isolate affected asset immediately; "
        "force password rotation for all accounts on this host; "
        "review audit logs for suspicious processes accessing /etc/shadow."
    ),
)

_reg(
    signal_type="sensitive_file_exposure",
    attack_ids=["T1552"],
    primary_id="T1552",
    tactic="TA0006",
    tactic_label="Credential Access",
    severity="high",
    confidence=0.85,
    rationale=(
        "Sensitive files (SSH configs, application config with credentials, "
        ".env files) found with insecure permissions. These are staging "
        "grounds for credential theft (T1552)."
    ),
    detection_opportunity=(
        "File integrity monitoring on /home, /root, /etc; "
        "scan for accidentally committed credentials in config files."
    ),
    remediation=(
        "Secure file permissions (chmod 600); "
        "rotate any credentials found in exposed files; "
        "add .gitignore rules to prevent future credential leaks."
    ),
)

# ── Lateral Movement ───────────────────────────────────────────────────────────

_reg(
    signal_type="auth_chain",
    attack_ids=["T1021.004", "T1550.003"],
    primary_id="T1021.004",
    tactic="TA0008",
    tactic_label="Lateral Movement",
    severity="high",
    confidence=0.80,
    rationale=(
        "authorized_keys entry with 'from=<host>' creates an SSH trust path: "
        "compromising the specified jump host grants access to the target. "
        "Classic ProxyJump lateral movement (T1021.004 SSH)."
    ),
    detection_opportunity=(
        "sshd logs: accepted key with 'from=' pattern in authorized_keys; "
        "ProxyJump configuration audit; unusual SSH connection patterns "
        "via known_hosts scanning."
    ),
    remediation=(
        "Review all authorized_keys with from= restrictions; "
        "ensure jump hosts have equivalent privilege controls as target hosts; "
        "consider removing ProxyJump capability if not business-justified."
    ),
)

_reg(
    signal_type="permission_propagation",
    attack_ids=["T1021.004", "T1078"],
    primary_id="T1021.004",
    tactic="TA0008",
    tactic_label="Lateral Movement",
    severity="high",
    confidence=0.85,
    rationale=(
        "Account on source asset can SSH to target asset (permission_propagation "
        "edge exists). Compromising the source account enables lateral movement "
        "to the target using valid credentials (T1021.004 via T1078 Valid Accounts)."
    ),
    detection_opportunity=(
        "SSH connection graph from auth.log: build adjacency of successful "
        "SSH logins; flag cross-asset SSH when source account is lower-privilege "
        "than target account."
    ),
    remediation=(
        "Implement network segmentation: restrict SSH access between trust zones; "
        "use jump servers for all privileged SSH; "
        "deploy fail2ban on SSH to rate-limit connection attempts."
    ),
)

_reg(
    signal_type="privilege_escalation_path",
    attack_ids=["T1021.004", "T1548.003", "T1078"],
    primary_id="T1021.004",
    tactic="TA0008",
    tactic_label="Lateral Movement",
    severity="critical",
    confidence=0.90,
    rationale=(
        "Multi-hop path: low-privilege account A → SSH to asset B (T1021.004) "
        "→ NOPASSWD sudo to admin account C (T1548.003). Each hop uses a "
        "valid account (T1078). The weakest link in this chain determines "
        "overall risk — often a shared or poorly-managed service account."
    ),
    detection_opportunity=(
        "SSH auth.log correlation: flag sequence of logins showing "
        "low→high privilege hop within short time window; "
        "sudo.log: detect NOPASSWD use following an SSH login."
    ),
    remediation=(
        "Break the chain at the weakest link: "
        "if NOPASSWD exists, remove it; "
        "if low-privilege account can SSH to admin host, revoke that access; "
        "deploy SSH CA to prevent unauthorized key reuse across hops."
    ),
)

_reg(
    signal_type="causal_hub",
    attack_ids=["T1021", "T1078"],
    primary_id="T1021",
    tactic="TA0008",
    tactic_label="Lateral Movement",
    severity="high",
    confidence=0.85,
    rationale=(
        "Account with high degree centrality (reaches many other accounts via "
        "permission_propagation edges). Compromising this account gives the "
        "attacker maximum lateral movement potential across the infrastructure."
    ),
    detection_opportunity=(
        "Graph centrality anomaly: flag accounts with degree > 2σ above mean; "
        "SIEM: unusual number of outgoing SSH connections from single account."
    ),
    remediation=(
        "Reduce blast radius: audit why this account has so many outgoing "
        "SSH edges; consider splitting into role-specific service accounts; "
        "add step-up authentication for SSH from this account."
    ),
)

# ── Privilege Escalation ────────────────────────────────────────────────────────

_reg(
    signal_type="nopasswd_sudo",
    attack_ids=["T1548.003"],
    primary_id="T1548.003",
    tactic="TA0004",
    tactic_label="Privilege Escalation",
    severity="critical",
    confidence=0.90,
    rationale=(
        "NOPASSWD sudo rule grants passwordless privilege escalation. "
        "Once the account is compromised (even via SSH key theft), the "
        "attacker can run 'sudo <any command>' as root without authentication. "
        "CIS Linux Benchmark v3.0 §5.3.3 explicitly flags this as T1548.003."
    ),
    detection_opportunity=(
        "auditd: -w /etc/sudoers -p wa -k sudoers_change; "
        "auth.log/sudo.log: sudo commands without password prompt; "
        "sudoers diffs between scans."
    ),
    remediation=(
        "Remove NOPASSWD: run 'sudo visudo' and remove NOPASSWD tag; "
        "replace with password-protected sudo; "
        "for automation use passwordlesssudo only for specific non-interactive commands."
    ),
)

_reg(
    signal_type="nopasswd_all_sudo",
    attack_ids=["T1548.003"],
    primary_id="T1548.003",
    tactic="TA0004",
    tactic_label="Privilege Escalation",
    severity="critical",
    confidence=0.98,
    rationale=(
        "Explicit '(ALL) NOPASSWD: ALL' rule grants unrestricted root access "
        "without any authentication. This is the most severe sudo "
        "misconfiguration — equivalent to having the root password in plain text."
    ),
    detection_opportunity=(
        "Same as nopasswd_sudo but critical severity: any sudo invocation "
        "from this account is equivalent to direct root code execution."
    ),
    remediation=(
        "CRITICAL — immediately remove the ALL NOPASSWD rule via visudo; "
        "audit who added the rule (check git history of /etc/sudoers); "
        "force re-authentication for all sudo-capable sessions."
    ),
)

_reg(
    signal_type="sudoers_wildcard",
    attack_ids=["T1548.003"],
    primary_id="T1548.003",
    tactic="TA0004",
    tactic_label="Privilege Escalation",
    severity="high",
    confidence=0.85,
    rationale=(
        "sudoers rule with wildcard command (e.g. '/usr/bin/*' or '/bin/*') "
        "allows execution of any command in that directory. Attackers use "
        "wildcards to escalate: 'sudo /usr/bin/apt-get install evil' or "
        "'sudo /bin/bash' via vim/less editor escapes."
    ),
    detection_opportunity=(
        "auditd: -w /etc/sudoers.d/ -p wa -k sudoers_change; "
        "sudo.log: commands matching wildcard patterns that include escalation tools."
    ),
    remediation=(
        "Replace wildcard rules with specific command paths; "
        "audit Cmnd_Alias definitions for editor tools (vim, less, more, nmap)."
    ),
)

_reg(
    signal_type="uid_0_non_root",
    attack_ids=["T1068", "T1548"],
    primary_id="T1068",
    tactic="TA0004",
    tactic_label="Privilege Escalation",
    severity="critical",
    confidence=0.99,
    rationale=(
        "Any account other than 'root' with UID=0 has root-equivalent privileges. "
        "This is explicitly a backdoor: T1068 (Exploitation for Privilege Escalation). "
        "CIS Linux Benchmark §5.4.1 prohibits non-root UID 0 accounts."
    ),
    detection_opportunity=(
        "getent passwd | awk -F: '($3==0)&&($1!=\"root\"){print}'; "
        "monitoring of /etc/passwd writes that add UID=0 entries."
    ),
    remediation=(
        "IMMEDIATE: change the UID of the account or lock/disable it; "
        "investigate how the UID was set to 0 (check audit logs); "
        "treat as a confirmed compromise indicator."
    ),
)

_reg(
    signal_type="in_admin_group",
    attack_ids=["T1078.003", "T1548.003"],
    primary_id="T1078.003",
    tactic="TA0001",
    tactic_label="Initial Access",
    severity="high",
    confidence=0.85,
    rationale=(
        "Membership in wheel/sudo/admin group means the account can invoke "
        "sudo. An adversary who compromises this account has immediate "
        "privilege escalation capability without exploiting any vulnerability."
    ),
    detection_opportunity=(
        "auth.log: group membership changes via usermod -aG; "
        "/etc/group file monitoring: changes to wheel/sudo/admin groups."
    ),
    remediation=(
        "Audit necessity of sudo group membership for this account; "
        "remove if not required; implement principle of least privilege."
    ),
)

# ── Initial Access / Persistence ────────────────────────────────────────────────

_reg(
    signal_type="dormant_privileged",
    attack_ids=["T1078.003"],
    primary_id="T1078.003",
    tactic="TA0001",
    tactic_label="Initial Access",
    severity="critical",
    confidence=0.85,
    rationale=(
        "Dormant account (no login >90 days) retaining privileged access is "
        "a classic adversary persistence mechanism. Legitimate monitoring "
        "coverage is low; the account provides a silent foothold."
    ),
    detection_opportunity=(
        "lastlog monitoring: dormant account performing sudo or SSH login "
        "after >90 days of inactivity; SIEM alert on dormant account activity."
    ),
    remediation=(
        "Disable the account if no longer needed; "
        "if still in use, force password rotation and increase monitoring; "
        "implement automated dormant account disable policy (90-day inactive)."
    ),
)

_reg(
    signal_type="departed_account",
    attack_ids=["T1078.003", "T1098"],
    primary_id="T1078.003",
    tactic="TA0001",
    tactic_label="Initial Access",
    severity="critical",
    confidence=0.95,
    rationale=(
        "Departed employee account (HR-departed status) still present and "
        "active. If the account was not disabled upon departure, it is a "
        "completely unmonitored privileged entry point — highest priority risk."
    ),
    detection_opportunity=(
        "HR system integration to trigger IAM deprovisioning on termination; "
        "access review triggers on account status change to 'departed'."
    ),
    remediation=(
        "IMMEDIATE: disable/lock the account; "
        "force rotation of all credentials it owns; "
        "revoke all active sessions; "
        "integrate HR system with IAM to auto-deprovision on termination."
    ),
)

_reg(
    signal_type="role_confusion",
    attack_ids=["T1078", "T1098"],
    primary_id="T1078",
    tactic="TA0001",
    tactic_label="Initial Access",
    severity="medium",
    confidence=0.70,
    rationale=(
        "Same username appears on multiple assets without UID continuity "
        "(SNADE pattern: same name, different entity). Either: "
        "(1) adversary deliberately used a legitimate-looking name to hide, "
        "(2) insider created shadow accounts for unauthorized access."
    ),
    detection_opportunity=(
        "Username entropy analysis across assets; "
        "accounts with identical names but different UIDs on same network segment; "
        "correlate with HR directory to identify unauthorized accounts."
    ),
    remediation=(
        "Investigate each cross-asset username pair for legitimate justification; "
        "require documented approval for shared service account names; "
        "decommission unrecognized accounts."
    ),
)

_reg(
    signal_type="orphan_account",
    attack_ids=["T1078.003"],
    primary_id="T1078.003",
    tactic="TA0001",
    tactic_label="Initial Access",
    severity="high",
    confidence=0.80,
    rationale=(
        "Active account with no linked human identity (orphan). "
        "Could be a legitimate service account or a shadow account created "
        "by an attacker. The absence of an owner means no accountability."
    ),
    detection_opportunity=(
        "Monthly automated review: cross-reference account_snapshots "
        "against human_identities table; "
        "flag accounts without IdentityAccount links as orphaned."
    ),
    remediation=(
        "Identify the owner of each orphan account; "
        "if no owner found within 30 days, disable the account; "
        "implement mandatory identity linking for all new privileged accounts."
    ),
)

_reg(
    signal_type="shadow_account",
    attack_ids=["T1078", "T1098"],
    primary_id="T1098",
    tactic="TA0003",
    tactic_label="Persistence",
    severity="critical",
    confidence=0.85,
    rationale=(
        "Shadow account: active account without any linked identity AND "
        "with privileged access. Classic adversary persistence mechanism "
        "that bypasses IAM and HR provisioning controls. "
        "T1098 Account Manipulation — adversary creates/maintains rogue accounts."
    ),
    detection_opportunity=(
        "Automated monthly IAM review: any privileged account (is_admin=True) "
        "without IdentityAccount link is a confirmed shadow account candidate."
    ),
    remediation=(
        "IMMEDIATE isolation and investigation: "
        "disable the account, rotate all credentials, "
        "preserve audit logs for forensic analysis, "
        "determine if this was created by insider or external attacker."
    ),
)

_reg(
    signal_type="same_name_different_entity",
    attack_ids=["T1078", "T1098"],
    primary_id="T1078",
    tactic="TA0001",
    tactic_label="Initial Access",
    severity="medium",
    confidence=0.70,
    rationale=(
        "Same username appears on different assets but UID differs. "
        "This is either legitimate (e.g., local admin accounts) or "
        "a SNADE attack where adversary creates similarly-named accounts "
        "across assets to persist without standing out."
    ),
    detection_opportunity=(
        "Periodic scan: for each username, track UID across assets; "
        "flag any UID mismatch as a potential SNADE indicator."
    ),
    remediation=(
        "Enforce consistent UID for same-named accounts via LDAP/NIS; "
        "audit the purpose of each UID variant; "
        "if unrecognizable, treat as adversarial and disable."
    ),
)

_reg(
    signal_type="new_privileged_account",
    attack_ids=["T1078.003", "T1098"],
    primary_id="T1078.003",
    tactic="TA0001",
    tactic_label="Initial Access",
    severity="high",
    confidence=0.80,
    rationale=(
        "New privileged account (is_admin=True, added since last baseline) "
        "may indicate an adversary establishing persistence (T1078) or "
        "an insider creating a backdoor account (T1098)."
    ),
    detection_opportunity=(
        "Diff between current and previous scan: flag all is_admin=True "
        "accounts not present in baseline; "
        "cross-reference with approved change tickets."
    ),
    remediation=(
        "Verify against approved account creation request; "
        "if unauthorized, disable and investigate; "
        "implement PAM workflow for all privileged account creation."
    ),
)

_reg(
    signal_type="behavior_similar",
    attack_ids=["T1078"],
    primary_id="T1078",
    tactic="TA0001",
    tactic_label="Initial Access",
    severity="medium",
    confidence=0.65,
    rationale=(
        "Accounts with highly similar SSH key comments (purpose annotations) "
        "across assets suggest coordinated credential staging by a single actor. "
        "Could indicate a legitimate shared service account or adversarial "
        "campaign using scripted deployment of SSH keys."
    ),
    detection_opportunity=(
        "NLP-based clustering of SSH key comments; "
        "flag groups of >3 accounts with >80% comment similarity "
        "that are not documented as shared service accounts."
    ),
    remediation=(
        "Audit the purpose of each similar key comment group; "
        "if undocumented shared key, require documented justification; "
        "if unauthorized, rotate the shared key and review access logs."
    ),
)

_reg(
    signal_type="temporal_similarity",
    attack_ids=["T1078.003"],
    primary_id="T1078.003",
    tactic="TA0001",
    tactic_label="Initial Access",
    severity="medium",
    confidence=0.60,
    rationale=(
        "Accounts active at nearly identical times across different assets "
        "suggest either legitimate automation or a compromised operator "
        "using a hopping pattern. When associated with a departed/dormant "
        "account, confidence in adversarial intent rises significantly."
    ),
    detection_opportunity=(
        "UEBA: simultaneous login events from single identity across "
        "multiple hosts within a narrow time window; "
        "correlation with jump-host usage patterns."
    ),
    remediation=(
        "If unexpected automation pattern: investigate the service/process "
        "generating the simultaneous sessions; "
        "if adversary: isolate all affected accounts and rotate credentials."
    ),
)

# ── Semiotics: Account Obfuscation ──────────────────────────────────────────────

_reg(
    signal_type="char_substitution",
    attack_ids=["T1036"],
    primary_id="T1036",
    tactic="TA0005",
    tactic_label="Defense Evasion",
    severity="medium",
    confidence=0.75,
    rationale=(
        "Username contains character substitution (e.g. l→1, 0→O, rn→m). "
        "Substitution obfuscation (T1036.004 Masquerading: Hindering Correlation) "
        "is used to evade detection rules that look for known account names."
    ),
    detection_opportunity=(
        "Account name normalization: detect 'l33t speak' username variants; "
        "SIEM: correlate renamed account activity with original account baseline; "
        "UEBA: flag sudden de-leet username corrections."
    ),
    remediation=(
        "Identify the legitimate account this mimics; "
        "if unauthorized: disable and investigate; "
        "if legitimate: rename to standard format to reduce detection noise."
    ),
)

_reg(
    signal_type="deliberate_anonymization",
    attack_ids=["T1078", "T1098"],
    primary_id="T1078",
    tactic="TA0001",
    tactic_label="Initial Access",
    severity="high",
    confidence=0.80,
    rationale=(
        "Common/human name (e.g. admin, test, user) with privileged access. "
        "Deliberate use of anonymous-looking names for privileged accounts "
        "hides them from casual review — T1078 Valid Accounts used for "
        "persistence and lateral movement."
    ),
    detection_opportunity=(
        "Privileged account naming policy: flag privileged accounts whose "
        "names match common wordlists; monthly review of admin group membership "
        "filtered by name entropy score."
    ),
    remediation=(
        "Rename to descriptive service account naming convention; "
        "document ownership; enforce PAM approval workflow for privileged access."
    ),
)

_reg(
    signal_type="symbolic_imitation",
    attack_ids=["T1078", "T1036"],
    primary_id="T1078",
    tactic="TA0001",
    tactic_label="Initial Access",
    severity="medium",
    confidence=0.70,
    rationale=(
        "Username mimics an existing legitimate account name via suffix/variant "
        "(e.g. admin_backup, admin_test). Adversary creates lookalike accounts "
        "(T1036.003 Masquerading: Hypervisor) to blend with legitimate service "
        "accounts and evade detection."
    ),
    detection_opportunity=(
        "Username similarity scoring (Levenshtein distance < 3) against known "
        "service accounts; SIEM: alert on new accounts with names >70% similar "
        "to existing privileged accounts."
    ),
    remediation=(
        "Investigate the purpose of mimic account; "
        "if unauthorized: disable and rotate any credentials it holds; "
        "enforce naming conventions with automation to prevent future creation."
    ),
)

_reg(
    signal_type="naming_style_drift",
    attack_ids=["T1036"],
    primary_id="T1036",
    tactic="TA0005",
    tactic_label="Defense Evasion",
    severity="low",
    confidence=0.55,
    rationale=(
        "Username character distribution (digit/special char ratio) deviates "
        "significantly from same-asset baseline. Anomalous naming style may "
        "indicate account obfuscation (T1036) or automated account creation "
        "by adversary tooling."
    ),
    detection_opportunity=(
        "Statistical anomaly detection on username character distributions; "
        "SIEM: correlate anomalous naming with other IOCs (new SSH keys, "
        "unusual login times)."
    ),
    remediation=(
        "If automated tooling suspected: audit creation process; "
        "enforce naming policy compliance for all new accounts."
    ),
)

_reg(
    signal_type="suspicious_account",
    attack_ids=["T1078"],
    primary_id="T1078",
    tactic="TA0001",
    tactic_label="Initial Access",
    severity="high",
    confidence=0.80,
    rationale=(
        "Account exhibits multiple anomalous features simultaneously "
        "(combined classification as suspicious). Multiple evasion indicators "
        "together strongly suggest a T1078 Valid Accounts threat actor account."
    ),
    detection_opportunity=(
        "Composite anomaly scoring: flag accounts with 3+ simultaneous "
        "anomaly indicators; prioritize for immediate investigation."
    ),
    remediation=(
        "IMMEDIATE: isolate the account and rotate all credentials; "
        "perform forensic analysis of account activity; "
        "treat as confirmed adversary presence until proven otherwise."
    ),
)

# ── Cognitive: Detection Blindspots ─────────────────────────────────────────────

_reg(
    signal_type="confirmation_bias",
    attack_ids=["T1098", "T1078"],
    primary_id="T1098",
    tactic="TA0003",
    tactic_label="Persistence",
    severity="high",
    confidence=0.80,
    rationale=(
        "Service account (classified as non-human) configured with interactive "
        "shell (bash/zsh) AND sudo privileges AND no recent login. "
        "This configuration bypasses mental model filters: operators assume "
        "service accounts are monitored. Adversaries use this blindspot for "
        "persistence via T1098 Account Manipulation."
    ),
    detection_opportunity=(
        "PAM: audit all accounts with interactive shell AND is_admin=True; "
        "flag service accounts (non-/bin/false, non-/usr/sbin/nologin) with sudo; "
        "monitor service accounts from unusual source IPs."
    ),
    remediation=(
        "Restrict service account shells to /usr/sbin/nologin or /bin/false; "
        "remove sudo for accounts that do not need it; "
        "implement session recording for all interactive service account logins."
    ),
)

_reg(
    signal_type="halo_effect",
    attack_ids=["T1078", "T1068"],
    primary_id="T1078",
    tactic="TA0001",
    tactic_label="Initial Access",
    severity="high",
    confidence=0.85,
    rationale=(
        "Common name (admin/test/user) or UID=0 non-root account has privileged "
        "access. The halo effect causes security reviewers to overlook these "
        "accounts as 'normal'. Adversaries exploit this bias — T1078 Valid "
        "Accounts and T1068 Exploitation for Privilege Escalation from a "
        "trusted-looking account."
    ),
    detection_opportunity=(
        "Privileged account audit filtered by common name list; "
        "getent passwd | awk -F: '($3==0)&&($1!=\"root\")'; "
        "automated alert on UID=0 additions outside of approved change windows."
    ),
    remediation=(
        "Rename common-name privileged accounts to descriptive service names; "
        "remove UID=0 from non-root accounts immediately; "
        "enforce least-privilege: audit every admin account against business justification."
    ),
)

_reg(
    signal_type="sunk_cost",
    attack_ids=["T1078.003"],
    primary_id="T1078.003",
    tactic="TA0001",
    tactic_label="Initial Access",
    severity="medium",
    confidence=0.75,
    rationale=(
        "Dormant or departed account retains privileged access. "
        "Sunk cost bias prevents IT from disabling 'historical' accounts. "
        "Dormant privileged accounts are the #1 initial access vector in "
        "incident response findings — classic T1078 Valid Accounts."
    ),
    detection_opportunity=(
        "Automated lifecycle policy: disable accounts with no login in 90 days; "
        "HR-triggered immediate disable on employee departure; "
        "monthly privileged access review (PAR) to catch retention drift."
    ),
    remediation=(
        "Apply automated lifecycle: 30-day dormant → flag for review; "
        "90-day dormant → auto-disable; "
        "HR departure → immediate revoke via IAM integration."
    ),
)

_reg(
    signal_type="social_proof_anomaly",
    attack_ids=["T1548.003"],
    primary_id="T1548.003",
    tactic="TA0004",
    tactic_label="Privilege Escalation",
    severity="medium",
    confidence=0.75,
    rationale=(
        "Account is the minority in its peer group (same sudo group) with "
        "NOPASSWD capability while most peers do not. The social proof anomaly "
        "suggests this account was specifically configured to be an exception — "
        "a classic backdoor configuration for T1548.003 privilege escalation."
    ),
    detection_opportunity=(
        "Group-based sudo audit: flag any account with NOPASSWD in a group "
        "where <30% of members have NOPASSWD; "
        "SUDO_LOG monitoring: correlate NOPASSWD invocations with anomaly scores."
    ),
    remediation=(
        "Remove NOPASSWD from the minority account immediately; "
        "if automation requires NOPASSWD: document and limit to specific commands; "
        "audit who granted the exception and review for malicious intent."
    ),
)

_reg(
    signal_type="normalcy_bias",
    attack_ids=["T1562", "T1078"],
    primary_id="T1562",
    tactic="TA0005",
    tactic_label="Defense Evasion",
    severity="low",
    confidence=0.65,
    rationale=(
        "Privileged account has no login history — likely unmonitored by "
        "UEBA/log-based detection. Normalcy bias causes operators to deprioritize "
        "accounts that 'never log in' — but adversaries deliberately use "
        "dormant privileged credentials to avoid detection (T1562 Impair Defenses)."
    ),
    detection_opportunity=(
        "UEBA: alert on first-ever login from a privileged account; "
        "file integrity monitoring on SSH keys and sudo configurations "
        "for accounts with no login activity."
    ),
    remediation=(
        "Force password/key rotation for all privileged accounts with no login history; "
        "implement session recording (auditd, BPF) for privileged account logins; "
        "monitor first-ever login events as high-priority alerts."
    ),
)

# ── Causal: Graph-Based ────────────────────────────────────────────────────────

_reg(
    signal_type="dormant_privilege_chain",
    attack_ids=["T1078.003", "T1078"],
    primary_id="T1078.003",
    tactic="TA0001",
    tactic_label="Initial Access",
    severity="critical",
    confidence=0.90,
    rationale=(
        "Dormant account (no login >90 days) retains access to privileged "
        "target assets. Adversary has established a silent persistence channel: "
        "reactivates the dormant account to perform recon or lateral movement "
        "without triggering new-account alerts. T1078 Valid Accounts persistence."
    ),
    detection_opportunity=(
        "Login anomaly: alert when a dormant account (last_login >90 days) "
        "performs any authentication event; "
        "compare dormant account activity against documented maintenance windows."
    ),
    remediation=(
        "IMMEDIATE: disable dormant account; "
        "if business justification exists: force credential rotation and "
        "implement time-bound access windows; "
        "automate dormancy detection and apply 30/60/90-day lifecycle policy."
    ),
)

# ── Anthropology: Identity & Trust ───────────────────────────────────────────────

_reg(
    signal_type="trust_chain_high_risk",
    attack_ids=["T1021.004", "T1078"],
    primary_id="T1021.004",
    tactic="TA0008",
    tactic_label="Lateral Movement",
    severity="high",
    confidence=0.85,
    rationale=(
        "Account can laterally reach 5+ privileged targets via SSH trust "
        "paths (shared SSH keys, authorized_keys, group membership). "
        "Compromising this account provides broad blast radius for "
        "T1021.004 Lateral Movement using T1078 Valid Accounts."
    ),
    detection_opportunity=(
        "SSH trust graph analysis: compute reachability from each privileged "
        "account; flag accounts with lateral reach to >5 privileged hosts; "
        "SIEM: alert on SSH connections from high-centrality accounts to "
        "new target assets."
    ),
    remediation=(
        "Reduce blast radius: audit why this account has so many SSH targets; "
        "implement SSH CA instead of shared keys; "
        "network-level controls: restrict SSH between trust zones."
    ),
)

_reg(
    signal_type="permission_cluster_mix",
    attack_ids=["T1078", "T1098"],
    primary_id="T1078",
    tactic="TA0001",
    tactic_label="Initial Access",
    severity="medium",
    confidence=0.70,
    rationale=(
        "Permission cluster mixes human-named and service-named accounts "
        "with identical/similar privilege profiles. Human accounts in a "
        "service-account cluster may be compromised or intentionally hidden "
        "among legitimate service accounts — T1078 Valid Accounts."
    ),
    detection_opportunity=(
        "Privilege cluster analysis: flag human-named accounts that cluster "
        "with service accounts by SSH key pattern; "
        "UEBA: human account with service-account behavior (cron, systemd, no TTY)."
    ),
    remediation=(
        "Investigate human accounts within service clusters: "
        "verify business justification; "
        "if unexplained: disable and rotate credentials."
    ),
)

_reg(
    signal_type="identity_isolation",
    attack_ids=["T1078.003", "T1098"],
    primary_id="T1098",
    tactic="TA0003",
    tactic_label="Persistence",
    severity="high",
    confidence=0.85,
    rationale=(
        "Privileged account has no linked human identity — no owner accountability. "
        "Identity isolation is the #1 enabler of shadow accounts: adversaries "
        "create privileged accounts with no owner link to evade IAM controls. "
        "T1098 Account Manipulation — adversary creates/maintains rogue accounts."
    ),
    detection_opportunity=(
        "Identity linkage audit: every privileged account must have an "
        "IdentityAccount link; automated monthly review of unlinked privileged accounts; "
        "PAM workflow: block creation of privileged accounts without owner assignment."
    ),
    remediation=(
        "IMMEDIATE: assign an owner to every privileged account; "
        "if no owner found within 7 days: disable the account; "
        "enforce PAM workflow: no privileged account without owner approval."
    ),
)

_reg(
    signal_type="permission_bridge",
    attack_ids=["T1021.004", "T1021"],
    primary_id="T1021.004",
    tactic="TA0008",
    tactic_label="Lateral Movement",
    severity="medium",
    confidence=0.75,
    rationale=(
        "Privileged account is a bridge connecting otherwise-separated "
        "account groups (components). Compromising this account enables "
        "cross-component lateral movement that would otherwise be impossible. "
        "Classic T1021.004 SSH-based lateral movement choke-point."
    ),
    detection_opportunity=(
        "Graph bridge detection: run betweenness centrality on permission graph; "
        "flag nodes with betweenness > 2σ above mean as bridges; "
        "treat bridges as Tier-0 assets requiring MFA and session recording."
    ),
    remediation=(
        "Apply Tier-0 controls to bridge accounts: MFA for all SSH sessions, "
        "session recording, jump server requirement; "
        "split clusters with additional network-level segmentation to reduce bridge risk."
    ),
)


# ── Public API ──────────────────────────────────────────────────────────────────

def get_mapping(signal_type: str) -> Optional[ATTACKMapping]:
    """Look up ATT&CK mapping for a signal type. Returns None if unknown."""
    return _SIGNAL_REGISTRY.get(signal_type)


def get_all_mappings() -> dict[str, ATTACKMapping]:
    """Return the full registry as a dict."""
    return dict(_SIGNAL_REGISTRY)


def enrich_signal(sig: dict) -> dict:
    """
    Enrich an internal threat signal dict with ATT&CK metadata.
    Mutates and returns the same dict.
    Signals without a MITRE ATT&CK mapping are logged and still returned.
    """
    sig_type = sig.get("type", "")
    mapping = _SIGNAL_REGISTRY.get(sig_type)
    if not mapping:
        logger.debug(
            "Signal type '%s' has no MITRE ATT&CK mapping — "
            "add entry to _SIGNAL_REGISTRY in mitre_mapping.py", sig_type
        )
        return sig

    # Boost severity based on ATT&CK severity
    severity_order = {"low": 0, "medium": 1, "high": 2, "critical": 3}
    current = severity_order.get(sig.get("severity", "low"), 0)
    mapped = severity_order.get(mapping.severity, 0)
    if mapped > current:
        sig["severity"] = mapping.severity

    sig["mitre_id"] = mapping.primary_id
    sig["mitre_ids"] = mapping.attack_ids
    sig["mitre_tactic"] = mapping.tactic
    sig["mitre_tactic_label"] = mapping.tactic_label
    sig["mitre_confidence"] = mapping.confidence
    sig["mitre_rationale"] = mapping.rationale
    sig["mitre_detection_opportunity"] = mapping.detection_opportunity
    sig["mitre_remediation"] = mapping.remediation
    return sig


def enrich_signal_list(signals: list[dict]) -> list[dict]:
    """Batch version of enrich_signal."""
    return [enrich_signal(sig) for sig in signals]


# ─── ATT&CK Navigator Layer File Export ─────────────────────────────────────────

def export_attack_nav_layer(signals: list[dict], analysis_id: int) -> dict:
    """
    Export signals as a MITRE ATT&CK Navigator layer JSON.
    Compatible with https://mitre-attack.github.io/attack-navigator/

    The layer shows:
      - techniques (cells) = which ATT&CK IDs are active in this analysis
      - color = severity (red=critical, orange=high, yellow=medium, green=low)
      - metadata = confidence, rationale per technique
    """
    technique_scores: dict[str, dict] = {}

    for sig in signals:
        mapping = _SIGNAL_REGISTRY.get(sig.get("type", ""))
        if not mapping:
            continue
        for tech_id in mapping.attack_ids:
            # Take the worst (highest severity + lowest confidence = most risk)
            if tech_id not in technique_scores:
                technique_scores[tech_id] = {
                    "technique_id": tech_id,
                    "score": 0,
                    "min_confidence": 1.0,
                    "signals": [],
                    "severity": "none",
                }
            entry = technique_scores[tech_id]
            sev_score = {"low": 1, "medium": 2, "high": 3, "critical": 4}.get(mapping.severity, 0)
            entry["score"] = max(entry["score"], sev_score)
            entry["min_confidence"] = min(entry["min_confidence"], mapping.confidence)
            entry["severity"] = mapping.severity if sev_score > {"low": 1, "medium": 2, "high": 3, "critical": 4}.get(entry["severity"], 0) else entry["severity"]
            entry["signals"].append({
                "type": sig.get("type"),
                "detail": sig.get("detail"),
                "username": sig.get("username"),
            })

    # Map score 1-4 to navigator color
    color_map = {4: "red", 3: "orange", 2: "yellow", 1: "#00ff00"}
    # Technique ID → display name (MITRE ATT&CK v16)
    TECHNIQUE_NAMES = {
        "T1021": "Remote Services",
        "T1021.004": "Remote SSH",
        "T1036": "Masquerading",
        "T1036.004": "Masquerade Task or Service",
        "T1078": "Valid Accounts",
        "T1078.003": "Valid Accounts: Cloud Accounts",
        "T1078.004": "Valid Accounts: SAML Accounts",
        "T1098": "Account Manipulation",
        "T1548": "Abuse Elevation Control Mechanism",
        "T1548.003": "Sudo and Sudo Caching",
        "T1550": "Use Alternate Authentication Material",
        "T1550.003": "SSH Hijacking",
        "T1552": "Unsecured Credentials",
        "T1552.004": "Unsecured Credentials: SSH Credentials",
        "T1003.004": "OS Credential Dumping: LSA Secrets",
    }
    cells = []
    for tech_id, entry in technique_scores.items():
        color = color_map.get(entry["score"], "#ffffff")
        cells.append({
            "techniqueID": tech_id,
            "name": TECHNIQUE_NAMES.get(tech_id, ""),
            "score": entry["score"] * 25,  # 0-100 scale
            "color": color,
            "comment": (
                f"{len(entry['signals'])} signal(s). "
                f"Confidence: {entry['min_confidence']:.0%}. "
                f"Evidence: {', '.join(s.get('detail','')[:60] for s in entry['signals'][:3])}"
            ),
        })

    return {
        "name": f"ITDR Analysis #{analysis_id}",
        "versions": {"attack": "16"},
        "domain": "enterprise-attack",
        "description": f"Identity Threat Detection — Analysis #{analysis_id}",
        "filters": {"platforms": ["Linux", "macOS", "Windows"]},
        "sorting": 0,
        "layout": {"layout": "side", "aggregateFunction": "average"},
        "hideDisabled": False,
        "techniques": cells,
        "gradient": {
            "colors": ["#ffffff", "#ff6666"],
            "minValue": 0,
            "maxValue": 100,
        },
    }
