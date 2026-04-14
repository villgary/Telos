"""
NHI Module API — Non-Human Identity registry and governance.
"""
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend import models
from backend.auth import get_current_user
from backend.database import get_db
from backend.schemas import (
    NHIIdentityResponse,
    NHIInventoryResponse,
    NHIAlertResponse,
    NHIDashboardResponse,
    NHIPolicyResponse,
)
from backend.services.nhi_analyzer import NHIAnalyzer


router = APIRouter(prefix="/api/v1/nhi", tags=["nhi"])


def _nhi_to_response(nhi: models.NHIIdentity) -> NHIIdentityResponse:
    return NHIIdentityResponse.model_validate(nhi)


def _alert_to_response(alert: models.NHIAlert) -> NHIAlertResponse:
    nhi = alert.nhi
    return NHIAlertResponse(
        id=alert.id,
        nhi_id=alert.nhi_id,
        alert_type=alert.alert_type,
        level=alert.level,
        title=alert.title,
        message=alert.message,
        is_read=alert.is_read,
        status=alert.status,
        resolved_at=alert.resolved_at,
        created_at=alert.created_at,
        nhi_username=nhi.username if nhi else None,
        nhi_type=nhi.nhi_type if nhi else None,
        asset_code=nhi.hostname if nhi else None,
    )


# ─── Dashboard ────────────────────────────────────────────────────────────────

