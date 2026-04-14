from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy.orm import Session
from fastapi.responses import StreamingResponse
import asyncio

from backend.database import get_db
from backend import models, schemas, auth
from backend.services.alert_sse_manager import alert_manager

router = APIRouter(prefix="/api/v1/alerts", tags=["告警"])


# ── Shared alert-creation helper (used by other routers/services) ────────────────

async def create_and_broadcast_alert(
    *,
    db: Session,
    asset_id: int,
    level: models.AlertLevel,
    title: str,
    message: str,
    job_id: int | None = None,
    diff_item_id: int | None = None,
    title_key: str | None = None,
    title_params: dict | None = None,
    message_key: str | None = None,
    message_params: dict | None = None,
) -> models.Alert:
    """
    Persist a new alert and broadcast it to all connected SSE clients.

    Usage from any service or router:
        from backend.routers.alerts import create_and_broadcast_alert
        await create_and_broadcast_alert(
            db=db, asset_id=aid, level=AlertLevel.critical,
            title="High-risk account detected",
            message="Account xyz on asset foo has critical risk level",
        )
    """
    alert = models.Alert(
        asset_id=asset_id,
        level=level,
        title=title,
        message=message,
        job_id=job_id,
        diff_item_id=diff_item_id,
        title_key=title_key,
        title_params=title_params,
        message_key=message_key,
        message_params=message_params,
    )
    db.add(alert)
    db.commit()
    db.refresh(alert)

    # Broadcast to all SSE clients
    try:
        alert_dict = schemas.AlertResponse.model_validate(alert).model_dump(mode="json")
        await alert_manager.broadcast(alert_dict)
    except Exception:
        # Never let broadcast failure break the main flow
        pass

    return alert


# ─────────────── Alert Config ───────────────

@router.get("/configs", response_model=list[schemas.AlertConfigResponse])
async def list_alert_configs(
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.require_role(models.UserRole.operator, models.UserRole.admin)),
):
    return db.query(models.AlertConfig).all()


@router.post("/configs", response_model=schemas.AlertConfigResponse, status_code=status.HTTP_201_CREATED)
async def create_alert_config(
    config_in: schemas.AlertConfigCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.require_role(models.UserRole.admin)),
):
    config = models.AlertConfig(
        name=config_in.name,
        channel=config_in.channel,
        enabled=config_in.enabled,
        settings=config_in.settings,
        asset_ids=config_in.asset_ids,
        risk_levels=config_in.risk_levels,
        created_by=user.id,
    )
    db.add(config)
    db.commit()
    db.refresh(config)
    return config


@router.put("/configs/{config_id}", response_model=schemas.AlertConfigResponse)
async def update_alert_config(
    config_id: int,
    update_in: schemas.AlertConfigUpdate,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.require_role(models.UserRole.admin)),
):
    config = db.query(models.AlertConfig).filter(models.AlertConfig.id == config_id).first()
    if not config:
        raise HTTPException(status_code=404, detail="告警配置不存在")

    if update_in.name is not None:
        config.name = update_in.name
    if update_in.enabled is not None:
        config.enabled = update_in.enabled
    if update_in.settings is not None:
        config.settings = update_in.settings
    if update_in.asset_ids is not None:
        config.asset_ids = update_in.asset_ids
    if update_in.risk_levels is not None:
        config.risk_levels = update_in.risk_levels

    db.commit()
    db.refresh(config)
    return config


@router.delete("/configs/{config_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_alert_config(
    config_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.require_role(models.UserRole.admin)),
):
    config = db.query(models.AlertConfig).filter(models.AlertConfig.id == config_id).first()
    if not config:
        raise HTTPException(status_code=404, detail="告警配置不存在")
    db.delete(config)
    db.commit()


# ─────────────── Alert List ───────────────

