"""Add i18n keys to alerts table for translated titles/messages."""
from alembic import op
import sqlalchemy as sa

revision = '016_alert_i18n'
down_revision = '015_security_policies'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('alerts', sa.Column('title_key', sa.String(64), nullable=True))
    op.add_column('alerts', sa.Column('title_params', sa.JSON, nullable=True))
    op.add_column('alerts', sa.Column('message_key', sa.String(64), nullable=True))
    op.add_column('alerts', sa.Column('message_params', sa.JSON, nullable=True))


def downgrade() -> None:
    op.drop_column('alerts', 'message_params')
    op.drop_column('alerts', 'message_key')
    op.drop_column('alerts', 'title_params')
    op.drop_column('alerts', 'title_key')
