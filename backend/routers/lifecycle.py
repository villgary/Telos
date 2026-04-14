"""
Account Lifecycle API — active/dormant/departed state tracking.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.database import get_db
from backend import models, schemas, auth
from backend.services.account_lifecycle import compute_lifecycles, _get_config

router = APIRouter(prefix="/api/v1/lifecycle", tags=["账号生命周期"])


@router.get("/dashboard", response_model=schemas.LifecycleDashboard)
async def get_lifecycle_dashboard(
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.get_current_user),
):
    """Get lifecycle summary counts and current thresholds."""
    active_days, dormant_days, _ = _get_config(db, "global")

    statuses = db.query(models.AccountLifecycleStatus).all()
    counts = {"active": 0, "dormant": 0, "departed": 0, "unknown": 0}
    for s in statuses:
        counts[s.lifecycle_status] = counts.get(s.lifecycle_status, 0) + 1

    return schemas.LifecycleDashboard(
        total=len(statuses),
        active=counts["active"],
        dormant=counts["dormant"],
        departed=counts["departed"],
        unknown=counts["unknown"],
        threshold_active=active_days,
        threshold_dormant=dormant_days,
    )


@router.get("/statuses")
async def list_lifecycle_statuses(
    status_filter: str = Query(None, alias="status"),
    asset_id: int = Query(None),
    search: str = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.get_current_user),
):
    """List account lifecycle statuses with filtering."""
    query = db.query(models.AccountLifecycleStatus).join(
        models.AccountSnapshot
    ).join(models.Asset)

    if status_filter:
        query = query.filter(models.AccountLifecycleStatus.lifecycle_status == status_filter)
    if asset_id:
        query = query.filter(models.Asset.id == asset_id)
    if search:
        query = query.filter(
            (models.AccountSnapshot.username.ilike(f"%{search}%"))
            | (models.Asset.asset_code.ilike(f"%{search}%"))
            | (models.Asset.ip.ilike(f"%{search}%"))
        )

    total = query.count()
    items = query.order_by(models.AccountLifecycleStatus.changed_at.desc().nullslast()).offset(offset).limit(limit).all()

    result = []
    for st in items:
        snap = st.snapshot
        asset = db.query(models.Asset).filter(models.Asset.id == st.snapshot.asset_id).first()
        result.append(schemas.LifecycleStatusItem(
            snapshot_id=st.snapshot_id,
            asset_id=st.snapshot.asset_id,
            asset_code=asset.asset_code if asset else "?",
            ip=asset.ip if asset else "?",
            hostname=asset.hostname if asset else None,
            username=snap.username if snap else "?",
            uid_sid=snap.uid_sid if snap else "?",
            is_admin=snap.is_admin if snap else False,
            lifecycle_status=st.lifecycle_status,
            previous_status=st.previous_status,
            last_login=snap.last_login if snap else None,
            changed_at=st.changed_at,
            category=asset.asset_category if asset else "?",
        ))

    return {"total": total, "statuses": result}


@router.post("/compute")
async def trigger_compute(
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.require_role(models.UserRole.admin)),
):
    """Manually trigger full lifecycle computation."""
    result = compute_lifecycles(db)
    return {"success": True, **result}


@router.get("/config", response_model=schemas.LifecycleConfigResponse)
async def get_config(
    category: str = Query("global"),
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.get_current_user),
):
    """Get lifecycle config for a category."""
    cfg = db.query(models.AccountLifecycleConfig).filter(
        models.AccountLifecycleConfig.category_slug == category
    ).first()
    if not cfg:
        # Return defaults
        return schemas.LifecycleConfigResponse(
            id=0, category_slug=category,
            active_days=30, dormant_days=90, auto_alert=True,
        )
    return cfg


@router.put("/config")
async def update_config(
    update: schemas.LifecycleConfigUpdate,
    category: str = Query("global"),
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.require_role(models.UserRole.admin)),
):
    """Update lifecycle config for a category."""
    from datetime import datetime as dt

    cfg = db.query(models.AccountLifecycleConfig).filter(
        models.AccountLifecycleConfig.category_slug == category
    ).first()

    if not cfg:
        cfg = models.AccountLifecycleConfig(category_slug=category)
        db.add(cfg)

    if update.active_days is not None:
        cfg.active_days = update.active_days
    if update.dormant_days is not None:
        cfg.dormant_days = update.dormant_days
    if update.auto_alert is not None:
        cfg.auto_alert = update.auto_alert
    cfg.updated_at = dt.utcnow()
    db.commit()
    return cfg
