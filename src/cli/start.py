"""
vibegame start - Launch project workspace: web dashboard + agent sessions in tmux.

Usage:
  vibegame start                      # Auto-resume if previous session exists
  vibegame start "build a platformer" # Start and send the initial input
  vibegame start --project ./game     # Start a different project
  vibegame start --new                # Force fresh start
  vibegame start --port 4040          # Exact port, assert if busy
  vibegame start --host 0.0.0.0       # Listen on all interfaces
  vibegame start --no-agents          # Dashboard only
"""

import json
import logging
import os
import secrets
import shlex
import shutil
import subprocess as sp
import sys
import tempfile
import time
from pathlib import Path
import socket
import urllib.error
import urllib.parse

from util.skills import rewrite_leading_skill, skill_invocation
import urllib.request

import typer

from cli.router import app

# tmux helpers come from the source tree's own copy, not the one `vibegame init`
# wrote into the project: the CLI must not have its behaviour pinned to whatever
# version a user's project happens to carry. The project copy is for the hooks
# and the team runtime, which run inside that project.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / ".vibegame"))
from team.tmux import (  # noqa: E402
    TmuxError,
    capture_pane,
    create_session,
    current_session_name,
    kill_pane,
    new_window,
    pane_dead,
    pane_in_session,
    paste_prompt,
    resolve_pane_id,
    send_trust_enter,
    session_exists,
    session_target,
    set_remain_on_exit,
    should_send_trust_enter,
    split_window,
    tmux_bin,
    window_target,
)


logger = logging.getLogger("vibegame.start")
DEFAULT_PORT = 8080
AGENT_BOOT_STABLE_SECONDS = 1.5


def _port_available(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        # Match ThreadingHTTPServer.allow_reuse_address, or a port left in
        # TIME_WAIT by the dashboard we just replaced reads as occupied for a
        # minute even though the server could bind it right away.
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((host, port))
        except OSError:
            return False
    return True


def _select_port(host: str, requested: int | None, start: int, exclude: set[int] | None = None) -> int:
    """Select a single free port. If requested is set, verify it's free; otherwise auto-scan from start."""
    if requested is not None:
        if not _port_available(host, requested):
            raise AssertionError(f"Port {requested} is already in use.")
        return requested

    exclude = exclude or set()
    for candidate in range(start, start + 100):
        if candidate not in exclude and _port_available(host, candidate):
            logger.info("port_selected mode=auto port=%s", candidate)
            return candidate

    raise AssertionError(f"No free port found from {start} to {start + 99}.")


def _connect_host(host: str) -> str:
    """Return a loopback address for local control when binding all interfaces."""
    return "127.0.0.1" if host in ("0.0.0.0", "::") else host


def _configure_logging(project_path: Path, debug: bool = False) -> Path:
    log_dir = project_path / ".vibegame" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "start.log"
    handler = logging.FileHandler(log_file)
    handler.setFormatter(logging.Formatter("%(asctime)s %(name)s %(levelname)s %(message)s"))
    logger.handlers.clear()
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG if debug else logging.INFO)
    logger.propagate = False
    logger.info("start_invoked cwd=%s debug=%s", project_path, debug)
    return log_file


def _run_lead(project_path: Path, args: str, debug: bool = False) -> sp.CompletedProcess:
    """Run `vibegame lead` with proper env from the project directory.

    Uses the globally-installed `vibegame` CLI; the team/ runtime modules are
    found in the project's .vibegame/ via VIBEGAME_TEAM_DIR.
    """
    team_dir = project_path / ".vibegame" / "team"
    env = os.environ.copy()
    env["VIBEGAME_ROLE"] = "orchestrator"
    env["VIBEGAME_TEAM_DIR"] = str(team_dir)
    if debug:
        env["VIBEGAME_DEBUG"] = "1"
    return sp.run(
        ["vibegame", "lead", *shlex.split(args)],
        cwd=project_path,
        env=env,
        capture_output=True,
        text=True,
    )


def _send_initial_input(target: str, message: str) -> None:
    """Send the user's request to a ready orchestrator pane as one message."""
    paste_prompt(target, message)


def _is_pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        return False


def _read_pid(project_path: Path, name: str) -> int | None:
    pid_file = project_path / ".vibegame" / "team" / "pids" / f"{name}.pid"
    try:
        return int(pid_file.read_text().strip())
    except (FileNotFoundError, ValueError):
        return None


