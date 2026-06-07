"""Verify migration 025 creates cloud_connections + cloud_connection_audit_log
and adds ai_agents.connection_id, then downgrades cleanly."""
import importlib
import os
import sys

os.environ.setdefault("ACCOUNTSCAN_MASTER_KEY", "test_master_key_0123456789abcdef01234567")
os.environ.setdefault("ACCOUNTSCAN_JWT_SECRET", "test_jwt_secret_0123456789abcdef0123456")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import pytest


@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "migration_025.db")


def _reload_backend_db(db_url):
    os.environ["DATABASE_URL"] = db_url
    for mod_name in list(sys.modules):
        if mod_name == "backend" or mod_name.startswith("backend."):
            del sys.modules[mod_name]
    return importlib.import_module("backend.database")


@pytest.fixture
def alembic_cfg(db_path):
    from alembic.config import Config
    cfg = Config(os.path.join(os.path.dirname(__file__), "..", "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
    return cfg


def test_migration_025_upgrade_then_downgrade(db_path, alembic_cfg):
    from alembic import command
    from sqlalchemy import create_engine, inspect

    _reload_backend_db(f"sqlite:///{db_path}")

    from backend.database import Base
    from backend import models  # noqa: F401

    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(bind=engine)
    # Build a pre-025 schema: drop the tables/columns that 025 introduces.
    # ai_agents keeps its pre-025 columns only; we drop and let migration
    # 024 re-create it (SQLite's ALTER TABLE DROP COLUMN can't remove a
    # column that still has a foreign-key definition in the same table).
    with engine.begin() as conn:
        conn.exec_driver_sql("DROP TABLE IF EXISTS cloud_connection_audit_log")
        conn.exec_driver_sql("DROP TABLE IF EXISTS cloud_connections")
        conn.exec_driver_sql("DROP TABLE IF EXISTS ai_agents")

    command.stamp(alembic_cfg, "023_nhi_alerts_enhancement")
    command.upgrade(alembic_cfg, "024_ai_agents")
    command.stamp(alembic_cfg, "024_ai_agents")
    command.upgrade(alembic_cfg, "025_cloud_connections")

    insp = inspect(engine)
    tables = set(insp.get_table_names())
    assert "cloud_connections" in tables
    assert "cloud_connection_audit_log" in tables

    conn_cols = {c["name"] for c in insp.get_columns("cloud_connections")}
    expected_conn = {
        "id", "name", "provider", "encrypted_api_key", "api_key_fingerprint",
        "last_sync_at", "last_sync_started_at", "last_sync_status", "last_sync_error",
        "created_by_user_id", "created_at", "updated_at",
    }
    assert not (expected_conn - conn_cols), f"missing columns: {expected_conn - conn_cols}"

    audit_cols = {c["name"] for c in insp.get_columns("cloud_connection_audit_log")}
    expected_audit = {
        "id", "connection_id", "actor_user_id", "action", "status",
        "before", "after", "note", "created_at",
    }
    assert not (expected_audit - audit_cols), f"missing columns: {expected_audit - audit_cols}"

    ai_cols = {c["name"] for c in insp.get_columns("ai_agents")}
    assert "connection_id" in ai_cols

    fk_names = {fk["name"] for fk in insp.get_foreign_keys("ai_agents")}
    assert "fk_ai_agents_connection_id" in fk_names

    conn_indexes = {ix["name"] for ix in insp.get_indexes("cloud_connections")}
    assert "ix_cloud_connections_provider" in conn_indexes
    assert "ix_cloud_connections_fingerprint" in conn_indexes

    audit_indexes = {ix["name"] for ix in insp.get_indexes("cloud_connection_audit_log")}
    assert "ix_cloud_audit_connection" in audit_indexes
    assert "ix_cloud_audit_actor" in audit_indexes
    assert "ix_cloud_audit_created" in audit_indexes

    ai_indexes = {ix["name"] for ix in insp.get_indexes("ai_agents")}
    assert "ix_ai_agents_connection" in ai_indexes

    command.downgrade(alembic_cfg, "024_ai_agents")
    insp2 = inspect(engine)
    tables2 = set(insp2.get_table_names())
    assert "cloud_connections" not in tables2
    assert "cloud_connection_audit_log" not in tables2
    assert "connection_id" not in {c["name"] for c in insp2.get_columns("ai_agents")}
    # FK on connection_id should be gone
    fk_names_after = {fk["name"] for fk in insp2.get_foreign_keys("ai_agents")}
    assert "fk_ai_agents_connection_id" not in fk_names_after
