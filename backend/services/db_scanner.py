"""
Database account scanner service.
Supports MySQL, PostgreSQL, Redis, MongoDB, MSSQL.
Returns a unified AccountInfo list for consistent diff/alert processing.
"""

import socket
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional, Tuple, Dict, Any

logger = logging.getLogger(__name__)

# ───────────────────────────────────────────────
#  Shared dataclasses (re-exported from ssh_scanner for compatibility)
# ───────────────────────────────────────────────

from backend.services.ssh_scanner import AccountInfo, ConnectionResult


# ───────────────────────────────────────────────
#  MySQL / MariaDB scanner
# ───────────────────────────────────────────────

def _scan_mysql(
    ip: str,
    port: int,
    username: str,
    password: str,
    timeout: int = 15,
) -> Tuple[ConnectionResult, List[AccountInfo]]:
    """
    Scan MySQL/MariaDB accounts via pymysql.
    Queries mysql.user table for user list and privileges.
    """
    try:
        import pymysql
    except ImportError:
        return (ConnectionResult(success=False, error="pymysql 未安装: pip install pymysql", status="offline"), [])

    try:
        conn = pymysql.connect(
            host=ip, port=port, user=username, password=password,
            connect_timeout=timeout, read_timeout=timeout, write_timeout=timeout,
        )
    except pymysql.err.OperationalError as e:
        err = str(e)
        if "Access denied" in err or "28000" in err:
            return (ConnectionResult(success=False, error=f"认证失败: {err}", status="auth_failed"), [])
        if "Unknown database" in err:
            # Try without db
            try:
                conn = pymysql.connect(host=ip, port=port, user=username, password=password,
                                      connect_timeout=timeout)
            except Exception:
                return (ConnectionResult(success=False, error=f"连接失败: {err}", status="offline"), [])
        else:
            return (ConnectionResult(success=False, error=f"连接失败: {err}", status="offline"), [])
    except Exception as e:
        return (ConnectionResult(success=False, error=f"连接失败: {e}", status="offline"), [])

    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cur:
            # Get all users with their privileges
            cur.execute("""
                SELECT
                    User, Host,
                    IF(Select_priv='Y',1,0) AS select_priv,
                    IF(Insert_priv='Y',1,0) AS insert_priv,
                    IF(Update_priv='Y',1,0) AS update_priv,
                    IF(Delete_priv='Y',1,0) AS delete_priv,
                    IF(Create_priv='Y',1,0) AS create_priv,
                    IF(Drop_priv='Y',1,0) AS drop_priv,
                    IF(Reload_priv='Y',1,0) AS reload_priv,
                    IF(Shutdown_priv='Y',1,0) AS shutdown_priv,
                    IF(Process_priv='Y',1,0) AS process_priv,
                    IF(File_priv='Y',1,0) AS file_priv,
                    IF(Grant_priv='Y',1,0) AS grant_priv,
                    IF(Super_priv='Y',1,0) AS super_priv,
                    IF(Repl_slave_priv='Y',1,0) AS repl_slave_priv,
                    IF(Repl_client_priv='Y',1,0) AS repl_client_priv,
                    IF(Create_user_priv='Y',1,0) AS create_user_priv,
                    IF(Lock_tables_priv='Y',1,0) AS lock_tables_priv,
                    IF(Execute_priv='Y',1,0) AS execute_priv,
                    IF(Repl_slave_priv='Y',1,0) AS repl_slave,
                    IF(Repl_client_priv='Y',1,0) AS repl_client,
                    max_connections AS max_connections,
                    CONCAT(user, '@', host) AS uid_sid
                FROM mysql.user
                WHERE 1=1
            """)
            rows = cur.fetchall()

            accounts: List[AccountInfo] = []
            for row in rows:
                user = row.get("User", "")
                host = row.get("Host", "")
                if not user:
                    continue

                uid_sid = f"mysql://{user}@{host}"
                is_admin = (
                    row.get("super_priv") == 1 or
                    row.get("grant_priv") == 1 or
                    row.get("reload_priv") == 1 or
                    user == "root"
                )
                # Determine status: MySQL doesn't have a direct enabled/disabled flag
                # in user table for all versions; check if host is '%' (wildcard = remote)
                account_status = "enabled"

                privileges = {
                    k: v for k, v in row.items()
                    if k not in ("User", "Host", "uid_sid", "max_connections")
                    and v == 1
                }

                accounts.append(AccountInfo(
                    username=f"{user}@{host}",
                    uid_sid=uid_sid,
                    is_admin=is_admin,
                    account_status=account_status,
                    home_dir="",
                    shell="",
                    groups=[],
                    sudo_config={"privileges": list(privileges.keys())} if privileges else None,
                    last_login=None,
                    raw_info={
                        "db_type": "mysql",
                        "user": user,
                        "host": host,
                        "is_remote": host == "%",
                        "privileges": privileges,
                    },
                ))

        return (ConnectionResult(success=True, status="online"), accounts)

    except Exception as e:
        logger.error("MySQL scan error: %s", e)
        return (ConnectionResult(success=False, error=f"扫描失败: {e}", status="offline"), [])
    finally:
        conn.close()


