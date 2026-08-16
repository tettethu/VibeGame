"""VibeGame play - Runtime API CLI wrapper.

Usage:
    vibegame play [--port PORT] <command> [ARGS]...

Wraps runtime REST API into simple CLI commands.
Discovers running server from .vibegame/logs/runtime/servers.json.
"""

import json
import os
import shlex
import sys
import tempfile
from datetime import datetime
from pathlib import Path

import click
import requests
import typer

from util.runtime import DEFAULT_RUNTIME_PORT

play_app = typer.Typer(
    name="play",
    no_args_is_help=True,
    help="Runtime API CLI wrapper for game interaction",
    rich_markup_mode=None,
    pretty_exceptions_enable=False,
)

TRACES_DIR = ".vibegame/traces"
RECORDING_FILE = ".recording"
PLAY_PORT: int | None = None
# When set (during `batch`), `_base_url` returns it instead of re-resolving the
# server from servers.json on every op — one resolution for the whole batch.
_BATCH_BASE_URL: str | None = None


@play_app.callback()
def play_callback(
    port: int | None = typer.Option(None, "--port", help="Runtime server port"),
):
    """Configure shared options for play subcommands."""
    global PLAY_PORT
    PLAY_PORT = port


def _resolve_path(path: str) -> Path:
    return Path(path).resolve()


# --- Batch ---


def _read_batch_ops(source: str | None) -> list[str]:
    """Read batch ops. `@file` reads a file; a bare string is inline; otherwise stdin.

    Ops are one command per line (the same format `record` writes to play.sh).
    Blank lines and `#` comments are skipped. As a convenience, a single-line
    inline string may use `;` to separate ops (do not use `;` with eval — its JS
    contains semicolons; use the newline/file form instead).
    """
    if source and source.startswith("@"):
        text = Path(source[1:]).read_text(encoding="utf-8")
    elif source is not None:
        text = source
    else:
        if sys.stdin.isatty():
            typer.echo("Provide ops as @file, inline string, or pipe to stdin", err=True)
            raise typer.Exit(1)
        text = sys.stdin.read()

    if "\n" not in text and ";" in text:
        raw = text.split(";")
    else:
        raw = text.splitlines()
    ops = []
    for line in raw:
        line = line.strip()
        # tolerate replay-format lines that prefix commands with `run `
        if line.startswith("run "):
            line = line[4:].strip()
        # drop a leading `vibegame play` so both raw verbs and full commands work
        if line.startswith("vibegame play "):
            line = line[len("vibegame play "):].strip()
        if not line or line.startswith("#"):
            continue
        ops.append(line)
    return ops


def _expand_at_files(argv: list[str]) -> list[str]:
    """Replace any `@path` token with that file's text (used for `eval @script.js`)."""
    out = []
    for tok in argv:
        if tok.startswith("@") and len(tok) > 1:
            out.append(Path(tok[1:]).read_text(encoding="utf-8"))
        else:
            out.append(tok)
    return out


def _batch_snapshot() -> dict | None:
    """Best-effort current snapshot for failure reports."""
    try:
        resp = _api("GET", "snapshot")
        if resp.status_code == 200:
            return resp.json()
    except Exception:
        return None
    return None


