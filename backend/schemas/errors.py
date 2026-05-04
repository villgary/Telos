from pydantic import BaseModel
from typing import Optional


class ErrorResponse(BaseModel):
    """Standard error response with optional trace ID for debugging."""
    detail: str
    code: Optional[str] = None
    trace_id: Optional[str] = None


class ValidationErrorItem(BaseModel):
    """Single validation error item with location and message."""
    loc: tuple[str, ...]
    msg: str
    type: str


class ValidationErrorResponse(BaseModel):
    """Response for validation errors with a list of error items."""
    detail: list[ValidationErrorItem]
    code: str = "validation_error"
