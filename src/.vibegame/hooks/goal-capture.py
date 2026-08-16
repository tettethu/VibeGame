#!/usr/bin/env python3
"""Record the user's verbatim build request into .vibegame/goal.md.

Fires on UserPromptSubmit for the orchestrator. A prompt that invokes the
vibegame-build skill is appended verbatim under `## User Input`, fenced so the
request's own headings cannot forge goal.md sections. Everything downstream
(GDD, prd.md, review) is derived from this text, so no agent rewrites it.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from team.hook_identity import is_subagent_event  # noqa: E402
from team.logger import get_logger  # noqa: E402
from team.paths import find_team_dir, primary_repo_root  # noqa: E402

SCRIPT = "goal-capture.py"
SECTION = "## User Input"
BUILD_MARKER = "vibegame-build"
ENTRY_PREFIX = "### Request "


def _load_input() -> dict:
    raw = sys.stdin.read().strip()
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _resolve_goal_path(payload: dict) -> Path | None:
    """Same resolution the other orchestrator hooks use: primary root, else cwd walk."""
    cwd = payload.get("cwd")
    primary_root = primary_repo_root(cwd)
    if primary_root is not None:
        return primary_root / ".vibegame" / "goal.md"
    team = find_team_dir(cwd)
    return None if team is None else team.parent / "goal.md"


def _fence_for(text: str) -> str:
    """A fence longer than any backtick run inside the request itself."""
    longest = max((len(run) for run in re.findall(r"`+", text)), default=0)
    return "`" * max(4, longest + 1)


def _entry(prompt: str, index: int) -> list[str]:
    fence = _fence_for(prompt)
    stamp = time.strftime("%Y-%m-%d %H:%M:%S")
    body = prompt.strip().splitlines()
    return [f"{ENTRY_PREFIX}{index} — {stamp}", "", f"{fence}text", *body, fence]


def _structural_lines(lines: list[str]) -> list[tuple[int, str]]:
    """Lines that carry document structure, i.e. everything outside a fenced block.

    Captured requests keep their own headings, so a plain line scan would read
    `## Requirements` from inside a request body as the next goal.md section.
    """
    out: list[tuple[int, str]] = []
    fence: str | None = None
    for i, line in enumerate(lines):
        opener = re.match(r"(`{3,}|~{3,})", line.lstrip())
        if fence is None:
            if opener:
                fence = opener.group(1)
            else:
                out.append((i, line))
        elif opener and opener.group(1)[0] == fence[0] and len(opener.group(1)) >= len(fence):
            fence = None
    return out


def append_request(goal_path: Path, prompt: str) -> int | None:
    """Append one request under `## User Input`. Returns its index, None if the section is gone."""
    lines = goal_path.read_text(encoding="utf-8").splitlines()
    structural = _structural_lines(lines)
    start = next((i for i, line in structural if line.strip() == SECTION), None)
    if start is None:
        return None
    end = next((i for i, line in structural if i > start and line.startswith("## ")), len(lines))

    index = sum(1 for i, line in structural if start < i < end and line.startswith(ENTRY_PREFIX)) + 1
    tail = end
    while tail > start + 1 and not lines[tail - 1].strip():
        tail -= 1

    updated = lines[:tail] + [""] + _entry(prompt, index) + [""] + lines[end:]
    goal_path.write_text("\n".join(updated).rstrip() + "\n", encoding="utf-8")
    return index


def main() -> int:
    parser = argparse.ArgumentParser(description="Vibegame goal capture hook")
    parser.add_argument("--source-app")
    args, _ = parser.parse_known_args()
    log = get_logger()

    if os.environ.get("VIBEGAME_ROLE") != "orchestrator":
        return 0
    payload = _load_input()
    if is_subagent_event(payload):
        return 0

    prompt = payload.get("prompt")
    if not isinstance(prompt, str) or not prompt.strip():
        # The one field this hook depends on. Log the payload shape so a CLI that
        # names it differently is diagnosable instead of silently uncaptured.
        log.hook(SCRIPT, {"source_app": args.source_app, "payload_keys": sorted(payload)},
                 {"skipped": "no prompt text in payload"})
        return 0
    if BUILD_MARKER not in prompt:
        return 0

    goal_path = _resolve_goal_path(payload)
    if goal_path is None or not goal_path.is_file():
        log.hook(SCRIPT, {"cwd": payload.get("cwd")}, {"skipped": "goal.md not found", "path": str(goal_path)})
        return 0

    index = append_request(goal_path, prompt)
    if index is None:
        log.hook(SCRIPT, {"path": str(goal_path)}, {"skipped": f"no '{SECTION}' section"})
        return 0
    log.hook(SCRIPT, {"chars": len(prompt)}, {"appended": index, "path": str(goal_path)})
    return 0


if __name__ == "__main__":
    from team.logger import run_hook

    run_hook(SCRIPT, main)
