"""Exercise object editing through the real Dashboard HTTP handler."""

import importlib
import json
import re
import threading
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

pytestmark = pytest.mark.base


@pytest.fixture
def dashboard(monkeypatch, tmp_path):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[3] / "src"))
    module = importlib.import_module("web.server")
    monkeypatch.setattr(module, "PROJECT_DIR", tmp_path)
    entity = tmp_path / "entities" / "hero.node.json"
    entity.parent.mkdir()
    entity.write_text(json.dumps({"name": "Hero", "config": {"speed": 100, "hp": 3}}))

    class Handler(module.DashboardRequestHandler):
        def log_message(self, *_args):
            pass

        def do_GET(self):
            if self.path == "/editor-test":
                styles = re.search(
                    r"<style>(.*?)</style>",
                    (module.STATIC_PATH / "index.html").read_text(encoding="utf-8"),
                    re.S,
                ).group(1)
                html = (
                    "<!doctype html><html><head><style>" + styles
                    + "</style></head><body style='display:flex;height:100vh'>"
                    "<aside id='sidebar' style='width:220px'></aside>"
                    "<main id='panel' style='flex:1;min-width:0'></main>"
                    "<output id='status' style='position:fixed;bottom:0;right:0'></output><script type='module'>"
                    "import * as objects from '/editor/objects-bridge.js';"
                    "window.objects = objects;"
                    "await objects.init(document.getElementById('sidebar'),"
                    "document.getElementById('panel'),"
                    "message => document.getElementById('status').textContent = message);"
                    "</script></body></html>"
                ).encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(html)))
                self.end_headers()
                self.wfile.write(html)
                return
            super().do_GET()

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    def request(method="GET", body=None, name="hero"):
        url = f"http://127.0.0.1:{server.server_port}/api/nodes/entities/{name}.node.json"
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(url, method=method, data=data, headers={
            "Content-Type": "application/json",
        })
        try:
            response = urllib.request.urlopen(req, timeout=10)
        except urllib.error.HTTPError as exc:
            response = exc
        with response:
            return response.status, json.load(response)

    request.base_url = f"http://127.0.0.1:{server.server_port}"
    try:
        yield module, entity, request
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=10)


def test_external_update_is_not_overwritten(dashboard):
    _, entity, request = dashboard
    _, loaded = request()
    external = {**loaded["data"], "config": {"speed": 200, "hp": 3}}
    entity.write_text(json.dumps(external))
    edited = {**loaded["data"], "config": {"speed": 100, "hp": 5}}
    status, result = request("PUT", {
        "data": edited, "baseVersion": loaded.get("version", "old-implementation"),
    })
    assert status == 409
    assert result["code"] == "edit_conflict"
    assert json.loads(entity.read_text()) == external


def test_consecutive_saves_return_new_versions(dashboard):
    _, entity, request = dashboard
    _, loaded = request()
    original = loaded["version"]
    for speed in (150, 200):
        loaded["data"]["config"]["speed"] = speed
        status, saved = request("PUT", {
            "data": loaded["data"], "baseVersion": loaded["version"],
        })
        assert status == 200
        assert saved["version"] != loaded["version"]
        loaded["version"] = saved["version"]
        assert request()[1]["version"] == saved["version"]
    assert loaded["version"] != original
    assert json.loads(entity.read_text())["config"]["speed"] == 200


@pytest.mark.parametrize("version,status", [(None, 428), ("", 400), (123, 400)])
def test_version_required(dashboard, version, status):
    _, entity, request = dashboard
    before = entity.read_bytes()
    body = {"data": {"name": "Replacement"}}
    if version is not None:
        body["baseVersion"] = version
    assert request("PUT", body)[0] == status
    assert entity.read_bytes() == before


