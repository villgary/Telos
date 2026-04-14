"""
Alert SSE Manager — pushes real-time alerts to connected frontend clients.

Architecture:
  - AlertSSEManager is a process-wide singleton
  - Frontend connects via EventSource to GET /api/v1/alerts/stream
  - Any backend service calls alert_manager.broadcast(alert_dict) to push an alert
  - Heartbeat comments are sent every 25s to keep the connection alive
    (nginx default proxy_read_timeout is 60s, so 25s heartbeat is safe)

Usage in other services:
  from backend.services.alert_sse_manager import alert_manager
  alert_manager.broadcast(alert_response_dict)
"""

from __future__ import annotations
import asyncio
import json
import logging
from typing import AsyncGenerator

logger = logging.getLogger(__name__)


class AlertSSEManager:
    """
    Manages concurrent SSE client connections for real-time alert push.

    Thread-safety note: FastAPI runs on asyncio; this class is accessed
    only from the async event loop, so no explicit locking is needed.
    """

    def __init__(self):
        # Map of user_id → asyncio.Queue for that user's SSE stream
        self._queues: dict[int, asyncio.Queue] = {}

    def connect(self, user_id: int) -> asyncio.Queue:
        """Register a new SSE client for a user. Returns their event queue."""
        if user_id not in self._queues:
            self._queues[user_id] = asyncio.Queue(maxsize=50)
        else:
            # Drain stale events from a reconnecting client
            q = self._queues[user_id]
            while not q.empty():
                try:
                    q.get_nowait()
                except asyncio.QueueEmpty:
                    break
        logger.info(f"SSE client connected: user_id={user_id} (total={len(self._queues)})")
        return self._queues[user_id]

    def disconnect(self, user_id: int) -> None:
        """Remove a client on disconnect."""
        self._queues.pop(user_id, None)
        logger.info(f"SSE client disconnected: user_id={user_id} (remaining={len(self._queues)})")

    async def broadcast(self, alert: dict) -> int:
        """
        Push an alert dict to all connected clients.
        Returns the number of clients that received the alert.
        """
        if not self._queues:
            return 0

        event = f"data: {json.dumps(alert, default=str)}\n\n"
        count = 0
        for user_id, q in list(self._queues.items()):
            try:
                q.put_nowait(event)
                count += 1
            except asyncio.QueueFull:
                # Drop if client buffer is full (slow consumer)
                logger.warning(f"SSE queue full for user_id={user_id}, dropping alert {alert.get('id')}")
        return count

    async def stream(self, user_id: int) -> AsyncGenerator[str, None]:
        """
        Async generator — yields SSE-formatted events for a client.
        Keeps the connection alive with heartbeat comments.
        """
        q = self.connect(user_id)
        heartbeat_count = 0
        try:
            while True:
                try:
                    event = await asyncio.wait_for(q.get(), timeout=25)
                    yield event
                    heartbeat_count = 0
                except asyncio.TimeoutError:
                    # Heartbeat comment — keeps nginx proxy from timing out
                    yield ": heartbeat\n\n"
                    heartbeat_count += 1
                    # After 5 missed heartbeats (~125s), forcibly close to avoid leaks
                    if heartbeat_count > 5:
                        logger.warning(f"SSE heartbeat timeout for user_id={user_id}")
                        break
        except asyncio.CancelledError:
            pass
        finally:
            self.disconnect(user_id)


# ── Process-wide singleton ──────────────────────────────────────────────────────

alert_manager = AlertSSEManager()
