"""Add identity fusion tables.

Revision ID: 009
Revises: 008_category_parent
Create Date: 2026-03-29
"""

from alembic import op
import sqlalchemy as sa


revision = "009"
down_revision = "008_category_parent"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "human_identities",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("display_name", sa.String(128), nullable=True),
        sa.Column("email", sa.String(256), nullable=True),
        sa.Column("primary_asset_id", sa.Integer(), sa.ForeignKey("assets.id"), nullable=True),
        sa.Column("confidence", sa.Integer(), server_default="0", nullable=False),
        sa.Column("source", sa.String(16), server_default="auto", nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "identity_accounts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("identity_id", sa.Integer(), nullable=False),
        sa.Column("snapshot_id", sa.Integer(), nullable=False),
        sa.Column("asset_id", sa.Integer(), nullable=False),
        sa.Column("match_type", sa.String(16), nullable=False),
        sa.Column("match_confidence", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKey(["identity_id"], ["human_identities.id"], name="fk_identity_account_identity"),
        sa.ForeignKey(["snapshot_id"], ["account_snapshots.id"], name="fk_identity_account_snapshot"),
        sa.ForeignKey(["asset_id"], ["assets.id"], name="fk_identity_account_asset"),
        sa.UniqueConstraint("identity_id", "snapshot_id", name="uq_identity_snapshot"),
    )


def downgrade():
    op.drop_table("identity_accounts")
    op.drop_table("human_identities")
