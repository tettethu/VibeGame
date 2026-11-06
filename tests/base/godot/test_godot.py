from __future__ import annotations

import json
import socket
import threading
from pathlib import Path

import jsonschema
import pytest
from typer.testing import CliRunner

from cli.godot import find_godot_binary, is_godot_project, project_engine
from cli.godot_check import check_godot_project
from cli.godot_runtime import BridgeClient, BridgeError
from cli.main import app

pytestmark = pytest.mark.base

SRC_ROOT = Path(__file__).resolve().parents[3] / "src"
runner = CliRunner()


def _init_project(tmp_path: Path) -> Path:
    project = tmp_path / "game"
    result = runner.invoke(
        app,
        ["godot", "init", str(project), "--name", "Test Game", "--lang", "en"],
    )
    assert result.exit_code == 0, result.output
    return project


def test_init_scaffolds_a_godot_project(tmp_path: Path) -> None:
    project = _init_project(tmp_path)
    assert (project / "project.godot").is_file()
    assert (project / "scenes" / "main.tscn").is_file()
    assert (project / "scripts" / "main.gd").is_file()
    assert (project / "addons" / "vibegame_bridge" / "bridge.gd").is_file()
    assert (project / ".vibegame" / "spec" / "godot" / "engine.md").is_file()
    assert (project / "CLAUDE.md").is_file()
    assert "{{language_name}}" not in (project / "CLAUDE.md").read_text(encoding="utf-8")

    data = json.loads((project / "project.json").read_text(encoding="utf-8"))
    assert data["engine"].startswith("godot@")
    assert data["startScene"] == "scenes/main.tscn"
    assert is_godot_project(project)
    assert project_engine(project) == data["engine"]


def test_project_schema_accepts_godot_engine(tmp_path: Path) -> None:
    project = _init_project(tmp_path)
    schema = json.loads(
        (SRC_ROOT / ".vibegame" / "schema" / "project.schema.json").read_text(encoding="utf-8")
    )
    data = json.loads((project / "project.json").read_text(encoding="utf-8"))
    jsonschema.validate(data, schema)


def test_check_passes_on_fresh_scaffold_without_godot(tmp_path: Path) -> None:
    project = _init_project(tmp_path)
    issues = check_godot_project(project, godot_bin=None, boot_check=False)
    assert [issue for issue in issues if issue.level == "error"] == []


def test_check_rejects_a_missing_entry_scene(tmp_path: Path) -> None:
    project = _init_project(tmp_path)
    (project / "scenes" / "main.tscn").unlink()
    issues = check_godot_project(project, godot_bin=None, boot_check=False)
    messages = " ".join(issue.message for issue in issues if issue.level == "error")
    assert "missing file" in messages


@pytest.mark.skipif(find_godot_binary() is None, reason="Godot is not installed")
def test_check_catches_a_gdscript_parse_error(tmp_path: Path) -> None:
    project = _init_project(tmp_path)
    script = project / "scripts" / "main.gd"
    script.write_text(script.read_text(encoding="utf-8") + "\nfunc broken( -> void:\n\tpass\n", encoding="utf-8")
    issues = check_godot_project(project, godot_bin=find_godot_binary(), boot_check=True)
    errors = [issue for issue in issues if issue.level == "error"]
    assert any("Parse Error" in issue.message for issue in errors), issues


class _FakeBridge:
    """One-connection fake of the Godot bridge protocol."""

    def __init__(self, responses: dict[str, dict]):
        self.responses = responses
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._socket.bind(("127.0.0.1", 0))
        self._socket.listen(1)
        self.port = self._socket.getsockname()[1]
        self._thread = threading.Thread(target=self._serve, daemon=True)

    def __enter__(self) -> "_FakeBridge":
        self._thread.start()
        return self

    def __exit__(self, *_exc) -> None:
        self._socket.close()

    def _serve(self) -> None:
        try:
            connection, _ = self._socket.accept()
        except OSError:
            return
        with connection, connection.makefile("rwb") as stream:
            for line in stream:
                request = json.loads(line)
                response = self.responses.get(request["cmd"], {"ok": False, "error": "unknown"})
                stream.write((json.dumps(response) + "\n").encode("utf-8"))
                stream.flush()


def test_bridge_client_roundtrip() -> None:
    with _FakeBridge(
        {
            "ping": {"ok": True, "engine": "godot"},
            "status": {"ok": True, "paused": False, "frame": 12},
        }
    ) as bridge:
        client = BridgeClient(port=bridge.port, timeout=5)
        client.connect()
        try:
            assert client.call("ping")["engine"] == "godot"
            assert client.call("status")["frame"] == 12
        finally:
            client.close()


def test_bridge_client_surfaces_bridge_errors() -> None:
    with _FakeBridge({"set": {"ok": False, "error": "node not found"}}) as bridge:
        client = BridgeClient(port=bridge.port, timeout=5)
        client.connect()
        try:
            with pytest.raises(BridgeError, match="node not found"):
                client.call("set", nodeId="Main", path="x", value=1)
        finally:
            client.close()


class _RecordingClient:
    """Stands in for BridgeClient behind the HTTP adapter and records every command."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    def call(self, command: str, **params) -> dict:
        self.calls.append((command, params))
        return {"ok": True, "result": 2}


def test_runtime_api_refuses_browser_requests(tmp_path: Path) -> None:
    """The runtime API refuses any request that carries an `Origin` header and never forwards it to the game.

    Target: Godot runtime HTTP adapter, src/cli/godot_runtime.py: _make_handler() -> Handler._dispatch().
    Input: a real ThreadingHTTPServer with the adapter handler and a recording bridge client. Requests: POST `/api/runtime/eval` with `Origin: https://evil.example`, the same POST without `Origin`, and OPTIONS `/api/runtime/eval` with `Origin`.
    Expect: the POST with `Origin` gets 403 and the client records no call. The POST without `Origin` gets 200 with result 2, and the client records exactly one `eval` call with code "1 + 1". No response has an `Access-Control-Allow-Origin` header. OPTIONS gets 501 (unsupported method), so a browser preflight cannot succeed.
    """
    import http.client
    from http.server import ThreadingHTTPServer

    from cli.godot_runtime import _make_handler

    client = _RecordingClient()
    server = ThreadingHTTPServer(("127.0.0.1", 0), _make_handler(client, tmp_path))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    def request(method: str, headers: dict[str, str]) -> http.client.HTTPResponse:
        connection = http.client.HTTPConnection("127.0.0.1", server.server_address[1], timeout=5)
        body = json.dumps({"code": "1 + 1"}) if method == "POST" else None
        connection.request(method, "/api/runtime/eval", body=body, headers={"Content-Type": "application/json", **headers})
        response = connection.getresponse()
        response.read()
        connection.close()
        return response

    try:
        browser = request("POST", {"Origin": "https://evil.example"})
        assert browser.status == 403
        assert client.calls == []

        cli = request("POST", {})
        assert cli.status == 200
        assert client.calls == [("eval", {"code": "1 + 1"})]

        preflight = request("OPTIONS", {"Origin": "https://evil.example"})
        assert preflight.status == 501
        for response in (browser, cli, preflight):
            assert response.getheader("Access-Control-Allow-Origin") is None
    finally:
        server.shutdown()
        server.server_close()
