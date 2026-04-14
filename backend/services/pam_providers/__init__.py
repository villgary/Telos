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


class TencentCloudBastionProvider(PAMProvider):
    """
    Tencent Cloud bastion host integration via CAM API.
    Requires: secret_id, secret_key, region, instance_id in config.
    """
    name = "tencent_cloud_bastion"

    def fetch_accounts(self, config: dict) -> list[PAMAccount]:
        import requests, hashlib, hmac, json, time
        from datetime import datetime

        secret_id = config.get("secret_id")
        secret_key = config.get("secret_key")
        region = config.get("region", "ap-shanghai")
        instance_id = config.get("instance_id")

        if not all([secret_id, secret_key]):
            raise ValueError("tencent_cloud_bastion: secret_id and secret_key required")

        service = "bastion"
        host = f"bastion.{region}.tencentcloudapi.com"
        endpoint = f"https://{host}"

        # Build Tencent Cloud API request (simplified)
        timestamp = str(int(time.time()))
        params = {"InstanceId": instance_id} if instance_id else {}

        def _sign(secret, date, service, payload):
            # Simplified — uses TC3-HMAC-SHA256
            return "placeholder_signature"

        headers = {
            "Content-Type": "application/json",
            "Host": host,
            "X-Api-Key": secret_id,
            "X-Api-Timestamp": timestamp,
        }
        payload = json.dumps(params)

        # Return placeholder — real implementation would call TencentCloudAPI
        return []


class AliyunBastionProvider(PAMProvider):
    """
    Alibaba Cloud bastion host (堡垒机) via RAM API.
    Requires: access_key_id, access_key_secret, region in config.
    """
    name = "aliyun_bastion"

    def fetch_accounts(self, config: dict) -> list[PAMAccount]:
        # Placeholder — real implementation calls Aliyun RAM API
        return []


class CyberArkProvider(PAMProvider):
    """
    CyberArk PVWA API integration.
    Requires: pvwa_url, auth_token in config.
    """
    name = "cyberark"

    def fetch_accounts(self, config: dict) -> list[PAMAccount]:
        # Placeholder — real implementation calls CyberArk PVWA API
        return []


PROVIDERS: dict[str, type[PAMProvider]] = {
    "custom_api": CustomAPIProvider,
    "tencent_cloud_bastion": TencentCloudBastionProvider,
    "aliyun_bastion": AliyunBastionProvider,
    "cyberark": CyberArkProvider,
}


def get_provider(provider: str) -> PAMProvider:
    cls = PROVIDERS.get(provider)
    if not cls:
        raise ValueError(f"Unknown PAM provider: {provider}")
    return cls()
