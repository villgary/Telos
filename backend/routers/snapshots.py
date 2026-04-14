from datetime import datetime, timedelta, timezone
from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import get_db
from backend import models, schemas, auth
from backend.services import diff_engine

router = APIRouter(prefix="/api/v1/snapshots", tags=["快照与差异"])


@router.get("/diff", response_model=schemas.DiffResponse)
async def diff_snapshots(
    base_job_id: int = Query(..., description="基准快照任务 ID"),
    compare_job_id: int = Query(..., description="对比快照任务 ID"),
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.get_current_user),
):
    """Compare two scan job snapshots and return differences."""
    job_a = db.query(models.ScanJob).filter(models.ScanJob.id == base_job_id).first()
    job_b = db.query(models.ScanJob).filter(models.ScanJob.id == compare_job_id).first()
    if not job_a:
        raise HTTPException(status_code=404, detail=f"基准扫描任务 {base_job_id} 不存在")
    if not job_b:
        raise HTTPException(status_code=404, detail=f"对比扫描任务 {compare_job_id} 不存在")
    if job_a.asset_id != job_b.asset_id:
        raise HTTPException(status_code=400, detail="两次扫描任务必须针对同一资产")

    snap_a = (
        db.query(models.AccountSnapshot)
        .filter(models.AccountSnapshot.job_id == base_job_id)
        .all()
    )
    snap_b = (
        db.query(models.AccountSnapshot)
        .filter(models.AccountSnapshot.job_id == compare_job_id)
        .all()
    )

    items, summary = diff_engine.compute_diff(snap_a, snap_b)
    return schemas.DiffResponse(
        base_job_id=base_job_id,
        compare_job_id=compare_job_id,
        items=items,
        summary=summary,
    )


@router.get("/by-asset/{asset_id}", response_model=list[schemas.ScanJobResponse])
async def list_jobs_by_asset(
    asset_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.get_current_user),
):
    """List all scan jobs for a specific asset."""
    return (
        db.query(models.ScanJob)
        .filter(models.ScanJob.asset_id == asset_id)
        .order_by(models.ScanJob.created_at.desc())
        .all()
    )


class AssetAccountSummary(BaseModel):
    """Lightweight account info for asset detail drawer."""
    id: int
    username: str
    uid_sid: str
    is_admin: bool
    account_status: Optional[str] = None
    home_dir: Optional[str] = None
    shell: Optional[str] = None
    groups: List[Any] = []
    last_login: Optional[str] = None
    snapshot_time: Optional[datetime] = None
    is_baseline: bool = False
    owner_identity_id: Optional[int] = None
    owner_email: Optional[str] = None
    owner_name: Optional[str] = None
    has_credential_findings: bool = False
    has_nopasswd_sudo: bool = False

    class Config:
        from_attributes = True


@router.get("/by-asset/{asset_id}/accounts", response_model=List[AssetAccountSummary])
async def list_asset_accounts(
    asset_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.get_current_user),
):
    """Return the latest snapshot for each username on an asset (for asset detail drawer)."""
    from sqlalchemy import func

    # Latest snapshot per username for this asset
    subq = (
        db.query(
            models.AccountSnapshot.username,
            func.max(models.AccountSnapshot.id).label("latest_id"),
        )
        .filter(
            models.AccountSnapshot.asset_id == asset_id,
            models.AccountSnapshot.deleted_at.is_(None),
        )
        .group_by(models.AccountSnapshot.username)
        .subquery()
    )

    snapshots = (
        db.query(models.AccountSnapshot)
        .join(subq, models.AccountSnapshot.id == subq.c.latest_id)
        .order_by(
            models.AccountSnapshot.is_admin.desc(),
            models.AccountSnapshot.username,
        )
        .all()
    )

    result = []
    for s in snapshots:
        raw = s.raw_info or {}
        cred_findings = raw.get("credential_findings") or []
        sudo_cfg = raw.get("sudo_config") or {}
        nopasswd = sudo_cfg.get("nopasswd_sudo") if isinstance(sudo_cfg, dict) else False
        result.append(AssetAccountSummary(
            id=s.id,
            username=s.username,
            uid_sid=s.uid_sid,
            is_admin=s.is_admin,
            account_status=s.account_status,
            home_dir=s.home_dir,
            shell=s.shell,
            groups=s.groups or [],
            last_login=str(s.last_login) if s.last_login else None,
            snapshot_time=s.snapshot_time,
            is_baseline=s.is_baseline,
            owner_identity_id=s.owner_identity_id,
            owner_email=s.owner_email,
            owner_name=s.owner_name,
            has_credential_findings=len(cred_findings) > 0,
            has_nopasswd_sudo=bool(nopasswd),
        ))
    return result


