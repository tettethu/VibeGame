#!/usr/bin/env python3
"""
Enforce Team Mode for Dynamic Agents

Blocks direct Agent / Task tool launches of the sprint-scoped agents
(architect / programmer / auditor / player). These must be spawned via
`vibegame lead agent` so the team context-injection pipeline runs.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Agent types that REQUIRE `vibegame lead agent` (sprint-scoped task agents that
# must run with the team context-injection pipeline rather than as a direct
# Claude Code `Task` subagent).
GENERAL_ONLY_AGENTS = {"architect", "programmer", "auditor", "player"}


def find_repo_root(start_path: str) -> str | None:
    current = Path(start_path).resolve()
    for _ in range(20):
        if (current / ".vibegame").is_dir():
            return str(current)
        if current.parent == current:
            return None
        current = current.parent
    return None


def extract_agent_type(name: str | None, subagent_type: str | None) -> str | None:
    """Extract agent type from name or subagent_type."""
    # Priority 1: parse from name (format: "<role>-<task>")
    if name:
        name_lower = name.lower()
        for prefix in ("architect-", "programmer-", "auditor-", "player-"):
            if name_lower.startswith(prefix):
                return prefix.rstrip("-")
    # Priority 2: use subagent_type directly
    if subagent_type:
        return subagent_type.lower()
    return None


def main():
    from team.logger import get_logger
    log = get_logger()

    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    # Only intercept Agent tool
    if input_data.get("tool_name") != "Agent":
        sys.exit(0)

    tool_input = input_data.get("tool_input", {})
    cwd = input_data.get("cwd", os.getcwd())

    agent_type = extract_agent_type(
        tool_input.get("name"),
        tool_input.get("subagent_type")
    )

    # Only block specific agent types
    if agent_type not in GENERAL_ONLY_AGENTS:
        sys.exit(0)

    repo_root = find_repo_root(cwd)
    if not repo_root:
        sys.exit(0)

    # Block and guide to lead.py
    log.hook("enforce-team-mode.py", {"agent_type": agent_type}, {"decision": "deny"})
    agent_name = tool_input.get("name", f"<name>")
    prompt = tool_input.get("prompt", "<prompt>")

    output = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": (
                f"{agent_type} agent must be spawned via vibegame lead to get task context.\n\n"
                f"Use:\n"
                f"  vibegame lead agent --name {agent_name} --agent-type {agent_type} --prompt '{prompt[:50]}...'"
            ),
        }
    }
    print(json.dumps(output, ensure_ascii=False))
    sys.exit(0)


if __name__ == "__main__":
    from team.logger import run_hook
    run_hook("enforce-team-mode.py", main)
