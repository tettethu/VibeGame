"""VibeGame runtime server for `vibegame run`."""

import argparse
import asyncio
import json
import logging
import os
import secrets
from pathlib import Path

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles

# Load unified .env (git root)
from util.env import load_unified_env
from util.runtime import DEFAULT_RUNTIME_PORT

load_unified_env()

# Runtime host logging to .vibegame/logs/runtime-host.log
_LOG_DIR = Path.cwd() / ".vibegame" / "logs"
_LOG_DIR.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(_LOG_DIR / "runtime-host.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)

CLI_DIR = Path(__file__).parent
SRC_DIR = CLI_DIR.parent  # src/
ENGINE_DIR = SRC_DIR / "engine"  # src/engine/
MODULES_DIR = SRC_DIR / "modules"  # src/modules/
DEMO_DIR = SRC_DIR.parent / "examples" / "demo"  # examples/demo/


app = FastAPI(title="VibeGame Runtime Server")


@app.get("/")
async def game_page():
    """Serve index.html with dev runtime config injected.

    Reads project.json runtimeDefaults.dev and injects window.__APP_CONFIG__
    before any fallback script in index.html. This lets the page know where to
    send API requests when running under `vibegame run` (separate from the
    runtime server origin).
    """
    game_index = _game_cwd() / "index.html"
    if not game_index.exists():
        return Response(
            content="index.html not found in game project.\nRun 'vibegame init' first.\n",
            status_code=404,
        )

    html = game_index.read_text(encoding="utf-8")

    # Read dev defaults from project.json
    dev_cfg = {"appBasePath": "", "apiBaseUrl": ""}
    proj_file = _game_cwd() / "project.json"
    if proj_file.exists():
        try:
            proj = json.loads(proj_file.read_text(encoding="utf-8"))
            dev_defaults = proj.get("runtimeDefaults", {}).get("dev", {})
            if dev_defaults.get("appBasePath") is not None:
                dev_cfg["appBasePath"] = dev_defaults["appBasePath"]
            if dev_defaults.get("apiBaseUrl") is not None:
                dev_cfg["apiBaseUrl"] = dev_defaults["apiBaseUrl"]
        except (json.JSONDecodeError, OSError):
            pass

    config_script = (
        f'<script>window.__APP_CONFIG__ = {{ appBasePath: {json.dumps(dev_cfg["appBasePath"])}, '
        f'apiBaseUrl: {json.dumps(dev_cfg["apiBaseUrl"])} }}</script>'
    )

    # Inject before the fallback __APP_CONFIG__ script, or before </head> as fallback
    marker = "<script>window.__APP_CONFIG__"
    if marker in html:
        html = html.replace(marker, config_script + "\n" + marker)
    else:
        html = html.replace("</head>", config_script + "\n</head>")

    return Response(content=html, media_type="text/html")


# --- Game Project API ---


def _game_cwd() -> Path:
    """Resolve game project directory: app.state.default_cwd or demo fallback."""
    cwd = getattr(app.state, "default_cwd", None)
    if cwd:
        return Path(cwd).resolve()
    return DEMO_DIR.resolve()


def _resolve_engine_dir(game_dir: Path) -> Path | None:
    """Prefer project-local engine, otherwise serve source repo engine."""
    game_engine = game_dir / "engine"
    if game_engine.is_dir():
        return game_engine
    if ENGINE_DIR.is_dir():
        return ENGINE_DIR
    return None


def _resolve_modules_dir(game_dir: Path) -> Path | None:
    """Prefer project-local modules, otherwise serve source repo modules.

    Lets a modules-free skeleton run directly (`vibegame run .`): init copies
    modules into real projects, but skeletons rely on this fallback the same
    way they rely on the source-engine fallback.
    """
    game_modules = game_dir / "modules"
    if game_modules.is_dir():
        return game_modules
    if MODULES_DIR.is_dir():
        return MODULES_DIR
    return None


@app.get("/api/project")
async def get_project():
    """Read project.json from game project directory."""
    proj_file = _game_cwd() / "project.json"
    if not proj_file.exists():
        return JSONResponse({"error": "project.json not found"}, status_code=404)
    return JSONResponse(json.loads(proj_file.read_text(encoding="utf-8")))


# Engine + game files: no-cache so browser always gets latest during development
@app.middleware("http")
async def dev_no_cache(request: Request, call_next):
    response = await call_next(request)
    if request.url.path.startswith((
        "/engine/",
        "/modules/",
        "/assets/",
        "/scripts/",
        "/scenes/",
        "/config/",
        "/entities/",
    )) or request.url.path in ("/", "/index.html", "/project.json"):
        response.headers["Cache-Control"] = "no-store, must-revalidate"
    return response


# Engine mount is dynamic - see run_server(). Prefers game dir's engine/,
# then falls back to source repo src/engine/.


# --- Runtime API (agent-driven game automation) ---

_runtime_ws: WebSocket | None = None
_runtime_futures: dict[str, asyncio.Future] = {}
_runtime_token: str = os.environ.get("VIBEGAME_RUNTIME_TOKEN") or secrets.token_hex(16)


async def _runtime_send(cmd: str, **params) -> dict:
    """Send command to browser runtime bridge and await response."""
    if not _runtime_ws:
        return {"error": "No runtime connection. Ensure vibegame run is running."}
    req_id = secrets.token_hex(8)
    loop = asyncio.get_running_loop()
    future = loop.create_future()
    _runtime_futures[req_id] = future
    try:
        await _runtime_ws.send_json({"id": req_id, "cmd": cmd, **params})
    except Exception:
        _runtime_futures.pop(req_id, None)
        return {"error": "Runtime connection lost"}
    try:
        return await asyncio.wait_for(future, timeout=300)
    except asyncio.TimeoutError:
        _runtime_futures.pop(req_id, None)
        return {"error": "Timeout waiting for engine response"}


@app.post("/api/runtime/activate")
async def runtime_activate():
    """Start runtime control mode (pauses game immediately)."""
    return JSONResponse(await _runtime_send("activate"))


@app.post("/api/runtime/deactivate")
async def runtime_deactivate():
    """Stop runtime control mode."""
    return JSONResponse(await _runtime_send("deactivate"))


@app.post("/api/runtime/continue")
async def runtime_continue(request: Request):
    """Run N frames then pause. Blocks until done or breakpoint hit."""
    body = await request.json()
    frames = body.get("frames", 60)
    return JSONResponse(await _runtime_send("continue", frames=frames))


@app.post("/api/runtime/pause")
async def runtime_pause():
    """Pause immediately."""
    return JSONResponse(await _runtime_send("pause"))


@app.post("/api/runtime/play")
async def runtime_play():
    """Resume free-running play (returns immediately)."""
    return JSONResponse(await _runtime_send("play"))


@app.get("/api/runtime/snapshot")
async def runtime_snapshot():
    """Get current frame state as structured JSON."""
    return JSONResponse(await _runtime_send("snapshot"))


@app.get("/api/runtime/screenshot")
async def runtime_screenshot():
    """Capture viewport as PNG image via Playwright screenshot broker."""
    import urllib.request
    import urllib.error

    broker_port = os.environ.get("VIBEGAME_SCREENSHOT_PORT")
    if not broker_port:
        return JSONResponse(
            {"error": "Screenshots require foreground mode (vibegame run without -b)"},
            status_code=503,
        )
    try:
        resp = urllib.request.urlopen(f"http://127.0.0.1:{broker_port}/screenshot", timeout=15)
        png_bytes = resp.read()
        return Response(content=png_bytes, media_type="image/png")
    except urllib.error.HTTPError as exc:
        body = exc.read()
        return JSONResponse(
            {"error": f"Screenshot broker error: {body.decode(errors='replace')}"},
            status_code=exc.code,
        )
    except Exception as exc:
        return JSONResponse(
            {"error": f"Screenshot broker unavailable: {exc}"},
            status_code=503,
        )


@app.post("/api/runtime/refresh")
async def runtime_refresh():
    """Reload the browser page via Playwright broker."""
    import urllib.request
    import urllib.error

    broker_port = os.environ.get("VIBEGAME_SCREENSHOT_PORT")
    if not broker_port:
        return JSONResponse(
            {"error": "Refresh requires foreground mode (vibegame run without -b)"},
            status_code=503,
        )
    try:
        req = urllib.request.Request(f"http://127.0.0.1:{broker_port}/refresh", method="GET")
        resp = urllib.request.urlopen(req, timeout=90)
        return JSONResponse(json.loads(resp.read()))
    except urllib.error.HTTPError as exc:
        body = exc.read()
        return JSONResponse(
            {"error": f"Refresh broker error: {body.decode(errors='replace')}"},
            status_code=exc.code,
        )
    except Exception as exc:
        return JSONResponse(
            {"error": f"Refresh broker unavailable: {exc}"},
            status_code=503,
        )


@app.post("/api/runtime/input")
async def runtime_input(request: Request):
    """Inject virtual input. {action, held?} - held=true to hold, omit for one-shot press."""
    body = await request.json()
    return JSONResponse(await _runtime_send("input", **body))


@app.post("/api/runtime/set")
async def runtime_set(request: Request):
    """Set a node property at runtime. {nodeId, path, value}."""
    body = await request.json()
    return JSONResponse(await _runtime_send("set", **body))


@app.post("/api/runtime/click")
async def runtime_click(request: Request):
    """Simulate mouse click at game coordinates. {x, y, button?}."""
    body = await request.json()
    return JSONResponse(await _runtime_send("click", **body))


@app.post("/api/runtime/mousemove")
async def runtime_mousemove(request: Request):
    """Move pointer to game coordinates. {x, y}."""
    body = await request.json()
    return JSONResponse(await _runtime_send("mousemove", **body))


@app.post("/api/runtime/drag")
async def runtime_drag(request: Request):
    """Drag from one point to another. {from: {x, y}, to: {x, y}, steps?, button?}."""
    body = await request.json()
    return JSONResponse(await _runtime_send("drag", **body))


@app.post("/api/runtime/key")
async def runtime_key(request: Request):
    """Simulate keyboard event. {key, type?}. type: press|down|up."""
    body = await request.json()
    return JSONResponse(await _runtime_send("key", **body))


@app.post("/api/runtime/eval")
async def runtime_eval(request: Request):
    """Execute JS code in engine context. {code}. Returns eval result."""
    body = await request.json()
    return JSONResponse(await _runtime_send("eval", **body))


@app.get("/api/runtime/status")
async def runtime_status():
    """Get runtime controller status (active, mode, frame count)."""
    return JSONResponse(await _runtime_send("status"))


@app.get("/api/runtime/console")
async def runtime_console_get(since: int | None = None, level: str | None = None):
    """Get recent console entries. ?since=<seq> ?level=error|warn|info|log"""
    params = {}
    if since is not None:
        params["since"] = since
    if level is not None:
        params["level"] = level
    return JSONResponse(await _runtime_send("console_get", **params))


@app.post("/api/runtime/console/clear")
async def runtime_console_clear():
    """Clear console buffer."""
    return JSONResponse(await _runtime_send("console_clear"))


@app.get("/api/runtime/network")
async def runtime_network_get(since: int | None = None, failedOnly: bool = False):
    """Get recent network requests. ?since=<seq> ?failedOnly=1"""
    params = {}
    if since is not None:
        params["since"] = since
    if failedOnly:
        params["failedOnly"] = True
    return JSONResponse(await _runtime_send("network_get", **params))


@app.post("/api/runtime/network/clear")
async def runtime_network_clear():
    """Clear network buffer."""
    return JSONResponse(await _runtime_send("network_clear"))


@app.websocket("/ws/runtime")
async def ws_runtime(ws: WebSocket, token: str = ""):
    """Runtime bridge WebSocket - connects backend REST API to browser engine."""
    await ws.accept()
    if token != _runtime_token:
        logger.warning("Runtime bridge rejected: invalid token")
        await ws.close(code=4003, reason="Invalid runtime token")
        return
    global _runtime_ws
    if _runtime_ws:
        logger.warning("Runtime bridge rejected: already connected")
        await ws.close(code=4001, reason="Runtime bridge already connected")
        return
    _runtime_ws = ws
    logger.info("Runtime bridge connected")
    try:
        while True:
            raw = await ws.receive_text()
            if raw in ("__ping__", "__pong__"):
                continue
            data = json.loads(raw)
            req_id = data.get("id")
            if req_id and req_id in _runtime_futures:
                _runtime_futures[req_id].set_result(data.get("result", {}))
                del _runtime_futures[req_id]
    except WebSocketDisconnect:
        logger.info("Runtime bridge disconnected")
    finally:
        _runtime_ws = None
        for f in _runtime_futures.values():
            if not f.done():
                f.set_result({"error": "Runtime connection closed"})
        _runtime_futures.clear()


def run_server(cwd: str = ".", host: str = "127.0.0.1", port: int = DEFAULT_RUNTIME_PORT):
    """Start the web server programmatically."""
    import uvicorn

    cwd_resolved = str(Path(cwd).resolve())
    app.state.default_cwd = cwd_resolved

    game_dir = Path(cwd_resolved)
    engine_dir = _resolve_engine_dir(game_dir)
    if engine_dir:
        app.mount("/engine", StaticFiles(directory=str(engine_dir)), name="engine")
        logger.info(f"Mounted /engine/ -> {engine_dir}")
    else:
        logger.warning("No engine directory found for /engine mount")

    modules_dir = _resolve_modules_dir(game_dir)
    if modules_dir:
        app.mount("/modules", StaticFiles(directory=str(modules_dir)), name="modules")
        logger.info(f"Mounted /modules/ -> {modules_dir}")
    else:
        logger.warning("No modules directory found for /modules mount")

    # Mount game project files at root only. This matches `python -m http.server`
    # and avoids the old `/game/...` alias masking broken deployment paths.
    if (game_dir / "project.json").exists():
        # Serve assets symlink target first. The URL stays `/assets/...`, matching
        # static servers, while allowing Starlette to serve symlinked asset dirs.
        assets_link = game_dir / "assets"
        if assets_link.is_symlink():
            assets_target = assets_link.resolve()
            if assets_target.is_dir():
                app.mount("/assets", StaticFiles(directory=str(assets_target)), name="assets")
                logger.info(f"Mounted /assets/ -> {assets_target} (symlink target)")
        app.mount("/", StaticFiles(directory=cwd_resolved, html=True), name="root-static")
        logger.info(f"Mounted / (root-static) -> {cwd_resolved}")
    elif DEMO_DIR.is_dir():
        app.mount("/", StaticFiles(directory=str(DEMO_DIR), html=True), name="root-static")
        logger.info(f"Mounted / (root-static) -> {DEMO_DIR} (demo fallback)")

    logger.info(f"Starting server, cwd={cwd_resolved}, port={port}")

    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="VibeGame runtime server")
    parser.add_argument("cwd", nargs="?", default=".", help="Working directory for Claude agent")
    parser.add_argument("--port", type=int, default=DEFAULT_RUNTIME_PORT)
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args()
    run_server(cwd=args.cwd, host=args.host, port=args.port)
