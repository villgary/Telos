"""AI Agent Cloud Discovery — CRUD on configured provider connections +
sync-now + per-connection audit log.

The user-facing concept is *discovery*: each configured `CloudConnection`
is a source that Telos periodically queries (or queries on demand) to
enumerate AI agents that exist in a provider account.
"""
from __future__ import annotations

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend import models, auth
from backend.database import get_db
from backend.schemas import cloud_connections as cloud_schemas
from backend.services import crypto
from backend.services.cloud_discovery.sync import run_connection_sync


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/ai-agents/discovery", tags=["ai-agents"])


# ── Helpers ────────────────────────────────────────────────────────────

def _write_audit(
    db: Session, connection_id: int, actor_user_id: int, action: str,
    *, before: dict | None = None, after: dict | None = None,
    status_val: str | None = None, note: str | None = None,
) -> None:
    """Insert a cloud_connection_audit_log row.

    `before` and `after` MUST NOT contain the api_key (plaintext or encrypted).
    They are name-only.
    """
    entry = models.CloudConnectionAuditLog(
        connection_id=connection_id,
        actor_user_id=actor_user_id,
        action=action,
        status=status_val,
        before=before,
        after=after,
        note=note,
    )
    db.add(entry)


# ── Endpoints ──────────────────────────────────────────────────────────

@router.get("", response_model=cloud_schemas.CloudConnectionListResponse)
async def list_connections(
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.get_current_user),
):
    rows = db.query(models.CloudConnection).order_by(models.CloudConnection.id).all()
    return cloud_schemas.CloudConnectionListResponse(
        total=len(rows),
        connections=[cloud_schemas.CloudConnectionResponse.model_validate(r) for r in rows],
    )


@router.post("", response_model=cloud_schemas.CloudConnectionResponse,
             status_code=status.HTTP_201_CREATED)
async def create_connection(
    body: cloud_schemas.CloudConnectionCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.require_admin),
):
    fp = crypto.fingerprint(body.api_key)
    if not fp:
        raise HTTPException(status_code=400, detail="api_key produced empty fingerprint")
    enc = crypto.encrypt(body.api_key)
    conn = models.CloudConnection(
        name=body.name,
        provider=body.provider,
        encrypted_api_key=enc,
        api_key_fingerprint=fp,
        created_by_user_id=user.id,
    )
    db.add(conn)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail=f"connection name '{body.name}' already exists")
    _write_audit(db, conn.id, user.id, "created",
                 after={"name": conn.name, "provider": conn.provider,
                        "api_key_fingerprint": conn.api_key_fingerprint})
    db.commit()
    db.refresh(conn)
    return conn


@router.patch("/{connection_id}", response_model=cloud_schemas.CloudConnectionResponse)
async def update_connection(
    connection_id: int,
    body: cloud_schemas.CloudConnectionUpdate,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.require_admin),
):
    conn = db.query(models.CloudConnection).filter(
        models.CloudConnection.id == connection_id).first()
    if not conn:
        raise HTTPException(status_code=404, detail="connection not found")
    before_name = conn.name
    conn.name = body.name
    _write_audit(db, conn.id, user.id, "renamed",
                 before={"name": before_name},
                 after={"name": conn.name})
    db.commit()
    db.refresh(conn)
    return conn


@router.post("/{connection_id}/rotate", response_model=cloud_schemas.CloudConnectionResponse)
async def rotate_connection(
    connection_id: int,
    body: cloud_schemas.CloudConnectionRotate,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.require_admin),
):
    conn = db.query(models.CloudConnection).filter(
        models.CloudConnection.id == connection_id).first()
    if not conn:
        raise HTTPException(status_code=404, detail="connection not found")
    fp = crypto.fingerprint(body.api_key)
    if not fp:
        raise HTTPException(status_code=400, detail="api_key produced empty fingerprint")
    old_fp = conn.api_key_fingerprint
    conn.encrypted_api_key = crypto.encrypt(body.api_key)
    conn.api_key_fingerprint = fp
    _write_audit(db, conn.id, user.id, "rotated",
                 before={"api_key_fingerprint": old_fp},
                 after={"api_key_fingerprint": fp})
    db.commit()
    db.refresh(conn)
    return conn


@router.delete("/{connection_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_connection(
    connection_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.require_admin),
):
    conn = db.query(models.CloudConnection).filter(
        models.CloudConnection.id == connection_id).first()
    if not conn:
        raise HTTPException(status_code=404, detail="connection not found")
    before = {"name": conn.name, "provider": conn.provider,
              "api_key_fingerprint": conn.api_key_fingerprint}
    _write_audit(db, conn.id, user.id, "deleted", before=before)
    # Soft-delete: NULL the FK on ai_agents but keep the agents
    db.query(models.AIAgent).filter(
        models.AIAgent.connection_id == connection_id
    ).update({models.AIAgent.connection_id: None})
    db.delete(conn)
    db.commit()
    return None


@router.post("/{connection_id}/sync", response_model=cloud_schemas.CloudConnectionSyncResponse)
async def sync_connection(
    connection_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.require_admin),
):
    conn = db.query(models.CloudConnection).filter(
        models.CloudConnection.id == connection_id).first()
    if not conn:
        raise HTTPException(status_code=404, detail="connection not found")
    if conn.last_sync_status == "running":
        raise HTTPException(status_code=409, detail="sync already in progress")

    _write_audit(db, conn.id, user.id, "sync_started")
    conn.last_sync_started_at = datetime.utcnow()
    db.commit()

    result = run_connection_sync(db, conn)
    db.commit()
    db.refresh(conn)

    err_truncated = result["error"]
    _write_audit(db, conn.id, user.id, "sync_finished",
                 status_val=result["status"], note=err_truncated)
    db.commit()
    return cloud_schemas.CloudConnectionSyncResponse(
        connection_id=conn.id,
        status=result["status"],
        agents_discovered=result["agents_discovered"],
        agents_updated=result["agents_updated"],
        error=err_truncated,
    )


@router.get("/{connection_id}/audit",
            response_model=cloud_schemas.CloudConnectionAuditListResponse)
async def list_audit(
    connection_id: int,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.get_current_user),
):
    if not db.query(models.CloudConnection).filter(
            models.CloudConnection.id == connection_id).first():
        raise HTTPException(status_code=404, detail="connection not found")
    q = db.query(models.CloudConnectionAuditLog).filter(
        models.CloudConnectionAuditLog.connection_id == connection_id
    ).order_by(models.CloudConnectionAuditLog.created_at.desc())
    total = q.count()
    rows = q.offset(offset).limit(limit).all()
    return cloud_schemas.CloudConnectionAuditListResponse(
        total=total,
        entries=[cloud_schemas.CloudConnectionAuditEntry.model_validate(r) for r in rows],
    )
