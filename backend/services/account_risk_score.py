"""
Account Risk Score Service — per-account risk scoring.

Factors:
- Long-term inactive (>90 days no login)       → +20
- Privileged account (is_admin=True)          → +15
- High-risk username (root/admin/postgres/sa) → +10
- NOPASSWD sudo rule                          → +10
- Cross-system identity (N assets linked)     → +5*N, cap 20
- Lifecycle status dormant                    → +10
- Lifecycle status departed                   → +20
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from backend import models

logger = logging.getLogger("account_risk_score")

DANGEROUS_ADMIN_NAMES = frozenset({
    "root", "administrator", "admin", "postgres",
    "mysql", "oracle", "sa", "sys", "system",
})


def _level_from_score(score: int) -> str:
    if score >= 70:
        return "critical"
    if score >= 45:
        return "high"
    if score >= 25:
        return "medium"
    return "low"


def _compute_score(
    snapshot: models.AccountSnapshot,
    lifecycle_status: Optional[str],
    identity: Optional[models.HumanIdentity],
    cross_asset_count: int,
    has_nopasswd_sudo: bool,
) -> tuple[int, list[dict]]:
    """Return (score, factors) for a snapshot."""
    score = 0
    factors: list[dict] = []

    # 1. Long-term inactive (>90 days)
    days_since_login: Optional[int] = None
    if snapshot.last_login:
        days_since_login = (datetime.utcnow() - snapshot.last_login).days
        if days_since_login > 90:
            factors.append({"factor": "长期未登录", "score": 20})
            score += 20

    # 2. Privileged account
    if snapshot.is_admin:
        factors.append({"factor": "特权账号", "score": 15})
        score += 15

    # 3. High-risk username
    username_lower = snapshot.username.lower()
    if username_lower in DANGEROUS_ADMIN_NAMES:
        factors.append({"factor": f"高危用户名({snapshot.username})", "score": 10})
        score += 10

    # 4. NOPASSWD sudo
    if has_nopasswd_sudo:
        factors.append({"factor": "免密sudo(NOPASSWD)", "score": 10})
        score += 10

    # 5. Cross-system identity
    if cross_asset_count > 1:
        extra = min(cross_asset_count * 5, 20)
        factors.append({"factor": f"跨{cross_asset_count}系统关联", "score": extra})
        score += extra

    # 6. Lifecycle dormant / departed
    if lifecycle_status == "dormant":
        factors.append({"factor": "休眠账号", "score": 10})
        score += 10
    elif lifecycle_status == "departed":
        factors.append({"factor": "离机账号", "score": 20})
        score += 20

    # Cap at 100
    score = min(score, 100)
    return score, factors


def _has_nopasswd_sudo(snapshot: models.AccountSnapshot) -> bool:
    """Check if snapshot has any NOPASSWD sudo rules."""
    sudo = snapshot.sudo_config
    if not sudo:
        return False
    if isinstance(sudo, list):
        for rule in sudo:
            if isinstance(rule, dict) and rule.get("nopasswd"):
                return True
            if isinstance(rule, str) and "NOPASSWD" in rule.upper():
                return True
    return False


def compute_account_score(
    db: Session,
    snapshot: models.AccountSnapshot,
) -> models.AccountRiskScore:
    """Compute and upsert risk score for a single snapshot."""
    # Identity
    identity: Optional[models.HumanIdentity] = None
    cross_asset_count = 0
    if snapshot.uid_sid:
        link = db.query(models.IdentityAccount).filter(
            models.IdentityAccount.snapshot_id == snapshot.id
        ).first()
        if link and link.identity_id:
            identity = db.query(models.HumanIdentity).filter(
                models.HumanIdentity.id == link.identity_id
            ).first()
            if identity:
                cross_asset_count = db.query(models.IdentityAccount).filter(
                    models.IdentityAccount.identity_id == identity.id
                ).count()

    # Lifecycle
    lifecycle_status: Optional[str] = None
    lc = db.query(models.AccountLifecycleStatus).filter(
        models.AccountLifecycleStatus.snapshot_id == snapshot.id
    ).first()
    if lc:
        lifecycle_status = lc.lifecycle_status

    # Score
    score, factors = _compute_score(
        snapshot, lifecycle_status, identity, cross_asset_count,
        _has_nopasswd_sudo(snapshot),
    )
    level = _level_from_score(score)

    # Upsert
    existing = db.query(models.AccountRiskScore).filter(
        models.AccountRiskScore.snapshot_id == snapshot.id
    ).first()
    if existing:
        existing.risk_score = score
        existing.risk_level = level
        existing.risk_factors = factors
        existing.identity_id = identity.id if identity else None
        existing.cross_asset_count = cross_asset_count
        existing.computed_at = datetime.now(timezone.utc)
        record = existing
    else:
        record = models.AccountRiskScore(
            snapshot_id=snapshot.id,
            risk_score=score,
            risk_level=level,
            risk_factors=factors,
            identity_id=identity.id if identity else None,
            cross_asset_count=cross_asset_count,
            computed_at=datetime.now(timezone.utc),
        )
        db.add(record)

    db.commit()
    db.refresh(record)
    return record


def compute_all_scores(db: Session) -> dict:
    """Recompute risk scores for all snapshots."""
    # Latest snapshot per (asset_id, username)
    from sqlalchemy import func, and_

    # Subquery: latest snapshot_id per (asset_id, username)
    subq = db.query(
        models.AccountSnapshot.asset_id,
        models.AccountSnapshot.username,
        func.max(models.AccountSnapshot.id).label("max_id"),
    ).group_by(
        models.AccountSnapshot.asset_id,
        models.AccountSnapshot.username,
    ).subquery()

    latest_ids = db.query(subq.c.max_id).all()
    snapshot_ids = [r[0] for r in latest_ids]

    if not snapshot_ids:
        return {"count": 0}

    snapshots = db.query(models.AccountSnapshot).filter(
        models.AccountSnapshot.id.in_(snapshot_ids)
    ).all()

    computed = 0
    for snap in snapshots:
        try:
            compute_account_score(db, snap)
            computed += 1
        except Exception as e:
            logger.warning(f"Score compute failed for snapshot {snap.id}: {e}")

    return {"count": computed}