def test_concurrent_saves_only_one_wins(dashboard):
    _, entity, request = dashboard
    _, loaded = request()
    barrier = threading.Barrier(2)

    def save(speed):
        barrier.wait(timeout=10)
        return request("PUT", {
            "data": {"name": "Hero", "config": {"speed": speed}},
            "baseVersion": loaded["version"],
        })[0]

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(save, [150, 200]))
    assert sorted(results) == [200, 409]
    assert json.loads(entity.read_text())["config"]["speed"] in (150, 200)


def test_revert_uses_same_precondition(dashboard):
    _, entity, request = dashboard
    _, loaded = request()
    entity.write_text(json.dumps({"name": "External"}))
    assert request("PUT", {
        "data": loaded["data"], "baseVersion": loaded["version"], "action": "revert",
    })[0] == 409
    assert json.loads(entity.read_text()) == {"name": "External"}


def test_format_change_is_detected(dashboard):
    _, entity, request = dashboard
    _, loaded = request()
    entity.write_text(json.dumps(loaded["data"], indent=4))
    assert request("PUT", {
        "data": loaded["data"], "baseVersion": loaded["version"],
    })[0] == 409


def test_actual_changes_are_logged(dashboard):
    _, entity, request = dashboard
    _, loaded = request()
    edited = {**loaded["data"], "config": {"speed": 200, "hp": 3}}
    status, result = request("PUT", {
        "data": edited, "baseVersion": loaded["version"],
        "changes": [{"path": "fake", "before": 0, "after": 1}],
    })
    assert status == 200
    assert result["changes"] == [{"field": "config.speed", "before": 100, "after": 200}]
    log = entity.parent.parent / ".vibegame" / "logs" / "user.jsonl"
    assert json.loads(log.read_text())["changes"] == result["changes"]


def test_failed_replace_preserves_file(dashboard, monkeypatch):
    module, entity, request = dashboard
    _, loaded = request()
    before = entity.read_bytes()

    def fail(*_args):
        raise OSError("simulated replace failure")

    monkeypatch.setattr(module.os, "replace", fail)
    assert request("PUT", {
        "data": {"name": "Replacement"}, "baseVersion": loaded["version"],
    })[0] == 500
    assert entity.read_bytes() == before
    assert list(entity.parent.iterdir()) == [entity]


@pytest.mark.parametrize("replacement,status", [(None, 404), ("{broken", 400), ("[]", 400)])
def test_external_removal_or_invalid_file(dashboard, replacement, status):
    _, entity, request = dashboard
    _, loaded = request()
    if replacement is None:
        entity.unlink()
    else:
        entity.write_text(replacement)
    assert request("PUT", {
        "data": loaded["data"], "baseVersion": loaded["version"],
    })[0] == status


def test_other_object_is_independent(dashboard):
    _, entity, request = dashboard
    other = entity.with_name("other.node.json")
    other.write_text('{"name":"Other"}')
    _, first = request()
    _, second = request(name="other")
    assert request("PUT", {
        "data": {"name": "Updated"}, "baseVersion": second["version"],
    }, name="other")[0] == 200
    assert request()[1]["version"] == first["version"]


@pytest.fixture
def editor(dashboard):
    _, entity, request = dashboard
    entity.with_name("other.node.json").write_text('{"name":"Other","config":{"speed":50}}')
    playwright = pytest.importorskip("playwright.sync_api")
    with playwright.sync_playwright() as p:
        if not Path(p.chromium.executable_path).is_file():
            pytest.skip("Install Playwright Chromium to run editor browser tests")
        browser = p.chromium.launch(headless=True, channel="chromium")
        context = browser.new_context(
            viewport={"width": 1440, "height": 960},
            permissions=["clipboard-read", "clipboard-write"],
        )
        page = context.new_page()
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(request.base_url + "/editor-test")
        page.locator('.at-file[data-path$="hero.node.json"]').click()
        page.locator('[data-path="config.hp"]').wait_for()
        try:
            yield page
            assert errors == []
        finally:
            browser.close()