def _pid_command(pid: int) -> str:
    result = sp.run(
        ["ps", "-p", str(pid), "-o", "command="],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def _pid_matches(pid: int, *markers: str) -> bool:
    command = _pid_command(pid)
    return bool(command and all(marker in command for marker in markers))


def _kill_dashboard(project_path: Path, session_name: str) -> None:
    """Kill the existing dashboard: process first, then tmux window."""
    import signal as _signal

    def _term_pid(pid: int | None, label: str, *markers: str) -> None:
        if not (pid and _is_pid_alive(pid)):
            return
        if markers and not _pid_matches(pid, *markers):
            logger.warning(
                "%s_skipped pid=%s reason=marker_mismatch markers=%s command=%s",
                label,
                pid,
                markers,
                _pid_command(pid),
            )
            return
        try:
            os.kill(pid, _signal.SIGTERM)
            deadline = time.time() + 3.0
            while time.time() < deadline and _is_pid_alive(pid):
                time.sleep(0.1)
            if _is_pid_alive(pid):
                os.kill(pid, _signal.SIGKILL)
        except ProcessLookupError:
            pass
        logger.info("%s pid=%s", label, pid)

    # Kill the Python server process (server.pid, written by server.py at startup)
    _term_pid(_read_pid(project_path, "server"), "server_killed", "server.py server", f"--project {project_path}")
    (project_path / ".vibegame" / "team" / "pids" / "server.pid").unlink(missing_ok=True)

    # Kill the launcher shell (dashboard.pid, written by the launch script)
    _term_pid(_read_pid(project_path, "dashboard"), "dashboard_killed", str(project_path / ".vibegame" / "dashboard" / "dashboard.sh"))
    (project_path / ".vibegame" / "team" / "pids" / "dashboard.pid").unlink(missing_ok=True)

    # Fallback: kill any zombie server.py processes for this project (e.g. from old
    # runs where dashboard.pid held the shell PID, not Python's PID)
    try:
        result = sp.run(
            ["pgrep", "-f", f"server.py server.*{project_path}"],
            capture_output=True, text=True,
        )
        for pid_str in result.stdout.strip().splitlines():
            try:
                zombie_pid = int(pid_str)
                if not _pid_matches(zombie_pid, "server.py server", f"--project {project_path}"):
                    continue
                os.kill(zombie_pid, _signal.SIGKILL)
                logger.info("zombie_server_killed pid=%s", zombie_pid)
            except (ValueError, ProcessLookupError):
                pass
    except FileNotFoundError:
        pass  # pgrep not available

    # Kill tmux window so the port is fully released before we bind a new one
    result = sp.run(
        [tmux_bin(), "list-windows", "-t", session_target(session_name), "-F", "#{window_index}"],
        capture_output=True, text=True,
    )
    if "1" in result.stdout.strip().splitlines():
        sp.run([tmux_bin(), "kill-window", "-t", window_target(session_name, 1)], capture_output=True)
        logger.info("dashboard_window_killed session=%s", session_name)


def _wait_http_ready(url: str, timeout: float = 10.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1) as response:
                if response.status == 200:
                    logger.info("http_ready url=%s", url)
                    return
        except (urllib.error.URLError, TimeoutError) as exc:
            logger.info("http_wait_pending url=%s error=%s", url, exc)
            time.sleep(0.2)
    raise AssertionError(f"Dashboard server did not become ready: {url}")


def _current_tmux_pane_id() -> str | None:
    if not os.environ.get("TMUX"):
        return None
    result = sp.run(
        [tmux_bin(), "display-message", "-p", "#{pane_id}"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    pane_id = result.stdout.strip()
    return pane_id or None


def _preregister_session(
    server_base_url: str,
    name: str,
    tmux_pane: str,
    cwd: str,
    cli: str,
    transcript_path: str | None = None,
    dashboard_token: str | None = None,
) -> None:
    assert cli, f"cli is required for _preregister_session (name={name})"
    source_app_base = 'codex' if cli == 'codex' else 'claude'
    payload = {
        "source_app": f"{source_app_base}-pending",
        "session_id": f"pending-{name}",
        "hook_event_type": "SessionStart",
        "timestamp": int(time.time() * 1000),
        "name": name,
        "tmux_pane": tmux_pane,
        "cwd": cwd,
        "transcript_path": transcript_path,
    }
    if dashboard_token:
        payload["dashboard_token"] = dashboard_token
    request = urllib.request.Request(
        f"{server_base_url}/events",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "User-Agent": "VG-Start/1.0"},
    )
    time.sleep(0.5)
    with urllib.request.urlopen(request, timeout=1) as response:
        assert response.status == 200, f"Pre-register failed for {name}: {response.status}"
    logger.info("session_preregistered name=%s pane=%s", name, tmux_pane)


def _sync_alive_agent(
    server_base_url: str,
    name: str,
    source_app: str,
    session_id: str,
    tmux_pane: str,
    cwd: str,
    transcript_path: str | None = None,
    event_type: str = "SessionSync",
    dashboard_token: str | None = None,
) -> None:
    """Register an agent with its real session_id and lifecycle event."""
    payload = {
        "source_app": source_app,
        "session_id": session_id,
        "hook_event_type": event_type,
        "timestamp": int(time.time() * 1000),
        "name": name,
        "tmux_pane": tmux_pane,
        "cwd": cwd,
        "transcript_path": transcript_path,
    }
    if dashboard_token:
        payload["dashboard_token"] = dashboard_token
    request = urllib.request.Request(
        f"{server_base_url}/events",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "User-Agent": "VG-Start/1.0"},
    )
    with urllib.request.urlopen(request, timeout=1) as response:
        assert response.status == 200, f"Sync alive agent failed for {name}: {response.status}"
    logger.info("session_synced name=%s source_app=%s session_id=%s event=%s", name, source_app, session_id, event_type)


def _sync_resumed_agent(
    server_base_url: str,
    name: str,
    cli: str,
    session_id: str | None,
    tmux_pane: str,
    cwd: str,
    transcript_path: str | None = None,
    dashboard_token: str | None = None,
) -> None:
    if not session_id:
        return
    _sync_alive_agent(
        server_base_url,
        name,
        "codex" if cli == "codex" else "claude",
        session_id,
        tmux_pane,
        cwd,
        transcript_path=transcript_path,
        event_type="SessionStart",
        dashboard_token=dashboard_token,
    )


ALWAYS_START_AGENT_NAMES = ("artist", "designer")
RESTORABLE_AGENT_NAMES = {"reviewer"}
START_MANAGED_AGENT_NAMES = set(ALWAYS_START_AGENT_NAMES) | RESTORABLE_AGENT_NAMES


def _last_reviewer_start(log_path: Path) -> dict | None:
    logger.info("reviewer_history_read path=%s", log_path)
    if not log_path.exists():
        logger.info("reviewer_history_missing path=%s", log_path)
        return None

    last_reviewer = None
    entry_count = 0
    with log_path.open(encoding="utf-8") as log_file:
        for line_number, line in enumerate(log_file, start=1):
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"Invalid agents log JSON at {log_path}:{line_number}: {exc.msg}"
                ) from exc
            if not isinstance(entry, dict):
                raise ValueError(
                    f"Invalid agents log entry at {log_path}:{line_number}: expected object"
                )
            entry_count += 1
            if entry.get("role") == "mate" and entry.get("mate_name") == "reviewer":
                last_reviewer = entry

    logger.info(
        "reviewer_history_read_ok path=%s entries=%s reviewer_session=%s",
        log_path,
        entry_count,
        (last_reviewer or {}).get("session_id"),
    )
    return last_reviewer


