"""Identity Threat Analysis tables

Revision ID: 019_identity_threat
Revises: 018_kb_entries
Create Date: 2026-04-07
"""
import sqlalchemy as sa
from alembic import op

revision = '019_identity_threat'
down_revision = '018_kb_entries'
branch_labels = None
depends_on = None


def upgrade():
    # identity_threat_analyses
    op.create_table(
        'identity_threat_analyses',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('analysis_type', sa.String(32), nullable=False),
        sa.Column('scope', sa.String(32), nullable=False),
        sa.Column('scope_id', sa.Integer(), nullable=True),
        sa.Column('semiotic_score', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('causal_score', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('ontological_score', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('cognitive_score', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('anthropological_score', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('overall_score', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('overall_level', sa.String(16), nullable=False),
        sa.Column('semiotic_signals', sa.JSON(), nullable=True),
        sa.Column('causal_signals', sa.JSON(), nullable=True),
        sa.Column('ontological_signals', sa.JSON(), nullable=True),
        sa.Column('cognitive_signals', sa.JSON(), nullable=True),
        sa.Column('anthropological_signals', sa.JSON(), nullable=True),
        sa.Column('threat_graph', sa.JSON(), nullable=True),
        sa.Column('llm_report', sa.Text(), nullable=True),
        sa.Column('analyzed_count', sa.Integer(), server_default='0'),
        sa.Column('duration_ms', sa.Integer(), nullable=True),
        sa.Column('model_used', sa.String(64), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
    )

    # threat_account_signals
    op.create_table(
        'threat_account_signals',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('analysis_id', sa.Integer(), nullable=False),
        sa.Column('snapshot_id', sa.Integer(), nullable=True),
        sa.Column('username', sa.String(128), nullable=False),
        sa.Column('asset_id', sa.Integer(), nullable=False),
        sa.Column('asset_code', sa.String(32), nullable=True),
        sa.Column('semiotic_flags', sa.JSON(), nullable=True),
        sa.Column('causal_flags', sa.JSON(), nullable=True),
        sa.Column('ontological_flags', sa.JSON(), nullable=True),
        sa.Column('cognitive_flags', sa.JSON(), nullable=True),
        sa.Column('anthropological_flags', sa.JSON(), nullable=True),
        sa.Column('account_score', sa.Integer(), server_default='0'),
        sa.Column('account_level', sa.String(16), server_default="'low'"),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['analysis_id'], ['identity_threat_analyses.id']),
        sa.ForeignKeyConstraint(['snapshot_id'], ['account_snapshots.id']),
    )

    # Indexes
    op.create_index('ix_identity_threat_analyses_created_at', 'identity_threat_analyses', ['created_at'])
    op.create_index('ix_identity_threat_analyses_scope', 'identity_threat_analyses', ['scope'])
    op.create_index('ix_threat_account_signals_analysis_id', 'threat_account_signals', ['analysis_id'])
    op.create_index('ix_threat_account_signals_username', 'threat_account_signals', ['username'])
    op.create_index('ix_threat_account_signals_account_score', 'threat_account_signals', ['account_score'])


def downgrade():
    op.drop_index('ix_threat_account_signals_account_score')
    op.drop_index('ix_threat_account_signals_username')
    op.drop_index('ix_threat_account_signals_analysis_id')
    op.drop_index('ix_identity_threat_analyses_scope')
    op.drop_index('ix_identity_threat_analyses_created_at')
    op.drop_table('threat_account_signals')
    op.drop_table('identity_threat_analyses')
