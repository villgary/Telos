"""013_account_risk_score — account_risk_scores table"""

from alembic import op
import sqlalchemy as sa


revision = '013_account_risk_score'
down_revision = '012_review_reminders'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'account_risk_scores',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('snapshot_id', sa.Integer(), sa.ForeignKey('account_snapshots.id'), nullable=False, unique=True),
        sa.Column('risk_score', sa.Integer(), nullable=False, default=0),
        sa.Column('risk_level', sa.String(16), nullable=False, default='low'),
        sa.Column('risk_factors', sa.JSON, nullable=False, default=list),
        sa.Column('identity_id', sa.Integer, sa.ForeignKey('human_identities.id'), nullable=True),
        sa.Column('cross_asset_count', sa.Integer, nullable=False, default=0),
        sa.Column('computed_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table('account_risk_scores')
