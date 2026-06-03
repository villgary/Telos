"""ai_agents table — first-class AI Agent identity (peer to NHI)

Revision ID: 024_ai_agents
Revises: 023_nhi_alerts_enhancement
Create Date: 2026-06-03
"""
import sqlalchemy as sa
from alembic import op


revision = "024_ai_agents"
down_revision = "023_nhi_alerts_enhancement"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_agents",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("agent_name", sa.String(128), nullable=False),
        sa.Column("framework", sa.String(32), nullable=False, server_default="unknown"),
        sa.Column("model", sa.String(64), nullable=True),
        sa.Column("owner_team", sa.String(64), nullable=True),
        sa.Column("owner_user", sa.String(64), nullable=True),
        sa.Column("api_key_fingerprint", sa.String(16), nullable=True),
        sa.Column("api_key_location", sa.String(256), nullable=True),
        sa.Column("capabilities", sa.JSON, nullable=True),
        sa.Column("last_invocation_at", sa.DateTime, nullable=True),
        sa.Column("last_seen_at", sa.DateTime, nullable=False),
        sa.Column("discovered_at", sa.DateTime, nullable=False),
        sa.Column("discovery_source", sa.String(16), nullable=False, server_default="ssh_scan"),
        sa.Column("asset_id", sa.Integer, sa.ForeignKey("assets.id"), nullable=True),
        sa.Column("nhi_identity_id", sa.Integer, sa.ForeignKey("nhi_identities.id"), nullable=True),
        sa.Column("risk_level", sa.String(16), nullable=False, server_default="low"),
        sa.Column("risk_score", sa.Integer, nullable=False, server_default="0"),
        sa.Column("risk_signals", sa.JSON, nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="active"),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=True, onupdate=sa.func.now()),
    )
    op.create_index("ix_ai_agents_dedup", "ai_agents",
                    ["framework", "agent_name", "owner_team", "asset_id"],
                    unique=True)
    op.create_index("ix_ai_agents_nhi", "ai_agents", ["nhi_identity_id"])
    op.create_index("ix_ai_agents_asset", "ai_agents", ["asset_id"])
    op.create_index("ix_ai_agents_fingerprint", "ai_agents", ["api_key_fingerprint"])


def downgrade() -> None:
    op.drop_index("ix_ai_agents_fingerprint", table_name="ai_agents")
    op.drop_index("ix_ai_agents_asset", table_name="ai_agents")
    op.drop_index("ix_ai_agents_nhi", table_name="ai_agents")
    op.drop_index("ix_ai_agents_dedup", table_name="ai_agents")
    op.drop_table("ai_agents")