@play_app.command("batch")
def play_batch(
    source: str = typer.Argument(
        None, help="@file, inline op string, or omit to read stdin (one `vibegame play` command per line)"
    ),
):
    """Run a sequence of play commands in one process (no per-command CLI startup).

    Halts on the first failing op and reports which op failed plus the current
    snapshot, so control returns to the caller to debug step by step.
    """
    global _BATCH_BASE_URL
    ops = _read_batch_ops(source)
    if not ops:
        typer.echo(json.dumps({"ok": True, "ran": 0}))
        return

    group = typer.main.get_command(play_app)
    subcommands = group.commands  # name -> click.Command
    _BATCH_BASE_URL = _base_url(".")  # resolve the server once for the whole batch
    try:
        for idx, line in enumerate(ops, 1):
            verb = shlex.split(line)[0]
            if verb == "eval":
                # everything after `eval` is raw JS (may contain ; and quotes);
                # `@file` loads the code from a file. No shlex splitting of the body.
                code = line[len(verb):].strip()
                rest = [_expand_at_files([code])[0]] if code else []
            else:
                rest = _expand_at_files(shlex.split(line)[1:])
            cmd = subcommands.get(verb)
            typer.echo(f"# [{idx}] {line}")
            if cmd is None:
                _batch_fail(idx, line, f"unknown play command: {verb!r}")
            try:
                ctx = cmd.make_context(verb, rest)
                cmd.invoke(ctx)
            except click.exceptions.Exit as e:
                if (e.exit_code or 0) != 0:
                    _batch_fail(idx, line, f"op exited {e.exit_code}")
            except (click.ClickException, SystemExit) as e:
                _batch_fail(idx, line, str(e))
            except Exception as e:  # runtime/HTTP error mid-op
                _batch_fail(idx, line, repr(e))
    finally:
        _BATCH_BASE_URL = None

    typer.echo(json.dumps({"ok": True, "ran": len(ops)}))


def _batch_fail(idx: int, line: str, error: str) -> None:
    report = {
        "ok": False,
        "failed_op": idx,
        "command": line,
        "error": error,
        "snapshot": _batch_snapshot(),
    }
    typer.echo(json.dumps(report, indent=2), err=True)
    raise typer.Exit(1)


def _base_url(project_path: str = ".") -> str:
    if _BATCH_BASE_URL is not None:
        return _BATCH_BASE_URL
    from cli.run import _prune_stale_servers

    p = _resolve_path(project_path)
    servers = _prune_stale_servers(p)
    if not servers:
        typer.echo("No running server found. Start with: vibegame run", err=True)
        raise typer.Exit(1)
    if PLAY_PORT is not None:
        server = servers.get(str(PLAY_PORT))
        if not server:
            typer.echo(f"No running server found on port {PLAY_PORT}.", err=True)
            raise typer.Exit(1)
        first = server
    else:
        if len(servers) > 1:
            ports = ", ".join(sorted(servers.keys(), key=lambda v: int(v) if v.isdigit() else v))
            typer.echo(f"Multiple runtime servers found: {ports}. Specify: vibegame play --port <PORT> ...", err=True)
            raise typer.Exit(1)
        first = next(iter(servers.values()))
    host = first.get("host", "127.0.0.1")
    port = first.get("port", DEFAULT_RUNTIME_PORT)
    return f"http://{host}:{port}"


def _api(method: str, endpoint: str, project_path: str = ".", **kwargs) -> requests.Response:
    url = f"{_base_url(project_path)}/api/runtime/{endpoint}"
    fn = requests.get if method == "GET" else requests.post
    kwargs.setdefault("timeout", 30)
    return fn(url, **kwargs)


def _print_json(resp: requests.Response) -> None:
    if resp.status_code != 200:
        typer.echo(f"Error {resp.status_code}: {resp.text}", err=True)
        raise typer.Exit(1)
    try:
        typer.echo(json.dumps(resp.json(), indent=2))
    except json.JSONDecodeError:
        typer.echo(resp.text)


# --- Recording ---


def _recording_state(project_path: str = ".") -> dict | None:
    """Load recording state from marker file, or None if not recording."""
    p = _resolve_path(project_path) / TRACES_DIR / RECORDING_FILE
    if p.exists():
        return json.loads(p.read_text())
    return None


def _save_recording_state(state: dict, project_path: str = ".") -> None:
    p = _resolve_path(project_path) / TRACES_DIR / RECORDING_FILE
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(state))


def _clear_recording(project_path: str = ".") -> None:
    p = _resolve_path(project_path) / TRACES_DIR / RECORDING_FILE
    if p.exists():
        p.unlink()


def _record(project_path: str, *cmd_parts: str) -> None:
    """Append command to recording script if active."""
    state = _recording_state(project_path)
    if not state:
        return
    state["step"] = state.get("step", 0) + 1
    _save_recording_state(state, project_path)
    script = Path(state["script_path"])
    parts = list(cmd_parts)
    record_port = PLAY_PORT if PLAY_PORT is not None else state.get("port")
    if record_port is not None and parts[:2] == ["vibegame", "play"] and "--port" not in parts:
        parts = parts[:2] + ["--port", str(record_port)] + parts[2:]
    cmd = " ".join(shlex.quote(p) for p in parts if p)
    with open(script, "a") as f:
        f.write(f"run {cmd}\n")


