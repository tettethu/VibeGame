"""Settings helpers for the local team runtime."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

from .launch import CLI_CONFIGS
from .paths import ensure_team_dir, settings_path, workspace_root

DEFAULT_SETTINGS = {
    "agents": {},
    "hooks": {
        "Stop": [
            {
                "role": "mate",
                "type": "check",
                "check": "agent-reported",
                "enabled": True,
            },
            {
                "role": "lead",
                "type": "check",
                "check": "no-working-agents",
                "enabled": True,
            },
            {
                "role": "lead",
                "type": "check",
                "check": "unread-messages",
                "enabled": True,
            },
        ],
    },
}

DEFAULT_CLAUDE_CLI = "claude"
DEFAULT_CLAUDE_MODEL = CLI_CONFIGS[DEFAULT_CLAUDE_CLI]["default_model"]


def _deep_merge(base: dict, override: dict) -> dict:
    result = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_settings(explicit_team_dir: str | None = None) -> dict:
    team_dir = ensure_team_dir(explicit_team_dir)
    path = settings_path(str(team_dir))
    if not path.exists():
        path.write_text(json.dumps(DEFAULT_SETTINGS, indent=2), encoding="utf-8")
        return deepcopy(DEFAULT_SETTINGS)
    try:
        raw = path.read_text(encoding="utf-8").strip()
        data = json.loads(raw) if raw else {}
    except (OSError, json.JSONDecodeError):
        data = {}
    if not isinstance(data, dict):
        data = {}
    merged = _deep_merge(DEFAULT_SETTINGS, data)
    return merged


def resolve_agent_settings(
    *,
    name: str | None,
    agent: str | None,
    model: str | None,
    explicit_team_dir: str | None = None,
) -> tuple[str | None, str | None, str | None]:
    settings = load_settings(explicit_team_dir)
    agents = settings.get("agents", {})
    docs = agent_doc_map(explicit_team_dir)
    resolved_name = name or agent
    lookup_key = agent or resolved_name
    config = {}
    if lookup_key and isinstance(agents.get(lookup_key), dict):
        config = agents[lookup_key]
    resolved_model = model if model is not None else config.get("model")
    # Explicit cli takes priority; model-based inference is only a fallback.
    resolved_cli = config.get("cli")
    if resolved_cli is None and resolved_model is not None:
        matches = [cli_name for cli_name, cfg in CLI_CONFIGS.items() if resolved_model in cfg.get("models", [])]
        if len(matches) == 1:
            resolved_cli = matches[0]
    if resolved_cli is None and lookup_key in docs:
        resolved_cli = DEFAULT_CLAUDE_CLI
    if resolved_model is None and resolved_cli in CLI_CONFIGS:
        resolved_model = CLI_CONFIGS[resolved_cli]["default_model"]
    return resolved_name, resolved_cli, resolved_model


def stop_hooks_for_role(role: str, explicit_team_dir: str | None = None) -> list[dict]:
    settings = load_settings(explicit_team_dir)
    hooks = settings.get("hooks", {}).get("Stop", [])
    return [
        hook for hook in hooks
        if isinstance(hook, dict) and hook.get("enabled", True) and hook.get("role") == role
    ]


def agent_doc_map(explicit_team_dir: str | None = None) -> dict[str, str]:
    agents_dir = workspace_root(explicit_team_dir) / ".claude" / "agents"
    if not agents_dir.is_dir():
        return {}
    docs: dict[str, str] = {}
    for path in sorted(agents_dir.glob("*.md")):
        docs[path.stem] = str(path)
    return docs
