"""Add asset_relationships table.

Supports hierarchical relationships between assets:
  hosts_vm / hosts_container / runs_service / network_peer / belongs_to

Revision ID: 004
Revises: 003_asset_code
Create Date: 2026-03-29
"""

from alembic import op
import sqlalchemy as sa


revision = "004"
down_revision = "003_asset_code"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "asset_relationships",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("parent_id", sa.Integer(), nullable=False),
        sa.Column("child_id", sa.Integer(), nullable=False),
        sa.Column(
            "relation_type",
            sa.String(32),
            nullable=False,
            comment="hosts_vm|hosts_container|runs_service|network_peer|belongs_to",
        ),
        sa.Column("description", sa.String(256), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["parent_id"], ["assets.id"]),
        sa.ForeignKeyConstraint(["child_id"], ["assets.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("parent_id", "child_id", name="uq_rel_parent_child"),
    )


def downgrade():
    op.drop_table("asset_relationships")
