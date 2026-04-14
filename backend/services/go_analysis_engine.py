"""
go_analysis_engine — Python wrapper for the Go analysis engine microservice.

When USE_GO_ANALYSIS_ENGINE=1, this module calls the Go engine via HTTP
instead of running the pure-Python analysis engines.

Go engine must be running on GO_ANALYSIS_ENGINE_URL (default: http://localhost:8082).

Usage:
    from backend.services.go_analysis_engine import run_full_analysis_go
    result = run_full_analysis_go(scope="global", scope_id=None, lang="zh")
"""

from __future__ import annotations

import os
import time

import requests

ANALYSIS_ENGINE_URL = os.environ.get("GO_ANALYSIS_ENGINE_URL", "http://localhost:8082")
ANALYSIS_ENGINE_TIMEOUT = int(os.environ.get("GO_ANALYSIS_ENGINE_TIMEOUT", "300"))


def run_full_analysis_go(
    scope: str = "global",
    scope_id: int | None = None,
    lang: str = "zh",
) -> dict:
    """
    Call the Go engine's /api/v1/analyze endpoint and return the raw result dict.

    Returns:
        dict with keys:
            layer_scores     — dict with semiotic/causal/ontological/cognitive/
                               anthropological/overall scores and overall_level
            semiotic_signals
            causal_signals
            ontological_signals
            cognitive_signals
            anthropological_signals
            threat_graph     — raw graph dict from Go (can be None on error)

    Raises:
        requests.HTTPError if the Go engine returns a non-2xx response.
    """
    url = f"{ANALYSIS_ENGINE_URL}/api/v1/analyze"
    payload = {"scope": scope, "lang": lang}
    if scope_id is not None:
        payload["scope_id"] = scope_id

    resp = requests.post(url, json=payload, timeout=ANALYSIS_ENGINE_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def run_diff_go(base_job_id: int, compare_job_id: int) -> dict:
    """
    Call the Go engine's /api/v1/diff endpoint.

    Returns:
        dict with keys: items[], summary{}
    """
    url = f"{ANALYSIS_ENGINE_URL}/api/v1/diff"
    payload = {"base_job_id": base_job_id, "compare_job_id": compare_job_id}
    resp = requests.post(url, json=payload, timeout=ANALYSIS_ENGINE_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def run_risk_propagate_go(job_id: int) -> dict:
    """
    Call the Go engine's /api/v1/risk-propagate endpoint.

    Returns:
        dict with keys: computed int, profiles_updated int
    """
    url = f"{ANALYSIS_ENGINE_URL}/api/v1/risk-propagate"
    payload = {"job_id": job_id}
    resp = requests.post(url, json=payload, timeout=ANALYSIS_ENGINE_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def run_account_scores_go(job_id: int) -> dict:
    """
    Call the Go engine's /api/v1/account-scores endpoint.

    Returns:
        dict with keys: count int, scores[]

    Raises:
        requests.HTTPError if the engine returns a non-2xx response.
    """
    url = f"{ANALYSIS_ENGINE_URL}/api/v1/account-scores"
    payload = {"job_id": job_id}
    resp = requests.post(url, json=payload, timeout=ANALYSIS_ENGINE_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def is_go_engine_available() -> bool:
    """Check if the Go engine is reachable."""
    try:
        resp = requests.get(
            f"{ANALYSIS_ENGINE_URL}/health",
            timeout=5,
        )
        return resp.status_code == 200
    except requests.RequestException:
        return False
