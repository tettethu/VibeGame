#!/usr/bin/env python3
"""
VG Status Line - Context window usage display for Claude Code.

Called periodically by Claude Code via statusLine config in settings.json.

Two effects:
  1. Render an ANSI-colored line to stdout for the tmux pane title.
  2. Side-channel a `StatusLine` event to the running Dashboard so
     the sidebar can show per-agent context%.

Dashboard URL discovery:
  - VIBEGAME_DASHBOARD_URL env (full URL ending in /events), this hook only
  - then, as in web_hook.py, <VIBEGAME_TEAM_DIR>/state.json -> dashboard_port
    before the VIBEGAME_DASHBOARD_PORT env var

The dashboard side-channel is best-effort: a failure (no dashboard running,
network error, stale port) is silently swallowed so the tmux status line
keeps rendering even when the dashboard is down.
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from team.paths import state_path  # noqa: E402

CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
BRIGHT_RED = "\033[91m"
DIM = "\033[90m"
RESET = "\033[0m"


def _usage_color(pct: float) -> str:
    if pct < 50:
        return GREEN
    if pct < 75:
        return YELLOW
    if pct < 90:
        return RED
    return BRIGHT_RED


def generate(data: dict) -> str:
    model_data = data.get("model") or {}
    model = model_data.get("display_name", "Claude") if isinstance(model_data, dict) else str(model_data or "Claude")
    session_id = data.get("session_id", "") or "--------"
    ctx = data.get("context_window") or {}
    used_pct = float(ctx.get("used_percentage", 0) or 0)
    color = _usage_color(used_pct)
    return " | ".join([
        f"{CYAN}[{model}]{RESET}",
        f"context: {color}{used_pct:.1f}%{RESET}",
        f"{DIM}{session_id}{RESET}",
    ])


# -- Dashboard side-channel --

def _read_dashboard_state() -> dict:
    team_dir = os.environ.get("VIBEGAME_TEAM_DIR", "").strip()
    if not team_dir:
        return {}
    try:
        return json.loads(state_path(team_dir).read_text(encoding="utf-8"))
    except Exception:
        return {}


def _read_dashboard_port() -> str | None:
    port = _read_dashboard_state().get("dashboard_port")
    return str(port) if port else None


def _read_dashboard_token() -> str | None:
    token = os.environ.get("VIBEGAME_DASHBOARD_TOKEN", "").strip() or str(_read_dashboard_state().get("dashboard_token") or "").strip()
    return token or None


def _server_url() -> str | None:
    env_url = os.environ.get("VIBEGAME_DASHBOARD_URL", "").strip()
    if env_url:
        return env_url if env_url.endswith("/events") else env_url.rstrip("/") + "/events"
    # state.json before the env var, matching web_hook.py: the env var is frozen
    # at agent spawn time, while state.json carries the port of the dashboard
    # running right now. After a dashboard restart on a new port the stale env
    # value would otherwise win and every update would go to a dead port.
    port = _read_dashboard_port() or os.environ.get("VIBEGAME_DASHBOARD_PORT", "").strip()
    if port:
        return f"http://localhost:{int(port)}/events"
    return None


def _context_pct(data: dict) -> float | None:
    ctx = data.get("context_window") or {}
    try:
        pct = float(ctx.get("used_percentage"))
    except (TypeError, ValueError):
        return None
    if pct != pct:  # NaN
        return None
    return max(0.0, min(100.0, pct))


def _send_to_dashboard(data: dict) -> None:
    role = os.environ.get("VIBEGAME_MATE_NAME", "").strip() or os.environ.get("VIBEGAME_ROLE", "").strip()
    if not role:
        return  # Not a vibegame team session.
    session_id = (data.get("session_id") or "").strip()
    pct = _context_pct(data)
    url = _server_url()
    if not (session_id and pct is not None and url):
        return
    ctx = data.get("context_window") or {}
    payload = {
        "source_app": "claude",
        "session_id": session_id,
        "hook_event_type": "StatusLine",
        "timestamp": int(time.time() * 1000),
        "name": role,
        "context": {
            "used_percentage": pct,
            "used_tokens": ctx.get("used_tokens"),
            "max_tokens": ctx.get("max_tokens"),
        },
    }
    dashboard_token = _read_dashboard_token()
    if dashboard_token:
        payload["dashboard_token"] = dashboard_token
    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "User-Agent": "VG-StatusLine/1.0"},
        )
        urllib.request.urlopen(req, timeout=0.3).close()
    except Exception:
        pass  # Best-effort; ignore failures so the tmux line always renders.


def main() -> None:
    try:
        data = json.loads(sys.stdin.read())
    except Exception as exc:
        print(f"{RED}[VG] {exc}{RESET}")
        sys.exit(0)
    _send_to_dashboard(data)
    try:
        print(generate(data))
    except Exception as exc:
        print(f"{RED}[VG] {exc}{RESET}")
    sys.exit(0)


if __name__ == "__main__":
    main()
