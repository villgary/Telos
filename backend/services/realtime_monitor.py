from __future__ import annotations

"""
Real-time threat monitor — runs every 5 minutes via APScheduler.

Detects new anomalies by comparing the latest scan snapshot against
the previously stored baseline snapshot, and creates Alert records.

Detections:
  1. New privileged account (is_admin=True was False last scan)
  2. New NOPASSWD sudo grant
  3. Credential findings appeared (critical risk)
  4. Dormant account became active
  5. Orphan (unlinked) account detected — shadow account signal
"""

import logging
from datetime import datetime, timezone, timedelta

from sqlalchemy import select, and_
from sqlalchemy.orm import Session

from backend import models
from backend.models import AlertLevel
from backend.database import SessionLocal

logger = logging.getLogger(__name__)


def _naive(dt: datetime) -> datetime:
    """Strip timezone info for naive-datetime comparisons."""
    if dt is None:
        return None
    if dt.tzinfo is not None:
        return dt.replace(tzinfo=None) - dt.utcoffset()
    return dt


class RealtimeMonitor:
    """Check for new anomalies and write alerts."""

    def check_and_alert(self, db: Session) -> int:
        """
        Run all anomaly detectors. Returns number of alerts created.
        Called every 5 minutes by APScheduler.
        """
        created = 0
        created += self._detect_new_privileges(db)
        created += self._detect_nopasswd_added(db)
        created += self._detect_credential_findings(db)
        created += self._detect_dormant_reactivated(db)
        created += self._detect_orphan_accounts(db)
        return created

    # ── Detector helpers ──────────────────────────────────────────────────────────

    def _create_alert(
        self,
        db: Session,
        asset_id: int,
        level: AlertLevel,
        title: str,
        message: str,
        job_id: int | None = None,
        snapshot_id: int | None = None,
        title_key: str | None = None,
        title_params: dict | None = None,
        message_key: str | None = None,
        message_params: dict | None = None,
    ) -> models.Alert:
        """Write an alert to DB. Returns the alert record."""
        alert = models.Alert(
            asset_id=asset_id,
            level=level,
            title=title,
            message=message,
            job_id=job_id,
            title_key=title_key,
            title_params=title_params,
            message_key=message_key,
            message_params=message_params,
        )
        db.add(alert)
        db.flush()  # ensure alert.id is populated before playbook triggering
        # Trigger any matching auto-playbooks
        self._trigger_matching_playbooks(alert, db, snapshot_id)
        return alert

    def _trigger_matching_playbooks(
        self,
        alert: models.Alert,
        db: Session,
        snapshot_id: int | None = None,
    ) -> int:
        """
        Find all enabled playbooks with trigger_type='alert' whose trigger_filter
        matches the given alert, and create pending PlaybookExecution records.

        Returns number of executions created.
        """
        if snapshot_id is None:
            snap = self._get_latest_snapshot_by_asset(db, alert.asset_id)
            snapshot_id = snap.id if snap else None

        if snapshot_id is None:
            logger.debug("No snapshot_id for alert %d — skipping playbook matching", alert.id)
            return 0

        playbooks = db.query(models.ReviewPlaybook).filter(
            models.ReviewPlaybook.trigger_type == "alert",
            models.ReviewPlaybook.enabled == True,
        ).all()

        created = 0
        for pb in playbooks:
            filter_spec = pb.trigger_filter or {}
            # Match by level (alert.level must be >= filter level)
            filter_level = filter_spec.get("level")
            if filter_level:
                severity_order = {"info": 0, "warning": 1, "high": 2, "critical": 3}
                alert_level_val = severity_order.get(alert.level.value, 0)
                required_val = severity_order.get(filter_level, 99)
                if alert_level_val < required_val:
                    continue

            # Match by keyword in title or message
            keyword = filter_spec.get("keyword", "")
            if keyword:
                text = (alert.title + " " + alert.message).lower()
                if keyword.lower() not in text:
                    continue

            # Match by explicit type field
            alert_type = filter_spec.get("type", "")
            if alert_type:
                if alert_type.lower() not in alert.title.lower() and alert_type.lower() not in alert.message.lower():
                    continue

            # All filter conditions passed — create execution
            execution = models.PlaybookExecution(
                playbook_id=pb.id,
                snapshot_id=snapshot_id,
                status="pending_approval" if pb.approval_required else "executing",
                triggered_by=None,
            )
            db.add(execution)
            db.flush()  # ensure execution.id is populated for logging
            created += 1
            logger.info(
                "Alert %d matched playbook '%s' (id=%d) — execution #%d created (status=%s)",
                alert.id, pb.name, pb.id, execution.id, execution.status,
            )

        return created

    def _latest_job_for_asset(self, db: Session, asset_id: int) -> models.ScanJob | None:
        return (
            db.query(models.ScanJob)
            .filter(
                models.ScanJob.asset_id == asset_id,
                models.ScanJob.status == models.ScanJobStatus.success,
            )
            .order_by(models.ScanJob.started_at.desc())
            .first()
        )

    def _get_latest_snapshot_by_asset(
        self, db: Session, asset_id: int,
    ) -> models.AccountSnapshot | None:
        return (
            db.query(models.AccountSnapshot)
            .filter(
                models.AccountSnapshot.asset_id == asset_id,
                models.AccountSnapshot.deleted_at.is_(None),
            )
            .order_by(models.AccountSnapshot.snapshot_time.desc())
            .first()
        )

    def _get_previous_snapshot(
        self, db: Session, asset_id: int, current_id: int,
    ) -> models.AccountSnapshot | None:
        return (
            db.query(models.AccountSnapshot)
            .filter(
                models.AccountSnapshot.asset_id == asset_id,
                models.AccountSnapshot.id != current_id,
                models.AccountSnapshot.deleted_at.is_(None),
            )
            .order_by(models.AccountSnapshot.snapshot_time.desc())
            .first()
        )

    # ── 1. New privileged account ──────────────────────────────────────────────

    def _detect_new_privileges(self, db: Session) -> int:
        """Alert when is_admin flips from False → True since last scan."""
        created = 0
        latest_by_asset = (
            db.query(
                models.AccountSnapshot.asset_id,
                models.AccountSnapshot.id,
            )
            .filter(models.AccountSnapshot.deleted_at.is_(None))
            .distinct(models.AccountSnapshot.asset_id)
            .order_by(
                models.AccountSnapshot.asset_id,
                models.AccountSnapshot.snapshot_time.desc(),
            )
            .all()
        )

        for asset_id, latest_id in latest_by_asset:
            prev = self._get_previous_snapshot(db, asset_id, latest_id)
            if not prev:
                continue

            prev_admin_ids = set(
                db.query(models.AccountSnapshot.username)
                .filter(
                    models.AccountSnapshot.asset_id == asset_id,
                    models.AccountSnapshot.id.in_([prev.id]),
                    models.AccountSnapshot.is_admin == True,  # noqa: E712
                )
                .scalars()
                .all()
            )

            latest = self._get_latest_snapshot_by_asset(db, asset_id)
            latest_admins = set(
                db.query(models.AccountSnapshot.username)
                .filter(
                    models.AccountSnapshot.asset_id == asset_id,
                    models.AccountSnapshot.id == latest.id,
                    models.AccountSnapshot.is_admin == True,  # noqa: E712
                )
                .scalars()
                .all()
            )

            new_admins = latest_admins - prev_admin_ids
            for username in new_admins:
                alert = self._create_alert(
                    db, asset_id, AlertLevel.high,
                    f"账号「{username}」新增管理权限",
                    f"资产 #{asset_id} 上的账号「{username}」在本次扫描中变为管理员权限，请确认是否经授权。",
                    job_id=self._latest_job_for_asset(db, asset_id).id
                    if self._latest_job_for_asset(db, asset_id)
                    else None,
                    snapshot_id=latest.id,
                    title_key="alert.admin_privilege_added",
                    title_params={"username": username},
                    message_key="alert.msg.admin_privilege_added",
                    message_params={"username": username, "asset_id": asset_id},
                )
                created += 1
                logger.info("Alert: new admin %s on asset %s", username, asset_id)

        return created

    # ── 2. NOPASSWD sudo added ──────────────────────────────────────────────────

    def _detect_nopasswd_added(self, db: Session) -> int:
        """Alert when NOPASSWD sudo rule appears in sudo_config since last scan."""
        created = 0
        # Find snapshots that have nopasswd_sudo=True in their sudo_config
        from sqlalchemy import or_ as or_filter

        nopasswd_snaps = (
            db.query(models.AccountSnapshot)
            .filter(
                models.AccountSnapshot.deleted_at.is_(None),
                models.AccountSnapshot.sudo_config.isnot(None),
            )
            .all()
        )

        for snap in nopasswd_snaps:
            prev = self._get_previous_snapshot(db, snap.asset_id, snap.id)
            if not prev:
                continue

            cfg = snap.sudo_config or {}
            prev_cfg = prev.sudo_config or {}

            had_nopasswd = prev_cfg.get("nopasswd_sudo", False)
            has_nopasswd = cfg.get("nopasswd_sudo", False)

            if not had_nopasswd and has_nopasswd:
                job = self._latest_job_for_asset(db, snap.asset_id)
                alert = self._create_alert(
                    db, snap.asset_id, AlertLevel.critical,
                    f"账号「{snap.username}」新增 NOPASSWD sudo 权限",
                    f"资产 #{snap.asset_id} 上的「{snap.username}」新增了 sudo 无密码执行权限，这是高危配置变更。",
                    job_id=job.id if job else None,
                    snapshot_id=snap.id,
                    title_key="alert.nopasswd_sudo_added",
                    title_params={"username": snap.username},
                    message_key="alert.msg.nopasswd_sudo_added",
                    message_params={"username": snap.username, "asset_id": snap.asset_id},
                )
                created += 1
                logger.info("Alert: NOPASSWD added for %s on asset %s", snap.username, snap.asset_id)

        return created

    # ── 3. Critical credential findings ─────────────────────────────────────────

    def _detect_credential_findings(self, db: Session) -> int:
        """
        Alert when raw_info contains a credential_finding with risk=critical
        on a snapshot that wasn't present in the previous scan.
        """
        created = 0
        snaps_with_findings = (
            db.query(models.AccountSnapshot)
            .filter(
                models.AccountSnapshot.deleted_at.is_(None),
                models.AccountSnapshot.raw_info.isnot(None),
            )
            .all()
        )

        for snap in snaps_with_findings:
            findings = snap.raw_info.get("credential_findings", [])
            critical_findings = [f for f in findings if f.get("risk") == "critical"]
            if not critical_findings:
                continue

            prev = self._get_previous_snapshot(db, snap.asset_id, snap.id)
            if prev:
                prev_findings = prev.raw_info.get("credential_findings", []) if prev.raw_info else []
                prev_critical = {f["path"] for f in prev_findings if f.get("risk") == "critical"}
                new_critical = [
                    f for f in critical_findings
                    if f.get("path") not in prev_critical
                ]
            else:
                new_critical = critical_findings

            if not new_critical:
                continue

            job = self._latest_job_for_asset(db, snap.asset_id)
            finding_msgs = "; ".join(f['warning'][:80] for f in new_critical[:3])
            alert = self._create_alert(
                db, snap.asset_id, AlertLevel.critical,
                f"发现敏感凭据泄露 — 「{snap.username}」",
                f"资产 #{snap.asset_id} 账号「{snap.username}」发现 {len(new_critical)} 个危险凭据：{finding_msgs}",
                job_id=job.id if job else None,
                snapshot_id=snap.id,
                title_key="alert.credential_leak",
                title_params={"username": snap.username},
                message_key="alert.msg.credential_leak",
                message_params={"username": snap.username, "asset_id": snap.asset_id, "count": len(new_critical), "finding_msgs": finding_msgs},
            )
            created += 1
            logger.info("Alert: credential leak for %s on asset %s: %d items",
                         snap.username, snap.asset_id, len(new_critical))

        return created

    # ── 4. Dormant account reactivated ─────────────────────────────────────────

    def _detect_dormant_reactivated(self, db: Session) -> int:
        """Alert when an account marked dormant/departed becomes active in latest scan."""
        created = 0

        # Get the most recent scan_time
        latest_time = (
            db.query(models.AccountSnapshot.snapshot_time)
            .filter(models.AccountSnapshot.deleted_at.is_(None))
            .order_by(models.AccountSnapshot.snapshot_time.desc())
            .first()
        )
        if not latest_time:
            return 0
        cutoff = _naive(latest_time[0]) - timedelta(days=1)

        # Accounts that appeared in the most recent scan
        latest_snaps = (
            db.query(models.AccountSnapshot)
            .filter(
                models.AccountSnapshot.deleted_at.is_(None),
                models.AccountSnapshot.snapshot_time >= cutoff,
            )
            .all()
        )

        by_asset_user: dict[tuple[int, str], tuple[models.AccountSnapshot, bool]] = {}
        for snap in latest_snaps:
            key = (snap.asset_id, snap.username)
            if key not in by_asset_user:
                by_asset_user[key] = (snap, snap.is_admin)
            else:
                # Use most recent
                existing_snap, _ = by_asset_user[key]
                if snap.snapshot_time > existing_snap.snapshot_time:
                    by_asset_user[key] = (snap, snap.is_admin)

        # Check lifecycle status
        dormant_reactivated: list[tuple[models.AccountSnapshot, models.AccountLifecycleStatus]] = []
        for (asset_id, username), (snap, is_admin) in by_asset_user.items():
            lc = (
                db.query(models.AccountLifecycleStatus)
                .filter(models.AccountLifecycleStatus.snapshot_id == snap.id)
                .first()
            )
            if lc and lc.lifecycle_status in ("dormant", "departed") and snap.last_login:
                # last_login within 7 days → recently reactivated
                if snap.last_login >= datetime.now(timezone.utc) - timedelta(days=7):
                    dormant_reactivated.append((snap, lc))

        for snap, lc in dormant_reactivated:
            job = self._latest_job_for_asset(db, snap.asset_id)
            alert = self._create_alert(
                db, snap.asset_id, AlertLevel.warning,
                f"休眠账号「{snap.username}」重新激活",
                f"账号「{snap.username}」(资产 #{snap.asset_id}) 之前状态为 {lc.lifecycle_status}，"
                f"最近登录时间 {snap.last_login}，请确认为正常业务行为。",
                job_id=job.id if job else None,
                snapshot_id=snap.id,
                title_key="alert.dormant_reactivated",
                title_params={"username": snap.username},
                message_key="alert.msg.dormant_reactivated",
                message_params={"username": snap.username, "asset_id": snap.asset_id, "lifecycle_status": lc.lifecycle_status, "last_login": str(snap.last_login)},
            )
            created += 1
            logger.info("Alert: dormant account %s reactivated on asset %s",
                         snap.username, snap.asset_id)

        return created

    # ── 5. Orphan (shadow) account detection ──────────────────────────────────

    def _detect_orphan_accounts(self, db: Session) -> int:
        """
        Alert when an active privileged account has no linked human identity.

        An 'orphan' account is one where there is no IdentityAccount link
        (no human owner). If it is privileged, it is a potential shadow account.
        Only alerts on accounts that were not already flagged (no duplicate alerts).
        """
        created = 0

        # Get usernames already alerted as orphan (avoid duplicate alerts)
        existing_orphan_usernames = set(
            r[0] for r in db.query(models.Alert.asset_id, models.Alert.message).filter(
                models.Alert.title.like("%孤儿%"),
                models.Alert.status != "dismissed",
            ).all()
        )

        # Get all latest snapshots per asset (active, not deleted)
        latest_snaps = (
            db.query(models.AccountSnapshot)
            .filter(
                models.AccountSnapshot.deleted_at.is_(None),
                models.AccountSnapshot.account_status.in_(["active", "unknown", ""]),
            )
            .distinct(models.AccountSnapshot.asset_id)
            .order_by(
                models.AccountSnapshot.asset_id,
                models.AccountSnapshot.snapshot_time.desc(),
            )
            .all()
        )

        # Build set of snapshot_ids that have a human identity link
        linked_snap_ids = set(
            r[0] for r in db.query(models.IdentityAccount.snapshot_id).all()
        )

        for snap in latest_snaps:
            if (snap.asset_id, snap.username) in existing_orphan_usernames:
                continue  # already alerted
            if snap.id in linked_snap_ids:
                continue  # has an owner

            # Only alert for privileged accounts (shadow account risk)
            if not snap.is_admin:
                continue

            job = self._latest_job_for_asset(db, snap.asset_id)
            alert = self._create_alert(
                db, snap.asset_id, AlertLevel.high,
                f"孤儿特权账号「{snap.username}」",
                f"资产 #{snap.asset_id} 账号「{snap.username}」(UID={snap.uid_sid}) "
                f"为特权账号但无关联人员身份，可能为影子账号，请立即确认归属。",
                job_id=job.id if job else None,
                snapshot_id=snap.id,
                title_key="alert.orphan_account",
                title_params={"username": snap.username},
                message_key="alert.msg.orphan_account",
                message_params={"username": snap.username, "asset_id": snap.asset_id, "uid_sid": snap.uid_sid},
            )
            created += 1
            logger.info(
                "Alert: orphan privileged account %s on asset %s",
                snap.username, snap.asset_id,
            )

        return created


# ── APScheduler entrypoint ──────────────────────────────────────────────────────

def run_monitor():
    """
    APScheduler calls this every 5 minutes.
    Creates a fresh DB session, runs checks, commits results.
    """
    db = SessionLocal()
    try:
        monitor = RealtimeMonitor()
        count = monitor.check_and_alert(db)
        if count > 0:
            db.commit()
            logger.info("RealtimeMonitor: created %d alerts", count)
        else:
            db.rollback()
    except Exception as e:
        logger.error("RealtimeMonitor error: %s", e)
        db.rollback()
    finally:
        db.close()