@router.get("", response_model=schemas.AlertListResponse)
async def list_alerts(
    asset_id: int = None,
    is_read: bool = None,
    status: str = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.get_current_user),
):
    query = db.query(models.Alert)
    if asset_id:
        query = query.filter(models.Alert.asset_id == asset_id)
    if is_read is not None:
        query = query.filter(models.Alert.is_read == is_read)
    if status:
        query = query.filter(models.Alert.status == status)

    total = query.count()
    unread_count = db.query(models.Alert).filter(models.Alert.is_read == False).count()

    alerts = (
        query.order_by(models.Alert.created_at.desc())
        .offset(offset).limit(limit).all()
    )
    return schemas.AlertListResponse(
        total=total,
        unread_count=unread_count,
        alerts=[schemas.AlertResponse.model_validate(a) for a in alerts],
    )


@router.post("/{alert_id}/read", status_code=status.HTTP_204_NO_CONTENT)
async def mark_alert_read(
    alert_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.get_current_user),
):
    alert = db.query(models.Alert).filter(models.Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="告警不存在")
    alert.is_read = True
    db.commit()


@router.post("/read-all", status_code=status.HTTP_204_NO_CONTENT)
async def mark_all_read(
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.require_role(models.UserRole.operator, models.UserRole.admin)),
):
    db.query(models.Alert).filter(models.Alert.is_read == False).update({"is_read": True})
    db.commit()


@router.delete("/{alert_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_alert(
    alert_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.require_role(models.UserRole.operator, models.UserRole.admin)),
):
    alert = db.query(models.Alert).filter(models.Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="告警不存在")
    db.delete(alert)
    db.commit()


# ─────────────── Alert Actions ───────────────

@router.post("/{alert_id}/acknowledge", response_model=schemas.AlertResponse)
async def acknowledge_alert(
    alert_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.get_current_user),
):
    """Acknowledge an alert — operator confirms receipt."""
    alert = db.query(models.Alert).filter(models.Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="告警不存在")
    alert.status = "acknowledged"
    alert.is_read = True
    db.commit()
    db.refresh(alert)
    return alert


@router.post("/{alert_id}/dismiss", response_model=schemas.AlertResponse)
async def dismiss_alert(
    alert_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.require_role(models.UserRole.operator, models.UserRole.admin)),
):
    """Dismiss an alert — mark as not actionable / false positive."""
    alert = db.query(models.Alert).filter(models.Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="告警不存在")
    alert.status = "dismissed"
    alert.is_read = True
    db.commit()
    db.refresh(alert)
    return alert


@router.post("/{alert_id}/respond", response_model=schemas.AlertResponse)
async def respond_to_alert(
    alert_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.require_role(models.UserRole.operator, models.UserRole.admin)),
):
    """Mark alert as responded — action has been taken."""
    alert = db.query(models.Alert).filter(models.Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="告警不存在")
    alert.status = "responded"
    alert.is_read = True
    db.commit()
    db.refresh(alert)
    return alert


# ─────────────── Real-time SSE Stream ─────────────────────────────────────────

@router.get("/stream")
async def alert_stream(
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.get_current_user),
):
    """
    Server-Sent Events (SSE) stream of new alerts.

    Frontend connects via:
      const es = new EventSource('/api/v1/alerts/stream')

    Each event is a JSON-encoded AlertResponse.
    Heartbeat comments (: heartbeat\\n\\n) are sent every 25s to keep
    the connection alive behind nginx proxies.
    """
    async def event_generator():
        queue = alert_manager.connect(user.id)
        heartbeat_count = 0
        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=25)
                    yield event
                    heartbeat_count = 0
                except asyncio.TimeoutError:
                    yield ": heartbeat\n\n"
                    heartbeat_count += 1
                    if heartbeat_count > 5:
                        break
        except asyncio.CancelledError:
            pass
        finally:
            alert_manager.disconnect(user.id)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",   # disable nginx buffering for SSE
        },
    )


@router.post("/{alert_id}/broadcast-test", response_model=schemas.AlertResponse)
async def broadcast_test_alert(
    alert_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.get_current_user),
):
    """
    Re-broadcast an existing alert to all SSE clients (for testing).
    In production, alerts are broadcast automatically when created
    by the realtime_monitor or identity_threat_analyzer.
    """
    alert = db.query(models.Alert).filter(models.Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="告警不存在")

    alert_dict = schemas.AlertResponse.model_validate(alert).model_dump(mode="json")
    await alert_manager.broadcast(alert_dict)
    return alert
