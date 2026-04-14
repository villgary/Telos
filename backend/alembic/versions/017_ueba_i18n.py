"""Add description_key and description_params to account_behavior_events."""
from alembic import op
import sqlalchemy as sa

revision = '017_ueba_i18n'
down_revision = '016_alert_i18n'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('account_behavior_events',
        sa.Column('description_key', sa.String(64), nullable=True))
    op.add_column('account_behavior_events',
        sa.Column('description_params', sa.JSON, nullable=True))


def downgrade() -> None:
    op.drop_column('account_behavior_events', 'description_params')
    op.drop_column('account_behavior_events', 'description_key')
