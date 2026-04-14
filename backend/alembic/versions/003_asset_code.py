"""Add asset_code to assets table.

Revision ID: 003
Revises: 002_asset_category_defs
Create Date: 2026-03-29
"""

from alembic import op
import sqlalchemy as sa


revision = "003"
down_revision = "002_asset_category_defs"
branch_labels = None
depends_on = None


def upgrade():
    # asset_code: VARCHAR(12), NOT NULL, UNIQUE
    # Backfill: ASM-{id:05d} for all existing rows
    op.add_column("assets", sa.Column("asset_code", sa.String(12), nullable=True))
    op.execute("UPDATE assets SET asset_code = 'ASM-' || printf('%05d', id)")
    op.alter_column("assets", "asset_code", nullable=False)
    op.create_index("ix_assets_asset_code", "assets", ["asset_code"], unique=True)


def downgrade():
    op.drop_index("ix_assets_asset_code", table_name="assets")
    op.drop_column("assets", "asset_code")
