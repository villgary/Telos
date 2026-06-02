"""NHI alerts enhancement — cluster_key, i18n, NHIPolicy thresholds

Revision ID: 023_nhi_alerts_enhancement
Revises: 022_snapshot_owner
Create Date: 2026-06-01
"""
import sqlalchemy as sa
from alembic import op


revision = "023_nhi_alerts_enhancement"
down_revision = "022_snapshot_owner"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # NHIAlert: cluster-friendly + i18n refresh tracking
    # SQLite: nhi_id nullability change needs a table rebuild via batch mode.
    # The column adds are plain ALTER TABLE ADD COLUMN (always appended).
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == "sqlite"

    if is_sqlite:
        with op.batch_alter_table("nhi_alerts") as batch:
            batch.alter_column("nhi_id", existing_type=sa.Integer(), nullable=True)
        op.execute("ALTER TABLE nhi_alerts ADD COLUMN cluster_key VARCHAR(192)")
        op.execute("ALTER TABLE nhi_alerts ADD COLUMN nhi_username VARCHAR(128)")
        op.execute("ALTER TABLE nhi_alerts ADD COLUMN nhi_type VARCHAR(32)")
        op.execute("ALTER TABLE nhi_alerts ADD COLUMN asset_count INTEGER")
        op.execute("ALTER TABLE nhi_alerts ADD COLUMN updated_at DATETIME DEFAULT CURRENT_TIMESTAMP")
    else:
        with op.batch_alter_table("nhi_alerts") as batch:
            batch.alter_column("nhi_id", existing_type=sa.Integer(), nullable=True)
            batch.add_column(sa.Column("cluster_key", sa.String(192), nullable=True))
            batch.add_column(sa.Column("nhi_username", sa.String(128), nullable=True))
            batch.add_column(sa.Column("nhi_type", sa.String(32), nullable=True))
            batch.add_column(sa.Column("asset_count", sa.Integer(), nullable=True))
            batch.add_column(
                sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=True)
            )
    op.create_index(
        "ix_nhi_alerts_cluster_alert_type_status",
        "nhi_alerts",
        ["cluster_key", "alert_type", "status"],
        unique=False,
    )

    # NHIPolicy: per-policy rule fields
    with op.batch_alter_table("nhi_policies") as batch:
        batch.add_column(
            sa.Column(
                "enabled_alert_types",
                sa.JSON(),
                server_default='["privilege_escalation","nopasswd_sudo","credential_leak","cross_asset_spread"]',
                nullable=True,
            )
        )
        batch.add_column(sa.Column("cross_asset_threshold", sa.Integer(), server_default="3", nullable=True))
        batch.add_column(sa.Column("cross_asset_window_days", sa.Integer(), server_default="7", nullable=True))


def downgrade() -> None:
    op.drop_index("ix_nhi_alerts_cluster_alert_type_status", table_name="nhi_alerts")
    with op.batch_alter_table("nhi_policies") as batch:
        batch.drop_column("cross_asset_window_days")
        batch.drop_column("cross_asset_threshold")
        batch.drop_column("enabled_alert_types")
    with op.batch_alter_table("nhi_alerts") as batch:
        batch.drop_column("updated_at")
        batch.drop_column("asset_count")
        batch.drop_column("nhi_type")
        batch.drop_column("nhi_username")
        batch.drop_column("cluster_key")
        # NOTE: this downgrade will fail if any cluster alerts (nhi_id IS NULL) exist.
        # Operator must resolve/clean them first, or run: DELETE FROM nhi_alerts WHERE nhi_id IS NULL;
        batch.alter_column("nhi_id", existing_type=sa.Integer(), nullable=False)
