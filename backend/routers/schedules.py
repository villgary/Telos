from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session

from backend.database import get_db
from backend import models, schemas, auth
from backend.services import scheduler_service

router = APIRouter(prefix="/api/v1/schedules", tags=["计划扫描"])


def _validate_cron(expr: str) -> bool:
    parts = expr.strip().split()
    if len(parts) != 5:
        return False
    try:
        ranges = [(0, 59), (0, 23), (1, 31), (1, 12), (0, 6)]
        for p, (lo, hi) in zip(parts, ranges):
            if p == '*':
                continue
            if '/' in p:
                p = p.split('/')[0]
            if p == '*':
                continue
            val = int(p)
            if not (lo <= val <= hi):
                return False
        return True
    except (ValueError, IndexError):
        return False


def _next_run(cron_expr: str) -> datetime:
    """Calculate approximate next run time (simplified)."""
    from apscheduler.triggers.cron import CronTrigger
    from datetime import datetime, timezone
    try:
        parts = cron_expr.strip().split()
        trigger = CronTrigger(
            minute=parts[0], hour=parts[1],
            day=parts[2], month=parts[3], day_of_week=parts[4],
        )
        next_t = trigger.get_next_fire_time(None, datetime.now(timezone.utc))
        return next_t
    except Exception:
        return None


@router.get("", response_model=list[schemas.ScanScheduleResponse])
async def list_schedules(
    asset_id: int = None,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.get_current_user),
):
    query = db.query(models.ScanSchedule)
    if asset_id:
        query = query.filter(models.ScanSchedule.asset_id == asset_id)
    schedules = query.order_by(models.ScanSchedule.created_at.desc()).all()
    return schedules


@router.post("", response_model=schemas.ScanScheduleResponse, status_code=status.HTTP_201_CREATED)
async def create_schedule(
    schedule_in: schemas.ScanScheduleCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.require_role(models.UserRole.operator, models.UserRole.admin)),
):
    asset = db.query(models.Asset).filter(models.Asset.id == schedule_in.asset_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="资产不存在")

    if not _validate_cron(schedule_in.cron_expr):
        raise HTTPException(status_code=400, detail=f"无效的 cron 表达式: {schedule_in.cron_expr}")

    next_run_at = _next_run(schedule_in.cron_expr)

    schedule = models.ScanSchedule(
        name=schedule_in.name,
        asset_id=schedule_in.asset_id,
        cron_expr=schedule_in.cron_expr,
        next_run_at=next_run_at,
        created_by=user.id,
    )
    db.add(schedule)
    db.commit()
    db.refresh(schedule)

    # Register with APScheduler
    scheduler_service.register_schedule(
        schedule.id, schedule.cron_expr, schedule.asset_id, schedule.name,
    )

    return schedule


@router.put("/{schedule_id}", response_model=schemas.ScanScheduleResponse)
async def update_schedule(
    schedule_id: int,
    update_in: schemas.ScanScheduleUpdate,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.require_role(models.UserRole.operator, models.UserRole.admin)),
):
    schedule = db.query(models.ScanSchedule).filter(models.ScanSchedule.id == schedule_id).first()
    if not schedule:
        raise HTTPException(status_code=404, detail="计划不存在")

    if update_in.name is not None:
        schedule.name = update_in.name
    if update_in.enabled is not None:
        schedule.enabled = update_in.enabled
    if update_in.cron_expr is not None:
        if not _validate_cron(update_in.cron_expr):
            raise HTTPException(status_code=400, detail=f"无效的 cron 表达式")
        schedule.cron_expr = update_in.cron_expr
        schedule.next_run_at = _next_run(update_in.cron_expr)

    db.commit()
    db.refresh(schedule)

    # Re-register with APScheduler
    if schedule.enabled:
        scheduler_service.register_schedule(
            schedule.id, schedule.cron_expr, schedule.asset_id, schedule.name,
        )
    else:
        scheduler_service.unregister_schedule(schedule.id)

    return schedule


@router.delete("/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_schedule(
    schedule_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.require_role(models.UserRole.operator, models.UserRole.admin)),
):
    schedule = db.query(models.ScanSchedule).filter(models.ScanSchedule.id == schedule_id).first()
    if not schedule:
        raise HTTPException(status_code=404, detail="计划不存在")

    scheduler_service.unregister_schedule(schedule_id)
    db.delete(schedule)
    db.commit()