# ───────────────────────────────────────────────
#  PostgreSQL scanner
# ───────────────────────────────────────────────

def _scan_postgresql(
    ip: str,
    port: int,
    username: str,
    password: str,
    timeout: int = 15,
) -> Tuple[ConnectionResult, List[AccountInfo]]:
    """
    Scan PostgreSQL roles via psycopg2.
    Queries pg_roles and pg_authid for role list and attributes.
    """
    try:
        import psycopg2
        from psycopg2 import sql, extras
    except ImportError:
        return (ConnectionResult(success=False, error="psycopg2 未安装: pip install psycopg2-binary", status="offline"), [])

    try:
        conn = psycopg2.connect(
            host=ip, port=port, user=username, password=password,
            connect_timeout=timeout,
            options="-c client_encoding=UTF8",
        )
    except psycopg2.OperationalError as e:
        err = str(e)
        if "password authentication failed" in err or "28P01" in err:
            return (ConnectionResult(success=False, error=f"认证失败: {err}", status="auth_failed"), [])
        return (ConnectionResult(success=False, error=f"连接失败: {err}", status="offline"), [])
    except Exception as e:
        return (ConnectionResult(success=False, error=f"连接失败: {e}", status="offline"), [])

    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            # Get roles with attributes (use RealDictCursor to avoid positional index errors)
            cur.execute("""
                SELECT
                    r.rolname,
                    r.rolsuper,
                    r.rolinherit,
                    r.rolcreaterole,
                    r.rolcreatedb,
                    r.rolcanlogin,
                    r.rolreplication,
                    r.rolbypassrls,
                    r.rolvaliduntil,
                    COALESCE(r.rolconnlimit, 0) AS conn_limit,
                    a.rolpassword AS password_hash
                FROM pg_roles r
                LEFT JOIN pg_authid a ON r.oid = a.oid
                WHERE r.rolname NOT LIKE 'pg_%%'
            """)
            rows = cur.fetchall()

            accounts: List[AccountInfo] = []
            for row in rows:
                rolname = str(row["rolname"])
                rolsuper = bool(row["rolsuper"])
                rolcreaterole = bool(row["rolcreaterole"])
                rolcreatedb = bool(row["rolcreatedb"])
                rolcanlogin = bool(row["rolcanlogin"])
                rolreplication = bool(row["rolreplication"])
                rolbypassrls = bool(row["rolbypassrls"])
                rolvaliduntil = row["rolvaliduntil"]
                conn_limit = row["conn_limit"]
                password_hash = row["password_hash"]

                # PostgreSQL superuser / bypass RLS = admin
                is_admin = rolsuper or rolcreaterole or rolbypassrls

                # Check expiry
                account_status = "enabled"
                if rolvaliduntil:
                    try:
                        expiry = datetime.strptime(str(rolvaliduntil), "%Y-%m-%d %H:%M:%S")
                        if expiry < datetime.now(timezone.utc):
                            account_status = "expired"
                    except Exception:
                        pass

                if not rolcanlogin:
                    account_status = "disabled"  # not a login role

                accounts.append(AccountInfo(
                    username=rolname,
                    uid_sid=f"pgsql://{rolname}",
                    is_admin=is_admin,
                    account_status=account_status,
                    home_dir="",
                    shell="",
                    groups=[],
                    sudo_config={
                        "rolsuper": rolsuper,
                        "rolcreaterole": rolcreaterole,
                        "rolcreatedb": rolcreatedb,
                        "rolcanlogin": rolcanlogin,
                        "rolreplication": rolreplication,
                        "rolbypassrls": rolbypassrls,
                        "conn_limit": conn_limit,
                    },
                    last_login=None,
                    raw_info={
                        "db_type": "postgresql",
                        "rolname": rolname,
                        "password_hash_present": password_hash is not None,
                    },
                ))

        return (ConnectionResult(success=True, status="online"), accounts)

    except Exception as e:
        logger.error("PostgreSQL scan error: %s", e)
        return (ConnectionResult(success=False, error=f"扫描失败: {e}", status="offline"), [])
    finally:
        conn.close()


