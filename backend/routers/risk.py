"""
Risk Propagation API — risk profiles, hotspots, and lateral movement analysis.
"""

from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from collections import defaultdict

from backend.database import get_db
from backend import models, schemas, auth
from backend.services.risk_propagation import propagate_risk
from backend.services.account_risk_score import compute_account_score, compute_all_scores

router = APIRouter(prefix="/api/v1/risk", tags=["风险传播"])


@router.post("/propagate")
async def trigger_propagation(
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.require_role(models.UserRole.admin)),
):
    """
    Trigger full risk propagation across all assets.
    Recomputes risk scores bottom-up through the asset topology.
    Admin only.
    """
    result = propagate_risk(db)
    return {"success": True, **result}


@router.get("/profile/{asset_id}", response_model=schemas.AssetRiskProfileResponse)
async def get_risk_profile(
    asset_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.get_current_user),
):
    """
    Get the risk profile for a single asset including propagation path.
    """
    profile = db.query(models.AssetRiskProfile).filter(
        models.AssetRiskProfile.asset_id == asset_id
    ).first()

    if not profile:
        # Compute on demand if not yet computed
        propagate_risk(db)
        profile = db.query(models.AssetRiskProfile).filter(
            models.AssetRiskProfile.asset_id == asset_id
        ).first()

    if not profile:
        raise HTTPException(status_code=404, detail="资产不存在")

    asset = db.query(models.Asset).filter(models.Asset.id == asset_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="资产不存在")

    # Build propagation path with full asset info
    path_nodes = []
    raw_path = profile.propagation_path or []
    for node in raw_path:
        a = db.query(models.Asset).filter(models.Asset.id == node["asset_id"]).first()
        if a:
            path_nodes.append(schemas.PropagationNode(
                asset_code=a.asset_code,
                ip=a.ip,
                hostname=a.hostname,
                risk_score=node.get("risk_score", 0),
                relation=node.get("relation"),
                is_entry_point=node.get("is_entry_point", False),
            ))

    # Build risk factors
    factor_items = [
        schemas.RiskFactorItem(
            factor=f["factor"],
            score=f["score"],
            description=f.get("description"),
            target=f.get("target"),
        )
        for f in (profile.risk_factors or [])
    ]

    return schemas.AssetRiskProfileResponse(
        asset=schemas.AssetSummary(
            id=asset.id,
            asset_code=asset.asset_code,
            ip=asset.ip,
            hostname=asset.hostname,
            asset_category=asset.asset_category,
            account_count=0,
            admin_count=0,
            latest_accounts=[],
        ),
        risk_score=profile.risk_score,
        risk_level=profile.risk_level,
        risk_factors=factor_items,
        affected_children_count=profile.affected_children,
        propagation_path=path_nodes,
        computed_at=profile.computed_at,
    )


@router.get("/overview")
async def get_risk_overview(
    limit: int = 50,
    offset: int = 0,
    min_score: int = 0,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.get_current_user),
):
    """
    Get risk overview for all assets (sorted by risk score descending).
    """
    profiles = db.query(models.AssetRiskProfile).filter(
        models.AssetRiskProfile.risk_score >= min_score
    ).order_by(
        models.AssetRiskProfile.risk_score.desc()
    ).offset(offset).limit(limit).all()

    result = []
    for p in profiles:
        asset = db.query(models.Asset).filter(models.Asset.id == p.asset_id).first()
        if asset:
            result.append(schemas.RiskOverviewItem(
                asset_id=asset.id,
                asset_code=asset.asset_code,
                ip=asset.ip,
                hostname=asset.hostname,
                risk_score=p.risk_score,
                risk_level=p.risk_level,
                affected_children_count=p.affected_children,
            ))

    total = db.query(models.AssetRiskProfile).filter(
        models.AssetRiskProfile.risk_score >= min_score
    ).count()

    return {"total": total, "results": result}


