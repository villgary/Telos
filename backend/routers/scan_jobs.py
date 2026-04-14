import os
from datetime import datetime, timezone
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from sqlalchemy import text

from backend.database import get_db
from backend import models, schemas, auth, encryption
from backend.models import AccountRiskScore
from backend.models import ScanJobStatus, AssetStatus, OSType, AssetCategory, DBType
from backend.services import ssh_scanner, win_scanner, alert_service
from backend.services.risk_propagation import propagate_risk
from backend.services.diff_engine import compute_diff
from backend.services.account_lifecycle import compute_lifecycles

router = APIRouter(prefix="/api/v1/scan-jobs", tags=["扫描任务"])


# ──────────────────────────────────────────────────────────────
#  Shared scan execution (called by both HTTP BackgroundTask and scheduler)
# ──────────────────────────────────────────────────────────────

def _execute_scan(job_id: int) -> None:
    """
    Execute the actual scan for a given job record.
    Handles credential decryption, scanner routing, snapshot writing, diff, and alerts.
    This function is called by both the HTTP BackgroundTasks and the scheduler.
    """
    from backend.database import SessionLocal
    db = SessionLocal()
    try:
        job = db.query(models.ScanJob).filter(models.ScanJob.id == job_id).first()
        if not job:
            return

        asset = db.query(models.Asset).filter(models.Asset.id == job.asset_id).first()
        if not asset:
            job.status = ScanJobStatus.failed
            job.error_message = "资产不存在"
            job.finished_at = datetime.now(timezone.utc)
            db.commit()
            return

        cred = asset.credential
        if cred.auth_type == models.AuthType.password:
            password = encryption.decrypt(cred.password_enc) if cred.password_enc else None
            private_key = None
            passphrase = None
        else:
            password = None
            private_key = encryption.decrypt(cred.private_key_enc) if cred.private_key_enc else None
            passphrase = encryption.decrypt(cred.passphrase_enc) if cred.passphrase_enc else None

        conn_result = None
        accounts = []

        try:
            if asset.asset_category == AssetCategory.database:
                from backend.services import db_scanner
                db_type_val = asset.db_type.value if asset.db_type else "mysql"
                conn_result, accounts = db_scanner.scan_asset(
                    ip=asset.ip,
                    port=asset.port or 0,
                    username=cred.username,
                    password=password,
                    db_type=db_type_val,
                    timeout=120,
                )
            elif asset.asset_category == AssetCategory.network:
                from backend.services import net_scanner
                conn_result, accounts = net_scanner.scan_asset(
                    ip=asset.ip,
                    port=asset.port,
                    username=cred.username,
                    password=password,
                    private_key=private_key,
                    passphrase=passphrase,
                    timeout=120,
                )
            elif asset.asset_category == AssetCategory.iot:
                from backend.services import iot_scanner
                conn_result, accounts = iot_scanner.scan_asset(
                    ip=asset.ip,
                    port=asset.port or 80,
                    username=cred.username,
                    password=password,
                    timeout=120,
                )
            elif asset.os_type == OSType.linux:
                # Try Go scanner first if GO_SCANNER_URL is configured
                go_used = False
                if os.environ.get("GO_SCANNER_URL"):
                    try:
                        from backend.services import ssh_scanner_go
                        conn_result, accounts = ssh_scanner_go.scan_asset(
                            ip=asset.ip,
                            port=asset.port,
                            username=cred.username,
                            password=password,
                            private_key=private_key,
                            passphrase=passphrase,
                            timeout=120,
                        )
                        go_used = True
                    except Exception as go_err:
                        import logging
                        logging.getLogger("scan_jobs").warning(
                            "Go scanner failed for %s:%s, falling back to Python: %s",
                            asset.ip, asset.port, go_err,
                        )
                if not go_used:
                    conn_result, accounts = ssh_scanner.scan_asset(
                        ip=asset.ip,
                        port=asset.port,
                        username=cred.username,
                        password=password,
                        private_key=private_key,
                        passphrase=passphrase,
                        timeout=120,
                    )
            elif asset.os_type == OSType.windows:
                conn_result, accounts = win_scanner.scan_asset(
                    ip=asset.ip,
                    port=asset.port,
                    username=cred.username,
                    password=password,
                    timeout=120,
                )
        except Exception as e:
            # Scanner itself threw — treat as failed
            job.status = ScanJobStatus.failed
            job.error_message = str(e)
            asset.status = AssetStatus.offline
            job.finished_at = datetime.now(timezone.utc)
            db.commit()
            return

        # Update asset status
        asset.status = AssetStatus(conn_result.status)
        asset.last_scan_at = datetime.now(timezone.utc)
        asset.last_scan_job_id = job.id

        if conn_result.success:
            job.status = ScanJobStatus.success
            job.success_count = len(accounts)
            for acct in accounts:
                snap = models.AccountSnapshot(
                    asset_id=asset.id,
                    job_id=job.id,
                    username=acct.username,
                    uid_sid=acct.uid_sid,
                    is_admin=acct.is_admin,
                    account_status=acct.account_status,
                    home_dir=acct.home_dir,
                    shell=acct.shell,
                    groups=acct.groups,
                    sudo_config=acct.sudo_config,
                    last_login=acct.last_login,
                    raw_info=acct.raw_info,
                    snapshot_time=job.started_at,
                )
                db.add(snap)
            db.flush()

            # Diff vs baseline
            baseline_snaps = (
                db.query(models.AccountSnapshot)
                .filter(
                    models.AccountSnapshot.asset_id == asset.id,
                    models.AccountSnapshot.is_baseline == True,
                    models.AccountSnapshot.job_id != job.id,
                )
                .all()
            )
            if baseline_snaps:
                latest_snaps = (
                    db.query(models.AccountSnapshot)
                    .filter(models.AccountSnapshot.job_id == job.id)
                    .all()
                )
                diff_items, _ = compute_diff(baseline_snaps, latest_snaps)
                snap_a_map = {s.uid_sid: s for s in baseline_snaps}
                snap_b_map = {s.uid_sid: s for s in latest_snaps}
                for di in diff_items:
                    uid_sid = di.uid_sid
                    snap_a = snap_a_map.get(uid_sid)
                    snap_b = snap_b_map.get(uid_sid)
                    diff_result = models.DiffResult(
                        base_job_id=baseline_snaps[0].job_id,
                        compare_job_id=job.id,
                        diff_type=models.DiffType(di.diff_type.value),
                        risk_level=models.RiskLevel(di.risk_level.value),
                        username=di.username,
                        snapshot_a_id=snap_a.id if snap_a else None,
                        snapshot_b_id=snap_b.id if snap_b else None,
                        status=models.DiffStatus.pending,
                    )
                    db.add(diff_result)
                db.flush()

                diff_objs = db.query(models.DiffResult).filter(
                    models.DiffResult.base_job_id == baseline_snaps[0].job_id,
                    models.DiffResult.compare_job_id == job.id,
                ).all()
                alert_service.process_scan_alerts(asset.id, job.id, diff_objs, db)
        else:
            job.status = ScanJobStatus.failed
            job.failed_count = 1
            job.error_message = conn_result.error
            asset.status = AssetStatus.offline

    except Exception as e:
        job.status = ScanJobStatus.failed
        job.error_message = str(e)
        asset.status = AssetStatus.offline

    finally:
        if "job" in dir() and job:
            job.finished_at = datetime.now(timezone.utc)
        # Propagate risk after scan completes
        try:
            propagate_risk(db)
        except Exception as e:
            import logging
            logging.getLogger("scan_jobs").warning(f"Risk propagation failed: {e}")
        # Compute account lifecycle statuses
        try:
            compute_lifecycles(db)
        except Exception as e:
            import logging
            logging.getLogger("scan_jobs").warning(f"Lifecycle compute failed: {e}")
        # Compute account risk scores
        try:
            from backend.services.account_risk_score import compute_all_scores
            compute_all_scores(db)
        except Exception as e:
            import logging
            logging.getLogger("scan_jobs").warning(f"Account risk score compute failed: {e}")
        db.commit()
        db.close()


