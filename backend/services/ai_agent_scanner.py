"""AI Agent scanner — probe parser, dedupe, risk scoring, AIAgent upsert.

Public API:
    fingerprint_api_key(key)            -> sha256[:16] prefix or None
    parse_signals(raw_info)             -> list of candidate AIAgent dicts
    score_risk(agent_dict, all_agents)  -> (score, level, signals)
    ingest(db, raw_info, asset_id)      -> list[AIAgent] (created or updated)
"""
from __future__ import annotations

import hashlib
import re
from typing import Optional


def fingerprint_api_key(key: Optional[str]) -> Optional[str]:
    """Return a 16-char sha256[:16] fingerprint prefixed with 'sha256:',
    or None for empty/None input. Never returns any portion of the key."""
    if not key:
        return None
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
    return f"sha256:{digest[:16]}"


# ── Signal parsing (Task 10) ────────────────────────────────────────────

_ENV_KEY_TO_FRAMEWORK = {
    "ANTHROPIC_API_KEY": ("claude_code", "claude"),
    "CLAUDE_API_KEY":    ("claude_code", "claude"),
    "OPENAI_API_KEY":    ("openai_assistant", "openai"),
    "OPENAI_ORG_ID":     ("openai_assistant", "openai"),
    "LANGCHAIN_API_KEY": ("langchain", None),
    "LANGCHAIN_TOOL_COUNT": (None, None),  # capability hint, not a key
    "COHERE_API_KEY":    ("custom", "cohere"),
    "GEMINI_API_KEY":    ("custom", "gemini"),
}

_FRAMEWORK_KEYWORDS = {
    "langchain": "langchain",
    "autogen":   "autogen",
    "crewai":    "crewai",
    "anthropic": "claude_code",
    "llamaindex":"llamaindex",
}

_PROCESS_FRAMEWORK = {
    "langchain": "langchain",
    "autogen":   "autogen",
    "crewai":    "crewai",
    "claude":    "claude_code",
    "gpt-":      "openai_assistant",
    "agent":     None,  # ambiguous — context-dependent
}

# Directories that are Python package infrastructure, not part of the project name.
_PYLIB_INFRA = {"lib", "venv", "site-packages", "dist-packages"}


def _extract_project_from_pylib_path(parts: list[str]) -> Optional[str]:
    """If *parts* is a Python lib path (e.g. /opt/app/venv/lib/python3.11/site-packages/..),
    return the project root directory name (e.g. 'app'). Return None if no project
    root is found or the path is not a Python lib path.
    """
    for marker in ("site-packages", "dist-packages"):
        if marker in parts:
            idx = parts.index(marker)
            i = idx - 1
            # Walk back past python3.X, lib, venv
            while i >= 0 and (parts[i] in _PYLIB_INFRA or parts[i].startswith("python")):
                i -= 1
            if i >= 0 and parts[i]:
                return parts[i]
            return None
    return None


def _infer_agent_name(framework: str, location: str) -> str:
    """Best-effort agent name from the location/path.

    For framework package paths like /opt/myapp/venv/.../site-packages/langchain,
    use the project root directory ('myapp') as the name prefix. Otherwise fall
    back to the last path component with common suffixes stripped.
    """
    if not location:
        return f"{framework}-agent"
    parts = location.rstrip("/").split("/")
    project = _extract_project_from_pylib_path(parts)
    if project:
        return f"{project}-{framework}"
    # Fallback: use last path component
    last = parts[-1] or location
    last = re.sub(r"\.(json|toml|yaml|yml)$", "", last)
    last = re.sub(r"^(credentials|config|settings)\.", "", last)
    return f"{framework}-{last}" if last else f"{framework}-agent"


def _parse_env_line(line: str) -> Optional[dict]:
    """'NAME|scope|fingerprint' -> {name, scope, fingerprint} or None."""
    parts = line.split("|")
    if len(parts) < 3:
        return None
    return {"name": parts[0].strip(), "scope": parts[1].strip(),
            "fingerprint": parts[2].strip()}


def _parse_process_line(line: str) -> Optional[dict]:
    """'name|count' -> {name, count} or None."""
    parts = line.split("|")
    if len(parts) < 2:
        return {"name": parts[0].strip(), "count": 1}
    return {"name": parts[0].strip(), "count": int(parts[1].strip())}


def _parse_path_line(line: str) -> Optional[dict]:
    """'path|framework' -> {path, framework} or None."""
    parts = line.split("|")
    if len(parts) < 2:
        return {"path": parts[0].strip(), "framework": "unknown"}
    return {"path": parts[0].strip(), "framework": parts[1].strip()}


