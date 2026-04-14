"""Add kb_entries table for admin-managed KB entries."""
from alembic import op
import sqlalchemy as sa

revision = '018_kb_entries'
down_revision = '017_ueba_i18n'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'kb_entries',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('entry_type', sa.String(16), nullable=False),
        sa.Column('title', sa.String(256), nullable=False),
        sa.Column('title_en', sa.String(256), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('description_en', sa.Text(), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.Index('ix_kb_entries_entry_type', 'entry_type'),
    )


def downgrade() -> None:
    op.drop_table('kb_entries')
