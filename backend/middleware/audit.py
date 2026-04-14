"""
Audit log decorator + helper for recording write operations.
Usage:
    from backend.middleware.audit import audit_log

    @router.post("/assets", ...)
    @audit_log(action="asset.create")
    async def create_asset(...):
        ...
"""
import functools
import json
import re
from typing import Callable, Optional, Set

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import AuditLog, User
from backend.auth import get_current_user
from backend.logging_config import get_trace_id


# Sensitive fields to redact from request body in audit logs.
# Uses case-insensitive substring matching to catch variants like
# "password", "Password", "PASSWORD", "password_hash", "old_password", etc.
_SENSITIVE_FIELD_PATTERNS: Set[str] = {
    "password", "passphrase", "secret", "token", "private_key",
    "access_token", "refresh_token", "api_key", "secret_key",
    "credential", "auth_key",
}

# IPv4 / IPv6 regex for basic format validation
_IP_RE = re.compile(
    r"^("
    r"(\d{1,3}\.){3}\d{1,3}"                        # IPv4
    r"|([0-9a-fA-F]{0,4}:){2,7}[0-9a-fA-F]{0,4}"     # IPv6 (abbreviated)
    r")$"
)


def _sanitize_body(body: Optional[dict]) -> Optional[dict]:
    """Remove sensitive fields from a request body dict before logging.

    Uses case-insensitive substring matching to catch variants like
    'password', 'my_password', 'PASSWORD', 'password_hash', etc.
    """
    if not body:
        return None
    sanitized = {}
    for k, v in body.items():
        key_lower = k.lower()
        if any(pat in key_lower for pat in _SENSITIVE_FIELD_PATTERNS):
            sanitized[k] = "[REDACTED]"
        elif isinstance(v, dict):
            sanitized[k] = _sanitize_body(v)
        else:
            sanitized[k] = v
    return sanitized


def audit_log(action: str, target_type: Optional[str] = None):
    """
    Decorator that writes an AuditLog entry after a successful handler execution.

    Args:
        action: dot-notation action name, e.g. "asset.create"
        target_type: override the target type derived from the action prefix
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract request/user/db from FastAPI kwargs
            request: Optional[Request] = kwargs.get("request")
            user: Optional[User] = kwargs.get("user")
            db: Optional[Session] = kwargs.get("db")

            # Also check positional args (self + request in methods)
            if not request:
                for v in args:
                    if isinstance(v, Request):
                        request = v
                        break

            result = await func(*args, **kwargs)

            # Only log successful write operations (2xx responses)
            if db and user and request:
                client_ip = request.headers.get("x-forwarded-for",
                                                 request.client.host if request.client else "unknown")
                if "," in client_ip:
                    client_ip = client_ip.split(",")[0].strip()
                # Validate IP format; discard malformed values
                if not _IP_RE.match(client_ip):
                    client_ip = None

                # Extract target_id from result (if response model has id)
                target_id: Optional[int] = None
                body: Optional[dict] = getattr(request.state, "_body_json", None)

                if isinstance(result, dict):
                    target_id = result.get("id")

                log_entry = AuditLog(
                    user_id=user.id,
                    action=action,
                    target_type=target_type or action.split(".")[0],
                    target_id=target_id,
                    detail={
                        "method": request.method,
                        "path": request.url.path,
                        "body": _sanitize_body(body),
                        "trace_id": get_trace_id(),
                    },
                    ip_address=client_ip,
                )
                db.add(log_entry)
                try:
                    db.commit()
                except Exception:
                    db.rollback()

            return result
        return wrapper
    return decorator


async def log_audit(
    db: Session,
    user: User,
    action: str,
    target_type: Optional[str],
    target_id: Optional[int],
    detail: Optional[dict],
    ip_address: str,
):
    """Programmatic audit log helper for inline use."""
    log_entry = AuditLog(
        user_id=user.id,
        action=action,
        target_type=target_type or action.split(".")[0],
        target_id=target_id,
        detail=detail,
        ip_address=ip_address,
    )
    db.add(log_entry)
    try:
        db.commit()
    except Exception:
        db.rollback()