@router.get("/recent")
async def list_recent_snapshots(
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.get_current_user),
):
    """Return recent account snapshots for policy evaluation selection."""
    from sqlalchemy import func
    # Latest snapshot per (username, asset_id) — sorted by snapshot_time desc
    subq = (
        db.query(
            models.AccountSnapshot.username,
            models.AccountSnapshot.asset_id,
            func.max(models.AccountSnapshot.id).label("latest_id"),
        )
        .filter(models.AccountSnapshot.deleted_at.is_(None))
        .group_by(models.AccountSnapshot.username, models.AccountSnapshot.asset_id)
        .subquery()
    )
    snapshots = (
        db.query(models.AccountSnapshot)
        .join(
            subq,
            models.AccountSnapshot.id == subq.c.latest_id,
        )
        .order_by(models.AccountSnapshot.snapshot_time.desc())
        .limit(limit)
        .all()
    )
    asset_ids = list(set(s.asset_id for s in snapshots))
    assets_map = {a.id: a for a in db.query(models.Asset).filter(models.Asset.id.in_(asset_ids)).all()}

    return [
        {
            "id": s.id,
            "username": s.username,
            "asset_id": s.asset_id,
            "asset_code": assets_map.get(s.asset_id, models.Asset()).asset_code if s.asset_id in assets_map else None,
            "asset_ip": assets_map.get(s.asset_id, models.Asset()).ip if s.asset_id in assets_map else None,
            "is_admin": s.is_admin,
            "snapshot_time": s.snapshot_time.isoformat() if s.snapshot_time else None,
            "last_login": s.last_login.isoformat() if s.last_login else None,
        }
        for s in snapshots
    ]


@router.get("/ownerless", response_model=list[schemas.SnapshotOwnerResponse])
async def list_ownerless_snapshots(
    is_admin: bool = Query(False, description="仅统计特权账号"),
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.get_current_user),
):
    """
    列出所有未设置归属人的账号快照（高风险信号）。
    用于推动运维人员主动填写归属人。
    """
    q = db.query(models.AccountSnapshot).filter(
        models.AccountSnapshot.deleted_at.is_(None),
        models.AccountSnapshot.owner_identity_id.is_(None),
    )
    if is_admin:
        q = q.filter(models.AccountSnapshot.is_admin == True)  # noqa: E712

    snapshots = q.order_by(models.AccountSnapshot.snapshot_time.desc()).limit(200).all()
    return [
        schemas.SnapshotOwnerResponse(
            snapshot_id=s.id,
            username=s.username,
            asset_id=s.asset_id,
            owner_identity_id=s.owner_identity_id,
            owner_email=s.owner_email,
            owner_name=s.owner_name,
        )
        for s in snapshots
    ]


@router.get("/{snapshot_id}/owner", response_model=schemas.SnapshotOwnerResponse)
async def get_snapshot_owner(
    snapshot_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.get_current_user),
):
    """获取指定账号快照的归属人信息。"""
    snap = db.query(models.AccountSnapshot).filter(
        models.AccountSnapshot.id == snapshot_id
    ).first()
    if not snap:
        raise HTTPException(status_code=404, detail="账号快照不存在")

    return schemas.SnapshotOwnerResponse(
        snapshot_id=snap.id,
        username=snap.username,
        asset_id=snap.asset_id,
        owner_identity_id=snap.owner_identity_id,
        owner_email=snap.owner_email,
        owner_name=snap.owner_name,
    )


