"""
Account Lifecycle Service — active/dormant/departed state machine.

Tracks account lifecycle based on last login time.
Triggers alerts on state transitions.
"""

import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from backend import models

logger = logging.getLogger("account_lifecycle")

# ── Default thresholds ─────────────────────────────────────────────────────────

DEFAULT_ACTIVE_DAYS = 30
DEFAULT_DORMANT_DAYS = 90


def _get_config(db: Session, category_slug: str) -> tuple[int, int, bool]:
    """Get (active_days, dormant_days, auto_alert) for a category. Falls back to global."""
    cfg = db.query(models.AccountLifecycleConfig).filter(
        models.AccountLifecycleConfig.category_slug == category_slug
    ).first()
    if cfg:
        return cfg.active_days, cfg.dormant_days, cfg.auto_alert

    global_cfg = db.query(models.AccountLifecycleConfig).filter(
        models.AccountLifecycleConfig.category_slug == "global"
    ).first()
    if global_cfg:
        return global_cfg.active_days, global_cfg.dormant_days, global_cfg.auto_alert

    return DEFAULT_ACTIVE_DAYS, DEFAULT_DORMANT_DAYS, True


def _compute_status(last_login: Optional[datetime], active_days: int, dormant_days: int) -> str:
    """Compute lifecycle status from last_login."""
    if last_login is None:
        return "unknown"
    now = datetime.now(timezone.utc)
    days_ago = (now - last_login).days
    if days_ago <= active_days:
        return "active"
    elif days_ago <= dormant_days:
        return "dormant"
    else:
        return "departed"


def _create_lifecycle_alert(
    db: Session,
    snap: models.AccountSnapshot,
    old_status: Optional[str],
    new_status: str,
    dormant_days: int,
) -> None:
    """Create an alert for a lifecycle state change."""
    from datetime import timedelta as td

    # Skip if already alerted for this snapshot
    existing = db.query(models.AccountLifecycleStatus).filter(
        models.AccountLifecycleStatus.snapshot_id == snap.id,
        models.AccountLifecycleStatus.alert_sent == True,
    ).first()
    if existing:
        return

    asset = db.query(models.Asset).filter(models.Asset.id == snap.asset_id).first()
    asset_code = asset.asset_code if asset else "?"
    asset_ip = asset.ip if asset else "?"

    if new_status == "departed":
        level = models.AlertLevel.critical
        title = f"离机账号告警: {snap.username}@{asset_code}"
        message = f"账号 {snap.username} 在 {asset_code}({asset_ip}) 已超过 {dormant_days} 天未登录，视为离机账号，建议禁用。"
        title_key = "lifecycle.alert.departed"
        title_params = {"username": snap.username, "asset_code": asset_code}
        message_key = "lifecycle.alert.departed.message"
        message_params = {"username": snap.username, "asset_code": asset_code, "ip": asset_ip, "days": dormant_days}
    elif new_status == "dormant":
        level = models.AlertLevel.warning
        title = f"休眠账号提醒: {snap.username}@{asset_code}"
        message = f"账号 {snap.username} 在 {asset_code}({asset_ip}) 已较长时间未登录（{active_days}~{dormant_days} 天），建议审查是否仍需保留。"
        title_key = "lifecycle.alert.dormant"
        title_params = {"username": snap.username, "asset_code": asset_code}
        message_key = "lifecycle.alert.dormant.message"
        message_params = {"username": snap.username, "asset_code": asset_code, "ip": asset_ip, "active_days": active_days, "dormant_days": dormant_days}
    else:
        return  # active or unknown → no alert

    alert = models.Alert(
        asset_id=snap.asset_id,
        level=level,
        title=title,
        message=message,
        title_key=title_key,
        title_params=title_params,
        message_key=message_key,
        message_params=message_params,
        is_read=False,
    )
    db.add(alert)
    logger.info(f"Lifecycle alert: {title}")


def compute_lifecycles(db: Session) -> dict:
    """
    Compute lifecycle status for all latest account snapshots.
    Returns summary dict.
    """
    # Ensure global config exists
    cfg = db.query(models.AccountLifecycleConfig).filter(
        models.AccountLifecycleConfig.category_slug == "global"
    ).first()
    if not cfg:
        cfg = models.AccountLifecycleConfig(
            category_slug="global",
            active_days=DEFAULT_ACTIVE_DAYS,
            dormant_days=DEFAULT_DORMANT_DAYS,
            auto_alert=True,
        )
        db.add(cfg)
        db.commit()

    # Gather all assets and their categories
    assets = {a.id: a for a in db.query(models.Asset).all()}
    asset_category: dict[int, str] = {a.id: a.asset_category for a in assets.values()}

    # Get latest snapshot per (asset_id, username)
    latest_job_ids = {a.id: a.last_scan_job_id for a in assets.values() if a.last_scan_job_id}
    if not latest_job_ids:
        return {"total": 0, "active": 0, "dormant": 0, "departed": 0, "unknown": 0}

    all_snaps = db.query(models.AccountSnapshot).filter(
        models.AccountSnapshot.job_id.in_(latest_job_ids.values()),
        models.AccountSnapshot.deleted_at.is_(None),
    ).all()

    # De-duplicate: latest snapshot per (asset_id, username)
    snap_map: dict[tuple, models.AccountSnapshot] = {}
    for s in all_snaps:
        key = (s.asset_id, s.username)
        if key not in snap_map or s.snapshot_time > snap_map[key].snapshot_time:
            snap_map[key] = s
    snapshots = list(snap_map.values())

    # Get existing lifecycle statuses
    existing = {s.snapshot_id: s for s in db.query(models.AccountLifecycleStatus).all()}
    snap_to_status = existing

    now = datetime.now(timezone.utc)
    counts = {"active": 0, "dormant": 0, "departed": 0, "unknown": 0}
    updated = 0
    alerts_created = 0

    for snap in snapshots:
        category = asset_category.get(snap.asset_id, "server")
        active_days, dormant_days, auto_alert = _get_config(db, category)
        new_status = _compute_status(snap.last_login, active_days, dormant_days)

        counts[new_status] = counts.get(new_status, 0) + 1

        existing_status: Optional[models.AccountLifecycleStatus] = snap_to_status.get(snap.id)
        old_status = existing_status.lifecycle_status if existing_status else None

        if existing_status:
            existing_status.lifecycle_status = new_status
            existing_status.previous_status = old_status
            if old_status != new_status:
                existing_status.changed_at = now
                existing_status.alert_sent = False
            existing_status.updated_at = now
            if auto_alert and new_status in ("dormant", "departed") and not existing_status.alert_sent:
                _create_lifecycle_alert(db, snap, old_status, new_status, dormant_days)
                existing_status.alert_sent = True
        else:
            status = models.AccountLifecycleStatus(
                snapshot_id=snap.id,
                lifecycle_status=new_status,
                previous_status=old_status,
                changed_at=now if old_status and old_status != new_status else None,
                alert_sent=False,
            )
            db.add(status)
            snap_to_status[snap.id] = status
            if auto_alert and new_status in ("dormant", "departed"):
                _create_lifecycle_alert(db, snap, old_status, new_status, dormant_days)
                status.alert_sent = True

        updated += 1

    db.commit()
    logger.info(f"Lifecycle compute: {updated} accounts, {counts}")
    return {"total": updated, **counts}
