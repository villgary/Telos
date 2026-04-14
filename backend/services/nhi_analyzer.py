"""
NHI Analyzer — Non-Human Identity classification and risk assessment.

Sprint 1 scope:
  1. Classify each AccountSnapshot as a specific NHIType
  2. Compute NHI risk level and risk signals
  3. Upsert NHIIdentity records into the DB
  4. Populate NHI alerts for rotation_due / no_owner / critical risks
"""
import re
from datetime import datetime, timezone
from typing import Optional
from dataclasses import dataclass, field
from collections import defaultdict

from sqlalchemy.orm import Session

from backend.database import SessionLocal
from backend import models


# ─── System account name patterns ──────────────────────────────────────────────

KNOWN_SYSTEM_ACCOUNTS = frozenset({
    "root", "bin", "daemon", "adm", "sync", "shutdown", "halt",
    "mail", "news", "uucp", "operator", "games", "gopher",
    "ftp", "nfsnobody", "postgres", "mysql", "redis", "nginx",
    "apache", "httpd", "www-data", "systemd", "dbus", "polkitd",
    "sshd", "rpc", "rpcuser", "rpcbind", "nobody", "distccd",
    "vnc", "x11", "厅", "avahi", "cups", "haldaemon",
    "oprofile", "gdm", "rtkit", "saned", "usbmuxd",
})

# Human username patterns (negative signals for service accounts)
HUMAN_NAME_PATTERNS = re.compile(
    r'^[a-z][a-z0-9_]{1,20}$', re.IGNORECASE
)

# Cloud provider identity patterns
CLOUD_KEYWORDS = frozenset({
    "aws", "amazon", "azure", "gcp", "google", "alibaba", "tencent",
    "kubernetes", "k8s", "eks", "gke", "aks",
    "iam", "role", "serviceaccount",
})


# ─── Dataclasses ───────────────────────────────────────────────────────────────

@dataclass
class NHIClassification:
    nhi_type: str        # NHIType value
    nhi_level: str       # NHILevel value
    risk_score: int      # 0-100
    risk_signals: list   # [{type, detail, severity}]
    credential_types: list[str]
    has_nopasswd_sudo: bool
    rotation_due_days: Optional[int]


@dataclass
class NHIRecord:
    snapshot_id: int
    asset_id: int
    username: str
    uid_sid: Optional[str]
    hostname: Optional[str]
    ip_address: Optional[str]
    is_admin: bool
    first_seen_at: Optional[datetime]
    last_seen_at: Optional[datetime]
    raw_info: dict = field(default_factory=dict)
    sudo_config: dict = field(default_factory=dict)


# ─── Classification Engine ─────────────────────────────────────────────────────

