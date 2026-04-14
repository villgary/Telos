"""
UEBA Service — User Entity Behavior Analytics.

Detects account behavior anomalies based on snapshot history:
- Dormant → Active transition (was dead, now alive)
- Active → Dormant/Departed (going silent)
- New privileged account (new admin account)
- Long-term never-logged-in privileged account
- Sudden login spike (account previously dormant now active across multiple assets)
"""

from datetime import datetime, timedelta, timezone
from typing import Optional
from sqlalchemy.orm import Session, aliased
from sqlalchemy import desc, and_, func
from backend import models

# ── Types ──────────────────────────────────────────────────────────────────

class BehaviorAnomaly:
    def __init__(
        self,
        event_type: str,
        severity: str,  # critical / high / medium / low
        username: str,
        asset_code: Optional[str],
        asset_ip: Optional[str],
        description: str,
        description_key: Optional[str] = None,
        description_params: Optional[dict] = None,
        snapshot_id: Optional[int] = None,
        detected_at: Optional[datetime] = None,
    ):
        self.event_type = event_type
        self.severity = severity
        self.username = username
        self.asset_code = asset_code
        self.asset_ip = asset_ip
        self.description = description
        self.description_key = description_key
        self.description_params = description_params or {}
        self.snapshot_id = snapshot_id
        self.detected_at = detected_at

    def to_dict(self):
        return {
            "event_type": self.event_type,
            "severity": self.severity,
            "username": self.username,
            "asset_code": self.asset_code,
            "asset_ip": self.asset_ip,
            "description": self.description,
            "description_key": self.description_key,
            "description_params": self.description_params,
            "snapshot_id": self.snapshot_id,
            "detected_at": self.detected_at.isoformat() if self.detected_at else None,
        }


# ── Core Detection ─────────────────────────────────────────────────────────

