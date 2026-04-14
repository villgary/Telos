from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from backend.database import get_db
from backend import models, schemas, auth
from backend.middleware.rate_limit import limiter

router = APIRouter(prefix="/api/v1/auth", tags=["认证"])


def _issue_tokens(db: Session, user: models.User, ip: str):
    """Create access token + refresh token, return both."""
    access_token = auth.create_access_token(data={"sub": user.username})
    refresh_token = auth._generate_refresh_token()
    token_hash = auth._hash_token(refresh_token)

    rt = models.RefreshToken(
        token_hash=token_hash,
        user_id=user.id,
        expires_at=datetime.now(timezone.utc) + timedelta(days=auth.REFRESH_TOKEN_EXPIRE_DAYS),
        ip_address=ip,
    )
    db.add(rt)
    db.commit()

    return access_token, refresh_token


@router.post("/login", response_model=schemas.TokenResponse)
@limiter.limit("5/minute")
async def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    """
    OAuth2 compatible token login. Returns access_token + expires_in seconds.
    On first login with default password, client should prompt password change.
    """
    user = db.query(models.User).filter(models.User.username == form_data.username).first()
    if not user or not auth.verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(status_code=403, detail="用户已被禁用")

    client_ip = auth.get_client_ip(request)
    access_token, refresh_token = _issue_tokens(db, user, client_ip)

    return schemas.TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=auth.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/refresh", response_model=schemas.RefreshResponse)
@limiter.limit("10/minute")
async def refresh_token(
    req: schemas.RefreshRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Exchange a valid refresh token for a new access token.
    Implements token rotation: old token is revoked after use.
    """
    token_hash = auth._hash_token(req.refresh_token)
    rt = db.query(models.RefreshToken).filter(
        models.RefreshToken.token_hash == token_hash,
    ).first()

    if not rt:
        raise HTTPException(status_code=401, detail="无效的 refresh token")

    if rt.revoked:
        raise HTTPException(status_code=401, detail="refresh token 已被撤销，请重新登录")

    if rt.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=401, detail="refresh token 已过期")

    user = db.query(models.User).filter(models.User.id == rt.user_id).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="用户不存在或已禁用")

    # Rotate: revoke old token and issue new one
    rt.revoked = True
    client_ip = auth.get_client_ip(request)

    # IP anomaly detection: log if refresh token is used from a different IP
    if rt.ip_address and rt.ip_address != client_ip:
        from backend.logging_config import logger
        logger.warning(
            "security.token.refresh_ip_mismatch",
            user_id=user.id,
            username=user.username,
            original_ip=rt.ip_address,
            current_ip=client_ip,
            token_id=rt.id,
        )

    new_access_token, new_refresh_token = _issue_tokens(db, user, client_ip)

    return schemas.RefreshResponse(
        access_token=new_access_token,
        token_type="bearer",
        expires_in=auth.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    req: schemas.RefreshRequest,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.get_current_user),
):
    """Revoke a specific refresh token."""
    token_hash = auth._hash_token(req.refresh_token)
    rt = db.query(models.RefreshToken).filter(
        models.RefreshToken.token_hash == token_hash,
        models.RefreshToken.user_id == user.id,
    ).first()
    if rt:
        rt.revoked = True
        db.commit()


@router.post("/password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    body: schemas.PasswordChange,
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.get_current_user),
):
    """Change own password. Requires correct old password and meets new password policy."""
    if not auth.verify_password(body.old_password, user.password_hash):
        raise HTTPException(status_code=400, detail="原密码错误")

    try:
        auth.validate_password_strength(body.new_password)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    user.password_hash = auth.hash_password(body.new_password)
    user.is_password_changed = True
    db.commit()

    # Revoke all existing refresh tokens for this user (forced re-login)
    db.query(models.RefreshToken).filter(
        models.RefreshToken.user_id == user.id,
        models.RefreshToken.revoked == False,  # noqa: E712
    ).update({"revoked": True})
    db.commit()


@router.get("/me", response_model=schemas.UserResponse)
async def get_me(user: models.User = Depends(auth.get_current_user)):
    return user


@router.post("/users", response_model=schemas.UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_in: schemas.UserCreate,
    db: Session = Depends(get_db),
    admin: models.User = Depends(auth.require_admin),
):
    """Create a new user (admin only)."""
    existing = db.query(models.User).filter(models.User.username == user_in.username).first()
    if existing:
        raise HTTPException(status_code=400, detail="用户名已存在")

    user = models.User(
        username=user_in.username,
        password_hash=auth.hash_password(user_in.password),
        role=user_in.role,
        email=user_in.email,
        is_password_changed=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.get("/users", response_model=list[schemas.UserResponse])
async def list_users(
    db: Session = Depends(get_db),
    admin: models.User = Depends(auth.require_admin),
):
    return db.query(models.User).all()
