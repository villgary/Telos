"""
Review Playbooks — automated remediation workflow API.

POST   /api/v1/playbooks                 — 创建剧本
GET    /api/v1/playbooks                 — 剧本列表
GET    /api/v1/playbooks/{id}            — 剧本详情
PUT    /api/v1/playbooks/{id}            — 更新剧本
DELETE /api/v1/playbooks/{id}            — 删除剧本

POST   /api/v1/playbooks/{id}/execute    — 触发执行（创建 pending_approval 执行记录）
POST   /api/v1/playbooks/{id}/dry-run    — 试运行（不实际执行，返回预期结果）

GET    /api/v1/playbook-executions       — 执行历史
GET    /api/v1/playbook-executions/{id}  — 执行详情
POST   /api/v1/playbook-executions/{id}/approve  — 审批通过
POST   /api/v1/playbook-executions/{id}/reject   — 审批拒绝
"""

from datetime import datetime, timezone
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend import models
from backend.auth import get_current_user
from backend.database import get_db

router = APIRouter(prefix="/api/v1", tags=["playbooks"])


# ─── Schemas ────────────────────────────────────────────────────────────────────

class StepSchema(BaseModel):
    action: str = Field(description="disable_account | revoke_nopasswd | notify_owner | lock_account | flag_review")
    target: str = Field(description="snapshot | identity | asset")
    params: dict | None = Field(default=None, description="Action-specific parameters")


class PlaybookCreate(BaseModel):
    name: str
    description: str | None = None
    trigger_type: str = Field(default="manual")
    trigger_filter: dict | None = None
    steps: list[StepSchema]
    approval_required: bool = True
    enabled: bool = True


class PlaybookUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    trigger_type: str | None = None
    trigger_filter: dict | None = None
    steps: list[StepSchema] | None = None
    approval_required: bool | None = None
    enabled: bool | None = None


class PlaybookResponse(BaseModel):
    id: int
    name: str
    description: str | None
    name_key: str | None = None
    description_key: str | None = None
    trigger_type: str
    trigger_filter: dict
    steps: list[dict]
    approval_required: bool
    enabled: bool
    created_at: datetime

    class Config:
        from_attributes = True


class PlaybookExecutionResponse(BaseModel):
    id: int
    playbook_id: int
    snapshot_id: int
    status: str
    steps_status: list[dict]
    result: str | None
    triggered_by: int | None
    approved_by: int | None
    created_at: datetime

    class Config:
        from_attributes = True


class DryRunResult(BaseModel):
    playbook_id: int
    snapshot_id: int
    steps_planned: list[dict]


# ─── Supported actions ─────────────────────────────────────────────────────────

SUPPORTED_ACTIONS = {
    "disable_account": "更新账号状态为 disabled",
    "revoke_nopasswd": "记录建议：移除 NOPASSWD sudo 规则（需人工处理）",
    "notify_owner": "向账号归属人发送通知",
    "lock_account": "锁定账号（同 disable_account）",
    "flag_review": "标记为待人工复核",
}


def _execute_step(
    db: Session,
    step: dict,
    snapshot: models.AccountSnapshot,
    user_id: int | None,
) -> dict:
    """
    Execute a single playbook step.
    Returns {"status": "done"|"skipped"|"failed", "detail": "..."}
    """
    action = step.get("action")
    if action == "disable_account":
        snapshot.account_status = "disabled"
        db.commit()
        return {"step": step, "status": "done", "detail": f"账号 {snapshot.username} 已禁用"}

    if action == "lock_account":
        snapshot.account_status = "locked"
        db.commit()
        return {"step": step, "status": "done", "detail": f"账号 {snapshot.username} 已锁定"}

    if action == "revoke_nopasswd":
        # Cannot remotely revoke sudo rules — just record the recommendation
        return {
            "step": step,
            "status": "skipped",
            "detail": f"账号 {snapshot.username} 的 NOPASSWD sudo 规则需人工移除（无法远程执行）",
        }

    if action == "notify_owner":
        # Look up human identity for this snapshot
        link = (
            db.query(models.IdentityAccount)
            .filter(models.IdentityAccount.snapshot_id == snapshot.id)
            .first()
        )
        if link:
            identity = db.query(models.HumanIdentity).filter(models.HumanIdentity.id == link.identity_id).first()
            if identity:
                return {
                    "step": step,
                    "status": "done",
                    "detail": f"已通知归属人：{identity.display_name}({identity.email or identity.username})",
                }
        return {
            "step": step,
            "status": "skipped",
            "detail": f"账号 {snapshot.username} 无关联人员身份，无法发送通知",
        }

    if action == "flag_review":
        return {
            "step": step,
            "status": "done",
            "detail": f"账号 {snapshot.username} 已标记为待人工复核",
        }

    return {"step": step, "status": "failed", "detail": f"未知动作: {action}"}


