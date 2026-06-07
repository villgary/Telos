"""Sync orchestration: run a single discovery pass against a CloudConnection.

The router's POST /sync endpoint and the 6h scheduler both call
run_connection_sync. The function:
  - updates connection.last_sync_started_at and last_sync_status in place
  - catches FatalDiscoveryError / RetryableError / generic Exception from
    the provider call and returns a structured result
  - on success, ingests RawAgents and returns discovered/updated counts
  - does NOT commit — the caller is responsible for commit/rollback
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING

from backend import models
from backend.services.ai_agent_scanner import ingest_cloud_agents
from backend.services.cloud_discovery import discover as cloud_discover
from backend.services.cloud_discovery.base import (
    FatalDiscoveryError, RetryableError,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


logger = logging.getLogger(__name__)


def run_connection_sync(db: "Session", connection: models.CloudConnection) -> dict:
    """Run a single sync for one connection. Returns a result dict.

    Mutates connection.last_sync_started_at/_status/_at/_error in place.
    Does NOT commit. Caller is responsible for commit/rollback and for
    any audit-log writes (the scheduler and router have different
    audit-log needs and neither wants the other to write for it).
    """
    connection.last_sync_status = "running"
    db.flush()

    try:
        raws = cloud_discover(connection)
    except FatalDiscoveryError as e:
        return _failed(connection, f"auth_failed: {e}")
    except RetryableError as e:
        return _failed(connection, f"rate_limited_or_transient: {e}")
    except Exception as e:
        logger.exception("Cloud discovery unexpected error")
        return _failed(connection, f"unexpected: {e!r}")

    pre_existing_ids = {
        row[0] for row in db.query(models.AIAgent.id)
        .filter(models.AIAgent.connection_id == connection.id).all()
    }
    ingested = ingest_cloud_agents(db, connection, raws)
    agents_discovered = sum(1 for a in ingested if a.id not in pre_existing_ids)
    agents_updated = sum(1 for a in ingested if a.id in pre_existing_ids)

    connection.last_sync_at = datetime.utcnow()
    connection.last_sync_status = "success"
    connection.last_sync_error = None
    return {
        "status": "success",
        "agents_discovered": agents_discovered,
        "agents_updated": agents_updated,
        "error": None,
    }


def _failed(connection, error_msg: str) -> dict:
    connection.last_sync_at = datetime.utcnow()
    connection.last_sync_status = "failed"
    connection.last_sync_error = error_msg[:256]
    return {
        "status": "failed",
        "agents_discovered": 0,
        "agents_updated": 0,
        "error": error_msg[:256],
    }