# ──────────────────────────────────────────────────────────────
#  Routes
# ──────────────────────────────────────────────────────────────

@router.get("", response_model=list[schemas.ScanJobResponse])
async def list_scan_jobs(
    asset_id: int = None,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.get_current_user),
):
    query = db.query(models.ScanJob).order_by(models.ScanJob.created_at.desc())
    if asset_id:
        query = query.filter(models.ScanJob.asset_id == asset_id)
    jobs = query.all()
    # Eager-load asset_ip for response
    asset_ids = list({j.asset_id for j in jobs})
    asset_map = {a.id: a.ip for a in db.query(models.Asset).filter(models.Asset.id.in_(asset_ids)).all()}
    result = []
    for job in jobs:
        resp = schemas.ScanJobResponse.model_validate(job)
        resp.asset_ip = asset_map.get(job.asset_id)
        result.append(resp)
    return result


@router.get("/{job_id}", response_model=schemas.ScanJobDetail)
async def get_scan_job(
    job_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.get_current_user),
):
    job = db.query(models.ScanJob).filter(models.ScanJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="扫描任务不存在")

    snapshots = (
        db.query(models.AccountSnapshot)
        .filter(models.AccountSnapshot.job_id == job_id)
        .all()
    )
    return schemas.ScanJobDetail(
        id=job.id,
        asset_id=job.asset_id,
        trigger_type=job.trigger_type.value,
        status=job.status,
        success_count=job.success_count,
        failed_count=job.failed_count,
        error_message=job.error_message,
        started_at=job.started_at,
        finished_at=job.finished_at,
        created_by=job.created_by,
        created_at=job.created_at,
        asset_ip=job.asset.ip,
        snapshots=[schemas.SnapshotResponse.model_validate(s) for s in snapshots],
    )


