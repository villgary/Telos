"""
PAM Integration API — read-only integration with PAM/Bastion systems.
"""

from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session

from backend.database import get_db
from backend import models, schemas, auth
from backend.services.pam_integration import sync_integration, get_comparison

router = APIRouter(prefix="/api/v1/pam", tags=["PAM集成"])


@router.get("/integrations")
async def list_integrations(
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.get_current_user),
):
    """List all PAM integrations."""
    items = db.query(models.PAMIntegration).all()
    result = []
    for it in items:
        count = db.query(models.PAMSyncedAccount).filter(
            models.PAMSyncedAccount.integration_id == it.id
        ).count()
        result.append(schemas.PAMIntegrationResponse(
            id=it.id,
            name=it.name,
            provider=it.provider,
            status=it.status,
            last_sync_at=it.last_sync_at,
            last_error=it.last_error,
            created_by=it.created_by,
            created_at=it.created_at,
            account_count=count,
        ))
    return {"integrations": result}


@router.post("/integrations")
async def create_integration(
    body: schemas.PAMIntegrationCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.require_role(models.UserRole.admin)),
):
    """Create a new PAM integration (admin only)."""
    integ = models.PAMIntegration(
        name=body.name,
        provider=body.provider,
        config=body.config,
        created_by=user.id,
    )
    db.add(integ)
    db.commit()
    db.refresh(integ)
    return schemas.PAMIntegrationResponse(
        id=integ.id, name=integ.name, provider=integ.provider,
        status=integ.status, last_sync_at=integ.last_sync_at,
        last_error=integ.last_error, created_by=integ.created_by,
        created_at=integ.created_at, account_count=0,
    )


@router.put("/integrations/{integration_id}")
async def update_integration(
    integration_id: int,
    body: schemas.PAMIntegrationUpdate,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.require_role(models.UserRole.admin)),
):
    """Update a PAM integration (admin only)."""
    integ = db.query(models.PAMIntegration).filter(
        models.PAMIntegration.id == integration_id
    ).first()
    if not integ:
        raise HTTPException(status_code=404, detail="Integration not found")

    if body.name is not None:
        integ.name = body.name
    if body.config is not None:
        integ.config = body.config
    if body.status is not None:
        integ.status = body.status
    db.commit()
    return {"success": True}


@router.delete("/integrations/{integration_id}", status_code=204)
async def delete_integration(
    integration_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.require_role(models.UserRole.admin)),
):
    """Delete a PAM integration (admin only)."""
    integ = db.query(models.PAMIntegration).filter(
        models.PAMIntegration.id == integration_id
    ).first()
    if not integ:
        raise HTTPException(status_code=404, detail="Integration not found")
    db.delete(integ)
    db.commit()


@router.post("/integrations/{integration_id}/sync")
async def sync_integration_endpoint(
    integration_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.require_role(models.UserRole.admin)),
):
    """Manually trigger PAM account sync (admin only)."""
    result = sync_integration(db, integration_id)
    if "error" in result:
        raise HTTPException(status_code=502, detail=result["error"])
    return {"success": True, **result}


@router.get("/integrations/{integration_id}/accounts")
async def list_pam_accounts(
    integration_id: int,
    limit: int = 100,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.get_current_user),
):
    """List synced PAM accounts for an integration."""
    items = db.query(models.PAMSyncedAccount).filter(
        models.PAMSyncedAccount.integration_id == integration_id
    ).limit(limit).all()

    snap_ids = [s.matched_snapshot_id for s in items if s.matched_snapshot_id]
    snap_map: dict = {}
    if snap_ids:
        snaps = db.query(models.AccountSnapshot).filter(
            models.AccountSnapshot.id.in_(snap_ids)
        ).all()
        snap_map = {s.id: s for s in snaps}

    asset_ids = [s.asset_id for s in items if s.asset_id]
    asset_map = {}
    if asset_ids:
        assets = db.query(models.Asset).filter(models.Asset.id.in_(asset_ids)).all()
        asset_map = {a.id: a for a in assets}

    result = []
    for acc in items:
        snap = snap_map.get(acc.matched_snapshot_id)
        asset = asset_map.get(acc.asset_id)
        snap_username = snap.username if snap else None
        is_admin = snap.is_admin if snap else False

        if acc.asset_id and is_admin and acc.account_type != "privileged":
            comparison_result = "privileged_gap"
        elif acc.asset_id:
            comparison_result = "matched"
        else:
            comparison_result = "unmatched_pam"

        result.append(schemas.PAMSyncedAccountItem(
            id=acc.id,
            integration_id=acc.integration_id,
            account_name=acc.account_name,
            account_type=acc.account_type,
            pam_status=acc.pam_status,
            last_used=acc.last_used,
            matched_asset_code=asset.asset_code if asset else None,
            matched_asset_ip=asset.ip if asset else None,
            matched_username=snap_username,
            is_admin=is_admin,
            match_confidence=acc.match_confidence,
            comparison_result=comparison_result,
        ))

    return {"accounts": result}


@router.get("/comparison")
async def get_comparison_view(
    integration_id: int = None,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.get_current_user),
):
    """Get unified comparison view of PAM accounts vs AccountScan."""
    results = get_comparison(db, integration_id=integration_id)
    return {"results": [schemas.PAMComparisonItem(**r) for r in results]}