def _record_screenshot(project_path: str) -> None:
    """Record screenshot with trace-relative output path."""
    state = _recording_state(project_path)
    if not state:
        return
    step = state.get("step", 0) + 1
    state["step"] = step
    _save_recording_state(state, project_path)
    script = Path(state["script_path"])
    record_port = PLAY_PORT if PLAY_PORT is not None else state.get("port")
    if record_port is None:
        cmd = f'run vibegame play screenshot -o "$TRACE_DIR/logs/step_{step:03d}.png"'
    else:
        cmd = f'run vibegame play --port {record_port} screenshot -o "$TRACE_DIR/logs/step_{step:03d}.png"'
    with open(script, "a") as f:
        f.write(f"{cmd}\n")


# --- Subcommands ---


@play_app.command("record")
def play_record(
    name: str = typer.Argument(None, help="Trace name (required to start)"),
    stop: bool = typer.Option(False, "--stop", help="Stop recording"),
    path: str = typer.Argument(".", help="Game project path"),
):
    """Record play commands to a reusable trace script."""
    if stop:
        state = _recording_state(path)
        if not state:
            typer.echo("Not recording.", err=True)
            raise typer.Exit(1)
        script = Path(state["script_path"])
        record_port = PLAY_PORT if PLAY_PORT is not None else state.get("port")
        with open(script, "a") as f:
            if record_port is None:
                f.write('\nrun vibegame play deactivate\n')
            else:
                f.write(f'\nrun vibegame play --port {record_port} deactivate\n')
            f.write('echo "=== Trace complete ===" >> "$LOG"\n')
        _clear_recording(path)
        typer.echo(f"Recording saved: {script}")
        typer.echo(
            "\nREMINDER: Review and clean up unnecessary steps:\n"
            "  - Remove redundant activate/deactivate\n"
            "  - Remove exploratory steps that aren't part of the test story\n"
            f"\nRun directly: bash {script}"
        )
        return

    if not name:
        typer.echo("Usage: vibegame play record <name>", err=True)
        raise typer.Exit(1)

    if _recording_state(path):
        typer.echo("Already recording. Stop first: vibegame play record --stop", err=True)
        raise typer.Exit(1)

    root = _resolve_path(path)
    trace_dir = root / TRACES_DIR / name
    logs_dir = trace_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    # Clear previous evidence
    for f in logs_dir.iterdir():
        f.unlink()

    script_path = trace_dir / "play.sh"
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    activate_cmd = "vibegame play activate" if PLAY_PORT is None else f"vibegame play --port {PLAY_PORT} activate"

    script_path.write_text(
        f'''#!/bin/bash
# Trace: {name}
# Recorded: {now}
#
# Edit this script to remove unnecessary steps before sharing.
set -e

TRACE_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG="$TRACE_DIR/logs/output.log"
mkdir -p "$TRACE_DIR/logs"

run() {{
    echo "--- $* ---" >> "$LOG"
    "$@" 2>&1 | tee -a "$LOG"
}}

echo "=== Trace: {name} - $(date) ===" > "$LOG"

run {activate_cmd}
'''
    )
    script_path.chmod(0o755)

    _save_recording_state(
        {"name": name, "script_path": str(script_path), "step": 0, "port": PLAY_PORT},
        path,
    )

    typer.echo(f"Recording to: {script_path}")
    typer.echo("Run 'vibegame play record --stop' when done.")