def _startup_agent_names(reviewer_start: dict | None) -> tuple[str, ...]:
    names = list(ALWAYS_START_AGENT_NAMES)
    if reviewer_start:
        names.append("reviewer")
    return tuple(names)


def _is_temporal_agent(name: str, agent: dict | None) -> bool:
    agent = agent or {}
    agent_type = agent.get("agent_type") or name
    return name not in START_MANAGED_AGENT_NAMES and agent_type not in ALWAYS_START_AGENT_NAMES


def _delete_dashboard_session(server_base_url: str, composite_id: str) -> bool:
    request = urllib.request.Request(
        f"{server_base_url}/sessions/{urllib.parse.quote(composite_id, safe='')}",
        method="DELETE",
        headers={"User-Agent": "VG-Start/1.0"},
    )
    try:
        with urllib.request.urlopen(request, timeout=1) as response:
            return response.status == 200
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return False
        logger.info("dashboard_session_delete_failed id=%s code=%s", composite_id, exc.code)
        return False
    except (urllib.error.URLError, TimeoutError):
        logger.info("dashboard_session_delete_unreachable id=%s", composite_id)
        return False


def _dashboard_agent_session_ids(server_base_url: str, name: str, agent: dict) -> set[str]:
    try:
        with urllib.request.urlopen(f"{server_base_url}/sessions", timeout=1) as response:
            sessions = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return set()
    if not isinstance(sessions, list):
        return set()
    workdir = agent.get("workdir")
    ids: set[str] = set()
    for session in sessions:
        if not isinstance(session, dict):
            continue
        if session.get("name") != name:
            continue
        if workdir and session.get("working_dir") and session.get("working_dir") != workdir:
            continue
        session_id = session.get("id")
        if session_id:
            ids.add(session_id)
    return ids


def _delete_dashboard_agent_rows(server_base_url: str, name: str, agent: dict) -> int:
    candidates = {
        f"claude-pending:pending-{name}",
        f"codex-pending:pending-{name}",
    }
    session_id = agent.get("session_id")
    if session_id:
        candidates.add(f"claude:{session_id}")
        candidates.add(f"codex:{session_id}")
    candidates.update(_dashboard_agent_session_ids(server_base_url, name, agent))
    deleted = 0
    for composite_id in sorted(candidates):
        if _delete_dashboard_session(server_base_url, composite_id):
            deleted += 1
    return deleted


def _delete_dashboard_pending_rows(server_base_url: str, name: str) -> int:
    deleted = 0
    for composite_id in sorted({
        f"claude-pending:pending-{name}",
        f"codex-pending:pending-{name}",
    }):
        if _delete_dashboard_session(server_base_url, composite_id):
            deleted += 1
    return deleted


def _end_dashboard_agent_session(server_base_url: str, name: str, agent: dict) -> bool:
    session_id = agent.get("session_id")
    if not session_id:
        return False
    cli = agent.get("cli")
    source_app = "codex" if cli == "codex" else "claude"
    payload = {
        "source_app": source_app,
        "session_id": session_id,
        "hook_event_type": "SessionEnd",
        "timestamp": int(time.time() * 1000),
        "name": name,
        "tmux_pane": agent.get("pane_id"),
        "cwd": agent.get("workdir"),
        "transcript_path": agent.get("transcript_path"),
    }
    request = urllib.request.Request(
        f"{server_base_url}/events",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "User-Agent": "VG-Start/1.0"},
    )
    try:
        with urllib.request.urlopen(request, timeout=1) as response:
            return response.status == 200
    except (urllib.error.URLError, TimeoutError):
        logger.info("dashboard_session_end_unreachable name=%s session_id=%s", name, session_id)
        return False


def _reconcile_temporal_agents(
    *,
    server_base_url: str,
    prev_agents: dict,
    team_dir: Path,
    pane_is_running,
    remove_agent_fn,
) -> list[str]:
    """Remove dead temporal agents from state and move dashboard rows to ended."""
    removed: list[str] = []
    for name, agent in list(prev_agents.items()):
        if not _is_temporal_agent(name, agent):
            continue
        pane_id = agent.get("pane_id")
        if pane_id and pane_is_running(pane_id):
            continue
        remove_agent_fn(name, str(team_dir))
        _end_dashboard_agent_session(server_base_url, name, agent)
        _delete_dashboard_pending_rows(server_base_url, name)
        removed.append(name)
    return removed


