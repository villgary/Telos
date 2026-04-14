"""Add asset_category_defs table.

Revision ID: 002
Revises: 001
Create Date: 2026-03-28

"""
from alembic import op
import sqlalchemy as sa

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # subtypekind enum
    op.execute("""
        CREATE TYPE subtypekind AS ENUM ('none', 'os', 'database', 'network')
    """)

    # New table (must exist before adding FK in assets)
    op.create_table(
        "asset_category_defs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("slug", sa.String(32), nullable=False),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("description", sa.String(256), nullable=True),
        sa.Column("icon", sa.String(32), nullable=True),
        sa.Column("sub_type_kind", sa.Enum("none", "os", "database", "network", name="subtypekind", create_type=False), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )
    op.create_index("ix_asset_category_defs_id", "asset_category_defs", ["id"])
    op.create_index("ix_asset_category_defs_slug", "asset_category_defs", ["slug"], unique=True)

    # Add FK column to assets (nullable, can be backfilled later)
    op.add_column("assets", sa.Column("asset_category_def_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_assets_category_def",
        "assets", "asset_category_defs",
        ["asset_category_def_id"], ["id"],
    )

    # Seed default categories (raw SQL — dialect agnostic)
    op.execute("""
        INSERT INTO asset_category_defs (slug, name, description, icon, sub_type_kind, created_at)
        VALUES
            ('server',   '服务器', 'Linux / Windows 主机',   'CloudServerOutlined', 'os',       NOW()),
            ('database', '数据库', 'MySQL / PostgreSQL / Redis 等', 'DatabaseOutlined', 'database', NOW()),
            ('network',  '网络设备', '交换机 / 路由器',         'GlobalOutlined',      'network',  NOW())
    """)


def downgrade() -> None:
    op.drop_constraint("fk_assets_category_def", "assets", type_="foreignkey")
    op.drop_column("assets", "asset_category_def_id")
    op.drop_index("ix_asset_category_defs_slug", table_name="asset_category_defs")
    op.drop_index("ix_asset_category_defs_id", table_name="asset_category_defs")
    op.drop_table("asset_category_defs")
    op.execute("DROP TYPE IF EXISTS subtypekind")
