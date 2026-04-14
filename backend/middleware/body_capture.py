"""
Body capture middleware: reads the request body on the way in and caches
the parsed JSON in request.state._body_json so the @audit_log decorator
can include it in audit records.

Starlette caches the raw body in request._body after the first read,
so endpoints that need the body (e.g. via Pydantic models) still work.
"""

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware


class BodyCaptureMiddleware(BaseHTTPMiddleware):
    """
    Intercepts every request, reads and buffers the body, then makes the
    parsed JSON dict available on request.state._body_json.

    Skipped for requests that never carry a body (GET / DELETE / OPTIONS).
    """

    # HTTP methods that should never have a body worth capturing
    _NO_BODY_METHODS = frozenset({"GET", "HEAD", "OPTIONS", "DELETE"})

    async def dispatch(self, request: Request, call_next):
        if request.method in self._NO_BODY_METHODS:
            request.state._body_json = None  # type: ignore[attr-defined]
            return await call_next(request)

        try:
            body_bytes = await request.body()
        except Exception:
            # Could not read body (e.g. streaming/chunked) — degrade gracefully
            request.state._body_json = None  # type: ignore[attr-defined]
            return await call_next(request)

        # Cache raw bytes so downstream handlers (Pydantic body models, etc.)
        # can still read them via request.body() or request._body.
        request._body = body_bytes  # type: ignore[attr-defined]

        if not body_bytes:
            request.state._body_json = None  # type: ignore[attr-defined]
            return await call_next(request)

        # Try to parse as JSON; silently fall back to None for non-JSON bodies
        # (e.g. multipart/form-data, text/plain).
        try:
            request.state._body_json = None if request.method == "GET" else \
                self._parse_json(body_bytes)  # type: ignore[attr-defined]
        except Exception:
            request.state._body_json = None  # type: ignore[attr-defined]

        return await call_next(request)

    @staticmethod
    def _parse_json(body_bytes: bytes):
        import json
        return json.loads(body_bytes.decode("utf-8"))
