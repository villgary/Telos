"""AI Agent scanner — probe parser, dedupe, risk scoring, AIAgent upsert.

Public API:
    fingerprint_api_key(key)            -> sha256[:16] prefix or None
    parse_signals(raw_info)             -> list of candidate AIAgent dicts
    score_risk(agent_dict, all_agents)  -> (score, level, signals)
    ingest(db, raw_info, asset_id)      -> list[AIAgent] (created or updated)
"""
from __future__ import annotations

import hashlib
from typing import Optional


def fingerprint_api_key(key: Optional[str]) -> Optional[str]:
    """Return a 16-char sha256[:16] fingerprint prefixed with 'sha256:',
    or None for empty/None input. Never returns any portion of the key."""
    if not key:
        return None
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
    return f"sha256:{digest[:16]}"
