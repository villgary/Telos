"""snapshot_owner — add owner fields to account_snapshots

Revision ID: 022_snapshot_owner
Revises: 021_nhi_module
"""
from alembic import op
import sqlalchemy as sa


revision = "022_snapshot_owner"
down_revision = "021_nhi_module"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "account_snapshots",
        sa.Column("owner_identity_id", sa.Integer(), sa.ForeignKey("human_identities.id"), nullable=True),
    )
    op.add_column(
        "account_snapshots",
        sa.Column("owner_email", sa.String(256), nullable=True),
    )
    op.add_column(
        "account_snapshots",
        sa.Column("owner_name", sa.String(128), nullable=True),
    )
    # 告警路由到归属人
    op.add_column(
        "alerts",
        sa.Column("target_identity_id", sa.Integer(), sa.ForeignKey("human_identities.id"), nullable=True),
    )


def downgrade():
    op.drop_column("alerts", "target_identity_id")
    op.drop_column("account_snapshots", "owner_name")
    op.drop_column("account_snapshots", "owner_email")
    op.drop_column("account_snapshots", "owner_identity_id")
