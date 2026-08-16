import http.server
import json
import os
import queue
import secrets
import signal
import shutil
import socket
import subprocess as sp
import sys
import threading
import time
from pathlib import Path
from urllib.parse import quote

import typer

from cli.router import app
from util.runtime import DEFAULT_RUNTIME_PORT


# Query keys the engine boot path (src/engine/boot.js) reads off location.search.
# User passthrough params (`vibegame run . -- k=v`, bot META["params"]) must not
# use these, or a game param would silently hijack engine runtime control.
# KEEP IN SYNC with boot.js: if the engine starts reading a new query key, add it
# here so passthrough validation keeps rejecting it.
RESERVED_QUERY_KEYS = frozenset({"runtime", "activate", "debug", "physicsDebug", "renderer", "fps"})
RENDERER_CHOICES = frozenset({"auto", "webgl", "canvas"})


def _parse_cli_query_tokens(tokens: list[str]) -> dict[str, str]:
    """Parse `key=value` passthrough tokens captured after `--`. Fail loud on bad shape."""
    out: dict[str, str] = {}
    for tok in tokens:
        if "=" not in tok:
            print(f"Error: passthrough arg must be key=value, got: {tok!r}")
            raise typer.Exit(1)
        key, value = tok.split("=", 1)
        key = key.strip()
        if not key:
            print(f"Error: passthrough arg has empty key: {tok!r}")
            raise typer.Exit(1)
        out[key] = value
    return out


def _validate_passthrough_params(params: dict[str, str], source: str) -> None:
    """Reject reserved-key collisions. Fail loud rather than letting a game param
    override an engine query key."""
    clash = sorted(set(params) & RESERVED_QUERY_KEYS)
    if clash:
        print(
            f"Error: {source} uses reserved query key(s): {', '.join(clash)}. "
            f"Reserved keys: {', '.join(sorted(RESERVED_QUERY_KEYS))}."
        )
        raise typer.Exit(1)


def _normalize_renderer(value: str) -> str:
    renderer = value.strip().lower()
    if renderer not in RENDERER_CHOICES:
        print(f"Error: --renderer must be one of: {', '.join(sorted(RENDERER_CHOICES))}")
        raise typer.Exit(1)
    return renderer


def _normalize_fps(value: int | None) -> int | None:
    """None = engine decides (project settings.fpsLimit, else 60 for runtime sessions).
    0 = explicitly uncapped. >0 = render fps cap for this session."""
    if value is None:
        return None
    if value < 0:
        print("Error: --fps must be >= 0 (0 = uncapped)")
        raise typer.Exit(1)
    return value


SOURCE_ENGINE_DIR = Path(__file__).resolve().parent.parent / "engine"


def _engine_fallback_warning(project_path: Path) -> list[str]:
    if (project_path / "engine").is_dir():
        return []
    if not SOURCE_ENGINE_DIR.is_dir():
        return []
    return [
        "Warning: using source engine fallback because this project has no ./engine directory.",
        "This is only for runnable skeletons. If this is a game project, run vibegame init first so ./engine is copied into the project root.",
    ]


def _runtime_logs_dir(project_path: Path) -> Path:
    return project_path / ".vibegame" / "logs" / "runtime"


def _legacy_runtime_logs_dir(project_path: Path) -> Path:
    return project_path / "logs"


def _servers_info_path(project_path: Path) -> Path:
    return _runtime_logs_dir(project_path) / "servers.json"


def _server_log_path(project_path: Path, port: int = DEFAULT_RUNTIME_PORT) -> Path:
    return _runtime_logs_dir(project_path) / f"server-{port}.log"


def _legacy_server_log_candidates(project_path: Path, port: int) -> list[Path]:
    legacy_dir = _legacy_runtime_logs_dir(project_path)
    return [
        legacy_dir / f"server-{port}.log",
        legacy_dir / "server.log",
    ]


def _display_server_log_path(project_path: Path, port: int) -> Path:
    current = _server_log_path(project_path, port)
    if current.exists():
        return current
    for candidate in _legacy_server_log_candidates(project_path, port):
        if candidate.exists():
            return candidate
    return current


def _normalize_server_entry(entry: dict, *, background_default: bool) -> dict:
    normalized = dict(entry)
    background = normalized.setdefault("background", background_default)
    legacy_pid = _coerce_pid(normalized.get("pid"))
    server_pid = _coerce_pid(normalized.get("server_pid"))
    launcher_pid = _coerce_pid(normalized.get("launcher_pid"))

    if background:
        server_pid = server_pid or legacy_pid
        launcher_pid = 0
        primary_pid = server_pid
    else:
        server_pid = server_pid or legacy_pid
        primary_pid = launcher_pid or server_pid or legacy_pid

    normalized["server_pid"] = server_pid
    normalized["launcher_pid"] = launcher_pid
    normalized["pid"] = primary_pid
    return normalized


def _coerce_pid(value: object) -> int:
    try:
        pid = int(value)
    except (TypeError, ValueError):
        return 0
    return pid if pid > 0 else 0


def _server_pid(info: dict) -> int:
    return _coerce_pid(info.get("server_pid") or info.get("pid"))


def _launcher_pid(info: dict) -> int:
    if info.get("background", True):
        return 0
    return _coerce_pid(info.get("launcher_pid"))


def _tracked_pid(info: dict) -> int:
    if info.get("background", True):
        return _server_pid(info)
    return _launcher_pid(info) or _server_pid(info)


def _pid_summary(info: dict) -> str:
    if info.get("background", True):
        server_pid = _server_pid(info)
        return f"Server PID: {server_pid}" if server_pid else "Server PID: ?"

    parts: list[str] = []
    launcher_pid = _launcher_pid(info)
    server_pid = _server_pid(info)
    if launcher_pid:
        parts.append(f"Launcher PID: {launcher_pid}")
    if server_pid:
        parts.append(f"Server PID: {server_pid}")
    return "  ".join(parts) if parts else "PID: ?"


