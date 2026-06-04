"""OpenAI Admin API — list projects and per-project API keys.

Reference: https://platform.openai.com/docs/api-reference/organization
(paths/fields may need adjustment when the live schema is confirmed).
"""
from __future__ import annotations

from typing import List

from backend.services.cloud_discovery.base import CloudDiscoveryBase
from backend.services.cloud_discovery import RawAgent
from backend.services import crypto


class OpenAIDiscovery(CloudDiscoveryBase):
    PROVIDER_NAME = "openai"
    BASE_URL = "https://api.openai.com"

    def _auth_headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._api_key}",
        }

    def _list_agents(self) -> List[RawAgent]:
        out: List[RawAgent] = []
        projects = self._http_get("/v1/organization/projects").get("data", [])
        for project in projects:
            keys_path = f"/v1/organization/projects/{project['id']}/api_keys"
            keys = self._http_get(keys_path).get("data", [])
            for key in keys:
                fp = crypto.fingerprint(key["id"]) or "0" * 16
                out.append(RawAgent(
                    provider="openai",
                    project_label=project["name"],
                    agent_name=f"{self.connection.name} / {project['name']} / {key['name']}",
                    api_key_fingerprint=fp,
                    capabilities={
                        "filesystem": False, "network": True, "code_exec": False,
                        "tool_count": 0,
                    },
                    model=None,
                    owner_team=None,  # OpenAI doesn't expose org name on this path
                ))
        return out