# ───────────────────────────────────────────────
#  Redis scanner
# ───────────────────────────────────────────────

def _scan_redis(
    ip: str,
    port: int,
    username: str,
    password: str,
    timeout: int = 15,
) -> Tuple[ConnectionResult, List[AccountInfo]]:
    """
    Scan Redis users via ACL LIST command (Redis 6+).
    Falls back to INFO clients for Redis < 6.
    """
    try:
        import redis
    except ImportError:
        return (ConnectionResult(success=False, error="redis 未安装: pip install redis", status="offline"), [])

    try:
        r = redis.Redis(host=ip, port=port, password=password or None,
                        socket_timeout=timeout, socket_connect_timeout=timeout,
                        decode_responses=True)
        r.ping()
    except redis.exceptions.AuthenticationError:
        return (ConnectionResult(success=False, error="Redis 认证失败", status="auth_failed"), [])
    except redis.exceptions.ConnectionError as e:
        return (ConnectionResult(success=False, error=f"Redis 连接失败: {e}", status="offline"), [])
    except Exception as e:
        return (ConnectionResult(success=False, error=f"连接失败: {e}", status="offline"), [])

    try:
        accounts: List[AccountInfo] = []

        # Try ACL LIST (Redis 6+)
        try:
            acl_lines = r.execute_command("ACL LIST")
            if acl_lines:
                for entry in acl_lines:
                    # RESP bulk strings; decode if needed
                    entry_str = entry.decode() if isinstance(entry, bytes) else str(entry)
                    # ACL LIST format: space-separated key=value or keyword pairs
                    # e.g. "resetkeys keys * commands * ... nopass user scanuser ... flags N"
                    # We need the username after the "user" keyword, skipping "flags" keyword value
                    parts = entry_str.split()
                    try:
                        # "user" appears as a keyword before the username; find it
                        user_idx = parts.index("user")
                        username_val = parts[user_idx + 1]
                    except (ValueError, IndexError):
                        continue

                    # Skip values that land right after "user" but are actually keywords
                    if username_val in ("on", "off", "nopass", "allchannels", "resetchannels",
                                       "allkeys", "resetkeys", "clearskeys", "flags", "keys",
                                       "commands", "categories"):
                        continue

                    is_admin = False
                    account_status = "enabled"
                    flags = []

                    # Parse flags by looking for specific flag values anywhere in the entry
                    for part in parts:
                        if part == "on":
                            account_status = "enabled"
                        elif part == "off":
                            account_status = "disabled"
                        elif part in ("N",):
                            flags.append(part)
                        elif part in ("A", "AS"):
                            flags.append(part)
                            is_admin = True
                        elif part == "nopass":
                            flags.append("nopass")
                        elif part == "allkeys":
                            flags.append("allkeys")
                        elif part == "resetkeys":
                            flags.append("resetkeys")
                        elif part == "overrider-user":
                            flags.append("overrider-user")

                    accounts.append(AccountInfo(
                        username=username_val,
                        uid_sid=f"redis://{username_val}@{ip}:{port}",
                        is_admin=is_admin,
                        account_status=account_status,
                        home_dir="",
                        shell="",
                        groups=[],
                        sudo_config={"acl_flags": flags} if flags else None,
                        last_login=None,
                        raw_info={
                            "db_type": "redis",
                            "acl_entry": entry_str[:200],
                            "flags": flags,
                        },
                    ))
        except redis.exceptions.ResponseError:
            # Redis < 6: no ACL, only one user
            info = r.info("server")
            accounts.append(AccountInfo(
                username="default",
                uid_sid=f"redis://default@{ip}:{port}",
                is_admin=True,  # only user available
                account_status="enabled",
                home_dir="",
                shell="",
                groups=[],
                sudo_config={"version_pre_6_no_acl": True},
                last_login=None,
                raw_info={"db_type": "redis", "version_pre_6": True},
            ))

        return (ConnectionResult(success=True, status="online"), accounts)

    except Exception as e:
        logger.error("Redis scan error: %s", e)
        return (ConnectionResult(success=False, error=f"扫描失败: {e}", status="offline"), [])
    finally:
        try:
            r.aclose()
        except Exception:
            pass


