#!/usr/bin/env python3
"""PostToolUse hook - touch last_teammate_message_at on any SendMessage.

This lets stop-hook's review-lock check distinguish between:
- orchestrator idle-waiting (teammates still communicating) → keep waiting
- session truly stalled (no teammate activity) → block with guidance

Input:  PostToolUse event JSON from stdin
Output: (no output = continue/approve) Update at every SendMessage including lead's message to avoid edge cases
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from team.hook_identity import is_subagent_event  # noqa: E402
from team.state import touch_teammate_message  # noqa: E402


def find_team_dir(start_path: str) -> str | None:
    """Find .vibegame/team dir from a starting path."""
    current = Path(start_path).resolve()
    while current != current.parent:
        team_dir = current / ".vibegame" / "team"
        if team_dir.is_dir():
            return str(team_dir)
        current = current.parent
    return None


def main():
    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    if data.get("hook_event_name") != "PostToolUse":
        sys.exit(0)

    if is_subagent_event(data):
        sys.exit(0)

    if data.get("tool_name") != "SendMessage":
        sys.exit(0)

    cwd = data.get("cwd", os.getcwd())
    team_dir = os.environ.get("VIBEGAME_TEAM_DIR") or find_team_dir(cwd)
    if not team_dir:
        sys.exit(0)

    touch_teammate_message(team_dir)
    sys.exit(0)


if __name__ == "__main__":
    from team.logger import run_hook
    run_hook("teammate-message-touch.py", main)
