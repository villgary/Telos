"""
Review Reminder API — periodic account review scheduling and reports.
"""

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.database import get_db
from backend import models, schemas, auth
from backend.services.review_reminder import generate_review_report, check_scheduled_reviews

router = APIRouter(prefix="/api/v1/review", tags=["审查提醒"])


def _report_to_resp(report: models.ReviewReport) -> schemas.ReviewReportResponse:
    reviewer_name = None
    if report.reviewer:
        reviewer_name = report.reviewer.username
    schedule_name = None
    if report.schedule:
        schedule_name = report.schedule.name
    return schemas.ReviewReportResponse(
        id=report.id,
        schedule_id=report.schedule_id,
        period=report.period,
        period_start=report.period_start,
        period_end=report.period_end,
        status=report.status,
        reviewed_by=report.reviewed_by,
        reviewed_at=report.reviewed_at,
        notes=report.notes,
        content_summary=report.content_summary,
        created_at=report.created_at,
        schedule_name=schedule_name,
        reviewer_name=reviewer_name,
    )


@router.get("/schedules")
async def list_schedules(
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.get_current_user),
):
    """List all review schedules."""
    items = db.query(models.ReviewSchedule).all()
    return {"schedules": [schemas.ReviewScheduleResponse.model_validate(s) for s in items]}


@router.post("/schedules")
async def create_schedule(
    body: schemas.ReviewScheduleCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.require_role(models.UserRole.admin)),
):
    """Create a new review schedule (admin only)."""
    from backend.services.review_reminder import _compute_next_run
    schedule = models.ReviewSchedule(
        name=body.name,
        period=body.period,
        day_of_month=body.day_of_month,
        alert_channels=body.alert_channels,
        enabled=body.enabled,
        created_by=user.id,
        next_run_at=_compute_next_run(models.ReviewSchedule(
            period=body.period, day_of_month=body.day_of_month
        ), datetime.now(timezone.utc)),
    )
    db.add(schedule)
    db.commit()
    db.refresh(schedule)
    return schemas.ReviewScheduleResponse.model_validate(schedule)


@router.put("/schedules/{schedule_id}")
async def update_schedule(
    schedule_id: int,
    body: schemas.ReviewScheduleUpdate,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.require_role(models.UserRole.admin)),
):
    """Update a review schedule (admin only)."""
    schedule = db.query(models.ReviewSchedule).filter(
        models.ReviewSchedule.id == schedule_id
    ).first()
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")

    if body.name is not None:
        schedule.name = body.name
    if body.period is not None:
        schedule.period = body.period
    if body.day_of_month is not None:
        schedule.day_of_month = body.day_of_month
    if body.alert_channels is not None:
        schedule.alert_channels = body.alert_channels
    if body.enabled is not None:
        schedule.enabled = body.enabled
        if body.enabled:
            from backend.services.review_reminder import _compute_next_run
            schedule.next_run_at = _compute_next_run(schedule, datetime.now(timezone.utc))
    db.commit()
    return {"success": True}


@router.delete("/schedules/{schedule_id}", status_code=204)
async def delete_schedule(
    schedule_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.require_role(models.UserRole.admin)),
):
    """Delete a review schedule (admin only)."""
    schedule = db.query(models.ReviewSchedule).filter(
        models.ReviewSchedule.id == schedule_id
    ).first()
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    db.delete(schedule)
    db.commit()


@router.get("/reports")
async def list_reports(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    status_filter: str = Query(None, alias="status"),
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.get_current_user),
):
    """List review reports (history)."""
    query = db.query(models.ReviewReport)
    if status_filter:
        query = query.filter(models.ReviewReport.status == status_filter)
    total = query.count()
    items = query.order_by(models.ReviewReport.created_at.desc()).offset(offset).limit(limit).all()
    return {"total": total, "reports": [_report_to_resp(r) for r in items]}


@router.get("/reports/{report_id}")
async def get_report(
    report_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.get_current_user),
):
    """Get a single review report with full content."""
    report = db.query(models.ReviewReport).filter(
        models.ReviewReport.id == report_id
    ).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return _report_to_resp(report)


@router.post("/reports/{report_id}/approve")
async def approve_report(
    report_id: int,
    notes: str = Query(None),
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.get_current_user),
):
    """Mark a review report as approved."""
    report = db.query(models.ReviewReport).filter(
        models.ReviewReport.id == report_id
    ).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    report.status = "approved"
    report.reviewed_by = user.id
    report.reviewed_at = datetime.now(timezone.utc)
    if notes:
        report.notes = notes
    db.commit()
    return {"success": True}


@router.post("/reports/{report_id}/dismiss")
async def dismiss_report(
    report_id: int,
    notes: str = Query(None),
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.get_current_user),
):
    """Mark a review report as dismissed."""
    report = db.query(models.ReviewReport).filter(
        models.ReviewReport.id == report_id
    ).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    report.status = "dismissed"
    report.reviewed_by = user.id
    report.reviewed_at = datetime.now(timezone.utc)
    if notes:
        report.notes = notes
    db.commit()
    return {"success": True}


@router.post("/generate")
async def manual_generate(
    schedule_id: int = Query(..., ge=1),
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.require_role(models.UserRole.admin)),
):
    """Manually trigger a review report generation."""
    report = generate_review_report(db, schedule_id, trigger="manual")
    return {"success": True, "report_id": report.id}
