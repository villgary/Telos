"""AI Agent Management API — first-class identity governance."""
from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend import models, schemas, auth
from backend.database import get_db
from backend.services.ai_agent_scanner import ingest_signals


router = APIRouter(prefix="/api/v1/ai-agents", tags=["ai-agents"])


@router.get("", response_model=schemas.ai_agents.AIAgentListResponse)
async def list_ai_agents(
    framework: Optional[str] = None,
    risk_level: Optional[str] = None,
    status: Optional[str] = None,
    owner_team: Optional[str] = None,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.get_current_user),
):
    query = db.query(models.AIAgent)
    if framework:
        query = query.filter(models.AIAgent.framework == framework)
    if risk_level:
        query = query.filter(models.AIAgent.risk_level == risk_level)
    if status:
        query = query.filter(models.AIAgent.status == status)
    if owner_team:
        query = query.filter(models.AIAgent.owner_team == owner_team)

    total = query.count()
    agents = (
        query.order_by(models.AIAgent.risk_score.desc(), models.AIAgent.last_seen_at.desc())
        .offset(offset).limit(limit).all()
    )
    return schemas.ai_agents.AIAgentListResponse(
        total=total,
        agents=[schemas.ai_agents.AIAgentResponse.model_validate(a) for a in agents],
    )


@router.get("/stats", response_model=schemas.ai_agents.AIAgentStatsResponse)
async def get_stats(
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.get_current_user),
):
    total = db.query(func.count(models.AIAgent.id)).scalar() or 0
    active = (
        db.query(func.count(models.AIAgent.id))
        .filter(models.AIAgent.status == "active")
        .scalar() or 0
    )
    critical_risk = (
        db.query(func.count(models.AIAgent.id))
        .filter(models.AIAgent.risk_level == "critical")
        .scalar() or 0
    )
    no_owner = (
        db.query(func.count(models.AIAgent.id))
        .filter(
            models.AIAgent.owner_user.is_(None),
            models.AIAgent.owner_team.is_(None),
        )
        .scalar() or 0
    )

    framework_rows = (
        db.query(models.AIAgent.framework, func.count(models.AIAgent.id))
        .group_by(models.AIAgent.framework).all()
    )
    risk_rows = (
        db.query(models.AIAgent.risk_level, func.count(models.AIAgent.id))
        .group_by(models.AIAgent.risk_level).all()
    )

    return schemas.ai_agents.AIAgentStatsResponse(
        total=total,
        active=active,
        critical_risk=critical_risk,
        no_owner=no_owner,
        by_framework={fw: cnt for fw, cnt in framework_rows},
        by_risk_level={rl: cnt for rl, cnt in risk_rows},
    )


@router.get("/{agent_id}", response_model=schemas.ai_agents.AIAgentDetailResponse)
async def get_ai_agent(
    agent_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.get_current_user),
):
    agent = db.query(models.AIAgent).filter(models.AIAgent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="AI Agent not found")
    return agent


@router.post("/{agent_id}/claim", response_model=schemas.ai_agents.AIAgentDetailResponse)
async def claim_ai_agent(
    agent_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.get_current_user),
):
    """Sets owner_user to the current authenticated user (v1)."""
    agent = db.query(models.AIAgent).filter(models.AIAgent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="AI Agent not found")
    agent.owner_user = user.username
    db.commit()
    db.refresh(agent)
    return agent


@router.post("/scan", response_model=schemas.ai_agents.AIAgentScanResponse)
async def trigger_scan(
    request: schemas.ai_agents.AIAgentScanRequest,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.require_role(models.UserRole.operator, models.UserRole.admin)),
):
    """Re-ingest AI Agent signals from AccountSnapshot.raw_info for the
    given asset (or all assets if asset_id is None).

    v1 does not run a fresh SSH scan — it re-parses already-collected
    raw_info. Live SSH scanning happens via the existing /scans trigger.
    """
    query = db.query(models.AccountSnapshot).filter(
        models.AccountSnapshot.deleted_at.is_(None),
        models.AccountSnapshot.raw_info.isnot(None),
    )
    if request.asset_id is not None:
        query = query.filter(models.AccountSnapshot.asset_id == request.asset_id)
    snapshots = query.all()

    agents_discovered = 0
    agents_updated = 0
    errors: List[str] = []
    for snap in snapshots:
        try:
            new_agents = ingest_signals(db, snap.raw_info, snap.asset_id)
            for a in new_agents:
                if a.discovered_at and a.discovered_at > (
                    datetime.utcnow().replace(microsecond=0)
                ):
                    agents_discovered += 1
                else:
                    agents_updated += 1
        except Exception as e:
            errors.append(f"snapshot {snap.id}: {e}")
    db.commit()

    return schemas.ai_agents.AIAgentScanResponse(
        scanned_assets=len({s.asset_id for s in snapshots if s.asset_id}),
        agents_discovered=agents_discovered,
        agents_updated=agents_updated,
        alerts_emitted=0,  # realtime monitor handles alerts on next tick
        errors=errors,
    )
