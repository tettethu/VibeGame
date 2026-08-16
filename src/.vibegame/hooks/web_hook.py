#!/usr/bin/env python3
"""
VibeGame Web Hook - Registers agent sessions with the Dashboard server.

Sends session metadata (transcript_path, role, event_type) to the dashboard.
The server reads the transcript directly for conversation content.

Requires VIBEGAME_ROLE env var to identify the agent (e.g. "orchestrator", "artist").

Example settings.json hook:
    "PreToolUse": [{
        "type": "command",
        "command": "python .vibegame/hooks/web_hook.py --event-type PreToolUse",
        "timeout": 5000
    }]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path
import traceback

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


HOOK_INPUT_RAW = ""
HOOK_INPUT_DATA = None
HOOK_EVENT_TYPE = ""
HOOK_SOURCE_APP = ""
ERROR_LOG_WRITTEN = False



def _log(message: str) -> None:
    print(f"[web_hook] {message}", file=sys.stderr)


def _now_iso() -> str:
    return datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S")


def _repo_root() -> Path:
    """Return the primary repo root, resolving through git worktree .git pointer."""
    for parent in Path(__file__).resolve().parents:
        git = parent / '.git'
        if git.is_dir():
            return parent
        if git.is_file():
            try:
                text = git.read_text(encoding='utf-8').strip()
                if text.startswith('gitdir:'):
                    gitdir = Path(text[7:].strip())
                    if not gitdir.is_absolute():
                        gitdir = (parent / gitdir).resolve()
                    # gitdir = <main>/.git/worktrees/<name> -> parent.parent = <main>/.git
                    return gitdir.parent.parent.parent
            except Exception:
                pass
    return Path(__file__).resolve().parents[2]  # fallback: .vibegame/hooks/ -> project


def _fail(message: str) -> None:
    """Log error to file and exit silently (hooks must not crash noisily)."""
    _log(message)
    _append_error_log(message)
    sys.exit(1)


def _append_error_log(message: str, exc: BaseException | None = None) -> None:
    global ERROR_LOG_WRITTEN
    if ERROR_LOG_WRITTEN:
        return
    ERROR_LOG_WRITTEN = True
    try:
        log_path = hook_log_path()
        log_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "kind": "hook_error",
            "script": "web_hook.py",
            "message": message,
            "event_type": HOOK_EVENT_TYPE,
            "source_app": HOOK_SOURCE_APP,
            "hook_input_raw": HOOK_INPUT_RAW,
            "hook_input": HOOK_INPUT_DATA,
        }
        if exc is not None:
            payload["error_type"] = type(exc).__name__
            payload["error"] = str(exc)
            payload["traceback"] = traceback.format_exc()
        with open(log_path, 'a', encoding='utf-8') as f:
            f.write(f"[{_now_iso()}] [HOOK_ERROR] {json.dumps(payload, ensure_ascii=False, default=str)}\n")
    except Exception:
        pass


def _read_dashboard_state() -> dict:
    team_dir = os.environ.get('VIBEGAME_TEAM_DIR', '').strip()
    if not team_dir:
        return {}
    try:
        import json as _json
        from team.paths import state_path
        return _json.loads(state_path(team_dir).read_text(encoding='utf-8'))
    except Exception:
        return {}


def _read_dashboard_port() -> str | None:
    state = _read_dashboard_state()
    port = state.get('dashboard_port')
    return str(port) if port else None


def _read_dashboard_token() -> str | None:
    token = os.environ.get('VIBEGAME_DASHBOARD_TOKEN', '').strip() or str(_read_dashboard_state().get('dashboard_token') or '').strip()
    if token:
        return token
    return None


# -- Event sender --

def send_event(event_data: dict, server_url: str) -> bool:
    try:
        req = urllib.request.Request(
            server_url,
            data=json.dumps(event_data).encode('utf-8'),
            headers={'Content-Type': 'application/json', 'User-Agent': 'VG-Hook/1.0'}
        )
        with urllib.request.urlopen(req, timeout=1) as response:
            body = response.read().decode('utf-8', errors='replace')
            if response.status != 200:
                _fail(f"Dashboard events endpoint rejected request: {response.status} {body}")
    except Exception as exc:
        _fail(f"send_event_failed url={server_url} error={exc}")
    _log(f"event_sent type={event_data['hook_event_type']} session={event_data['session_id']} url={server_url}")
    return True


def send_permission_request(payload: dict, server_url: str) -> dict | None:
    url = server_url.replace('/events', '/permission')
    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode('utf-8'),
            headers={'Content-Type': 'application/json', 'User-Agent': 'VG-Hook/1.0'}
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = resp.read().decode('utf-8', errors='replace')
            if resp.status != 200:
                _fail(f"Dashboard permission endpoint rejected request: {resp.status} {body}")
            decision = json.loads(body)
            if not isinstance(decision, dict):
                _fail(f"Permission response must be a JSON object: {body}")
            return decision
    except Exception as exc:
        _fail(f"send_permission_failed url={url} error={exc}")


# -- Main --

def main():
    global HOOK_INPUT_RAW, HOOK_INPUT_DATA, HOOK_EVENT_TYPE, HOOK_SOURCE_APP
    global is_codex_subagent_transcript, hook_log_path

    # Plain sessions (no VIBEGAME_ROLE) are not part of a vibegame team - skip silently.
    role = os.environ.get('VIBEGAME_MATE_NAME', '').strip() or os.environ.get('VIBEGAME_ROLE', '').strip()
    if not role:
        sys.exit(0)

    # Project hooks also run in plain Claude Code sessions. Load project-owned
    # modules only after confirming this process belongs to a VibeGame session.
    from team.hook_identity import is_codex_subagent_transcript  # noqa: E402
    from team.logger import hook_log_path  # noqa: E402

    HOOK_INPUT_RAW = sys.stdin.read()

    parser = argparse.ArgumentParser(description='VibeGame Web Hook')
    parser.add_argument('--event-type', required=True)
    parser.add_argument('--source-app', default=None)
    parser.add_argument('--server-url', default=None)
    args = parser.parse_args()
    HOOK_EVENT_TYPE = args.event_type
    HOOK_SOURCE_APP = args.source_app or ""

    try:
        input_data = json.loads(HOOK_INPUT_RAW)
        HOOK_INPUT_DATA = input_data
    except json.JSONDecodeError as exc:
        _fail(f"invalid_stdin_json event_type={args.event_type} error={exc}")
    if not isinstance(input_data, dict):
        _fail('web_hook.py stdin must be a JSON object')

    if args.event_type != 'PermissionRequest' and is_codex_subagent_transcript(input_data.get('transcript_path')):
        _log(f"skip_codex_subagent event={args.event_type} session={input_data.get('session_id', '')}")
        sys.exit(0)

    # AskUserQuestion: deny and tell the model to ask in plain text. The decision
    # channel can only allow/deny, never carry the user's selection back to the tool,
    # so the dashboard chat box is the answer channel instead. No dashboard port needed.
    if args.event_type == 'PermissionRequest' and input_data.get('tool_name') == 'AskUserQuestion':
        output = {
            'hookSpecificOutput': {
                'hookEventName': 'PermissionRequest',
                'decision': {
                    'behavior': 'deny',
                    'message': 'Do not use this tool, just output your question and options(if any)',
                },
            }
        }
        print(json.dumps(output))
        sys.exit(0)

    default_port = _read_dashboard_port() or os.environ.get('VIBEGAME_DASHBOARD_PORT', '').strip()
    if not default_port:
        _fail('dashboard_port not found in state.json and VIBEGAME_DASHBOARD_PORT not set')
    server_url = args.server_url or f'http://localhost:{default_port}/events'

    # PermissionRequest: only ask browser for ExitPlanMode
    if args.event_type == 'PermissionRequest':
        tool_name = input_data.get('tool_name', '')
        if tool_name != 'ExitPlanMode':
            _fail(f"Unsupported PermissionRequest tool: {tool_name}")
        decision = send_permission_request(input_data, server_url)
        if not decision or 'behavior' not in decision:
            _fail(f"Permission response missing behavior: {decision}")
        output = {
            'hookSpecificOutput': {
                'hookEventName': 'PermissionRequest',
                'decision': decision,
            }
        }
        print(json.dumps(output))
        sys.exit(0)

    # Detect tmux pane at runtime (no extra env var needed)
    tmux_pane = None
    pane_target = os.environ.get('TMUX_PANE', '').strip()
    if pane_target:
        tmux_pane = pane_target
    if os.environ.get('TMUX'):
        try:
            import subprocess
            if not tmux_pane:
                command = ['tmux', 'display-message', '-p']
                if pane_target:
                    command.extend(['-t', pane_target])
                command.append('#{pane_id}')
                r = subprocess.run(
                    command,
                    capture_output=True, text=True, timeout=2,
                )
                if r.returncode == 0 and r.stdout.strip():
                    tmux_pane = r.stdout.strip()
        except Exception as exc:
            _log(f"tmux_probe_failed error={exc}")

    session_id = input_data.get('session_id', '')
    if not session_id:
        _fail('session_id missing from hook stdin')
    timestamp = input_data.get('timestamp') or int(datetime.now().timestamp() * 1000)
    cwd = input_data.get('cwd') or os.environ.get('CLAUDE_PROJECT_DIR', '').strip() or str(_repo_root())
    if not cwd:
        _fail(f"cwd missing for event {args.event_type}")

    if not args.source_app:
        _fail('--source-app is required')
    source_app = args.source_app

    event_data = {
        'source_app': source_app,
        'session_id': session_id,
        'hook_event_type': args.event_type,
        'timestamp': timestamp,
        'name': role,
        'transcript_path': input_data.get('transcript_path'),
        'cwd': cwd,
        'tmux_pane': tmux_pane,
        'model': input_data.get('model'),
    }
    dashboard_token = _read_dashboard_token()
    if dashboard_token:
        event_data['dashboard_token'] = dashboard_token

    send_event(event_data, server_url)
    sys.exit(0)


if __name__ == '__main__':
    try:
        main()
    except SystemExit as exc:
        if exc.code not in (0, None):
            _append_error_log(f"system_exit code={exc.code}", exc)
        raise
    except Exception as exc:
        _append_error_log("unhandled_exception", exc)
        raise