def detect_all_anomalies(db: Session) -> list[BehaviorAnomaly]:
    """
    Scan all accounts across the latest snapshots and detect anomalies.
    Results are persisted to the account_behavior_events table.
    """
    anomalies: list[BehaviorAnomaly] = []
    now = datetime.now(timezone.utc)

    # Get the latest non-deleted snapshot per (username, asset_id) pair
    subq = (
        db.query(
            models.AccountSnapshot.username,
            models.AccountSnapshot.asset_id,
            func.max(models.AccountSnapshot.id).label("latest_id"),
        )
        .filter(models.AccountSnapshot.deleted_at.is_(None))
        .group_by(
            models.AccountSnapshot.username,
            models.AccountSnapshot.asset_id,
        )
        .subquery()
    )

    latest_snapshots = (
        db.query(models.AccountSnapshot)
        .join(
            subq,
            and_(
                models.AccountSnapshot.username == subq.c.username,
                models.AccountSnapshot.asset_id == subq.c.asset_id,
                models.AccountSnapshot.id == subq.c.latest_id,
            ),
        )
        .all()
    )

    # Build lifecycle status map: snapshot_id → status
    lifecycle_map: dict[int, str] = {}
    lifecycle_rows = db.query(models.AccountLifecycleStatus).all()
    for row in lifecycle_rows:
        lifecycle_map[row.snapshot_id] = row.lifecycle_status

    # Get previous snapshots (second-latest) for transition detection
    prev_snapshots_map: dict[tuple, models.AccountSnapshot] = {}
    for snap in latest_snapshots:
        # Find the second-latest snapshot for this (username, asset_id)
        prev = (
            db.query(models.AccountSnapshot)
            .filter(
                models.AccountSnapshot.username == snap.username,
                models.AccountSnapshot.asset_id == snap.asset_id,
                models.AccountSnapshot.id != snap.id,
                models.AccountSnapshot.deleted_at.is_(None),
            )
            .order_by(desc(models.AccountSnapshot.snapshot_time))
            .offset(1)
            .limit(1)
            .first()
        )
        if prev:
            prev_snapshots_map[(snap.username, snap.asset_id)] = prev

    # ── Detection Rules ───────────────────────────────────────────────────

    # Group snapshots by (username) for cross-asset analysis
    from collections import defaultdict
    by_username: dict[str, list[models.AccountSnapshot]] = defaultdict(list)
    for snap in latest_snapshots:
        by_username[snap.username].append(snap)

    for snap in latest_snapshots:
        prev_snap = prev_snapshots_map.get((snap.username, snap.asset_id))
        asset = snap.asset
        current_status = lifecycle_map.get(snap.id, "unknown")
        prev_status = lifecycle_map.get(prev_snap.id, "unknown") if prev_snap else None

        # Rule 1: Dormant → Active (was dormant on prev scan, now has last_login)
        if prev_snap and prev_status == "departed" and current_status == "active":
            anomalies.append(BehaviorAnomaly(
                event_type="dormant_to_active",
                severity="high",
                username=snap.username,
                asset_code=asset.asset_code if asset else None,
                asset_ip=asset.ip if asset else None,
                description=f"Account {snap.username} (@{asset.asset_code if asset else snap.asset_id}) reactivated from departed status",
                description_key="ueba.desc.dormantToActive",
                description_params={"username": snap.username, "asset": asset.asset_code if asset else str(snap.asset_id), "last_login": str(snap.last_login or "N/A")},
                snapshot_id=snap.id,
                detected_at=now,
            ))

        # Rule 2: Active → Dormant/Departed (went silent)
        if prev_snap and prev_status == "active" and current_status in ("dormant", "departed"):
            anomalies.append(BehaviorAnomaly(
                event_type="went_dormant",
                severity="medium",
                username=snap.username,
                asset_code=asset.asset_code if asset else None,
                asset_ip=asset.ip if asset else None,
                description=f"Account {snap.username} (@{asset.asset_code if asset else snap.asset_id}) became {current_status}, no login for {_days_since(snap.last_login)} days",
                description_key="ueba.desc.wentDormant",
                description_params={"username": snap.username, "asset": asset.asset_code if asset else str(snap.asset_id), "status": current_status, "days": _days_since(snap.last_login)},
                snapshot_id=snap.id,
                detected_at=now,
            ))

        # Rule 3: New privileged account (is_admin and prev didn't exist)
        if snap.is_admin and not prev_snap:
            # Check if this is truly new or just first scan
            total_prev = (
                db.query(models.AccountSnapshot)
                .filter(
                    models.AccountSnapshot.username == snap.username,
                    models.AccountSnapshot.id != snap.id,
                    models.AccountSnapshot.deleted_at.is_(None),
                )
                .count()
            )
            if total_prev == 0:
                anomalies.append(BehaviorAnomaly(
                    event_type="new_privileged_account",
                    severity="high",
                    username=snap.username,
                    asset_code=asset.asset_code if asset else None,
                    asset_ip=asset.ip if asset else None,
                    description=f"New privileged account discovered: {snap.username} (@{asset.asset_code if asset else snap.asset_id})",
                    description_key="ueba.desc.newPrivileged",
                    description_params={"username": snap.username, "asset": asset.asset_code if asset else str(snap.asset_id)},
                    snapshot_id=snap.id,
                    detected_at=now,
                ))

        # Rule 4: Never-logged-in privileged account (always risky)
        if snap.is_admin and not snap.last_login:
            anomalies.append(BehaviorAnomaly(
                event_type="privileged_no_login",
                severity="medium",
                username=snap.username,
                asset_code=asset.asset_code if asset else None,
                asset_ip=asset.ip if asset else None,
                description=f"Privileged account {snap.username} (@{asset.asset_code if asset else snap.asset_id}) has never logged in",
                description_key="ueba.desc.privilegedNoLogin",
                description_params={"username": snap.username, "asset": asset.asset_code if asset else str(snap.asset_id)},
                snapshot_id=snap.id,
                detected_at=now,
            ))

        # Rule 5: Admin status gained (escalation)
        if snap.is_admin and prev_snap and not prev_snap.is_admin:
            anomalies.append(BehaviorAnomaly(
                event_type="privilege_escalation",
                severity="critical",
                username=snap.username,
                asset_code=asset.asset_code if asset else None,
                asset_ip=asset.ip if asset else None,
                description=f"Account {snap.username} (@{asset.asset_code if asset else snap.asset_id}) escalated: regular → privileged",
                description_key="ueba.desc.privilegeEscalation",
                description_params={"username": snap.username, "asset": asset.asset_code if asset else str(snap.asset_id)},
                snapshot_id=snap.id,
                detected_at=now,
            ))

    # Rule 6: Cross-asset sudden activity (same user active on many assets suddenly)
    for username, snaps in by_username.items():
        prev_all_dormant = all(
            prev_snapshots_map.get((s.username, s.asset_id)) is None
            or lifecycle_map.get(prev_snapshots_map[(s.username, s.asset_id)].id, "unknown") in ("dormant", "departed")
            for s in snaps
            if prev_snapshots_map.get((s.username, s.asset_id)) is not None
        )
        current_all_active = all(lifecycle_map.get(s.id, "unknown") == "active" for s in snaps)
        if prev_all_dormant and current_all_active and len(snaps) >= 3:
            anomalies.append(BehaviorAnomaly(
                event_type="cross_asset_awakening",
                severity="critical",
                username=username,
                asset_code=f"{len(snaps)} assets",
                asset_ip=None,
                description=f"Account {username} simultaneously reactivated on {len(snaps)} assets (all previously dormant/departed)",
                description_key="ueba.desc.crossAssetAwakening",
                description_params={"username": username, "count": len(snaps)},
                snapshot_id=None,
                detected_at=now,
            ))

    # Persist anomalies
    for anomaly in anomalies:
        existing = db.query(models.AccountBehaviorEvent).filter(
            models.AccountBehaviorEvent.snapshot_id == anomaly.snapshot_id,
            models.AccountBehaviorEvent.event_type == anomaly.event_type,
            models.AccountBehaviorEvent.detected_at >= (now - timedelta(hours=1)),
        ).first()
        if not existing:
            db.add(models.AccountBehaviorEvent(
                event_type=anomaly.event_type,
                severity=anomaly.severity,
                username=anomaly.username,
                asset_code=anomaly.asset_code,
                asset_ip=anomaly.asset_ip,
                description=anomaly.description,
                description_key=anomaly.description_key,
                description_params=anomaly.description_params,
                snapshot_id=anomaly.snapshot_id,
                detected_at=anomaly.detected_at,
            ))
    db.commit()

    return anomalies


