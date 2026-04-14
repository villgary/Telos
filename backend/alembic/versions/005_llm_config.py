"""Add llm_configs table.

Revision ID: 005
Revises: 004_asset_relationships
Create Date: 2026-03-29
"""

from alembic import op
import sqlalchemy as sa


revision = "005"
down_revision = "004_asset_relationships"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "llm_configs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("api_key_enc", sa.Text(), nullable=True),
        sa.Column("base_url", sa.String(256), nullable=True),
        sa.Column("model", sa.String(64), nullable=False, server_default="gpt-4o-mini"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade():
    op.drop_table("llm_configs")
