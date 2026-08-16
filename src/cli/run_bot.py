"""
Bot runner for `vibegame run --bot <path>`.

Loads a Python bot file in-process via importlib, drives a Playwright-controlled
browser through a decide() loop, records trace + writes a verdict.

User-facing contract lives in `src/.vibegame/spec/engine/runtime.md` `## Runtime bot`.
This file is the implementation; do not duplicate the spec here.
"""

import importlib.util
import json
import signal
import threading
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Callable


# Phaser KeyCode names -> DOM KeyboardEvent.code.
# Source of truth: src/engine/InputMap.js DOM_TO_PHASER (line 9), inverted.
# Kept here so the runner does NOT need to import JS-side code.
PHASER_TO_DOM: dict[str, str] = {
    "LEFT": "ArrowLeft", "RIGHT": "ArrowRight", "UP": "ArrowUp", "DOWN": "ArrowDown",
    "SPACE": "Space", "ENTER": "Enter", "ESC": "Escape", "TAB": "Tab",
    "SHIFT": "ShiftLeft", "CTRL": "ControlLeft", "ALT": "AltLeft",
    "BACKSPACE": "Backspace", "DELETE": "Delete",
    **{c: f"Key{c}" for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"},
    **{str(d): f"Digit{d}" for d in range(10)},
}

DEFAULT_MAX_SECONDS = 10
TAP_HOLD_S = 0.04         # internal down->up hold for "tap" kind
TAP_HOLD_MIN_S = 0.02

TERMINAL_KINDS = {"done", "fail", "breakpoint"}
EXECUTE_KINDS = {"wait", "tap", "hold", "down", "up", "mousemove", "click", "drag"}


def load_bot(bot_path: Path) -> tuple[Callable, dict, Callable]:
    """Load bot file as a Python module via importlib.

    Returns (decide_fn, meta_dict, compact_fn).
    Raises ImportError if `decide` is missing.
    """
    spec = importlib.util.spec_from_file_location("user_bot", bot_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load bot file: {bot_path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    decide = getattr(mod, "decide", None)
    if decide is None:
        raise ImportError(f"bot {bot_path} has no `decide(snap, ctx)` function")
    meta = getattr(mod, "META", {})
    if not isinstance(meta, dict):
        raise TypeError(f"bot {bot_path}: META must be a dict, got {type(meta).__name__}")
    compact = getattr(mod, "compact", lambda snap, ctx: snap)
    return decide, meta, compact


def build_key_map(input_map_path: Path) -> dict[str, str]:
    """Read config/input-map.json -> {action: dom_code}.

    Mirrors src/engine/InputMap.js: accepts both flat `{action: [keys]}` and
    nested `{actions: {action: {keys: [...]}}}` shapes. Takes the FIRST listed
    physical key per action; unknown Phaser names fall through to the next.
    """
    if not input_map_path.exists():
        return {}
    data = json.loads(input_map_path.read_text(encoding="utf-8"))
    actions = data.get("actions", data) if isinstance(data, dict) else {}
    out: dict[str, str] = {}
    for action, val in actions.items():
        if isinstance(val, list):
            keys = val
        elif isinstance(val, dict):
            keys = val.get("keys", [])
        else:
            continue
        for k in keys:
            dom = PHASER_TO_DOM.get(str(k).upper())
            if dom:
                out[action] = dom
                break
    return out


class Ctx:
    """Runner-controlled state passed into bot.decide(snap, ctx).

    Pure data, no methods. See spec for field semantics.
    """

    def __init__(self, key_map: dict[str, str]) -> None:
        self.KEY: dict[str, str] = key_map
        self.scratch: dict[str, Any] = {}
        self.elapsed_s: float = 0.0
        self.tick: int = 0


def _normalize_keys(key: Any) -> list[str]:
    """Convert key field (str | list[str]) to list."""
    if isinstance(key, str):
        return [key]
    if isinstance(key, list):
        return [str(k) for k in key]
    raise TypeError(f"action key must be str or list[str], got {type(key).__name__}")


def _normalize_point(value: Any, label: str = "point") -> dict[str, Any]:
    """Convert {x,y} or [x,y] into a pointer target."""
    if isinstance(value, dict):
        x = value.get("x")
        y = value.get("y")
        space = value.get("space", "game")
        button = value.get("button", "left")
        steps = value.get("steps")
    elif isinstance(value, (tuple, list)) and len(value) == 2:
        x, y = value
        space = "game"
        button = "left"
        steps = None
    else:
        raise TypeError(f"{label} must be {{x, y}} or [x, y], got {type(value).__name__}")

    if not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
        raise TypeError(f"{label}.x and {label}.y must be numbers")
    if space not in {"game", "client"}:
        raise ValueError(f"{label}.space must be 'game' or 'client', got {space!r}")
    out = {"x": float(x), "y": float(y), "space": space, "button": button}
    if steps is not None:
        out["steps"] = int(steps)
    return out


def _point_to_client(page, point: dict[str, Any]) -> tuple[float, float]:
    """Resolve a pointer target to browser client coordinates."""
    if point["space"] == "client":
        return point["x"], point["y"]
    try:
        res = page.evaluate(
            "([x, y]) => window.__vibegameTest.gameToClient(x, y)",
            [point["x"], point["y"]],
        )
    except TypeError:
        # Unit-test mocks often expose a one-arg evaluate(). Treat game coords
        # as client coords there so action translation stays testable.
        res = {"x": point["x"], "y": point["y"]}
    if not isinstance(res, dict) or "x" not in res or "y" not in res:
        raise RuntimeError("window.__vibegameTest.gameToClient(x, y) returned invalid coordinates")
    return float(res["x"]), float(res["y"])


def _normalize_drag(value: Any) -> dict[str, Any]:
    """Convert a drag action key into start/end pointer targets."""
    if not isinstance(value, dict):
        raise TypeError(f"drag key must be a dict, got {type(value).__name__}")
    from_value = value.get("from") or (
        {"x": value.get("fromX"), "y": value.get("fromY")}
        if value.get("fromX") is not None and value.get("fromY") is not None else None
    )
    to_value = value.get("to") or (
        {"x": value.get("toX"), "y": value.get("toY")}
        if value.get("toX") is not None and value.get("toY") is not None else None
    )
    if from_value is None or to_value is None:
        raise TypeError("drag key must include 'from' and 'to'")
    default_space = value.get("space")
    if default_space and isinstance(from_value, dict) and "space" not in from_value:
        from_value = {**from_value, "space": default_space}
    if default_space and isinstance(to_value, dict) and "space" not in to_value:
        to_value = {**to_value, "space": default_space}
    return {
        "from": _normalize_point(from_value, "drag.from"),
        "to": _normalize_point(to_value, "drag.to"),
        "button": value.get("button", "left"),
        "steps": int(value.get("steps", 10)),
    }


def translate_action(page, action: tuple) -> str | None:
    """Execute one Action via Playwright. Returns terminal kind or None.

    Synchronous Playwright API. Raises on unknown kind.
    """
    if not isinstance(action, (tuple, list)) or len(action) != 4:
        raise ValueError(f"action must be a 4-tuple (kind, key, duration_s, reason), got: {action!r}")
    kind, key, duration, _reason = action

    if kind in TERMINAL_KINDS:
        return kind

    if kind not in EXECUTE_KINDS:
        raise ValueError(f"unknown action kind: {kind!r}")

    duration = float(duration)

    if kind == "wait":
        if duration > 0:
            time.sleep(duration)
        return None

    if kind == "tap":
        keys = _normalize_keys(key)
        for k in keys:
            page.keyboard.down(k)
        hold = min(TAP_HOLD_S, max(duration / 2, TAP_HOLD_MIN_S))
        time.sleep(hold)
        for k in keys:
            page.keyboard.up(k)
        remainder = duration - hold
        if remainder > 0:
            time.sleep(remainder)
        return None

    if kind == "hold":
        keys = _normalize_keys(key)
        for k in keys:
            page.keyboard.down(k)
        if duration > 0:
            time.sleep(duration)
        for k in keys:
            page.keyboard.up(k)
        return None

    if kind == "down":
        keys = _normalize_keys(key)
        # Press without releasing. Used for asymmetric input timing
        # (e.g. charge mechanics: down F -> tap W -> up F).
        # Caller is responsible for a matching "up" before the bot ends.
        for k in keys:
            page.keyboard.down(k)
        if duration > 0:
            time.sleep(duration)
        return None

    if kind == "mousemove":
        point = _normalize_point(key)
        x, y = _point_to_client(page, point)
        page.mouse.move(x, y)
        if duration > 0:
            time.sleep(duration)
        return None

    if kind == "click":
        point = _normalize_point(key)
        x, y = _point_to_client(page, point)
        page.mouse.click(x, y, button=point["button"])
        if duration > 0:
            time.sleep(duration)
        return None

    if kind == "drag":
        drag = _normalize_drag(key)
        start_x, start_y = _point_to_client(page, drag["from"])
        end_x, end_y = _point_to_client(page, drag["to"])
        page.mouse.move(start_x, start_y)
        page.mouse.down(button=drag["button"])
        page.mouse.move(end_x, end_y, steps=drag["steps"])
        page.mouse.up(button=drag["button"])
        if duration > 0:
            time.sleep(duration)
        return None

    # kind == "up"
    keys = _normalize_keys(key)
    for k in keys:
        page.keyboard.up(k)
    if duration > 0:
        time.sleep(duration)
    return None


def make_run_id(bot_path: Path) -> str:
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    return f"{ts}-{bot_path.stem}"


def _enter_breakpoint(page, server_url: str | None, reason: str) -> None:
    """Activate engine runtime control mode and block until SIGINT/SIGTERM."""
    try:
        page.evaluate("window.__vibegameTest.activate()")
    except Exception as e:
        print(f"warning: breakpoint activate failed: {e}")

    print()
    print(f"BREAKPOINT: {reason}")
    if server_url:
        print(f"  Server:  {server_url}")
        print(f"  Inspect: vibegame play snapshot")
        print(f"  Step:    vibegame play continue -f N")
    print(f"  Exit:    Ctrl+C this process", flush=True)

    stop = threading.Event()
    prev_int = signal.signal(signal.SIGINT, lambda *_: stop.set())
    prev_term = signal.signal(signal.SIGTERM, lambda *_: stop.set())
    try:
        while not stop.is_set():
            stop.wait(timeout=0.5)
    finally:
        signal.signal(signal.SIGINT, prev_int)
        signal.signal(signal.SIGTERM, prev_term)


def run_bot(
    page,
    project_path: Path,
    bot_path: Path,
    max_seconds: float | None = None,
    *,
    server_url: str | None = None,
    out_dir: Path | None = None,
) -> dict:
    """Run a bot loop against a ready Playwright page. Returns result dict.

    Caller is responsible for browser/context/video lifecycle and for ensuring
    `window.__vibegame_ready === true` before calling. This function additionally
    waits for `__vibegameTest.snapshot` to be available before starting the
    bot clock.

    out_dir lets the caller pre-compute the run dir (so it can route the
    Playwright video into the same dir via --shot). If omitted, a fresh
    timestamp-based dir under .vibegame/logs/bot/ is created.

    Side effects:
        Writes trace.jsonl + result.json under out_dir.
    """
    bot_path = bot_path.resolve()
    setup_start = time.perf_counter()

    decide, meta, compact = load_bot(bot_path)

    if out_dir is None:
        run_id = make_run_id(bot_path)
        out_dir = project_path / ".vibegame" / "logs" / "bot" / run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    trace_path = out_dir / "trace.jsonl"
    result_path = out_dir / "result.json"

    budget = float(max_seconds if max_seconds is not None else meta.get("max_seconds", DEFAULT_MAX_SECONDS))

    key_map = build_key_map(project_path / "config" / "input-map.json")
    ctx = Ctx(key_map=key_map)

    # Wait for the in-browser test surface to be ready, then probe once.
    page.wait_for_function(
        "typeof window.__vibegameTest?.snapshot === 'function'", timeout=10000
    )
    _ = page.evaluate("window.__vibegameTest.snapshot()")

    setup_s = time.perf_counter() - setup_start
    loop_start = time.perf_counter()

    status: str | None = None
    reason = ""
    error_str: str | None = None
    console_errors: list[dict] = []

    def _on_console(msg):
        if msg.type == "error":
            console_errors.append(
                {"level": msg.type, "text": msg.text, "time": time.time()}
            )

    page.on("console", _on_console)

    decisions_recorded = 0

    with trace_path.open("w", encoding="utf-8") as trace_f:
        while True:
            ctx.elapsed_s = time.perf_counter() - loop_start
            if ctx.elapsed_s > budget:
                status = "timeout"
                reason = f"exceeded {budget:.2f}s"
                break

            try:
                snap = page.evaluate("window.__vibegameTest.snapshot()")
            except Exception as exc:
                status = "crash"
                error_str = f"snapshot() failed: {exc}\n{traceback.format_exc()}"
                reason = "bot crashed: snapshot failed"
                break

            try:
                action = decide(snap, ctx)
            except Exception:
                status = "crash"
                error_str = traceback.format_exc()
                reason = "bot crashed: decide() raised"
                break

            try:
                state = compact(snap, ctx)
            except Exception:
                status = "crash"
                error_str = traceback.format_exc()
                reason = "bot crashed: compact() raised"
                break

            trace_entry = {
                "tick": ctx.tick,
                "t": round(ctx.elapsed_s, 4),
                "action": list(action) if isinstance(action, tuple) else action,
                "state": state,
            }
            trace_f.write(json.dumps(trace_entry, ensure_ascii=False) + "\n")
            trace_f.flush()
            decisions_recorded += 1

            try:
                terminal = translate_action(page, action)
            except Exception:
                status = "crash"
                error_str = traceback.format_exc()
                kind = action[0] if isinstance(action, (tuple, list)) and action else "?"
                reason = f"bot crashed: action {kind!r} execution"
                break

            if terminal in TERMINAL_KINDS:
                status = terminal
                reason = str(action[3]) if len(action) > 3 else terminal
                if terminal == "breakpoint":
                    _enter_breakpoint(page, server_url, reason)
                break

            ctx.tick += 1

    duration_s = time.perf_counter() - loop_start

    result = {
        "ok": status == "done",
        "status": status,
        "reason": reason,
        "setup_s": round(setup_s, 4),
        "duration_s": round(duration_s, 4),
        "decision_count": decisions_recorded,
        "bot_file": str(bot_path),
        "bot_meta": meta,
        "error": error_str,
        "console_errors": console_errors,
    }
    result_path.write_text(json.dumps(result, indent=2, ensure_ascii=False))

    return result
