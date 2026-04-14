"""Add asset_risk_profiles table.

Revision ID: 006
Revises: 005_llm_config
Create Date: 2026-03-29
"""

from alembic import op
import sqlalchemy as sa


revision = "006"
down_revision = "005_llm_config"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "asset_risk_profiles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("asset_id", sa.Integer(), nullable=False),
        sa.Column("risk_score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("risk_level", sa.String(16), nullable=False, server_default="'low'"),
        sa.Column("risk_factors", sa.JSON(), nullable=True),
        sa.Column("affected_children", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("propagation_path", sa.JSON(), nullable=True),
        sa.Column("computed_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("asset_id", name="uq_risk_asset_id"),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"], name="fk_risk_asset"),
    )


def downgrade():
    op.drop_table("asset_risk_profiles")
