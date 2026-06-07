"""credentials.api_token_enc — add the encrypted-token column for the new
api_token auth type.

Revision ID: 026_credential_api_token
Revises: 025_cloud_connections
Create Date: 2026-06-07
"""
import sqlalchemy as sa
from alembic import op


revision = "026_credential_api_token"
down_revision = "025_cloud_connections"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # SQLite can't ALTER TABLE ADD COLUMN with a foreign-key constraint on
    # the same table; the credentials table has no FK on this column, so
    # we could go direct — but using batch mode keeps the downgrade
    # path uniform across sqlite/postgres.
    with op.batch_alter_table("credentials") as batch:
        batch.add_column(sa.Column("api_token_enc", sa.Text, nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("credentials") as batch:
        batch.drop_column("api_token_enc")