@router.get("/dashboard", response_model=NHIDashboardResponse)
def get_dashboard(
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """
    NHI module overview — human vs NHI ratio, risk breakdown, top alerts.
    """
    total_nhi = db.query(models.NHIIdentity).filter(
        models.NHIIdentity.is_active == True
    ).count()

    # Human count: active snapshots not classified as NHI
    # (approximate — only count accounts that went through classification)
    nhi_snapshot_ids = [
        r[0] for r in db.query(models.NHIIdentity.snapshot_id).all()
    ]
    human_count = 0
    if nhi_snapshot_ids:
        human_count = db.query(models.AccountSnapshot).filter(
            models.AccountSnapshot.deleted_at.is_(None),
            models.AccountSnapshot.id.notin_(nhi_snapshot_ids),
        ).count()
    else:
        human_count = db.query(models.AccountSnapshot).filter(
            models.AccountSnapshot.deleted_at.is_(None)
        ).count()

    # Type breakdown
    type_rows = db.query(
        models.NHIIdentity.nhi_type,
        func.count(models.NHIIdentity.id),
    ).filter(
        models.NHIIdentity.is_active == True
    ).group_by(models.NHIIdentity.nhi_type).all()
    by_type = {r[0]: r[1] for r in type_rows}

    # Level breakdown
    level_rows = db.query(
        models.NHIIdentity.nhi_level,
        func.count(models.NHIIdentity.id),
    ).filter(
        models.NHIIdentity.is_active == True
    ).group_by(models.NHIIdentity.nhi_level).all()
    by_level = {r[0]: r[1] for r in level_rows}

    # Counts
    critical_count = db.query(models.NHIIdentity).filter(
        models.NHIIdentity.is_active == True,
        models.NHIIdentity.nhi_level == "critical",
    ).count()
    high_count = db.query(models.NHIIdentity).filter(
        models.NHIIdentity.is_active == True,
        models.NHIIdentity.nhi_level == "high",
    ).count()
    no_owner_count = db.query(models.NHIIdentity).filter(
        models.NHIIdentity.is_active == True,
        models.NHIIdentity.owner_identity_id.is_(None),
        models.NHIIdentity.owner_email.is_(None),
    ).count()
    rotation_due_count = db.query(models.NHIIdentity).filter(
        models.NHIIdentity.is_active == True,
        models.NHIIdentity.rotation_due_days != None,
        models.NHIIdentity.rotation_due_days <= 30,
    ).count()
    has_nopasswd_count = db.query(models.NHIIdentity).filter(
        models.NHIIdentity.is_active == True,
        models.NHIIdentity.has_nopasswd_sudo == True,
    ).count()

    # Top 10 risks
    top_risks = db.query(models.NHIIdentity).filter(
        models.NHIIdentity.is_active == True,
    ).order_by(models.NHIIdentity.risk_score.desc()).limit(10).all()

    # Recent alerts
    recent_alerts = db.query(models.NHIAlert).filter(
        models.NHIAlert.status == "new"
    ).order_by(models.NHIAlert.created_at.desc()).limit(10).all()

    nhi_ratio = round(total_nhi / max(total_nhi + human_count, 1), 3)

    return NHIDashboardResponse(
        total_nhi=total_nhi,
        total_human=human_count,
        nhi_ratio=nhi_ratio,
        by_type=by_type,
        by_level=by_level,
        critical_count=critical_count,
        high_count=high_count,
        no_owner_count=no_owner_count,
        rotation_due_count=rotation_due_count,
        has_nopasswd_count=has_nopasswd_count,
        top_risks=[_nhi_to_response(n) for n in top_risks],
        recent_alerts=[_alert_to_response(a) for a in recent_alerts],
    )


# ─── Inventory ────────────────────────────────────────────────────────────────

@router.get("/inventory", response_model=NHIInventoryResponse)
def list_nhi(
    nhi_type: Annotated[str | None, Query(description="Filter by NHI type")] = None,
    level: Annotated[str | None, Query(description="Filter by risk level")] = None,
    no_owner: Annotated[bool, Query(description="Only NHIs without owner")] = False,
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """
    Paginated NHI inventory list.
    """
    query = db.query(models.NHIIdentity).filter(
        models.NHIIdentity.is_active == True
    )
    if nhi_type:
        query = query.filter(models.NHIIdentity.nhi_type == nhi_type)
    if level:
        query = query.filter(models.NHIIdentity.nhi_level == level)
    if no_owner:
        query = query.filter(
            models.NHIIdentity.owner_identity_id.is_(None),
            models.NHIIdentity.owner_email.is_(None),
        )

    total = query.count()
    items = query.order_by(
        models.NHIIdentity.risk_score.desc()
    ).offset(offset).limit(limit).all()

    # Breakdowns
    type_rows = db.query(
        models.NHIIdentity.nhi_type,
        func.count(models.NHIIdentity.id),
    ).filter(models.NHIIdentity.is_active == True).group_by(
        models.NHIIdentity.nhi_type
    ).all()
    type_breakdown = {r[0]: r[1] for r in type_rows}

    level_rows = db.query(
        models.NHIIdentity.nhi_level,
        func.count(models.NHIIdentity.id),
    ).filter(models.NHIIdentity.is_active == True).group_by(
        models.NHIIdentity.nhi_level
    ).all()
    level_breakdown = {r[0]: r[1] for r in level_rows}

    return NHIInventoryResponse(
        items=[_nhi_to_response(n) for n in items],
        total=total,
        type_breakdown=type_breakdown,
        level_breakdown=level_breakdown,
    )


@router.get("/{nhi_id}", response_model=NHIIdentityResponse)
def get_nhi(
    nhi_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """Get a single NHI record."""
    nhi = db.query(models.NHIIdentity).filter(
        models.NHIIdentity.id == nhi_id
    ).first()
    if not nhi:
        raise HTTPException(404, "NHI not found")
    return _nhi_to_response(nhi)


@router.patch("/{nhi_id}/owner")
def assign_nhi_owner(
    nhi_id: int,
    owner_email: Annotated[str, Query(description="Owner email")],
    owner_name: Annotated[str | None, Query(description="Owner display name")] = None,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """Assign an owner to an NHI record."""
    nhi = db.query(models.NHIIdentity).filter(
        models.NHIIdentity.id == nhi_id
    ).first()
    if not nhi:
        raise HTTPException(404, "NHI not found")

    # Try to find matching human identity
    identity = db.query(models.HumanIdentity).filter(
        models.HumanIdentity.email == owner_email
    ).first()

    nhi.owner_identity_id = identity.id if identity else None
    nhi.owner_email = owner_email
    nhi.owner_name = owner_name or ""
    db.commit()

    return {"ok": True, "owner_email": owner_email}


@router.patch("/{nhi_id}/monitor")
def toggle_nhi_monitoring(
    nhi_id: int,
    enabled: Annotated[bool, Query(description="Enable or disable monitoring")] = True,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """Enable or disable monitoring for an NHI."""
    nhi = db.query(models.NHIIdentity).filter(
        models.NHIIdentity.id == nhi_id
    ).first()
    if not nhi:
        raise HTTPException(404, "NHI not found")
    nhi.is_monitored = enabled
    db.commit()
    return {"ok": True, "is_monitored": enabled}


# ─── Sync ───────────────────────────────────────────────────────────────────

@router.post("/sync")
def sync_nhi(
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """
    Re-scan all account snapshots and update NHI registry.
    Returns summary of the sync operation.
    """
    analyzer = NHIAnalyzer(db)
    total, nhi_count, human_count = analyzer.sync_all()
    alerts_created = analyzer.generate_alerts()

    return {
        "ok": True,
        "total_snapshots_processed": total,
        "nhi_count": nhi_count,
        "human_count": human_count,
        "alerts_created": alerts_created,
    }


# ─── Alerts ─────────────────────────────────────────────────────────────────

@router.get("/alerts", response_model=list[NHIAlertResponse])
def list_nhi_alerts(
    level: Annotated[str | None, Query(description="Filter by alert level")] = None,
    status_filter: Annotated[str | None, Query(alias="status", description="Filter by status")] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """List NHI-specific alerts."""
    query = db.query(models.NHIAlert)
    if level:
        query = query.filter(models.NHIAlert.level == level)
    if status_filter:
        query = query.filter(models.NHIAlert.status == status_filter)
    alerts = query.order_by(
        models.NHIAlert.created_at.desc()
    ).offset(offset).limit(limit).all()
    return [_alert_to_response(a) for a in alerts]


@router.patch("/alerts/{alert_id}/acknowledge")
def acknowledge_nhi_alert(
    alert_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """Mark NHI alert as acknowledged."""
    alert = db.query(models.NHIAlert).filter(
        models.NHIAlert.id == alert_id
    ).first()
    if not alert:
        raise HTTPException(404, "Alert not found")
    alert.is_read = True
    alert.status = "acknowledged"
    db.commit()
    return {"ok": True}


@router.patch("/alerts/{alert_id}/resolve")
def resolve_nhi_alert(
    alert_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """Mark NHI alert as resolved."""
    alert = db.query(models.NHIAlert).filter(
        models.NHIAlert.id == alert_id
    ).first()
    if not alert:
        raise HTTPException(404, "Alert not found")
    alert.status = "resolved"
    alert.resolved_at = datetime.now(timezone.utc)
    alert.resolved_by = user.id
    alert.is_read = True
    db.commit()
    return {"ok": True}


# ─── Policies ────────────────────────────────────────────────────────────────

@router.get("/policies", response_model=list[NHIPolicyResponse])
def list_nhi_policies(
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """List all NHI governance policies."""
    policies = db.query(models.NHIPolicy).all()
    return [NHIPolicyResponse.model_validate(p) for p in policies]


@router.post("/policies", response_model=NHIPolicyResponse, status_code=status.HTTP_201_CREATED)
def create_nhi_policy(
    body: dict,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """Create a new NHI governance policy."""
    policy = models.NHIPolicy(
        name=body.get("name"),
        description=body.get("description"),
        nhi_type=body.get("nhi_type"),
        severity_filter=body.get("severity_filter"),
        rotation_days=body.get("rotation_days"),
        alert_threshold_days=body.get("alert_threshold_days"),
        require_owner=body.get("require_owner", True),
        require_monitoring=body.get("require_monitoring", False),
        enabled=body.get("enabled", True),
        created_by=user.id,
    )
    db.add(policy)
    db.commit()
    db.refresh(policy)
    return NHIPolicyResponse.model_validate(policy)


@router.delete("/policies/{policy_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_nhi_policy(
    policy_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """Delete an NHI policy."""
    policy = db.query(models.NHIPolicy).filter(
        models.NHIPolicy.id == policy_id
    ).first()
    if not policy:
        raise HTTPException(404, "Policy not found")
    db.delete(policy)
    db.commit()
