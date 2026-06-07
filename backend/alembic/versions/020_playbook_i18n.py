"""Add i18n keys to review_playbooks

Revision ID: 020_playbook_i18n
Revises: 019_identity_threat
Create Date: 2026-04-07
"""
import sqlalchemy as sa
from alembic import op

revision = '020_playbook_i18n'
down_revision = '019_identity_threat'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # The review_playbooks table is defined in backend/models/alerts.py
    # but no prior migration ever creates it. Create it here so this
    # migration is self-healing on a fresh DB.
    op.create_table(
        'review_playbooks',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(128), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('name_key', sa.String(128), nullable=True),
        sa.Column('description_key', sa.String(128), nullable=True),
        sa.Column('trigger_type', sa.String(32), nullable=False),
        sa.Column('trigger_filter', sa.JSON, default=dict),
        sa.Column('steps', sa.JSON, default=list),
        sa.Column('approval_required', sa.Boolean, default=True),
        sa.Column('enabled', sa.Boolean, default=True),
        sa.Column('created_by', sa.Integer, sa.ForeignKey('users.id'), nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    # These lines were here originally — the create_table above is new.
    # If the table already existed in some env (e.g. one where a
    # pre-020 migration did create it), the original lines below will
    # be no-ops; on a fresh DB they ensure the new i18n columns are
    # present from the start.
    conn = op.get_bind()
    has_name_key = conn.execute(
        sa.text("PRAGMA table_info(review_playbooks)")
    ).fetchall()
    has_name_key = any(row[1] == 'name_key' for row in has_name_key)
    if not has_name_key:
        op.add_column('review_playbooks', sa.Column('name_key', sa.String(128), nullable=True))
        op.add_column('review_playbooks', sa.Column('description_key', sa.String(128), nullable=True))


def downgrade() -> None:
    # Drop the table entirely — it didn't exist before this migration
    # was self-healed.
    op.drop_table('review_playbooks')
