#!/usr/bin/env python3
"""
Vibegame Session Start Hook

Two responsibilities:
1. Record transcript_path into team state (used by lead.py to read transcripts later).
2. Append a roster entry into <primary_repo_root>/.vibegame/logs/agents.jsonl —
   one append per SessionStart firing. Append-only event stream; consumers
   aggregate by (cli, session_id, working_dir) and take last-wins for current state.

Context injection lives elsewhere:
- orchestrator: vibegame-start skill (.claude/skills/vibegame-start/SKILL.md)
- mate: lead.py prompt

Compatible with both Claude Code and Codex CLI.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _record_transcript_path(role: str, session_id: str, transcript_path: str) -> None:
    """Record transcript_path to team state for any role."""
    try:
        if role == "orchestrator":
            from team.state import update_lead
            update_lead(
                session_id=session_id,
                transcript_path=transcript_path,
                last_transcript_at=time.time(),
            )
        elif role == "mate":
            mate_name = os.environ.get("VIBEGAME_MATE_NAME", "")
            team_dir = os.environ.get("VIBEGAME_TEAM_DIR", "")
            if mate_name and team_dir:
                from team.state import update_agent
                update_agent(
                    mate_name,
                    explicit_team_dir=team_dir,
                    session_id=session_id,
                    transcript_path=transcript_path,
                    last_transcript_at=time.time(),
                )
    except Exception:
        pass


def record_general_mate_transcript(hook_input: dict, session_id: str) -> None:
    if os.environ.get("VIBEGAME_ROLE") != "mate":
        return
    if os.environ.get("VIBEGAME_TEAM_DIR", "") == "":
        return
    if os.environ.get("VIBEGAME_MATE_NAME", "") == "":
        return
    transcript_path = hook_input.get("transcript_path", "")
    if not transcript_path:
        return
    try:
        from team.state import update_agent

        update_agent(
            os.environ["VIBEGAME_MATE_NAME"],
            os.environ["VIBEGAME_TEAM_DIR"],
            session_id=session_id or None,
            transcript_path=transcript_path,
            last_transcript_at=time.time(),
        )
    except Exception:
        pass


def _extract_model(value) -> str | None:
    """Normalize hook_input.model into a string. Claude sends a dict, Codex a string."""
    if isinstance(value, dict):
        return value.get("id") or value.get("display_name") or None
    if isinstance(value, str):
        return value or None
    return None


def _settings_model_for(role: str, mate_name: str) -> str | None:
    """Fallback: look up model from <primary_repo_root>/.vibegame/settings.json."""
    name = mate_name if role == "mate" else "orchestrator"
    if not name:
        return None
    path = settings_path()
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    agent = data.get("agents", {}).get(name)
    if not isinstance(agent, dict):
        return None
    model = agent.get("model")
    return model if isinstance(model, str) and model else None


def _append_agents_jsonl(
    *,
    cli: str,
    session_id: str,
    working_dir: str,
    role: str,
    mate_name: str,
    model: str | None,
    transcript_path: str,
) -> None:
    """Append one entry to <primary_repo_root>/.vibegame/logs/agents.jsonl."""
    root = primary_repo_root()
    if root is None:
        raise RuntimeError("primary_repo_root() returned None; vibegame requires a git repository")
    log_path = root / ".vibegame" / "logs" / "agents.jsonl"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "cli": cli,
        "session_id": session_id,
        "working_dir": working_dir,
        "role": role,
        "mate_name": mate_name or None,
        "model": model,
        "transcript_path": transcript_path or None,
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    # O_APPEND on POSIX is atomic for small single-line writes — no lock needed.
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def main():
    global is_subagent_event, primary_repo_root, settings_path

    role = os.environ.get("VIBEGAME_ROLE", "")
    if not role:
        return

    from team.hook_identity import is_subagent_event  # noqa: E402
    from team.paths import primary_repo_root, settings_path  # noqa: E402

    parser = argparse.ArgumentParser(description="Vibegame Session Start Hook")
    parser.add_argument("--source-app", required=True, choices=("claude", "codex"))
    args, _ = parser.parse_known_args()

    from team.logger import get_logger
    log = get_logger()

    hook_input: dict = {}
    try:
        hook_input = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        pass

    if is_subagent_event(hook_input):
        sys.exit(0)

    session_id = hook_input.get("session_id", "")
    if not session_id:
        sys.exit(0)

    if role == "mate":
        record_general_mate_transcript(hook_input, session_id)

    transcript_path = hook_input.get("transcript_path", "")
    if transcript_path:
        _record_transcript_path(role, session_id, transcript_path)
    elif role == "orchestrator":
        _record_transcript_path(role, session_id, "")

    mate_name = os.environ.get("VIBEGAME_MATE_NAME", "")
    working_dir = hook_input.get("cwd", "") or os.getcwd()
    model = _extract_model(hook_input.get("model")) or _settings_model_for(role, mate_name)
    _append_agents_jsonl(
        cli=args.source_app,
        session_id=session_id,
        working_dir=working_dir,
        role=role,
        mate_name=mate_name,
        model=model,
        transcript_path=transcript_path,
    )

    log.hook(
        "session-start.py",
        {"session_id": session_id, "role": role, "cli": args.source_app},
        {"transcript_recorded": bool(transcript_path), "agents_jsonl_appended": True},
    )


if __name__ == "__main__":
    if not os.environ.get("VIBEGAME_ROLE", ""):
        sys.exit(0)
    from team.logger import run_hook
    run_hook("session-start.py", main)
