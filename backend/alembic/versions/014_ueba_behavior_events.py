"""Add account_behavior_events table (UEBA)

Revision ID: 014
Revises: 013
Create Date: 2026-03-31
"""

from alembic import op
import sqlalchemy as sa


revision = "014"
down_revision = "013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "account_behavior_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("event_type", sa.String(32), nullable=False, index=True),
        sa.Column("severity", sa.String(16), nullable=False, default="medium"),
        sa.Column("username", sa.String(128), nullable=False, index=True),
        sa.Column("asset_code", sa.String(32), nullable=True),
        sa.Column("asset_ip", sa.String(45), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("snapshot_id", sa.Integer(), sa.ForeignKey("account_snapshots.id"), nullable=True),
        sa.Column("detected_at", sa.DateTime(), nullable=False, default=sa.func.now(), index=True),
    )
    op.create_index("ix_behavior_events_type", "account_behavior_events", ["event_type"])
    op.create_index("ix_behavior_events_detected", "account_behavior_events", ["detected_at"])


def downgrade() -> None:
    op.drop_table("account_behavior_events")
