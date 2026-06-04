"""Verify migration 024 creates the ai_agents table with the expected shape,
then downgrades cleanly."""
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
    return str(tmp_path / "migration_024.db")


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


def test_migration_024_upgrade_then_downgrade(db_path, alembic_cfg):
    """Apply migration 024 on a pre-024 schema, verify table+indexes, downgrade."""
    from alembic import command
    from sqlalchemy import create_engine, inspect

    _reload_backend_db(f"sqlite:///{db_path}")

    # Build pre-024 schema via ORM metadata, which will create everything
    # EXCEPT ai_agents (since the model is registered but no migration ran yet).
    from backend.database import Base
    from backend import models  # noqa: F401

    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(bind=engine)
    with engine.begin() as conn:
        conn.exec_driver_sql("DROP TABLE IF EXISTS ai_agents")

    # Stamp at 023 so alembic only runs 024
    command.stamp(alembic_cfg, "023_nhi_alerts_enhancement")
    command.upgrade(alembic_cfg, "024_ai_agents")

    insp = inspect(engine)
    tables = insp.get_table_names()
    assert "ai_agents" in tables, "024 should create ai_agents table"

    cols = {c["name"] for c in insp.get_columns("ai_agents")}
    expected = {
        "id", "agent_name", "framework", "model", "owner_team", "owner_user",
        "api_key_fingerprint", "api_key_location", "capabilities",
        "last_invocation_at", "last_seen_at", "discovered_at", "discovery_source",
        "asset_id", "nhi_identity_id", "risk_level", "risk_score", "risk_signals",
        "status", "notes", "created_at", "updated_at",
    }
    missing = expected - cols
    assert not missing, f"024 should add columns {missing} to ai_agents"

    indexes = {ix["name"] for ix in insp.get_indexes("ai_agents")}
    assert "ix_ai_agents_dedup" in indexes
    assert "ix_ai_agents_nhi" in indexes
    assert "ix_ai_agents_asset" in indexes
    assert "ix_ai_agents_fingerprint" in indexes

    # Downgrade should drop them
    command.downgrade(alembic_cfg, "023_nhi_alerts_enhancement")
    insp2 = inspect(engine)
    tables2 = insp2.get_table_names()
    assert "ai_agents" not in tables2, "downgrade should drop ai_agents"