class NHIAnalyzer:
    """
    Classifies account snapshots as NHI types and computes risk.
    """

    def __init__(self, db: Session):
        self.db = db

    # ── Step 1: Classify a single account ────────────────────────────────────

    def classify_account(self, snap: models.AccountSnapshot, asset_code: str = "") -> NHIClassification:
        """
        Classify a single AccountSnapshot into NHIType + NHILevel + risk signals.
        """
        raw = snap.raw_info or {}
        sudo = snap.sudo_config or {}
        username = snap.username.lower()
        risk_signals: list[dict] = []
        credential_types: list[str] = []

        # ── Credential type detection ───────────────────────────────────────
        if raw.get("ssh_key_audit", {}).get("keys"):
            credential_types.append("ssh_key")
        if raw.get("credential_findings"):
            credential_types.append("credential_findings")
        if sudo.get("nopasswd_sudo") or sudo.get("in_admin_group"):
            credential_types.append("sudo")
        if raw.get("password_expiry", {}).get("days_until_expiry") is not None:
            credential_types.append("password")
        if raw.get("cert_info"):
            credential_types.append("cert")

        # ── NHI Type classification ───────────────────────────────────────
        nhi_type = self._classify_type(username, snap.shell, snap.home_dir,
                                        snap.uid_sid, raw, credential_types)

        # ── Risk signals ───────────────────────────────────────────────────
        risk_signals = self._detect_risk_signals(snap, nhi_type, raw, sudo,
                                                   credential_types, asset_code)

        # ── Risk score (0-100) ─────────────────────────────────────────────
        risk_score = self._compute_risk_score(risk_signals)

        # ── NHI Level ──────────────────────────────────────────────────────
        nhi_level = self._score_to_level(risk_score)

        # ── NOPASSWD sudo ─────────────────────────────────────────────────
        has_nopasswd = bool(sudo.get("nopasswd_sudo"))

        # ── Rotation due days (rough estimate based on risk) ──────────────
        rotation_due_days = self._estimate_rotation_days(nhi_type, has_nopasswd, risk_score)

        return NHIClassification(
            nhi_type=nhi_type,
            nhi_level=nhi_level,
            risk_score=risk_score,
            risk_signals=risk_signals,
            credential_types=credential_types,
            has_nopasswd_sudo=has_nopasswd,
            rotation_due_days=rotation_due_days,
        )

    def _classify_type(
        self, username: str, shell: Optional[str], home_dir: Optional[str],
        uid_sid: str, raw: dict, credential_types: list[str],
    ) -> str:
        """
        Classify into NHIType based on username, shell, homedir, uid patterns.
        """
        # ── System account (uid < 100 or known system name) ───────────────
        if uid_sid in ("0", "1", "2", "3") or username in KNOWN_SYSTEM_ACCOUNTS:
            return "system"

        # ── Non-login shell → service or system ────────────────────────────
        if shell in ("/sbin/nologin", "/usr/sbin/nologin", "/bin/false",
                     "/bin/sync", "/sbin/shutdown", "/usr/sbin/shutdown",
                     "false", "nologin", "/usr/bin/nologin"):
            # Further classify: root-like or regular service
            if username in ("root", "Administrator"):
                return "system"
            if home_dir and any(p in home_dir for p in ("/var/", "/opt/", "/srv/",
                                                          "/nonexistent", "/nonexist",
                                                          "/usr/lib/", "/etc/")):
                return "service"
            if not home_dir:
                return "system"
            return "service"

        # ── Service-like homedir with no typical human name ────────────────
        if home_dir and any(p in home_dir for p in ("/var/", "/opt/", "/srv/",
                                                      "/nonexistent", "/nonexist")):
            return "service"

        # ── Numeric or machine-generated username ──────────────────────────
        if re.match(r'^\d+$', username):
            return "service"
        if re.match(r'^[a-z]+-\d+$', username) or re.match(r'^svc[-_]', username):
            return "service"

        # ── CI/CD pipeline patterns ─────────────────────────────────────────
        if any(k in username for k in ("runner", "actions", "pipeline", "deploy",
                                        "jenkins", "github", "gitlab", "cicd", "ci-")):
            return "cicd"

        # ── Cloud identity keywords ─────────────────────────────────────────
        if any(k in username.lower() for k in CLOUD_KEYWORDS):
            return "cloud"

        # ── API key / PAT present but no human characteristics ─────────────
        if "ssh_key" in credential_types and not HUMAN_NAME_PATTERNS.match(username):
            return "service"

        # ── No clear signals → unknown (likely human but ambiguous) ─────────
        return "unknown"

    def _detect_risk_signals(
        self, snap: models.AccountSnapshot, nhi_type: str,
        raw: dict, sudo: dict, credential_types: list[str], asset_code: str,
    ) -> list[dict]:
        """
        Generate risk signals for this NHI.
        """
        signals: list[dict] = []
        username = snap.username

        # ── P0: NOPASSWD sudo ──────────────────────────────────────────────
        if sudo.get("nopasswd_sudo"):
            signals.append({
                "type": "nopasswd_sudo",
                "detail": f"{username} has NOPASSWD sudo — privilege escalation risk",
                "severity": "critical",
                "evidence": f"sudo_config.nopasswd_sudo=true on {asset_code or snap.asset_id}",
            })

        # ── P0: Shared SSH key across assets ──────────────────────────────
        ssh_keys = raw.get("ssh_key_audit", {}).get("keys", [])
        if len(ssh_keys) > 2:
            signals.append({
                "type": "multiple_ssh_keys",
                "detail": f"{username} has {len(ssh_keys)} SSH keys — credential sprawl risk",
                "severity": "high",
                "evidence": f"ssh_key_audit.keys count={len(ssh_keys)}",
            })

        # ── P1: Critical credential findings ──────────────────────────────
        findings = raw.get("credential_findings", [])
        critical_findings = [f for f in findings if f.get("risk") == "critical"]
        if critical_findings:
            signals.append({
                "type": "credential_leak",
                "detail": f"{username} has {len(critical_findings)} critical credential findings",
                "severity": "critical",
                "evidence": f"credential_findings: {[f.get('file', '') for f in critical_findings]}",
            })

        # ── P1: SSH key world-readable ────────────────────────────────────
        world_readable = [k for k in ssh_keys
                         if k.get("file", "").startswith("/etc/ssh/")]
        if world_readable:
            signals.append({
                "type": "ssh_key_world_readable",
                "detail": f"{username} SSH key has world-readable permissions",
                "severity": "high",
                "evidence": world_readable[0].get("file", ""),
            })

        # ── P1: Admin service account ────────────────────────────────────
        if nhi_type == "service" and snap.is_admin:
            signals.append({
                "type": "privileged_service_account",
                "detail": f"Service account {username} has admin privileges",
                "severity": "high",
                "evidence": f"is_admin=true on {asset_code or snap.asset_id}",
            })

        # ── P2: No credential ever rotated (rough: raw_info has no rotation record) ──
        if "ssh_key" in credential_types and not raw.get("ssh_key_audit", {}).get("last_rotated"):
            signals.append({
                "type": "credential_never_rotated",
                "detail": f"{username} SSH key has no rotation record",
                "severity": "medium",
                "evidence": "No last_rotated timestamp in ssh_key_audit",
            })

        # ── P2: Long-lived password (if password age available) ──────────
        pwd_info = raw.get("password_expiry", {})
        days = pwd_info.get("days_until_expiry")
        if days is not None and days < 0:
            signals.append({
                "type": "password_expired",
                "detail": f"{username} password expired {abs(days)} days ago",
                "severity": "medium",
                "evidence": f"days_until_expiry={days}",
            })

        # ── P3: No owner assigned ─────────────────────────────────────────
        if snap.account_status != "deleted":
            signals.append({
                "type": "no_owner",
                "detail": f"{username} has no owner assigned — will be flagged",
                "severity": "info",
                "evidence": "owner_identity_id=null",
            })

        return signals

    def _compute_risk_score(self, signals: list[dict]) -> int:
        """
        Compute 0-100 risk score from signals.
        """
        weights = {"critical": 50, "high": 25, "medium": 10, "low": 5, "info": 1}
        score = 0
        seen_types: set[str] = set()
        for sig in signals:
            if sig["type"] in seen_types:
                continue
            score += weights.get(sig["severity"], 0)
            seen_types.add(sig["type"])
        return min(score, 100)

    def _score_to_level(self, score: int) -> str:
        if score >= 80:
            return "critical"
        elif score >= 50:
            return "high"
        elif score >= 25:
            return "medium"
        elif score >= 5:
            return "low"
        return "low"

    def _estimate_rotation_days(self, nhi_type: str, has_nopasswd: bool, risk_score: int) -> Optional[int]:
        """
        Rough rotation schedule based on type and risk.
        Returns estimated days until rotation is recommended.
        """
        if nhi_type == "system":
            return None  # System accounts may not be rotatable
        if has_nopasswd or risk_score >= 80:
            return 30   # Critical: rotate in 30 days
        elif risk_score >= 50:
            return 90
        elif risk_score >= 25:
            return 180
        return None  # No rotation needed

    # ── Step 2: Sync all snapshots → NHI identities ───────────────────────────

    def sync_all(self, asset_filter: list[int] = None) -> tuple[int, int, int]:
        """
        Scan all account snapshots, classify them, upsert NHIIdentity records.
        Returns (total_processed, nhi_count, human_count).
        """
        # Get asset codes for display
        asset_codes = {
            a.id: (a.asset_code or f"ASM-{a.id:05d}", a.ip or "")
            for a in self.db.query(models.Asset).all()
        }

        query = self.db.query(models.AccountSnapshot).filter(
            models.AccountSnapshot.deleted_at.is_(None)
        )
        if asset_filter:
            query = query.filter(models.AccountSnapshot.asset_id.in_(asset_filter))

        snapshots = query.all()
        nhi_count = 0
        human_count = 0

        for snap in snapshots:
            is_human = _is_human(snap.username)
            if is_human:
                human_count += 1
                continue

            nhi_count += 1
            classification = self.classify_account(snap)

            # Check if record already exists for this snapshot
            existing = self.db.query(models.NHIIdentity).filter(
                models.NHIIdentity.snapshot_id == snap.id
            ).first()

            asset_code, ip_addr = asset_codes.get(snap.asset_id, ("", ""))
            now = datetime.now(timezone.utc)

            if existing:
                existing.nhi_type = classification.nhi_type
                existing.nhi_level = classification.nhi_level
                existing.risk_score = classification.risk_score
                existing.risk_signals = classification.risk_signals
                existing.credential_types = classification.credential_types
                existing.has_nopasswd_sudo = classification.has_nopasswd_sudo
                existing.last_seen_at = snap.snapshot_time or now
                existing.rotation_due_days = classification.rotation_due_days
            else:
                nhi = models.NHIIdentity(
                    snapshot_id=snap.id,
                    asset_id=snap.asset_id,
                    nhi_type=classification.nhi_type,
                    nhi_level=classification.nhi_level,
                    username=snap.username,
                    uid_sid=snap.uid_sid,
                    hostname=asset_code,
                    ip_address=ip_addr,
                    is_admin=snap.is_admin,
                    credential_types=classification.credential_types,
                    has_nopasswd_sudo=classification.has_nopasswd_sudo,
                    risk_score=classification.risk_score,
                    risk_signals=classification.risk_signals,
                    first_seen_at=snap.snapshot_time or now,
                    last_seen_at=snap.snapshot_time or now,
                    rotation_due_days=classification.rotation_due_days,
                )
                self.db.add(nhi)

        self.db.commit()
        return len(snapshots), nhi_count, human_count

    # ── Step 3: Generate NHI alerts ──────────────────────────────────────────

    def generate_alerts(self) -> int:
        """
        Generate NHIAlert records for critical conditions.
        Returns count of new alerts created.
        """
        nhis = self.db.query(models.NHIIdentity).filter(
            models.NHIIdentity.is_active == True
        ).all()

        now = datetime.now(timezone.utc)
        created = 0

        for nhi in nhis:
            # Critical/high risk → create alert
            if nhi.nhi_level in ("critical", "high"):
                existing = self.db.query(models.NHIAlert).filter(
                    models.NHIAlert.nhi_id == nhi.id,
                    models.NHIAlert.status == "new",
                    models.NHIAlert.alert_type == "risk_alert",
                ).first()
                if not existing:
                    self.db.add(models.NHIAlert(
                        nhi_id=nhi.id,
                        alert_type="risk_alert",
                        level=nhi.nhi_level,
                        title=f"NHI风险: {nhi.username}",
                        message=f"非人类身份 {nhi.username} 风险等级为 {nhi.nhi_level}，风险评分 {nhi.risk_score}",
                    ))
                    created += 1

            # No owner → create alert
            if not nhi.owner_identity_id and not nhi.owner_email:
                existing = self.db.query(models.NHIAlert).filter(
                    models.NHIAlert.nhi_id == nhi.id,
                    models.NHIAlert.status == "new",
                    models.NHIAlert.alert_type == "no_owner",
                ).first()
                if not existing:
                    self.db.add(models.NHIAlert(
                        nhi_id=nhi.id,
                        alert_type="no_owner",
                        level="medium",
                        title=f"NHI无Owner: {nhi.username}",
                        message=f"非人类身份 {nhi.username} 未分配Owner，请及时认领",
                    ))
                    created += 1

        self.db.commit()
        return created


