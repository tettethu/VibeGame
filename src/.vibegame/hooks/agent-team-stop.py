#!/usr/bin/env python3
"""Unified Stop hook for the workspace-local vibegame team runtime.

Stop Hook Judgment Logic
========================

Role-based dispatch:
- Unknown role → approve (no vibegame context)
- mate → must report completion before stop
- orchestrator → run through priority checks below

Orchestrator Priority Checks (in order):

1. Project config check
   Run `vibegame check` - block if errors found.

2. Session context check
   No team dir found → approve (no vibegame session).

3. Unread messages → BLOCK immediately
   Any unread teammate messages? Block and tell orchestrator to read them.
   Unread messages always have highest priority because they may contain
   critical feedback or reports.

4. Working agents → WAIT (up to 270s)
   Agents still working? Wait for one of:
   - New unread messages arrived → block with sender summary
   - User sent new prompt → block (user wants attention)
   - 270s timeout → block with agent names, suggest checking their status
   Each outcome has a distinct feedback message.

5. Review lock → BLOCK
   review-lock.json still locked? Block and tell orchestrator to read
   reviewer feedback and continue working until review passes.
   Auto-release lock if reviewer appears dead (consecutive block count
   reaches REVIEW_LOCK_MAX_BLOCKS without file modifications to
   review-lock.json or logs/review.md).

6. All checks pass → APPROVE stop

Mate Rules:
- Agent must set status to "can-stop" via report before stop is allowed.
- Use `vibegame mate report "[summary]"` for progress updates.
- Use `vibegame mate report --over "[summary]"` only when work is complete and this is the final handoff.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from team.hook_identity import is_subagent_event  # noqa: E402
from team.messages import unread_inbound  # noqa: E402
from team.paths import ensure_team_dir, find_team_dir, primary_repo_root, state_path  # noqa: E402
from team.settings import stop_hooks_for_role  # noqa: E402
from team.state import load_state, require_agent  # noqa: E402
from team.logger import get_logger  # noqa: E402

STOP_WAIT_TIMEOUT = 270.0
STOP_WAIT_INTERVAL = 2.0
REVIEW_LOCK_MAX_BLOCKS = 3  # auto-release after N consecutive blocks without reviewer activity


# -- Dashboard notification --------------------------------------------------

def _read_dashboard_state(team_dir: str | None) -> dict:
    if team_dir:
        try:
            return json.loads(state_path(team_dir).read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _read_dashboard_port(team_dir: str | None) -> str | None:
    state = _read_dashboard_state(team_dir)
    port = state.get("dashboard_port")
    if port:
        return str(port)
    return os.environ.get("VIBEGAME_DASHBOARD_PORT", "").strip() or None


def _read_dashboard_token(team_dir: str | None) -> str | None:
    token = os.environ.get("VIBEGAME_DASHBOARD_TOKEN", "").strip() or str(_read_dashboard_state(team_dir).get("dashboard_token") or "").strip()
    return token or None


def _detect_tmux_pane() -> str | None:
    pane_target = os.environ.get("TMUX_PANE", "").strip()
    if pane_target:
        return pane_target
    if not os.environ.get("TMUX"):
        return None
    try:
        r = subprocess.run(
            ["tmux", "display-message", "-p", "#{pane_id}"],
            capture_output=True, text=True, timeout=2,
        )
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()
    except Exception:
        pass
    return None


def _notify_dashboard_stop(payload: dict, role: str, team_dir: str | None, source_app: str = "claude") -> None:
    """Report Stop event to dashboard so session status is set to stopped."""
    port = _read_dashboard_port(team_dir)
    if not port:
        return
    session_id = payload.get("session_id", "")
    if not session_id:
        return
    event = {
        "source_app": source_app,
        "session_id": session_id,
        "hook_event_type": "Stop",
        "timestamp": payload.get("timestamp") or int(datetime.now().timestamp() * 1000),
        "name": os.environ.get("VIBEGAME_MATE_NAME", "").strip() or role,
        "transcript_path": payload.get("transcript_path"),
        "cwd": payload.get("cwd") or os.environ.get("CLAUDE_PROJECT_DIR", "").strip(),
        "tmux_pane": _detect_tmux_pane(),
        "model": payload.get("model"),
    }
    dashboard_token = _read_dashboard_token(team_dir)
    if dashboard_token:
        event["dashboard_token"] = dashboard_token
    url = f"http://localhost:{port}/events"
    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(event).encode("utf-8"),
            headers={"Content-Type": "application/json", "User-Agent": "VG-Hook/1.0"},
        )
        urllib.request.urlopen(req, timeout=2)
    except Exception:
        pass  # Dashboard unavailable — don't fail the stop hook


def _notify_dashboard_status(payload: dict, role: str, team_dir: str | None, source_app: str, status: str) -> None:
    """Notify dashboard of a custom status (e.g. 'waiting')."""
    port = _read_dashboard_port(team_dir)
    if not port:
        return
    session_id = payload.get("session_id", "")
    if not session_id:
        return
    event = {
        "source_app": source_app,
        "session_id": session_id,
        "hook_event_type": "StatusUpdate",
        "status": status,
        "timestamp": payload.get("timestamp") or int(datetime.now().timestamp() * 1000),
        "name": os.environ.get("VIBEGAME_MATE_NAME", "").strip() or role,
    }
    # Without dashboard_token, _event_belongs_to_project rejects this as foreign
    # (StatusUpdate carries no cwd to fall back on). That made agents appear
    # to flicker on/off between accepted lifecycle events.
    dashboard_token = _read_dashboard_token(team_dir)
    if dashboard_token:
        event["dashboard_token"] = dashboard_token
    url = f"http://localhost:{port}/events"
    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(event).encode("utf-8"),
            headers={"Content-Type": "application/json", "User-Agent": "VG-Hook/1.0"},
        )
        urllib.request.urlopen(req, timeout=2)
    except Exception:
        pass


# ---------------------------------------------------------------------------

def _approve(reason: str = "", payload: dict | None = None, role: str | None = None, team_dir: str | None = None, source_app: str = "claude") -> None:
    if payload is not None and role is not None:
        _notify_dashboard_stop(payload, role, team_dir, source_app)


def _block(reason: str) -> None:
    print(json.dumps({"decision": "block", "reason": reason}))


def _load_input() -> dict:
    raw = sys.stdin.read().strip()
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _resolve_source_app(cli_source_app: str | None, payload: dict) -> str:
    explicit = (cli_source_app or "").strip()
    if explicit:
        return explicit
    payload_source_app = str(payload.get("source_app", "")).strip()
    if payload_source_app:
        return payload_source_app
    if os.environ.get("CODEX_THREAD_ID", "").strip():
        return "codex"
    return "claude"


def _resolve_orchestrator_team_dir(payload: dict) -> str | None:
    cwd = payload.get("cwd")
    primary_root = primary_repo_root(cwd)
    if primary_root is not None:
        return str(primary_root / ".vibegame" / "team")
    candidate = find_team_dir(cwd)
    if candidate is None:
        return None
    return str(candidate)


def _resolve_project_dir(payload: dict | None = None) -> Path:
    payload = payload or {}
    env_dir = os.environ.get("CLAUDE_PROJECT_DIR", "")
    if env_dir:
        return Path(env_dir).resolve()
    cwd = payload.get("cwd", "")
    if cwd:
        return Path(cwd).resolve()
    return Path.cwd().resolve()


def _run_project_check(project_dir: Path) -> str | None:
    if not (project_dir / "project.json").exists():
        return None
    try:
        result = subprocess.run(
            ["vibegame", "check", str(project_dir)],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=project_dir,
        )
        if result.returncode != 0:
            return result.stdout.strip() or result.stderr.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return None


# -- Mate stop check --------------------------------------------------------

def check_mate_stop(team_dir: str, mate_name: str) -> tuple[bool, str]:
    hooks = stop_hooks_for_role("mate", team_dir)
    if not hooks:
        return True, "mate stop allowed"
    agent = require_agent(mate_name, team_dir)
    for hook in hooks:
        if hook.get("type") != "check":
            continue
        if hook.get("check") == "agent-reported" and agent.get("status") != "can-stop":
            return False, (
                f"Report your progress before stopping.\n"
                "Use `vibegame mate report \"[summary]\"` — progress update when you should keep working now.\n"
                "Use `vibegame mate report --over \"[summary]\"` — when current turn/task/preparation is done, and you will stop and wait for new instructions."
            )
    return True, "mate stop allowed"


# -- Shared helpers ---------------------------------------------------------

def current_working_agents(team_dir: str) -> list[str]:
    state = load_state(team_dir)
    agents = state.get("agents", {})
    return [name for name, agent in agents.items() if agent.get("status") == "working"]


def format_messages_summary(messages: list[dict]) -> str:
    """Return a summary of senders without message content."""
    senders: dict[str, int] = {}
    for msg in messages:
        name = str(msg.get("name", "?"))
        senders[name] = senders.get(name, 0) + 1
    names = sorted(senders.keys())
    summary = ", ".join(f"{n} ({senders[n]})" for n in names)
    return f"From: {summary or 'unknown'}"


def has_active_tasks(project_dir: Path) -> list[str]:
    """Return names of active tasks from .vibegame/tasks/tasks.jsonl."""
    tasks_path = project_dir / ".vibegame" / "tasks" / "tasks.jsonl"
    try:
        lines = tasks_path.read_text(encoding="utf-8").splitlines()
    except (FileNotFoundError, PermissionError):
        return []
    done_statuses = {"done", "decomposed", "archived"}
    active = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            task = json.loads(line)
            if task.get("status") not in done_statuses:
                active.append(task.get("name", "?"))
        except json.JSONDecodeError:
            continue
    return active


# -- Orchestrator stop checks -----------------------------------------------

def _review_file_mtimes(project_dir: Path) -> tuple[float, float]:
    """Return (lock_mtime, log_mtime) for review-lock.json and logs/review.md."""
    lock_path = project_dir / ".vibegame" / "review-lock.json"
    review_log = project_dir / ".vibegame" / "logs" / "review.md"
    lock_mtime = lock_path.stat().st_mtime if lock_path.exists() else 0.0
    log_mtime = review_log.stat().st_mtime if review_log.exists() else 0.0
    return lock_mtime, log_mtime


def _load_block_state(project_dir: Path) -> dict:
    state_path = project_dir / ".vibegame" / "review-block-state.json"
    try:
        return json.loads(state_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_block_state(project_dir: Path, state: dict) -> None:
    state_path = project_dir / ".vibegame" / "review-block-state.json"
    state_path.write_text(json.dumps(state), encoding="utf-8")


def _cleanup_block_state(project_dir: Path) -> None:
    state_path = project_dir / ".vibegame" / "review-block-state.json"
    try:
        state_path.unlink()
    except FileNotFoundError:
        pass


def check_review_lock(project_dir: Path) -> str | None:
    """Check review-lock status. Returns block message if locked, None if clear.

    Auto-releases if orchestrator has been blocked REVIEW_LOCK_MAX_BLOCKS
    consecutive times without any reviewer file activity.
    """
    lock_path = project_dir / ".vibegame" / "review-lock.json"
    if not lock_path.exists():
        _cleanup_block_state(project_dir)
        return None
    try:
        lock = json.loads(lock_path.read_text())
    except (json.JSONDecodeError, Exception):
        return None

    if not lock.get("locked"):
        _cleanup_block_state(project_dir)
        return None

    # Track consecutive blocks; reset counter if reviewer files were modified
    cur_lock_mtime, cur_log_mtime = _review_file_mtimes(project_dir)
    state = _load_block_state(project_dir)

    if cur_lock_mtime > state.get("lock_mtime", 0.0) or cur_log_mtime > state.get("log_mtime", 0.0):
        # Reviewer was active — reset counter, this block doesn't count
        state = {"count": 0, "lock_mtime": cur_lock_mtime, "log_mtime": cur_log_mtime}
    else:
        state["count"] = state.get("count", 0) + 1
        state["lock_mtime"] = cur_lock_mtime
        state["log_mtime"] = cur_log_mtime

    _save_block_state(project_dir, state)

    if state["count"] >= REVIEW_LOCK_MAX_BLOCKS:
        lock_path.write_text(json.dumps({"locked": False, "verdict": "timeout"}))
        _cleanup_block_state(project_dir)
        return None

    active = has_active_tasks(project_dir)
    hint = f" Active tasks: {', '.join(active)}" if active else " No active tasks."
    return (
        f"Review lock is active (reviewer has not released it).{hint}\n"
        f"Read reviewer feedback and continue working until review passes.\n"
        f"If unsure, re-read .claude/skills/vibegame-build/SKILL.md to recall the workflow."
    )


def wait_for_messages_or_timeout(
    team_dir: str,
    timeout: float = STOP_WAIT_TIMEOUT,
) -> list[dict] | None:
    """Wait for new unread messages from teammates.

    Returns list of messages if any arrived, None on timeout.
    """
    deadline = time.time() + timeout
    while True:
        unread = unread_inbound(team_dir)
        if unread:
            return unread
        if time.time() >= deadline:
            return None
        time.sleep(STOP_WAIT_INTERVAL)


# -- Main -------------------------------------------------------------------

def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description="VibeGame agent-team-stop hook")
    parser.add_argument("--source-app")
    args, _ = parser.parse_known_args()

    log = get_logger()
    payload = _load_input()
    if is_subagent_event(payload):
        return 0

    source_app = _resolve_source_app(args.source_app, payload)
    env_team_dir = os.environ.get("VIBEGAME_TEAM_DIR")
    role = os.environ.get("VIBEGAME_ROLE")
    session_id = payload.get("session_id", "")
    project_dir = _resolve_project_dir(payload)
    team_dir: str | None = None

    if role == "mate":
        team_dir = str(ensure_team_dir(env_team_dir))
        mate_name = os.environ.get("VIBEGAME_MATE_NAME")
        if not mate_name:
            _block("Missing VIBEGAME_MATE_NAME for mate stop hook.")
            return 0
        allowed, message = check_mate_stop(team_dir, mate_name)

    elif role == "orchestrator":
        # 1. Project config
        check_errors = _run_project_check(project_dir)
        if check_errors:
            _block(f"Project config has errors. Fix them before stopping:\n{check_errors}")
            return 0

        # 2. Session context
        team_dir = str(ensure_team_dir(env_team_dir)) if env_team_dir else _resolve_orchestrator_team_dir(payload)
        if team_dir is None:
            _approve("No vibegame session context.", payload, role, team_dir, source_app)
            return 0

        # 4. Unread messages → block immediately
        unread = unread_inbound(team_dir)
        if unread:
            allowed = False
            message = (
                f"Unread teammate messages. {format_messages_summary(unread)}\n"
                "Use `vibegame lead read --name ALL` to read them before stopping."
            )
        else:
            # 5. Working agents → wait for messages/timeout
            working = current_working_agents(team_dir)
            if working:
                _notify_dashboard_status(payload, role, team_dir, source_app, "waiting")
                event_messages = wait_for_messages_or_timeout(team_dir)
                _notify_dashboard_status(payload, role, team_dir, source_app, "running")
                if event_messages:
                    allowed = False
                    message = (
                        f"New teammate report(s). {format_messages_summary(event_messages)}\n"
                        "Use `vibegame lead read --name ALL` to read them before stopping."
                    )
                else:
                    allowed = False
                    message = (
                        f"Agents still working after {int(STOP_WAIT_TIMEOUT)}s: {', '.join(sorted(working))}. "
                        "Check whether they are stuck or need help.\n"
                        f"Use `vibegame lead log --name <agent>` to check their progress."
                    )
            else:
                # 6. Review lock → block
                review_msg = check_review_lock(project_dir)
                if review_msg:
                    allowed = False
                    message = review_msg
                else:
                    # 7. All clear
                    allowed = True
                    message = "orchestrator stop allowed"

    else:
        _approve("No vibegame session context.", payload, role, team_dir, source_app)
        return 0

    if allowed:
        _approve(message, payload, role, team_dir, source_app)
    else:
        _block(message)
    log.hook(
        "agent-team-stop.py",
        {"role": role, "session_id": session_id},
        {"decision": "approve" if allowed else "block"},
    )
    return 0


if __name__ == "__main__":
    from team.logger import run_hook
    run_hook("agent-team-stop.py", main)