# ───────────────────────────────────────────────
#  MongoDB scanner
# ───────────────────────────────────────────────

def _scan_mongodb(
    ip: str,
    port: int,
    username: str,
    password: str,
    timeout: int = 15,
) -> Tuple[ConnectionResult, List[AccountInfo]]:
    """
    Scan MongoDB users via pymongo.
    Queries admin.system.users or usersInfo command.
    """
    try:
        from pymongo import MongoClient
        from pymongo.errors import OperationFailure, ServerSelectionTimeoutError
    except ImportError:
        return (ConnectionResult(success=False, error="pymongo 未安装: pip install pymongo", status="offline"), [])

    try:
        uri = f"mongodb://{username}:{password}@{ip}:{port}/?authSource=admin&serverSelectionTimeoutMS={timeout*1000}"
        client = MongoClient(uri, serverSelectionTimeoutMS=timeout * 1000)
        # Test connection
        client.admin.command("ping")
    except OperationFailure as e:
        err = str(e)
        if "auth failed" in err.lower() or "13" in err:
            return (ConnectionResult(success=False, error=f"认证失败: {err}", status="auth_failed"), [])
        return (ConnectionResult(success=False, error=f"连接失败: {err}", status="offline"), [])
    except ServerSelectionTimeoutError:
        return (ConnectionResult(success=False, error="MongoDB 连接超时", status="offline"), [])
    except Exception as e:
        return (ConnectionResult(success=False, error=f"连接失败: {e}", status="offline"), [])

    try:
        accounts: List[AccountInfo] = []

        # Get all users in all databases
        for db_name in client.list_database_names():
            if db_name in ("local", "config"):
                continue
            try:
                db = client[db_name]
                users = db.command("usersInfo")["users"]
                for user_doc in users:
                    uname = user_doc.get("user", "")
                    if not uname:
                        continue

                    # Check roles for admin status
                    roles = user_doc.get("roles", [])
                    db_roles = [r.get("role", "") for r in roles]
                    admin_roles = {"root", "dbAdminAnyDatabase", "userAdminAnyDatabase",
                                   "readWriteAnyDatabase", "readAnyDatabase"}
                    is_admin = any(r in admin_roles for r in db_roles) or uname == "admin"

                    # Check if user is disabled (MongoDB doesn't have built-in disable)
                    account_status = "enabled"

                    accounts.append(AccountInfo(
                        username=f"{uname}@{db_name}",
                        uid_sid=f"mongodb://{uname}@{ip}:{port}/{db_name}",
                        is_admin=is_admin,
                        account_status=account_status,
                        home_dir="",
                        shell="",
                        groups=[],
                        sudo_config={"roles": db_roles},
                        last_login=None,
                        raw_info={
                            "db_type": "mongodb",
                            "user": uname,
                            "db": db_name,
                            "roles": db_roles,
                            "authentication_restrictions": user_doc.get("authenticationRestrictions", []),
                        },
                    ))
            except OperationFailure:
                continue

        return (ConnectionResult(success=True, status="online"), accounts)

    except Exception as e:
        logger.error("MongoDB scan error: %s", e)
        return (ConnectionResult(success=False, error=f"扫描失败: {e}", status="offline"), [])
    finally:
        try:
            client.close()
        except Exception:
            pass


