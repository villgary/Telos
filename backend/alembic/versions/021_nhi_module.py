"""NHI Module tables

Revision ID: 021_nhi_module
Revises: 020_playbook_i18n
"""
from alembic import op
import sqlalchemy as sa


revision = "021_nhi_module"
down_revision = "020_playbook_i18n"
branch_labels = None
depends_on = None


def upgrade():
    # NHI Identity registry
    op.create_table(
        "nhi_identities",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("snapshot_id", sa.Integer(), sa.ForeignKey("account_snapshots.id"), nullable=True),
        sa.Column("asset_id", sa.Integer(), sa.ForeignKey("assets.id"), nullable=True),
        sa.Column("nhi_type", sa.String(32), nullable=False, server_default="unknown"),
        sa.Column("nhi_level", sa.String(16), nullable=False, server_default="low"),
        sa.Column("username", sa.String(128), nullable=False, index=True),
        sa.Column("uid_sid", sa.String(256), nullable=True),
        sa.Column("hostname", sa.String(256), nullable=True),
        sa.Column("ip_address", sa.String(64), nullable=True),
        sa.Column("is_admin", sa.Boolean(), server_default="false"),
        sa.Column("credential_types", sa.JSON(), server_default="[]"),
        sa.Column("has_nopasswd_sudo", sa.Boolean(), server_default="false"),
        sa.Column("risk_score", sa.Integer(), server_default="0"),
        sa.Column("risk_signals", sa.JSON(), server_default="[]"),
        sa.Column("owner_identity_id", sa.Integer(), sa.ForeignKey("human_identities.id"), nullable=True),
        sa.Column("owner_email", sa.String(256), nullable=True),
        sa.Column("owner_name", sa.String(128), nullable=True),
        sa.Column("first_seen_at", sa.DateTime(), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(), nullable=True),
        sa.Column("last_rotated_at", sa.DateTime(), nullable=True),
        sa.Column("rotation_due_days", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true"),
        sa.Column("is_monitored", sa.Boolean(), server_default="false"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index("ix_nhi_identities_username", "nhi_identities", ["username"])

    # NHI Alerts
    op.create_table(
        "nhi_alerts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("nhi_id", sa.Integer(), sa.ForeignKey("nhi_identities.id"), nullable=False),
        sa.Column("alert_type", sa.String(64), nullable=False),
        sa.Column("level", sa.String(16), nullable=False),
        sa.Column("title", sa.String(256), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("title_key", sa.String(64), nullable=True),
        sa.Column("title_params", sa.JSON(), nullable=True),
        sa.Column("message_key", sa.String(64), nullable=True),
        sa.Column("message_params", sa.JSON(), nullable=True),
        sa.Column("is_read", sa.Boolean(), server_default="false"),
        sa.Column("status", sa.String(16), server_default="new"),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.Column("resolved_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # NHI Policies
    op.create_table(
        "nhi_policies",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(128), nullable=False, unique=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("nhi_type", sa.String(32), nullable=True),
        sa.Column("severity_filter", sa.String(16), nullable=True),
        sa.Column("rotation_days", sa.Integer(), nullable=True),
        sa.Column("alert_threshold_days", sa.Integer(), nullable=True),
        sa.Column("require_owner", sa.Boolean(), server_default="true"),
        sa.Column("require_monitoring", sa.Boolean(), server_default="false"),
        sa.Column("enabled", sa.Boolean(), server_default="true"),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
    )


def downgrade():
    op.drop_table("nhi_policies")
    op.drop_table("nhi_alerts")
    op.drop_table("nhi_identities")
