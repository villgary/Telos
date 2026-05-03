"""
LDAP/Active Directory account scanner service.
Supports Active Directory and OpenLDAP for user and group enumeration.
Returns a unified AccountInfo list for consistent diff/alert processing.
"""

import logging
import re
from datetime import datetime, timezone
from typing import List, Optional, Tuple, Dict, Any, Set

from backend.services.ssh_scanner import AccountInfo, ConnectionResult

logger = logging.getLogger(__name__)

# Admin group patterns to detect privileged accounts
ADMIN_GROUP_PATTERNS = [
    r"Domain Admins",
    r"Enterprise Admins",
    r"Schema Admins",
    r"Administrators",
    r"Domain Controllers",
    r"Group Policy Creator Owners",
    r"Read-Only Domain Controllers",
    r"Account Operators",
    r"Backup Operators",
    r"Server Operators",
    r"Cryptographic Operators",
]


def _is_admin_group(group_dn: str) -> bool:
    """Check if a group DN represents an admin group."""
    group_dn_lower = group_dn.lower()
    for pattern in ADMIN_GROUP_PATTERNS:
        if re.search(pattern, group_dn, re.IGNORECASE):
            return True
    return False


def _parse_ad_timestamp(timestamp: Optional[int]) -> Optional[datetime]:
    """Parse Active Directory timestamp (100-nanosecond intervals since 1601)."""
    if not timestamp or timestamp == 0:
        return None
    try:
        # AD timestamps are in 100-nanosecond intervals since Jan 1, 1601
        seconds = timestamp / 10_000_000
        return datetime(1601, 1, 1, tzinfo=timezone.utc).replace(
            year=datetime(1601, 1, 1).year + int(seconds // 31536000)
        ) + timedelta(days=int(seconds % 31536000) // 86400)
    except Exception:
        return None


def _parse_ad_account_control(control: int) -> str:
    """Parse AD userAccountControl flags to determine if account is enabled."""
    # Bit 1 (0x2) = UF_ACCOUNTDISABLE
    if control & 0x2:
        return "disabled"
    return "enabled"


def _scan_active_directory(
    ip: str,
    port: int,
    username: str,
    password: str,
    base_dn: Optional[str],
    use_ssl: bool,
    timeout: int,
) -> Tuple[ConnectionResult, List[AccountInfo]]:
    """
    Scan Active Directory for user accounts using ldap3.
    """
    try:
        from ldap3 import Server, Connection, ALL, SUBTREE, SAFE_SYNC
        from ldap3.core.exceptions import LDAPBindError, LDAPSocketOpenError
    except ImportError:
        return (
            ConnectionResult(
                success=False,
                error="ldap3 未安装: pip install ldap3",
                status="offline"
            ),
            []
        )

    # Determine SSL setting
    use_ssl = use_ssl or port == 636

    # Default ports
    if port == 0:
        port = 636 if use_ssl else 389

    # Server URL
    server_url = f"ldaps://{ip}:{port}" if use_ssl else f"ldap://{ip}:{port}"

    try:
        server = Server(server_url, get_info=ALL, connect_timeout=timeout)

        # Connection with sync mode
        conn = Connection(
            server,
            user=username,
            password=password,
            auto_bind=True,
            authentication="SIMPLE" if not use_ssl else "SIMPLE",
            ssl=use_ssl,
            raise_exceptions=True,
        )

    except LDAPBindError as e:
        if "data 52e" in str(e).lower() or "data 775" in str(e).lower():
            return (
                ConnectionResult(
                    success=False,
                    error=f"认证失败: {e}",
                    status="auth_failed"
                ),
                []
            )
        return (
            ConnectionResult(
                success=False,
                error=f"认证失败: {e}",
                status="auth_failed"
            ),
            []
        )
    except LDAPSocketOpenError as e:
        return (
            ConnectionResult(
                success=False,
                error=f"连接失败: {e}",
                status="offline"
            ),
            []
        )
    except Exception as e:
        return (
            ConnectionResult(
                success=False,
                error=f"连接失败: {e}",
                status="offline"
            ),
            []
        )

    try:
        # If no base_dn provided, get it from server info
        if not base_dn:
            if hasattr(server, 'info') and server.info:
                try:
                    base_dn = str(server.info.naming_contexts[0])
                except Exception:
                    base_dn = "DC=domain,DC=local"
            else:
                base_dn = "DC=domain,DC=local"

        # First, get all admin groups for membership checking
        admin_group_dns: Set[str] = set()

        try:
            conn.search(
                search_base=base_dn,
                search_filter="(objectClass=group)",
                search_scope=SUBTREE,
                attributes=["distinguishedName", "cn"],
            )
            for entry in conn.entries:
                dn = str(entry.distinguishedName)
                cn = str(entry.cn) if hasattr(entry, 'cn') else ""
                if _is_admin_group(cn) or _is_admin_group(dn):
                    admin_group_dns.add(dn.lower())
        except Exception as e:
            logger.warning(f"Failed to fetch admin groups: {e}")

        # Search for all users
        conn.search(
            search_base=base_dn,
            search_filter="(&(objectClass=user)(objectCategory=person))",
            search_scope=SUBTREE,
            attributes=[
                "sAMAccountName",
                "distinguishedName",
                "userAccountControl",
                "memberOf",
                "lastLogonTimestamp",
                "pwdLastSet",
                "whenCreated",
                "whenChanged",
                "displayName",
                "mail",
                "userPrincipalName",
                "description",
                "title",
                "department",
                "company",
            ],
        )

        accounts: List[AccountInfo] = []

        for entry in conn.entries:
            try:
                username_attr = str(entry.sAMAccountName) if hasattr(entry, 'sAMAccountName') else None
                if not username_attr:
                    continue

                dn = str(entry.distinguishedName) if hasattr(entry, 'distinguishedName') else ""
                uid_sid = f"ldap://{dn}"

                # Parse account control for enabled/disabled status
                uac = int(entry.userAccountControl) if hasattr(entry, 'userAccountControl') else 0
                account_status = _parse_ad_account_control(uac)

                # Check if admin via memberOf
                member_of = []
                is_admin = False
                if hasattr(entry, 'memberOf') and entry.memberOf:
                    for group_dn in entry.memberOf:
                        group_dn_str = str(group_dn)
                        member_of.append(group_dn_str)
                        if group_dn_str.lower() in admin_group_dns:
                            is_admin = True
                        if _is_admin_group(group_dn_str):
                            is_admin = True

                # Parse last logon (AD timestamp)
                last_login = None
                if hasattr(entry, 'lastLogonTimestamp') and entry.lastLogonTimestamp:
                    try:
                        ll = int(entry.lastLogonTimestamp)
                        if ll > 0:
                            # Convert AD timestamp to datetime
                            # AD timestamps are 100-nanosecond intervals since Jan 1, 1601
                            last_login = datetime(1601, 1, 1, tzinfo=timezone.utc)
                            seconds = ll / 10_000_000
                            last_login = last_login.replace(
                                year=last_login.year + int(seconds // 31536000)
                            )
                            from datetime import timedelta
                            last_login = last_login + timedelta(seconds=seconds % 31536000)
                    except Exception:
                        last_login = None

                # Parse pwdLastSet
                pwd_last_set = None
                if hasattr(entry, 'pwdLastSet') and entry.pwdLastSet:
                    try:
                        pls = int(entry.pwdLastSet)
                        if pls > 0:
                            from datetime import timedelta
                            pwd_last_set = datetime(1601, 1, 1, tzinfo=timezone.utc)
                            seconds = pls / 10_000_000
                            pwd_last_set = pwd_last_set.replace(
                                year=pwd_last_set.year + int(seconds // 31536000)
                            )
                            pwd_last_set = pwd_last_set + timedelta(seconds=seconds % 31536000)
                    except Exception:
                        pwd_last_set = None

                # Additional info
                raw_info: Dict[str, Any] = {
                    "directory_type": "active_directory",
                    "distinguished_name": dn,
                    "user_account_control": uac,
                    "member_of": member_of,
                    "display_name": str(entry.displayName) if hasattr(entry, 'displayName') else None,
                    "email": str(entry.mail) if hasattr(entry, 'mail') else None,
                    "user_principal_name": str(entry.userPrincipalName) if hasattr(entry, 'userPrincipalName') else None,
                    "description": str(entry.description) if hasattr(entry, 'description') else None,
                    "title": str(entry.title) if hasattr(entry, 'title') else None,
                    "department": str(entry.department) if hasattr(entry, 'department') else None,
                    "company": str(entry.company) if hasattr(entry, 'company') else None,
                    "pwd_last_set": pwd_last_set.isoformat() if pwd_last_set else None,
                    "when_created": str(entry.whenCreated) if hasattr(entry, 'whenCreated') else None,
                    "when_changed": str(entry.whenChanged) if hasattr(entry, 'whenChanged') else None,
                }

                accounts.append(AccountInfo(
                    username=username_attr,
                    uid_sid=uid_sid,
                    is_admin=is_admin,
                    account_status=account_status,
                    home_dir="",  # LDAP doesn't have home_dir concept
                    shell="",  # LDAP doesn't have shell concept
                    groups=member_of,
                    sudo_config=None,
                    last_login=last_login,
                    raw_info=raw_info,
                ))

            except Exception as e:
                logger.warning(f"Error parsing LDAP entry: {e}")
                continue

        return (ConnectionResult(success=True, status="online"), accounts)

    except Exception as e:
        logger.error(f"AD scan error: {e}")
        return (
            ConnectionResult(success=False, error=f"扫描失败: {e}", status="offline"),
            []
        )
    finally:
        try:
            conn.unbind()
        except Exception:
            pass


def _scan_openldap(
    ip: str,
    port: int,
    username: str,
    password: str,
    base_dn: Optional[str],
    use_ssl: bool,
    timeout: int,
) -> Tuple[ConnectionResult, List[AccountInfo]]:
    """
    Scan OpenLDAP for user accounts.
    """
    try:
        from ldap3 import Server, Connection, ALL, SUBTREE
        from ldap3.core.exceptions import LDAPBindError, LDAPSocketOpenError
    except ImportError:
        return (
            ConnectionResult(
                success=False,
                error="ldap3 未安装: pip install ldap3",
                status="offline"
            ),
            []
        )

    if port == 0:
        port = 636 if use_ssl else 389

    server_url = f"ldaps://{ip}:{port}" if use_ssl else f"ldap://{ip}:{port}"

    try:
        server = Server(server_url, get_info=ALL, connect_timeout=timeout)
        conn = Connection(
            server,
            user=username,
            password=password,
            auto_bind=True,
            authentication="SIMPLE",
            ssl=use_ssl,
            raise_exceptions=True,
        )

    except LDAPBindError as e:
        return (
            ConnectionResult(
                success=False,
                error=f"认证失败: {e}",
                status="auth_failed"
            ),
            []
        )
    except LDAPSocketOpenError as e:
        return (
            ConnectionResult(
                success=False,
                error=f"连接失败: {e}",
                status="offline"
            ),
            []
        )
    except Exception as e:
        return (
            ConnectionResult(
                success=False,
                error=f"连接失败: {e}",
                status="offline"
            ),
            []
        )

    try:
        if not base_dn:
            if hasattr(server, 'info') and server.info:
                try:
                    base_dn = str(server.info.naming_contexts[0])
                except Exception:
                    base_dn = "dc=example,dc=com"
            else:
                base_dn = "dc=example,dc=com"

        # Get admin groups first
        admin_group_dns: Set[str] = set()

        try:
            conn.search(
                search_base=base_dn,
                search_filter="(objectClass=posixGroup)",
                search_scope=SUBTREE,
                attributes=["distinguishedName", "cn", "memberUid"],
            )
            for entry in conn.entries:
                cn = str(entry.cn) if hasattr(entry, 'cn') else ""
                if _is_admin_group(cn):
                    dn = str(entry.distinguishedName) if hasattr(entry, 'distinguishedName') else ""
                    admin_group_dns.add(dn.lower())
                    # Also check memberUid for direct membership
                    if hasattr(entry, 'memberUid'):
                        admin_group_dns.add(str(entry.memberUid).lower())
        except Exception as e:
            logger.warning(f"Failed to fetch admin groups: {e}")

        # Search for users (person, inetOrgPerson, posixAccount)
        conn.search(
            search_base=base_dn,
            search_filter="(|(objectClass=person)(objectClass=inetOrgPerson)(objectClass=posixAccount))",
            search_scope=SUBTREE,
            attributes=[
                "uid",
                "cn",
                "distinguishedName",
                "uidNumber",
                "gidNumber",
                "homeDirectory",
                "loginShell",
                "gecos",
                "memberOf",
                "shadowLastChange",
                "shadowMax",
                "shadowExpire",
                "createTimestamp",
                "modifyTimestamp",
                "shadowFlag",
            ],
        )

        accounts: List[AccountInfo] = []

        for entry in conn.entries:
            try:
                # Try uid first, then cn
                username_attr = None
                if hasattr(entry, 'uid') and entry.uid:
                    username_attr = str(entry.uid)
                elif hasattr(entry, 'cn') and entry.cn:
                    username_attr = str(entry.cn)
                else:
                    continue

                if not username_attr:
                    continue

                dn = str(entry.distinguishedName) if hasattr(entry, 'distinguishedName') else ""
                uid_sid = f"ldap://{dn}"

                # Check admin status via memberOf or sudoers-like groups
                member_of = []
                is_admin = False
                if hasattr(entry, 'memberOf') and entry.memberOf:
                    for group_dn in entry.memberOf:
                        group_dn_str = str(group_dn)
                        member_of.append(group_dn_str)
                        if _is_admin_group(group_dn_str):
                            is_admin = True
                        if group_dn_str.lower() in admin_group_dns:
                            is_admin = True

                # Check if user is in admin group via memberUid
                if hasattr(entry, 'gidNumber') and entry.gidNumber:
                    gid = int(entry.gidNumber)
                    # GID 0 (root) or GID for admin groups
                    if gid == 0:
                        is_admin = True

                # Account status - check shadow flags or assume enabled
                account_status = "enabled"
                if hasattr(entry, 'shadowFlag'):
                    try:
                        sf = int(entry.shadowFlag)
                        if sf & 0x10000:  # LDAP_ACB_DISABLED
                            account_status = "disabled"
                    except Exception:
                        pass

                # Last login from shadowLastChange
                last_login = None
                if hasattr(entry, 'shadowLastChange'):
                    try:
                        from datetime import timedelta
                        last_change = int(entry.shadowLastChange)
                        last_login = datetime(1970, 1, 1, tzinfo=timezone.utc) + timedelta(days=last_change)
                    except Exception:
                        last_login = None

                raw_info: Dict[str, Any] = {
                    "directory_type": "openldap",
                    "distinguished_name": dn,
                    "uid_number": str(entry.uidNumber) if hasattr(entry, 'uidNumber') else None,
                    "gid_number": str(entry.gidNumber) if hasattr(entry, 'gidNumber') else None,
                    "home_directory": str(entry.homeDirectory) if hasattr(entry, 'homeDirectory') else None,
                    "login_shell": str(entry.loginShell) if hasattr(entry, 'loginShell') else None,
                    "gecos": str(entry.gecos) if hasattr(entry, 'gecos') else None,
                    "member_of": member_of,
                    "create_timestamp": str(entry.createTimestamp) if hasattr(entry, 'createTimestamp') else None,
                    "modify_timestamp": str(entry.modifyTimestamp) if hasattr(entry, 'modifyTimestamp') else None,
                }

                accounts.append(AccountInfo(
                    username=username_attr,
                    uid_sid=uid_sid,
                    is_admin=is_admin,
                    account_status=account_status,
                    home_dir=str(entry.homeDirectory) if hasattr(entry, 'homeDirectory') else "",
                    shell=str(entry.loginShell) if hasattr(entry, 'loginShell') else "",
                    groups=member_of,
                    sudo_config=None,
                    last_login=last_login,
                    raw_info=raw_info,
                ))

            except Exception as e:
                logger.warning(f"Error parsing LDAP entry: {e}")
                continue

        return (ConnectionResult(success=True, status="online"), accounts)

    except Exception as e:
        logger.error(f"LDAP scan error: {e}")
        return (
            ConnectionResult(success=False, error=f"扫描失败: {e}", status="offline"),
            []
        )
    finally:
        try:
            conn.unbind()
        except Exception:
            pass


def scan_asset(
    ip: str,
    port: int,
    username: str,
    password: str,
    *,
    directory_type: str = "active_directory",
    base_dn: Optional[str] = None,
    use_ssl: bool = True,
    timeout: int = 30,
) -> Tuple[ConnectionResult, List[AccountInfo]]:
    """
    Scan LDAP/Active Directory for user accounts.

    Args:
        ip: LDAP server IP address
        port: LDAP port (636 for LDAPS, 389 for LDAP, 0 for default)
        username: Bind DN or UPN for authentication
        password: Bind password
        directory_type: Type of directory (active_directory, openldap, 389ds, custom)
        base_dn: Base DN for search (auto-detected if not provided)
        use_ssl: Use SSL/TLS (recommended for production)
        timeout: Connection timeout in seconds

    Returns:
        Tuple of (ConnectionResult, List[AccountInfo])
    """
    if directory_type == "active_directory":
        return _scan_active_directory(ip, port, username, password, base_dn, use_ssl, timeout)
    elif directory_type in ("openldap", "389ds", "custom"):
        return _scan_openldap(ip, port, username, password, base_dn, use_ssl, timeout)
    else:
        # Default to AD-style scan
        return _scan_active_directory(ip, port, username, password, base_dn, use_ssl, timeout)
