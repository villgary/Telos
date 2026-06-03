"""Tests for AI Agent signal parser — turns probe output into candidate agents."""
import os
import sys

os.environ.setdefault("ACCOUNTSCAN_MASTER_KEY", "test_master_key_0123456789abcdef01234567")
os.environ.setdefault("ACCOUNTSCAN_JWT_SECRET", "test_jwt_secret_0123456789abcdef0123456")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from backend.services.ai_agent_scanner import parse_signals


def _signal_block(config_files="", env_vars="", processes="", framework_paths="", package_json=""):
    return {
        "ai_agent_signals": {
            "config_files":    [c for c in config_files.split("\n") if c],
            "env_vars":        [e for e in env_vars.split("\n") if e],
            "processes":       [p for p in processes.split("\n") if p],
            "framework_paths": [f for f in framework_paths.split("\n") if f],
            "package_json":    [p for p in package_json.split("\n") if p],
        }
    }


class TestParseSignals:
    def test_empty_signals_returns_empty_list(self):
        assert parse_signals({"ai_agent_signals": {}}) == []

    def test_none_signals_returns_empty_list(self):
        assert parse_signals({}) == []

    def test_env_var_with_anthropic_key_creates_anthropic_agent(self):
        raw = _signal_block(
            env_vars="ANTHROPIC_API_KEY|user|sha256:abc",
        )
        agents = parse_signals(raw)
        assert len(agents) == 1
        assert agents[0]["framework"] == "claude_code"
        assert agents[0]["api_key_fingerprint"] == "sha256:abc"
        assert agents[0]["api_key_location"] == "env:ANTHROPIC_API_KEY"

    def test_env_var_with_openai_key_creates_openai_agent(self):
        raw = _signal_block(env_vars="OPENAI_API_KEY|user|sha256:xyz")
        agents = parse_signals(raw)
        assert len(agents) == 1
        assert agents[0]["framework"] == "openai_assistant"
        assert agents[0]["model"] == "openai"

    def test_framework_path_detected(self):
        raw = _signal_block(
            framework_paths="/opt/app/venv/lib/python3.11/site-packages/langchain|langchain",
        )
        agents = parse_signals(raw)
        assert len(agents) == 1
        assert agents[0]["framework"] == "langchain"
        assert agents[0]["agent_name"] == "app-langchain"

    def test_process_with_langchain_creates_agent(self):
        raw = _signal_block(processes="langchain-server|3")
        agents = parse_signals(raw)
        assert len(agents) == 1
        assert agents[0]["framework"] == "langchain"

    def test_multiple_signals_dedupe_to_single_agent(self):
        """Same framework on one asset collapses to one agent."""
        raw = _signal_block(
            framework_paths="/opt/app/venv/.../langchain|langchain",
            processes="langchain-server|1",
        )
        agents = parse_signals(raw)
        assert len(agents) == 1
        assert agents[0]["framework"] == "langchain"

    def test_config_file_with_plaintext_key_is_critical_signal(self):
        raw = _signal_block(
            config_files="/home/alice/.config/anthropic/credentials.json",
        )
        agents = parse_signals(raw)
        assert len(agents) == 1
        assert "plaintext_key" in agents[0]["evidence"]

    def test_capabilities_from_signals(self):
        raw = _signal_block(
            env_vars="LANGCHAIN_TOOL_COUNT|user|5",
        )
        agents = parse_signals(raw)
        assert len(agents) == 1
        assert agents[0]["capabilities"]["tool_count"] == 5

    def test_unknown_signal_returns_empty(self):
        raw = _signal_block(
            config_files="/etc/some/random/file.json",
            processes="bash|1",
        )
        assert parse_signals(raw) == []
