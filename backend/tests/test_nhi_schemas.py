"""Tests for backend.schemas.nhi validation rules."""
import os
import sys
from datetime import datetime

os.environ.setdefault("ACCOUNTSCAN_MASTER_KEY", "test_master_key_0123456789abcdef01234567")
os.environ.setdefault("ACCOUNTSCAN_JWT_SECRET", "test_jwt_secret_0123456789abcdef0123456")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import pytest
from pydantic import ValidationError

from backend.schemas.nhi import (
    NHIAlertResponse,
    NHIPolicyCreate,
    NHIPolicyUpdate,
)


class TestNHIAlertResponse:
    def test_cluster_fields_optional(self):
        a = NHIAlertResponse(
            id=1, nhi_id=None, cluster_key="service:deploy", nhi_username="deploy",
            nhi_type="service", asset_count=3, alert_type="cross_asset_spread",
            level="warning", title="x", message="y", is_read=False, status="new",
            resolved_at=None, created_at=datetime(2026, 6, 1), updated_at=datetime(2026, 6, 1),
        )
        assert a.cluster_key == "service:deploy"
        assert a.nhi_id is None
        assert a.asset_count == 3

    def test_legacy_alert_no_cluster_fields(self):
        a = NHIAlertResponse(
            id=2, nhi_id=42, cluster_key=None, nhi_username=None, nhi_type=None,
            asset_count=None, alert_type="risk_alert", level="critical", title="x",
            message="y", is_read=False, status="new", resolved_at=None,
            created_at=datetime(2026, 6, 1), updated_at=datetime(2026, 6, 1),
        )
        assert a.nhi_id == 42
        assert a.cluster_key is None


class TestNHIPolicyCreate:
    def _base(self, **overrides):
        defaults = {
            "name": "default",
            "enabled_alert_types": ["nopasswd_sudo", "cross_asset_spread"],
            "cross_asset_threshold": 3,
            "cross_asset_window_days": 7,
        }
        defaults.update(overrides)
        return NHIPolicyCreate(**defaults)

    def test_minimal_create(self):
        p = self._base()
        assert p.cross_asset_threshold == 3
        assert "nopasswd_sudo" in p.enabled_alert_types

    def test_threshold_too_low_rejected(self):
        with pytest.raises(ValidationError):
            self._base(cross_asset_threshold=1)

    def test_threshold_too_high_rejected(self):
        with pytest.raises(ValidationError):
            self._base(cross_asset_threshold=101)

    def test_window_too_low_rejected(self):
        with pytest.raises(ValidationError):
            self._base(cross_asset_window_days=0)

    def test_window_too_high_rejected(self):
        with pytest.raises(ValidationError):
            self._base(cross_asset_window_days=400)

    def test_unknown_alert_type_rejected(self):
        with pytest.raises(ValidationError):
            self._base(enabled_alert_types=["nopasswd_sudo", "made_up_type"])

    def test_empty_alert_types_allowed(self):
        p = self._base(enabled_alert_types=[])
        assert p.enabled_alert_types == []


class TestNHIPolicyUpdate:
    def test_partial_update(self):
        u = NHIPolicyUpdate(cross_asset_threshold=5)
        assert u.cross_asset_threshold == 5
        assert u.cross_asset_window_days is None
        assert u.enabled_alert_types is None

    def test_partial_update_validates(self):
        with pytest.raises(ValidationError):
            NHIPolicyUpdate(cross_asset_threshold=0)
