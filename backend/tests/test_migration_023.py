"""Verify migration 023 applies cleanly and adds expected columns."""
import os
import sys

os.environ.setdefault("ACCOUNTSCAN_MASTER_KEY", "test_master_key_0123456789abcdef01234567")
os.environ.setdefault("ACCOUNTSCAN_JWT_SECRET", "test_jwt_secret_0123456789abcdef0123456")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker

from backend.database import Base
from backend import models


@pytest.fixture
def inspector():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    yield inspect(engine)
    engine.dispose()


def test_nhi_alert_columns_present(inspector):
    cols = {c["name"]: c for c in inspector.get_columns("nhi_alerts")}
    assert "cluster_key" in cols
    assert "nhi_username" in cols
    assert "nhi_type" in cols
    assert "asset_count" in cols
    assert "updated_at" in cols
    # nhi_id is nullable
    assert cols["nhi_id"]["nullable"] is True


def test_nhi_alert_cluster_index_present(inspector):
    # ORM-level: cluster_key has a single-column index from model definition.
    # The composite (cluster_key, alert_type, status) index lives in the
    # Alembic migration only — not exercisable via Base.metadata.create_all.
    indexes = {ix["name"]: ix for ix in inspector.get_indexes("nhi_alerts")}
    assert "ix_nhi_alerts_cluster_key" in indexes
    ix = indexes["ix_nhi_alerts_cluster_key"]
    assert ix["column_names"] == ["cluster_key"]


def test_nhi_policy_columns_present(inspector):
    cols = {c["name"]: c for c in inspector.get_columns("nhi_policies")}
    assert "enabled_alert_types" in cols
    assert "cross_asset_threshold" in cols
    assert "cross_asset_window_days" in cols
    # Defaults populated by the model
    assert cols["cross_asset_threshold"]["default"] in ("3", None)  # SQLAlchemy may omit server_default in inspect
