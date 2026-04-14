"""Add parent_id to asset_category_defs, change sub_type_kind to string.

Revision ID: 008
Revises: 007_compliance
Create Date: 2026-03-29
"""

from alembic import op
import sqlalchemy as sa


revision = "008"
down_revision = "007_compliance"
branch_labels = None
depends_on = None


def upgrade():
    # Add parent_id column (nullable FK to self)
    op.add_column(
        "asset_category_defs",
        sa.Column("parent_id", sa.Integer(), sa.ForeignKey("asset_category_defs.id"), nullable=True),
    )
    # sub_type_kind was stored as string in SQLite even as Enum column;
    # no type change needed — just ensure it stays string
    op.alter_column("asset_category_defs", "sub_type_kind", existing_type=sa.String(64), nullable=False)


def downgrade():
    op.drop_column("asset_category_defs", "parent_id")