@play_app.command("screenshot")
def play_screenshot(
    output: str = typer.Option(None, "--output", "-o", help="Output file path (default: temp)"),
    path: str = typer.Argument(".", help="Game project path"),
):
    """Capture screenshot to file, print path to stdout."""
    resp = _api("GET", "screenshot", path)
    if resp.status_code != 200:
        typer.echo(f"Error {resp.status_code}: {resp.text}", err=True)
        raise typer.Exit(1)
    if output:
        out_path = Path(output)
    else:
        fd, tmp = tempfile.mkstemp(suffix=".png", prefix="vibegame-")
        os.close(fd)
        out_path = Path(tmp)
    out_path.write_bytes(resp.content)
    typer.echo(str(out_path))
    _record_screenshot(path)


@play_app.command("snapshot")
def play_snapshot(
    path: str = typer.Argument(".", help="Game project path"),
):
    """Print JSON snapshot of runtime state."""
    _print_json(_api("GET", "snapshot", path))
    _record(path, "vibegame", "play", "snapshot")


@play_app.command("activate")
def play_activate(
    path: str = typer.Argument(".", help="Game project path"),
):
    """Activate runtime control mode. Game pauses immediately."""
    _print_json(_api("POST", "activate", path))
    _record(path, "vibegame", "play", "activate")


@play_app.command("deactivate")
def play_deactivate(
    path: str = typer.Argument(".", help="Game project path"),
):
    """Deactivate runtime control mode."""
    _print_json(_api("POST", "deactivate", path))
    _record(path, "vibegame", "play", "deactivate")


@play_app.command("eval")
def play_eval(
    code: str = typer.Argument(None, help="JS code to evaluate (reads stdin if omitted)"),
    path: str = typer.Argument(".", help="Game project path"),
):
    """Evaluate JS in engine context. Reads from stdin if no code argument."""
    if code is None:
        if sys.stdin.isatty():
            typer.echo("Provide code as argument or pipe to stdin", err=True)
            raise typer.Exit(1)
        code = sys.stdin.read()
    _print_json(_api("POST", "eval", path, json={"code": code}))
    _record(path, "vibegame", "play", "eval", code)


@play_app.command("pause")
def play_pause(
    path: str = typer.Argument(".", help="Game project path"),
):
    """Pause the game."""
    _print_json(_api("POST", "pause", path))
    _record(path, "vibegame", "play", "pause")


@play_app.command("continue")
def play_continue(
    frames: int = typer.Option(60, "--frames", "-f", help="Number of frames to advance"),
    path: str = typer.Argument(".", help="Game project path"),
):
    """Advance N frames then pause."""
    _print_json(_api("POST", "continue", path, json={"frames": frames}))
    _record(path, "vibegame", "play", "continue", "-f", str(frames))


@play_app.command("play")
def play_play(
    path: str = typer.Argument(".", help="Game project path"),
):
    """Resume free-running playback."""
    _print_json(_api("POST", "play", path))
    _record(path, "vibegame", "play", "play")


@play_app.command("status")
def play_status(
    path: str = typer.Argument(".", help="Game project path"),
):
    """Show runtime controller status."""
    _print_json(_api("GET", "status", path))
    _record(path, "vibegame", "play", "status")


@play_app.command("refresh")
def play_refresh(
    path: str = typer.Argument(".", help="Game project path"),
):
    """Reload the browser page."""
    resp = _api("POST", "refresh", path, timeout=90)
    _print_json(resp)
    _record(path, "vibegame", "play", "refresh")


@play_app.command("console")
def play_console(
    level: str = typer.Option(None, "--level", "-l", help="Filter: error|warn|info|log"),
    since: int = typer.Option(None, "--since", "-s", help="Sequence number to fetch from"),
    clear: bool = typer.Option(False, "--clear", help="Clear console buffer"),
    path: str = typer.Argument(".", help="Game project path"),
):
    """Show or clear console log entries."""
    if clear:
        _print_json(_api("POST", "console/clear", path))
        _record(path, "vibegame", "play", "console", "--clear")
        return
    params = {}
    if level:
        params["level"] = level
    if since is not None:
        params["since"] = since
    _print_json(_api("GET", "console", path, params=params))
    parts = ["vibegame", "play", "console"]
    if level:
        parts.extend(["-l", level])
    if since is not None:
        parts.extend(["-s", str(since)])
    _record(path, *parts)


