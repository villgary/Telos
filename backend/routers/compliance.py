"""
Compliance API — framework evaluation, results, and dashboard.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from collections import defaultdict

from backend.database import get_db
from backend import models, schemas, auth
from backend.services.compliance_engine import (
    run_full_framework, run_all_frameworks, _ensure_frameworks,
)

router = APIRouter(prefix="/api/v1/compliance", tags=["合规框架"])

# i18n key mapping for compliance checks
_CHECK_TITLE_KEYS = {
    "CC6.1-PrivilegedAccess": "compliance.check.CC6_1.title",
    "CC6.3-UnusedPrivileged": "compliance.check.CC6_3.title",
    "CC6.6-PeriodicReview": "compliance.check.CC6_6.title",
    "A.9.2.3-PrivilegeMgmt": "compliance.check.A9_2_3.title",
    "A.9.2.5-AccessReview": "compliance.check.A9_2_5.title",
    "A.9.4.3-PasswordPolicy": "compliance.check.A9_4_3.title",
    "DBAP-ThreeSeparation": "compliance.check.DBAP_TS.title",
    "DBAP-OfflineAudit": "compliance.check.DBAP_OA.title",
    # 等保2.0 specific (same check_key, different title)
    "dengbao2.CC6.3-UnusedPrivileged": "compliance.check.CC6_3_dengbao.title",
}

_CHECK_DESC_KEYS = {
    # SOC2
    "CC6.1-PrivilegedAccess": "compliance.check.CC6_1.desc",
    "CC6.3-UnusedPrivileged": "compliance.check.CC6_3.desc",
    "CC6.6-PeriodicReview": "compliance.check.CC6_6.desc",
    # ISO27001
    "A.9.2.3-PrivilegeMgmt": "compliance.check.A9_2_3.desc",
    "A.9.2.5-AccessReview": "compliance.check.A9_2_5.desc",
    "A.9.4.3-PasswordPolicy": "compliance.check.A9_4_3.desc",
    # 等保2.0
    "DBAP-ThreeSeparation": "compliance.check.DBAP_TS.desc",
    "DBAP-OfflineAudit": "compliance.check.DBAP_OA.desc",
    # 等保2.0 CC6.3 (same key as SOC2 but different description)
    "dengbao2.CC6.3-UnusedPrivileged": "compliance.check.CC6_3_dengbao.desc",
}

_FRAMEWORK_NAME_KEYS = {
    "soc2": "compliance.framework.soc2.name",
    "iso27001": "compliance.framework.iso27001.name",
    "dengbao2": "compliance.framework.dengbao2.name",
}

_FRAMEWORK_DESC_KEYS = {
    "soc2": "compliance.framework.soc2.desc",
    "iso27001": "compliance.framework.iso27001.desc",
    "dengbao2": "compliance.framework.dengbao2.desc",
}


def _build_check_result_item(
    db: Session,
    check: models.ComplianceCheck,
) -> schemas.ComplianceCheckResultItem:
    """Build the latest ComplianceCheckResultItem for one check."""
    # Get most recent result for this check
    result = db.query(models.ComplianceResult).filter(
        models.ComplianceResult.check_id == check.id,
    ).order_by(models.ComplianceResult.evaluated_at.desc()).first()

    failed_count = int(db.query(models.ComplianceResult).filter(
        models.ComplianceResult.check_id == check.id,
        models.ComplianceResult.status == "fail",
    ).count())
    passed_count = int(db.query(models.ComplianceResult).filter(
        models.ComplianceResult.check_id == check.id,
        models.ComplianceResult.status == "pass",
    ).count())

    evidence_items: list[schemas.ComplianceEvidenceItem] = []
    if result and result.evidence:
        for ev in result.evidence:
            if isinstance(ev, dict):
                evidence_items.append(schemas.ComplianceEvidenceItem(
                    asset_code=ev.get("asset_code", ""),
                    ip=ev.get("ip", ""),
                    hostname=ev.get("hostname"),
                    username=ev.get("username"),
                    description=ev.get("description", ""),
                    description_key=ev.get("description_key"),
                ))

    status = result.status if result else "never_run"
    return schemas.ComplianceCheckResultItem(
        check_key=check.check_key,
        title=check.title,
        description=check.description,
        title_key=_CHECK_TITLE_KEYS.get(check.check_key),
        description_key=_CHECK_DESC_KEYS.get(check.check_key),
        severity=check.severity.upper(),
        status=status,
        failed_count=failed_count,
        passed_count=passed_count,
        evidence=evidence_items,
    )


@router.get("/dashboard", response_model=schemas.ComplianceDashboardResponse)
async def get_compliance_dashboard(
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.get_current_user),
):
    """
    Compliance overview: score and check summaries per framework.
    """
    _ensure_frameworks(db)

    frameworks = db.query(models.ComplianceFramework).filter(
        models.ComplianceFramework.enabled == True
    ).all()

    result: list[schemas.ComplianceFrameworkDashboard] = []

    for fw in frameworks:
        checks = db.query(models.ComplianceCheck).filter(
            models.ComplianceCheck.framework_id == fw.id,
            models.ComplianceCheck.enabled == True,
        ).all()

        # Find most recent run
        latest_run = db.query(models.ComplianceRun).filter(
            models.ComplianceRun.framework_id == fw.id,
            models.ComplianceRun.status == "completed",
        ).order_by(models.ComplianceRun.started_at.desc()).first()

        check_items: list[schemas.ComplianceCheckResultItem] = []
        total = 0
        passed = 0
        failed = 0

        for ch in checks:
            item = _build_check_result_item(db, ch)
            # Check-level title/description key can vary by framework
            fw_ch_key = f"{fw.slug}.{ch.check_key}"
            if item.title_key is None or not _CHECK_TITLE_KEYS.get(item.title_key):
                item.title_key = _CHECK_TITLE_KEYS.get(fw_ch_key) or _CHECK_TITLE_KEYS.get(ch.check_key)
            if item.description_key is None:
                item.description_key = _CHECK_DESC_KEYS.get(fw_ch_key) or _CHECK_DESC_KEYS.get(ch.check_key)
            check_items.append(item)
            total += 1
            if item.status == "pass":
                passed += 1
            elif item.status == "fail":
                failed += 1

        score = int(passed / total * 100) if total > 0 else 0

        result.append(schemas.ComplianceFrameworkDashboard(
            slug=fw.slug,
            name=fw.name,
            description=fw.description,
            name_key=_FRAMEWORK_NAME_KEYS.get(fw.slug),
            description_key=_FRAMEWORK_DESC_KEYS.get(fw.slug),
            score=score,
            total=total,
            passed=passed,
            failed=failed,
            checks=check_items,
        ))

    return schemas.ComplianceDashboardResponse(frameworks=result)


@router.get("/frameworks")
async def list_frameworks(
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.get_current_user),
):
    """List all compliance frameworks."""
    _ensure_frameworks(db)
    frameworks = db.query(models.ComplianceFramework).filter(
        models.ComplianceFramework.enabled == True
    ).all()
    return [schemas.ComplianceFrameworkResponse.model_validate(fw) for fw in frameworks]


@router.get("/frameworks/{slug}/checks")
async def get_framework_checks(
    slug: str,
    run_id: Optional[int] = None,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.get_current_user),
):
    """Get all checks for a framework with latest results."""
    _ensure_frameworks(db)
    fw = db.query(models.ComplianceFramework).filter(
        models.ComplianceFramework.slug == slug,
    ).first()
    if not fw:
        raise HTTPException(status_code=404, detail="Framework not found")

    checks = db.query(models.ComplianceCheck).filter(
        models.ComplianceCheck.framework_id == fw.id,
        models.ComplianceCheck.enabled == True,
    ).all()

    return [_build_check_result_item(db, ch) for ch in checks]


@router.post("/frameworks/{slug}/run", response_model=schemas.ComplianceRunResponse)
async def run_framework(
    slug: str,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.get_current_user),
):
    """Manually trigger a compliance evaluation for one framework."""
    try:
        run = run_full_framework(
            db, slug,
            trigger_type="manual",
            created_by=user.id,
        )
        db.commit()  # commit after service finishes all writes
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

    fw = db.query(models.ComplianceFramework).get(run.framework_id)
    return schemas.ComplianceRunResponse(
        id=run.id,
        framework_id=run.framework_id,
        framework_slug=fw.slug if fw else slug,
        framework_name=fw.name if fw else slug,
        trigger_type=run.trigger_type,
        status=run.status,
        total=run.total,
        passed=run.passed,
        failed=run.failed,
        error_message=run.error_message,
        started_at=run.started_at,
        finished_at=run.finished_at,
        created_by=run.created_by,
    )


@router.post("/run-all")
async def run_all(
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.get_current_user),
):
    """Manually trigger all framework evaluations."""
    try:
        runs = run_all_frameworks(db, trigger_type="manual", created_by=user.id)
        db.commit()
        return [{"framework": r.framework_id, "run_id": r.id, "status": r.status} for r in runs]
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/runs")
async def list_runs(
    limit: int = 20,
    offset: int = 0,
    framework_slug: Optional[str] = None,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.get_current_user),
):
    """Compliance run history."""
    query = db.query(models.ComplianceRun).order_by(
        models.ComplianceRun.started_at.desc()
    )
    if framework_slug:
        fw = db.query(models.ComplianceFramework).filter(
            models.ComplianceFramework.slug == framework_slug,
        ).first()
        if fw:
            query = query.filter(models.ComplianceRun.framework_id == fw.id)

    total = query.count()
    runs = query.offset(offset).limit(limit).all()

    items = []
    for r in runs:
        fw = db.query(models.ComplianceFramework).get(r.framework_id)
        items.append(schemas.ComplianceRunResponse(
            id=r.id,
            framework_id=r.framework_id,
            framework_slug=fw.slug if fw else "",
            framework_name=fw.name if fw else "",
            trigger_type=r.trigger_type,
            status=r.status,
            total=r.total,
            passed=r.passed,
            failed=r.failed,
            error_message=r.error_message,
            started_at=r.started_at,
            finished_at=r.finished_at,
            created_by=r.created_by,
        ))

    return {"total": total, "runs": items}


@router.get("/results")
async def get_results(
    run_id: Optional[int] = None,
    check_key: Optional[str] = None,
    framework_slug: Optional[str] = None,
    limit: int = 100,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.get_current_user),
):
    """Get detailed compliance results."""
    query = db.query(models.ComplianceResult)

    if run_id:
        query = query.filter(models.ComplianceResult.run_id == run_id)
    if check_key:
        ch = db.query(models.ComplianceCheck).filter(
            models.ComplianceCheck.check_key == check_key,
        ).first()
        if ch:
            query = query.filter(models.ComplianceResult.check_id == ch.id)
    if framework_slug:
        fw = db.query(models.ComplianceFramework).filter(
            models.ComplianceFramework.slug == framework_slug,
        ).first()
        if fw:
            query = query.filter(models.ComplianceResult.framework_id == fw.id)

    results = query.limit(limit).all()
    items = []
    for r in results:
        ch = db.query(models.ComplianceCheck).get(r.check_id)
        asset = db.query(models.Asset).get(r.asset_id)
        items.append(schemas.ComplianceResultResponse(
            id=r.id,
            run_id=r.run_id,
            check_id=r.check_id,
            check_key=ch.check_key if ch else "",
            check_title=ch.title if ch else "",
            asset_id=r.asset_id,
            asset_code=asset.asset_code if asset else "",
            ip=asset.ip if asset else "",
            hostname=asset.hostname if asset else None,
            status=r.status,
            evidence=r.evidence,
            evaluated_at=r.evaluated_at,
        ))

    return {"results": items}
