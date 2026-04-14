"""
Structured logging configuration using structlog.
All logs are JSON-formatted with trace_id correlation support.
"""
import logging
import os
import sys
import uuid
import contextvars
from typing import Optional

import structlog

# ──────────────────────────────────────────
#  Trace ID context (propagates through async tasks)
# ──────────────────────────────────────────
_trace_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("trace_id", default="")


def get_trace_id() -> str:
    return _trace_id_var.get()


def set_trace_id(tid: str) -> None:
    _trace_id_var.set(tid)


def new_trace_id() -> str:
    return uuid.uuid4().hex[:16]


# ──────────────────────────────────────────
#  Configure structlog
# ──────────────────────────────────────────

def configure_logging():
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()

    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer(),
    ]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )

    # Set stdlib root logger level so backend.* loggers inherit it
    root_logger = logging.getLogger("backend")
    root_logger.setLevel(getattr(logging, log_level, logging.INFO))
    root_logger.handlers.clear()
    root_logger.addHandler(logging.StreamHandler(sys.stdout))

    return structlog.get_logger()


# ──────────────────────────────────────────
#  Module-level logger (imported by services)
# ──────────────────────────────────────────
configure_logging()
logger = structlog.get_logger("accountscan")
