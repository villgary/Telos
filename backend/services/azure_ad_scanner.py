"""
Azure AD account scanner.
Uses msgraph SDK to enumerate users, groups, and directory roles.
"""

import logging
from datetime import datetime, timezone
from typing import Tuple, List, Optional, Dict, Any

from backend.services.ssh_scanner import AccountInfo, ConnectionResult

logger = logging.getLogger(__name__)

# Privileged Azure AD roles
PRIVILEGED_ROLES = {
    "Global Administrator",
    "Privileged Role Administrator",
    "Exchange Administrator",
    "SharePoint Administrator",
    "Security Administrator",
    "Helpdesk Administrator",
    "User Administrator",
}


def _is_privileged_role(role_name: str) -> bool:
    """Check if role is considered privileged."""
    return role_name in PRIVILEGED_ROLES


def scan_asset(
    ip: str,
    port: int,
    username: str,
    password: Optional[str] = None,
    *,
    tenant_id: Optional[str] = None,
    timeout: int = 30,
) -> Tuple[ConnectionResult, List[AccountInfo]]:
    """
    Scan Azure AD for account information.

    Args:
        ip: Tenant ID (can also be used as identifier)
        port: Port (not used for Azure, always 443)
        username: Azure Client ID (application ID)
        password: Azure Client Secret
        tenant_id: Azure Tenant ID (overwrites ip if provided)
        timeout: Connection timeout

    Returns:
        Tuple of (ConnectionResult, List[AccountInfo])
    """
    try:
        from azure.identity import ClientSecretCredential
        from msgraph import GraphServiceClient
    except ImportError:
        return (
            ConnectionResult(success=False, error="Azure SDKs not installed: pip install azure-identity msgraph", status="offline"),
            []
        )

    if not tenant_id:
        tenant_id = ip

    if not password:
        return (
            ConnectionResult(success=False, error="Client Secret required", status="auth_failed"),
            []
        )

    try:
        # Initialize credentials and client
        credential = ClientSecretCredential(
            tenant_id=tenant_id,
            client_id=username,
            client_secret=password,
        )
        client = GraphServiceClient(credential, timeout=timeout)

        accounts: List[AccountInfo] = []

        # Get all users
        users = client.users.get_all().top(100).select(["id", "userPrincipalName", "displayName", "accountEnabled", "userType", "createdDateTime", "lastSignInDateTime"]).get_all().result

        for user in users:
            try:
                if not user.account_enabled:
                    account_status = "disabled"
                elif user.user_type == "Member":
                    account_status = "active"
                else:
                    account_status = "guest"

                uid_sid = f"azure://{user.id}"

                # Get group memberships
                groups = []
                try:
                    member_of = client.users.by_user_id(user.id).member_of.get().value
                    for item in member_of:
                        if hasattr(item, "display_name"):
                            groups.append(item.display_name)
                except Exception as e:
                    logger.warning(f"Error getting group memberships for {user.user_principal_name}: {e}")

                # Get directory roles
                is_admin = False
                try:
                    role_assignments = client.users.by_user_id(user.id).member_of.get().value
                    for item in role_assignments:
                        # Azure AD directory roles have @odata.type like "#microsoft.graph.directoryRole"
                        if hasattr(item, "role_template_id"):
                            # This is a directory role assignment
                            is_admin = True
                            break
                except Exception:
                    pass

                # Build sudo_config equivalent
                sudo_config = {
                    "scanner": "azure_ad",
                    "tenant_id": tenant_id,
                    "object_id": user.id,
                    "user_type": user.user_type,
                    "groups": groups,
                    "is_admin": is_admin,
                }

                # Build raw_info
                raw_info = {
                    "scanner": "azure_ad",
                    "object_id": user.id,
                    "user_principal_name": user.user_principal_name,
                    "display_name": user.display_name,
                    "tenant_id": tenant_id,
                    "user_type": user.user_type,
                    "account_enabled": user.account_enabled,
                    "created_datetime": str(user.created_date_time) if user.created_date_time else None,
                    "last_signin_datetime": str(user.last_sign_in_date_time) if user.last_sign_in_date_time else None,
                    "groups": groups,
                }

                accounts.append(AccountInfo(
                    username=user.user_principal_name or user.display_name or user.id,
                    uid_sid=uid_sid,
                    is_admin=is_admin,
                    account_status=account_status,
                    home_dir="",
                    shell="",
                    groups=groups,
                    sudo_config=sudo_config,
                    last_login=user.last_sign_in_date_time,
                    raw_info=raw_info,
                ))

            except Exception as e:
                logger.warning(f"Error processing Azure AD user: {e}")
                continue

        return (ConnectionResult(success=True, status="online"), accounts)

    except Exception as e:
        error_msg = str(e).lower()
        if "authentication" in error_msg or "credential" in error_msg or "unauthorized" in error_msg:
            return (
                ConnectionResult(success=False, error=f"Azure AD authentication failed: {e}", status="auth_failed"),
                []
            )
        if "forbidden" in error_msg or "permission" in error_msg:
            return (
                ConnectionResult(success=False, error=f"Azure AD permission denied: {e}", status="auth_failed"),
                []
            )
        logger.error(f"Azure AD scan error: {e}")
        return (
            ConnectionResult(success=False, error=f"Cloud IAM scan failed: {e}", status="offline"),
            []
        )
