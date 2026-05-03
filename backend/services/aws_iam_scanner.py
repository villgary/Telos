"""
AWS IAM account scanner.
Uses boto3 to enumerate IAM users, groups, policies, access keys, and MFA status.
"""

import logging
from datetime import datetime, timezone
from typing import Tuple, List, Optional, Dict, Any

from backend.services.ssh_scanner import AccountInfo, ConnectionResult

logger = logging.getLogger(__name__)

# Admin AWS managed policies
ADMIN_POLICIES = {
    "arn:aws:iam::aws:policy/AdministratorAccess",
    "arn:aws:iam::aws:policy/PowerUserAccess",
}


def _parse_iam_arn(arn: str) -> Dict[str, str]:
    """Parse AWS ARN into components."""
    parts = arn.split(":")
    if len(parts) >= 6:
        return {
            "partition": parts[1],
            "service": parts[2],
            "region": parts[3],
            "account": parts[4],
            "resource": ":".join(parts[5:]),
        }
    return {}


def _is_admin_policy(policy_arn: str) -> bool:
    """Check if policy ARN represents admin access."""
    return policy_arn in ADMIN_POLICIES or "AdministratorAccess" in policy_arn


def _get_user_admin_status(iam_client, username: str) -> bool:
    """Check if user has admin access via group or direct policy."""
    try:
        # Check attached policies directly
        response = iam_client.list_attached_user_policies(UserName=username)
        for policy in response.get("AttachedPolicies", []):
            if _is_admin_policy(policy["PolicyArn"]):
                return True

        # Check groups
        response = iam_client.list_groups_for_user(UserName=username)
        for group in response.get("Groups", []):
            # Check group's attached policies
            group_response = iam_client.list_attached_group_policies(GroupName=group["GroupName"])
            for policy in group_response.get("AttachedPolicies", []):
                if _is_admin_policy(policy["PolicyArn"]):
                    return True

        return False
    except Exception as e:
        logger.warning(f"Error checking admin status for {username}: {e}")
        return False


def _get_access_key_age_days(access_key_date: datetime) -> int:
    """Calculate age of access key in days."""
    if access_key_date is None:
        return 0
    now = datetime.now(timezone.utc)
    if access_key_date.tzinfo is None:
        access_key_date = access_key_date.replace(tzinfo=timezone.utc)
    return (now - access_key_date).days


