"""
UEBA API — User Entity Behavior Analytics.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone

from backend.database import get_db
from backend import models, auth
from backend.services.ueba_service import detect_all_anomalies, get_behavior_summary

router = APIRouter(prefix="/api/v1/ueba", tags=["UEBA"])


@router.get("/summary")
async def get_summary(
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.get_current_user),
):
    """Get UEBA summary statistics and recent anomaly events (last 7 days)."""
    return get_behavior_summary(db)


@router.post("/detect")
async def trigger_detection(
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.require_role(models.UserRole.operator, models.UserRole.admin)),
):
    """
    Trigger anomaly detection for all accounts.
    Persists events to account_behavior_events table.
    """
    anomalies = detect_all_anomalies(db)
    return {
        "success": True,
        "detected": len(anomalies),
        "anomalies": [a.to_dict() for a in anomalies],
    }


@router.get("/events")
async def list_events(
    days: int = Query(7, ge=1, le=90),
    severity: str = Query(None),
    event_type: str = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.get_current_user),
):
    """List behavior anomaly events with optional filters."""
    q = db.query(models.AccountBehaviorEvent).filter(
        models.AccountBehaviorEvent.detected_at >= datetime.now(timezone.utc) - timedelta(days=days)
    )
    if severity:
        q = q.filter(models.AccountBehaviorEvent.severity == severity)
    if event_type:
        q = q.filter(models.AccountBehaviorEvent.event_type == event_type)

    total = q.count()
    events = q.order_by(models.AccountBehaviorEvent.detected_at.desc()).offset(offset).limit(limit).all()

    return {
        "total": total,
        "events": [
            {
                "id": e.id,
                "event_type": e.event_type,
                "severity": e.severity,
                "username": e.username,
                "asset_code": e.asset_code,
                "asset_ip": e.asset_ip,
                "description": e.description,
                "description_key": e.description_key,
                "description_params": e.description_params,
                "snapshot_id": e.snapshot_id,
                "detected_at": e.detected_at.isoformat() if e.detected_at else None,
            }
            for e in events
        ],
    }


@router.get("/event-types")
async def get_event_types(
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.get_current_user),
):
    """Get list of available event types with descriptions."""
    return [
        {
            "type": "dormant_to_active",
            "label_zh": "休眠账号恢复",
            "label_en": "Dormant Account Reactivated",
            "severity": "high",
            "description_zh": "此前处于休眠/离机状态的账号恢复了活跃登录",
            "description_en": "An account previously marked dormant or departed has resumed activity",
        },
        {
            "type": "went_dormant",
            "label_zh": "账号进入休眠",
            "label_en": "Account Went Dormant",
            "severity": "medium",
            "description_zh": "活跃账号变为休眠状态，超过配置天数未登录",
            "description_en": "An active account stopped logging in and went dormant",
        },
        {
            "type": "new_privileged_account",
            "label_zh": "新特权账号",
            "label_en": "New Privileged Account",
            "severity": "high",
            "description_zh": "新发现具备管理员权限的账号",
            "description_en": "A new privileged (admin) account was discovered on first scan",
        },
        {
            "type": "privileged_no_login",
            "label_zh": "特权账号从未登录",
            "label_en": "Privileged Account Never Logged In",
            "severity": "medium",
            "description_zh": "特权账号存在但从未有过登录记录",
            "description_en": "A privileged account exists but has never logged in",
        },
        {
            "type": "privilege_escalation",
            "label_zh": "权限提升",
            "label_en": "Privilege Escalation Detected",
            "severity": "critical",
            "description_zh": "账号权限从普通用户提升为管理员",
            "description_en": "An account's privileges escalated from regular user to administrator",
        },
        {
            "type": "cross_asset_awakening",
            "label_zh": "跨资产同时活跃",
            "label_en": "Cross-Asset Simultaneous Activity",
            "severity": "critical",
            "description_zh": "同一账号在多个资产上同时恢复活跃（此前均休眠）",
            "description_en": "The same account became active across multiple assets simultaneously (all were dormant before)",
        },
    ]