def _days_since(dt: Optional[datetime]) -> int:
    if not dt:
        return 9999
    return (datetime.utcnow() - dt).days


# ── Summary Stats ─────────────────────────────────────────────────────────

def get_behavior_summary(db: Session) -> dict:
    """Return behavior summary statistics."""
    now = datetime.now(timezone.utc)
    total_accounts = db.query(models.AccountSnapshot).filter(
        models.AccountSnapshot.deleted_at.is_(None),
    ).count()

    # Count latest snapshot per account — join with lifecycle_status table
    lifecycle_alias = aliased(models.AccountLifecycleStatus)
    active_accounts = (
        db.query(lifecycle_alias.lifecycle_status, func.count(models.AccountSnapshot.id))
        .outerjoin(lifecycle_alias, models.AccountSnapshot.id == lifecycle_alias.snapshot_id)
        .filter(models.AccountSnapshot.deleted_at.is_(None))
        .group_by(lifecycle_alias.lifecycle_status)
        .all()
    )
    active_count = sum(c for s, c in active_accounts if s == "active")
    dormant_count = sum(c for s, c in active_accounts if s == "dormant")
    departed_count = sum(c for s, c in active_accounts if s == "departed")

    recent_anomalies = db.query(models.AccountBehaviorEvent).filter(
        models.AccountBehaviorEvent.detected_at >= now - timedelta(days=7)
    ).count()

    critical_anomalies = db.query(models.AccountBehaviorEvent).filter(
        models.AccountBehaviorEvent.severity == "critical",
        models.AccountBehaviorEvent.detected_at >= now - timedelta(days=7)
    ).count()

    # Recent behavior events (last 7 days)
    recent_events = (
        db.query(models.AccountBehaviorEvent)
        .filter(models.AccountBehaviorEvent.detected_at >= now - timedelta(days=7))
        .order_by(desc(models.AccountBehaviorEvent.detected_at))
        .limit(20)
        .all()
    )

    return {
        "total_accounts": total_accounts,
        "active_accounts": active_count,
        "dormant_accounts": dormant_count,
        "departed_accounts": departed_count,
        "recent_anomaly_count": recent_anomalies,
        "critical_anomaly_count": critical_anomalies,
        "recent_events": [
            {
                "id": e.id,
                "event_type": e.event_type,
                "severity": e.severity,
                "username": e.username,
                "asset_code": e.asset_code,
                "asset_ip": e.asset_ip,
                "description": e.description,
                "description_key": e.description_key,
                "description_params": e.description_params or {},
                "detected_at": e.detected_at.isoformat() if e.detected_at else None,
            }
            for e in recent_events
        ],
    }