# ───────────────────────────────────────────────
#  MSSQL scanner
# ───────────────────────────────────────────────

def _scan_mssql(
    ip: str,
    port: int,
    username: str,
    password: str,
    timeout: int = 15,
) -> Tuple[ConnectionResult, List[AccountInfo]]:
    """
    Scan MSSQL logins accounts via pyodbc or pymssql.
    Queries sys.sql_logins and sys.server_role_members.
    """
    try:
        import pyodbc
    except ImportError:
        return (ConnectionResult(success=False, error="pyodbc 未安装: pip install pyodbc", status="offline"), [])

    # Build connection string
    # Try trusted first, then SQL auth
    conn_strs = [
        f"DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={ip},{port};DATABASE=master;Trusted_Connection=yes;TrustServerCertificate=yes;",
        f"DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={ip},{port};DATABASE=master;UID={username};PWD={password};TrustServerCertificate=yes;",
    ]

    conn = None
    last_error = None
    for conn_str in conn_strs:
        try:
            conn = pyodbc.connect(conn_str, timeout=timeout)
            break
        except Exception as e:
            last_error = str(e)
            if "login timeout" in last_error.lower() or "connection refused" in last_error.lower():
                return (ConnectionResult(success=False, error=f"连接超时/拒绝: {last_error}", status="offline"), [])
            if "login failed" in last_error.lower():
                return (ConnectionResult(success=False, error=f"认证失败: {last_error}", status="auth_failed"), [])

    if conn is None:
        return (ConnectionResult(success=False, error=f"连接失败: {last_error}", status="offline"), [])

    try:
        accounts: List[AccountInfo] = []
        cur = conn.cursor()

        # Get all SQL logins
        cur.execute("""
            SELECT
                s.name,
                s.type_desc,
                s.is_disabled,
                s.create_date,
                s.modify_date,
                s.default_database_name,
                CASE WHEN s.is_policy_checked = 1 THEN 1 ELSE 0 END AS is_policy_checked,
                CASE WHEN s.is_expiration_checked = 1 THEN 1 ELSE 0 END AS is_expiration_checked,
                CASE WHEN s.is_locked = 1 THEN 1 ELSE 0 END AS is_locked,
                CASE WHEN r.role_id IS NOT NULL THEN 1 ELSE 0 END AS is_sysadmin
            FROM sys.sql_logins s
            LEFT JOIN sys.server_role_members r ON s.principal_id = r.member_principal_id
                AND r.role_principal_id = 3  -- sysadmin role
            WHERE s.name NOT LIKE '#%'
        """)

        rows = cur.fetchall()
        seen = set()

        for row in rows:
            name = row[0]
            if name in seen:
                continue
            seen.add(name)

            type_desc = row[1]
            is_disabled = bool(row[2])
            default_db = row[5]
            is_locked = bool(row[8])
            is_sysadmin = bool(row[9])

            # SQL auth vs Windows auth
            is_windows_auth = type_desc and "WINDOWS" in type_desc.upper()

            is_admin = is_sysadmin
            account_status = "locked" if is_locked else ("disabled" if is_disabled else "enabled")

            accounts.append(AccountInfo(
                username=name,
                uid_sid=f"mssql://{name}@{ip}:{port}",
                is_admin=is_admin,
                account_status=account_status,
                home_dir="",
                shell="",
                groups=[],
                sudo_config={
                    "type": type_desc,
                    "is_sysadmin": is_sysadmin,
                    "is_windows_auth": is_windows_auth,
                    "default_db": default_db,
                    "is_policy_checked": bool(row[6]),
                },
                last_login=None,
                raw_info={
                    "db_type": "mssql",
                    "login_name": name,
                    "type_desc": type_desc,
                    "is_sysadmin": is_sysadmin,
                    "is_windows_auth": is_windows_auth,
                    "default_db": default_db,
                },
            ))

        cur.close()
        return (ConnectionResult(success=True, status="online"), accounts)

    except Exception as e:
        logger.error("MSSQL scan error: %s", e)
        return (ConnectionResult(success=False, error=f"扫描失败: {e}", status="offline"), [])
    finally:
        if conn:
            conn.close()