def edit(page, field, value):
    control = page.locator('[data-path="config.' + field + '"]')
    control.fill(str(value))
    control.press("Tab")


def wait_status(page, text):
    page.wait_for_function(
        "text => document.getElementById('status').textContent.includes(text)", arg=text
    )


def test_editor_consecutive_save_and_undo(editor, dashboard):
    page = editor
    _, entity, _ = dashboard
    for speed in (150, 200):
        edit(page, "speed", speed)
        page.locator("#obj-save").click()
        page.wait_for_function("document.getElementById('obj-dirty').textContent === 'Saved'")
        assert json.loads(entity.read_text())["config"]["speed"] == speed
    edit(page, "speed", 250)
    page.locator("#obj-undo").click()
    assert page.locator('[data-path="config.speed"]').input_value() == "200"
    edit(page, "hp", 5)
    page.locator("#obj-save").click()
    page.wait_for_function("document.getElementById('obj-dirty').textContent === 'Saved'")
    assert json.loads(entity.read_text())["config"] == {"speed": 200, "hp": 5}


def test_editor_conflict_copy_reload_and_save(editor, dashboard, tmp_path):
    page = editor
    _, entity, _ = dashboard
    edit(page, "hp", 5)
    entity.write_text('{"name":"Hero","config":{"speed":200,"hp":3}}')
    page.locator("#obj-save").click()
    page.locator("#obj-conflict").wait_for(state="visible")
    assert page.locator('[data-path="config.hp"]').input_value() == "5"
    assert page.locator("#obj-dirty").inner_text() == "Conflict"
    assert page.locator("#obj-undo").is_enabled()
    assert json.loads(entity.read_text())["config"] == {"speed": 200, "hp": 3}
    page.screenshot(path=str(tmp_path / "object-conflict.png"))
    page.locator("#obj-copy-local").click()
    wait_status(page, "Copied local JSON")
    copied = page.evaluate("navigator.clipboard.readText()")
    assert json.loads(copied)["config"] == {"speed": 100, "hp": 5}
    page.once("dialog", lambda dialog: dialog.dismiss())
    page.locator("#obj-reload-disk").click()
    assert page.locator('[data-path="config.hp"]').input_value() == "5"
    page.once("dialog", lambda dialog: dialog.accept())
    page.locator("#obj-reload-disk").click()
    wait_status(page, "Reloaded ")
    assert page.locator('[data-path="config.speed"]').input_value() == "200"
    edit(page, "hp", 7)
    page.locator("#obj-save").click()
    wait_status(page, "Saved ")
    assert json.loads(entity.read_text())["config"] == {"speed": 200, "hp": 7}


def test_editor_revert_conflict_preserves_edits(editor, dashboard):
    page = editor
    _, entity, _ = dashboard
    edit(page, "hp", 5)
    entity.write_text('{"name":"External","config":{"speed":200,"hp":3}}')
    page.locator("#obj-revert").click()
    page.locator("#obj-conflict").wait_for(state="visible")
    assert page.locator('[data-path="config.hp"]').input_value() == "5"
    assert page.locator("#obj-undo").is_enabled()
    assert json.loads(entity.read_text())["name"] == "External"


def test_editor_revert_and_reload_failure(editor, dashboard):
    page = editor
    _, entity, _ = dashboard
    edit(page, "hp", 5)
    page.locator("#obj-revert").click()
    wait_status(page, "Reverted")
    assert page.locator('[data-path="config.hp"]').input_value() == "3"
    edit(page, "hp", 5)
    entity.write_text('{"name":"External","config":{"hp":7}}')
    page.locator("#obj-save").click()
    page.locator("#obj-conflict").wait_for(state="visible")
    entity.unlink()
    page.once("dialog", lambda dialog: dialog.accept())
    page.locator("#obj-reload-disk").click()
    wait_status(page, "Reload failed")
    assert page.locator('[data-path="config.hp"]').input_value() == "5"
    assert page.locator("#obj-copy-local").is_enabled()


