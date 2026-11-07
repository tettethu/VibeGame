#!/usr/bin/env python3
"""Record prompt submission for the orchestrator and mates; mark mates working on new work."""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
import argparse

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from team.hook_identity import is_subagent_event  # noqa: E402
from team.paths import ensure_team_dir, find_team_dir, primary_repo_root  # noqa: E402
from team.shortcut import has_work  # noqa: E402
from team.state import update_agent  # noqa: E402
from team.wake import record_prompt  # noqa: E402


def _load_input() -> dict:
    raw = sys.stdin.read().strip()
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _resolve_orchestrator_team_dir(payload: dict) -> str | None:
    cwd = payload.get("cwd")
    primary_root = primary_repo_root(cwd)
    if primary_root is not None:
        return str(primary_root / ".vibegame" / "team")
    candidate = find_team_dir(cwd)
    if candidate is None:
        return None
    return str(candidate)


def record_last_user_prompt(team_dir: str) -> None:
    record_prompt(team_dir)


def record_mate_prompt(payload: dict) -> None:
    """Acknowledge the submission; any prompt beyond notices is work the mate must report on."""
    fields = {"last_prompt_at": time.time()}
    if has_work(payload["prompt"]):
        fields["status"] = "working"
    update_agent(os.environ["VIBEGAME_MATE_NAME"], os.environ["VIBEGAME_TEAM_DIR"], **fields)


def main() -> int:
    parser = argparse.ArgumentParser(description="Vibegame user prompt submit hook")
    parser.add_argument("--source-app")
    parser.parse_known_args()

    role = os.environ.get("VIBEGAME_ROLE")
    if role not in ("orchestrator", "mate"):
        return 0
    payload = _load_input()
    if is_subagent_event(payload):
        return 0
    if role == "mate":
        record_mate_prompt(payload)
        return 0
    team_dir = os.environ.get("VIBEGAME_TEAM_DIR") or _resolve_orchestrator_team_dir(payload)
    if not team_dir:
        return 0
    ensure_team_dir(team_dir)
    record_last_user_prompt(team_dir)
    return 0


if __name__ == "__main__":
    from team.logger import run_hook
    run_hook("user-prompt-submit.py", main)
