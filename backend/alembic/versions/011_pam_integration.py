"""Add PAM integration tables.

Revision ID: 011
Revises: 010_account_lifecycle
Create Date: 2026-03-29
"""

from alembic import op
import sqlalchemy as sa


revision = "011"
down_revision = "010_account_lifecycle"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "pam_integrations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("config", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(16), server_default="active", nullable=False),
        sa.Column("last_sync_at", sa.DateTime(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "pam_synced_accounts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("integration_id", sa.Integer(), nullable=False),
        sa.Column("asset_id", sa.Integer(), sa.ForeignKey("assets.id"), nullable=True),
        sa.Column("account_name", sa.String(128), nullable=False),
        sa.Column("account_type", sa.String(32), nullable=False),
        sa.Column("pam_status", sa.String(16), nullable=False),
        sa.Column("last_used", sa.DateTime(), nullable=True),
        sa.Column("matched_snapshot_id", sa.Integer(), sa.ForeignKey("account_snapshots.id"), nullable=True),
        sa.Column("match_confidence", sa.Integer(), server_default="0", nullable=False),
        sa.Column("synced_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKey(["integration_id"], ["pam_integrations.id"], name="fk_pam_integration"),
    )


def downgrade():
    op.drop_table("pam_synced_accounts")
    op.drop_table("pam_integrations")