# ───────────────────────────────────────────────
#  Oracle scanner
# ───────────────────────────────────────────────

def _scan_oracle(
    ip: str,
    port: int,
    username: str,
    password: str,
    timeout: int = 15,
) -> Tuple[ConnectionResult, List[AccountInfo]]:
    """
    Scan Oracle accounts via oracledb (thin mode).
    Queries dba_users, dba_role_privs, v$instance.
    Requires scanuser to have SELECT ANY DICTIONARY or explicit grants on
    the relevant views.
    """
    try:
        import oracledb
    except ImportError:
        return (ConnectionResult(success=False, error="oracledb 未安装: pip install oracledb", status="offline"), [])

    # Build DSN: supports both thin mode (connection string) and thick mode
    dsn = f"{ip}:{port}/XE"

    try:
        conn = oracledb.connect(
            user=username,
            password=password,
            dsn=dsn,
        )
    except oracledb.DatabaseError as e:
        err = str(e)
        if "ORA-01017" in err or "ORA-12170" in err:
            return (ConnectionResult(success=False, error=f"认证失败: {err}", status="auth_failed"), [])
        if "ORA-12541" in err:
            return (ConnectionResult(success=False, error=f"TNS:监听器未就绪: {err}", status="offline"), [])
        return (ConnectionResult(success=False, error=f"连接失败: {err}", status="offline"), [])
    except Exception as e:
        return (ConnectionResult(success=False, error=f"连接失败: {e}", status="offline"), [])

    try:
        accounts: List[AccountInfo] = []

        with conn.cursor() as cur:
            # 1. Instance info
            cur.execute("SELECT instance_name, host_name, version FROM v$instance")
            inst_row = cur.fetchone()
            instance_name = inst_row[0] if inst_row else ""
            version = inst_row[2] if inst_row else ""

            # 2. All database users (accounts)
            cur.execute("""
                SELECT
                    username,
                    account_status,
                    lock_date,
                    expiry_date,
                    created,
                    default_tablespace,
                    profile,
                    authentication_type
                FROM dba_users
                WHERE username NOT IN ('SYS', 'SYSTEM')
                  AND username NOT LIKE 'APEX%'
                  AND username NOT LIKE 'FLOWS%'
                  AND username NOT LIKE 'ORD%'
                  AND username NOT LIKE 'GSMC%'
                ORDER BY username
            """)
            user_rows = cur.fetchall()

            # 3. Role/privilege info for each user (batch)
            cur.execute("""
                SELECT
                    grantee,
                    granted_role,
                    admin_option
                FROM dba_role_privs
                WHERE grantee NOT IN ('SYS', 'SYSTEM')
                  AND grantee NOT LIKE 'APEX%'
                ORDER BY grantee
            """)
            role_rows = cur.fetchall()

            # Build role map: grantee -> [(role, admin_opt), ...]
            from collections import defaultdict
            role_map: Dict[str, list] = defaultdict(list)
            for grantee, role, admin_opt in role_rows:
                role_map[grantee].append((role, bool(admin_opt)))

            # DBA-level roles that imply admin
            ADMIN_ROLES = {
                "DBA", "DATABASE", "RESOURCE", "CONNECT",
                "DBA_EXP", "IMP_FULL_DATABASE", "EXP_FULL_DATABASE",
                "DATAPUMP_EXP_FULL_DATABASE", "DATAPUMP_IMP_FULL_DATABASE",
                "EXECUTE_CATALOG_ROLE", "SELECT_CATALOG_ROLE",
            }

            for row in user_rows:
                username_raw = row[0]
                account_status = row[1]
                lock_date = row[2]
                expiry_date = row[3]
                created = row[4]
                default_ts = row[5]
                profile = row[6]
                auth_type = row[7]

                # Map Oracle status to our enum
                status_map = {
                    "OPEN": "enabled",
                    "EXPIRED": "enabled",       # expired but still valid
                    "EXPIRED(GRACE)": "enabled",
                    "EXPIRED & LOCKED": "disabled",
                    "LOCKED(TIMED)": "disabled",
                    "LOCKED": "disabled",
                }
                mapped_status = status_map.get(str(account_status), "enabled")

                # Check if admin via roles
                roles = role_map.get(username_raw, [])
                role_names = [r[0] for r in roles]
                is_admin = any(r in ADMIN_ROLES for r in role_names)

                # Also flag if user has DBA or RESOURCE+CONNECT (common combo)
                if "RESOURCE" in role_names and "CONNECT" in role_names:
                    is_admin = True

                sudo_config = {
                    "roles": role_names,
                    "admin_roles": [r for r, ao in roles if ao],
                    "default_tablespace": default_ts,
                    "profile": profile,
                    "auth_type": auth_type,
                    "created": str(created) if created else None,
                    "version": version,
                }

                accounts.append(AccountInfo(
                    username=username_raw,
                    uid_sid=f"oracle://{username_raw}@{ip}:{port}/XE",
                    is_admin=is_admin,
                    account_status=mapped_status,
                    home_dir="",
                    shell="",
                    groups=[],
                    sudo_config=sudo_config,
                    last_login=None,
                    raw_info={
                        "db_type": "oracle",
                        "username": username_raw,
                        "account_status": str(account_status),
                        "lock_date": str(lock_date) if lock_date else None,
                        "expiry_date": str(expiry_date) if expiry_date else None,
                        "roles": role_names,
                        "is_admin": is_admin,
                        "instance_name": instance_name,
                        "version": version,
                    },
                ))

        return (ConnectionResult(success=True, status="online"), accounts)

    except Exception as e:
        logger.error("Oracle scan error: %s", e)
        return (ConnectionResult(success=False, error=f"扫描失败: {e}", status="offline"), [])
    finally:
        conn.close()


