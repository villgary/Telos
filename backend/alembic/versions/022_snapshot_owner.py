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
    # FK-bearing columns need batch mode on SQLite (ALTER TABLE can't add
    # a column with a foreign-key definition in the SQLite dialect).
    # Plain non-FK columns can be added directly.
    # The FK is added as a separately named constraint because batch mode
    # on SQLite chokes on unnamed constraints during the table-copy dance.
    with op.batch_alter_table("account_snapshots") as batch:
        batch.add_column(sa.Column("owner_identity_id", sa.Integer(), nullable=True))
        batch.create_foreign_key(
            "fk_account_snapshots_owner_identity",
            "human_identities",
            ["owner_identity_id"], ["id"],
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
    with op.batch_alter_table("alerts") as batch:
        batch.add_column(sa.Column("target_identity_id", sa.Integer(), nullable=True))
        batch.create_foreign_key(
            "fk_alerts_target_identity",
            "human_identities",
            ["target_identity_id"], ["id"],
        )


def downgrade():
    with op.batch_alter_table("alerts") as batch:
        batch.drop_column("target_identity_id")
    op.drop_column("account_snapshots", "owner_name")
    op.drop_column("account_snapshots", "owner_email")
    with op.batch_alter_table("account_snapshots") as batch:
        batch.drop_column("owner_identity_id")
