#!/usr/bin/env python3
from __future__ import annotations

"""
Enforce Team Setup - PreToolUse Hook

Blocks tool calls until orchestrator completes team setup.

Flow: need_team -> Bash(lead.py start) -> need_members -> Bash(lead.py agent) -> ready

Only active when VIBEGAME_ROLE=orchestrator (vibegame claude sessions).
State tracked in .vibegame/.session-lock (JSONL, one entry per session_id).
"""

import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from team.hook_identity import is_subagent_event  # noqa: E402

LOCK_FILE = ".vibegame/.session-lock"

ALWAYS_ALLOWED = {"ToolSearch", "Read", "Glob", "Grep", "Bash"}

REQUIRED_MEMBERS = {"artist", "designer"}


def resolve_project_dir(hook_input: dict = {}) -> Path:
    """Resolve project root: CLAUDE_PROJECT_DIR > stdin cwd > cwd."""
    env_dir = os.environ.get("CLAUDE_PROJECT_DIR", "")
    if env_dir:
        return Path(env_dir).resolve()
    cwd = hook_input.get("cwd", "")
    if cwd:
        return Path(cwd).resolve()
    return Path.cwd().resolve()


def read_lock(project_dir: Path, session_id: str) -> dict | None:
    lock_path = project_dir / LOCK_FILE
    try:
        lines = lock_path.read_text(encoding="utf-8").splitlines()
    except (FileNotFoundError, PermissionError):
        return None
    result = None
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
            if entry.get("session_id") == session_id:
                result = entry
        except json.JSONDecodeError:
            continue
    return result


def write_lock(project_dir: Path, lock: dict) -> None:
    lock_path = project_dir / LOCK_FILE
    session_id = lock.get("session_id", "")
    try:
        lines = lock_path.read_text(encoding="utf-8").splitlines()
    except (FileNotFoundError, PermissionError):
        lines = []
    new_lines = []
    replaced = False
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        try:
            entry = json.loads(stripped)
            if entry.get("session_id") == session_id:
                new_lines.append(json.dumps(lock, ensure_ascii=False))
                replaced = True
            else:
                new_lines.append(stripped)
        except json.JSONDecodeError:
            new_lines.append(stripped)
    if not replaced:
        new_lines.append(json.dumps(lock, ensure_ascii=False))
    try:
        lock_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    except Exception:
        pass


def extract_team_name(tool_input: dict) -> str | None:
    for key in ("team_name", "teamName", "name"):
        value = tool_input.get(key)
        if isinstance(value, str):
            team_name = value.strip()
            if team_name:
                return team_name
    return None


def _extract_flag_values(cmd: str, flag: str) -> list[str]:
    """Extract all values for a CLI flag (accepts both - and _ variants)."""
    escaped = re.escape(flag).replace(r"\-", r"[-_]")
    return [m.lower().strip("'\"") for m in re.findall(rf"{escaped}\s+(\S+)", cmd)]


def _extract_flag_value(cmd: str, flag: str) -> str | None:
    """Extract first value for a CLI flag (accepts both - and _ variants)."""
    values = _extract_flag_values(cmd, flag)
    return values[0] if values else None


def detect_member_roles_general(cmd: str) -> list[str]:
    """Extract all agent roles from a lead.py command (supports multi-command strings)."""
    found = []
    for val in _extract_flag_values(cmd, "--agent-type"):
        if val in REQUIRED_MEMBERS:
            found.append(val)
    if not found:
        for val in _extract_flag_values(cmd, "--name"):
            if val in REQUIRED_MEMBERS:
                found.append(val)
    return found


def detect_member_role_general(cmd: str) -> str | None:
    """Extract first agent role from a lead.py agent command via --agent-type or --name."""
    roles = detect_member_roles_general(cmd)
    return roles[0] if roles else None


def format_members_status(lock: dict) -> tuple[str, str]:
    spawned = sorted(m for m in REQUIRED_MEMBERS if lock.get(f"{m}_spawned"))
    missing = sorted(REQUIRED_MEMBERS - set(spawned))
    return ", ".join(spawned) or "none", ", ".join(missing)


def deny(reason: str):
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
            "reason": reason,
        }
    }, ensure_ascii=False), flush=True)
    sys.exit(0)


# ── General mode handlers ───────────────────────────────────────────────────

def is_lead_command(cmd: str) -> bool:
    # Match both the new `vibegame lead` form and any legacy fallback that
    # still says lead.py — although scripts/lead.py was deleted in the
    # rename sprint, user docs / muscle memory may still try it.
    return "vibegame lead" in cmd or "lead.py" in cmd


def handle_general_need_team(tool_name: str, tool_input: dict, lock: dict, project_dir: Path):
    if tool_name == "Bash":
        cmd = tool_input.get("command", "")
        if is_lead_command(cmd) and "start" in cmd:
            lock["phase"] = "need_members"
            write_lock(project_dir, lock)
            sys.exit(0)
        # Other lead.py commands (status, list, etc.) allowed during setup
        if is_lead_command(cmd):
            sys.exit(0)
    deny(
        "[Team Setup] You must start the team runtime first.\n"
        "Allowed: `vibegame lead start`, ToolSearch, Read, Glob, Grep\n\n"
        "Start the team, then spawn artist and designer via `vibegame lead agent`."
    )


