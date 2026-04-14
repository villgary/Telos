import os
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from backend.database import get_db
from backend import models, schemas

# ── Config (all security-sensitive vars are mandatory) ─────────

_JWT_SECRET = os.getenv("ACCOUNTSCAN_JWT_SECRET")
if not _JWT_SECRET:
    raise RuntimeError(
        "ACCOUNTSCAN_JWT_SECRET environment variable is not set. "
        "Generate one: python -c \"import secrets; print(secrets.token_hex(32))\""
    )

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "15"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


# ── Helpers ────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, _JWT_SECRET, algorithm=ALGORITHM)


def _hash_token(token: str) -> str:
    """SHA-256 hash a token for storage."""
    return hashlib.sha256(token.encode()).hexdigest()


def _generate_refresh_token() -> str:
    return secrets.token_urlsafe(48)  # ~64-char URL-safe token


def validate_password_strength(password: str) -> None:
    """Raise ValueError if password doesn't meet strength requirements.

    Delegates to schemas._check_password_strength (single source of truth).
    """
    schemas._check_password_strength(password)


def get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


# ── Dependencies ──────────────────────────────────────────────

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> models.User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="无效或已过期的认证凭据",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, _JWT_SECRET, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = db.query(models.User).filter(models.User.username == username).first()
    if user is None or not user.is_active:
        raise credentials_exception
    return user


def require_role(*roles: models.UserRole):
    """Dependency factory: require current user has one of the given roles."""
    def dependency(user: models.User = Depends(get_current_user)) -> models.User:
        if user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"此操作需要以下角色之一: {', '.join(r.value for r in roles)}",
            )
        return user
    return dependency


def require_admin(user: models.User = Depends(get_current_user)) -> models.User:
    if user.role != models.UserRole.admin:
        raise HTTPException(status_code=403, detail="需要 admin 角色")
    return user


# ── Seed ──────────────────────────────────────────────────────

def seed_default_user(db: Session):
    """Create default admin if no users exist."""
    if db.query(models.User).count() == 0:
        admin_password = os.getenv("ACCOUNTSCAN_ADMIN_PASSWORD")
        if not admin_password:
            raise RuntimeError(
                "ACCOUNTSCAN_ADMIN_PASSWORD environment variable is not set. "
                "Generate one: python -c \"import secrets; print(secrets.token_urlsafe(24))\""
            )
        admin = models.User(
            username="admin",
            password_hash=hash_password(admin_password),
            role=models.UserRole.admin,
            email="admin@example.com",
            is_password_changed=False,
        )
        db.add(admin)
        db.commit()
