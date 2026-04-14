"""
Security Policies API — OPA/Rego Policy Engine.
"""

from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional

from backend.database import get_db
from backend import models, auth
from backend.services.policy_engine import evaluate_all_policies, evaluate_policy, parse_rule

router = APIRouter(prefix="/api/v1/policies", tags=["安全策略"])


# ── Schemas ──────────────────────────────────────────────────────────────────

class PolicyCreate(BaseModel):
    name: str
    description: Optional[str] = None
    category: Optional[str] = None
    severity: str = "high"
    rego_code: str
    enabled: bool = True


class PolicyUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    severity: Optional[str] = None
    rego_code: Optional[str] = None
    enabled: Optional[bool] = None


class PolicyResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    name_key: Optional[str] = None
    description_key: Optional[str] = None
    category: Optional[str]
    severity: str
    rego_code: str
    enabled: bool
    is_built_in: bool
    created_at: datetime

    model_config = {"from_attributes": True, "extra": "forbid"}


# ── Policy Evaluation (literal paths — must be registered BEFORE /{policy_id}) ──

@router.get("/policy-results")
async def get_results(
    days: int = Query(7, ge=1, le=90),
    policy_id: Optional[int] = None,
    passed: Optional[bool] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.get_current_user),
):
    """Get policy evaluation results (last N days)."""
    q = db.query(models.PolicyEvaluationResult).filter(
        models.PolicyEvaluationResult.evaluated_at >= datetime.now(timezone.utc) - timedelta(days=days)
    )
    if policy_id:
        q = q.filter(models.PolicyEvaluationResult.policy_id == policy_id)
    if passed is not None:
        q = q.filter(models.PolicyEvaluationResult.passed == passed)

    total = q.count()
    rows = q.order_by(models.PolicyEvaluationResult.evaluated_at.desc()).offset(offset).limit(limit).all()

    # Fetch related data
    snapshot_ids = list(set(r.snapshot_id for r in rows))
    policy_ids = list(set(r.policy_id for r in rows))
    snapshots_map = {s.id: s for s in db.query(models.AccountSnapshot).filter(models.AccountSnapshot.id.in_(snapshot_ids)).all()}
    assets_map = {a.id: a for s in snapshots_map.values() for a in [db.query(models.Asset).filter(models.Asset.id == s.asset_id).first()] if a}
    policies_map = {p.id: p for p in db.query(models.SecurityPolicy).filter(models.SecurityPolicy.id.in_(policy_ids)).all()}

    return {
        "total": total,
        "results": [
            {
                "id": r.id,
                "policy_id": r.policy_id,
                "policy_name": policies_map.get(r.policy_id, models.SecurityPolicy()).name if r.policy_id in policies_map else "",
                "policy_name_key": policies_map.get(r.policy_id, models.SecurityPolicy()).name_key if r.policy_id in policies_map else None,
                "snapshot_id": r.snapshot_id,
                "username": snapshots_map.get(r.snapshot_id, models.AccountSnapshot()).username if r.snapshot_id in snapshots_map else "",
                "asset_code": assets_map.get(snapshots_map.get(r.snapshot_id, models.AccountSnapshot()).asset_id, models.Asset()).asset_code if r.snapshot_id in snapshots_map and snapshots_map[r.snapshot_id].asset_id in assets_map else None,
                "passed": r.passed,
                "message": r.message,
                "evaluated_at": r.evaluated_at.isoformat() if r.evaluated_at else None,
            }
            for r in rows
        ],
    }


@router.post("/evaluate-all")
async def evaluate_all(
    snapshot_id: int = Query(..., description="Account snapshot ID to evaluate all policies against"),
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.get_current_user),
):
    """Evaluate all enabled policies against a single account snapshot."""
    snapshot = db.query(models.AccountSnapshot).filter(models.AccountSnapshot.id == snapshot_id).first()
    if not snapshot:
        raise HTTPException(status_code=404, detail="快照不存在")
    asset = db.query(models.Asset).filter(models.Asset.id == snapshot.asset_id).first()

    results = evaluate_all_policies(snapshot, asset, db)
    failed = [r for r in results if not r["passed"]]

    return {
        "snapshot_id": snapshot_id,
        "username": snapshot.username,
        "asset_code": asset.asset_code if asset else None,
        "total_policies": len(results),
        "passed": len(results) - len(failed),
        "failed": len(failed),
        "results": [
            {
                "policy_id": r["policy_id"],
                "policy_name": r["policy_name"],
                "policy_name_key": r.get("policy_name_key"),
                "severity": r.get("severity", "high"),
                "passed": r["passed"],
                "message": r.get("message"),
            }
            for r in results
        ],
        "violations": [
            {
                "policy_id": r["policy_id"],
                "policy_name": r["policy_name"],
                "policy_name_key": r.get("policy_name_key"),
                "severity": r.get("severity", "high"),
                "message": r.get("message"),
            }
            for r in failed
        ],
    }