# ───────────────────────────────────────────────
#  Unified entry point
# ───────────────────────────────────────────────

def scan_asset(
    ip: str,
    port: int,
    username: str,
    password: Optional[str] = None,
    db_type: str = "mysql",
    timeout: int = 120,
) -> Tuple[ConnectionResult, List[AccountInfo]]:
    """
    Unified database scanner. Routes to the appropriate DB-specific scanner.

    Args:
        ip: Database server IP
        port: Database server port
        username: Database username
        password: Database password
        db_type: One of mysql, postgresql, redis, mongodb, mssql
        timeout: Operation timeout in seconds

    Returns:
        (ConnectionResult, List[AccountInfo])
    """
    # Set default ports if not specified
    if port == 0 or port is None:
        defaults = {"mysql": 3306, "postgresql": 5432, "redis": 6379,
                    "mongodb": 27017, "mssql": 1433, "oracle": 1521}
        port = defaults.get(db_type, 3306)

    # Connection test first
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((ip, port))
        sock.close()
        if result != 0:
            return (ConnectionResult(success=False, error=f"端口 {port} 无法连接", status="offline"), [])
    except Exception as e:
        return (ConnectionResult(success=False, error=f"网络探测失败: {e}", status="offline"), [])

    password = password or ""

    if db_type == "mysql":
        return _scan_mysql(ip, port, username, password, timeout)
    elif db_type == "postgresql":
        return _scan_postgresql(ip, port, username, password, timeout)
    elif db_type == "redis":
        return _scan_redis(ip, port, username, password, timeout)
    elif db_type == "mongodb":
        return _scan_mongodb(ip, port, username, password, timeout)
    elif db_type == "mssql":
        return _scan_mssql(ip, port, username, password, timeout)
    elif db_type == "oracle":
        return _scan_oracle(ip, port, username, password, timeout)
    else:
        return (ConnectionResult(success=False, error=f"不支持的数据库类型: {db_type}", status="offline"), [])
