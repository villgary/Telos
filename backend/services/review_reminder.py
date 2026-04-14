"""
Review Reminder Service — periodic account review reports.
"""

import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from dateutil.relativedelta import relativedelta
from typing import Optional

from sqlalchemy.orm import Session

from backend import models

logger = logging.getLogger("review_reminder")


def _get_period_dates(schedule: models.ReviewSchedule, from_dt: datetime) -> tuple[datetime, datetime]:
    """Return (period_start, period_end) for a schedule."""
    day = schedule.day_of_month or 1
    if schedule.period == "quarterly":
        # Go back to the start of the current quarter
        current_quarter = (from_dt.month - 1) // 3
        period_start = from_dt.replace(month=current_quarter * 3 + 1, day=day, hour=0, minute=0, second=0)
        period_end = period_start + relativedelta(months=3)
    else:  # monthly
        period_start = from_dt.replace(day=day, hour=0, minute=0, second=0)
        # If day hasn't passed this month, go back one month
        if period_start > from_dt:
            period_start = (period_start - relativedelta(months=1))
        period_end = period_start + relativedelta(months=1)
    return period_start, period_end


def _compute_next_run(schedule: models.ReviewSchedule, after: datetime) -> datetime:
    """Compute next run time for a schedule."""
    day = schedule.day_of_month or 1
    if schedule.period == "quarterly":
        return after.replace(day=day, hour=9, minute=0, second=0) + relativedelta(months=3)
    else:
        next_run = after.replace(day=day, hour=9, minute=0, second=0)
        if next_run <= after:
            next_run = next_run + relativedelta(months=1)
        return next_run


def generate_review_report(db: Session, schedule_id: int, trigger: str = "manual") -> models.ReviewReport:
    """
    Generate a review report for a schedule.
    Queries dormant/departed/high-risk accounts and builds a summary.
    """
    schedule = db.query(models.ReviewSchedule).filter(
        models.ReviewSchedule.id == schedule_id
    ).first()
    if not schedule:
        raise ValueError(f"Schedule {schedule_id} not found")

    now = datetime.now(timezone.utc)
    period_start, period_end = _get_period_dates(schedule, now)

    # ── Query dormant accounts ─────────────────────────────────────────────────
    # Get latest snapshot per (asset, username) with lifecycle status
    lifecycle_statuses = db.query(models.AccountLifecycleStatus).all()
    statuses_map = {s.snapshot_id: s for s in lifecycle_statuses}

    snap_ids = list(statuses_map.keys())
    if not snap_ids:
        snapshots = []
    else:
        snapshots = db.query(models.AccountSnapshot).filter(
            models.AccountSnapshot.id.in_(snap_ids)
        ).all()
    snap_map = {s.id: s for s in snapshots}
    asset_ids = list({s.asset_id for s in snapshots})
    assets_map = {a.id: a for a in db.query(models.Asset).filter(models.Asset.id.in_(asset_ids)).all()} if asset_ids else {}

    dormant_list = []
    departed_list = []
    privileged_total = 0

    for snap in snapshots:
        st = statuses_map.get(snap.id)
        if not st:
            continue
        if snap.is_admin:
            privileged_total += 1
        asset = assets_map.get(snap.asset_id)
        entry = {
            "username": snap.username,
            "uid": snap.uid_sid,
            "asset_code": asset.asset_code if asset else "?",
            "ip": asset.ip if asset else "?",
            "hostname": asset.hostname if asset else None,
            "last_login": snap.last_login.isoformat() if snap.last_login else None,
            "status": st.lifecycle_status,
        }
        if st.lifecycle_status == "dormant":
            dormant_list.append(entry)
        elif st.lifecycle_status == "departed":
            departed_list.append(entry)

    # ── Query high-risk assets ────────────────────────────────────────────────
    profiles = db.query(models.AssetRiskProfile).filter(
        models.AssetRiskProfile.risk_score >= 45
    ).all()
    high_risk_assets = []
    for p in profiles:
        a = assets_map.get(p.asset_id)
        if a:
            high_risk_assets.append({
                "asset_code": a.asset_code,
                "ip": a.ip,
                "risk_score": p.risk_score,
                "risk_level": p.risk_level,
                "risk_factors": p.risk_factors[:3] if p.risk_factors else [],
            })

    # ── Build summary ────────────────────────────────────────────────────────
    content_summary = {
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
        "total_accounts": len(snapshots),
        "privileged_accounts": privileged_total,
        "dormant_accounts": dormant_list,
        "departed_accounts": departed_list,
        "high_risk_assets": high_risk_assets[:20],  # top 20
        "summary": {
            "dormant_count": len(dormant_list),
            "departed_count": len(departed_list),
            "high_risk_count": len(high_risk_assets),
            "privileged_count": privileged_total,
        }
    }

    # ── Save report ──────────────────────────────────────────────────────────
    report = models.ReviewReport(
        schedule_id=schedule_id,
        period=schedule.period,
        period_start=period_start,
        period_end=period_end,
        status="pending_review",
        content_summary=content_summary,
    )
    db.add(report)

    # Update next run
    schedule.next_run_at = _compute_next_run(schedule, now)
    db.commit()
    db.refresh(report)

    # ── Send notifications ──────────────────────────────────────────────────
    channels = schedule.alert_channels or {}
    emails = channels.get("email", [])
    webhook = channels.get("webhook")

    if trigger == "manual" or schedule.next_run_at:
        # Notify: in-app alert + email/webhook placeholder
        if emails or webhook:
            _send_notifications(schedule, report, emails, webhook)

    logger.info(f"Review report generated: schedule={schedule_id}, dormant={len(dormant_list)}, departed={len(departed_list)}")
    return report


