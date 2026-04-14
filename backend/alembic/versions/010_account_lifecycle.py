"""Add account lifecycle tables.

Revision ID: 010
Revises: 009_identity_fusion
Create Date: 2026-03-29
"""

from alembic import op
import sqlalchemy as sa


revision = "010"
down_revision = "009_identity_fusion"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "account_lifecycle_configs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("category_slug", sa.String(32), nullable=False),
        sa.Column("active_days", sa.Integer(), server_default="30", nullable=False),
        sa.Column("dormant_days", sa.Integer(), server_default="90", nullable=False),
        sa.Column("auto_alert", sa.Boolean(), server_default="1", nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("category_slug", name="uq_lifecycle_category"),
    )

    op.create_table(
        "account_lifecycle_statuses",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("snapshot_id", sa.Integer(), nullable=False),
        sa.Column("lifecycle_status", sa.String(16), nullable=False),
        sa.Column("previous_status", sa.String(16), nullable=True),
        sa.Column("changed_at", sa.DateTime(), nullable=True),
        sa.Column("alert_sent", sa.Boolean(), server_default="0", nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKey(["snapshot_id"], ["account_snapshots.id"], name="fk_lifecycle_snapshot"),
        sa.UniqueConstraint("snapshot_id", name="uq_lifecycle_snapshot"),
    )


def downgrade():
    op.drop_table("account_lifecycle_statuses")
    op.drop_table("account_lifecycle_configs")
