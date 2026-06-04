"""Anthropic Admin API — list orgs, projects, and per-project API keys.

Reference: https://docs.anthropic.com/en/api/administration-api
(adjust paths/fields if the real schema differs; this v1 ships with the
shape we observed in the Anthropic Admin console.)
"""
from __future__ import annotations

from typing import List

from backend.services.cloud_discovery.base import CloudDiscoveryBase
from backend.services.cloud_discovery import RawAgent


class AnthropicDiscovery(CloudDiscoveryBase):
    PROVIDER_NAME = "anthropic"
    BASE_URL = "https://api.anthropic.com"

    def _auth_headers(self) -> dict:
        return {
            "x-api-key": self._api_key,
            "anthropic-version": "2023-06-01",
        }

    def _list_agents(self) -> List[RawAgent]:
        out: List[RawAgent] = []
        for org in self._paginate("/v1/organizations"):
            projects_path = f"/v1/organizations/{org['id']}/projects"
            for project in self._paginate(projects_path):
                keys_path = f"/v1/organizations/{org['id']}/projects/{project['id']}/api_keys"
                for key in self._paginate(keys_path):
                    fp = self.fingerprint_key_id(key["id"])
                    out.append(RawAgent(
                        provider="anthropic",
                        project_label=project["name"],
                        agent_name=f"{self.connection.name} / {project['name']} / {key['name']}",
                        api_key_fingerprint=fp,
                        capabilities={
                            "filesystem": False, "network": True, "code_exec": False,
                            "tool_count": 0,
                        },
                        model=None,
                        owner_team=org["name"],
                    ))
        return out

    # ── Helpers ────────────────────────────────────────────────────────
    def _paginate(self, path: str) -> list:
        page = self._http_get(path, params={"limit": 100})
        items = list(page.get("data", []))
        # Pagination is a v2 enhancement; v1 stops at one page
        return items

    @staticmethod
    def fingerprint_key_id(key_id: str) -> str:
        # Use the existing fingerprint helper against the key ID (not the secret)
        from backend.services import crypto
        return crypto.fingerprint(key_id) or "0" * 16
