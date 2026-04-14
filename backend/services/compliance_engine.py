"""
Compliance Engine — evaluates security check rules against asset/account data.

Each check is a Python function registered in CHECK_DEFINITIONS.
Functions return list[dict] of failed evidence items (empty = pass).
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional
from collections import defaultdict

from sqlalchemy.orm import Session

from backend import models

logger = logging.getLogger("compliance_engine")

# ── Check Definitions ──────────────────────────────────────────────────────────

def _check_shared_admin(
    db: Session,
    assets: list[models.Asset],
    snaps_by_asset: dict[int, list[models.AccountSnapshot]],
    params: Optional[dict],
) -> list[dict]:
    """
    SOC2 CC6.1: Shared privileged accounts.
    Fail if the same admin username appears on 3+ distinct assets.
    """
    threshold = (params or {}).get("min_assets", 3)
    admin_snaps: dict[str, list[int]] = defaultdict(list)  # username → [asset_ids]

    for asset in assets:
        for snap in snaps_by_asset.get(asset.id, []):
            if snap.is_admin:
                admin_snaps[snap.username].append(asset.id)

    failures = []
    for username, asset_ids in admin_snaps.items():
        if len(asset_ids) >= threshold:
            assets_involved = [db.query(models.Asset).get(aid) for aid in asset_ids]
            failures.append({
                "asset_code": ",".join(a.asset_code for a in assets_involved if a),
                "ip": ",".join(a.ip for a in assets_involved if a),
                "username": username,
                "description": f"Admin account '{username}' found on {len(asset_ids)} assets (threshold: {threshold})",
            })
    return failures


def _check_unused_privileged(
    db: Session,
    assets: list[models.Asset],
    snaps_by_asset: dict[int, list[models.AccountSnapshot]],
    params: Optional[dict],
) -> list[dict]:
    """
    SOC2 CC6.3 / ISO27001 A.9.2.3: Unused privileged accounts.
    Fail if any admin account has not logged in within threshold days.
    """
    days = (params or {}).get("max_age_days", 90)
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    failures = []

    for asset in assets:
        for snap in snaps_by_asset.get(asset.id, []):
            if not snap.is_admin:
                continue
            if snap.last_login is None or snap.last_login < cutoff:
                failures.append({
                    "asset_code": asset.asset_code,
                    "ip": asset.ip,
                    "hostname": asset.hostname,
                    "username": snap.username,
                    "description": (
                        f"Admin account '{snap.username}' "
                        f"{'has never logged in' if snap.last_login is None else 'last login ' + snap.last_login.strftime('%Y-%m-%d')}, exceeds {days} days"
                    ),
                })
    return failures


def _check_unsupported_os(
    db: Session,
    assets: list[models.Asset],
    snaps_by_asset: dict[int, list[models.AccountSnapshot]],
    params: Optional[dict],
) -> list[dict]:
    """
    SOC2 CC6.6 / Periodic Review: Assets not scanned recently.
    """
    days = (params or {}).get("max_scan_interval_days", 30)
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    failures = []

    for asset in assets:
        if asset.last_scan_at is None or asset.last_scan_at < cutoff:
            failures.append({
                "asset_code": asset.asset_code,
                "ip": asset.ip,
                "hostname": asset.hostname,
                "description": (
                    f"Last scan {asset.last_scan_at.strftime('%Y-%m-%d') if asset.last_scan_at else 'never scanned'}, exceeds {days} days without scan"
                ),
            })
    return failures


def _check_nopasswd_sudo(
    db: Session,
    assets: list[models.Asset],
    snaps_by_asset: dict[int, list[models.AccountSnapshot]],
    params: Optional[dict],
) -> list[dict]:
    """
    ISO27001 A.9.2.3 / A.9.4.3: NOPASSWD sudo rules indicate privilege escalation risk.
    """
    failures = []

    for asset in assets:
        for snap in snaps_by_asset.get(asset.id, []):
            sudo = snap.sudo_config or {}
            if sudo.get("nopasswd_sudo") or sudo.get("nopasswd_all"):
                failures.append({
                    "asset_code": asset.asset_code,
                    "ip": asset.ip,
                    "hostname": asset.hostname,
                    "username": snap.username,
                    "description": f"Account '{snap.username}' has passwordless sudo (NOPASSWD) permission",
                })
    return failures


def _check_admin_ratio(
    db: Session,
    assets: list[models.Asset],
    snaps_by_asset: dict[int, list[models.AccountSnapshot]],
    params: Optional[dict],
) -> list[dict]:
    """
    等保2.0 三权分立：管理员账号比例超过阈值视为风险。
    """
    threshold = (params or {}).get("max_admin_ratio", 0.5)
    failures = []

    for asset in assets:
        snaps = snaps_by_asset.get(asset.id, [])
        if not snaps:
            continue
        total = len(snaps)
        admin_count = sum(1 for s in snaps if s.is_admin)
        if total > 0 and (admin_count / total) > threshold:
            failures.append({
                "asset_code": asset.asset_code,
                "ip": asset.ip,
                "hostname": asset.hostname,
                "description": f"Admin account ratio {int(admin_count/total*100)}% ({admin_count}/{total}), exceeds threshold {int(threshold*100)}%",
            })
    return failures


def _check_offline_with_privileged(
    db: Session,
    assets: list[models.Asset],
    snaps_by_asset: dict[int, list[models.AccountSnapshot]],
    params: Optional[dict],
) -> list[dict]:
    """
    等保2.0 账号离机审计：资产离线超 N 天且有特权账号视为高风险。
    """
    days = (params or {}).get("max_offline_days", 7)
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    failures = []

    for asset in assets:
        if asset.status != models.AssetStatus.offline:
            continue
        if asset.last_scan_at is not None and asset.last_scan_at >= cutoff:
            continue
        admin_snaps = [s for s in snaps_by_asset.get(asset.id, []) if s.is_admin]
        if admin_snaps:
            failures.append({
                "asset_code": asset.asset_code,
                "ip": asset.ip,
                "hostname": asset.hostname,
                "description": f"Asset offline >{days} days with privileged accounts: {', '.join(s.username for s in admin_snaps)}",
            })
    return failures


def _check_auth_failures(
    db: Session,
    assets: list[models.Asset],
    snaps_by_asset: dict[int, list[models.AccountSnapshot]],
    params: Optional[dict],
) -> list[dict]:
    """
    ISO27001 A.9.4.3 / 等保2.0: 扫描认证失败的资产。
    """
    failures = []

    for asset in assets:
        if asset.status == models.AssetStatus.auth_failed:
            failures.append({
                "asset_code": asset.asset_code,
                "ip": asset.ip,
                "hostname": asset.hostname,
                "description": "Scan authentication failed, unable to complete account audit",
            })
    return failures


CHECK_DEFINITIONS: dict[str, callable] = {
    "CC6.1-PrivilegedAccess":  _check_shared_admin,
    "CC6.3-UnusedPrivileged":  _check_unused_privileged,
    "CC6.6-PeriodicReview":     _check_unsupported_os,
    "A.9.2.3-PrivilegeMgmt":    _check_nopasswd_sudo,
    "A.9.2.5-AccessReview":     _check_unsupported_os,   # reuse: same logic
    "A.9.4.3-PasswordPolicy":   _check_auth_failures,
    "DBAP-ThreeSeparation":     _check_admin_ratio,
    "DBAP-OfflineAudit":        _check_offline_with_privileged,
}


def _ensure_frameworks(db: Session) -> None:
    """Seed the three frameworks and their checks if not already present."""
    existing = db.query(models.ComplianceFramework).count()
    if existing > 0:
        return

    frameworks_def = [
        {
            "slug": "soc2",
            "name": "SOC2",
            "description": "SOC 2 Trust Services Criteria — 账号安全与特权访问控制",
            "checks": [
                {"check_key": "CC6.1-PrivilegedAccess",  "title": "共享特权账号检测",
                 "description": "同名管理员账号出现在多个资产，违反最小权限原则",
                 "severity": "high"},
                {"check_key": "CC6.3-UnusedPrivileged",  "title": "未使用特权账号清理",
                 "description": "90天+未登录的管理员账号应被禁用或移除",
                 "severity": "critical"},
                {"check_key": "CC6.6-PeriodicReview",     "title": "周期性访问审查",
                 "description": "所有资产应在30天内完成至少一次扫描",
                 "severity": "medium"},
            ],
        },
        {
            "slug": "iso27001",
            "name": "ISO 27001",
            "description": "ISO/IEC 27001:2022 信息安全管理体系 — 访问控制域",
            "checks": [
                {"check_key": "A.9.2.3-PrivilegeMgmt",   "title": "特权访问管理",
                 "description": "不应存在无密码 sudo 权限的账号",
                 "severity": "high"},
                {"check_key": "A.9.2.5-AccessReview",     "title": "访问权限定期审查",
                 "description": "所有资产应定期扫描，确保账号变更可追踪",
                 "severity": "medium"},
                {"check_key": "A.9.4.3-PasswordPolicy",   "title": "认证策略合规",
                 "description": "存在认证失败的资产说明凭据配置有误，需修复",
                 "severity": "high"},
            ],
        },
        {
            "slug": "dengbao2",
            "name": "等保2.0",
            "description": "网络安全等级保护制度 2.0 — 三级系统账号安全要求",
            "checks": [
                {"check_key": "DBAP-ThreeSeparation",    "title": "三权分立检查",
                 "description": "管理员账号占比不应超过50%，应区分管理/审计/运维账号",
                 "severity": "critical"},
                {"check_key": "DBAP-OfflineAudit",       "title": "离线资产账号审计",
                 "description": "离线资产中含特权账号时，应及时处置或下线",
                 "severity": "high"},
                {"check_key": "CC6.3-UnusedPrivileged",  "title": "长期未登录特权账号",
                 "description": "90天+未登录管理员账号应被评估是否需要禁用",
                 "severity": "high"},
            ],
        },
    ]

    for fw in frameworks_def:
        fw_record = models.ComplianceFramework(
            slug=fw["slug"],
            name=fw["name"],
            description=fw["description"],
            version="1.0",
            enabled=True,
        )
        db.add(fw_record)
        db.flush()

        for ch in fw["checks"]:
            ch_record = models.ComplianceCheck(
                framework_id=fw_record.id,
                check_key=ch["check_key"],
                title=ch["title"],
                description=ch["description"],
                severity=ch["severity"],
                applies_to="server,database,network,iot",
                enabled=True,
            )
            db.add(ch_record)

    db.flush()  # caller commits
    logger.info("Compliance frameworks seeded: SOC2, ISO27001, 等保2.0")


def run_full_framework(
    db: Session,
    framework_slug: str,
    trigger_type: str = "manual",
    created_by: Optional[int] = None,
) -> models.ComplianceRun:
    """
    Run all enabled checks for a framework and store results.
    """
    _ensure_frameworks(db)

    fw = db.query(models.ComplianceFramework).filter(
        models.ComplianceFramework.slug == framework_slug,
        models.ComplianceFramework.enabled == True,
    ).first()
    if not fw:
        raise ValueError(f"Framework '{framework_slug}' not found or disabled")

    # Load all assets
    assets = db.query(models.Asset).all()
    if not assets:
        assets = []

    # Load all snapshots
    job_ids = [a.last_scan_job_id for a in assets if a.last_scan_job_id]
    all_snaps = db.query(models.AccountSnapshot).filter(
        models.AccountSnapshot.job_id.in_(job_ids)
    ).all() if job_ids else []

    snaps_by_asset: dict[int, list[models.AccountSnapshot]] = defaultdict(list)
    for s in all_snaps:
        snaps_by_asset[s.asset_id].append(s)

    # Create run record
    run = models.ComplianceRun(
        framework_id=fw.id,
        trigger_type=trigger_type,
        status="running",
        started_at=datetime.now(timezone.utc),
        created_by=created_by,
    )
    db.add(run)
    db.flush()

    total = 0
    passed = 0
    failed = 0

    try:
        checks = db.query(models.ComplianceCheck).filter(
            models.ComplianceCheck.framework_id == fw.id,
            models.ComplianceCheck.enabled == True,
        ).all()

        for check in checks:
            fn = CHECK_DEFINITIONS.get(check.check_key)
            if not fn:
                logger.warning(f"No handler for check {check.check_key}")
                continue

            try:
                evidence = fn(db, assets, snaps_by_asset, check.parameters)
            except Exception as e:
                logger.warning(f"Check {check.check_key} failed to execute: {e}")
                evidence = []

            status = "pass" if not evidence else "fail"
            if status == "pass":
                passed += 1
            else:
                failed += 1
            total += 1

            # Store ONE result per check per run, with all evidence aggregated
            result = models.ComplianceResult(
                run_id=run.id,
                framework_id=fw.id,
                check_id=check.id,
                asset_id=assets[0].id if assets else 0,
                status=status,
                evidence=evidence if evidence else None,
                evaluated_at=datetime.now(timezone.utc),
            )
            db.add(result)

        run.status = "completed"
        run.total = total
        run.passed = passed
        run.failed = failed
        run.finished_at = datetime.now(timezone.utc)
        logger.info(f"Compliance run for {framework_slug}: {passed}/{total} passed")

    except Exception as e:
        run.status = "failed"
        run.error_message = str(e)
        run.finished_at = datetime.now(timezone.utc)
        logger.error(f"Compliance run failed for {framework_slug}: {e}")

    return run


def run_all_frameworks(
    db: Session,
    trigger_type: str = "manual",
    created_by: Optional[int] = None,
) -> list[models.ComplianceRun]:
    """Run all enabled frameworks sequentially."""
    _ensure_frameworks(db)
    runs = []
    frameworks = db.query(models.ComplianceFramework).filter(
        models.ComplianceFramework.enabled == True
    ).all()
    for fw in frameworks:
        try:
            run = run_full_framework(db, fw.slug, trigger_type, created_by)
            runs.append(run)
        except Exception as e:
            logger.error(f"Framework {fw.slug} failed: {e}")
    return runs
