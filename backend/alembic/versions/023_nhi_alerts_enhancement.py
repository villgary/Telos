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
    with op.batch_alter_table("nhi_alerts") as batch:
        batch.alter_column("nhi_id", existing_type=sa.Integer(), nullable=True)
        batch.add_column(sa.Column("cluster_key", sa.String(128), nullable=True))
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
        batch.alter_column("nhi_id", existing_type=sa.Integer(), nullable=False)
