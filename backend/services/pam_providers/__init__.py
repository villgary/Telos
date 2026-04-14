"""
PAM Provider base and registry.
"""

from abc import ABC, abstractmethod
from typing import Any


class PAMAccount:
    def __init__(
        self,
        account_name: str,
        account_type: str = "regular",
        pam_status: str = "unknown",
        last_used: Any = None,
    ):
        self.account_name = account_name
        self.account_type = account_type  # privileged / regular / service
        self.pam_status = pam_status       # active / disabled / pending
        self.last_used = last_used


class PAMProvider(ABC):
    name: str = "base"

    @abstractmethod
    def fetch_accounts(self, config: dict) -> list[PAMAccount]:
        """Fetch accounts from PAM system. Read-only."""
        raise NotImplementedError


class CustomAPIProvider(PAMProvider):
    """
    Generic OpenAPI provider — user configures URL + auth headers.
    Expected response format:
    {
      "accounts": [
        {"account_name": "admin", "account_type": "privileged", "status": "active", "last_used": "2026-01-15T10:00:00Z"}
      ]
    }
    """
    name = "custom_api"

    def fetch_accounts(self, config: dict) -> list[PAMAccount]:
        import requests
        import os
        from datetime import datetime

        url = config.get("api_url")
        if not url:
            raise ValueError("custom_api: api_url is required in config")

        headers = {}
        api_key = config.get("api_key")
        if api_key:
            auth_type = config.get("auth_type", "bearer")
            if auth_type == "bearer":
                headers["Authorization"] = f"Bearer {api_key}"
            elif auth_type == "api_key":
                key_name = config.get("api_key_name", "X-API-Key")
                headers[key_name] = api_key
            elif auth_type == "basic":
                import base64
                credentials = base64.b64encode(api_key.encode()).decode()
                headers["Authorization"] = f"Basic {credentials}"

        timeout = config.get("timeout", 30)
        resp = requests.get(url, headers=headers, timeout=timeout, proxies={
            "http": os.getenv("HTTP_PROXY"),
            "https": os.getenv("HTTPS_PROXY"),
        })
        resp.raise_for_status()
        data = resp.json()

        accounts = []
        account_list = data if isinstance(data, list) else data.get("accounts", [])
        for item in account_list:
            last_used = None
            lu = item.get("last_used") or item.get("lastUsed") or item.get("last_login")
            if lu:
                try:
                    last_used = datetime.fromisoformat(lu.replace("Z", "+00:00"))
                except Exception:
                    pass

            accounts.append(PAMAccount(
                account_name=str(item.get("account_name", item.get("name", "?"))),
                account_type=str(item.get("account_type", item.get("type", "regular"))),
                pam_status=str(item.get("pam_status", item.get("status", "unknown"))),
                last_used=last_used,
            ))
        return accounts


PROVIDERS: dict[str, type[PAMProvider]] = {
    "custom_api": CustomAPIProvider,
}


def get_provider(provider: str) -> PAMProvider:
    cls = PROVIDERS.get(provider)
    if not cls:
        raise ValueError(f"Unknown or unimplemented PAM provider: {provider}")
    return cls()