def _send_notifications(schedule: models.ReviewSchedule, report: models.ReviewReport,
                        emails: list, webhook: Optional[str]) -> None:
    """Send email/webhook notifications. Placeholder — SMTP config needed."""
    summary = report.content_summary or {}
    s = summary.get("summary", {})

    alert_title = f"账号审查提醒: {schedule.name}"
    alert_body = (
        f"周期：{schedule.period}，报告时间：{report.created_at.strftime('%Y-%m-%d')}\n"
        f"总账号数：{s.get('total_accounts', 0)}，特权账号：{s.get('privileged_count', 0)}\n"
        f"休眠账号：{s.get('dormant_count', 0)}，离机账号：{s.get('departed_count', 0)}，"
        f"高风险资产：{s.get('high_risk_count', 0)}\n"
        f"请登录 AccountScan 完成审查。"
    )
    summary_data = {
        "period": schedule.period,
        "date": report.created_at.strftime('%Y-%m-%d'),
        "total": s.get('total_accounts', 0),
        "privileged": s.get('privileged_count', 0),
        "dormant": s.get('dormant_count', 0),
        "departed": s.get('departed_count', 0),
        "high_risk": s.get('high_risk_count', 0),
    }

    # Create in-app alert
    # Pick the first asset as representative
    high_risk = summary.get("high_risk_assets", [])
    if high_risk:
        asset_code = high_risk[0]["asset_code"]
        asset = db.query(models.Asset).filter(models.Asset.asset_code == asset_code).first()
        asset_id = asset.id if asset else None
    else:
        asset_id = None

    if asset_id:
        alert = models.Alert(
            asset_id=asset_id,
            level=models.AlertLevel.warning,
            title=alert_title,
            message=alert_body,
            title_key="review.alert.title",
            title_params={"schedule_name": schedule.name},
            message_key="review.alert.message",
            message_params=summary_data,
            is_read=False,
        )
        db.add(alert)
        db.commit()

    # Email/webhook: require SMTP config — log intent only
    if emails:
        logger.info(f"Review reminder email would be sent to: {emails}")
    if webhook:
        logger.info(f"Review reminder webhook would be called: {webhook}")


def check_scheduled_reviews(db: Session) -> dict:
    """
    Check all enabled schedules and run any that are due.
    Called by scheduler_service daily.
    """
    now = datetime.now(timezone.utc)
    due = db.query(models.ReviewSchedule).filter(
        models.ReviewSchedule.enabled == True,
        models.ReviewSchedule.next_run_at <= now,
    ).all()

    results = []
    for schedule in due:
        try:
            report = generate_review_report(db, schedule.id, trigger="scheduled")
            results.append({"schedule_id": schedule.id, "report_id": report.id})
        except Exception as e:
            logger.warning(f"Scheduled review failed for schedule {schedule.id}: {e}")
            results.append({"schedule_id": schedule.id, "error": str(e)})

    return {"triggered": len(results), "results": results}
