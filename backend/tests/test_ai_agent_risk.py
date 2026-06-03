"""Tests for AI Agent risk scoring — 8 rules with threshold boundaries."""
import os
import sys
from datetime import datetime, timedelta

os.environ.setdefault("ACCOUNTSCAN_MASTER_KEY", "test_master_key_0123456789abcdef01234567")
os.environ.setdefault("ACCOUNTSCAN_JWT_SECRET", "test_jwt_secret_0123456789abcdef0123456")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from backend.services.ai_agent_scanner import score_risk


def _agent(**overrides):
    base = {
        "agent_name": "test-agent",
        "framework": "langchain",
        "model": None,
        "owner_team": "data-eng",
        "owner_user": "alice",
        "api_key_fingerprint": "sha256:abc",
        "capabilities": {"filesystem": False, "network": False,
                         "code_exec": False, "tool_count": 0},
        "evidence": [],
        "last_invocation_at": None,
    }
    base.update(overrides)
    return base


class TestScoreRisk:
    def test_clean_agent_is_low(self):
        score, level, signals = score_risk(_agent(), all_agents=[])
        assert score == 0
        assert level == "low"
        assert signals == []

    def test_plaintext_key_in_config_is_critical(self):
        a = _agent(evidence=["plaintext_key"])
        score, level, signals = score_risk(a, all_agents=[])
        assert score == 40
        assert level == "medium"  # 40 is in [25, 50) under 25/50/75 thresholds

    def test_no_owner_adds_30(self):
        a = _agent(owner_user=None, owner_team=None)
        score, level, _ = score_risk(a, all_agents=[])
        assert score == 30
        assert level == "medium"  # 30 is in [25, 50)

    def test_code_exec_adds_25(self):
        a = _agent(capabilities={**_agent()["capabilities"], "code_exec": True})
        score, level, _ = score_risk(a, all_agents=[])
        assert score == 25
        assert level == "medium"

    def test_network_adds_15(self):
        a = _agent(capabilities={**_agent()["capabilities"], "network": True})
        score, level, _ = score_risk(a, all_agents=[])
        assert score == 15
        assert level == "low"  # < 25

    def test_filesystem_adds_10(self):
        a = _agent(capabilities={**_agent()["capabilities"], "filesystem": True})
        score, level, _ = score_risk(a, all_agents=[])
        assert score == 10
        assert level == "low"

    def test_autogen_framework_adds_15(self):
        a = _agent(framework="autogen")
        score, level, _ = score_risk(a, all_agents=[])
        assert score == 15

    def test_crewai_framework_adds_15(self):
        a = _agent(framework="crewai")
        score, level, _ = score_risk(a, all_agents=[])
        assert score == 15

    def test_dormant_30_days_adds_15(self):
        a = _agent(last_invocation_at=datetime.utcnow() - timedelta(days=31))
        score, level, _ = score_risk(a, all_agents=[])
        assert score == 15

    def test_dormant_under_30_days_no_signal(self):
        a = _agent(last_invocation_at=datetime.utcnow() - timedelta(days=5))
        score, level, _ = score_risk(a, all_agents=[])
        assert score == 0

    def test_duplicate_fingerprint_on_other_asset_adds_20(self):
        a = _agent(api_key_fingerprint="sha256:abc")
        other = {"asset_id": 99, "api_key_fingerprint": "sha256:abc"}
        score, level, _ = score_risk(a, all_agents=[other])
        assert score == 20

    def test_same_fingerprint_same_asset_does_not_count(self):
        a = _agent(asset_id=5, api_key_fingerprint="sha256:abc")
        other = {"asset_id": 5, "api_key_fingerprint": "sha256:abc"}
        score, _, _ = score_risk(a, all_agents=[other])
        assert score == 0

    def test_threshold_24_is_low_25_is_medium(self):
        # 25 = network(15) + filesystem(10) → 25, exactly medium
        a = _agent(capabilities={**_agent()["capabilities"],
                                  "network": True, "filesystem": True})
        score, level, _ = score_risk(a, all_agents=[])
        assert score == 25
        assert level == "medium"

    def test_threshold_49_is_medium_50_is_high(self):
        # 25 (code_exec) + 15 (network) + 10 (filesystem) = 50 → high
        a = _agent(capabilities={**_agent()["capabilities"],
                                  "network": True, "code_exec": True,
                                  "filesystem": True})
        score, level, _ = score_risk(a, all_agents=[])
        assert score == 50
        assert level == "high"

    def test_threshold_74_is_high_75_is_critical(self):
        # 40 (plaintext) + 30 (no owner) + 15 (autogen) = 85 → critical
        a = _agent(framework="autogen", owner_user=None, owner_team=None,
                   evidence=["plaintext_key"])
        score, level, _ = score_risk(a, all_agents=[])
        assert score == 85
        assert level == "critical"

    def test_signals_list_includes_evidence(self):
        a = _agent(evidence=["plaintext_key"])
        _, _, signals = score_risk(a, all_agents=[])
        assert any(s["signal"] == "plaintext_key" for s in signals)
        assert any(s["weight"] == 40 for s in signals)