def _agent_launch_mode(
    *,
    force_new: bool,
    state: dict | None,
    configured_cli: str | None,
    pane_alive: bool,
) -> tuple[str, str]:
    """Return alive/resume/fresh plus a concise reason."""
    if force_new:
        return "fresh", "new team"
    if not state:
        return "fresh", "no previous state"

    previous_cli = state.get("cli")
    session_id = state.get("session_id")

    if not previous_cli:
        return "fresh", "previous cli missing"
    cli_changed = previous_cli != configured_cli
    claude_family_switch = (
        cli_changed
        and isinstance(previous_cli, str)
        and isinstance(configured_cli, str)
        and previous_cli.startswith("claude")
        and configured_cli.startswith("claude")
    )
    if cli_changed and not claude_family_switch:
        return "fresh", f"cli changed: {previous_cli} -> {configured_cli}"
    # A live pane must be restarted when the Claude profile changes so the new
    # endpoint and credentials take effect. Resume its local Claude session in
    # the replacement pane instead of silently keeping the old profile alive.
    if claude_family_switch:
        pane_alive = False
    if pane_alive:
        return "alive", "pane alive"
    transcript_path = state.get("transcript_path")
    if isinstance(transcript_path, str) and transcript_path and not Path(transcript_path).is_file():
        return "fresh", "previous transcript missing"
    if not session_id:
        return "fresh", "previous session missing"
    if claude_family_switch:
        return "resume", f"compatible claude cli change: {previous_cli} -> {configured_cli}"
    return "resume", "matching previous session"


def _wait_for_expected_sessions(base_url: str, expected_names: set[str], timeout: float = 15.0) -> None:
    deadline = time.time() + timeout
    sessions_url = f"{base_url}/sessions"
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(sessions_url, timeout=1) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            logger.info("session_wait_pending url=%s error=%s", sessions_url, exc)
            time.sleep(0.25)
            continue
        seen = {
            item.get("name")
            for item in payload
            if isinstance(item, dict) and item.get("source_app") in ("claude", "codex")
        }
        if expected_names.issubset(seen):
            logger.info("session_wait_ready expected=%s seen=%s", sorted(expected_names), sorted(seen))
            return
        logger.info("session_wait_pending expected=%s seen=%s", sorted(expected_names), sorted(seen))
        time.sleep(0.25)
    raise AssertionError(f"Dashboard sessions missing. expected={sorted(expected_names)}")


def _assert_tmux_pane_alive(
    pane_id: str,
    role: str,
    timeout: float = 2.0,
    stable_for: float = 0.0,
) -> None:
    deadline = time.time() + timeout
    alive_since: float | None = None
    saw_pane = False
    while time.time() < deadline:
        dead = sp.run(
            [tmux_bin(), "display-message", "-p", "-t", pane_id, "#{pane_dead}"],
            capture_output=True,
            text=True,
        )
        if dead.returncode == 0 and dead.stdout.strip() == "1":
            output = sp.run(
                [tmux_bin(), "capture-pane", "-t", pane_id, "-p", "-S", "-80"],
                capture_output=True,
                text=True,
            ).stdout.strip()
            logger.error("pane_boot_failed role=%s pane=%s output=%s", role, pane_id, output)
            message = f"{role} pane died during boot: {pane_id}"
            if output:
                message += f"\nLast pane output:\n{output}"
            raise AssertionError(message)
        exists = sp.run(
            [tmux_bin(), "list-panes", "-a", "-F", "#{pane_id}"],
            capture_output=True,
            text=True,
        )
        now = time.time()
        exists_now = exists.returncode == 0 and pane_id in exists.stdout.splitlines()
        if exists_now:
            saw_pane = True
            if alive_since is None:
                alive_since = now
            if stable_for <= 0 or now - alive_since >= stable_for:
                return
        else:
            alive_since = None
            if saw_pane:
                logger.error("pane_boot_disappeared role=%s pane=%s", role, pane_id)
                raise AssertionError(f"{role} pane disappeared during boot: {pane_id}")
        time.sleep(0.05)
    if saw_pane and stable_for > 0:
        raise AssertionError(f"{role} pane did not stay alive for {stable_for:.1f}s during boot: {pane_id}")
    raise AssertionError(f"{role} pane missing after boot wait: {pane_id}")


def _dashboard_runtime_paths(project_path: Path) -> tuple[Path, Path]:
    runtime_dir = project_path / ".vibegame" / "dashboard"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    return runtime_dir / "dashboard.db", runtime_dir / "dashboard.log"


def _dashboard_token_option(token: str) -> str:
    """Format the token as one argv entry, even when it starts with a dash."""
    return f"--dashboard-token={shlex.quote(token)}"


def _clear_session_lock(project_path: Path) -> None:
    try:
        (project_path / ".vibegame" / ".session-lock").unlink(missing_ok=True)
    except OSError:
        logger.exception("session_lock_clear_failed")


def _write_launch_script(
    name: str,
    workdir: Path,
    env_vars: dict[str, str],
    command: str,
    *,
    use_exec: bool = True,
) -> str:
    """Write a launch script that records PID and runs the command.

    use_exec=True (default): exec replaces the shell (agents - pane lifecycle tied to process).
    use_exec=False: run as child process so the shell survives Ctrl+C (dashboard - restartable).
    """
    pid_dir = workdir / ".vibegame" / "team" / "pids"
    scripts_dir = workdir / ".vibegame" / "dashboard"
    scripts_dir.mkdir(parents=True, exist_ok=True)

    run_prefix = "exec " if use_exec else ""
    lines = [
        "#!/bin/sh",
        "set -e",
    ]
    for key, val in env_vars.items():
        lines.append(f"export {key}={shlex.quote(val)}")
    lines.extend([
        f"cd {shlex.quote(str(workdir))}",
        f"mkdir -p {shlex.quote(str(pid_dir))}",
        f"echo $$ > {shlex.quote(str(pid_dir / f'{name}.pid'))}",
        f"{run_prefix}{command}",
        "",
    ])

    if use_exec:
        fd, path = tempfile.mkstemp(prefix=f"vibegame-{name}-", suffix=".sh")
        os.close(fd)
        script = Path(path)
    else:
        # Stable path so the user can re-run it
        script = scripts_dir / f"{name}.sh"

    script.write_text("\n".join(lines), encoding="utf-8")
    script.chmod(0o700)
    return str(script)


