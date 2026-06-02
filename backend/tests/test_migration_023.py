"""Verify migration 023 applies cleanly and adds expected columns."""
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
    """Per-test file-based sqlite DB; alembic and inspect see the same file."""
    return str(tmp_path / "migration.db")


def _reload_backend_db(db_url):
    """Point backend.database at a fresh URL by reimporting it."""
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


def _build_pre_023_schema(db_path):
    """Create the pre-023 schema via ORM metadata, then drop 023's additions
    so the migration has something to add back."""
    from sqlalchemy import create_engine, inspect, text

    engine = create_engine(f"sqlite:///{db_path}")
    from backend.database import Base
    from backend import models  # noqa: F401 — register models

    Base.metadata.create_all(bind=engine)

    # Drop the 023 additions so upgrade() has work to do. Index must be dropped
    # before its column, and the nhi_id nullability change is a no-op here
    # (SQLite can't toggle NOT NULL via ALTER, but the migration's batch mode
    # still runs and the test only verifies the columns/index end up correct).
    with engine.begin() as conn:
        conn.execute(text("DROP INDEX IF EXISTS ix_nhi_alerts_cluster_alert_type_status"))
        for col in ("cluster_key", "nhi_username", "nhi_type", "asset_count", "updated_at"):
            conn.execute(text(f"ALTER TABLE nhi_alerts DROP COLUMN {col}"))
        for col in ("enabled_alert_types", "cross_asset_threshold", "cross_asset_window_days"):
            conn.execute(text(f"ALTER TABLE nhi_policies DROP COLUMN {col}"))
    return engine


def test_migration_023_upgrade_then_downgrade(db_path, alembic_cfg):
    """Apply migration 023 on a pre-023 schema and verify it adds the expected
    columns and index, then downgrade and verify they are gone."""
    from alembic import command
    from sqlalchemy import inspect

    _reload_backend_db(f"sqlite:///{db_path}")
    _build_pre_023_schema(db_path)

    # Apply 023 on top of the pre-023 schema. We stamp at 022 first so alembic
    # only runs the 023 migration.
    command.stamp(alembic_cfg, "022")
    command.upgrade(alembic_cfg, "023_nhi_alerts_enhancement")

    from sqlalchemy import create_engine as _create_engine
    engine = _create_engine(f"sqlite:///{db_path}")
    insp = inspect(engine)

    cols = {c["name"] for c in insp.get_columns("nhi_alerts")}
    for added in ("cluster_key", "nhi_username", "nhi_type", "asset_count", "updated_at"):
        assert added in cols, f"023 should add {added} to nhi_alerts"

    indexes = {ix["name"] for ix in insp.get_indexes("nhi_alerts")}
    assert "ix_nhi_alerts_cluster_alert_type_status" in indexes

    policy_cols = {c["name"] for c in insp.get_columns("nhi_policies")}
    for added in ("enabled_alert_types", "cross_asset_threshold", "cross_asset_window_days"):
        assert added in policy_cols, f"023 should add {added} to nhi_policies"

    # Downgrade should remove them
    command.downgrade(alembic_cfg, "022")
    insp2 = inspect(engine)
    cols2 = {c["name"] for c in insp2.get_columns("nhi_alerts")}
    for added in ("cluster_key", "nhi_username", "nhi_type", "asset_count", "updated_at"):
        assert added not in cols2, f"downgrade should drop {added} from nhi_alerts"

    indexes2 = {ix["name"] for ix in insp2.get_indexes("nhi_alerts")}
    assert "ix_nhi_alerts_cluster_alert_type_status" not in indexes2

    policy_cols2 = {c["name"] for c in insp2.get_columns("nhi_policies")}
    for added in ("enabled_alert_types", "cross_asset_threshold", "cross_asset_window_days"):
        assert added not in policy_cols2, f"downgrade should drop {added} from nhi_policies"