# ─── Standalone helper (mirrors identity_threat.py _is_human) ─────────────────

_HUMAN_SERVICE_PATTERNS = re.compile(
    r'^(root|bin|daemon|adm|sync|shutdown|halt|mail|news|uucp|operator|games|'
    r'gopher|ftp|nobody|nfsnobody|postgres|mysql|redis|nginx|apache|httpd|'
    r'www-data|systemd|dbus|polkitd|sshd|rpc|rpcuser|rpcbind)$'
)


def _is_human(username: str) -> bool:
    """
    Returns True if the username looks like a human (interactive) account.
    Used to filter out NHI candidates.
    """
    lower = username.lower()
    if _HUMAN_SERVICE_PATTERNS.match(lower):
        return False
    if re.match(r'^\d+$', username):
        return False
    # Service-like prefixes
    if re.match(r'^(svc|service|app|daemon|bot|guest|default|centos|ubuntu|debian|admin[a-z]?)',
                lower):
        return False
    return True


# ─── CLI entrypoint ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Run sync: python -m backend.services.nhi_analyzer
    db = SessionLocal()
    analyzer = NHIAnalyzer(db)
    total, nhi, human = analyzer.sync_all()
    alerts = analyzer.generate_alerts()
    print(f"NHI Sync complete: {total} snapshots → {nhi} NHI, {human} human. {alerts} alerts created.")
    db.close()
