"""
Tests for backend.services.diff_engine (summary counter accuracy).
"""

import pytest
import sys
import os
from unittest.mock import MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

os.environ.setdefault("ACCOUNTSCAN_MASTER_KEY", "test_master_key_0123456789abcdef01234567")
os.environ.setdefault("ACCOUNTSCAN_JWT_SECRET", "test_jwt_secret_0123456789abcdef0123456")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("JWT_EXPIRE_MINUTES", "15")
os.environ.setdefault("REFRESH_TOKEN_EXPIRE_DAYS", "7")

for mod in list(sys.modules):
    if mod.startswith("backend"):
        del sys.modules[mod]

from backend import models
from backend.services import diff_engine
from backend.models import DiffType, RiskLevel


def make_snap(uid_sid, username, is_admin=False,
              account_status="active", shell="/bin/bash"):
    """构造一个 mock AccountSnapshot。"""
    snap = MagicMock(spec=models.AccountSnapshot)
    snap.uid_sid = uid_sid
    snap.username = username
    snap.is_admin = is_admin
    snap.account_status = account_status
    snap.shell = shell
    return snap


class TestComputeDiffSummary:
    """summary 计数器准确性测试"""

    def test_no_snapshots(self):
        items, summary = diff_engine.compute_diff([], [])
        assert items == []
        assert summary["added"] == 0
        assert summary["removed"] == 0
        assert summary["escalated"] == 0
        assert summary["deactivated"] == 0
        assert summary["modified"] == 0

    def test_added_account(self):
        snap_b = make_snap("uid1", "alice")
        items, summary = diff_engine.compute_diff([], [snap_b])
        assert summary["added"] == 1
        assert summary["removed"] == 0
        assert summary["escalated"] == 0
        assert summary["modified"] == 0

    def test_removed_account(self):
        snap_a = make_snap("uid1", "alice")
        items, summary = diff_engine.compute_diff([snap_a], [])
        assert summary["removed"] == 1
        assert summary["added"] == 0

    def test_escalated_account(self):
        # 普通用户 -> 管理员
        snap_a = make_snap("uid1", "alice", is_admin=False)
        snap_b = make_snap("uid1", "alice", is_admin=True)
        items, summary = diff_engine.compute_diff([snap_a], [snap_b])
        assert summary["escalated"] == 1
        assert summary["modified"] == 0  # 不应被计入 modified

    def test_deactivated_account(self):
        # 管理员 -> 普通用户
        snap_a = make_snap("uid1", "alice", is_admin=True)
        snap_b = make_snap("uid1", "alice", is_admin=False)
        items, summary = diff_engine.compute_diff([snap_a], [snap_b])
        assert summary["deactivated"] == 1
        assert summary["modified"] == 0

    def test_account_status_change_only(self):
        """account_status 变化不应重复计入 modified"""
        snap_a = make_snap("uid1", "alice", is_admin=False, account_status="active")
        snap_b = make_snap("uid1", "alice", is_admin=False, account_status="locked")
        items, summary = diff_engine.compute_diff([snap_a], [snap_b])
        assert summary["modified"] == 1
        assert summary["escalated"] == 0
        assert summary["deactivated"] == 0

    def test_shell_change_only(self):
        """shell 变化应正确计入 modified"""
        snap_a = make_snap("uid1", "alice", shell="/bin/bash")
        snap_b = make_snap("uid1", "alice", shell="/bin/sh")
        items, summary = diff_engine.compute_diff([snap_a], [snap_b])
        assert summary["modified"] == 1

    def test_no_double_counting_is_admin_then_status(self):
        """
        is_admin 变化 + account_status 变化同账号，只应记 1 次。
        之前有 bug：status 变化重复累加 modified。
        """
        snap_a = make_snap("uid1", "alice", is_admin=False, account_status="active")
        snap_b = make_snap("uid1", "alice", is_admin=True, account_status="locked")
        items, summary = diff_engine.compute_diff([snap_a], [snap_b])
        assert summary["escalated"] == 1
        assert summary["modified"] == 0  # 不应重复计数

    def test_no_double_counting_is_admin_then_shell(self):
        snap_a = make_snap("uid1", "alice", is_admin=True, shell="/bin/bash")
        snap_b = make_snap("uid1", "alice", is_admin=False, shell="/bin/sh")
        items, summary = diff_engine.compute_diff([snap_a], [snap_b])
        assert summary["deactivated"] == 1
        assert summary["modified"] == 0

    def test_no_change_no_item(self):
        """无变化则不产生 DiffItem"""
        snap_a = make_snap("uid1", "alice")
        snap_b = make_snap("uid1", "alice")
        items, _ = diff_engine.compute_diff([snap_a], [snap_b])
        assert items == []

    def test_mixed_changes(self):
        """混合场景"""
        snap_a = [
            make_snap("uid1", "alice", is_admin=False),
            make_snap("uid2", "bob", account_status="active"),
        ]
        snap_b = [
            make_snap("uid1", "alice", is_admin=True),    # escalated
            make_snap("uid2", "bob", account_status="locked"),  # modified
            make_snap("uid3", "carol"),                   # added
        ]
        items, summary = diff_engine.compute_diff(snap_a, snap_b)
        assert summary["escalated"] == 1
        assert summary["modified"] == 1
        assert summary["added"] == 1
        assert summary["removed"] == 0


class TestComputeDiffItems:
    """DiffItem 内容正确性测试"""

    def test_removed_item_has_correct_fields(self):
        snap_a = make_snap("uid1", "alice")
        items, _ = diff_engine.compute_diff([snap_a], [])
        assert len(items) == 1
        item = items[0]
        assert item.diff_type == DiffType.removed
        assert item.risk_level == RiskLevel.warning
        assert item.username == "alice"
        assert item.field_changes == {"status": ("present", "absent")}

    def test_added_item_risk_is_critical(self):
        snap_b = make_snap("uid1", "newuser", is_admin=True)
        items, _ = diff_engine.compute_diff([], [snap_b])
        assert items[0].risk_level == RiskLevel.critical

    def test_escalated_item_risk_is_critical(self):
        snap_a = make_snap("uid1", "alice", is_admin=False)
        snap_b = make_snap("uid1", "alice", is_admin=True)
        items, _ = diff_engine.compute_diff([snap_a], [snap_b])
        assert items[0].risk_level == RiskLevel.critical
