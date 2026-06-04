"""cloud_connections + cloud_connection_audit_log tables, plus ai_agents.connection_id

Revision ID: 025_cloud_connections
Revises: 024_ai_agents
Create Date: 2026-06-04
"""
import sqlalchemy as sa
from alembic import op


revision = "025_cloud_connections"
down_revision = "024_ai_agents"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "cloud_connections",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("provider", sa.String(16), nullable=False),
        sa.Column("encrypted_api_key", sa.Text, nullable=False),
        sa.Column("api_key_fingerprint", sa.String(16), nullable=False),
        sa.Column("last_sync_at", sa.DateTime, nullable=True),
        sa.Column("last_sync_started_at", sa.DateTime, nullable=True),
        sa.Column("last_sync_status", sa.String(16), nullable=True),
        sa.Column("last_sync_error", sa.String(256), nullable=True),
        sa.Column("created_by_user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=True, onupdate=sa.func.now()),
        sa.UniqueConstraint("name", name="uq_cloud_connections_name"),
    )
    op.create_index("ix_cloud_connections_provider", "cloud_connections", ["provider"])
    op.create_index(
        "ix_cloud_connections_fingerprint", "cloud_connections", ["api_key_fingerprint"]
    )

    op.create_table(
        "cloud_connection_audit_log",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "connection_id",
            sa.Integer,
            sa.ForeignKey("cloud_connections.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("actor_user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("action", sa.String(32), nullable=False),
        sa.Column("status", sa.String(16), nullable=True),
        sa.Column("before", sa.JSON, nullable=True),
        sa.Column("after", sa.JSON, nullable=True),
        sa.Column("note", sa.String(256), nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_cloud_audit_connection", "cloud_connection_audit_log", ["connection_id"])
    op.create_index("ix_cloud_audit_actor", "cloud_connection_audit_log", ["actor_user_id"])
    op.create_index("ix_cloud_audit_created", "cloud_connection_audit_log", ["created_at"])

    op.add_column(
        "ai_agents",
        sa.Column(
            "connection_id",
            sa.Integer,
            sa.ForeignKey("cloud_connections.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_ai_agents_connection", "ai_agents", ["connection_id"])


def downgrade() -> None:
    op.drop_index("ix_ai_agents_connection", table_name="ai_agents")
    op.drop_column("ai_agents", "connection_id")
    op.drop_index("ix_cloud_audit_created", table_name="cloud_connection_audit_log")
    op.drop_index("ix_cloud_audit_actor", table_name="cloud_connection_audit_log")
    op.drop_index("ix_cloud_audit_connection", table_name="cloud_connection_audit_log")
    op.drop_table("cloud_connection_audit_log")
    op.drop_index("ix_cloud_connections_fingerprint", table_name="cloud_connections")
    op.drop_index("ix_cloud_connections_provider", table_name="cloud_connections")
    op.drop_table("cloud_connections")