@app.command("start")
def start(
    initial_input: list[str] | None = typer.Argument(
        None,
        metavar="[INPUT]...",
        help="Initial input sent to the orchestrator after startup",
    ),
    project: str = typer.Option(
        ".", "--project", help="Game project path (default: current dir)"
    ),
    host: str = typer.Option("localhost", "--host", help="Dashboard server host"),
    port: int | None = typer.Option(None, "--port", "-p", help="Exact dashboard server port. Omit to auto-select from 8080."),
    new: bool = typer.Option(False, "--new", help="Force fresh start, ignore previous session"),
    no_agents: bool = typer.Option(False, "--no-agents", help="Start dashboard only, no agent sessions"),
    debug: bool = typer.Option(False, "--debug", help="Debug mode: remain-on-exit for all panes, verbose logging"),
):
    """Launch VibeGame Dashboard and agent tmux sessions."""
    message = " ".join(initial_input or []).strip()
    if message and no_agents:
        raise typer.BadParameter("Initial input requires agents; remove --no-agents.")

    project_path = Path(project).resolve()
    log_file = _configure_logging(project_path, debug=debug)


    from cli.check import check_runtime
    rt_issues = check_runtime(project_path)
    rt_errors = [i for i in rt_issues if i.level == "error"]
    if rt_errors:
        for e in rt_errors:
            print(e)
        raise AssertionError(
            f"Runtime check failed ({len(rt_errors)} error(s)). "
            f"Run: vibegame init {shlex.quote(str(project_path))}"
        )

    server_py = Path(__file__).parent.parent / "web" / "server.py"

    # Import team modules
    team_dir = project_path / ".vibegame" / "team"
    team_dir.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(project_path / ".vibegame"))
    # Only project state lives here. tmux behaviour is imported from the source
    # tree at module scope, so it no longer depends on the project's vintage —
    # which is what the getattr fallback here used to paper over.
    try:
        from team.paths import default_session_name
        from team.state import init_state, load_state, remove_agent, set_dashboard_port, update_lead
    except ImportError:
        logger.exception("team_runtime_import_failed")
        raise AssertionError("team runtime modules not found in .vibegame/team/")

    def _pane_is_running(pane_id: str | None) -> bool:
        return bool(
            pane_id
            and pane_in_session(session_name, pane_id)
            and not pane_dead(pane_id)
        )

    # --- Read previous state ---
    prev_state = load_state(str(team_dir))
    prev_agents = prev_state.get("agents", {}) if not new else {}
    orch_session_id = prev_state.get("lead", {}).get("session_id") if not new else None

    team_start_mode = "new" if new else "per-agent"

    # --- Session ---
    inside_tmux = bool(os.environ.get("TMUX"))
    current_pane_id = _current_tmux_pane_id() if inside_tmux else None
    if inside_tmux:
        session_name = current_session_name()
        assert session_name, "Inside tmux but current session name is unavailable."
    else:
        session_name = default_session_name(str(team_dir))
        if session_exists(session_name) and not new:
            # Reuse session; per-agent reuse still requires the pane to belong to it.
            logger.info("reuse_existing_session session=%s", session_name)
        else:
            if session_exists(session_name):
                sp.run([tmux_bin(), "kill-session", "-t", session_target(session_name)], capture_output=True)
            create_session(session_name)
            logger.info("tmux_session_created session=%s", session_name)

    # --- Port ---
    requested_port = port
    connect_host = _connect_host(host)
    # Retire our previous dashboard before probing, or restarting on the same
    # --port always fails against the instance we are about to replace.
    _kill_dashboard(project_path, session_name)
    port = _select_port(host, requested_port, DEFAULT_PORT)

    print(f"Starting VibeGame Dashboard for {project_path.name}...")
    print(f"  Mode: {team_start_mode}")
    print(f"  Dashboard: http://{host}:{port}")
    # The event stream shares this port (ws://.../stream); no second listener.
    if connect_host != host:
        print(f"  Local control: http://{connect_host}:{port}")
    if requested_port is None:
        print(f"  Port: auto -> {port}")
    else:
        print(f"  Port: exact {port}")
    print(f"  Session: {session_name}")
    print(f"  Log: {log_file}")
    server_base_url = f"http://{connect_host}:{port}"

    # --- Init team state ---
    os.chdir(project_path)
    close_current_old_orchestrator_pane = False
    if new:
        prev_lead = prev_state.get("lead", {})
        prev_lead_pane = prev_lead.get("pane_id") if isinstance(prev_lead, dict) else None
        if (
            prev_lead_pane
            and prev_lead_pane != current_pane_id
            and pane_in_session(session_name, prev_lead_pane)
        ):
            kill_pane(prev_lead_pane)
            print(f"  Previous orchestrator: killed pane {prev_lead_pane}")
            logger.info("previous_orchestrator_killed pane=%s", prev_lead_pane)
        elif prev_lead_pane == current_pane_id:
            close_current_old_orchestrator_pane = True
            logger.info("previous_orchestrator_current_pane_skipped pane=%s", prev_lead_pane)
        if (team_dir / "messages.py").is_file():
            _run_lead(project_path, "close -f")
        _clear_session_lock(project_path)
    init_state(session_name, str(team_dir))
    if new:
        update_lead(
            explicit_team_dir=str(team_dir),
            pane_id=None,
            cli=None,
            model=None,
            command=None,
            session_id=None,
            transcript_path=None,
            last_transcript_at=None,
        )
    dashboard_token = secrets.token_urlsafe(24)
    set_dashboard_port(port, str(team_dir), token=dashboard_token)

    # --- Dashboard --- (already retired above, before port selection)
    db_path, dashboard_log_path = _dashboard_runtime_paths(project_path)
    reset_flag = " --reset-db" if new else ""
    dashboard_script = _write_launch_script(
        "dashboard", project_path,
        {},
        (
            f"{shlex.quote(sys.executable)} {shlex.quote(str(server_py))} server --port {port} "
            f"--host {shlex.quote(host)} "
            f"--project {shlex.quote(str(project_path))} "
            f"--db {shlex.quote(str(db_path))} "
            f"--log-file {shlex.quote(str(dashboard_log_path))}"
            f" {_dashboard_token_option(dashboard_token)}"
            f"{reset_flag}"
        ),
        use_exec=False,
    )
    dashboard_pane = new_window(
        session_name,
        name="dashboard",
        index=1,
    )
    logger.debug("dashboard_script path=%s", dashboard_script)
    if debug:
        set_remain_on_exit(dashboard_pane)
    dashboard_launch = f"/bin/sh {shlex.quote(dashboard_script)}"
    sp.run([tmux_bin(), "send-keys", "-t", dashboard_pane, dashboard_launch, "Enter"], capture_output=True)
    _assert_tmux_pane_alive(dashboard_pane, "dashboard")
    _wait_http_ready(f"{server_base_url}/status")

    removed_temporal = _reconcile_temporal_agents(
        server_base_url=server_base_url,
        prev_agents=prev_agents,
        team_dir=team_dir,
        pane_is_running=_pane_is_running,
        remove_agent_fn=remove_agent,
    )
    if removed_temporal:
        print(f"  Removed stale temporal agents: {', '.join(sorted(removed_temporal))}")

    # Open browser (best-effort; skip when the opener is absent, e.g. headless/container)
    url = f"http://{connect_host}:{port}"
    opener = "open" if sys.platform == "darwin" else "xdg-open"
    if shutil.which(opener):
        # Popen, not run: xdg-open may exec the browser in the foreground on
        # minimal Linux environments and would block startup until it exits.
        sp.Popen([opener, url], stdout=sp.DEVNULL, stderr=sp.DEVNULL)

    print(f"\n  tmux session: {session_name}")
    print(f"  Restart Dashboard: Ctrl+C in dashboard pane, then: {dashboard_script}")
    print(f"  Stop all: tmux kill-session -t {session_target(session_name)}")

    # --- Orchestrator FIRST ---
    # Start or resume orchestrator before mates so dashboard registration is stable.
    if not no_agents:
        from team.settings import resolve_agent_settings
        from team.launch import prepare_launch, build_initial_prompt_command, runtime_env_values, resolve_env_value

        _, orch_cli, orch_model = resolve_agent_settings(
            name="orchestrator", agent="orchestrator", model=None,
            explicit_team_dir=str(team_dir),
        )
        assert orch_cli, "Orchestrator CLI not configured. Run: vibegame setup"
        assert orch_model, "Orchestrator model not configured. Run: vibegame setup"

        # The initial input is written in the Claude form (`/vibegame-build ...`),
        # because that is what a user types and what a task's instruction.md holds.
        # Codex would take it as literal text, so rewrite before either delivery
        # path uses it -- the dashboard does the same for the prompts it sends.
        if message:
            rewritten = rewrite_leading_skill(orch_cli, message)
            if rewritten != message:
                logger.info("initial_input_skill_rewritten cli=%s head=%s",
                            orch_cli, rewritten.split(None, 1)[0])
                message = rewritten

        orch_lead = prev_state.get("lead", {}) if not new else {}
        prev_orch_pane = orch_lead.get("pane_id")
        orch_pane_alive = _pane_is_running(prev_orch_pane)
        orch_mode, orch_reason = _agent_launch_mode(
            force_new=new,
            state=orch_lead,
            configured_cli=orch_cli,
            pane_alive=orch_pane_alive,
        )

        if orch_mode != "alive" and orch_pane_alive:
            logger.info("orchestrator_restart pane=%s reason=%s", prev_orch_pane, orch_reason)
            kill_pane(prev_orch_pane)
            orch_pane_alive = False

        if orch_mode == "alive":
            input_target = prev_orch_pane
            logger.info("orchestrator_alive pane=%s skipping_spawn", prev_orch_pane)
            print(f"  Orchestrator: already running (pane {prev_orch_pane}), skipping spawn")
            _pane_label = resolve_pane_id(prev_orch_pane)
            if orch_session_id:
                cli = orch_lead.get("cli") or orch_cli
                _sync_alive_agent(
                    server_base_url, "orchestrator",
                    "codex" if cli == "codex" else "claude",
                    orch_session_id, _pane_label, str(project_path),
                    transcript_path=orch_lead.get("transcript_path"),
                    dashboard_token=dashboard_token,
                )
            else:
                _preregister_session(
                    server_base_url, "orchestrator", _pane_label, str(project_path),
                    cli=orch_cli,
                    transcript_path=orch_lead.get("transcript_path"),
                    dashboard_token=dashboard_token,
                )
        else:
            orch_base_cmd, orch_config, orch_model = prepare_launch(
                orch_cli, orch_model, agent="orchestrator",
                name="orchestrator", team_root=str(project_path),
            )

            # Append system prompt (orchestrator.md)
            orchestrator_content = (project_path / ".vibegame" / "orchestrator.md").read_text(encoding="utf-8").strip()
            sys_prompt_flag = orch_config.get("system_prompt_flag")
            if sys_prompt_flag:
                orch_base_cmd += f" {sys_prompt_flag} {shlex.quote(orchestrator_content)}"

            fresh_prompt = skill_invocation(orch_cli, "vibegame-start")
            fresh_orch_cmd = build_initial_prompt_command(orch_base_cmd, fresh_prompt, orch_config)

            # Resume first. Claude-family profile switches share Claude Code's
            # local session format; if the new endpoint rejects the resume,
            # fall back once to a fresh orchestrator in the same pane.
            if orch_mode == "resume" and orch_session_id:
                resume_val = orch_config.get("resume", "--resume")
                resume_cmd = f"{orch_base_cmd} {resume_val} {shlex.quote(orch_session_id)}"
                if orch_cli.startswith("claude"):
                    fallback_notice = shlex.quote(
                        "Claude resume failed; starting a fresh orchestrator session."
                    )
                    orch_cmd = (
                        f"{resume_cmd} || {{ echo {fallback_notice} >&2; "
                        f"exec {fresh_orch_cmd}; }}"
                    )
                else:
                    orch_cmd = resume_cmd
            else:
                orch_cmd = fresh_orch_cmd

            # Resolve env vars from .env
            runtime_env = runtime_env_values(str(team_dir))
            orch_env = {
                "VIBEGAME_ROLE": "orchestrator",
                "VIBEGAME_TEAM_DIR": str(team_dir),
            }
            for key, val in (orch_config.get("env") or {}).items():
                orch_env[key] = resolve_env_value(val, orch_model, runtime_env)

            orch_script = _write_launch_script(
                "orchestrator", project_path,
                orch_env,
                orch_cmd,
            )
            logger.debug("orchestrator_script path=%s cmd=%s", orch_script, orch_cmd)
            if orch_mode == "resume" and orch_session_id:
                print(f"  Orchestrator: resuming {orch_cli}/{orch_model} ({orch_session_id[:8]}...)")
            else:
                print(f"  Orchestrator: {orch_cli}/{orch_model} (fresh: {orch_reason})")
            orch_target = window_target(session_name, 0)
            orch_pane = split_window(orch_target, layout="even-horizontal")
            input_target = orch_pane
            if debug:
                set_remain_on_exit(orch_pane)
            orch_pane_label = resolve_pane_id(orch_pane)
            # Pre-register BEFORE sending the launch command so merge_pending
            # always has a pending row to clean up when SessionStart fires.
            _preregister_session(
                server_base_url,
                "orchestrator",
                orch_pane_label,
                str(project_path),
                cli=orch_cli,
                transcript_path=prev_state.get("lead", {}).get("transcript_path"),
                dashboard_token=dashboard_token,
            )
            # Clear stale session metadata BEFORE launching so the hook's
            # update_lead(session_id=real) is never overwritten by None.
            if orch_mode == "fresh":
                update_lead(
                    explicit_team_dir=str(team_dir),
                    session_id=None,
                    transcript_path=None,
                    last_transcript_at=None,
                )
            orch_launch = f"cd {shlex.quote(str(project_path))} && exec /bin/sh {shlex.quote(orch_script)}"
            sp.run([tmux_bin(), "send-keys", "-t", orch_pane, orch_launch, "Enter"], capture_output=True)
            _assert_tmux_pane_alive(
                orch_pane,
                "orchestrator",
                timeout=6.0,
                stable_for=AGENT_BOOT_STABLE_SECONDS,
            )
            if should_send_trust_enter(orch_config):
                send_trust_enter(orch_pane)
                _assert_tmux_pane_alive(
                    orch_pane,
                    "orchestrator",
                    timeout=2.0,
                    stable_for=0.5,
                )
            update_lead(
                explicit_team_dir=str(team_dir),
                pane_id=orch_pane, cli=orch_cli, model=orch_model,
            )
            if orch_mode == "resume" and orch_session_id:
                _sync_resumed_agent(
                    server_base_url,
                    "orchestrator",
                    orch_cli,
                    orch_session_id,
                    orch_pane_label,
                    str(project_path),
                    transcript_path=prev_state.get("lead", {}).get("transcript_path"),
                    dashboard_token=dashboard_token,
                )
            logger.info("orchestrator_boot_ok pane=%s mode=%s reason=%s", orch_pane, orch_mode, orch_reason)
            _wait_for_expected_sessions(server_base_url, {"orchestrator"}, timeout=30.0)

        if message:
            # Every CLI takes the same two steps: the startup skill at launch,
            # then the user's request as its own submission. Codex used to get
            # both fused into one launch argument because send-keys split
            # multi-line input; paste_prompt delivers it in one block instead.
            assert input_target, "Orchestrator pane unavailable for initial input."
            _send_initial_input(input_target, message)
            print(f"  Initial input: sent to orchestrator ({len(message)} chars)")
            logger.info("initial_input_sent pane=%s chars=%s", input_target, len(message))

    # --- Managed teammates (synchronous, split into window 0 by `vibegame lead`) ---
    if not no_agents and (team_dir / "messages.py").is_file():
        # Only wait for orchestrator here if we didn't already wait at line 596 above.
        # When orch was freshly spawned, we waited at 596 and don't need to wait again.
        # Filled per freshly launched role below; see the comment at the add site.
        wait_for: set[str] = set()

        reviewer_start = _last_reviewer_start(
            project_path / ".vibegame" / "logs" / "agents.jsonl"
        )
        startup_agent_names = _startup_agent_names(reviewer_start)
        for role in startup_agent_names:
            agent_state = prev_agents.get(role)
            if role == "reviewer" and agent_state is None:
                agent_state = reviewer_start
            _, configured_cli, configured_model = resolve_agent_settings(
                name=role, agent=role, model=None,
                explicit_team_dir=str(team_dir),
            )
            assert configured_cli, f"CLI not configured for {role}. Run: vibegame setup"
            sid = (agent_state or {}).get("session_id")
            pane_id = (agent_state or {}).get("pane_id", "")
            pane_alive = _pane_is_running(pane_id)
            agent_mode, agent_reason = _agent_launch_mode(
                force_new=new,
                state=agent_state,
                configured_cli=configured_cli,
                pane_alive=pane_alive,
            )

            # Already alive: skip spawn, sync to dashboard with real or pending session_id
            if agent_mode == "alive":
                print(f"  [{role}] already running (pane {pane_id}), skipping")
                mate_sid = agent_state.get("session_id")
                _pane_label = resolve_pane_id(pane_id)
                try:
                    if mate_sid:
                        previous_cli = agent_state.get("cli") or configured_cli
                        _sync_alive_agent(
                            server_base_url, role,
                            "codex" if previous_cli == "codex" else "claude",
                            mate_sid, _pane_label, str(project_path),
                            transcript_path=agent_state.get("transcript_path"),
                            dashboard_token=dashboard_token,
                        )
                    else:
                        _preregister_session(
                            server_base_url, role, _pane_label, str(project_path),
                            cli=configured_cli,
                            transcript_path=agent_state.get("transcript_path"),
                            dashboard_token=dashboard_token,
                        )
                except Exception:
                    pass
                continue

            if pane_alive:
                print(f"  [{role}] restarting (fresh: {agent_reason})")
                result = _run_lead(project_path, f"kill --name {shlex.quote(role)} -f", debug=debug)
                if result.returncode != 0:
                    kill_pane(pane_id)
                    remove_agent(role, str(team_dir))
            elif agent_state:
                # Stale state entry with no live pane (e.g. previous boot crash) — clear it.
                remove_agent(role, str(team_dir))

            # Dead or absent: determine resume flag
            resume_flag = ""
            if agent_mode == "resume" and sid:
                resume_flag = f"--resume {shlex.quote(sid)}"

            lead_args = (
                f"agent --agent-type {role} --name {role} "
                f"{resume_flag} "
                f"--prompt 'You are the {role}. Stand by for tasks.'"
            )
            print(f"  [{role}] vibegame lead {lead_args} ({agent_mode}: {agent_reason})")
            result = _run_lead(project_path, lead_args, debug=debug)
            if result.returncode != 0:
                logger.error("agent_boot_failed role=%s rc=%s stderr=%s", role, result.returncode, result.stderr.strip())
                print(f"  [{role}] FAILED (rc={result.returncode}): {result.stderr.strip()}")
                raise AssertionError(f"{role} launch failed")
            logger.info("agent_boot_ok role=%s stdout=%s", role, result.stdout.strip())
            print(f"  [{role}] OK: {result.stdout.strip()}")
            pane_marker = next(
                (token.split("=", 1)[1] for token in result.stdout.split() if token.startswith("pane=")),
                None,
            )
            assert pane_marker, f"{role} launch output missing pane marker: {result.stdout}"
            _preregister_session(
                server_base_url, role,
                resolve_pane_id(pane_marker),
                str(project_path),
                cli=configured_cli,
                transcript_path=(agent_state or {}).get("transcript_path"),
                dashboard_token=dashboard_token,
            )
            if agent_mode == "resume" and sid:
                _sync_resumed_agent(
                    server_base_url,
                    role,
                    configured_cli,
                    sid,
                    resolve_pane_id(pane_marker),
                    str(project_path),
                    transcript_path=(agent_state or {}).get("transcript_path"),
                    dashboard_token=dashboard_token,
                )
            # Only roles launched here. A role that was already alive is skipped
            # above, and when it has no session_id it gets a pending row only —
            # its process will never fire another SessionStart, so waiting on it
            # would time out on a teammate that is in fact healthy.
            wait_for.add(role)

        print(f"  Agents: {', '.join(startup_agent_names)} (per-agent)")
        _wait_for_expected_sessions(server_base_url, wait_for)

    if close_current_old_orchestrator_pane and current_pane_id:
        logger.info("previous_orchestrator_current_pane_scheduled_close pane=%s", current_pane_id)
        sp.Popen(
            ["sh", "-c", f"sleep 1; {shlex.quote(tmux_bin())} kill-pane -t {shlex.quote(current_pane_id)}"],
            stdout=sp.DEVNULL,
            stderr=sp.DEVNULL,
        )
    elif not inside_tmux:
        os.execvp(tmux_bin(), [tmux_bin(), "attach-session", "-t", session_target(session_name)])