@router.patch("/{snapshot_id}/owner", response_model=schemas.SnapshotOwnerResponse)
async def set_snapshot_owner(
    snapshot_id: int,
    body: schemas.SnapshotOwnerAssign,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.get_current_user),
):
    """
    设置账号快照的归属人。
    优先通过 email 查找 HumanIdentity 并建立关联；
    同时在 owner_email / owner_name 冗余存储。
    """
    snap = db.query(models.AccountSnapshot).filter(
        models.AccountSnapshot.id == snapshot_id
    ).first()
    if not snap:
        raise HTTPException(status_code=404, detail="账号快照不存在")

    owner_identity_id = None
    if body.owner_email:
        # 查找或提示 HumanIdentity
        identity = db.query(models.HumanIdentity).filter(
            models.HumanIdentity.email == body.owner_email
        ).first()
        if identity:
            owner_identity_id = identity.id
            # 同步冗余字段
            snap.owner_identity_id = identity.id
            snap.owner_email = identity.email
            snap.owner_name = identity.display_name or body.owner_name
        else:
            # 没有 HumanIdentity 记录，仅用冗余字段
            snap.owner_email = body.owner_email
            snap.owner_name = body.owner_name
    elif body.owner_name:
        snap.owner_name = body.owner_name

    db.commit()
    db.refresh(snap)
    return schemas.SnapshotOwnerResponse(
        snapshot_id=snap.id,
        username=snap.username,
        asset_id=snap.asset_id,
        owner_identity_id=snap.owner_identity_id,
        owner_email=snap.owner_email,
        owner_name=snap.owner_name,
    )


@router.post("/bulk-set-owner")
async def bulk_set_snapshot_owner(
    body: dict,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.get_current_user),
):
    """
    批量设置账号快照归属人。
    Body: {"snapshot_ids": [1,2,3], "owner_email": "zhangsan@company.com", "owner_name": "张三"}
    """
    snapshot_ids = body.get("snapshot_ids", [])
    owner_email = body.get("owner_email")
    owner_name = body.get("owner_name")

    if not snapshot_ids or not owner_email:
        raise HTTPException(status_code=400, detail="snapshot_ids 和 owner_email 均不能为空")

    snapshots = db.query(models.AccountSnapshot).filter(
        models.AccountSnapshot.id.in_(snapshot_ids)
    ).all()

    if not snapshots:
        raise HTTPException(status_code=404, detail="未找到任何匹配的账号快照")

    identity = db.query(models.HumanIdentity).filter(
        models.HumanIdentity.email == owner_email
    ).first()

    updated = 0
    for snap in snapshots:
        if identity:
            snap.owner_identity_id = identity.id
            snap.owner_email = identity.email
            snap.owner_name = identity.display_name or owner_name
        else:
            snap.owner_email = owner_email
            snap.owner_name = owner_name
        updated += 1

    db.commit()
    return {"ok": True, "updated": updated}


@router.get("/dashboard", response_model=schemas.DashboardStats)
async def dashboard_stats(
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.get_current_user),
):
    """Return dashboard statistics."""
    total_assets = db.query(models.Asset).count()
    online_assets = db.query(models.Asset).filter(
        models.Asset.status == models.AssetStatus.online
    ).count()
    offline_assets = db.query(models.Asset).filter(
        models.Asset.status == models.AssetStatus.offline
    ).count()
    auth_failed_assets = db.query(models.Asset).filter(
        models.Asset.status == models.AssetStatus.auth_failed
    ).count()
    total_jobs = db.query(models.ScanJob).count()
    total_snapshots = db.query(models.AccountSnapshot).count()

    # Recent added accounts: snapshots from last 24h with is_admin=True (new admin)
    yesterday = datetime.now(timezone.utc) - timedelta(hours=24)
    recent_admin = (
        db.query(models.AccountSnapshot)
        .filter(
            models.AccountSnapshot.snapshot_time >= yesterday,
            models.AccountSnapshot.is_admin == True,  # noqa: E712
        )
        .count()
    )

    # Assets by category
    from sqlalchemy import func
    category_rows = (
        db.query(models.Asset.asset_category, func.count(models.Asset.id))
        .group_by(models.Asset.asset_category)
        .all()
    )
    assets_by_category = [
        schemas.CategoryCount(category=str(row[0].value), count=row[1])
        for row in category_rows
    ]

    # Recent jobs (last 10)
    recent_jobs = (
        db.query(models.ScanJob)
        .order_by(models.ScanJob.started_at.desc())
        .limit(10)
        .all()
    )
    recent_job_stats = [
        schemas.RecentJobStat(
            id=j.id,
            asset_id=j.asset_id,
            status=j.status.value,
            success_count=j.success_count,
            failed_count=j.failed_count,
            started_at=j.started_at,
        )
        for j in recent_jobs
    ]

    return schemas.DashboardStats(
        total_assets=total_assets,
        online_assets=online_assets,
        offline_assets=offline_assets,
        auth_failed_assets=auth_failed_assets,
        total_snapshots=total_snapshots,
        total_jobs=total_jobs,
        recent_added_accounts=recent_admin,
        assets_by_category=assets_by_category,
        recent_jobs=recent_job_stats,
    )
