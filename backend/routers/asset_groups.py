from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.database import get_db
from backend import models, schemas, auth

router = APIRouter(prefix="/api/v1/asset-groups", tags=["资产分组"])


@router.get("", response_model=list[schemas.AssetGroupResponse])
async def list_groups(
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.get_current_user),
):
    """List all asset groups."""
    return db.query(models.AssetGroup).all()


@router.post("", response_model=schemas.AssetGroupResponse, status_code=status.HTTP_201_CREATED)
async def create_group(
    group_in: schemas.AssetGroupCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.require_role(models.UserRole.operator, models.UserRole.admin)),
):
    """Create a new asset group (operator+)."""
    existing = db.query(models.AssetGroup).filter(
        models.AssetGroup.name == group_in.name
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="分组名称已存在")

    group = models.AssetGroup(
        name=group_in.name,
        description=group_in.description,
        color=group_in.color,
        created_by=user.id,
    )
    db.add(group)
    db.commit()
    db.refresh(group)
    return group


@router.put("/{group_id}", response_model=schemas.AssetGroupResponse)
async def update_group(
    group_id: int,
    update_in: schemas.AssetGroupUpdate,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.require_role(models.UserRole.operator, models.UserRole.admin)),
):
    """Update an asset group (operator+)."""
    group = db.query(models.AssetGroup).filter(models.AssetGroup.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="分组不存在")

    if update_in.name is not None:
        existing = db.query(models.AssetGroup).filter(
            models.AssetGroup.name == update_in.name,
            models.AssetGroup.id != group_id,
        ).first()
        if existing:
            raise HTTPException(status_code=400, detail="分组名称已被占用")
        group.name = update_in.name
    if update_in.description is not None:
        group.description = update_in.description
    if update_in.color is not None:
        group.color = update_in.color

    db.commit()
    db.refresh(group)
    return group


@router.delete("/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_group(
    group_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.require_role(models.UserRole.admin)),
):
    """Delete an asset group (admin only)."""
    group = db.query(models.AssetGroup).filter(models.AssetGroup.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="分组不存在")
    if group.assets:
        raise HTTPException(status_code=400, detail="此分组仍包含资产，无法删除")
    db.delete(group)
    db.commit()
