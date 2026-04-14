"""
Alert service: sends notifications via email or in-app.
Triggers are computed after each scan by comparing against the baseline snapshot.
"""
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Optional

from backend.models import Alert, AlertConfig, AlertChannel, AlertLevel, DiffResult, RiskLevel
from backend.database import SessionLocal
from backend import models

logger = logging.getLogger(__name__)


def _risk_to_alert_level(risk: RiskLevel) -> AlertLevel:
    mapping = {
        RiskLevel.critical: AlertLevel.critical,
        RiskLevel.warning: AlertLevel.warning,
        RiskLevel.info: AlertLevel.info,
    }
    return mapping.get(risk, AlertLevel.warning)


def _send_email(config: AlertConfig, alerts: List[Alert]) -> bool:
    """Send alerts via SMTP. Returns True on success."""
    settings = config.settings or {}
    try:
        host = settings.get("smtp_host", "localhost")
        port = int(settings.get("smtp_port", 587))
        from_addr = settings.get("from_addr", "noreply@accountscan")
        to_addrs = settings.get("to_addrs", [])
        username = settings.get("smtp_user")
        password = settings.get("smtp_password")
        use_tls = settings.get("use_tls", True)

        if not to_addrs:
            logger.warning("No recipient addresses configured for alert config %s", config.id)
            return False

        body_lines = [f"AccountScan 告警通知 ({len(alerts)} 条)"]
        body_lines.append("=" * 50)
        for a in alerts:
            body_lines.append(f"[{a.level.value.upper()}] {a.title}")
            body_lines.append(a.message)
            body_lines.append("-" * 40)

        msg = MIMEMultipart()
        msg["From"] = from_addr
        msg["To"] = ", ".join(to_addrs)
        msg["Subject"] = f"AccountScan 告警 - {len(alerts)} 条待处理"
        msg.attach(MIMEText("\n".join(body_lines), "plain", "utf-8"))

        with smtplib.SMTP(host, port, timeout=15) as server:
            if use_tls:
                server.starttls()
            if username and password:
                server.login(username, password)
            server.sendmail(from_addr, to_addrs, msg.as_string())

        logger.info("Email alert sent: %d alerts via SMTP %s", len(alerts), host)
        return True
    except Exception as e:
        logger.error("Failed to send email alert: %s", e)
        return False


def _create_inapp_alerts(config: AlertConfig, db, alerts_data: List[dict]) -> int:
    """Write in-app alerts to DB. Returns count created."""
    count = 0
    for item in alerts_data:
        alert = Alert(
            config_id=config.id,
            asset_id=item["asset_id"],
            job_id=item.get("job_id"),
            level=item["level"],
            title=item["title"],
            message=item["message"],
            target_identity_id=item.get("target_identity_id"),
        )
        db.add(alert)
        count += 1
    return count


def get_owner_notification_targets(snapshot_id: int, db) -> tuple:
    """
    根据账号快照获取归属人通知目标。
    Returns (email_list, identity_id_or_none).
    优先级：owner_identity_id → HumanIdentity.email > owner_email > owner_name
    """
    from backend.models import AccountSnapshot, HumanIdentity, IdentityAccount

    snap = db.query(AccountSnapshot).filter(AccountSnapshot.id == snapshot_id).first()
    if not snap:
        return ([], None)

    # 1. 已有 HumanIdentity FK
    if snap.owner_identity_id:
        identity = db.query(HumanIdentity).filter(HumanIdentity.id == snap.owner_identity_id).first()
        if identity and identity.email:
            return ([identity.email], identity.id)

    # 2. 冗余字段 owner_email
    if snap.owner_email:
        return ([snap.owner_email], snap.owner_identity_id)

    # 3. 跨资产同名账号找 HumanIdentity（IdentityAccount 链路）
    links = db.query(IdentityAccount).filter(
        IdentityAccount.snapshot_id == snapshot_id
    ).all()
    for link in links:
        identity = db.query(HumanIdentity).filter(HumanIdentity.id == link.identity_id).first()
        if identity and identity.email:
            return ([identity.email], identity.id)

    return ([], snap.owner_identity_id)


def process_scan_alerts(
    asset_id: int,
    job_id: int,
    diff_results: List[DiffResult],
    db=None,
) -> int:
    """
    After a scan completes, process diff results against all active alert configs.
    Returns total number of alerts created.
    """
    if db is None:
        db = SessionLocal()

    try:
        configs = db.query(AlertConfig).filter(AlertConfig.enabled == True).all()
        if not configs:
            return 0

        total_created = 0

        for config in configs:
            # Filter by asset
            if config.asset_ids and asset_id not in config.asset_ids:
                continue

            # Collect relevant diff items
            relevant = []
            for diff in diff_results:
                rl = _risk_to_alert_level(diff.risk_level)
                if config.risk_levels and rl.value not in config.risk_levels:
                    continue
                relevant.append(diff)

            if not relevant:
                continue

            # Build alert records
            alerts_data = []
            for diff in relevant:
                level = _risk_to_alert_level(diff.risk_level)
                title = f"{diff.diff_type.value}账号告警: {diff.username}"
                changes_str = f"类型: {diff.diff_type.value}"
                message = f"资产 {asset_id} 扫描任务 {job_id}\n风险: {diff.risk_level.value}\n{changes_str}"
                # 尝试路由到账号责任人
                emails, identity_id = get_owner_notification_targets(diff.snapshot_a_id or 0, db)
                alerts_data.append({
                    "asset_id": asset_id,
                    "job_id": job_id,
                    "level": level,
                    "title": title,
                    "message": message,
                    "target_identity_id": identity_id,
                })

            if config.channel == AlertChannel.email:
                # Write to DB for record
                count = _create_inapp_alerts(config, db, alerts_data)
                total_created += count
            elif config.channel == AlertChannel.in_app:
                count = _create_inapp_alerts(config, db, alerts_data)
                total_created += count

        db.commit()
        return total_created
    except Exception as e:
        logger.error("Error processing alerts: %s", e)
        db.rollback()
        return 0