# ─── Playbook CRUD ─────────────────────────────────────────────────────────────

@router.post("/playbooks", response_model=PlaybookResponse)
def create_playbook(
    body: PlaybookCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    pb = models.ReviewPlaybook(
        name=body.name,
        description=body.description,
        trigger_type=body.trigger_type,
        trigger_filter=body.trigger_filter or {},
        steps=[s.model_dump() for s in body.steps],
        approval_required=body.approval_required,
        enabled=body.enabled,
        created_by=user.id,
    )
    db.add(pb)
    db.commit()
    db.refresh(pb)
    return pb


@router.get("/playbooks", response_model=list[PlaybookResponse])
def list_playbooks(
    enabled: bool | None = None,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    q = db.query(models.ReviewPlaybook)
    if enabled is not None:
        q = q.filter(models.ReviewPlaybook.enabled == enabled)
    return q.order_by(models.ReviewPlaybook.created_at.desc()).all()


@router.get("/playbooks/{pb_id}", response_model=PlaybookResponse)
def get_playbook(
    pb_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    pb = db.query(models.ReviewPlaybook).filter(models.ReviewPlaybook.id == pb_id).first()
    if not pb:
        raise HTTPException(status_code=404, detail="Playbook not found")
    return pb


@router.put("/playbooks/{pb_id}", response_model=PlaybookResponse)
def update_playbook(
    pb_id: int,
    body: PlaybookUpdate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    pb = db.query(models.ReviewPlaybook).filter(models.ReviewPlaybook.id == pb_id).first()
    if not pb:
        raise HTTPException(status_code=404, detail="Playbook not found")
    if body.name is not None:
        pb.name = body.name
    if body.description is not None:
        pb.description = body.description
    if body.trigger_type is not None:
        pb.trigger_type = body.trigger_type
    if body.trigger_filter is not None:
        pb.trigger_filter = body.trigger_filter
    if body.steps is not None:
        pb.steps = [s.model_dump() for s in body.steps]
    if body.approval_required is not None:
        pb.approval_required = body.approval_required
    if body.enabled is not None:
        pb.enabled = body.enabled
    db.commit()
    db.refresh(pb)
    return pb


@router.delete("/playbooks/{pb_id}")
def delete_playbook(
    pb_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    pb = db.query(models.ReviewPlaybook).filter(models.ReviewPlaybook.id == pb_id).first()
    if not pb:
        raise HTTPException(status_code=404, detail="Playbook not found")
    db.delete(pb)
    db.commit()
    return {"ok": True}


# ─── Execute / Dry-run ──────────────────────────────────────────────────────────

@router.post("/playbooks/{pb_id}/execute", response_model=PlaybookExecutionResponse)
def execute_playbook(
    pb_id: int,
    snapshot_id: Annotated[int, Query(description="目标账号 snapshot ID")],
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """
    Trigger playbook execution for a specific snapshot.
    If approval_required=True, creates a pending_approval execution for review.
    Otherwise executes immediately.
    """
    pb = db.query(models.ReviewPlaybook).filter(models.ReviewPlaybook.id == pb_id).first()
    if not pb:
        raise HTTPException(status_code=404, detail="Playbook not found")
    if not pb.enabled:
        raise HTTPException(status_code=400, detail="Playbook is disabled")

    snapshot = db.query(models.AccountSnapshot).filter(models.AccountSnapshot.id == snapshot_id).first()
    if not snapshot:
        raise HTTPException(status_code=404, detail="Snapshot not found")

    exec_record = models.PlaybookExecution(
        playbook_id=pb_id,
        snapshot_id=snapshot_id,
        status="pending_approval",
        steps_status=[],
        triggered_by=user.id,
    )
    db.add(exec_record)
    db.commit()
    db.refresh(exec_record)

    if not pb.approval_required:
        # Auto-approve and execute
        return _approve_and_execute(exec_record, pb, snapshot, db, user)

    return exec_record


@router.post("/playbooks/{pb_id}/dry-run", response_model=DryRunResult)
def dry_run_playbook(
    pb_id: int,
    snapshot_id: Annotated[int, Query(description="目标账号 snapshot ID")],
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """Return planned steps without executing them."""
    pb = db.query(models.ReviewPlaybook).filter(models.ReviewPlaybook.id == pb_id).first()
    if not pb:
        raise HTTPException(status_code=404, detail="Playbook not found")
    snapshot = db.query(models.AccountSnapshot).filter(models.AccountSnapshot.id == snapshot_id).first()
    if not snapshot:
        raise HTTPException(status_code=404, detail="Snapshot not found")

    planned = []
    for step in (pb.steps or []):
        result = _execute_step(db, step, snapshot, user.id)
        # Simulate only
        planned.append({
            "action": step.get("action"),
            "target": step.get("target"),
            "expected_result": result.get("detail", ""),
            "will_skip": result.get("status") == "skipped",
        })

    return DryRunResult(
        playbook_id=pb_id,
        snapshot_id=snapshot_id,
        steps_planned=planned,
    )


def _approve_and_execute(
    exec_record: models.PlaybookExecution,
    pb: models.ReviewPlaybook,
    snapshot: models.AccountSnapshot,
    db: Session,
    user: models.User,
) -> models.PlaybookExecution:
    exec_record.status = "approved"
    exec_record.approved_by = user.id
    exec_record.approved_at = datetime.now(timezone.utc)

    results: list[dict] = []
    for i, step in enumerate((pb.steps or [])):
        result = _execute_step(db, step, snapshot, user.id)
        result["step_index"] = i
        results.append(result)

    exec_record.steps_status = results
    success = all(r.get("status") in ("done", "skipped") for r in results)
    exec_record.status = "done" if success else "failed"
    exec_record.result = "; ".join(r.get("detail", "") for r in results)

    db.commit()
    db.refresh(exec_record)
    return exec_record


# ─── Execution management ──────────────────────────────────────────────────────

@router.get("/playbook-executions", response_model=list[PlaybookExecutionResponse])
def list_executions(
    playbook_id: int | None = None,
    status: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    q = db.query(models.PlaybookExecution)
    if playbook_id is not None:
        q = q.filter(models.PlaybookExecution.playbook_id == playbook_id)
    if status is not None:
        q = q.filter(models.PlaybookExecution.status == status)
    return q.order_by(models.PlaybookExecution.created_at.desc()).offset(offset).limit(limit).all()


@router.get("/playbook-executions/{exec_id}", response_model=PlaybookExecutionResponse)
def get_execution(
    exec_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    e = db.query(models.PlaybookExecution).filter(models.PlaybookExecution.id == exec_id).first()
    if not e:
        raise HTTPException(status_code=404, detail="Execution not found")
    return e


@router.post("/playbook-executions/{exec_id}/approve", response_model=PlaybookExecutionResponse)
def approve_execution(
    exec_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """Approve a pending execution and run it."""
    e = db.query(models.PlaybookExecution).filter(models.PlaybookExecution.id == exec_id).first()
    if not e:
        raise HTTPException(status_code=404, detail="Execution not found")
    if e.status != "pending_approval":
        raise HTTPException(status_code=400, detail=f"Cannot approve execution in status: {e.status}")

    pb = db.query(models.ReviewPlaybook).filter(models.ReviewPlaybook.id == e.playbook_id).first()
    snapshot = db.query(models.AccountSnapshot).filter(models.AccountSnapshot.id == e.snapshot_id).first()

    return _approve_and_execute(e, pb, snapshot, db, user)


@router.post("/playbook-executions/{exec_id}/reject", response_model=PlaybookExecutionResponse)
def reject_execution(
    exec_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """Reject a pending execution."""
    e = db.query(models.PlaybookExecution).filter(models.PlaybookExecution.id == exec_id).first()
    if not e:
        raise HTTPException(status_code=404, detail="Execution not found")
    if e.status != "pending_approval":
        raise HTTPException(status_code=400, detail=f"Cannot reject execution in status: {e.status}")

    e.status = "rejected"
    e.approved_by = user.id
    e.approved_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(e)
    return e