# ── CRUD ─────────────────────────────────────────────────────────────────────

@router.get("", response_model=list[PolicyResponse])
async def list_policies(
    category: Optional[str] = None,
    enabled: Optional[bool] = None,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.get_current_user),
):
    """List all security policies."""
    q = db.query(models.SecurityPolicy)
    if category:
        q = q.filter(models.SecurityPolicy.category == category)
    if enabled is not None:
        q = q.filter(models.SecurityPolicy.enabled == enabled)
    return q.order_by(models.SecurityPolicy.is_built_in.desc(), models.SecurityPolicy.id).all()


@router.get("/{policy_id}", response_model=PolicyResponse)
async def get_policy(
    policy_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.get_current_user),
):
    """Get a single policy by ID."""
    pol = db.query(models.SecurityPolicy).filter(models.SecurityPolicy.id == policy_id).first()
    if not pol:
        raise HTTPException(status_code=404, detail="策略不存在")
    return pol


@router.post("", response_model=PolicyResponse)
async def create_policy(
    data: PolicyCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.require_role(models.UserRole.admin)),
):
    """Create a new security policy (admin only)."""
    # Validate Rego code parses
    try:
        parse_rule(data.rego_code)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Rego 解析错误: {e}")

    pol = models.SecurityPolicy(
        name=data.name,
        description=data.description,
        category=data.category,
        severity=data.severity,
        rego_code=data.rego_code,
        enabled=data.enabled,
        created_by=user.id,
    )
    db.add(pol)
    db.commit()
    db.refresh(pol)
    return pol


@router.put("/{policy_id}", response_model=PolicyResponse)
async def update_policy(
    policy_id: int,
    data: PolicyUpdate,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.require_role(models.UserRole.admin)),
):
    """Update a security policy (admin only). Built-in policies cannot be deleted."""
    pol = db.query(models.SecurityPolicy).filter(models.SecurityPolicy.id == policy_id).first()
    if not pol:
        raise HTTPException(status_code=404, detail="策略不存在")

    if data.name is not None:
        pol.name = data.name
    if data.description is not None:
        pol.description = data.description
    if data.category is not None:
        pol.category = data.category
    if data.severity is not None:
        pol.severity = data.severity
    if data.rego_code is not None:
        try:
            parse_rule(data.rego_code)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Rego 解析错误: {e}")
        pol.rego_code = data.rego_code
    if data.enabled is not None:
        pol.enabled = data.enabled

    pol.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(pol)
    return pol


@router.delete("/{policy_id}")
async def delete_policy(
    policy_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.require_role(models.UserRole.admin)),
):
    """Delete a policy (admin only). Built-in policies cannot be deleted."""
    pol = db.query(models.SecurityPolicy).filter(models.SecurityPolicy.id == policy_id).first()
    if not pol:
        raise HTTPException(status_code=404, detail="策略不存在")
    if pol.is_built_in:
        raise HTTPException(status_code=403, detail="内置策略不可删除")
    db.delete(pol)
    db.commit()
    return {"success": True}


# ── Single-policy evaluation ──────────────────────────────────────────────────

@router.post("/{policy_id}/evaluate/{snapshot_id}")
async def evaluate_single(
    policy_id: int,
    snapshot_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.get_current_user),
):
    """Evaluate a single policy against a single account snapshot."""
    pol = db.query(models.SecurityPolicy).filter(models.SecurityPolicy.id == policy_id).first()
    if not pol:
        raise HTTPException(status_code=404, detail="策略不存在")
    snapshot = db.query(models.AccountSnapshot).filter(models.AccountSnapshot.id == snapshot_id).first()
    if not snapshot:
        raise HTTPException(status_code=404, detail="快照不存在")
    asset = db.query(models.Asset).filter(models.Asset.id == snapshot.asset_id).first()

    result = evaluate_policy(pol, snapshot, asset)

    # Persist
    eval_result = models.PolicyEvaluationResult(
        policy_id=policy_id,
        snapshot_id=snapshot_id,
        passed=result["passed"],
        message=result.get("message"),
        evaluated_at=datetime.now(timezone.utc),
    )
    db.add(eval_result)
    db.commit()

    return {
        "policy_id": policy_id,
        "policy_name": pol.name,
        "snapshot_id": snapshot_id,
        "username": snapshot.username,
        "asset_code": asset.asset_code if asset else None,
        "passed": result["passed"],
        "message": result.get("message"),
        "evaluated_at": eval_result.evaluated_at.isoformat(),
    }
