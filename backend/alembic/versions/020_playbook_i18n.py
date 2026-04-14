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
    op.add_column('review_playbooks', sa.Column('name_key', sa.String(128), nullable=True))
    op.add_column('review_playbooks', sa.Column('description_key', sa.String(128), nullable=True))


def downgrade() -> None:
    op.drop_column('review_playbooks', 'description_key')
    op.drop_column('review_playbooks', 'name_key')
