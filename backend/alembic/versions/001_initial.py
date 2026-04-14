"""Initial migration — create all tables.

Revision ID: 001
Revises:
Create Date: 2026-03-28

"""
from alembic import op
import sqlalchemy as sa

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def _enum_columns(enum_name: str, *values: str):
    """Build the (name, Enum(sqlite_format, pg_format)) column definition list."""
    return [(v,) for v in values]


# ─── Upgrade ───────────────────────────────────────────────────────────────────

def upgrade() -> None:
    dialect = op.get_context().dialect.name

    # ── Pre-create enum types (PostgreSQL only; SQLite ignores create_type=False)
    for enum_name, values in [
        ("userrole",        "admin", "operator", "viewer"),
        ("authtype",        "password", "ssh_key"),
        ("assetcategory",   "server", "database", "network"),
        ("ostype",          "linux", "windows"),
        ("dbtype",          "mysql", "postgresql", "redis", "mongodb", "mssql"),
        ("networkvendor",   "cisco", "h3c", "huawei", "generic"),
        ("assetstatus",     "untested", "online", "offline", "auth_failed"),
        ("scanjobstatus",   "pending", "running", "success", "partial_success", "failed", "cancelled"),
        ("triggertype",     "manual", "scheduled"),
        ("difftype",        "added", "removed", "escalated", "deactivated", "modified"),
        ("risklevel",       "critical", "warning", "info"),
        ("diffstatus",      "pending", "confirmed_safe", "confirmed_threat"),
        ("alertchannel",    "email", "in_app"),
        ("alertlevel",      "critical", "warning", "info"),
    ]:
        enum_type = sa.Enum(*values, name=enum_name, create_type=True)
        enum_type.create(op.get_bind(), checkfirst=False)

    # Helper to get the right SQLAlchemy type
    def enum_col(name: str, values: tuple):
        pg_type = sa.Enum(*values, name=name, create_type=False)
        return sa.Column(pg_type)

    # ── users ──────────────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("username", sa.String(64), nullable=False),
        sa.Column("password_hash", sa.String(256), nullable=False),
        sa.Column("role", sa.Enum("admin", "operator", "viewer", name="userrole", create_type=False), nullable=False),
        sa.Column("email", sa.String(128), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, default=True),
        sa.Column("is_password_changed", sa.Boolean(), nullable=False, default=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("username"),
    )
    op.create_index("ix_users_id", "users", ["id"])
    op.create_index("ix_users_username", "users", ["username"], unique=True)

    # ── credentials ────────────────────────────────────────────────────────────
    op.create_table(
        "credentials",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("auth_type", sa.Enum("password", "ssh_key", name="authtype", create_type=False), nullable=False),
        sa.Column("username", sa.String(128), nullable=False),
        sa.Column("password_enc", sa.Text(), nullable=True),
        sa.Column("private_key_enc", sa.Text(), nullable=True),
        sa.Column("passphrase_enc", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_index("ix_credentials_id", "credentials", ["id"])

    # ── asset_groups ───────────────────────────────────────────────────────────
    op.create_table(
        "asset_groups",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("description", sa.String(512), nullable=True),
        sa.Column("color", sa.String(8), nullable=False, default="#1890ff"),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_index("ix_asset_groups_id", "asset_groups", ["id"])

    # ── scan_jobs (FK to assets added after assets table) ─────────────────────
    op.create_table(
        "scan_jobs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("asset_id", sa.Integer(), nullable=False),
        sa.Column("trigger_type", sa.Enum("manual", "scheduled", name="triggertype", create_type=False), nullable=False),
        sa.Column("status", sa.Enum("pending", "running", "success", "partial_success", "failed", "cancelled", name="scanjobstatus", create_type=False), nullable=False),
        sa.Column("success_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_scan_jobs_id", "scan_jobs", ["id"])

    # ── assets ──────────────────────────────────────────────────────────────────
    op.create_table(
        "assets",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("ip", sa.String(45), nullable=False),
        sa.Column("hostname", sa.String(255), nullable=True),
        sa.Column("asset_category", sa.Enum("server", "database", "network", name="assetcategory", create_type=False), nullable=False),
        sa.Column("os_type", sa.Enum("linux", "windows", name="ostype", create_type=False), nullable=True),
        sa.Column("db_type", sa.Enum("mysql", "postgresql", "redis", "mongodb", "mssql", name="dbtype", create_type=False), nullable=True),
        sa.Column("network_type", sa.Enum("cisco", "h3c", "huawei", "generic", name="networkvendor", create_type=False), nullable=True),
        sa.Column("group_id", sa.Integer(), nullable=True),
        sa.Column("port", sa.Integer(), nullable=False, server_default="22"),
        sa.Column("status", sa.Enum("untested", "online", "offline", "auth_failed", name="assetstatus", create_type=False), nullable=False),
        sa.Column("last_scan_at", sa.DateTime(), nullable=True),
        sa.Column("last_scan_job_id", sa.Integer(), nullable=True),
        sa.Column("credential_id", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["group_id"], ["asset_groups.id"]),
        sa.ForeignKeyConstraint(["credential_id"], ["credentials.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("ip", "port", name="uq_asset_ip_port"),
    )
    op.create_index("ix_assets_id", "assets", ["id"])
    op.create_index("ix_assets_ip", "assets", ["ip"])

    # ── Add scan_jobs.asset_id FK now that assets exists ────────────────────────
    op.create_foreign_key("fk_scan_jobs_asset", "scan_jobs", "assets", ["asset_id"], ["id"])
    op.create_foreign_key("fk_assets_last_scan_job", "assets", "scan_jobs", ["last_scan_job_id"], ["id"])

    # ── account_snapshots ──────────────────────────────────────────────────────
    op.create_table(
        "account_snapshots",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("asset_id", sa.Integer(), nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=False),
        sa.Column("username", sa.String(128), nullable=False),
        sa.Column("uid_sid", sa.String(256), nullable=False),
        sa.Column("is_admin", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("account_status", sa.String(32), nullable=True),
        sa.Column("home_dir", sa.String(512), nullable=True),
        sa.Column("shell", sa.String(128), nullable=True),
        sa.Column("groups", sa.JSON(), nullable=True),
        sa.Column("sudo_config", sa.JSON(), nullable=True),
        sa.Column("last_login", sa.DateTime(), nullable=True),
        sa.Column("raw_info", sa.JSON(), nullable=True),
        sa.Column("snapshot_time", sa.DateTime(), nullable=False),
        sa.Column("is_baseline", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"]),
        sa.ForeignKeyConstraint(["job_id"], ["scan_jobs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_account_snapshots_id", "account_snapshots", ["id"])
    op.create_index("ix_account_snapshots_username", "account_snapshots", ["username"])

    # ── diff_results ────────────────────────────────────────────────────────────
    op.create_table(
        "diff_results",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("base_job_id", sa.Integer(), nullable=False),
        sa.Column("compare_job_id", sa.Integer(), nullable=False),
        sa.Column("diff_type", sa.Enum("added", "removed", "escalated", "deactivated", "modified", name="difftype", create_type=False), nullable=False),
        sa.Column("risk_level", sa.Enum("critical", "warning", "info", name="risklevel", create_type=False), nullable=False),
        sa.Column("username", sa.String(128), nullable=False),
        sa.Column("snapshot_a_id", sa.Integer(), nullable=True),
        sa.Column("snapshot_b_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.Enum("pending", "confirmed_safe", "confirmed_threat", name="diffstatus", create_type=False), nullable=False),
        sa.Column("reviewed_by", sa.Integer(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["base_job_id"], ["scan_jobs.id"]),
        sa.ForeignKeyConstraint(["compare_job_id"], ["scan_jobs.id"]),
        sa.ForeignKeyConstraint(["reviewed_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["snapshot_a_id"], ["account_snapshots.id"]),
        sa.ForeignKeyConstraint(["snapshot_b_id"], ["account_snapshots.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_diff_results_id", "diff_results", ["id"])

    # ── audit_logs ──────────────────────────────────────────────────────────────
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("target_type", sa.String(32), nullable=True),
        sa.Column("target_id", sa.Integer(), nullable=True),
        sa.Column("detail", sa.JSON(), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_logs_id", "audit_logs", ["id"])
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])

    # ── scan_schedules ──────────────────────────────────────────────────────────
    op.create_table(
        "scan_schedules",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("asset_id", sa.Integer(), nullable=False),
        sa.Column("cron_expr", sa.String(64), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("next_run_at", sa.DateTime(), nullable=True),
        sa.Column("last_run_at", sa.DateTime(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_scan_schedules_id", "scan_schedules", ["id"])

    # ── alert_configs ───────────────────────────────────────────────────────────
    op.create_table(
        "alert_configs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("channel", sa.Enum("email", "in_app", name="alertchannel", create_type=False), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("settings", sa.JSON(), nullable=True),
        sa.Column("asset_ids", sa.JSON(), nullable=True),
        sa.Column("risk_levels", sa.JSON(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_alert_configs_id", "alert_configs", ["id"])

    # ── alerts ──────────────────────────────────────────────────────────────────
    op.create_table(
        "alerts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("config_id", sa.Integer(), nullable=True),
        sa.Column("asset_id", sa.Integer(), nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=True),
        sa.Column("diff_item_id", sa.Integer(), nullable=True),
        sa.Column("level", sa.Enum("critical", "warning", "info", name="alertlevel", create_type=False), nullable=False),
        sa.Column("title", sa.String(256), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["config_id"], ["alert_configs.id"]),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"]),
        sa.ForeignKeyConstraint(["job_id"], ["scan_jobs.id"]),
        sa.ForeignKeyConstraint(["diff_item_id"], ["diff_results.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_alerts_id", "alerts", ["id"])

    # ── refresh_tokens ──────────────────────────────────────────────────────────
    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("revoked", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index("ix_refresh_tokens_id", "refresh_tokens", ["id"])
    op.create_index("ix_refresh_tokens_token_hash", "refresh_tokens", ["token_hash"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_refresh_tokens_token_hash", table_name="refresh_tokens")
    op.drop_index("ix_refresh_tokens_id", table_name="refresh_tokens")
    op.drop_table("refresh_tokens")

    op.drop_index("ix_alerts_id", table_name="alerts")
    op.drop_table("alerts")

    op.drop_index("ix_alert_configs_id", table_name="alert_configs")
    op.drop_table("alert_configs")

    op.drop_index("ix_scan_schedules_id", table_name="scan_schedules")
    op.drop_table("scan_schedules")

    op.drop_index("ix_audit_logs_action", table_name="audit_logs")
    op.drop_index("ix_audit_logs_id", table_name="audit_logs")
    op.drop_table("audit_logs")

    op.drop_index("ix_diff_results_id", table_name="diff_results")
    op.drop_table("diff_results")

    op.drop_index("ix_account_snapshots_username", table_name="account_snapshots")
    op.drop_index("ix_account_snapshots_id", table_name="account_snapshots")
    op.drop_table("account_snapshots")

    op.drop_constraint("fk_assets_last_scan_job", "assets", type_="foreignkey")
    op.drop_constraint("fk_scan_jobs_asset", "scan_jobs", type_="foreignkey")
    op.drop_index("ix_assets_ip", table_name="assets")
    op.drop_index("ix_assets_id", table_name="assets")
    op.drop_table("assets")

    op.drop_index("ix_scan_jobs_id", table_name="scan_jobs")
    op.drop_table("scan_jobs")

    op.drop_index("ix_asset_groups_id", table_name="asset_groups")
    op.drop_table("asset_groups")

    op.drop_index("ix_credentials_id", table_name="credentials")
    op.drop_table("credentials")

    op.drop_index("ix_users_username", table_name="users")
    op.drop_index("ix_users_id", table_name="users")
    op.drop_table("users")

    # Drop PostgreSQL enum types
    for name in [
        "userrole", "authtype", "assetcategory", "ostype", "dbtype",
        "networkvendor", "assetstatus", "scanjobstatus", "triggertype",
        "difftype", "risklevel", "diffstatus", "alertchannel", "alertlevel",
    ]:
        op.execute(f"DROP TYPE IF EXISTS {name}")
