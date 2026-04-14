"""Add compliance tables.

Revision ID: 007
Revises: 006_risk_profiles
Create Date: 2026-03-29
"""

from alembic import op
import sqlalchemy as sa


revision = "007"
down_revision = "006_risk_profiles"
branch_labels = None
depends_on = None


def upgrade():
    # compliance_frameworks
    op.create_table(
        "compliance_frameworks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("slug", sa.String(32), nullable=False),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("version", sa.String(16), nullable=False, server_default="1.0"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug", name="uq_compliance_slug"),
    )

    # compliance_checks
    op.create_table(
        "compliance_checks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("framework_id", sa.Integer(), nullable=False),
        sa.Column("check_key", sa.String(64), nullable=False),
        sa.Column("title", sa.String(256), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("severity", sa.String(16), nullable=False, server_default="medium"),
        sa.Column("applies_to", sa.String(128), nullable=False,
                  server_default="server,database,network,iot"),
        sa.Column("parameters", sa.JSON(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["framework_id"], ["compliance_frameworks.id"],
                               name="fk_compliance_check_framework"),
        sa.UniqueConstraint("framework_id", "check_key", name="uq_fw_check_key"),
    )

    # compliance_runs
    op.create_table(
        "compliance_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("framework_id", sa.Integer(), nullable=False),
        sa.Column("trigger_type", sa.String(16), nullable=False, server_default="manual"),
        sa.Column("status", sa.String(16), nullable=False, server_default="running"),
        sa.Column("total", sa.Integer(), server_default="0"),
        sa.Column("passed", sa.Integer(), server_default="0"),
        sa.Column("failed", sa.Integer(), server_default="0"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["framework_id"], ["compliance_frameworks.id"],
                               name="fk_compliance_run_framework"),
    )

    # compliance_results
    op.create_table(
        "compliance_results",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=False),
        sa.Column("framework_id", sa.Integer(), nullable=False),
        sa.Column("check_id", sa.Integer(), nullable=False),
        sa.Column("asset_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(8), nullable=False),
        sa.Column("evidence", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("evaluated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["run_id"], ["compliance_runs.id"],
                               name="fk_compliance_result_run"),
        sa.ForeignKeyConstraint(["framework_id"], ["compliance_frameworks.id"],
                               name="fk_compliance_result_framework"),
        sa.ForeignKeyConstraint(["check_id"], ["compliance_checks.id"],
                               name="fk_compliance_result_check"),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"],
                               name="fk_compliance_result_asset"),
        sa.UniqueConstraint("run_id", "check_id", name="uq_run_check"),
    )


def downgrade():
    op.drop_table("compliance_results")
    op.drop_table("compliance_runs")
    op.drop_table("compliance_checks")
    op.drop_table("compliance_frameworks")