def test_editor_undo_preserves_conflict(editor, dashboard):
    page = editor
    _, entity, _ = dashboard
    edit(page, "hp", 5)
    entity.write_text('{"name":"External"}')
    page.locator("#obj-save").click()
    page.locator("#obj-conflict").wait_for(state="visible")
    page.locator("#obj-undo").click()
    page.locator("#obj-conflict").wait_for(state="visible")
    assert page.locator("#obj-dirty").inner_text() == "Conflict"
    assert page.locator("#obj-save").is_disabled()
    assert page.locator('[data-path="config.hp"]').input_value() == "3"


def test_editor_network_failure_allows_retry(editor, dashboard):
    page = editor
    _, entity, _ = dashboard

    def abort_save(route):
        route.abort() if route.request.method == "PUT" else route.continue_()

    page.route("**/api/nodes/**", abort_save)
    edit(page, "hp", 5)
    page.locator("#obj-save").click()
    wait_status(page, "Save failed")
    assert page.locator("#obj-save").is_enabled()
    assert page.locator('[data-path="config.hp"]').input_value() == "5"
    page.unroute("**/api/nodes/**", abort_save)
    page.locator("#obj-save").click()
    wait_status(page, "Saved ")
    assert json.loads(entity.read_text())["config"]["hp"] == 5


def test_editor_late_save_does_not_mark_other_object_saved(editor, dashboard):
    page = editor
    pending = []

    def defer_save(route):
        if route.request.method == "PUT":
            pending.append((route, route.fetch()))
            page.evaluate("window.deferredSaveReady = true")
        else:
            route.continue_()

    page.route("**/api/nodes/**", defer_save)
    edit(page, "hp", 5)
    page.locator("#obj-save").click()
    page.wait_for_function("document.getElementById('obj-dirty').textContent === 'Saving'")
    page.wait_for_function("window.deferredSaveReady === true")
    page.locator('.at-file[data-path$="other.node.json"]').click()
    page.wait_for_function("document.querySelector('.obj-title')?.textContent === 'Other'")
    assert pending
    edit(page, "speed", 75)
    with page.expect_response(lambda response: response.request.method == "PUT"):
        pending[0][0].fulfill(response=pending[0][1])
    assert page.locator("#obj-dirty").inner_text() == "Unsaved"
    assert page.locator('[data-path="config.speed"]').input_value() == "75"


def test_editor_panel_switch_preserves_pending_conflict(editor, dashboard):
    page = editor
    _, entity, _ = dashboard
    pending = []

    def defer_save(route):
        if route.request.method == "PUT":
            pending.append((route, route.fetch()))
            page.evaluate("window.deferredSaveReady = true")
        else:
            route.continue_()

    page.route("**/api/nodes/**", defer_save)
    edit(page, "hp", 5)
    entity.write_text('{"name":"External"}')
    page.locator("#obj-save").click()
    page.wait_for_function("document.getElementById('obj-dirty').textContent === 'Saving'")
    page.wait_for_function("window.deferredSaveReady === true")
    assert pending
    page.evaluate("""() => {
      window.objects.destroy();
      document.getElementById('panel').innerHTML = '<p>Another panel</p>';
    }""")
    with page.expect_response(lambda response: response.request.method == "PUT"):
        pending[0][0].fulfill(response=pending[0][1])
    # Let the real fetch handler finish while the editor is unmounted.
    page.evaluate("() => new Promise(resolve => setTimeout(resolve, 0))")
    page.evaluate("""() => window.objects.init(
      document.getElementById('sidebar'), document.getElementById('panel'),
      message => document.getElementById('status').textContent = message)
    """)
    page.locator("#obj-conflict").wait_for(state="visible")
    assert page.locator('[data-path="config.hp"]').input_value() == "5"
    assert page.locator("#obj-undo").is_enabled()
