"""Shared base class for cloud provider discovery modules."""
from __future__ import annotations

import logging
import time
from typing import Callable, List, TypeVar

import httpx

from backend.services import crypto
from backend.services.cloud_discovery import RawAgent


logger = logging.getLogger(__name__)


class RetryableError(Exception):
    """Transient provider failure — retry with backoff."""


class FatalDiscoveryError(Exception):
    """Provider rejected the request definitively (401, 403). Do not retry."""


T = TypeVar("T")


def _retry_with_backoff(fn: Callable[[], T], max_attempts: int = 3) -> T:
    """Run fn() with exponential backoff (1s, 2s, 4s) on RetryableError.

    Re-raises the last RetryableError if all attempts fail. FatalDiscoveryError
    propagates immediately.
    """
    delay = 1.0
    last_exc: Exception | None = None
    for attempt in range(max_attempts):
        try:
            return fn()
        except FatalDiscoveryError:
            raise
        except RetryableError as e:
            last_exc = e
            if attempt == max_attempts - 1:
                break
            time.sleep(delay)
            delay *= 2
    assert last_exc is not None
    raise last_exc


class CloudDiscoveryBase:
    """Subclassed by AnthropicDiscovery and OpenAIDiscovery.

    Subclasses implement _http_get(path) -> dict and _list_subresources()
    to produce RawAgent rows.
    """

    PROVIDER_NAME: str = ""  # set by subclass
    BASE_URL: str = ""

    def __init__(self, connection):
        self.connection = connection
        self._api_key = crypto.decrypt(connection.encrypted_api_key)

    # ── Public entry point ─────────────────────────────────────────────
    def run(self) -> List[RawAgent]:
        try:
            return self._list_agents()
        except FatalDiscoveryError as e:
            logger.warning("Cloud discovery fatal: provider=%s err=%s",
                           self.PROVIDER_NAME, e)
            raise
        except RetryableError as e:
            logger.warning("Cloud discovery gave up: provider=%s err=%s",
                           self.PROVIDER_NAME, e)
            raise

    # ── HTTP helper ────────────────────────────────────────────────────
    def _http_get(self, path: str, params: dict | None = None) -> dict:
        url = f"{self.BASE_URL}{path}"
        headers = self._auth_headers()

        def _do():
            try:
                resp = httpx.get(url, headers=headers, params=params, timeout=10.0)
            except httpx.TimeoutException as e:
                raise RetryableError(f"timeout: {e}") from e
            except httpx.HTTPError as e:
                raise RetryableError(f"network: {e}") from e

            if resp.status_code in (401, 403):
                raise FatalDiscoveryError(f"auth_failed: {resp.status_code}")
            if resp.status_code == 429:
                raise RetryableError("rate_limited")
            if 500 <= resp.status_code < 600:
                raise RetryableError(f"server_error: {resp.status_code}")
            if resp.status_code >= 400:
                raise FatalDiscoveryError(f"http_error: {resp.status_code}")
            return resp.json()

        return _retry_with_backoff(_do, max_attempts=3)

    # ── Hooks for subclasses ────────────────────────────────────────────
    def _auth_headers(self) -> dict:
        """Override in subclass. Must never log the key value."""
        raise NotImplementedError

    def _list_agents(self) -> List[RawAgent]:
        """Override in subclass. Should call self._http_get() and assemble RawAgent rows."""
        raise NotImplementedError
