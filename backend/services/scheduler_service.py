"""
Background scheduler using APScheduler.
Runs scheduled scans and dispatches alerts.
"""
import logging
from datetime import datetime, timezone
from typing import Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from backend.database import SessionLocal
from backend import models
from backend.services import alert_service
from backend.services.diff_engine import compute_diff

logger = logging.getLogger(__name__)


class SchedulerService:
    """
    Singleton scheduler service wrapping APScheduler BackgroundScheduler.
    Replaces module-level global _scheduler with a proper encapsulated class.
    """

    _instance: Optional["SchedulerService"] = None

    def __init__(self):
        self._scheduler: Optional[BackgroundScheduler] = None

    @classmethod
    def get_instance(cls) -> "SchedulerService":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @property
    def is_running(self) -> bool:
        return self._scheduler is not None and self._scheduler.running

    def start(self) -> None:
        """Start the scheduler and register all jobs."""
        if self._scheduler is not None:
            return

        self._scheduler = BackgroundScheduler(timezone="UTC", daemon=True)

        # Daily check for review reminders at 9am UTC
        self._scheduler.add_job(
            _check_review_reminders, CronTrigger(hour=9, minute=0),
            id="daily_review_check",
        )

        self._scheduler.start()
        self._sync_scheduler_jobs()

        # Real-time threat monitor — every 5 minutes
        from backend.services.realtime_monitor import run_monitor
        self._scheduler.add_job(run_monitor, "interval", minutes=5, id="realtime_monitor")

        logger.info("Scheduler started")

    def stop(self) -> None:
        """Shutdown the scheduler gracefully."""
        if self._scheduler:
            self._scheduler.shutdown(wait=False)
            self._scheduler = None
            logger.info("Scheduler stopped")

    def _sync_scheduler_jobs(self) -> None:
        """Sync DB schedules → APScheduler. Replaces all jobs each call."""
        if self._scheduler is None:
            return

        db = SessionLocal()
        try:
            # Remove all existing scan jobs
            for job in self._scheduler.get_jobs():
                self._scheduler.remove_job(job.id)

            schedules = db.query(models.ScanSchedule).filter(
                models.ScanSchedule.enabled == True  # noqa: E712
            ).all()
            for schedule in schedules:
                try:
                    trigger = CronTrigger(**_parse_cron(schedule.cron_expr))
                    self._scheduler.add_job(
                        _run_scan,
                        trigger=trigger,
                        args=[schedule.asset_id, schedule.id],
                        id=f"scan_{schedule.id}",
                        name=schedule.name,
                        replace_existing=True,
                    )
                    logger.info("Registered schedule: %s cron=%s", schedule.name, schedule.cron_expr)
                except Exception as e:
                    logger.error("Invalid cron for schedule %s: %s", schedule.id, e)
        finally:
            db.close()

    def register_schedule(self, schedule_id: int, cron_expr: str, asset_id: int, name: str) -> None:
        """Add or update a single schedule in APScheduler."""
        if self._scheduler is None:
            return
        try:
            trigger = CronTrigger(**_parse_cron(cron_expr))
            self._scheduler.add_job(
                _run_scan,
                trigger=trigger,
                args=[asset_id, schedule_id],
                id=f"scan_{schedule_id}",
                name=name,
                replace_existing=True,
            )
        except Exception as e:
            logger.error("Failed to register schedule %s: %s", schedule_id, e)
            raise

    def unregister_schedule(self, schedule_id: int) -> None:
        """Remove a schedule from APScheduler."""
        if self._scheduler is None:
            return
        try:
            self._scheduler.remove_job(f"scan_{schedule_id}")
        except Exception:
            pass


# ── Module-level backward-compatible wrappers ───────────────────────────────

_svc: Optional[SchedulerService] = None


def _svc_get() -> SchedulerService:
    global _svc
    if _svc is None:
        _svc = SchedulerService.get_instance()
    return _svc


def start_scheduler() -> None:
    _svc_get().start()


def stop_scheduler() -> None:
    _svc_get().stop()


def register_schedule(schedule_id: int, cron_expr: str, asset_id: int, name: str) -> None:
    _svc_get().register_schedule(schedule_id, cron_expr, asset_id, name)


def unregister_schedule(schedule_id: int) -> None:
    _svc_get().unregister_schedule(schedule_id)


# ── Background job functions (must be module-level for APScheduler) ────────

def _run_scan(asset_id: int, schedule_id: int):
    """
    Execute a scheduled scan: scan asset → compute diff vs baseline → fire alerts.
    Runs in a background thread (called by APScheduler).
    """
    db = SessionLocal()
    try:
        asset = db.query(models.Asset).filter(models.Asset.id == asset_id).first()
        if not asset:
            logger.warning("Schedule %s: asset %s not found", schedule_id, asset_id)
            return

        schedule = db.query(models.ScanSchedule).filter(
            models.ScanSchedule.id == schedule_id
        ).first()
        if not schedule or not schedule.enabled:
            logger.info("Schedule %s disabled, skipping", schedule_id)
            return

        logger.info("Scheduled scan starting: asset=%s schedule=%s", asset_id, schedule.name)

        # Pre-create job record BEFORE scan so status is visible
        job = models.ScanJob(
            asset_id=asset_id,
            trigger_type=models.TriggerType.scheduled,
            status=models.ScanJobStatus.running,
            created_by=schedule.created_by,
            started_at=datetime.now(timezone.utc),
        )
        db.add(job)
        db.commit()
        db.refresh(job)

        # Delegate to shared _execute_scan (creates its own session)
        from backend.routers.scan_jobs import _execute_scan as _do_scan
        _do_scan(job.id)

        # Update schedule last_run after scan completes
        schedule.last_run_at = datetime.now(timezone.utc)
        db.commit()
        logger.info("Scheduled scan finished: job=%s", job.id)

    except Exception as e:
        logger.error("Scheduled scan error: %s", e)
        db.rollback()
    finally:
        db.close()


def _check_review_reminders():
    """Called daily by scheduler to trigger due review reports."""
    from backend.services.review_reminder import check_scheduled_reviews
    db = SessionLocal()
    try:
        result = check_scheduled_reviews(db)
        if result["triggered"] > 0:
            logger.info(f"Scheduled reviews triggered: {result}")
    except Exception as e:
        logger.warning(f"Review reminder check failed: {e}")
    finally:
        db.close()


def _parse_cron(cron_expr: str) -> dict:
    """Parse 'min hour dom mon dow' → APScheduler CronTrigger kwargs."""
    parts = cron_expr.strip().split()
    if len(parts) != 5:
        raise ValueError(f"Invalid cron expr: {cron_expr} (need 5 fields)")
    return dict(minute=parts[0], hour=parts[1], day=parts[2], month=parts[3], day_of_week=parts[4])
