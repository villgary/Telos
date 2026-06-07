"""Add parent_id to asset_category_defs, change sub_type_kind to string.

Revision ID: 008
Revises: 007_compliance
Create Date: 2026-03-29
"""

from alembic import op
import sqlalchemy as sa


revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade():
    # Add parent_id column (nullable FK to self). SQLite can't ALTER TABLE
    # to add a column with a foreign-key definition — use batch mode.
    # Name the FK explicitly: batch mode on SQLite chokes on unnamed
    # constraints during the table-copy-and-move dance.
    with op.batch_alter_table("asset_category_defs") as batch:
        batch.add_column(
            sa.Column("parent_id", sa.Integer(), nullable=True),
        )
        batch.create_foreign_key(
            "fk_asset_category_defs_parent",
            "asset_category_defs",
            ["parent_id"], ["id"],
        )
    # sub_type_kind was stored as string in SQLite even as Enum column;
    # no type change needed — leave it alone (no alter_column call).


def downgrade():
    # SQLite can't drop a column with a foreign-key definition via plain
    # ALTER TABLE — use batch mode.
    with op.batch_alter_table("asset_category_defs") as batch:
        batch.drop_column("parent_id")
