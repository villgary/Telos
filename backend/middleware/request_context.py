"""
Request context middleware: injects trace_id into each request.
"""
import uuid
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from backend.logging_config import set_trace_id, new_trace_id


class TraceIdMiddleware(BaseHTTPMiddleware):
    """
    Generates a unique trace_id for every incoming HTTP request and:
      - sets it in a context variable (propagates through async tasks)
      - adds it to the response X-Trace-ID header
    """

    async def dispatch(self, request: Request, call_next):
        # Accept incoming trace ID from header (for distributed tracing), or generate new
        incoming = request.headers.get("x-trace-id", "")
        trace_id = incoming if len(incoming) == 16 else new_trace_id()

        set_trace_id(trace_id)

        response: Response = await call_next(request)
        response.headers["X-Trace-ID"] = trace_id
        return response