def handle_general_need_members(tool_name: str, tool_input: dict, lock: dict, project_dir: Path):
    spawned_str, missing_str = format_members_status(lock)
    if tool_name == "Bash":
        cmd = tool_input.get("command", "")
        if is_lead_command(cmd) and "agent" in cmd:
            members = detect_member_roles_general(cmd)
            if members:
                for member in members:
                    lock[f"{member}_spawned"] = True
                if all(lock.get(f"{m}_spawned") for m in REQUIRED_MEMBERS):
                    lock["phase"] = "ready"
                write_lock(project_dir, lock)
                sys.exit(0)
            # lead.py agent for non-required member: deny
            deny(
                f"[Team Setup] Only artist/designer agents can be spawned now.\n"
                f"Spawned: {spawned_str}\nMissing: {missing_str}"
            )
        # Other lead.py commands (send, inbox, etc.) allowed during setup
        if is_lead_command(cmd):
            sys.exit(0)
    deny(
        f"[Team Setup] Spawn remaining team members before doing other work.\n"
        f"Spawned: {spawned_str}\nMissing: {missing_str}\n\n"
        f"Use `vibegame lead agent --agent-type <role>` to spawn: {missing_str}."
    )


def _track_lead_phase(lock: dict, project_dir: Path, phase: str, tool_input: dict):
    """Update lock phases for lead.py commands within always-allowed Bash."""
    cmd = tool_input.get("command", "")
    if not is_lead_command(cmd):
        return
    if phase == "need_team" and "start" in cmd:
        lock["phase"] = "need_members"
        write_lock(project_dir, lock)
    elif phase == "need_members" and "agent" in cmd:
        members = detect_member_roles_general(cmd)
        if members:
            for member in members:
                lock[f"{member}_spawned"] = True
            if all(lock.get(f"{m}_spawned") for m in REQUIRED_MEMBERS):
                lock["phase"] = "ready"
            write_lock(project_dir, lock)
        else:
            from team.logger import get_logger
            get_logger().hook(
                "enforce-team-setup.py",
                {"phase": phase, "event": "member_detect_failed"},
                {"cmd_prefix": cmd[:200]},
            )


# ── Main ────────────────────────────────────────────────────────────────────

def _is_pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        return False


def _detect_phase_from_state(project_dir: Path) -> str:
    """Detect team setup phase from state.json + PID files (ground truth)."""
    try:
        from team.state import load_state
        from team.tmux import session_exists
    except ImportError:
        return "need_team"

    team_dir = str(project_dir / ".vibegame" / "team")
    try:
        state = load_state(team_dir)
    except Exception:
        return "need_team"

    sess = state.get("session_name")
    if not sess or not session_exists(sess):
        return "need_team"

    pid_dir = project_dir / ".vibegame" / "team" / "pids"
    agents = state.get("agents", {})
    alive = set()
    for name, agent in agents.items():
        role = agent.get("agent_type") or name
        if role not in REQUIRED_MEMBERS:
            continue
        pid_file = pid_dir / f"{name}.pid"
        try:
            pid = int(pid_file.read_text().strip())
            if _is_pid_alive(pid):
                alive.add(role)
        except (FileNotFoundError, ValueError):
            pass

    if REQUIRED_MEMBERS <= alive:
        return "ready"
    return "need_members"


def main():
    from team.logger import get_logger
    log = get_logger()

    if os.environ.get("VIBEGAME_ROLE") != "orchestrator":
        sys.exit(0)

    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    if is_subagent_event(input_data):
        sys.exit(0)

    project_dir = resolve_project_dir(input_data)

    # Detect phase from state.json (ground truth: tmux session + pane liveness)
    phase = _detect_phase_from_state(project_dir)
    if phase == "ready":
        sys.exit(0)

    tool_name = input_data.get("tool_name", "")
    tool_input = input_data.get("tool_input", {})
    session_id = input_data.get("session_id", "")

    # Build a lock-like dict for compatibility with existing handlers
    lock = {
        "session_id": session_id,
        "phase": phase,
        "artist_spawned": False,
        "designer_spawned": False,
    }

    # Always-allowed tools pass through, but track lead.py phase transitions for Bash
    if tool_name in ALWAYS_ALLOWED:
        if tool_name == "Bash":
            _track_lead_phase(lock, project_dir, phase, tool_input)
        sys.exit(0)

    # Phase enforcement for other tools
    log.hook(
        "enforce-team-setup.py",
        {"phase": phase, "tool": tool_name},
        {"decision": "enforce_setup"},
    )
    if phase == "need_team":
        handle_general_need_team(tool_name, tool_input, lock, project_dir)
    elif phase == "need_members":
        handle_general_need_members(tool_name, tool_input, lock, project_dir)

    sys.exit(0)


if __name__ == "__main__":
    from team.logger import run_hook
    run_hook("enforce-team-setup.py", main)