@router.post("", response_model=schemas.ScanJobResponse, status_code=status.HTTP_202_ACCEPTED)
async def trigger_scan(
    asset_id: int,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.require_role(models.UserRole.operator, models.UserRole.admin)),
):
    """
    Trigger a scan for a specific asset.
    Returns 202 Accepted immediately; the scan runs in the background.
    Poll GET /scan-jobs/{job_id} to check status.
    """
    asset = db.query(models.Asset).filter(models.Asset.id == asset_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="资产不存在")

    # Create job record BEFORE scan starts (so status is visible immediately)
    job = models.ScanJob(
        asset_id=asset_id,
        trigger_type=models.TriggerType.manual,
        status=ScanJobStatus.running,
        created_by=user.id,
        started_at=datetime.now(timezone.utc),
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    # Register background scan task
    background_tasks.add_task(_execute_scan, job.id)

    # Audit log (sync — after response sent)
    def _audit_log():
        from backend.database import SessionLocal as SL2
        ad = SL2()
        try:
            al = models.AuditLog(
                user_id=user.id,
                action="scan.trigger",
                target_type="asset",
                target_id=asset_id,
                detail={"job_id": job.id},
                ip_address=auth.get_client_ip(request),
            )
            ad.add(al)
            ad.commit()
        finally:
            ad.close()

    background_tasks.add_task(_audit_log)

    return job


@router.post("/{job_id}/set-baseline", status_code=status.HTTP_204_NO_CONTENT)
async def set_baseline(
    job_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.require_role(models.UserRole.operator, models.UserRole.admin)),
):
    """Mark all snapshots from this job as the baseline for their asset."""
    job = db.query(models.ScanJob).filter(models.ScanJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="扫描任务不存在")

    db.query(models.AccountSnapshot).filter(
        models.AccountSnapshot.asset_id == job.asset_id,
        models.AccountSnapshot.is_baseline == True,
    ).update({"is_baseline": False})

    db.query(models.AccountSnapshot).filter(
        models.AccountSnapshot.job_id == job_id,
    ).update({"is_baseline": True})

    db.commit()


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_scan_job(
    job_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.require_role(models.UserRole.admin)),
):
    """Delete a scan job and all its snapshots."""
    job = db.query(models.ScanJob).filter(models.ScanJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="扫描任务不存在")

    # Use a PostgreSQL stored function to atomically delete the job and all dependents
    # This avoids FK violation issues by deleting in the right order within one transaction
    try:
        db.execute(text("""
            CREATE OR REPLACE FUNCTION delete_scan_job(job_id_param BIGINT)
            RETURNS VOID AS $$
            DECLARE
                snap_ids BIGINT[];
            BEGIN
                -- Collect snapshot IDs
                SELECT ARRAY_AGG(id) INTO snap_ids
                FROM account_snapshots
                WHERE job_id = job_id_param;

                -- Handle empty snap_ids safely
                IF snap_ids IS NULL OR array_length(snap_ids, 1) IS NULL THEN
                    snap_ids := ARRAY[]::BIGINT[];
                END IF;

                -- Delete from all tables that reference snapshots by snapshot_id (in FK dependency order)
                DELETE FROM threat_account_signals WHERE snapshot_id = ANY(snap_ids);
                DELETE FROM playbook_executions WHERE snapshot_id = ANY(snap_ids);
                DELETE FROM identity_accounts WHERE snapshot_id = ANY(snap_ids);
                DELETE FROM account_risk_scores WHERE snapshot_id = ANY(snap_ids);
                DELETE FROM account_lifecycle_statuses WHERE snapshot_id = ANY(snap_ids);
                DELETE FROM account_behavior_events WHERE snapshot_id = ANY(snap_ids);
                -- nhi_alerts references nhi_identities, delete alerts first
                DELETE FROM nhi_alerts WHERE nhi_id IN (SELECT id FROM nhi_identities WHERE snapshot_id = ANY(snap_ids));
                DELETE FROM nhi_identities WHERE snapshot_id = ANY(snap_ids);
                DELETE FROM policy_evaluation_results WHERE snapshot_id = ANY(snap_ids);
                DELETE FROM pam_synced_accounts WHERE matched_snapshot_id = ANY(snap_ids);
                DELETE FROM diff_results
                    WHERE snapshot_a_id = ANY(snap_ids) OR snapshot_b_id = ANY(snap_ids);

                -- Also delete alerts that reference this job directly
                DELETE FROM alerts WHERE job_id = job_id_param;

                -- Clear job_id refs
                UPDATE diff_results SET base_job_id = NULL WHERE base_job_id = job_id_param;
                UPDATE diff_results SET compare_job_id = NULL WHERE compare_job_id = job_id_param;

                -- Clear asset last_scan_job_id refs
                UPDATE assets SET last_scan_job_id = NULL WHERE last_scan_job_id = job_id_param;

                -- Delete snapshots
                DELETE FROM account_snapshots WHERE job_id = job_id_param;

                -- Delete the job
                DELETE FROM scan_jobs WHERE id = job_id_param;
            END;
            $$ LANGUAGE plpgsql;
        """))
        db.execute(text("SELECT delete_scan_job(:job_id)"), {"job_id": job_id})
        db.commit()
        return
    except Exception:
        db.rollback()
        raise
