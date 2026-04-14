"""
Rate limiting configuration using slowapi.
Applied per IP address (from X-Forwarded-For if behind proxy).
"""
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import Request
from fastapi.responses import JSONResponse


def get_real_ip(request: Request) -> str:
    """Return the real client IP, checking X-Forwarded-For header first."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


# Shared limiter instance — use this in both main.py and endpoint decorators
limiter = Limiter(key_func=get_real_ip, default_limits=["100/minute"])


def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content={
            "detail": f"请求过于频繁，请稍后再试: {exc.detail}",
            "retry_after": getattr(exc, "retry_after", None),
        },
    )
