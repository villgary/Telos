"""Add security_policies and policy_evaluation_results tables

Revision ID: 015
Revises: 014
Create Date: 2026-03-31
"""

from alembic import op
import sqlalchemy as sa


revision = "015"
down_revision = "014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "security_policies",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category", sa.String(32), nullable=True),
        sa.Column("severity", sa.String(16), nullable=False, default="high"),
        sa.Column("rego_code", sa.Text(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, default=True),
        sa.Column("is_built_in", sa.Boolean(), nullable=False, default=False),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    op.create_table(
        "policy_evaluation_results",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("policy_id", sa.Integer(), sa.ForeignKey("security_policies.id"), nullable=False),
        sa.Column("snapshot_id", sa.Integer(), sa.ForeignKey("account_snapshots.id"), nullable=False),
        sa.Column("passed", sa.Boolean(), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("evaluated_at", sa.DateTime(), nullable=False, server_default=sa.func.now(), index=True),
    )

    # Seed built-in policies
    _seed_builtin_policies()


def downgrade() -> None:
    op.drop_table("policy_evaluation_results")
    op.drop_table("security_policies")


def _seed_builtin_policies() -> None:
    """Seed default built-in security policies."""
    from alembic import op
    import sqlalchemy as sa
    from datetime import datetime, timezone

    built_in = [
        {
            "name": "禁止 root 账号免密 sudo",
            "description": "检测配置了 NOPASSWD 的 sudoer，该配置允许免密提权",
            "category": "privilege",
            "severity": "critical",
            "rego_code": 'deny["NOPASSWD sudoer detected"] {\n  input.account.sudo_config\n  startswith(input.account.sudo_config, "NOPASSWD")\n}',
            "enabled": True,
            "is_built_in": True,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        },
        {
            "name": "禁止 root 账号远程登录",
            "description": "禁止 root 账号通过 SSH 远程登录（shell=/usr/sbin/nologin）",
            "category": "privilege",
            "severity": "high",
            "rego_code": 'deny["Root remote login allowed"] {\n  input.account.username == "root"\n  not startswith(input.account.shell, "/usr/sbin/nologin")\n}',
            "enabled": True,
            "is_built_in": True,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        },
        {
            "name": "禁止休眠账号保留特权",
            "description": "长期未登录（>90天）的账号不应保留 sudo/管理员权限",
            "category": "lifecycle",
            "severity": "high",
            "rego_code": 'deny["Dormant privileged account"] {\n  input.account.is_admin == true\n  days_since(input.account.last_login) > 90\n}',
            "enabled": True,
            "is_built_in": True,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        },
        {
            "name": "禁止通用共享账号名",
            "description": "禁止使用 admin/root/test/guest 等通用共享账号名",
            "category": "compliance",
            "severity": "medium",
            "rego_code": 'deny["Shared admin username detected"] {\n  contains(lower(input.account.username), "admin")\n}',
            "enabled": True,
            "is_built_in": True,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        },
        {
            "name": "禁止 UID 0 非 root 账号",
            "description": "UID 0 表示超级用户，禁止除 root 外的任何账号使用 UID 0",
            "category": "privilege",
            "severity": "critical",
            "rego_code": 'deny["Non-root UID 0 detected"] {\n  input.account.uid_sid == "0"\n  input.account.username != "root"\n}',
            "enabled": True,
            "is_built_in": True,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        },
    ]