def parse_signals(raw_info: dict) -> list[dict]:
    """Turn raw_info["ai_agent_signals"] into a list of candidate agent dicts.

    Each candidate is one agent per (framework, asset) — multiple signals for
    the same framework on the same asset collapse to a single candidate.
    """
    if not raw_info:
        return []
    signals = raw_info.get("ai_agent_signals") or {}
    if not signals:
        return []

    candidates: dict[str, dict] = {}  # key=framework, value=merged agent

    def _default_capabilities() -> dict:
        return {"filesystem": False, "network": False,
                "code_exec": False, "tool_count": 0}

    # ── env_vars ──────────────────────────────────────────────────────────
    for line in signals.get("env_vars") or []:
        env = _parse_env_line(line)
        if not env:
            continue
        # Tool count hint (not a key) — also indicates a langchain agent exists
        if env["name"] == "LANGCHAIN_TOOL_COUNT":
            tool_count = int(env["fingerprint"] or 0)
            if "langchain" not in candidates:
                candidates["langchain"] = {
                    "agent_name": _infer_agent_name("langchain", ""),
                    "framework": "langchain",
                    "model": None,
                    "api_key_fingerprint": None,
                    "api_key_location": "env:LANGCHAIN_TOOL_COUNT",
                    "evidence": ["env_capability"],
                    "capabilities": {"filesystem": False, "network": True,
                                     "code_exec": False, "tool_count": tool_count},
                }
            else:
                candidates["langchain"].setdefault("capabilities", {})["tool_count"] = tool_count
            continue
        if env["name"] not in _ENV_KEY_TO_FRAMEWORK:
            continue
        framework, model = _ENV_KEY_TO_FRAMEWORK[env["name"]]
        if framework is None:
            continue
        if framework not in candidates:
            candidates[framework] = {
                "agent_name": _infer_agent_name(framework, ""),
                "framework": framework,
                "model": model,
                "api_key_fingerprint": env["fingerprint"],
                "api_key_location": f"env:{env['name']}",
                "evidence": ["env_key"],
                "capabilities": {"filesystem": False, "network": True,
                                 "code_exec": False, "tool_count": 0},
            }
        else:
            # Reinforce existing
            candidates[framework]["api_key_fingerprint"] = (
                candidates[framework].get("api_key_fingerprint") or env["fingerprint"]
            )

    # ── config_files ──────────────────────────────────────────────────────
    for path in signals.get("config_files") or []:
        path_l = path.lower()
        for kw, framework in _FRAMEWORK_KEYWORDS.items():
            if kw in path_l:
                if framework not in candidates:
                    candidates[framework] = {
                        "agent_name": _infer_agent_name(framework, path),
                        "framework": framework,
                        "model": None,
                        "api_key_fingerprint": None,
                        "api_key_location": f"file:{path}",
                        "evidence": ["plaintext_key"],
                        "capabilities": {"filesystem": True, "network": False,
                                         "code_exec": False, "tool_count": 0},
                    }
                else:
                    candidates[framework].setdefault("evidence", []).append("plaintext_key")
                    candidates[framework]["capabilities"]["filesystem"] = True
                break

    # ── processes ─────────────────────────────────────────────────────────
    for line in signals.get("processes") or []:
        proc = _parse_process_line(line)
        if not proc:
            continue
        proc_l = proc["name"].lower()
        for kw, framework in _PROCESS_FRAMEWORK.items():
            if kw in proc_l and framework:
                if framework not in candidates:
                    candidates[framework] = {
                        "agent_name": _infer_agent_name(framework, proc["name"]),
                        "framework": framework,
                        "model": None,
                        "api_key_fingerprint": None,
                        "api_key_location": f"process:{proc['name']}",
                        "evidence": ["process"],
                        "capabilities": {"filesystem": False, "network": False,
                                         "code_exec": True, "tool_count": 0},
                    }
                else:
                    candidates[framework].setdefault("evidence", []).append("process")
                    candidates[framework]["capabilities"]["code_exec"] = True
                break

    # ── framework_paths ──────────────────────────────────────────────────
    for line in signals.get("framework_paths") or []:
        fp = _parse_path_line(line)
        if not fp:
            continue
        framework = fp["framework"]
        if framework not in _FRAMEWORK_KEYWORDS.values():
            framework = "unknown"
        if framework not in candidates:
            candidates[framework] = {
                "agent_name": _infer_agent_name(framework, fp["path"]),
                "framework": framework,
                "model": None,
                "api_key_fingerprint": None,
                "api_key_location": f"path:{fp['path']}",
                "evidence": ["framework_path"],
                "capabilities": {"filesystem": True, "network": False,
                                 "code_exec": False, "tool_count": 0},
            }
        else:
            candidates[framework].setdefault("evidence", []).append("framework_path")
            candidates[framework]["capabilities"]["filesystem"] = True

    return list(candidates.values())
