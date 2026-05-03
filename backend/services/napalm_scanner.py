"""
NAPALM-based network device account scanner.
Uses NAPALM's structured get_users() API for vendor-neutral account enumeration.
"""

import logging
from typing import Tuple, List, Optional, Dict, Any

from backend.services.ssh_scanner import AccountInfo, ConnectionResult

logger = logging.getLogger(__name__)

# NAPALM driver mapping
NAPALM_DRIVERS = {
    "cisco_ios": "cisco_ios",
    "cisco_nxos": "cisco_nxos",
    "arista_eos": "arista_eos",
    "huawei_vrp": "huawei_vrp",
    "hp_procurve": "hp_procurve",
    "juniper_junos": "juniper_junos",
    "generic": "cisco_ios",  # Fallback to Cisco-style
}

# Admin privilege thresholds by vendor family
PRIVILEGE_THRESHOLDS = {
    "cisco_ios": 15,
    "cisco_nxos": 15,
    "arista_eos": 15,
    "huawei_vrp": 3,
    "hp_procurve": 3,
    "juniper_junos": 10,
    "generic": 15,
}


def _get_driver(vendor: str):
    """Get NAPALM driver class for vendor."""
    try:
        from napalm import get_network_driver
        driver_name = NAPALM_DRIVERS.get(vendor, "cisco_ios")
        return get_network_driver(driver_name)
    except ImportError:
        return None


def _map_vendor_to_napalm(vendor: str) -> str:
    """Map network vendor slug to NAPALM driver name."""
    mapping = {
        "cisco": "cisco_ios",
        "cisco_nxos": "cisco_nxos",
        "arista": "arista_eos",
        "huawei": "huawei_vrp",
        "hp": "hp_procurve",
        "juniper": "juniper_junos",
        "generic": "cisco_ios",
    }
    return mapping.get(vendor, "cisco_ios")


