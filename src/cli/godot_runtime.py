"""Runtime adapter for VibeGame Godot projects.

Godot games cannot be driven through Playwright. This module bridges the two
worlds:

    Godot bridge (GDScript, TCP JSON lines)
        <-> this adapter (HTTP /api/runtime/*)
        <-> `vibegame play` (unchanged CLI)

The adapter also tracks the running runtime in the same
`.vibegame/logs/runtime/servers.json` registry as the Phaser runtime, so
`vibegame run --status`-style bookkeeping and `vibegame close` keep working.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import signal
import socket
import subprocess
import sys
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

if __package__ in (None, ""):  # running as a script from a detached child
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


class BridgeError(RuntimeError):
    """The Godot bridge rejected a command or the game went away."""


class BridgeClient:
    """Synchronous line-delimited JSON client for the Godot bridge."""

    def __init__(self, host: str = "127.0.0.1", port: int = 35700, timeout: float = 30.0):
        self.host = host
        self.port = port
        self.timeout = timeout
        self._sock: socket.socket | None = None
        self._file = None
        self._lock = threading.Lock()

    def connect(self) -> None:
        sock = socket.create_connection((self.host, self.port), timeout=2.0)
        sock.settimeout(self.timeout)
        self._sock = sock
        self._file = sock.makefile("rwb")

    def wait_ready(self, timeout: float = 45.0, process: subprocess.Popen | None = None) -> None:
        deadline = time.monotonic() + timeout
        last_error: Exception | None = None
        while time.monotonic() < deadline:
            if process is not None and process.poll() is not None:
                raise BridgeError(
                    f"Godot exited with code {process.returncode} before the bridge was ready"
                )
            try:
                self.connect()
                return
            except OSError as exc:
                last_error = exc
                time.sleep(0.15)
        raise BridgeError(
            f"timed out waiting for the Godot bridge on {self.host}:{self.port} ({last_error})"
        )

    def call(self, command: str, **params) -> dict:
        with self._lock:
            if self._sock is None or self._file is None:
                raise BridgeError("bridge is not connected")
            payload = {"cmd": command, **params}
            try:
                self._file.write((json.dumps(payload) + "\n").encode("utf-8"))
                self._file.flush()
                line = self._file.readline()
            except (OSError, ValueError) as exc:
                raise BridgeError(f"bridge I/O failed: {exc}") from exc
            if not line:
                raise BridgeError("bridge closed the connection (did the game exit?)")
            try:
                response = json.loads(line)
            except json.JSONDecodeError as exc:
                raise BridgeError(f"invalid bridge response: {exc}") from exc
            if not isinstance(response, dict):
                raise BridgeError("invalid bridge response: expected an object")
            if not response.get("ok"):
                raise BridgeError(str(response.get("error") or "bridge command failed"))
            return response

    def close(self) -> None:
        with self._lock:
            if self._file is not None:
                try:
                    self._file.close()
                except OSError:
                    pass
                self._file = None
            if self._sock is not None:
                try:
                    self._sock.close()
                except OSError:
                    pass
                self._sock = None


def _free_port(start: int = 35700, end: int = 35800) -> int:
    for port in range(start, end):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind(("127.0.0.1", port))
            except OSError:
                continue
            return port
    raise RuntimeError(f"no free bridge port in {start}-{end - 1}")


def _decode_json_body(handler: BaseHTTPRequestHandler) -> dict:
    length = int(handler.headers.get("Content-Length", "0") or 0)
    if length <= 0:
        return {}
    raw = handler.rfile.read(length)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise BridgeError(f"invalid JSON body: {exc}") from exc
    return data if isinstance(data, dict) else {}


def _continue_and_wait(client: BridgeClient, frames: int) -> dict:
    client.call("continue", frames=frames)
    timeout = max(5.0, frames / 30.0 + 3.0)
    deadline = time.monotonic() + timeout
    last_status: dict = {}
    while time.monotonic() < deadline:
        last_status = client.call("status")
        if int(last_status.get("stepRemaining", 0)) == 0:
            return last_status
        time.sleep(0.02)
    return last_status


def _make_handler(client: BridgeClient, project: Path):
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, _format: str, *args) -> None:
            # Keep the runtime log focused on Godot output.
            return

        def _send_json(self, payload: dict, status: int = 200) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _send_png(self, payload: bytes) -> None:
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def do_GET(self) -> None:
            self._dispatch("GET")

        def do_POST(self) -> None:
            self._dispatch("POST")

        def _dispatch(self, method: str) -> None:
            # `eval` can run arbitrary code in the game process. Browsers attach
            # `Origin` to cross-site requests and the CLI never does, so refusing
            # it keeps web pages from driving the runtime.
            origin = self.headers.get("Origin")
            if origin is not None:
                self.close_connection = True  # the unread request body must not reach the next request
                self._send_json({"error": f"browser requests are not accepted (Origin: {origin})"}, status=403)
                return
            parsed = urllib.parse.urlparse(self.path)
            path = parsed.path.rstrip("/") or "/"
            query = urllib.parse.parse_qs(parsed.query)
            try:
                if path in {"/health", "/api/health"}:
                    self._send_json({"ok": True, "engine": "godot"})
                    return
                if path == "/api/project":
                    data = json.loads((project / "project.json").read_text(encoding="utf-8"))
                    self._send_json(data)
                    return
                if not path.startswith("/api/runtime/"):
                    self._send_json({"error": f"not found: {path}"}, status=404)
                    return
                command = path[len("/api/runtime/"):]
                self._handle_runtime(method, command, query)
            except BridgeError as exc:
                self._send_json({"error": str(exc)}, status=500)
            except Exception as exc:  # noqa: BLE001 - adapter boundary
                self._send_json({"error": f"{type(exc).__name__}: {exc}"}, status=500)

        def _handle_runtime(self, method: str, command: str, query: dict) -> None:
            if method == "GET":
                if command == "screenshot":
                    response = client.call("screenshot")
                    image = base64.b64decode(response.get("data", ""))
                    if not image:
                        raise BridgeError("bridge returned an empty screenshot")
                    self._send_png(image)
                    return
                if command == "snapshot":
                    self._send_json(client.call("snapshot", maxDepth=int(query.get("maxDepth", ["8"])[0])))
                    return
                if command == "status":
                    self._send_json(client.call("status"))
                    return
                if command == "console":
                    params: dict = {}
                    if "since" in query:
                        params["since"] = int(query["since"][0])
                    if "level" in query:
                        params["level"] = query["level"][0]
                    self._send_json(client.call("console_get", **params))
                    return
                if command == "network":
                    self._send_json({"ok": True, "entries": [], "next": 0})
                    return
                self._send_json({"error": f"unsupported GET: {command}"}, status=404)
                return

            body = _decode_json_body(self)
            if command == "activate":
                self._send_json(client.call("activate"))
            elif command == "deactivate":
                self._send_json(client.call("deactivate"))
            elif command == "pause":
                self._send_json(client.call("pause"))
            elif command == "play":
                self._send_json(client.call("play"))
            elif command == "continue":
                self._send_json(_continue_and_wait(client, int(body.get("frames", 60))))
            elif command == "refresh":
                self._send_json(client.call("refresh"))
                time.sleep(0.15)
            elif command == "eval":
                self._send_json(client.call("eval", code=str(body.get("code", ""))))
            elif command == "set":
                self._send_json(
                    client.call(
                        "set",
                        nodeId=str(body.get("nodeId", "")),
                        path=str(body.get("path", "")),
                        value=body.get("value"),
                    )
                )
            elif command == "click":
                response = client.call(
                    "click",
                    x=float(body.get("x", 0.0)),
                    y=float(body.get("y", 0.0)),
                    button=str(body.get("button", "left")),
                )
                time.sleep(0.08)
                self._send_json(response)
            elif command == "mousemove":
                response = client.call(
                    "mousemove",
                    x=float(body.get("x", 0.0)),
                    y=float(body.get("y", 0.0)),
                )
                time.sleep(0.05)
                self._send_json(response)
            elif command == "drag":
                response = client.call(
                    "drag",
                    fromX=float(body.get("fromX", 0.0)),
                    fromY=float(body.get("fromY", 0.0)),
                    toX=float(body.get("toX", 0.0)),
                    toY=float(body.get("toY", 0.0)),
                    steps=int(body.get("steps", 10)),
                    button=str(body.get("button", "left")),
                )
                time.sleep(0.12)
                self._send_json(response)
            elif command == "key":
                response = client.call(
                    "key",
                    key=str(body.get("key", "")),
                    type=str(body.get("type", "press")),
                )
                time.sleep(0.08)
                self._send_json(response)
            elif command == "input":
                params = {"action": str(body.get("action", ""))}
                if "held" in body:
                    params["held"] = bool(body["held"])
                response = client.call("input", **params)
                time.sleep(0.08)
                self._send_json(response)
            elif command == "console/clear":
                self._send_json(client.call("console_clear"))
            elif command == "network/clear":
                self._send_json({"ok": True})
            else:
                self._send_json({"error": f"unsupported POST: {command}"}, status=404)

    return Handler


def _write_server_info(
    project: Path,
    *,
    host: str,
    port: int,
    background: bool,
    server_pid: int,
    launcher_pid: int = 0,
) -> None:
    from cli.run import _write_server_info as write_info

    write_info(
        project,
        host=host,
        port=port,
        background=background,
        server_pid=server_pid,
        launcher_pid=launcher_pid,
    )


def _remove_server_info(project: Path, port: int) -> None:
    from cli.run import _remove_server_info as remove_info

    remove_info(project, port)


def serve(
    project_path: Path,
    *,
    host: str,
    port: int,
    bridge_port: int,
    godot_bin: str,
    headless: bool,
    background: bool,
) -> int:
    """Launch Godot and expose the runtime API until the game exits."""
    project_path = project_path.resolve()
    command = [godot_bin]
    if headless:
        command.append("--headless")
    command.extend(["--path", str(project_path), "--", f"--vibegame-bridge={bridge_port}"])
    env = dict(os.environ)
    env.pop("VIBEGAME_GODOT_BRIDGE_DISABLE", None)

    process = subprocess.Popen(command, cwd=str(project_path), env=env)
    client = BridgeClient(port=bridge_port)
    server: ThreadingHTTPServer | None = None
    try:
        try:
            client.wait_ready(timeout=45.0, process=process)
        except BridgeError:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
            raise

        server = ThreadingHTTPServer((host, port), _make_handler(client, project_path))
        server.daemon_threads = True
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        _write_server_info(
            project_path,
            host=host,
            port=port,
            background=background,
            server_pid=os.getpid(),
            launcher_pid=0 if background else os.getpid(),
        )
        print(
            f"Godot runtime ready: http://{host}:{port} "
            f"(bridge {bridge_port}, game PID {process.pid})",
            flush=True,
        )

        stop = threading.Event()

        def _stop(_signum=None, _frame=None) -> None:
            stop.set()

        signal.signal(signal.SIGINT, _stop)
        signal.signal(signal.SIGTERM, _stop)
        while not stop.is_set() and process.poll() is None:
            time.sleep(0.2)
    finally:
        if server is not None:
            server.shutdown()
            server.server_close()
        client.close()
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        _remove_server_info(project_path, port)
    return 0 if process.returncode in (None, 0) else int(process.returncode)


def _server_log_path(project: Path, port: int) -> Path:
    from cli.run import _server_log_path as log_path

    return log_path(project, port)


def run_godot(
    *,
    project_path: Path,
    host: str,
    port: str,
    background: bool,
    headless: bool,
    godot_bin: str | None,
    logs: bool,
    status: bool,
) -> None:
    """Entry point behind `vibegame godot run`."""
    import typer

    from cli.godot import find_godot_binary, is_godot_project, project_engine
    from cli.run import (
        _display_server_log_path,
        _handle_existing_server,
        _read_server_info,
        _resolve_runtime_port,
        _tracked_server_lines,
    )

    project_path = project_path.resolve()
    if not (project_path / "project.json").is_file():
        typer.echo(f"Error: {project_path} is not a game project (no project.json)", err=True)
        raise typer.Exit(1)
    if not is_godot_project(project_path):
        typer.echo(
            f"Error: {project_path} is not a Godot project "
            f"(engine={project_engine(project_path) or 'missing'}); "
            "use `vibegame run` for Phaser projects",
            err=True,
        )
        raise typer.Exit(1)

    resolved_port = _resolve_runtime_port(port, host)

    if status:
        lines = _tracked_server_lines(project_path)
        if not lines:
            typer.echo("No tracked server found")
            raise typer.Exit(1)
        for line in lines:
            typer.echo(f"  {line}")
        raise typer.Exit(0)

    if logs:
        log_file = _display_server_log_path(project_path, resolved_port)
        if not log_file.exists():
            typer.echo(f"No server log file found for port {resolved_port}", err=True)
            raise typer.Exit(1)
        lines = log_file.read_text(encoding="utf-8").splitlines()
        for line in lines[-50:]:
            typer.echo(line)
        typer.echo(f"\nLog file: {log_file}")
        raise typer.Exit(0)

    binary = find_godot_binary(godot_bin)
    if not binary:
        from cli.godot import require_godot_binary

        require_godot_binary(godot_bin)

    _handle_existing_server(project_path, host, resolved_port)
    bridge_port = _free_port()

    if not background:
        typer.echo("=== VibeGame Godot Run ===")
        typer.echo(f"  Project: {project_path}")
        typer.echo(f"  Godot:   {binary}")
        typer.echo(f"  Game:    http://{host}:{resolved_port}")
        typer.echo(f"  Runtime API: http://{host}:{resolved_port}/api/runtime/")
        typer.echo(f"  Bridge port: {bridge_port}")
        typer.echo("  Press Ctrl+C to stop\n")
        try:
            code = serve(
                project_path,
                host=host,
                port=resolved_port,
                bridge_port=bridge_port,
                godot_bin=binary,
                headless=headless,
                background=False,
            )
        except BridgeError as exc:
            typer.echo(f"Error: {exc}", err=True)
            raise typer.Exit(1) from exc
        except OSError as exc:
            typer.echo(f"Error: could not start the Godot runtime: {exc}", err=True)
            raise typer.Exit(1) from exc
        raise typer.Exit(code)

    log_file = _server_log_path(project_path, resolved_port)
    log_file.parent.mkdir(parents=True, exist_ok=True)
    child_command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--serve",
        "--project",
        str(project_path),
        "--host",
        host,
        "--port",
        str(resolved_port),
        "--bridge-port",
        str(bridge_port),
        "--godot",
        binary,
    ]
    if headless:
        child_command.append("--headless")
    child_command.append("--background")

    with open(log_file, "w", encoding="utf-8") as log_handle:
        child = subprocess.Popen(
            child_command,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
        )

    deadline = time.monotonic() + 45
    info = None
    while time.monotonic() < deadline:
        info = _read_server_info(project_path, resolved_port)
        if info:
            break
        if child.poll() is not None:
            typer.echo("Godot runtime failed to start.", err=True)
            try:
                tail = log_file.read_text(encoding="utf-8").splitlines()[-20:]
            except OSError:
                tail = []
            for line in tail:
                typer.echo(f"  {line}", err=True)
            raise typer.Exit(1)
        time.sleep(0.25)

    if not info:
        typer.echo("Godot runtime still starting; check `vibegame godot run --logs`.", err=True)
        raise typer.Exit(1)

    typer.echo("=== VibeGame Godot Run (background) ===")
    typer.echo(f"  Project: {project_path}")
    typer.echo(f"  Game:    http://{host}:{resolved_port}")
    typer.echo(f"  Runtime API: http://{host}:{resolved_port}/api/runtime/")
    typer.echo(f"  Bridge port: {bridge_port}")
    typer.echo(f"  Runtime PID: {child.pid}")
    typer.echo(f"  Log: {log_file}")
    typer.echo("")
    typer.echo("  vibegame godot run --status   Server status")
    typer.echo("  vibegame godot run --logs     View logs")
    typer.echo("  vibegame close                Stop server")
    raise typer.Exit(0)


def main() -> None:
    parser = argparse.ArgumentParser(description="VibeGame Godot runtime adapter")
    parser.add_argument("--serve", action="store_true")
    parser.add_argument("--project", required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--bridge-port", type=int, required=True)
    parser.add_argument("--godot", required=True)
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--background", action="store_true")
    args = parser.parse_args()
    raise SystemExit(
        serve(
            Path(args.project),
            host=args.host,
            port=args.port,
            bridge_port=args.bridge_port,
            godot_bin=args.godot,
            headless=args.headless,
            background=args.background,
        )
    )


if __name__ == "__main__":
    main()
