"""review_reminders — review_schedules + review_reports tables"""

from alembic import op
import sqlalchemy as sa


revision = '012_review_reminders'
down_revision = '011_pam_integration'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # review_schedules
    op.create_table(
        'review_schedules',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('name', sa.String(128), nullable=False),
        sa.Column('period', sa.String(16), nullable=False),  # monthly / quarterly
        sa.Column('day_of_month', sa.Integer(), nullable=True),  # 1-28
        sa.Column('alert_channels', sa.JSON, nullable=True),
        sa.Column('enabled', sa.Boolean, nullable=False, default=True),
        sa.Column('next_run_at', sa.DateTime, nullable=True),
        sa.Column('created_by', sa.Integer, sa.ForeignKey('users.id'), nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
    )

    # review_reports
    op.create_table(
        'review_reports',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('schedule_id', sa.Integer, sa.ForeignKey('review_schedules.id'), nullable=False),
        sa.Column('period', sa.String(16), nullable=False),
        sa.Column('period_start', sa.DateTime, nullable=False),
        sa.Column('period_end', sa.DateTime, nullable=False),
        sa.Column('status', sa.String(16), nullable=False, default='pending_review'),
        sa.Column('reviewed_by', sa.Integer, sa.ForeignKey('users.id'), nullable=True),
        sa.Column('reviewed_at', sa.DateTime, nullable=True),
        sa.Column('notes', sa.Text, nullable=True),
        sa.Column('content_summary', sa.JSON, nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table('review_reports')
    op.drop_table('review_schedules')