@play_app.command("input")
def play_input(
    action: str = typer.Option(..., "--action", "-a", help="Input action name from input-map"),
    held: bool = typer.Option(False, "--held", help="Hold the input"),
    release: bool = typer.Option(False, "--release", help="Release held input"),
    path: str = typer.Argument(".", help="Game project path"),
):
    """Inject input action."""
    body: dict = {"action": action}
    if release:
        body["held"] = False
    elif held:
        body["held"] = True
    _print_json(_api("POST", "input", path, json=body))
    parts = ["vibegame", "play", "input", "-a", action]
    if release:
        parts.append("--release")
    elif held:
        parts.append("--held")
    _record(path, *parts)


@play_app.command("set")
def play_set(
    node: str = typer.Option(..., "--node", "-n", help="Node ID"),
    prop_path: str = typer.Option(..., "--path", "-p", help="Property path (e.g. x, config.hp)"),
    value: str = typer.Option(..., "--value", "-v", help="Value (JSON or string)"),
    path: str = typer.Argument(".", help="Game project path"),
):
    """Set a node property."""
    try:
        parsed_value = json.loads(value)
    except (json.JSONDecodeError, TypeError):
        parsed_value = value
    _print_json(_api("POST", "set", path, json={"nodeId": node, "path": prop_path, "value": parsed_value}))
    _record(path, "vibegame", "play", "set", "-n", node, "-p", prop_path, "-v", value)


@play_app.command("click")
def play_click(
    x: float = typer.Option(..., "--x", "-x", help="X coordinate"),
    y: float = typer.Option(..., "--y", "-y", help="Y coordinate"),
    path: str = typer.Argument(".", help="Game project path"),
):
    """Simulate a click."""
    _print_json(_api("POST", "click", path, json={"x": x, "y": y}))
    _record(path, "vibegame", "play", "click", "-x", str(x), "-y", str(y))


@play_app.command("mousemove")
def play_mousemove(
    x: float = typer.Option(..., "--x", "-x", help="X coordinate"),
    y: float = typer.Option(..., "--y", "-y", help="Y coordinate"),
    path: str = typer.Argument(".", help="Game project path"),
):
    """Move pointer to game-world coordinates."""
    _print_json(_api("POST", "mousemove", path, json={"x": x, "y": y}))
    _record(path, "vibegame", "play", "mousemove", "-x", str(x), "-y", str(y))


@play_app.command("drag")
def play_drag(
    from_x: float = typer.Option(..., "--from-x", help="Start X"),
    from_y: float = typer.Option(..., "--from-y", help="Start Y"),
    to_x: float = typer.Option(..., "--to-x", help="End X"),
    to_y: float = typer.Option(..., "--to-y", help="End Y"),
    path: str = typer.Argument(".", help="Game project path"),
):
    """Drag between two game-world coordinates."""
    _print_json(_api("POST", "drag", path, json={"fromX": from_x, "fromY": from_y, "toX": to_x, "toY": to_y}))
    _record(path, "vibegame", "play", "drag", "--from-x", str(from_x), "--from-y", str(from_y), "--to-x", str(to_x), "--to-y", str(to_y))


@play_app.command("network")
def play_network(
    clear: bool = typer.Option(False, "--clear", help="Clear network buffer"),
    path: str = typer.Argument(".", help="Game project path"),
):
    """Show or clear network request entries."""
    if clear:
        _print_json(_api("POST", "network/clear", path))
        _record(path, "vibegame", "play", "network", "--clear")
        return
    _print_json(_api("GET", "network", path))
    _record(path, "vibegame", "play", "network")


@play_app.command("key")
def play_key(
    code: str = typer.Option(..., "--code", "-c", help="Key code (e.g. Space, ArrowUp, KeyA)"),
    type_: str = typer.Option("press", "--type", "-t", help="press|down|up"),
    path: str = typer.Argument(".", help="Game project path"),
):
    """Simulate a keyboard event."""
    _print_json(_api("POST", "key", path, json={"key": code, "type": type_}))
    parts = ["vibegame", "play", "key", "-c", code]
    if type_ != "press":
        parts.extend(["-t", type_])
    _record(path, *parts)