def _write_all_servers(project_path: Path, servers: dict[str, dict]) -> None:
    info_file = _servers_info_path(project_path)
    if servers:
        info_file.parent.mkdir(parents=True, exist_ok=True)
        info_file.write_text(json.dumps(servers), encoding="utf-8")
    else:
        info_file.unlink(missing_ok=True)


def _is_server_entry_stale(info: dict) -> bool:
    host = info.get("host", "127.0.0.1")
    port = info.get("port")
    tracked_pids = {_tracked_pid(info), _launcher_pid(info), _server_pid(info)}
    daemon_pid = _coerce_pid(info.get("daemon_pid"))
    if daemon_pid:
        tracked_pids.add(daemon_pid)
    if any(pid and _is_process_alive(pid) for pid in tracked_pids):
        return False
    if not isinstance(port, int) or port <= 0:
        return True
    return not _is_port_in_use(host, port)


def _prune_stale_servers(project_path: Path) -> dict[str, dict]:
    servers = _read_all_servers(project_path)
    cleaned = {port_key: info for port_key, info in servers.items() if not _is_server_entry_stale(info)}
    if cleaned != servers:
        _write_all_servers(project_path, cleaned)
    return cleaned


def _migrate_old_server_info(project_path: Path) -> None:
    """Migrate runtime state from legacy logs/ to .vibegame/logs/runtime/."""
    new_path = _servers_info_path(project_path)
    legacy_dir = _legacy_runtime_logs_dir(project_path)
    legacy_multi = legacy_dir / "servers.json"
    legacy_single = legacy_dir / "server.json"

    merged: dict[str, dict] = {}
    if new_path.exists():
        try:
            existing = json.loads(new_path.read_text(encoding="utf-8"))
            if isinstance(existing, dict):
                merged.update(existing)
        except (json.JSONDecodeError, OSError):
            pass

    migrated = False

    if legacy_multi.exists():
        try:
            data = json.loads(legacy_multi.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                for port_key, entry in data.items():
                    if isinstance(entry, dict) and str(port_key) not in merged:
                        merged[str(port_key)] = _normalize_server_entry(entry, background_default=True)
                        migrated = True
        except (json.JSONDecodeError, OSError):
            pass
        legacy_multi.unlink(missing_ok=True)

    if legacy_single.exists():
        try:
            entry = json.loads(legacy_single.read_text(encoding="utf-8"))
            if isinstance(entry, dict):
                normalized = _normalize_server_entry(entry, background_default=True)
                port_key = str(normalized.get("port", DEFAULT_RUNTIME_PORT))
                if port_key not in merged:
                    merged[port_key] = normalized
                    migrated = True
        except (json.JSONDecodeError, OSError):
            pass
        legacy_single.unlink(missing_ok=True)

    if migrated:
        new_path.parent.mkdir(parents=True, exist_ok=True)
        new_path.write_text(json.dumps(merged), encoding="utf-8")


def _read_all_servers(project_path: Path) -> dict:
    """Return {port_str: {pid, launcher_pid, server_pid, host, port, background}, ...}."""
    _migrate_old_server_info(project_path)
    info_file = _servers_info_path(project_path)
    if not info_file.exists():
        return {}
    try:
        data = json.loads(info_file.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return {}
        return {
            str(port_key): _normalize_server_entry(entry, background_default=True)
            for port_key, entry in data.items()
            if isinstance(entry, dict)
        }
    except (json.JSONDecodeError, OSError):
        return {}


def _read_server_info(project_path: Path, port: int) -> dict | None:
    return _read_all_servers(project_path).get(str(port))


def _tracked_server_lines(project_path: Path) -> list[str]:
    lines: list[str] = []
    servers = _prune_stale_servers(project_path)
    for _port_key, info in sorted(servers.items(), key=lambda x: int(x[0])):
        pid = _tracked_pid(info)
        alive = _is_process_alive(pid) if pid else False
        s_host, s_port = info.get("host", "?"), info.get("port", "?")
        mode = "background" if info.get("background", True) else "foreground"
        state = "running" if alive else "dead"
        lines.append(
            f"Port {s_port}: {state}  {mode}  {_pid_summary(info)}  Address: http://{s_host}:{s_port}"
        )
    return lines


def _write_server_info(
    project_path: Path,
    *,
    host: str,
    port: int,
    background: bool,
    server_pid: int,
    launcher_pid: int = 0,
) -> None:
    servers = _read_all_servers(project_path)
    servers[str(port)] = _normalize_server_entry(
        {
            "pid": launcher_pid if not background else server_pid,
            "launcher_pid": launcher_pid,
            "server_pid": server_pid,
            "host": host,
            "port": port,
            "background": background,
        },
        background_default=background,
    )
    _write_all_servers(project_path, servers)


def _remove_server_info(project_path: Path, port: int) -> None:
    servers = _read_all_servers(project_path)
    servers.pop(str(port), None)
    _write_all_servers(project_path, servers)


def _is_process_alive(pid: int) -> bool:
    """Cross-platform process liveness check."""
    if sys.platform == "win32":
        result = sp.run(["tasklist", "/FI", f"PID eq {pid}"], capture_output=True, text=True)
        return str(pid) in result.stdout
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def _kill_server(pid: int) -> bool:
    """Cross-platform process kill."""
    if sys.platform == "win32":
        result = sp.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True)
        return result.returncode == 0
    try:
        os.kill(pid, signal.SIGTERM)
        return True
    except (ProcessLookupError, PermissionError):
        return False


def _terminate_process(pid: int, *, force: bool = False, include_tree: bool = False) -> bool:
    if pid <= 0:
        return False

    if sys.platform == "win32":
        cmd = ["taskkill", "/PID", str(pid)]
        if include_tree:
            cmd.append("/T")
        if force:
            cmd.append("/F")
        result = sp.run(cmd, capture_output=True)
        return result.returncode == 0

    sig = signal.SIGKILL if force else signal.SIGTERM
    try:
        os.kill(pid, sig)
        return True
    except (ProcessLookupError, PermissionError):
        return False


def _wait_for_process_exit(pid: int, timeout: float = 5.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not _is_process_alive(pid):
            return True
        time.sleep(0.2)
    return not _is_process_alive(pid)


def _list_descendant_pids(pid: int) -> list[int]:
    if pid <= 0 or sys.platform == "win32":
        return []

    result = sp.run(["ps", "-axo", "pid=,ppid="], capture_output=True, text=True)
    if result.returncode != 0:
        return []

    children_by_parent: dict[int, list[int]] = {}
    for line in result.stdout.splitlines():
        parts = line.split()
        if len(parts) != 2:
            continue
        child_pid = _coerce_pid(parts[0])
        parent_pid = _coerce_pid(parts[1])
        if child_pid and parent_pid:
            children_by_parent.setdefault(parent_pid, []).append(child_pid)

    descendants: list[int] = []
    stack = list(children_by_parent.get(pid, []))
    while stack:
        child_pid = stack.pop()
        descendants.append(child_pid)
        stack.extend(children_by_parent.get(child_pid, []))
    return descendants


def _terminate_runtime_processes(info: dict) -> tuple[bool, str]:
    host = info.get("host", "127.0.0.1")
    port = info.get("port", 0)
    background = info.get("background", True)
    launcher_pid = _launcher_pid(info)
    server_pid = _server_pid(info)
    descendant_pids = _list_descendant_pids(launcher_pid) if launcher_pid else []

    if background:
        daemon_pid = _coerce_pid(info.get("daemon_pid"))
        # Kill daemon first (it manages server lifecycle)
        if daemon_pid and _is_process_alive(daemon_pid):
            _terminate_process(daemon_pid, force=False, include_tree=True)
            if not _wait_for_process_exit(daemon_pid, timeout=5):
                _terminate_process(daemon_pid, force=True, include_tree=True)
                _wait_for_process_exit(daemon_pid, timeout=2)
        # Kill server directly (handles orphan case if daemon crashed)
        if server_pid and _is_process_alive(server_pid):
            _terminate_process(server_pid, force=False, include_tree=True)
            if not _wait_for_process_exit(server_pid, timeout=5):
                _terminate_process(server_pid, force=True, include_tree=True)
                _wait_for_process_exit(server_pid, timeout=2)
        port_released = _wait_for_port_release(host, port)
        alive = (daemon_pid and _is_process_alive(daemon_pid)) or (server_pid and _is_process_alive(server_pid))
        if alive or (isinstance(port, int) and port > 0 and not port_released):
            return False, f"background runtime still alive"
        return True, f"stopped background runtime (daemon {daemon_pid}, server {server_pid})"

    if launcher_pid and _is_process_alive(launcher_pid):
        _terminate_process(launcher_pid, force=False, include_tree=True)
        if not _wait_for_process_exit(launcher_pid, timeout=10):
            _terminate_process(launcher_pid, force=True, include_tree=True)
            _wait_for_process_exit(launcher_pid, timeout=2)

    if server_pid and _is_process_alive(server_pid):
        _terminate_process(server_pid, force=False, include_tree=True)
        if not _wait_for_process_exit(server_pid, timeout=5):
            _terminate_process(server_pid, force=True, include_tree=True)
            _wait_for_process_exit(server_pid, timeout=2)

    for child_pid in descendant_pids:
        if _is_process_alive(child_pid):
            _terminate_process(child_pid, force=False, include_tree=True)
    for child_pid in descendant_pids:
        if _is_process_alive(child_pid):
            _terminate_process(child_pid, force=True, include_tree=True)

    remaining_pids = [pid for pid in {launcher_pid, server_pid, *descendant_pids} if pid and _is_process_alive(pid)]
    if isinstance(port, int) and port > 0:
        port_released = _wait_for_port_release(host, port)
    else:
        port_released = True

    summary = _pid_summary(info)
    if remaining_pids or not port_released:
        return False, f"foreground runtime still alive ({summary})"
    if launcher_pid or server_pid:
        return True, f"stopped foreground runtime ({summary})"
    return False, "missing launcher/server pid"


def _wait_for_port_release(host: str, port: int, timeout: float = 3.0) -> bool:
    """Wait for port to be released. Returns True if port is free."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex((host, port)) != 0:
                return True
        time.sleep(0.2)
    return False


def _is_port_in_use(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex((host, port)) == 0


def _resolve_runtime_port(value: str, host: str) -> int:
    if value == "auto":
        for candidate in range(DEFAULT_RUNTIME_PORT, 65536):
            if not _is_port_in_use(host, candidate):
                return candidate
        print(f"Error: no free port found from {DEFAULT_RUNTIME_PORT} to 65535")
        raise typer.Exit(1)

    try:
        port = int(value)
    except ValueError:
        print("Error: --port must be an integer or auto")
        raise typer.Exit(1)

    if not 1 <= port <= 65535:
        print("Error: --port must be between 1 and 65535, or auto")
        raise typer.Exit(1)
    return port


def _handle_existing_server(project_path: Path, host: str, port: int) -> None:
    """Check for existing server on this port, clean up or abort."""
    info = _read_server_info(project_path, port)
    if info:
        stopped, message = _terminate_runtime_processes(info)
        if stopped:
            print(f"Stopped previous runtime on port {port} ({message})")
        _remove_server_info(project_path, port)

    if _is_port_in_use(host, port):
        print(f"Port {port} is in use by another process (not this project)")
        print("Use --port to choose a different port, or find the process manually")
        raise typer.Exit(1)


def _server_script_path() -> Path:
    return Path(__file__).resolve().parent / "runtime_server.py"


def _server_command(project_path: Path, host: str, port: int) -> list[str]:
    return [
        sys.executable,
        str(_server_script_path()),
        str(project_path),
        "--host",
        host,
        "--port",
        str(port),
    ]


def _server_env(runtime_token: str | None = None, screenshot_port: int | None = None) -> dict[str, str]:
    env = dict(os.environ)
    env.setdefault("PYTHONUNBUFFERED", "1")
    if runtime_token:
        env["VIBEGAME_RUNTIME_TOKEN"] = runtime_token
    if screenshot_port:
        env["VIBEGAME_SCREENSHOT_PORT"] = str(screenshot_port)
    return env


def _runtime_page_url(
    base_url: str,
    runtime_token: str,
    *,
    activate: bool = False,
    physics_debug: bool = False,
    renderer: str = "auto",
    fps: int | None = None,
    extra: dict[str, str] | None = None,
) -> str:
    params = [f"runtime={runtime_token}"]
    if activate:
        params.append("activate=1")
        params.append("debug=1")
    if physics_debug:
        params.append("physicsDebug=1")
    if renderer != "auto":
        params.append(f"renderer={renderer}")
    if fps is not None:
        params.append(f"fps={fps}")
    # Generic passthrough: append user kv verbatim (URL-encoded). The engine does
    # not interpret these; the game reads them via URLSearchParams(location.search).
    for key, value in (extra or {}).items():
        params.append(f"{quote(str(key), safe='')}={quote(str(value), safe='')}")
    return f"{base_url}/?{'&'.join(params)}"


def _resolve_shot_path(project_path: Path, shot: str | None) -> Path | None:
    if not shot:
        return None
    target = Path(shot).expanduser()
    if not target.is_absolute():
        target = project_path / target
    if not target.suffix:
        target = target.with_suffix(".mp4")
    return target.resolve()


def _shot_work_dir(project_path: Path) -> Path:
    return _runtime_logs_dir(project_path) / "shot-work"


def _validate_shot_target(shot_path: Path | None) -> None:
    if not shot_path:
        return
    if shot_path.suffix.lower() == ".mp4" and not shutil.which("ffmpeg"):
        print("Error: --shot .mp4 output requires ffmpeg.")
        print("Install ffmpeg or use a .webm output path.")
        raise typer.Exit(1)


def _raw_shot_path(work_dir: Path, target_path: Path) -> Path:
    stamp = int(time.time() * 1000)
    return work_dir / f"{target_path.stem}-{stamp}.webm"


def _write_shot_video(source_path: Path, target_path: Path, work_dir: Path) -> Path:
    target_path.parent.mkdir(parents=True, exist_ok=True)
    if target_path.suffix.lower() != ".mp4":
        shutil.move(str(source_path), str(target_path))
        return target_path

    work_dir.mkdir(parents=True, exist_ok=True)
    raw_path = _raw_shot_path(work_dir, target_path)
    shutil.move(str(source_path), str(raw_path))
    result = sp.run(
        [
            "ffmpeg",
            "-y",
            "-loglevel",
            "error",
            "-i",
            str(raw_path),
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            str(target_path),
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {result.stderr.strip() or result.stdout.strip()}")
    raw_path.unlink(missing_ok=True)
    return target_path


def _finalize_shot(page, context, shot_path: Path | None, work_dir: Path) -> Path | None:
    video = page.video if shot_path else None
    try:
        page.close()
    except Exception:
        pass
    try:
        context.close()
    except Exception:
        pass
    if not shot_path or not video:
        return None
    source_path = Path(video.path())
    return _write_shot_video(source_path, shot_path, work_dir)


_screenshot_queue: queue.Queue = queue.Queue()
_refresh_queue: queue.Queue = queue.Queue()


class _PlaywrightBrokerHandler(http.server.BaseHTTPRequestHandler):
    """HTTP handler that delegates Playwright ops (screenshot, refresh) to the owning thread."""

    def do_GET(self):
        if self.path == "/screenshot":
            self._handle_screenshot()
        elif self.path == "/refresh":
            self._handle_refresh()
        else:
            self.send_response(404)
            self.end_headers()

    def _handle_screenshot(self):
        resp_q: queue.Queue = queue.Queue(maxsize=1)
        _screenshot_queue.put(resp_q)
        try:
            result = resp_q.get(timeout=15)
        except queue.Empty:
            self.send_response(503)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"error":"Screenshot timed out"}')
            return
        if isinstance(result, Exception):
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            msg = f'{{"error":"Screenshot failed: {result}"}}'
            self.wfile.write(msg.encode())
            return
        png_bytes: bytes = result
        self.send_response(200)
        self.send_header("Content-Type", "image/png")
        self.send_header("Content-Length", str(len(png_bytes)))
        self.end_headers()
        self.wfile.write(png_bytes)

    def _handle_refresh(self):
        resp_q: queue.Queue = queue.Queue(maxsize=1)
        _refresh_queue.put(resp_q)
        try:
            result = resp_q.get(timeout=75)
        except queue.Empty:
            self.send_response(503)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"error":"Refresh timed out"}')
            return
        if isinstance(result, Exception):
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            msg = f'{{"error":"Refresh failed: {result}"}}'
            self.wfile.write(msg.encode())
            return
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"status":"ok"}')

    def log_message(self, format, *args):
        pass  # silence request logging


def _drain_queues(page) -> None:
    """Execute pending Playwright requests on the owning thread."""
    while True:
        try:
            resp_q = _screenshot_queue.get_nowait()
        except queue.Empty:
            break
        try:
            resp_q.put(page.screenshot(type="png"))
        except Exception as exc:
            resp_q.put(exc)
    while True:
        try:
            resp_q = _refresh_queue.get_nowait()
        except queue.Empty:
            break
        try:
            page.evaluate("window.location.reload()")
            resp_q.put("ok")
        except Exception as exc:
            resp_q.put(exc)


class BrowserLaunchError(RuntimeError):
    """No launch attempt succeeded, carrying what each one actually said."""


def launch_browser(playwright, *, headless: bool, args: list[str]):
    """Try Chrome, then the bundled Chromium, and report every failure.

    Both attempts used to be wrapped in bare `except Exception` and the user was
    told "No browser found. Install Chrome". Inside a container that is false and
    expensive: the browser is there, it just cannot open a window without a
    display. An agent read that message literally, spent 13 minutes and 892 MB
    installing a second Chromium, and only recovered by finding --headless.
    """
    plans = [("Chrome", {"channel": "chrome", "headless": False})] if not headless else []
    plans.append(("Chromium", {"headless": headless}))

    failures = []
    for label, kwargs in plans:
        try:
            return playwright.chromium.launch(args=args, **kwargs), label
        except Exception as e:
            first = str(e).strip().splitlines()[0] if str(e).strip() else repr(e)
            failures.append(f"  {label}: {type(e).__name__}: {first[:300]}")
    raise BrowserLaunchError("\n".join(failures))


def browser_launch_message(error: BrowserLaunchError, *, headless: bool) -> str:
    """One diagnosis for both launch sites: the foreground prints it, the
    background daemon hands it to its parent through the status file."""
    message = f"Could not launch a browser:\n{error}"
    if not headless:
        message += ("\n\nA container or SSH session has no display. Retry with "
                    "--headless before installing anything.")
    return message


def _browser_launch_args() -> list[str]:
    args = [
        "--disable-background-timer-throttling",
        "--disable-backgrounding-occluded-windows",
        "--disable-renderer-backgrounding",
    ]
    if sys.platform == "darwin":
        args.extend([
            "--enable-gpu",
            "--ignore-gpu-blocklist",
            "--use-angle=metal",
        ])
    return args


def _start_screenshot_broker() -> http.server.HTTPServer:
    """Start a daemon HTTP server on a random port for Playwright operations."""
    server = http.server.HTTPServer(("127.0.0.1", 0), _PlaywrightBrokerHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def _bg_status_file(project_path: Path, port: int) -> Path:
    """Temp file for daemon child to signal readiness to parent."""
    return _runtime_logs_dir(project_path) / f".bg-status-{port}"


def _run_daemon_child(
    project_path: Path,
    host: str,
    port: int,
    runtime_token: str,
    log_file: Path,
    status_file: Path,
    *,
    headless: bool = True,
    activate: bool = False,
    physics_debug: bool = False,
    renderer: str = "auto",
    fps: int | None = None,
    shot_path: str | None = None,
    extra_params: dict[str, str] | None = None,
) -> None:
    """Background daemon: full runtime setup (server + Playwright) then screenshot drain loop."""
    import urllib.request

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        status_file.write_text(json.dumps({"error": "playwright not installed"}))
        os._exit(1)

    _screenshot_broker: http.server.HTTPServer | None = None
    proc: sp.Popen | None = None
    shot_target = Path(shot_path) if shot_path else None

    try:
        # 1. Screenshot broker
        _screenshot_broker = _start_screenshot_broker()
        _screenshot_port = _screenshot_broker.server_address[1]

        # 2. Server (child of daemon, not detached)
        proc = _start_server_process(
            project_path, host, port,
            log_file=log_file,
            detached=False,
            runtime_token=runtime_token,
            screenshot_port=_screenshot_port,
        )

        # 3. Wait for server ready
        url = f"http://{host}:{port}"
        server_ready = False
        for _ in range(30):
            if proc.poll() is not None:
                break
            try:
                urllib.request.urlopen(f"{url}/api/project", timeout=1)
                server_ready = True
                break
            except Exception:
                time.sleep(0.5)
        if not server_ready:
            status_file.write_text(json.dumps({"error": "server startup failed"}))
            os._exit(1)

        # 4. Write server info so vibegame close works from this point
        servers = _read_all_servers(project_path)
        servers[str(port)] = _normalize_server_entry({
            "host": host,
            "port": port,
            "background": True,
            "pid": os.getpid(),
            "server_pid": proc.pid,
            "daemon_pid": os.getpid(),
        }, background_default=True)
        _write_all_servers(project_path, servers)

        # 5. Playwright
        launch_args = _browser_launch_args()

        with sync_playwright() as p:
            try:
                browser, _ = launch_browser(p, headless=headless, args=launch_args)
            except BrowserLaunchError as e:
                # The handler below is the one path that reaches the parent.
                raise RuntimeError(browser_launch_message(e, headless=headless)) from e
            context = None
            page = None

            vp_w, vp_h = 960, 720
            proj_file = project_path / "project.json"
            if proj_file.exists():
                try:
                    proj = json.loads(proj_file.read_text(encoding="utf-8"))
                    vp_w = proj.get("settings", {}).get("width", vp_w)
                    vp_h = proj.get("settings", {}).get("height", vp_h)
                except Exception:
                    pass

            context_kwargs = {"viewport": {"width": vp_w, "height": vp_h}}
            if shot_target:
                _shot_work_dir(project_path).mkdir(parents=True, exist_ok=True)
                context_kwargs.update(
                    {
                        "record_video_dir": str(_shot_work_dir(project_path)),
                        "record_video_size": {"width": vp_w, "height": vp_h},
                    }
                )
            context = browser.new_context(**context_kwargs)
            page = context.new_page()
            page.goto(
                _runtime_page_url(
                    url, runtime_token, activate=activate,
                    physics_debug=physics_debug, renderer=renderer, fps=fps, extra=extra_params,
                ),
                wait_until="domcontentloaded",
            )
            page.wait_for_function("window.__vibegame_ready === true", timeout=30000)

            # 6. Signal readiness to parent
            status_file.write_text(json.dumps({"ready": True, "daemon_pid": os.getpid()}))

            # 7. Drain loop
            stop = threading.Event()
            signal.signal(signal.SIGINT, lambda *_: stop.set())
            signal.signal(signal.SIGTERM, lambda *_: stop.set())
            while not stop.is_set():
                _drain_queues(page)
                stop.wait(timeout=0.3)

            if page and context:
                try:
                    _finalize_shot(page, context, shot_target, _shot_work_dir(project_path))
                except Exception as exc:
                    with open(log_file, "a", encoding="utf-8") as lf:
                        lf.write(f"\nShot save failed: {exc}\n")
            browser.close()

    except Exception as exc:
        try:
            status_file.write_text(json.dumps({"error": str(exc)}))
        except Exception:
            pass
        os._exit(1)

    finally:
        if _screenshot_broker:
            try:
                _screenshot_broker.shutdown()
            except Exception:
                pass
        if proc:
            try:
                _stop_server_process(proc, host, port)
            except Exception:
                pass
        try:
            _remove_server_info(project_path, port)
        except Exception:
            pass
        try:
            status_file.unlink(missing_ok=True)
        except Exception:
            pass


def _start_server_process(
    project_path: Path,
    host: str,
    port: int,
    *,
    log_file: Path,
    detached: bool,
    runtime_token: str | None = None,
    screenshot_port: int | None = None,
) -> sp.Popen:
    log_file.parent.mkdir(parents=True, exist_ok=True)
    with open(log_file, "w", encoding="utf-8") as lf:
        popen_kwargs: dict = {
            "stdout": lf,
            "stderr": sp.STDOUT,
            "stdin": sp.DEVNULL,
            "cwd": str(project_path),
            "env": _server_env(runtime_token, screenshot_port=screenshot_port),
        }
        if detached:
            if sys.platform == "win32":
                popen_kwargs["creationflags"] = sp.CREATE_NO_WINDOW
            else:
                popen_kwargs["start_new_session"] = True
        return sp.Popen(_server_command(project_path, host, port), **popen_kwargs)


def _stop_server_process(proc: sp.Popen | None, host: str, port: int) -> None:
    if proc is None or proc.poll() is not None:
        return
    _kill_server(proc.pid)
    try:
        proc.wait(timeout=5)
    except sp.TimeoutExpired:
        if sys.platform == "win32":
            sp.run(["taskkill", "/PID", str(proc.pid), "/F"], capture_output=True)
        else:
            proc.kill()
            proc.wait(timeout=5)
    _wait_for_port_release(host, port)


@app.command("run", context_settings={"allow_extra_args": True})
def run(
    ctx: typer.Context,
    path: str = typer.Argument(default=".", help="Game project path (default: current directory)"),
    host: str = typer.Option("127.0.0.1", "--host", help="Server host"),
    port: str = typer.Option(str(DEFAULT_RUNTIME_PORT), "--port", "-p", help="Server port, or auto"),
    background: bool = typer.Option(False, "--background", "-b", help="Run server in background"),
    headless: bool = typer.Option(False, "--headless", help="Run with a headless browser for runtime automation"),
    activate: bool = typer.Option(False, "--activate", help="Start runtime control mode paused before the first gameplay frame"),
    physics_debug: bool = typer.Option(False, "--debug", help="Show Phaser Arcade physics debug bodies"),
    renderer: str = typer.Option("auto", "--renderer", help="Renderer: auto, webgl, or canvas"),
    fps: int | None = typer.Option(None, "--fps", help="Render FPS cap for this session. 0 = uncapped. Default: project settings.fpsLimit, else 60 for runtime sessions"),
    shot: str | None = typer.Option(None, "--shot", help="Record runtime browser video to FILE (.mp4 requires ffmpeg)"),
    bot: str | None = typer.Option(None, "--bot", help="Run a Python bot script. See spec/engine/runtime.md `## Runtime bot`."),
    max_seconds: float | None = typer.Option(None, "--max-seconds", help="Bot mode: override META[max_seconds]. Default 10."),
    logs: bool = typer.Option(False, "--logs", help="Show runtime server logs"),
    status: bool = typer.Option(False, "--status", help="Show tracked server status"),
):
    """Launch the vibegame runtime server for a game project."""
    project_path = Path(path).resolve()
    if not project_path.is_dir():
        print(f"Error: Path does not exist or is not a directory: {project_path}")
        raise typer.Exit(1)

    resolved_port = _resolve_runtime_port(port, host)

    if status:
        servers = _prune_stale_servers(project_path)
        if not servers:
            print("No tracked server found")
            raise typer.Exit(1)
        for _port_key, info in sorted(servers.items(), key=lambda x: int(x[0])):
            pid = _tracked_pid(info)
            alive = _is_process_alive(pid) if pid else False
            s_host, s_port = info.get("host", "?"), info.get("port", "?")
            mode = "background" if info.get("background", True) else "foreground"
            state = "running" if alive else "dead"
            print(
                f"  Port {s_port}: {state}  {mode}  {_pid_summary(info)}  Address: http://{s_host}:{s_port}"
            )
        raise typer.Exit(0)

    if logs:
        log_file = _display_server_log_path(project_path, resolved_port)
        if not log_file.exists():
            print(f"No server log file found for port {resolved_port}")
            raise typer.Exit(1)
        content = log_file.read_text(encoding="utf-8")
        lines = content.splitlines()
        for line in lines[-50:]:
            print(line)
        print(f"\nLog file: {log_file}")
        raise typer.Exit(0)

    port = resolved_port

    shot_path = _resolve_shot_path(project_path, shot)
    _validate_shot_target(shot_path)
    renderer = _normalize_renderer(renderer)
    fps = _normalize_fps(fps)

    # Passthrough params: tokens after `--` (`vibegame run . -- k=v`) become URL query
    # (?k=v) on the game page, read by the game via URLSearchParams(location.search).
    # The engine does not interpret them. Bot mode also feeds META["params"] below.
    _passthrough_params: dict[str, str] = _parse_cli_query_tokens(ctx.args)
    _validate_passthrough_params(_passthrough_params, "passthrough args after `--`")

    # Bot mode preparation. Sprint 1 requires foreground; -b combination is a follow-up.
    _bot_path: Path | None = None
    _bot_out_dir: Path | None = None
    if bot:
        if background:
            print("Error: --bot is not supported with --background in this release.")
            raise typer.Exit(1)
        from cli.run_bot import make_run_id as _make_bot_run_id, load_bot as _load_bot
        _bot_path = Path(bot).resolve()
        if not _bot_path.exists():
            print(f"Error: bot file not found: {bot}")
            raise typer.Exit(1)
        # bot META["params"] also feed the passthrough query. CLI `-- k=v` wins on clash.
        _, _bot_meta, _ = _load_bot(_bot_path)
        _bot_params = _bot_meta.get("params", {})
        if not isinstance(_bot_params, dict):
            print(f"Error: bot META['params'] must be a dict, got {type(_bot_params).__name__}")
            raise typer.Exit(1)
        _bot_params = {str(k): str(v) for k, v in _bot_params.items()}
        _validate_passthrough_params(_bot_params, "bot META['params']")
        _passthrough_params = {**_bot_params, **_passthrough_params}
        _bot_run_id = _make_bot_run_id(_bot_path)
        _bot_out_dir = project_path / ".vibegame" / "logs" / "bot" / _bot_run_id
        _bot_out_dir.mkdir(parents=True, exist_ok=True)
        if shot_path is None:
            shot_path = _bot_out_dir / "video.webm"
            _validate_shot_target(shot_path)

    if background:
        _handle_existing_server(project_path, host, port)
        runtime_token = secrets.token_hex(16)
        log_file = _server_log_path(project_path, port)
        status_file = _bg_status_file(project_path, port)
        status_file.parent.mkdir(parents=True, exist_ok=True)
        status_file.unlink(missing_ok=True)

        if sys.platform == "win32":
            print("Background mode with runtime API is not supported on Windows.")
            raise typer.Exit(1)

        daemon_pid = os.fork()
        if daemon_pid > 0:
            # Parent: wait for daemon child to finish setup, then print info and exit
            deadline = time.monotonic() + 60
            while time.monotonic() < deadline:
                if status_file.exists():
                    time.sleep(0.1)  # brief settle for write completion
                    break
                time.sleep(0.5)
            if not status_file.exists():
                print("Background runtime still starting.")
                print("Check status: vibegame run --status")
                sys.stdout.flush()
                os._exit(0)
            try:
                status = json.loads(status_file.read_text(encoding="utf-8"))
            except Exception:
                print("Background runtime still starting.")
                print("Check status: vibegame run --status")
                sys.stdout.flush()
                os._exit(0)
            finally:
                status_file.unlink(missing_ok=True)
            if status.get("error"):
                print(f"Background runtime failed: {status['error']}")
                sys.stdout.flush()
                os._exit(1)

            tracked_lines = _tracked_server_lines(project_path)
            tracked_block = ""
            if tracked_lines:
                tracked_block = "\n\nBackground runtimes\n" + "\n".join(
                    f"  {line}" for line in tracked_lines
                )

            print("=== VibeGame Run (background) ===")
            print(f"  Server started in background\n")
            print(f"  Project: {project_path}")
            for line in _engine_fallback_warning(project_path):
                print(f"  {line}")
            print(f"  Address: http://{host}:{port}")
            print(f"  Runtime API: http://{host}:{port}/api/runtime/")
            if activate:
                print("  Activate: runtime control active at frame 0")
            if physics_debug:
                print("  Debug: physics bodies visible")
            if shot_path:
                print(f"  Shot: {shot_path} (saved on close)")
            print(f"  Daemon PID: {daemon_pid}")
            print(f"  Log: {log_file}\n")
            print(f"  Game:   http://{host}:{port}/")
            print(f"  vibegame run --status   Server status")
            print(f"  vibegame run --logs     View logs")
            print(f"  vibegame close          Stop server")
            if tracked_block:
                print(tracked_block)
            sys.stdout.flush()
            os._exit(0)

        # Child: daemonize then run full runtime setup
        os.setsid()
        devnull_fd = os.open(os.devnull, os.O_RDWR)
        os.dup2(devnull_fd, 0)
        os.dup2(devnull_fd, 1)
        os.dup2(devnull_fd, 2)
        os.close(devnull_fd)
        _run_daemon_child(
            project_path,
            host,
            port,
            runtime_token,
            log_file,
            status_file,
            headless=headless,
            activate=activate,
            physics_debug=physics_debug,
            renderer=renderer,
            fps=fps,
            shot_path=str(shot_path) if shot_path else None,
            extra_params=_passthrough_params,
        )
        os._exit(0)

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print(
            "playwright is required for vibegame run.\n"
            "Install: pip install playwright && playwright install chromium"
        )
        raise typer.Exit(1)

    _handle_existing_server(project_path, host, port)

    log_file = _server_log_path(project_path, port)
    runtime_token = secrets.token_hex(16)

    # Start screenshot broker before server so we can pass the port via env.
    _screenshot_broker = _start_screenshot_broker()
    _screenshot_port = _screenshot_broker.server_address[1]

    proc = _start_server_process(
        project_path,
        host,
        port,
        log_file=log_file,
        detached=False,
        runtime_token=runtime_token,
        screenshot_port=_screenshot_port,
    )
    _write_server_info(
        project_path,
        host=host,
        port=port,
        background=False,
        server_pid=proc.pid,
        launcher_pid=os.getpid(),
    )

    import urllib.request

    url = f"http://{host}:{port}"
    server_ready = False
    for _ in range(30):
        if proc.poll() is not None:
            _remove_server_info(project_path, port)
            print("Server failed to start.")
            print(f"Check log: {log_file}")
            raise typer.Exit(1)
        try:
            urllib.request.urlopen(f"{url}/api/project", timeout=1)
            server_ready = True
            break
        except Exception:
            time.sleep(0.5)
    if not server_ready:
        _stop_server_process(proc, host, port)
        _remove_server_info(project_path, port)
        print("Server failed to start (timeout waiting for response)")
        print(f"Check log: {log_file}")
        raise typer.Exit(1)

    mode_label = "headless" if headless else "visible"
    try:
        tracked_lines = _tracked_server_lines(project_path)
        tracked_block = ""
        if tracked_lines:
            tracked_block = "\n\nTracked runtimes\n" + "\n".join(
                f"  {line}" for line in tracked_lines
            )
        print(f"=== VibeGame Run ({mode_label}) ===")
        print(f"  VibeGame Run ({mode_label} runtime session)\n")
        print(f"  Project:   {project_path}")
        for line in _engine_fallback_warning(project_path):
            print(f"  {line}")
        print(f"  Game:      {url}/")
        print(f"  Runtime API: {url}/api/runtime/")
        if shot_path:
            print(f"  Shot:      {shot_path}")
        print(f"  Log:       {log_file}\n")
        print(f"  Press Ctrl+C to stop")
        if tracked_block:
            print(tracked_block)

        with sync_playwright() as p:
            launch_args = _browser_launch_args()
            try:
                browser, browser_label = launch_browser(
                    p, headless=headless, args=launch_args
                )
            except BrowserLaunchError as e:
                print(browser_launch_message(e, headless=headless))
                raise typer.Exit(1)
            _vp_w, _vp_h = 960, 720
            _proj_file = project_path / "project.json"
            if _proj_file.exists():
                try:
                    _proj = json.loads(_proj_file.read_text(encoding="utf-8"))
                    _settings = _proj.get("settings", {})
                    _vp_w = _settings.get("width", _vp_w)
                    _vp_h = _settings.get("height", _vp_h)
                except Exception:
                    pass
            context_kwargs = {"viewport": {"width": _vp_w, "height": _vp_h}}
            if shot_path:
                _shot_work_dir(project_path).mkdir(parents=True, exist_ok=True)
                context_kwargs.update(
                    {
                        "record_video_dir": str(_shot_work_dir(project_path)),
                        "record_video_size": {"width": _vp_w, "height": _vp_h},
                    }
                )
            context = browser.new_context(**context_kwargs)
            page = context.new_page()
            page.goto(
                _runtime_page_url(
                    url, runtime_token, activate=activate,
                    physics_debug=physics_debug, renderer=renderer, fps=fps, extra=_passthrough_params,
                ),
                wait_until="domcontentloaded",
            )
            page.wait_for_function("window.__vibegame_ready === true", timeout=30000)
            print(f"Runtime session connected ({mode_label}, {browser_label}). Runtime API ready.")
            if activate:
                print("Runtime control active: paused at frame 0.")
            if physics_debug:
                print("Physics debug active: Arcade bodies visible.")
            bot_result: dict | None = None
            try:
                if _bot_path is not None:
                    from cli.run_bot import run_bot as _bot_loop
                    bot_result = _bot_loop(
                        page,
                        project_path,
                        _bot_path,
                        max_seconds,
                        server_url=url,
                        out_dir=_bot_out_dir,
                    )
                else:
                    stop = threading.Event()
                    signal.signal(signal.SIGINT, lambda *_: stop.set())
                    signal.signal(signal.SIGTERM, lambda *_: stop.set())
                    while not stop.is_set():
                        _drain_queues(page)
                        stop.wait(timeout=0.3)
            except KeyboardInterrupt:
                pass
            finally:
                saved_shot = None
                try:
                    saved_shot = _finalize_shot(page, context, shot_path, _shot_work_dir(project_path))
                except Exception as exc:
                    print(f"Shot save failed: {exc}")
                finally:
                    browser.close()
                if saved_shot:
                    print(f"Shot saved: {saved_shot}")
                print("Runtime session closed.")

            if bot_result is not None:
                print()
                print(f"Bot result: status={bot_result['status']}  ok={bot_result['ok']}")
                print(f"Reason:     {bot_result['reason']}")
                if _bot_out_dir is not None:
                    print(f"Run dir:    {_bot_out_dir}")
                    print(f"Result:     {_bot_out_dir / 'result.json'}")
                _bot_exit_code = 0 if bot_result["ok"] else 1
                # typer.Exit propagates through the outer finally that stops the
                # server, so cleanup still runs.
                raise typer.Exit(_bot_exit_code)
    finally:
        _screenshot_broker.shutdown()
        _stop_server_process(proc, host, port)
        _remove_server_info(project_path, port)


@app.command("close")
def close(
    path: str = typer.Argument(default=".", help="Game project path (default: current directory)"),
    port: int = typer.Option(0, "--port", "-p", help="Port of the server to stop (required if multiple)"),
    all_servers: bool = typer.Option(False, "--all", help="Stop all running servers"),
):
    """Stop the runtime server for a game project."""
    project_path = Path(path).resolve()
    servers = _prune_stale_servers(project_path)

    if not servers:
        print("No server info found (server not running?)")
        raise typer.Exit(0)

    if all_servers:
        ports_to_close = [int(k) for k in servers]
    elif port:
        if str(port) not in servers:
            print(f"No server tracked on port {port}")
            active = [k for k, v in servers.items() if _is_process_alive(_tracked_pid(v))]
            if active:
                print(f"Active ports: {', '.join(active)}")
            raise typer.Exit(1)
        ports_to_close = [port]
    elif len(servers) == 1:
        ports_to_close = [int(next(iter(servers)))]
    else:
        print("Multiple servers tracked. Specify --port or --all:")
        for port_key, info in sorted(servers.items(), key=lambda x: int(x[0])):
            pid = _tracked_pid(info)
            alive = _is_process_alive(pid) if pid else False
            state = "running" if alive else "dead"
            print(f"  Port {port_key}: {state}  {_pid_summary(info)}")
        raise typer.Exit(1)

    for p in ports_to_close:
        info = servers.get(str(p), {})
        if not info:
            print(f"Port {p}: invalid info, cleaning up")
            _remove_server_info(project_path, p)
            continue
        if _is_server_entry_stale(info):
            print(f"Port {p}: tracked runtime already gone, cleaning up")
            _remove_server_info(project_path, p)
            continue
        stopped, message = _terminate_runtime_processes(info)
        if stopped:
            print(f"Port {p}: {message}")
        else:
            print(f"Port {p}: failed to stop runtime ({message})")
        _remove_server_info(project_path, p)