def scan_asset(
    ip: str,
    port: int,
    username: str,
    password: Optional[str] = None,
    *,
    region: str = "us-east-1",
    timeout: int = 30,
) -> Tuple[ConnectionResult, List[AccountInfo]]:
    """
    Scan AWS IAM for account information.

    Args:
        ip: AWS account ID or alias (used as identifier)
        port: Port (not used for AWS, always 443)
        username: AWS Access Key ID
        password: AWS Secret Access Key
        region: AWS region
        timeout: Connection timeout (used for API calls)

    Returns:
        Tuple of (ConnectionResult, List[AccountInfo])
    """
    import boto3
    from botocore.config import Config
    from botocore.exceptions import ClientException, NoCredentialsError, EndpointConnectionError

    if not password:
        return (
            ConnectionResult(success=False, error="Secret Access Key required", status="auth_failed"),
            []
        )

    try:
        config = Config(connect_timeout=timeout, read_timeout=timeout)
        session = boto3.Session(
            aws_access_key_id=username,
            aws_secret_access_key=password,
            region_name=region,
        )
        iam = session.client("iam", config=config)

        accounts: List[AccountInfo] = []

        # Get account ID from ARN
        account_id = ip if ip.isdigit() else None
        try:
            caller_identity = iam.get_caller_identity()
            account_id = caller_identity["Account"]
        except Exception:
            pass

        # List all users
        paginator = iam.get_paginator("list_users")
        for page in paginator.paginate():
            for user in page.get("Users", []):
                try:
                    username_str = user["UserName"]
                    user_arn = user["Arn"]
                    uid_sid = f"aws://{user_arn}"

                    # Check admin status
                    is_admin = _get_user_admin_status(iam, username_str)

                    # Get groups
                    groups = []
                    try:
                        group_response = iam.list_groups_for_user(UserName=username_str)
                        groups = [g["GroupName"] for g in group_response.get("Groups", [])]
                    except Exception:
                        pass

                    # Get login profile (console access)
                    has_console_access = False
                    try:
                        iam.get_login_profile(UserName=username_str)
                        has_console_access = True
                    except ClientException:
                        pass

                    # Get MFA devices
                    mfa_devices = []
                    try:
                        mfa_response = iam.list_mfa_devices(UserName=username_str)
                        mfa_devices = [d["SerialNumber"] for d in mfa_response.get("MFADevices", [])]
                    except Exception:
                        pass

                    # Get access keys and their age
                    access_keys = []
                    try:
                        keys_response = iam.list_access_keys(UserName=username_str)
                        for key in keys_response.get("AccessKeyMetadata", []):
                            access_keys.append({
                                "access_key_id": key["AccessKeyId"],
                                "status": key["Status"],
                                "create_date": key["CreateDate"],
                            })
                    except Exception:
                        pass

                    # Build sudo_config equivalent
                    sudo_config = {
                        "scanner": "aws_iam",
                        "account_id": account_id,
                        "region": region,
                        "groups": groups,
                        "has_console_access": has_console_access,
                        "mfa_devices": mfa_devices,
                        "access_keys": access_keys,
                    }

                    # Build raw_info
                    raw_info = {
                        "scanner": "aws_iam",
                        "user_arn": user_arn,
                        "user_id": user.get("UserId"),
                        "account_id": account_id,
                        "region": region,
                        "path": user.get("Path"),
                        "groups": groups,
                        "has_console_access": has_console_access,
                        "mfa_devices": mfa_devices,
                        "access_keys": access_keys,
                        "permissions_boundary": user.get("PermissionsBoundary", {}),
                        "tags": user.get("Tags", []),
                        "password_last_used": str(user.get("PasswordLastUsed", "")),
                        "create_date": str(user.get("CreateDate", "")),
                    }

                    # Determine account status
                    if user.get("PasswordLastUsed"):
                        account_status = "active"
                    elif has_console_access:
                        account_status = "enabled"
                    else:
                        account_status = "active"  # IAM users without console are service accounts

                    accounts.append(AccountInfo(
                        username=username_str,
                        uid_sid=uid_sid,
                        is_admin=is_admin,
                        account_status=account_status,
                        home_dir=f"s3://{account_id}/home/{username_str}",
                        shell="",
                        groups=groups,
                        sudo_config=sudo_config,
                        last_login=user.get("PasswordLastUsed"),
                        raw_info=raw_info,
                    ))

                except Exception as e:
                    logger.warning(f"Error processing IAM user: {e}")
                    continue

        return (ConnectionResult(success=True, status="online"), accounts)

    except NoCredentialsError:
        return (
            ConnectionResult(success=False, error="Invalid AWS credentials", status="auth_failed"),
            []
        )
    except EndpointConnectionError as e:
        return (
            ConnectionResult(success=False, error=f"AWS endpoint connection failed: {e}", status="offline"),
            []
        )
    except ClientException as e:
        error_code = e.response.get("Error", {}).get("Code", "")
        if error_code in ["InvalidClientTokenId", "SignatureDoesNotMatch"]:
            return (
                ConnectionResult(success=False, error="Invalid AWS credentials", status="auth_failed"),
                []
            )
        return (
            ConnectionResult(success=False, error=f"AWS API error: {e}", status="offline"),
            []
        )
    except Exception as e:
        logger.error(f"AWS IAM scan error: {e}")
        return (
            ConnectionResult(success=False, error=f"Cloud IAM scan failed: {e}", status="offline"),
            []
        )
