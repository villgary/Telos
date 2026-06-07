"""Cloud provider admin API discovery — per-provider modules peer to ssh_scanner.

Public API:
    RawAgent             — normalized per-agent dict produced by a provider module
    discover(connection) — dispatcher; returns List[RawAgent]
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from backend import models


@dataclass
class RawAgent:
    """One AI Agent as seen by a provider's admin API.

    Provider modules produce these. The ingest step in
    ai_agent_scanner.ingest_cloud_agents() turns them into AIAgent rows.
    """
    provider: str                              # "anthropic" | "openai"
    project_label: str                         # human-readable project / org name
    agent_name: str                            # fully-qualified synthetic name
    api_key_fingerprint: str                   # 16-char hex (sha256[:16])
    capabilities: Dict[str, Any] = field(default_factory=lambda: {
        "filesystem": False, "network": False, "code_exec": False, "tool_count": 0,
    })
    model: Optional[str] = None
    owner_team: Optional[str] = None


def discover(connection: "models.CloudConnection") -> List[RawAgent]:
    """Dispatch to the per-provider module based on `connection.provider`."""
    from backend.services.cloud_discovery.anthropic import AnthropicDiscovery
    from backend.services.cloud_discovery.openai import OpenAIDiscovery

    providers = {
        "anthropic": AnthropicDiscovery,
        "openai": OpenAIDiscovery,
    }
    impl = providers.get(connection.provider)
    if impl is None:
        raise ValueError(f"Unsupported cloud provider: {connection.provider}")
    return impl(connection).run()


__all__ = ["RawAgent", "discover"]
