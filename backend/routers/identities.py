"""
Identity Fusion API — cross-system account identity management.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.database import get_db
from backend import models, schemas, auth
from backend.services.identity_fusion import fuse_identities, get_identity_list

router = APIRouter(prefix="/api/v1/identities", tags=["身份融合"])


@router.get("")
async def list_identities(
    search: str = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.get_current_user),
):
    """List all human identities with stats."""
    results, total = get_identity_list(db, search=search, limit=limit, offset=offset)
    return {"total": total, "identities": results}


@router.get("/suggestions")
async def get_suggestions(
    q: str = Query(..., min_length=1),
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.get_current_user),
):
    """
    Suggest identity links for a given username or uid.
    Returns snapshots that could belong to existing identities.
    """
    snapshots = db.query(models.AccountSnapshot).filter(
        (models.AccountSnapshot.username.ilike(f"%{q}%"))
        | (models.AccountSnapshot.uid_sid.ilike(f"%{q}%"))
    ).limit(20).all()

    results = []
    for snap in snapshots:
        asset = db.query(models.Asset).filter(models.Asset.id == snap.asset_id).first()
        if not asset:
            continue

        # Find candidate identities
        candidates = []
        # UID match
        same_uid = db.query(models.IdentityAccount).join(models.HumanIdentity).filter(
            models.IdentityAccount.asset_id != snap.asset_id,
            models.IdentityAccount.match_type == "uid",
        ).all()
        for link in same_uid:
            ident = db.query(models.HumanIdentity).get(link.identity_id)
            if ident:
                candidates.append(ident.id)

        results.append(schemas.IdentitySuggestion(
            snapshot_id=snap.id,
            asset_code=asset.asset_code,
            ip=asset.ip,
            username=snap.username,
            uid_sid=snap.uid_sid,
            is_admin=snap.is_admin,
            match_reason=f"uid={snap.uid_sid}" if snap.uid_sid else f"user={snap.username}",
            candidate_identities=candidates[:5],
        ))

    return {"suggestions": results}


@router.get("/{identity_id}", response_model=schemas.HumanIdentityResponse)
async def get_identity(
    identity_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.get_current_user),
):
    """Get full details of one identity including all linked accounts."""
    ident = db.query(models.HumanIdentity).filter(
        models.HumanIdentity.id == identity_id
    ).first()
    if not ident:
        raise HTTPException(status_code=404, detail="Identity not found")

    links = db.query(models.IdentityAccount).filter(
        models.IdentityAccount.identity_id == identity_id
    ).all()

    snap_ids = [l.snapshot_id for l in links]
    asset_ids = list({l.asset_id for l in links})

    snaps = db.query(models.AccountSnapshot).filter(
        models.AccountSnapshot.id.in_(snap_ids)
    ).all()
    snap_by_id = {s.id: s for s in snaps}

    assets = db.query(models.Asset).filter(models.Asset.id.in_(asset_ids)).all()
    assets_map = {a.id: a for a in assets}

    snaps_assets = db.query(models.AccountSnapshot).filter(
        models.AccountSnapshot.id.in_(snap_ids)
    ).all()

    profiles = db.query(models.AssetRiskProfile).filter(
        models.AssetRiskProfile.asset_id.in_(asset_ids)
    ).all()
    risk_map = {p.asset_id: p.risk_score for p in profiles}

    admin_count = sum(1 for s in snaps if s.is_admin)
    latest_login = max((s.last_login for s in snaps if s.last_login), default=None)
    max_risk = max((risk_map.get(l.asset_id, 0) for l in links), default=0)

    account_items = [
        schemas.IdentityAccountItem(
            id=l.id,
            snapshot_id=l.snapshot_id,
            asset_id=l.asset_id,
            asset_code=assets_map.get(l.asset_id, models.Asset(asset_code="?", ip="?")).asset_code,
            ip=assets_map.get(l.asset_id, models.Asset(ip="?")).ip,
            hostname=assets_map.get(l.asset_id, models.Asset(hostname=None)).hostname,
            username=snap_by_id.get(l.snapshot_id, models.AccountSnapshot(username="?", uid_sid="")).username,
            uid_sid=snap_by_id.get(l.snapshot_id, models.AccountSnapshot(uid_sid="")).uid_sid,
            is_admin=snap_by_id.get(l.snapshot_id, models.AccountSnapshot(is_admin=False)).is_admin,
            account_status=snap_by_id.get(l.snapshot_id, models.AccountSnapshot(account_status=None)).account_status,
            last_login=snap_by_id.get(l.snapshot_id, models.AccountSnapshot(last_login=None)).last_login,
            match_type=l.match_type,
            match_confidence=l.match_confidence,
        )
        for l in links
    ]

    return schemas.HumanIdentityResponse(
        id=ident.id,
        display_name=ident.display_name,
        email=ident.email,
        confidence=ident.confidence,
        source=ident.source,
        account_count=len(snaps),
        admin_count=admin_count,
        asset_count=len(asset_ids),
        max_risk_score=max_risk,
        latest_login=latest_login,
        accounts=account_items,
    )


@router.post("/link")
async def link_account(
    req: schemas.IdentityLinkRequest,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.require_role(models.UserRole.admin)),
):
    """Manually link a snapshot to an existing identity."""
    ident = db.query(models.HumanIdentity).filter(
        models.HumanIdentity.id == req.identity_id
    ).first()
    if not ident:
        raise HTTPException(status_code=404, detail="Identity not found")

    snap = db.query(models.AccountSnapshot).filter(
        models.AccountSnapshot.id == req.snapshot_id
    ).first()
    if not snap:
        raise HTTPException(status_code=404, detail="Snapshot not found")

    existing = db.query(models.IdentityAccount).filter(
        models.IdentityAccount.identity_id == req.identity_id,
        models.IdentityAccount.snapshot_id == req.snapshot_id,
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Already linked")

    link = models.IdentityAccount(
        identity_id=req.identity_id,
        snapshot_id=req.snapshot_id,
        asset_id=snap.asset_id,
        match_type=req.match_type,
        match_confidence=req.match_confidence,
    )
    db.add(link)
    ident.source = "manual"
    ident.confidence = max(ident.confidence, req.match_confidence)
    db.commit()
    return {"success": True, "link_id": link.id}


@router.delete("/{identity_id}/unlink/{link_id}")
async def unlink_account(
    identity_id: int,
    link_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.require_role(models.UserRole.admin)),
):
    """Unlink an account from an identity."""
    link = db.query(models.IdentityAccount).filter(
        models.IdentityAccount.id == link_id,
        models.IdentityAccount.identity_id == identity_id,
    ).first()
    if not link:
        raise HTTPException(status_code=404, detail="Link not found")
    db.delete(link)
    db.commit()
    return {"success": True}


@router.post("/re-match")
async def rematch_identities(
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.require_role(models.UserRole.admin)),
):
    """Trigger full identity re-matching across all assets."""
    result = fuse_identities(db)
    return {"success": True, **result}
