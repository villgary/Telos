from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.database import get_db
from backend import models, schemas, auth

router = APIRouter(prefix="/api/v1/users", tags=["用户管理"])


@router.get("", response_model=list[schemas.UserResponse])
async def list_users(
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.require_role(models.UserRole.admin)),
):
    """List all users (admin only)."""
    return db.query(models.User).order_by(models.User.id).all()


@router.post("", response_model=schemas.UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_in: schemas.UserCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.require_role(models.UserRole.admin)),
):
    """Create a new user (admin only)."""
    existing = db.query(models.User).filter(models.User.username == user_in.username).first()
    if existing:
        raise HTTPException(status_code=400, detail="用户名已存在")

    new_user = models.User(
        username=user_in.username,
        password_hash=auth.hash_password(user_in.password),
        role=user_in.role,
        email=user_in.email,
        is_active=True,
        is_password_changed=True,  # Admin-created user doesn't need forced password change
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user


@router.put("/{target_id}", response_model=schemas.UserResponse)
async def update_user(
    target_id: int,
    update_in: schemas.UserUpdate,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.require_role(models.UserRole.admin)),
):
    """Update user role, email, active status, or password (admin only)."""
    target = db.query(models.User).filter(models.User.id == target_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="用户不存在")

    # Prevent admin from deactivating the last admin
    if update_in.is_active is not None and not update_in.is_active:
        admin_count = db.query(models.User).filter(
            models.User.role == models.UserRole.admin,
            models.User.is_active == True,
            models.User.id != target_id,
        ).count()
        if admin_count == 0:
            raise HTTPException(status_code=400, detail="不能禁用最后一个管理员账号")

    if update_in.role is not None:
        target.role = update_in.role
    if update_in.email is not None:
        target.email = update_in.email
    if update_in.is_active is not None:
        target.is_active = update_in.is_active
    if update_in.password is not None:
        auth.validate_password_strength(update_in.password)
        target.password_hash = auth.hash_password(update_in.password)
        target.is_password_changed = True

    db.commit()
    db.refresh(target)
    return target


@router.delete("/{target_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    target_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.require_role(models.UserRole.admin)),
):
    """Delete a user (admin only). Cannot delete yourself."""
    if target_id == user.id:
        raise HTTPException(status_code=400, detail="不能删除自己")

    target = db.query(models.User).filter(models.User.id == target_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="用户不存在")

    db.delete(target)
    db.commit()