def scan_asset(
    ip: str,
    port: int,
    username: str,
    password: Optional[str] = None,
    private_key: Optional[str] = None,
    passphrase: Optional[str] = None,
    *,
    vendor: str = "generic",
    timeout: int = 30,
    optional_args: Optional[Dict[str, Any]] = None,
) -> Tuple[ConnectionResult, List[AccountInfo]]:
    """
    Scan a network device for accounts using NAPALM.

    Args:
        ip: Device IP address
        port: SSH port (default 22)
        username: SSH username
        password: SSH password
        private_key: SSH private key content
        passphrase: Private key passphrase
        vendor: Vendor type (cisco, huawei, hp, juniper, arista, generic)
        timeout: Connection timeout in seconds
        optional_args: Extra args for NAPALM (e.g., 'secret' for enable password)

    Returns:
        Tuple of (ConnectionResult, List[AccountInfo])
    """
    try:
        from napalm import get_network_driver
        from napalm.base.exceptions import (
            ConnectionException,
            AuthenticationException,
            MergeException,
            CommandErrorException,
        )
    except ImportError:
        return (
            ConnectionResult(
                success=False,
                error="NAPALM 未安装: pip install napalm",
                status="offline"
            ),
            []
        )

    # Get driver
    napalm_vendor = _map_vendor_to_napalm(vendor)
    priv_threshold = PRIVILEGE_THRESHOLDS.get(napalm_vendor, 15)

    try:
        driver = get_network_driver(napalm_vendor)
    except Exception as e:
        logger.warning(f"NAPALM driver error for {napalm_vendor}: {e}")
        return (
            ConnectionResult(
                success=False,
                error=f"不支持的设备类型: {vendor}",
                status="offline"
            ),
            []
        )

    # Build connection arguments
    napalm_args = {
        "hostname": ip,
        "username": username,
        "password": password or "",
        "timeout": timeout,
    }

    # Add port if non-standard
    if port and port != 22:
        napalm_args["port"] = port

    # Handle private key
    if private_key:
        try:
            from io import StringIO
            import paramiko

            if passphrase:
                key = paramiko.RSAKey.from_private_key(
                    StringIO(private_key),
                    password=passphrase,
                )
            else:
                key = paramiko.RSAKey.from_private_key(StringIO(private_key))

            # Write key to temp file for NAPALM (NAPALM expects file path)
            import tempfile
            import os

            with tempfile.NamedTemporaryFile(mode='w', suffix='.pem', delete=False) as f:
                f.write(private_key)
                key_file = f.name

            napalm_args["key_file"] = key_file
        except Exception as e:
            logger.warning(f"Failed to parse private key: {e}")
            # Fall back to password auth
            pass

    # Handle enable/secret password (optional_args)
    if optional_args and "secret" in optional_args:
        napalm_args["optional_args"] = {"secret": optional_args["secret"]}

    try:
        # Connect
        device = driver(**napalm_args)
        device.open()

    except AuthenticationException as e:
        logger.warning(f"NAPALM auth failed {ip}:{port} — {e}")
        return (
            ConnectionResult(
                success=False,
                error=f"认证失败: {e}",
                status="auth_failed"
            ),
            []
        )

    except ConnectionException as e:
        logger.warning(f"NAPALM connect failed {ip}:{port} — {e}")
        return (
            ConnectionResult(
                success=False,
                error=f"连接失败: {e}",
                status="offline"
            ),
            []
        )

    except Exception as e:
        logger.warning(f"NAPALM connection error {ip}:{port} — {e}")
        return (
            ConnectionResult(
                success=False,
                error=f"连接失败: {e}",
                status="offline"
            ),
            []
        )

    try:
        # Get users using NAPALM's structured API
        users_data = device.get_users()

        accounts: List[AccountInfo] = []

        for username_str, user_info in users_data.items():
            try:
                level = user_info.get("level", 0)
                role = user_info.get("role", "")
                authorized_from = user_info.get("authorized_from", "")
                authorized_to = user_info.get("authorized_to", "")

                # Determine admin status
                is_admin = level >= priv_threshold

                # Build groups list
                groups = [f"privilege_{level}"]
                if role:
                    groups.append(f"role_{role}")

                # uid_sid format
                uid_sid = f"napalm://{vendor}:{username_str}"

                # Build sudo_config equivalent
                sudo_config = {
                    "scanner": "napalm",
                    "vendor": vendor,
                    "napalm_vendor": napalm_vendor,
                    "privilege_level": level,
                    "role": role,
                    "is_admin": is_admin,
                }

                # Build raw_info
                raw_info = {
                    "scanner": "napalm",
                    "vendor": vendor,
                    "napalm_vendor": napalm_vendor,
                    "level": level,
                    "role": role,
                    "authorized_from": authorized_from,
                    "authorized_to": authorized_to,
                }

                accounts.append(AccountInfo(
                    username=username_str,
                    uid_sid=uid_sid,
                    is_admin=is_admin,
                    account_status="enabled",  # NAPALM doesn't expose disabled status
                    home_dir="",
                    shell="",
                    groups=groups,
                    sudo_config=sudo_config,
                    last_login=None,
                    raw_info=raw_info,
                ))

            except Exception as e:
                logger.warning(f"Error parsing user {username_str}: {e}")
                continue

        return (ConnectionResult(success=True, status="online"), accounts)

    except CommandErrorException as e:
        logger.warning(f"NAPALM command error {ip}:{port} — {e}")
        return (
            ConnectionResult(
                success=False,
                error=f"命令执行失败: {e}",
                status="offline"
            ),
            []
        )

    except Exception as e:
        logger.error(f"NAPALM scan error {ip}:{port} — {e}")
        return (
            ConnectionResult(
                success=False,
                error=f"扫描失败: {e}",
                status="offline"
            ),
            []
        )

    finally:
        try:
            device.close()
        except Exception:
            pass


def detect_device_type(ip: str, port: int, username: str, password: str, timeout: int = 30) -> str:
    """
    Auto-detect network device type using NAPALM's probing.

    Returns NAPALM driver name (e.g., 'cisco_ios', 'huawei_vrp').
    """
    try:
        from napalm import get_network_driver
    except ImportError:
        return "generic"

    # Try common drivers in order
    drivers_to_try = [
        "cisco_ios",
        "huawei_vrp",
        "arista_eos",
        "hp_procurve",
        "juniper_junos",
    ]

    for driver_name in drivers_to_try:
        try:
            driver = get_network_driver(driver_name)
            device = driver(
                hostname=ip,
                username=username,
                password=password,
                timeout=timeout,
                port=port or 22,
            )
            device.open()
            device.close()
            return driver_name
        except Exception:
            continue

    return "generic"