@router.get("/hotspots")
async def get_risk_hotspots(
    threshold: int = 60,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.get_current_user),
):
    """
    Get high-risk lateral movement paths.
    A hotspot is a chain from a high-risk leaf asset to a root,
    where the path represents potential lateral movement risk.
    """
    # Get all high-risk profiles
    profiles = db.query(models.AssetRiskProfile).filter(
        models.AssetRiskProfile.risk_score >= threshold
    ).all()

    all_rels = db.query(models.AssetRelationship).all()

    # Build child → parent mapping
    parent_map: dict[int, int] = {}  # child_id → parent_id
    for rel in all_rels:
        parent_map[rel.child_id] = rel.parent_id

    hotspots: list[dict] = []

    # Pre-fetch all assets for node building
    all_asset_ids = set(parent_map.keys()) | {p.asset_id for p in profiles}
    assets_in_map = {a.id: a for a in db.query(models.Asset).filter(
        models.Asset.id.in_(all_asset_ids)
    ).all()}
    profiles_map = {p.asset_id: p for p in profiles}

    # Build relation type map: child_id → relation_type
    rel_type_map: dict[int, str] = {}
    for rel in all_rels:
        rel_type_map[rel.child_id] = rel.relation_type.value if hasattr(rel.relation_type, 'value') else str(rel.relation_type)

    for profile in profiles:
        asset = assets_in_map.get(profile.asset_id)
        if not asset:
            continue

        # Walk up to find root
        chain: list[dict] = [{"asset_id": asset.id, "asset_code": asset.asset_code, "ip": asset.ip}]
        current_id = asset.id
        root_id = current_id
        while current_id in parent_map:
            parent_id = parent_map[current_id]
            parent = assets_in_map.get(parent_id)
            if not parent:
                break
            chain.append({"asset_id": parent.id, "asset_code": parent.asset_code, "ip": parent.ip})
            root_id = parent.id
            current_id = parent.id

        if len(chain) < 2:
            continue  # No propagation path, skip

        # Build structured nodes for visualization
        nodes: list[schemas.PropagationNode] = []
        for i, node_data in enumerate(chain):
            node_asset = assets_in_map.get(node_data["asset_id"])
            if not node_asset:
                continue
            node_profile = profiles_map.get(node_asset.id)
            rel_type = rel_type_map.get(node_data["asset_id"]) if i > 0 else None
            nodes.append(schemas.PropagationNode(
                asset_code=node_asset.asset_code,
                ip=node_asset.ip,
                hostname=node_asset.hostname,
                risk_score=node_profile.risk_score if node_profile else 0,
                relation=rel_type,
                is_entry_point=(i == 0),
            ))

        # Build description
        top_factors = profile.risk_factors[:2] if profile.risk_factors else []
        factor_desc = "；".join([f"{f['factor']}(+{f['score']})" for f in top_factors]) if top_factors else "高风险资产"

        path_str = " → ".join([c["asset_code"] for c in chain])

        hotspots.append({
            "entry_asset": {
                "asset_code": asset.asset_code,
                "ip": asset.ip,
                "hostname": asset.hostname,
                "risk_score": profile.risk_score,
            },
            "root_asset": {
                "asset_code": chain[-1]["asset_code"],
                "ip": chain[-1]["ip"],
            },
            "max_risk_score": profile.risk_score,
            "path": [path_str],
            "risk_description": f"{asset.asset_code}({factor_desc}) → {chain[-1]['asset_code']}(共{len(chain)}层)",
            "chain_length": len(chain),
            "nodes": [n.model_dump() for n in nodes],
        })

    # Sort by max_risk_score descending
    hotspots.sort(key=lambda h: h["max_risk_score"], reverse=True)

    return {"hotspots": [schemas.RiskHotspotItem.model_validate(h) for h in hotspots[:20]]}


# ── Account Risk Score ────────────────────────────────────────────────────────────

@router.get("/account/{snapshot_id}", response_model=schemas.AccountRiskScoreResponse)
async def get_account_risk(
    snapshot_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.get_current_user),
):
    """Get risk score for a single account snapshot."""
    score = db.query(models.AccountRiskScore).filter(
        models.AccountRiskScore.snapshot_id == snapshot_id
    ).first()

    snapshot = db.query(models.AccountSnapshot).filter(
        models.AccountSnapshot.id == snapshot_id
    ).first()
    if not snapshot:
        raise HTTPException(status_code=404, detail="快照不存在")

    if not score:
        score = compute_account_score(db, snapshot)

    asset = db.query(models.Asset).filter(models.Asset.id == snapshot.asset_id).first()

    return schemas.AccountRiskScoreResponse(
        id=score.id,
        snapshot_id=score.snapshot_id,
        risk_score=score.risk_score,
        risk_level=score.risk_level,
        risk_factors=score.risk_factors or [],
        identity_id=score.identity_id,
        cross_asset_count=score.cross_asset_count,
        computed_at=score.computed_at,
        username=snapshot.username,
        asset_code=asset.asset_code if asset else None,
        asset_ip=asset.ip if asset else None,
        is_admin=snapshot.is_admin,
        last_login=snapshot.last_login,
        owner_identity_id=snapshot.owner_identity_id,
        owner_email=snapshot.owner_email,
        owner_name=snapshot.owner_name,
    )


@router.get("/accounts")
async def list_account_risks(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    min_score: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.get_current_user),
):
    """List account risk scores sorted by score descending."""
    query = db.query(models.AccountRiskScore).filter(
        models.AccountRiskScore.risk_score >= min_score
    ).order_by(models.AccountRiskScore.risk_score.desc())

    total = query.count()
    items = query.offset(offset).limit(limit).all()

    result = []
    for s in items:
        snapshot = db.query(models.AccountSnapshot).filter(
            models.AccountSnapshot.id == s.snapshot_id
        ).first()
        if not snapshot:
            continue
        asset = db.query(models.Asset).filter(models.Asset.id == snapshot.asset_id).first()
        result.append(schemas.AccountRiskScoreResponse(
            id=s.id,
            snapshot_id=s.snapshot_id,
            risk_score=s.risk_score,
            risk_level=s.risk_level,
            risk_factors=s.risk_factors or [],
            identity_id=s.identity_id,
            cross_asset_count=s.cross_asset_count,
            computed_at=s.computed_at,
            username=snapshot.username,
            asset_code=asset.asset_code if asset else None,
            asset_ip=asset.ip if asset else None,
            is_admin=snapshot.is_admin,
            last_login=snapshot.last_login,
            owner_identity_id=snapshot.owner_identity_id,
            owner_email=snapshot.owner_email,
            owner_name=snapshot.owner_name,
        ))

    return {"total": total, "results": result}


@router.post("/accounts/recompute")
async def recompute_account_risks(
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.require_role(models.UserRole.admin)),
):
    """Recompute risk scores for all accounts (admin only)."""
    result = compute_all_scores(db)
    return {"success": True, **result}
