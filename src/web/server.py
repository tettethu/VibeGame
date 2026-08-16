#!/usr/bin/env python3
"""
VibeGame Dashboard - Web server for game development.

Usage:
    python server.py server [--port PORT] [--host HOST] [--project DIR]

Serves the Dashboard, session management, and game project file browsing.
"""

import argparse
import re
import logging

logger = logging.getLogger('vibegame.dashboard')
import json
import os
import sqlite3
import subprocess
import sys
import threading
import time
import urllib.request
from datetime import datetime
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
import uuid
from pathlib import Path
from typing import Any, Optional
from urllib.parse import parse_qs, unquote, urlparse
from xml.etree import ElementTree

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from util.skills import rewrite_leading_skill  # noqa: E402
import socket

# Default configuration
DEFAULT_HOST = 'localhost'
STATIC_PATH = Path(__file__).parent / 'static'
GLOBAL_DASHBOARD_DIR = Path.home() / '.vibegame' / 'dashboard'

# Game project directory (set at startup via --project)
PROJECT_DIR: Optional[Path] = None
DASHBOARD_TOKEN: Optional[str] = None
IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg', '.bmp'}
PREVIEW_IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.webp', '.gif', '.svg', '.bmp'}
PREVIEW_TEXT_EXTENSIONS = {'.md', '.json', '.txt', '.yaml', '.yml', '.toml', '.py', '.js', '.ts', '.html', '.css', '.xml', '.csv', '.log'}
SESSION_SWEEP_INTERVAL_SECONDS = 5.0
MAX_DASHBOARD_PROMPT_CHARS = 12000
TMUX_SUBMIT_ENTER_DELAYS = (0.05, 0.35)
STREAM_DISCONNECTED_MARKER = 'stream disconnected before completion'
STREAM_DISCONNECTED_TOOL = 'StreamDisconnected'
CLAUDE_REQUEST_INTERRUPTED_MARKERS = {
    '[Request interrupted by user]',
    '[Request interrupted by user for tool use]',
}

# Play game file server (in-process, injects __APP_CONFIG__)
_terminal_codex_event_cache: dict[str, tuple[int, int, str | None]] = {}


def _empty_token_usage(provider: str) -> dict[str, Any]:
    return {
        'provider': provider,
        'input_tokens': 0,
        'cache_write_tokens': 0,
        'cached_input_tokens': 0,
        'output_tokens': 0,
        'reasoning_output_tokens': 0,
        'total_tokens': 0,
        'entries': 0,
        'groups': 0,
    }


def _token_int(data: dict, key: str) -> int:
    try:
        return int(data.get(key) or 0)
    except (TypeError, ValueError):
        return 0


def _claude_usage_values(usage: dict) -> dict[str, int]:
    values = {
        'input_tokens': _token_int(usage, 'input_tokens'),
        'cache_write_tokens': _token_int(usage, 'cache_creation_input_tokens'),
        'cached_input_tokens': _token_int(usage, 'cache_read_input_tokens'),
        'output_tokens': _token_int(usage, 'output_tokens'),
        'reasoning_output_tokens': 0,
    }
    values['total_tokens'] = sum(values.values())
    return values


def extract_claude_token_usage(path: str) -> dict[str, Any]:
    result = _empty_token_usage('claude')
    if not path:
        return result

    usage_by_key: dict[str, dict[str, int]] = {}
    try:
        with open(path) as f:
            for line_no, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue

                msg = entry.get('message', {})
                if not isinstance(msg, dict) or msg.get('role') != 'assistant':
                    continue
                usage = msg.get('usage')
                if not isinstance(usage, dict):
                    continue

                request_id = entry.get('requestId') or entry.get('request_id')
                message_id = msg.get('id') or entry.get('message_id')
                if request_id:
                    key = f"req:{request_id}"
                elif message_id:
                    key = f"msg:{message_id}"
                else:
                    key = f"line:{line_no}"

                result['entries'] += 1
                usage_by_key[key] = _claude_usage_values(usage)
    except Exception:
        return result

    result['groups'] = len(usage_by_key)
    for values in usage_by_key.values():
        for key in (
            'input_tokens',
            'cache_write_tokens',
            'cached_input_tokens',
            'output_tokens',
            'reasoning_output_tokens',
            'total_tokens',
        ):
            result[key] += values[key]
    return result


def extract_codex_token_usage(path: str) -> dict[str, Any] | None:
    if not path:
        return None

    result = _empty_token_usage('codex')
    latest: dict[str, Any] | None = None
    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue

                payload = entry.get('payload', {})
                if not isinstance(payload, dict):
                    continue
                if entry.get('type') != 'event_msg' or payload.get('type') != 'token_count':
                    continue

                info = payload.get('info')
                if not isinstance(info, dict):
                    continue
                usage = info.get('total_token_usage')
                if not isinstance(usage, dict):
                    continue

                result['entries'] += 1
                latest = usage
    except Exception:
        return None

    if latest is None:
        return None

    result['groups'] = 1
    result['input_tokens'] = _token_int(latest, 'input_tokens')
    result['cached_input_tokens'] = _token_int(latest, 'cached_input_tokens')
    result['output_tokens'] = _token_int(latest, 'output_tokens')
    result['reasoning_output_tokens'] = _token_int(latest, 'reasoning_output_tokens')
    total_tokens = _token_int(latest, 'total_tokens')
    result['total_tokens'] = total_tokens or (result['input_tokens'] + result['output_tokens'])
    return result


def extract_token_usage(path: str, is_codex_transcript: bool) -> dict[str, Any] | None:
    if is_codex_transcript:
        return extract_codex_token_usage(path)
    return extract_claude_token_usage(path)


def _project_runtime_dir(project_dir: Path) -> Path:
    return project_dir / '.vibegame' / 'dashboard'


def _default_runtime_dir(project_dir: Optional[Path] = None) -> Path:
    return _project_runtime_dir(project_dir) if project_dir else GLOBAL_DASHBOARD_DIR


def _default_db_path(project_dir: Optional[Path] = None) -> Path:
    return _default_runtime_dir(project_dir) / 'dashboard.db'


def _read_project_dev_config(project_dir: Path) -> dict:
    """Read runtimeDefaults.dev from project.json; return {appBasePath, apiBaseUrl}."""
    cfg = {'appBasePath': '', 'apiBaseUrl': ''}
    try:
        proj = json.loads((project_dir / 'project.json').read_text(encoding='utf-8'))
        dev = proj.get('runtimeDefaults', {}).get('dev', {})
        if dev.get('appBasePath') is not None:
            cfg['appBasePath'] = dev['appBasePath']
        if dev.get('apiBaseUrl') is not None:
            cfg['apiBaseUrl'] = dev['apiBaseUrl']
    except (OSError, json.JSONDecodeError):
        pass
    return cfg


def _path_is_inside(path: str | None, root: Path | None) -> bool:
    if not path or not root:
        return False
    try:
        resolved = Path(path).resolve()
        root_resolved = root.resolve()
        resolved.relative_to(root_resolved)
        return True
    except (OSError, ValueError):
        pass
    # Worktree: path like .../vibegame-worktree-<project>-<task> is a sibling
    # of project_dir. Match if the resolved path's name contains the project dir name.
    try:
        project_name = root.resolve().name
        resolved = Path(path).resolve()
        if f"worktree-{project_name}" in resolved.name:
            return True
        # Also handle ../project/../worktree style paths
        if f"worktree-{project_name}" in str(resolved):
            return True
    except (OSError, ValueError):
        pass
    return False


def _event_is_token_authenticated(event: dict) -> bool:
    """True when the event proves project membership with the dashboard token."""
    event_token = str(event.get('dashboard_token') or '').strip()
    return bool(DASHBOARD_TOKEN and event_token and event_token == DASHBOARD_TOKEN)


def _event_belongs_to_project(event: dict) -> bool:
    if not PROJECT_DIR:
        return True
    event_token = str(event.get('dashboard_token') or '').strip()
    if DASHBOARD_TOKEN and event_token:
        return event_token == DASHBOARD_TOKEN
    return _path_is_inside(event.get('cwd'), PROJECT_DIR)


def _tmux_pane_matches_working_dir(pane: str | None, working_dir: str | None) -> bool:
    """Return whether a live tmux pane is currently rooted in the claimed workspace."""
    if not pane or not working_dir:
        return False
    try:
        result = subprocess.run(
            ['tmux', 'display-message', '-p', '-t', pane, '#{pane_current_path}'],
            capture_output=True,
            text=True,
            timeout=2,
        )
        if result.returncode != 0:
            return False
        return _path_is_inside(result.stdout.strip(), Path(working_dir))
    except (OSError, subprocess.SubprocessError):
        return False


def _run_tmux_send_command(
    action: str,
    command: list[str],
    *,
    prompt: str | None = None,
    timeout: float,
) -> None:
    logger.info("[SEND] tmux_%s command=%s", action, command)
    try:
        result = subprocess.run(
            command,
            input=prompt,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        logger.error("[SEND] tmux_%s failed error=%s", action, exc)
        raise RuntimeError(f"tmux {action}: {exc}") from exc
    logger.info(
        "[SEND] tmux_%s returncode=%d stderr=%r",
        action,
        result.returncode,
        result.stderr.strip(),
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or "command failed without error text"
        raise RuntimeError(f"tmux {action}: {detail}")


def _tmux_send_prompt(pane: str, prompt: str) -> None:
    """Paste a complete prompt through a private tmux buffer and submit it."""
    prepared = prompt if prompt.endswith('\n') else prompt + '\n'
    buffer_name = f"vibegame-send-{uuid.uuid4().hex}"
    operation_error: RuntimeError | None = None
    cleanup_error: RuntimeError | None = None
    try:
        _run_tmux_send_command(
            "load-buffer",
            ['tmux', 'load-buffer', '-b', buffer_name, '-'],
            prompt=prepared,
            timeout=10,
        )
        _run_tmux_send_command(
            "paste-buffer",
            ['tmux', 'paste-buffer', '-p', '-r', '-b', buffer_name, '-t', pane],
            timeout=10,
        )
        for delay in TMUX_SUBMIT_ENTER_DELAYS:
            time.sleep(delay)
            _run_tmux_send_command(
                "Enter",
                ['tmux', 'send-keys', '-t', pane, 'Enter'],
                timeout=5,
            )
    except RuntimeError as exc:
        operation_error = exc
    try:
        _run_tmux_send_command(
            "delete-buffer",
            ['tmux', 'delete-buffer', '-b', buffer_name],
            timeout=2,
        )
    except RuntimeError as exc:
        cleanup_error = exc

    if operation_error is not None:
        if cleanup_error is not None:
            logger.error("[SEND] prompt failed and buffer cleanup also failed: %s", cleanup_error)
        raise operation_error
    if cleanup_error is not None:
        raise cleanup_error


def _read_review_doc(project_dir: Path, name: str, rel_path: str) -> dict[str, Any]:
    path = (project_dir / rel_path).resolve()
    root = project_dir.resolve()
    try:
        path.relative_to(root)
    except ValueError:
        return {'name': name, 'path': rel_path, 'exists': False, 'content': '', 'error': 'invalid path'}
    try:
        content = path.read_text(encoding='utf-8')
    except FileNotFoundError:
        return {'name': name, 'path': rel_path, 'exists': False, 'content': ''}
    except OSError as exc:
        return {'name': name, 'path': rel_path, 'exists': False, 'content': '', 'error': str(exc)}
    return {
        'name': name,
        'path': rel_path,
        'preview_path': str(path),
        'exists': True,
        'content': content,
        'mtime': int(path.stat().st_mtime * 1000),
    }


def _review_lock_state(project_dir: Path) -> dict[str, Any]:
    lock_path = project_dir / '.vibegame' / 'review-lock.json'
    review_log_path = project_dir / '.vibegame' / 'logs' / 'review.md'
    result: dict[str, Any] = {
        'state': 'open',
        'locked': False,
        'path': '.vibegame/review-lock.json',
        'exists': False,
        'review_log': {
            'path': '.vibegame/logs/review.md',
            'exists': review_log_path.is_file(),
        },
    }
    if review_log_path.is_file():
        try:
            result['review_log']['mtime'] = int(review_log_path.stat().st_mtime * 1000)
            result['review_log']['preview_path'] = str(review_log_path.resolve())
        except OSError:
            pass
    if not lock_path.exists():
        return result
    result['exists'] = True
    try:
        result['mtime'] = int(lock_path.stat().st_mtime * 1000)
        data = json.loads(lock_path.read_text(encoding='utf-8'))
    except json.JSONDecodeError as exc:
        result['state'] = 'unknown'
        result['error'] = f'invalid json: {exc.msg}'
        return result
    except OSError as exc:
        result['state'] = 'unknown'
        result['error'] = str(exc)
        return result
    if not isinstance(data, dict):
        result['state'] = 'unknown'
        result['error'] = 'lock payload is not an object'
        return result
    result['locked'] = bool(data.get('locked'))
    result['state'] = 'locked' if result['locked'] else 'open'
    if data.get('verdict') is not None:
        result['verdict'] = data.get('verdict')
    return result


def build_review_payload(project_dir: Optional[Path]) -> dict[str, Any]:
    if not project_dir:
        return {'docs': [], 'review_lock': {'state': 'unknown', 'error': 'project not configured'}}
    docs = [
        _read_review_doc(project_dir, 'goal.md', '.vibegame/goal.md'),
        _read_review_doc(project_dir, 'GDD.md', '.vibegame/GDD.md'),
        _read_review_doc(project_dir, 'assets.md', '.vibegame/assets.md'),
    ]
    return {
        'docs': docs,
        'review_lock': _review_lock_state(project_dir),
    }


PLAY_PREFIX = '/play'

# Game code resolves project files through appBasePath, but ES module specifiers
# do not: scripts import '/engine/Node.js' and the engine dynamically imports
# '/modules/...'. Under a prefix those resolve against the dashboard root, so an
# import map redirects the two roots that game code actually names.
PLAY_IMPORT_ROOTS = ('/engine/', '/modules/')


def _play_index_html(game_dir: Path) -> bytes | None:
    """The game's index.html, rebased to be served under PLAY_PREFIX."""
    index_path = game_dir / 'index.html'
    if not index_path.is_file():
        return None
    html = index_path.read_text(encoding='utf-8')
    imports = {root: f'{PLAY_PREFIX}{root}' for root in PLAY_IMPORT_ROOTS}
    # appBasePath is where the files are; apiBaseUrl stays whatever the project
    # configured, because this preview serves files only -- it is not the
    # runtime API, and pointing the engine's API calls at /play would 404.
    dev = _read_project_dev_config(game_dir)
    head = (
        f'<script>window.__APP_CONFIG__ = {{'
        f' appBasePath: {json.dumps(PLAY_PREFIX)},'
        f' apiBaseUrl: {json.dumps(dev.get("apiBaseUrl", ""))}'
        f' }}</script>\n'
        f'<script type="importmap">{json.dumps({"imports": imports})}</script>'
    )
    # The game's own line is `window.__APP_CONFIG__ = window.__APP_CONFIG__ || {...}`,
    # so injecting *before* it leaves our values in place.
    marker = '<script>window.__APP_CONFIG__'
    if marker in html:
        html = html.replace(marker, head + '\n' + marker, 1)
    else:
        html = html.replace('</head>', head + '\n</head>', 1)
    return html.encode('utf-8')


def _validate_play_path(game_dir: Path, rel: str) -> Path | None:
    """Resolve a path under the game project, refusing anything that escapes it."""
    root = game_dir.resolve()
    try:
        target = (root / rel.lstrip('/')).resolve()
    except OSError:
        return None
    if not target.is_relative_to(root) or not target.is_file():
        return None
    return target


def _validate_asset_path(rel_path: str) -> Path | None:
    """Validate that a relative path is under assets/ and return resolved Path, or None."""
    if not PROJECT_DIR:
        return None
    target = (PROJECT_DIR / rel_path).resolve()
    assets_dir = (PROJECT_DIR / 'assets').resolve()
    if not target.is_relative_to(assets_dir):
        return None
    return target


def _validate_node_path(rel_path: str) -> Path | None:
    """Validate that a relative path points to entities/nodes *.node.json."""
    if not PROJECT_DIR or not rel_path:
        return None
    candidate = Path(rel_path)
    if candidate.is_absolute() or candidate.suffix != '.json' or not candidate.name.endswith('.node.json'):
        return None
    try:
        target = (PROJECT_DIR / candidate).resolve()
        root = PROJECT_DIR.resolve()
        rel_parts = target.relative_to(root).parts
    except (OSError, ValueError):
        return None
    if not rel_parts or rel_parts[0] not in {'entities', 'nodes'}:
        return None
    if any(part in {'.vibegame', '.claude', '.codex', '.trellis', 'node_modules'} for part in rel_parts):
        return None
    return target


def _build_node_tree(game_dir: Path) -> dict:
    """Build a tree containing only entities/ and nodes/ *.node.json files."""
    root = {
        'name': game_dir.name,
        'type': 'folder',
        'path': '',
        'children': [],
    }
    for folder_name in ('entities', 'nodes'):
        folder = game_dir / folder_name
        if folder.is_dir():
            root['children'].append(_build_node_subtree(folder, game_dir))
    return root


def _build_node_subtree(dirpath: Path, game_dir: Path) -> dict:
    node = {
        'name': dirpath.name,
        'type': 'folder',
        'path': str(dirpath.relative_to(game_dir)),
        'children': [],
    }
    try:
        entries = sorted(dirpath.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
    except PermissionError:
        return node
    for entry in entries:
        if entry.name.startswith('.'):
            continue
        if entry.is_dir():
            child = _build_node_subtree(entry, game_dir)
            if child['children']:
                node['children'].append(child)
        elif entry.is_file() and entry.name.endswith('.node.json'):
            node['children'].append({
                'name': entry.name,
                'type': 'file',
                'path': str(entry.relative_to(game_dir)),
                'size': entry.stat().st_size,
            })
    return node


def _project_manifest_paths(project_dir: Path) -> list[Path]:
    """Return manifest paths in the same order the engine reads them."""
    root = project_dir.resolve()
    try:
        data = json.loads((project_dir / 'project.json').read_text(encoding='utf-8'))
        manifests = data.get('manifests', ['assets/manifest.json'])
        if not isinstance(manifests, list):
            manifests = ['assets/manifest.json']
    except (OSError, json.JSONDecodeError):
        manifests = ['assets/manifest.json']
    paths: list[Path] = []
    for raw in manifests:
        if isinstance(raw, str):
            try:
                path = (project_dir / raw).resolve()
                path.relative_to(root)
            except (OSError, ValueError):
                continue
            paths.append(path)
    return paths


def _resolve_manifest_texture(key: str) -> dict | None:
    """Resolve a manifest texture key to an image path and manifest entry."""
    if not PROJECT_DIR or not key:
        return None
    root = PROJECT_DIR.resolve()
    lookup_keys = [key]
    if ':' in key:
        base_key = key.rsplit(':', 1)[0]
        if base_key:
            lookup_keys.append(base_key)
    for manifest_path in _project_manifest_paths(PROJECT_DIR):
        if not manifest_path.is_file():
            continue
        try:
            manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(manifest, dict):
            continue
        for lookup_key in lookup_keys:
            entry = manifest.get(lookup_key)
            if not isinstance(entry, dict):
                continue
            result = {
                'key': lookup_key,
                'requestedKey': key,
                'manifest': str(manifest_path.relative_to(root)),
                'path': '',
                'url': '',
                'type': entry.get('type', 'image'),
                'frameWidth': entry.get('frameWidth'),
                'frameHeight': entry.get('frameHeight'),
                'pivot': entry.get('pivot'),
                'sprites': entry.get('sprites'),
            }
            rel_asset = entry.get('path')
            if not isinstance(rel_asset, str) or not rel_asset:
                result['missingPath'] = True
                return result
            try:
                image_path = (manifest_path.parent / rel_asset).resolve()
                image_rel = str(image_path.relative_to(root))
            except (OSError, ValueError):
                continue
            result['path'] = image_rel
            result['url'] = '/' + image_rel
            return result
    return None


def _diff_json(before: Any, after: Any, prefix: str = '') -> list[dict]:
    """Return simple path-based JSON diffs for user operation logs."""
    if before == after:
        return []
    if isinstance(before, list) and isinstance(after, list):
        changes: list[dict] = []
        for index in range(max(len(before), len(after))):
            path = f'{prefix}.{index}' if prefix else str(index)
            old = before[index] if index < len(before) else None
            new = after[index] if index < len(after) else None
            changes.extend(_diff_json(old, new, path))
        return changes
    if isinstance(before, dict) and isinstance(after, dict):
        changes: list[dict] = []
        keys = sorted(set(before.keys()) | set(after.keys()))
        for key in keys:
            path = f'{prefix}.{key}' if prefix else str(key)
            changes.extend(_diff_json(before.get(key), after.get(key), path))
        return changes
    return [{'field': prefix or '$', 'before': before, 'after': after}]


def _append_user_operation_log(entry: dict) -> None:
    if not PROJECT_DIR:
        raise RuntimeError('No project directory configured')
    log_path = PROJECT_DIR / '.vibegame' / 'logs' / 'user.jsonl'
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open('a', encoding='utf-8') as f:
        f.write(json.dumps(entry, ensure_ascii=False) + '\n')


def _preview_kind_for_path(path: Path | str) -> str | None:
    ext = Path(path).suffix.lower()
    if ext in PREVIEW_TEXT_EXTENSIONS:
        return 'markdown'
    if ext in PREVIEW_IMAGE_EXTENSIONS:
        return 'image'
    return None


def _preview_roots() -> list[Path]:
    roots: list[Path] = []
    seen: set[str] = set()

    def add_root(path: Path | None) -> None:
        if path is None:
            return
        try:
            resolved = path.resolve()
        except Exception:
            return
        key = str(resolved)
        if key in seen:
            return
        seen.add(key)
        roots.append(resolved)

    add_root(PROJECT_DIR)
    if db is not None:
        try:
            for session in db.get_sessions(limit=200):
                workdir = str(session.get('working_dir') or '').strip()
                if workdir:
                    add_root(Path(workdir))
        except Exception:
            pass
    return roots


def _resolve_preview_file_path(raw_path: str) -> Path | None:
    if not raw_path:
        return None
    candidate = Path(raw_path)
    was_relative = not candidate.is_absolute()
    if not candidate.is_absolute():
        if PROJECT_DIR is None:
            return None
        candidate = PROJECT_DIR / candidate
    kind = _preview_kind_for_path(candidate)
    if kind is None:
        return None
    try:
        resolved = candidate.resolve()
    except Exception:
        return None
    if not resolved.is_file():
        return None
    if was_relative:
        try:
            if PROJECT_DIR is None or not resolved.is_relative_to(PROJECT_DIR.resolve()):
                return None
        except Exception:
            return None
    # Text files restricted to project/worktree roots; images allowed anywhere
    if kind == 'image':
        return resolved
    for root in _preview_roots():
        try:
            if resolved.is_relative_to(root):
                return resolved
        except Exception:
            continue
    return None


def _format_dashboard_prompt(prompt: str, source_app: str | None = None) -> str:
    text = str(prompt)
    if not text.strip():
        return ''
    if len(text) > MAX_DASHBOARD_PROMPT_CHARS:
        raise ValueError(
            f"Message too long. Keep it under {MAX_DASHBOARD_PROMPT_CHARS} characters."
        )
    # Same rewrite `vibegame start` applies to its initial input; shared so a new
    # skill cannot work from one entry point and arrive as literal text on the other.
    return rewrite_leading_skill(source_app, text)


def _build_asset_tree(dirpath: Path, game_dir: Path, skip_dirs: set[str] | None = None) -> dict:
    """Build directory tree structure for assets/ folder."""
    node = {
        'name': dirpath.name,
        'type': 'folder',
        'path': str(dirpath.relative_to(game_dir)),
        'children': [],
    }
    try:
        entries = sorted(dirpath.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
    except PermissionError:
        return node
    for entry in entries:
        if entry.name.startswith('.'):
            continue
        if entry.is_dir():
            if skip_dirs and entry.name in skip_dirs:
                node['children'].append({
                    'name': entry.name,
                    'type': 'folder',
                    'path': str(entry.relative_to(game_dir)),
                    'children': [],
                    'lazy': True,
                })
            else:
                node['children'].append(_build_asset_tree(entry, game_dir, skip_dirs))
        elif entry.is_file() and entry.suffix.lower() in IMAGE_EXTENSIONS:
            node['children'].append({
                'name': entry.name,
                'type': 'file',
                'path': str(entry.relative_to(game_dir)),
                'size': entry.stat().st_size,
            })
    return node


def _guess_content_type(path: Path) -> str:
    """Guess MIME type from file extension."""
    ext = path.suffix.lower()
    types = {
        '.html': 'text/html', '.css': 'text/css', '.js': 'application/javascript',
        '.md': 'text/markdown; charset=utf-8',
        '.json': 'application/json', '.png': 'image/png', '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg', '.gif': 'image/gif', '.svg': 'image/svg+xml',
        '.webp': 'image/webp', '.mp3': 'audio/mpeg', '.ogg': 'audio/ogg',
        '.wav': 'audio/wav', '.woff2': 'font/woff2', '.woff': 'font/woff',
    }
    return types.get(ext, 'application/octet-stream')


class Database:
    """SQLite database manager for session metadata (transcript is the source of truth)."""

    def __init__(self, db_path: Path):
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        self._init_tables()

    def _init_tables(self):
        self.conn.executescript('''
            PRAGMA journal_mode = WAL;
            PRAGMA synchronous = NORMAL;

            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                source_app TEXT NOT NULL,
                session_id TEXT NOT NULL,
                name TEXT,
                transcript_path TEXT,
                working_dir TEXT,
                tmux_pane TEXT,
                started_at INTEGER NOT NULL,
                ended_at INTEGER,
                status TEXT DEFAULT 'active',
                sort_order INTEGER DEFAULT 0
            );

            CREATE INDEX IF NOT EXISTS idx_sessions_status
                ON sessions(status, started_at DESC);
        ''')
        # Migrate: add columns if missing
        for col, col_type in [
            ('name', 'TEXT'),
            ('transcript_path', 'TEXT'),
            ('tmux_pane', 'TEXT'),
            ('sort_order', 'INTEGER DEFAULT 0'),
            ('model', 'TEXT'),
            ('context_pct', 'REAL'),
            ('context_updated_at', 'INTEGER'),
        ]:
            try:
                self.conn.execute(f'SELECT {col} FROM sessions LIMIT 1')
            except sqlite3.OperationalError:
                self.conn.execute(f'ALTER TABLE sessions ADD COLUMN {col} {col_type}')
        self.conn.commit()

    # Roles that always have exactly one DB row per project; matched by name+cwd, not session_id.
    FIXED_ROLES = {'orchestrator', 'artist', 'designer', 'reviewer'}

    def upsert_session(self, source_app: str, session_id: str, **kwargs) -> str:
        """Insert or update a session, return composite id."""
        composite_id = f"{source_app}:{session_id}"
        now = int(time.time() * 1000)
        started_at = kwargs.get('started_at', now)
        working_dir = kwargs.get('working_dir')
        name = kwargs.get('name')
        transcript_path = kwargs.get('transcript_path')
        tmux_pane = kwargs.get('tmux_pane')
        model = kwargs.get('model')
        status = kwargs.get('status', 'stopped')

        with self._lock:
            existing_id = None

            # Fixed roles: match by (name, working_dir) so restarts replace in-place.
            if name and name in self.FIXED_ROLES and working_dir:
                row = self.conn.execute(
                    'SELECT id FROM sessions WHERE name = ? AND working_dir = ?',
                    (name, working_dir)
                ).fetchone()
                if row:
                    existing_id = row[0]

            # Dynamic sessions: normal (source_app, session_id) lookup.
            if existing_id is None:
                row = None
                if working_dir:
                    row = self.conn.execute(
                        'SELECT id FROM sessions WHERE source_app = ? AND session_id = ? AND working_dir = ?',
                        (source_app, session_id, working_dir)
                    ).fetchone()
                if row is None:
                    row = self.conn.execute(
                        'SELECT id FROM sessions WHERE source_app = ? AND session_id = ?',
                        (source_app, session_id)
                    ).fetchone()
                if row:
                    existing_id = row[0]

            if existing_id is not None:
                if name and name in self.FIXED_ROLES:
                    # Pending must not overwrite a real (non-pending) row — the real row must stay
                    # visible in the dashboard while the agent boots.
                    if source_app.endswith('-pending'):
                        existing_src = self.conn.execute(
                            'SELECT source_app FROM sessions WHERE id = ?', (existing_id,)
                        ).fetchone()
                        if existing_src and not existing_src[0].endswith('-pending'):
                            self.conn.commit()
                            return composite_id  # no-op: real row wins
                    # Full replace: update id/source_app/session_id so lifecycle calls use the new composite_id.
                    reset_context = existing_id != composite_id
                    self.conn.execute('''
                        UPDATE sessions SET
                            id              = ?,
                            source_app      = ?,
                            session_id      = ?,
                            transcript_path = COALESCE(?, transcript_path),
                            working_dir     = COALESCE(?, working_dir),
                            name            = ?,
                            tmux_pane       = COALESCE(?, tmux_pane),
                            model           = COALESCE(?, model),
                            context_pct     = CASE WHEN ? THEN NULL ELSE context_pct END,
                            context_updated_at = CASE WHEN ? THEN NULL ELSE context_updated_at END
                        WHERE id = ?
                    ''', (composite_id, source_app, session_id,
                          transcript_path, working_dir, name, tmux_pane, model,
                          reset_context, reset_context,
                          existing_id))
                else:
                    self.conn.execute('''
                        UPDATE sessions SET
                            transcript_path = COALESCE(?, transcript_path),
                            working_dir     = COALESCE(?, working_dir),
                            name            = COALESCE(?, name),
                            tmux_pane       = COALESCE(?, tmux_pane),
                            model           = COALESCE(?, model)
                        WHERE id = ?
                    ''', (transcript_path, working_dir, name, tmux_pane, model, existing_id))
            else:
                max_order = self.conn.execute(
                    'SELECT COALESCE(MAX(sort_order), -1) FROM sessions'
                ).fetchone()[0]
                self.conn.execute('''
                    INSERT INTO sessions
                        (id, source_app, session_id, name, transcript_path, working_dir, tmux_pane, started_at, status, sort_order, model)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (composite_id, source_app, session_id, name, transcript_path,
                      working_dir, tmux_pane, started_at, status, max_order + 1, model))
            self.conn.commit()
        return composite_id

    def stop_session(self, composite_id: str):
        now = int(time.time() * 1000)
        with self._lock:
            self.conn.execute(
                "UPDATE sessions SET status = 'stopped', ended_at = NULL, started_at = ? WHERE id = ?",
                (now, composite_id)
            )
            self.conn.commit()

    def merge_pending(self, tmux_pane: str | None, real_composite_id: str, name: str | None = None):
        """Delete pending session matching (tmux_pane+name) or name."""
        with self._lock:
            row = None
            if tmux_pane and name:
                # Require both pane AND name to avoid merging wrong agent (e.g. artist pane label
                # coinciding with orchestrator's registered pane label after tmux slot reuse).
                row = self.conn.execute(
                    "SELECT id FROM sessions WHERE source_app LIKE '%-pending' AND tmux_pane = ? AND name = ? AND id != ?",
                    (tmux_pane, name, real_composite_id)
                ).fetchone()
            if not row and name:
                row = self.conn.execute(
                    "SELECT id FROM sessions WHERE source_app LIKE '%-pending' AND name = ? AND id != ?",
                    (name, real_composite_id)
                ).fetchone()
            if row:
                self.conn.execute("DELETE FROM sessions WHERE id = ?", (row[0],))
                self.conn.commit()
                logger.info(f"[MERGE] Deleted pending session {row[0]} in favor of {real_composite_id}")

    def dedup_source_app(self, session_id: str, keep_composite_id: str) -> None:
        """Delete non-pending rows with the same session_id but different source_app."""
        with self._lock:
            rows = self.conn.execute(
                "SELECT id FROM sessions WHERE session_id = ? AND id != ? AND source_app NOT LIKE '%-pending'",
                (session_id, keep_composite_id)
            ).fetchall()
            for row in rows:
                self.conn.execute("DELETE FROM sessions WHERE id = ?", (row[0],))
                logger.info(f"[DEDUP] Deleted stale session {row[0]} in favor of {keep_composite_id}")
            if rows:
                self.conn.commit()

    def resume_session(self, composite_id: str, update_sort: bool = False):
        """Set session to running. update_sort=True bumps started_at (for UserPromptSubmit)."""
        now = int(time.time() * 1000)
        with self._lock:
            if update_sort:
                self.conn.execute(
                    "UPDATE sessions SET status = 'running', ended_at = NULL, started_at = ? WHERE id = ?",
                    (now, composite_id)
                )
            else:
                self.conn.execute(
                    "UPDATE sessions SET status = 'running', ended_at = NULL WHERE id = ?",
                    (composite_id,)
                )
            self.conn.commit()

    def wait_session(self, composite_id: str):
        """Set session to waiting (stop hook polling for teammate messages)."""
        with self._lock:
            self.conn.execute(
                "UPDATE sessions SET status = 'waiting' WHERE id = ?",
                (composite_id,)
            )
            self.conn.commit()

    def end_session(self, composite_id: str, status: str = 'ended'):
        now = int(time.time() * 1000)
        with self._lock:
            self.conn.execute(
                'UPDATE sessions SET status = ?, ended_at = ? WHERE id = ?',
                (status, now, composite_id)
            )
            self.conn.commit()

    def get_sessions(self, status: Optional[str] = None, limit: int = 50, project_dir: Path | None = None) -> list[dict]:
        with self._lock:
            if status:
                rows = self.conn.execute('''
                    SELECT * FROM sessions WHERE status = ?
                    ORDER BY started_at DESC LIMIT ?
                ''', (status, limit)).fetchall()
            else:
                rows = self.conn.execute('''
                    SELECT * FROM sessions
                    ORDER BY started_at DESC LIMIT ?
                ''', (limit,)).fetchall()

        # Fixed roles may have stale subagent rows with no pane; keep the row users can message.
        by_name: dict[str, dict] = {}
        unnamed = []
        for row in rows:
            d = self._to_dict(row)
            if project_dir and not _path_is_inside(d.get('working_dir'), project_dir):
                continue
            name = d.get('name') or ''
            if d.get('source_app', '').endswith('-pending') and not name:
                continue
            if not name:
                unnamed.append(d)
                continue
            existing = by_name.get(name)
            if existing is None or self._session_rank(d) > self._session_rank(existing):
                by_name[name] = d
        result = list(by_name.values()) + unnamed
        result.sort(key=lambda session: session.get('started_at') or 0, reverse=True)
        return result

    def _session_rank(self, session: dict) -> tuple[int, int, int]:
        has_tmux_pane = 1 if session.get('tmux_pane') else 0
        has_working_dir = 1 if session.get('working_dir') else 0
        started_at = int(session.get('started_at') or 0)
        if session.get('name') not in self.FIXED_ROLES:
            return (0, 0, started_at)
        return (has_tmux_pane, has_working_dir, started_at)

    def get_session(self, session_id: str) -> Optional[dict]:
        with self._lock:
            row = self.conn.execute(
                'SELECT * FROM sessions WHERE id = ?', (session_id,)
            ).fetchone()
        return self._to_dict(row) if row else None

    def get_sessions_for_sweep(self) -> list[dict]:
        with self._lock:
            rows = self.conn.execute('''
                SELECT * FROM sessions
                WHERE source_app NOT LIKE '%-pending'
                  AND tmux_pane IS NOT NULL
                  AND tmux_pane != ''
                  AND status IN ('running', 'stopped')
            ''').fetchall()
        return [self._to_dict(row) for row in rows]

    def delete_all_sessions(self) -> int:
        with self._lock:
            count = self.conn.execute('SELECT COUNT(*) FROM sessions').fetchone()[0]
            self.conn.execute('DELETE FROM sessions')
            self.conn.commit()
        return count

    def delete_session(self, session_id: str) -> bool:
        with self._lock:
            existing = self.conn.execute(
                'SELECT id FROM sessions WHERE id = ?', (session_id,)
            ).fetchone()
            if not existing:
                return False
            self.conn.execute('DELETE FROM sessions WHERE id = ?', (session_id,))
            self.conn.commit()
            return True

    def _to_dict(self, row: sqlite3.Row) -> dict:
        return {
            'id': row['id'],
            'source_app': row['source_app'],
            'session_id': row['session_id'],
            'name': row['name'],
            'transcript_path': row['transcript_path'],
            'working_dir': row['working_dir'],
            'tmux_pane': row['tmux_pane'],
            'started_at': row['started_at'],
            'ended_at': row['ended_at'],
            'status': row['status'],
            'model': row['model'],
            'context_pct': row['context_pct'],
            'context_updated_at': row['context_updated_at'],
        }

    def update_context(self, composite_id: str, pct: float) -> bool:
        """Update context_pct for an existing session row. Returns True if updated."""
        now = int(time.time() * 1000)
        with self._lock:
            cur = self.conn.execute(
                'UPDATE sessions SET context_pct = ?, context_updated_at = ? WHERE id = ?',
                (pct, now, composite_id),
            )
            self.conn.commit()
            return cur.rowcount > 0

    def close(self):
        self.conn.close()


def _extract_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return '\n'.join(
            b.get('text', '') for b in content
            if isinstance(b, dict) and b.get('type') == 'text'
        )
    return ''


def _should_hide_claude_entry_by_structure(entry: dict) -> bool:
    """Hide transcript entries only when Claude marks them structurally."""
    if entry.get('isMeta'):
        return True
    return entry.get('type') == 'system'


def _is_system_injection(text: str) -> str | None:
    """Detect system-injected user messages. Returns tool name if detected, None otherwise."""
    stripped = str(text or '').strip()
    if '<task-notification' in stripped:
        return 'TaskNotification'
    if stripped.startswith('<system-reminder>'):
        return 'SystemReminder'
    if '<hook_prompt' in stripped:
        return 'StopHook'
    if '<subagent_notification' in stripped:
        return 'SubagentNotification'
    if stripped.startswith('<skill>'):
        return 'Skill'
    if stripped.startswith('# AGENTS.md instructions for '):
        return 'SessionStart'
    return None


def _parse_skill_name(text: str) -> str:
    """Extract skill name from <skill><name>...</name> block."""
    match = re.search(r'<skill>\s*<name>([^<]+)</name>', text)
    return match.group(1).strip() if match else 'skill'


def _extract_xml_block(text: str, tag: str) -> tuple[ElementTree.Element, str, str, int] | None:
    if not isinstance(text, str):
        return None
    start_tag = f'<{tag}>'
    end_tag = f'</{tag}>'
    start = text.find(start_tag)
    if start < 0:
        return None
    end = text.find(end_tag, start)
    if end < 0:
        return None
    block = text[start:end + len(end_tag)]
    try:
        root = ElementTree.fromstring(block.strip())
    except ElementTree.ParseError:
        return None
    if root.tag != tag:
        return None
    return root, text[:start].strip(), text[end + len(end_tag):].strip(), start


def _extract_environment_context(text: str) -> tuple[dict[str, Any], str, str, int] | None:
    extracted = _extract_xml_block(text, 'environment_context')
    if not extracted:
        return None
    root, before, after, start = extracted
    workspace_roots = [
        (node.text or '').strip()
        for node in root.findall('./filesystem/workspace_roots/root')
        if (node.text or '').strip()
    ]
    permission_profile = root.find('./filesystem/permission_profile')
    file_system = root.find('./filesystem/permission_profile/file_system')
    context: dict[str, Any] = {
        'cwd': (root.findtext('cwd') or '').strip(),
        'shell': (root.findtext('shell') or '').strip(),
        'current_date': (root.findtext('current_date') or '').strip(),
        'timezone': (root.findtext('timezone') or '').strip(),
        'workspace_roots': workspace_roots,
        'permission_profile': permission_profile.get('type') if permission_profile is not None else '',
        'file_system': file_system.get('type') if file_system is not None else '',
    }
    return context, before, after, start


def _extract_codex_skill(text: str) -> tuple[dict[str, str], str, str, int] | None:
    if not isinstance(text, str):
        return None
    start = text.find('<skill>')
    if start < 0:
        return None
    end_tag = '</skill>'
    end = text.find(end_tag, start)
    if end < 0:
        return None
    inner = text[start + len('<skill>'):end]
    name_match = re.search(r'<name>\s*([^<\n]+?)\s*</name>', inner)
    path_match = re.search(r'<path>\s*([^<\n]+?)\s*</path>', inner)
    if not name_match or not path_match or path_match.start() < name_match.end():
        return None
    skill = {
        'name': name_match.group(1).strip(),
        'path': path_match.group(1).strip(),
        'content': inner[path_match.end():].strip(),
    }
    if not skill['name'] or not skill['path'] or not skill['content']:
        return None
    return skill, text[:start].strip(), text[end + len(end_tag):].strip(), start


def _extract_codex_project_instructions(
    text: str,
) -> tuple[dict[str, str], str, str, int] | None:
    if not isinstance(text, str):
        return None
    header = re.search(r'^# AGENTS\.md instructions for ([^\n]+)\s*$', text, re.MULTILINE)
    if not header:
        return None
    open_tag = '<INSTRUCTIONS>'
    close_tag = '</INSTRUCTIONS>'
    open_start = text.find(open_tag, header.end())
    if open_start < 0 or text[header.end():open_start].strip():
        return None
    close_start = text.find(close_tag, open_start + len(open_tag))
    if close_start < 0:
        return None
    content = text[open_start + len(open_tag):close_start].strip()
    paragraphs = [
        re.sub(r'\s+', ' ', paragraph).strip()
        for paragraph in re.split(r'\n\s*\n', content)
        if paragraph.strip()
    ]
    project_path = header.group(1).strip()
    if not project_path or not content or not paragraphs:
        return None
    instructions = {
        'project_path': project_path,
        'source_path': str(Path(project_path) / 'AGENTS.md'),
        'summary': paragraphs[0],
        'content': content,
    }
    end = close_start + len(close_tag)
    return instructions, text[:header.start()].strip(), text[end:].strip(), header.start()


def _extract_codex_context_block(text: str) -> tuple[str, dict[str, Any], str, str] | None:
    agents_header = re.search(r'^# AGENTS\.md instructions for [^\n]+\s*$', text, re.MULTILINE)
    markers = [
        (text.find('<environment_context>'), 'EnvironmentContext', '</environment_context>'),
        (text.find('<skill>'), 'Skill', '</skill>'),
        (
            agents_header.start() if agents_header else -1,
            'ProjectInstructions',
            '</INSTRUCTIONS>',
        ),
    ]
    candidates = [marker for marker in markers if marker[0] >= 0]
    if not candidates:
        return None
    start, tool, close_tag = min(candidates, key=lambda marker: marker[0])
    extractors = {
        'EnvironmentContext': _extract_environment_context,
        'Skill': _extract_codex_skill,
        'ProjectInstructions': _extract_codex_project_instructions,
    }
    extracted = extractors[tool](text)
    if extracted and extracted[3] == start:
        data, before, after, _ = extracted
        return tool, data, before, after

    error_names = {
        'EnvironmentContext': 'environment context',
        'Skill': 'Skill context',
        'ProjectInstructions': 'AGENTS.md context',
    }
    close_start = text.find(close_tag, start)
    after = text[close_start + len(close_tag):].strip() if close_start >= 0 else ''
    return (
        'ContextParseError',
        {'message': f'Unable to parse Codex {error_names[tool]} injection'},
        text[:start].strip(),
        after,
    )


def _append_codex_context_message(
    messages: list[dict],
    tool: str,
    context: dict[str, Any],
    ts: str | int | None,
) -> None:
    identity = context.get('name') or context.get('project_path') or context.get('current_date') or 'context'
    messages.append({
        'role': 'tool_use',
        'tool': tool,
        'input': context,
        'id': f'codex-context:{tool}:{ts or identity}:{len(messages)}',
        'ts': ts,
    })


def _append_codex_user_text(messages: list[dict], text: str, ts: str | int | None) -> None:
    text = str(text or '').strip()
    if not text:
        return
    hook_prompt = _parse_codex_hook_prompt(text)
    if hook_prompt:
        messages.append({
            'role': 'tool_use',
            'tool': 'StopHook',
            'input': {
                'action': 'continue',
                'event': hook_prompt.get('event', ''),
                'details': hook_prompt.get('details', ''),
                'hook_run_id': hook_prompt.get('hook_run_id', ''),
            },
            'id': '',
            'ts': ts,
        })
        return
    system_tool = _is_system_injection(text)
    if system_tool:
        input_data = {'name': _parse_skill_name(text)} if system_tool == 'Skill' else {'text': text}
        messages.append({
            'role': 'tool_use',
            'tool': system_tool,
            'input': input_data,
            'id': '',
            'ts': ts,
        })
        return
    messages.append({'role': 'user', 'text': text, 'ts': ts})


def _append_codex_user_text_with_context(
    messages: list[dict],
    text: str,
    ts: str | int | None,
) -> None:
    rest = str(text or '').strip()
    while rest:
        extracted = _extract_codex_context_block(rest)
        if not extracted:
            _append_codex_user_text(messages, rest, ts)
            return
        tool, data, before, after = extracted
        _append_codex_user_text(messages, before, ts)
        _append_codex_context_message(messages, tool, data, ts)
        rest = after


def _normalize_claude_user_text(text: str) -> str | None:
    stripped = str(text or '').strip()
    if not stripped:
        return None
    if not (stripped.startswith('<command-message>') and '<command-name>' in stripped):
        return stripped

    command_name = None
    command_args = ''
    name_start = stripped.find('<command-name>')
    name_end = stripped.find('</command-name>')
    if name_start != -1 and name_end != -1 and name_end > name_start:
        command_name = stripped[name_start + len('<command-name>'):name_end].strip()

    args_start = stripped.find('<command-args>')
    args_end = stripped.find('</command-args>')
    if args_start != -1 and args_end != -1 and args_end > args_start:
        command_args = stripped[args_start + len('<command-args>'):args_end].strip()

    if not command_name:
        return None
    if command_args:
        return f"{command_name}\n{command_args}"
    return command_name


def _is_codex_turn_aborted_message(text: str) -> bool:
    return '<turn_aborted>' in text and '</turn_aborted>' in text


def _is_claude_request_interrupted_message(text: str) -> bool:
    return str(text or '').strip() in CLAUDE_REQUEST_INTERRUPTED_MARKERS


def _interrupted_message(ts: Any = None) -> dict:
    return {
        'role': 'tool_use',
        'tool': 'interrupted',
        'input': {'summary': 'User interrupted the turn'},
        'id': '',
        'ts': ts,
    }


def _parse_codex_hook_prompt(text: str) -> dict | None:
    stripped = str(text or '').strip()
    if not stripped.startswith('<hook_prompt') or not stripped.endswith('</hook_prompt>'):
        return None
    match = re.match(r'^<hook_prompt\b([^>]*)>(.*)</hook_prompt>$', stripped, re.DOTALL)
    if not match:
        return None
    attrs = match.group(1) or ''
    body = (match.group(2) or '').strip()
    run_match = re.search(r'hook_run_id="([^"]+)"', attrs)
    hook_run_id = run_match.group(1) if run_match else ''
    event = hook_run_id.split(':', 1)[0] if hook_run_id else ''
    return {
        'event': event or 'hook',
        'hook_run_id': hook_run_id,
        'details': body,
    }


def _collapse_interrupted_before_user(messages: list[dict]) -> list[dict]:
    collapsed: list[dict] = []
    total = len(messages)
    for index, message in enumerate(messages):
        if message.get('tool') == 'interrupted':
            next_message = messages[index + 1] if index + 1 < total else None
            if next_message and next_message.get('role') == 'user':
                continue
        collapsed.append(message)
    return collapsed


def _stream_disconnect_text(text: str | None) -> str | None:
    text = str(text or '').strip()
    if not text:
        return None
    idx = text.lower().find(STREAM_DISCONNECTED_MARKER)
    if idx == -1:
        return None
    end = text.find('\n', idx)
    if end == -1:
        end = len(text)
    return text[idx:end].strip()


def _stream_disconnect_message(message: str, ts: Any = None) -> dict:
    return {
        'role': 'tool_use',
        'tool': STREAM_DISCONNECTED_TOOL,
        'input': {'message': message},
        'id': '',
        'ts': ts,
    }


def _terminal_codex_event(path: str) -> str | None:
    if not path:
        return None
    try:
        stat = Path(path).stat()
    except OSError:
        return None
    cache_key = str(path)
    cached = _terminal_codex_event_cache.get(cache_key)
    fingerprint = (stat.st_mtime_ns, stat.st_size)
    if cached and cached[:2] == fingerprint:
        return cached[2]

    last_lifecycle_event: str | None = None
    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                payload = entry.get('payload', {})
                if entry.get('type') != 'event_msg' or not isinstance(payload, dict):
                    continue
                event_type = payload.get('type')
                if event_type == 'task_started':
                    last_lifecycle_event = 'task_started'
                elif event_type == 'task_complete':
                    last_lifecycle_event = 'task_complete'
                elif event_type == 'error' and _stream_disconnect_text(payload.get('message')):
                    last_lifecycle_event = 'stream_disconnect'
    except Exception:
        result = None
    else:
        result = last_lifecycle_event if last_lifecycle_event in ('task_complete', 'stream_disconnect') else None
    _terminal_codex_event_cache[cache_key] = (*fingerprint, result)
    return result


def has_terminal_codex_stream_disconnect(path: str) -> bool:
    return _terminal_codex_event(path) == 'stream_disconnect'


def has_terminal_codex_task_complete(path: str) -> bool:
    return _terminal_codex_event(path) == 'task_complete'


def _is_codex_transcript_path(path: str | None) -> bool:
    return bool(path and '.codex/sessions/' in path)


def _apply_terminal_transcript_status(db: Database, session: dict) -> dict:
    transcript_path = session.get('transcript_path')
    if (
        session.get('status') == 'running'
        and _is_codex_transcript_path(transcript_path)
        and _terminal_codex_event(transcript_path or '')
    ):
        db.end_session(session['id'], status='stopped')
        session['status'] = 'stopped'
    return session


def _apply_session_lifecycle(db: Database, composite_id: str, event_type: str, session_id: str, event: dict | None = None) -> None:
    if event_type == 'SessionStart':
        db.dedup_source_app(session_id, composite_id)
        logger.info(f"[LIFECYCLE] {composite_id} -> stopped (session started)")
        db.stop_session(composite_id)
    elif event_type in ('UserPromptSubmit', 'PreToolUse'):
        logger.info(f"[LIFECYCLE] {composite_id} -> running (trigger: {event_type})")
        db.resume_session(composite_id, update_sort=(event_type == 'UserPromptSubmit'))
    elif event_type == 'Stop':
        logger.info(f"[LIFECYCLE] {composite_id} -> stopped")
        db.end_session(composite_id, status='stopped')
    elif event_type == 'SessionEnd':
        logger.info(f"[LIFECYCLE] {composite_id} -> ended")
        db.end_session(composite_id, status='ended')
    elif event_type == 'StatusUpdate':
        status = (event or {}).get('status', '')
        if status in ('waiting', 'running'):
            logger.info(f"[LIFECYCLE] {composite_id} -> {status} (StatusUpdate)")
            if status == 'waiting':
                db.wait_session(composite_id)
            else:
                db.resume_session(composite_id)
    else:
        logger.info(f"[LIFECYCLE] {composite_id} no status change (event: {event_type})")


def _dashboard_sessions(status: Optional[str] = None, limit: int = 50) -> list[dict]:
    """Return sessions visible to the current Dashboard project."""
    if db is None:
        return []
    return db.get_sessions(status, limit=limit, project_dir=PROJECT_DIR)


def _should_backfill_session_metadata(session: dict) -> bool:
    source_app = str(session.get('source_app') or '')
    return not source_app.endswith('-pending')


def find_transcript(session_id: str) -> Optional[str]:
    """Scan for a transcript matching this session_id.

    Checks in order:
    1. ~/.claude/projects/{session_id}.jsonl  (Claude Code transcripts)
    2. ~/.codex/sessions/**/rollout-*-{session_id}.jsonl  (Codex session rollouts)
    3. ~/.codex/history.jsonl (Codex CLI history, session_id as a field)
    """
    # 1. Claude Code transcript
    claude_base = Path.home() / '.claude' / 'projects'
    if claude_base.exists():
        target = f"{session_id}.jsonl"
        for p in claude_base.rglob(target):
            return str(p)

    # 2. Codex session rollout files
    codex_sessions = Path.home() / '.codex' / 'sessions'
    if codex_sessions.exists():
        for p in codex_sessions.rglob(f"rollout-*-{session_id}.jsonl"):
            return str(p)

    # 3. Codex history.jsonl (flat file, session_id as a field)
    history_path = Path.home() / '.codex' / 'history.jsonl'
    if history_path.exists():
        return str(history_path)

    return None


def _queued_match_key(text: str) -> str:
    """Whitespace-insensitive key for pairing a queued message with its real entry.

    The two sides reach us differently: `queue-operation` carries the raw typed
    line (`/cmd args`), while the real user entry is rebuilt from the
    `<command-name>`/`<command-args>` wrapper as `cmd\\nargs`. Comparing
    verbatim misses that pair and the dashboard shows the message twice.
    """
    return ' '.join(str(text or '').split())


def _match_queued(messages: list, text: str) -> dict | None:
    """Find the last unconsumed queued message with the same text."""
    key = _queued_match_key(text)
    for m in reversed(messages):
        if m.get('role') != 'user' or not m.get('_queued'):
            continue
        if _queued_match_key(m['text']) == key:
            return m
    return None


TOOL_OUTPUT_EDGE_CHARS = 500


def _truncate_tool_output(text: str, edge_chars: int = TOOL_OUTPUT_EDGE_CHARS) -> str:
    visible_chars = edge_chars * 2
    if len(text) <= visible_chars:
        return text
    omitted = text[edge_chars:-edge_chars]
    omitted_lines = len(omitted.splitlines()) or 1
    omitted_chars = len(omitted)
    return (
        f"{text[:edge_chars].rstrip()}\n\n"
        f"[omit {omitted_lines} lines, {omitted_chars} chars from middle; "
        f"dashboard preview keeps first/last {edge_chars} chars]\n\n"
        f"{text[-edge_chars:].lstrip()}"
    )


def _skip_js_string_or_comment(source: str, index: int) -> int:
    """Skip one JS string/comment, returning the first index after it."""
    if source.startswith('//', index):
        newline = source.find('\n', index + 2)
        return len(source) if newline < 0 else newline + 1
    if source.startswith('/*', index):
        end = source.find('*/', index + 2)
        return len(source) if end < 0 else end + 2
    quote = source[index]
    if quote not in ('"', "'", '`'):
        return index
    index += 1
    while index < len(source):
        if source[index] == '\\':
            index += 2
        elif source[index] == quote:
            return index + 1
        else:
            index += 1
    return len(source)


def _matching_js_delimiter(source: str, start: int, opening: str, closing: str) -> int:
    depth = 0
    index = start
    while index < len(source):
        if source[index] in ('"', "'", '`') or source.startswith('//', index) or source.startswith('/*', index):
            index = _skip_js_string_or_comment(source, index)
            continue
        if source[index] == opening:
            depth += 1
        elif source[index] == closing:
            depth -= 1
            if depth == 0:
                return index
        index += 1
    return -1


def _mask_js_strings_and_comments(source: str) -> str:
    """Preserve source offsets while hiding strings/comments from regex searches."""
    masked = list(source)
    index = 0
    while index < len(source):
        if source[index] in ('"', "'", '`') or source.startswith('//', index) or source.startswith('/*', index):
            end = _skip_js_string_or_comment(source, index)
            masked[index:end] = ' ' * (end - index)
            index = end
        else:
            index += 1
    return ''.join(masked)


def _decode_js_string(source: str, index: int = 0) -> tuple[str, int]:
    quote = source[index]
    end = _skip_js_string_or_comment(source, index)
    body = source[index + 1:max(index + 1, end - 1)]
    escapes = {'n': '\n', 'r': '\r', 't': '\t', 'b': '\b', 'f': '\f', 'v': '\v', '0': '\0'}
    result = []
    cursor = 0
    while cursor < len(body):
        if body[cursor] != '\\' or cursor + 1 >= len(body):
            result.append(body[cursor])
            cursor += 1
            continue
        escaped = body[cursor + 1]
        if escaped == 'x' and cursor + 3 < len(body):
            try:
                result.append(chr(int(body[cursor + 2:cursor + 4], 16)))
                cursor += 4
                continue
            except ValueError:
                pass
        if escaped == 'u' and cursor + 5 < len(body):
            try:
                result.append(chr(int(body[cursor + 2:cursor + 6], 16)))
                cursor += 6
                continue
            except ValueError:
                pass
        result.append(escapes.get(escaped, escaped))
        cursor += 2
    return ''.join(result), end


def _js_expression_value(expression: str) -> Any:
    expression = expression.strip()
    if not expression:
        return ''
    if expression[0] in ('"', "'", '`'):
        return _decode_js_string(expression)[0]
    constants = {'true': True, 'false': False, 'null': None, 'undefined': None}
    if expression in constants:
        return constants[expression]
    try:
        return int(expression)
    except ValueError:
        try:
            return float(expression)
        except ValueError:
            return expression


def _js_object_fields(source: str) -> dict[str, tuple[Any, str]]:
    """Parse primitive fields from JSON or common JavaScript object literals."""
    source = source.strip()
    if not source.startswith('{'):
        return {}
    end = _matching_js_delimiter(source, 0, '{', '}')
    if end < 0:
        return {}
    try:
        value = json.loads(source[:end + 1])
        if isinstance(value, dict):
            return {str(key): (item, json.dumps(item)) for key, item in value.items()}
    except (json.JSONDecodeError, TypeError):
        pass

    fields: dict[str, tuple[Any, str]] = {}
    index = 1
    while index < end:
        while index < end and (source[index].isspace() or source[index] == ','):
            index += 1
        if index >= end:
            break
        if source[index] in ('"', "'"):
            key, index = _decode_js_string(source, index)
        else:
            match = re.match(r'[A-Za-z_$][A-Za-z0-9_$]*', source[index:])
            if not match:
                break
            key = match.group(0)
            index += len(key)
        while index < end and source[index].isspace():
            index += 1
        if index >= end or source[index] != ':':
            break
        index += 1
        value_start = index
        stack = []
        while index < end:
            if source[index] in ('"', "'", '`') or source.startswith('//', index) or source.startswith('/*', index):
                index = _skip_js_string_or_comment(source, index)
                continue
            char = source[index]
            if char in '([{':
                stack.append(char)
            elif char in ')]}':
                if not stack:
                    break
                stack.pop()
            elif char == ',' and not stack:
                break
            index += 1
        expression = source[value_start:index].strip()
        fields[key] = (_js_expression_value(expression), expression)
    return fields


def _find_codex_js_tool_calls(source: str) -> list[tuple[str, str, int]]:
    """Find actual tools.* calls, excluding occurrences in strings/comments."""
    calls = []
    index = 0
    while index < len(source):
        if source[index] in ('"', "'", '`') or source.startswith('//', index) or source.startswith('/*', index):
            index = _skip_js_string_or_comment(source, index)
            continue
        if source.startswith('tools.', index):
            name_match = re.match(r'tools\.([A-Za-z_][A-Za-z0-9_]*)\s*\(', source[index:])
            if name_match:
                name = name_match.group(1)
                open_index = index + name_match.group(0).rfind('(')
                close_index = _matching_js_delimiter(source, open_index, '(', ')')
                if close_index >= 0:
                    calls.append((name, source[open_index + 1:close_index], index))
                    index = close_index + 1
                    continue
        index += 1
    return calls


def _js_array_items(expression: str) -> list[str]:
    """Split a JavaScript array literal into top-level item expressions."""
    expression = expression.strip()
    if not expression.startswith('['):
        return []
    end = _matching_js_delimiter(expression, 0, '[', ']')
    if end < 0:
        return []

    items = []
    item_start = 1
    stack = []
    index = 1
    while index < end:
        if expression[index] in ('"', "'", '`') or expression.startswith('//', index) or expression.startswith('/*', index):
            index = _skip_js_string_or_comment(expression, index)
            continue
        char = expression[index]
        if char in '([{':
            stack.append(char)
        elif char in ')]}':
            if stack:
                stack.pop()
        elif char == ',' and not stack:
            item = expression[item_start:index].strip()
            if item:
                items.append(item)
            item_start = index + 1
        index += 1

    item = expression[item_start:end].strip()
    if item:
        items.append(item)
    return items


def _resolve_js_array_items(
    source: str,
    expression: str,
    before: int,
    depth: int = 0,
) -> list[str]:
    """Resolve a nearby array literal or a variable assigned to one."""
    expression = expression.strip()
    if not expression or depth > 4:
        return []
    if expression.startswith('['):
        return _js_array_items(expression)
    if not re.fullmatch(r'[A-Za-z_$][A-Za-z0-9_$]*', expression):
        return []

    prefix = source[:before]
    masked = _mask_js_strings_and_comments(prefix)
    escaped_name = re.escape(expression)
    assign_pattern = re.compile(rf'(?:const|let|var)\s+{escaped_name}\s*=')
    assign_matches = list(assign_pattern.finditer(masked))
    if not assign_matches:
        return []

    value_start = assign_matches[-1].end()
    while value_start < len(prefix) and prefix[value_start].isspace():
        value_start += 1
    assigned_source = prefix[value_start:]
    if assigned_source.startswith('['):
        value_end = _matching_js_delimiter(assigned_source, 0, '[', ']')
        if value_end >= 0:
            return _js_array_items(assigned_source[:value_end + 1])
    assigned_name = re.match(r'[A-Za-z_$][A-Za-z0-9_$]*', assigned_source)
    if assigned_name:
        return _resolve_js_array_items(
            source,
            assigned_name.group(0),
            value_start,
            depth + 1,
        )
    return []


def _resolve_js_tool_argument_objects(
    source: str,
    expression: str,
    call_position: int,
) -> list[str]:
    """Expand object arguments read from a static array inside Array.map."""
    expression = expression.strip()
    if expression.startswith('{'):
        return [expression]

    property_access = re.fullmatch(
        r'([A-Za-z_$][A-Za-z0-9_$]*)\.([A-Za-z_$][A-Za-z0-9_$]*)',
        expression,
    )
    if not property_access:
        return [expression]
    callback_name, property_name = property_access.groups()

    callback = re.escape(callback_name)
    map_pattern = re.compile(
        rf'(?P<iterable>[A-Za-z_$][A-Za-z0-9_$]*)\.map\s*'
        rf'\(\s*(?:async\s+)?(?:{callback}|\(\s*{callback}\s*\))\s*=>'
    )
    masked = _mask_js_strings_and_comments(source)
    containing_maps = []
    for match in map_pattern.finditer(masked):
        open_index = masked.find('(', match.start(), match.end())
        close_index = _matching_js_delimiter(source, open_index, '(', ')')
        if open_index < call_position < close_index:
            containing_maps.append(match)
    if not containing_maps:
        return [expression]

    map_match = containing_maps[-1]
    items = _resolve_js_array_items(
        source,
        map_match.group('iterable'),
        map_match.start(),
    )
    arguments = []
    for item in items:
        field = _js_object_fields(item).get(property_name)
        if field:
            arguments.append(field[1])
    return arguments if arguments else [expression]


def _resolve_js_string_values(source: str, expression: str, before: int, depth: int = 0) -> list[str]:
    """Resolve strings, string arrays, and nearby const/for-of variables."""
    expression = expression.strip()
    if not expression or depth > 4:
        return []
    if expression[0] in ('"', "'", '`'):
        return [_decode_js_string(expression)[0]]
    if expression.startswith('['):
        end = _matching_js_delimiter(expression, 0, '[', ']')
        values = []
        index = 1
        while 0 <= index < end:
            if expression[index] in ('"', "'", '`'):
                value, index = _decode_js_string(expression, index)
                values.append(value)
            else:
                index += 1
        return values
    if not re.fullmatch(r'[A-Za-z_$][A-Za-z0-9_$]*', expression):
        return []

    prefix = source[:before]
    masked = _mask_js_strings_and_comments(prefix)
    escaped_name = re.escape(expression)
    for_pattern = re.compile(rf'for\s*\(\s*(?:const|let|var)\s+{escaped_name}\s+of\s+')
    for_matches = list(for_pattern.finditer(masked))
    if for_matches:
        value_start = for_matches[-1].end()
        if prefix[value_start:value_start + 1] == '[':
            value_end = _matching_js_delimiter(prefix, value_start, '[', ']')
            if value_end >= 0:
                return _resolve_js_string_values(source, prefix[value_start:value_end + 1], value_start, depth + 1)
        iterable = re.match(r'[A-Za-z_$][A-Za-z0-9_$]*', prefix[value_start:])
        if iterable:
            return _resolve_js_string_values(source, iterable.group(0), value_start, depth + 1)

    assign_pattern = re.compile(rf'(?:const|let|var)\s+{escaped_name}\s*=')
    assign_matches = list(assign_pattern.finditer(masked))
    if assign_matches:
        value_start = assign_matches[-1].end()
        while value_start < len(prefix) and prefix[value_start].isspace():
            value_start += 1
        original = prefix[value_start:]
        if original and original[0] in ('"', "'", '`'):
            value, _ = _decode_js_string(original)
            return [value]
        if original.startswith('['):
            value_end = _matching_js_delimiter(original, 0, '[', ']')
            if value_end >= 0:
                return _resolve_js_string_values(source, original[:value_end + 1], value_start, depth + 1)
        assigned = re.match(r'[A-Za-z_$][A-Za-z0-9_$]*', original)
        if assigned:
            return _resolve_js_string_values(source, assigned.group(0), value_start, depth + 1)
    return []


def _decode_codex_inner_tool(
    raw_input: str,
    inner_tool: str,
    args_source: str,
    call_position: int,
) -> list[tuple[str, dict]]:
    fields = _js_object_fields(args_source)

    if inner_tool == 'apply_patch':
        patch_values = _resolve_js_string_values(raw_input, args_source, call_position)
        operations = []
        for patch_value in patch_values:
            operations.extend(re.findall(
                r'^\*\*\*\s+(Add|Update|Delete)\s+File:\s*(.+?)\s*$',
                patch_value,
                re.MULTILINE,
            ))
        operation_names = {operation for operation, _ in operations}
        labels = {'Add': 'Added', 'Update': 'Edited', 'Delete': 'Deleted'}
        tool = labels[next(iter(operation_names))] if len(operation_names) == 1 else 'apply_patch'
        paths = [path.strip() for _, path in operations]
        return [(tool, {
            'path': paths[0] if paths else '',
            'paths': paths,
            'raw': raw_input,
        })]

    structured = {key: value for key, (value, _) in fields.items()}
    if inner_tool == 'exec_command':
        command_expression = fields.get('cmd', ('', ''))[1]
        workdir_expression = fields.get('workdir', ('', ''))[1]
        commands = _resolve_js_string_values(raw_input, command_expression, call_position)
        workdirs = _resolve_js_string_values(raw_input, workdir_expression, call_position)
        return [('Ran', {
            'command': commands[0] if commands else structured.get('cmd', ''),
            'workdir': workdirs[0] if workdirs else structured.get('workdir', ''),
            'raw': raw_input,
        })]
    if inner_tool == 'view_image':
        path_expression = fields.get('path', ('', ''))[1]
        paths = _resolve_js_string_values(raw_input, path_expression, call_position)
        if not paths and structured.get('path'):
            paths = [str(structured['path'])]
        return [
            ('Viewed Image', {'path': path, 'raw': raw_input})
            for path in (paths or [''])
        ]
    if structured:
        structured['raw'] = raw_input
        return [(inner_tool, structured)]
    return [(inner_tool, {'raw': raw_input})]


def decode_codex_custom_tool_inputs(payload: dict) -> list[tuple[str, dict]]:
    """Recover every inner operation represented by one Codex exec cell."""
    raw_input = str(payload.get('input') or '')
    calls = _find_codex_js_tool_calls(raw_input)
    if not calls:
        return [_decode_codex_direct_tool(
            str(payload.get('name') or ''),
            {'raw': raw_input},
        )]
    operations = []
    for inner_tool, args_source, call_position in calls:
        argument_objects = _resolve_js_tool_argument_objects(
            raw_input,
            args_source,
            call_position,
        )
        for argument_source in argument_objects:
            operations.extend(_decode_codex_inner_tool(
                raw_input,
                inner_tool,
                argument_source,
                call_position,
            ))
    return operations


def _decode_codex_direct_tool(tool_name: str, args: dict) -> tuple[str, dict]:
    if tool_name == 'exec_command':
        return 'Ran', {
            'command': args.get('cmd', args.get('command', '')),
            'workdir': args.get('workdir', ''),
            **args,
        }
    if tool_name == 'view_image':
        return 'Viewed Image', {'path': args.get('path', ''), **args}
    if tool_name == 'apply_patch':
        raw_patch = str(args.get('patch') or args.get('raw') or '')
        decoded = _decode_codex_inner_tool(raw_patch, 'apply_patch', json.dumps(raw_patch), 0)
        return decoded[0]
    return tool_name, args


def _codex_tool_output_text(output: Any) -> str:
    if isinstance(output, str):
        return output
    if isinstance(output, list):
        parts = []
        for block in output:
            if isinstance(block, dict) and block.get('type') in ('input_text', 'output_text'):
                parts.append(str(block.get('text') or ''))
            elif block is not None:
                parts.append(json.dumps(block) if isinstance(block, (dict, list)) else str(block))
        return ''.join(parts)
    if isinstance(output, (dict, list)):
        return json.dumps(output)
    return str(output or '')


def parse_transcript(path: str) -> list[dict]:
    """Parse a Claude Code JSONL transcript into a flat list of chat messages.

    Each entry is one of:
      {role: 'user',        text: str,  ts: int|None}
      {role: 'assistant',   text: str,  ts: int|None}
      {role: 'tool_use',    tool: str,  input: dict, id: str, ts: int|None}
      {role: 'tool_result', tool_use_id: str, content: str, is_error: bool, ts: int|None}
    """
    messages = []
    if not path:
        return messages
    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue

                if _should_hide_claude_entry_by_structure(entry):
                    continue

                msg = entry.get('message', {})
                entry_type = entry.get('type', '')
                ts = entry.get('timestamp')

                # Queue-operation: treat as user message immediately (unless system injection)
                if entry_type == 'queue-operation' and entry.get('operation') == 'enqueue':
                    text = (entry.get('content') or '').strip()
                    if text:
                        sys_tool = _is_system_injection(text)
                        if sys_tool:
                            inp = {'name': _parse_skill_name(text)} if sys_tool == 'Skill' else {'text': text}
                            messages.append({'role': 'tool_use', 'tool': sys_tool, 'input': inp, 'id': '', 'ts': ts})
                        else:
                            messages.append({'role': 'user', 'text': text, 'ts': ts, '_queued': True})
                    continue

                if not msg:
                    continue

                role = msg.get('role', '')
                content = msg.get('content', '')
                ts = entry.get('timestamp')

                if entry.get('isCompactSummary') is True:
                    summary = _extract_text(content).strip()
                    if summary:
                        messages.append({
                            'role': 'tool_use',
                            'tool': 'Compact',
                            'input': {'summary': summary},
                            'id': f"claude-compact:{entry.get('uuid', '')}",
                            'ts': ts,
                        })
                    continue

                if role == 'user':
                    if isinstance(content, list):
                        for block in content:
                            if not isinstance(block, dict):
                                continue
                            btype = block.get('type', '')
                            if btype == 'tool_result':
                                rc = block.get('content', '')
                                if isinstance(rc, list):
                                    rc = '\n'.join(
                                        b.get('text', '') for b in rc
                                        if isinstance(b, dict) and b.get('type') == 'text'
                                    )
                                stream_disconnect = _stream_disconnect_text(str(rc))
                                messages.append({
                                    'role': 'tool_result',
                                    'tool_use_id': block.get('tool_use_id', ''),
                                    'content': _truncate_tool_output(str(rc)),
                                    'is_error': bool(block.get('is_error', False)),
                                    'ts': ts,
                                })
                                if stream_disconnect:
                                    messages.append(_stream_disconnect_message(stream_disconnect, ts))
                            elif btype == 'text':
                                raw_text = block.get('text', '')
                                text = _normalize_claude_user_text(raw_text)
                                if text:
                                    if _is_claude_request_interrupted_message(raw_text):
                                        messages.append(_interrupted_message(ts))
                                        continue
                                    sys_tool = _is_system_injection(raw_text)
                                    if sys_tool:
                                        inp = {'name': _parse_skill_name(raw_text)} if sys_tool == 'Skill' else {'text': text}
                                        messages.append({'role': 'tool_use', 'tool': sys_tool, 'input': inp, 'id': '', 'ts': ts})
                                        continue
                                    # Skip if matching queue-operation already added this
                                    match = _match_queued(messages, text)
                                    if match:
                                        match.pop('_queued', None)  # consume
                                        continue
                                    messages.append({'role': 'user', 'text': text, 'ts': ts})
                    else:
                        raw_text = _extract_text(content)
                        text = _normalize_claude_user_text(raw_text)
                        if text:
                            if _is_claude_request_interrupted_message(raw_text):
                                messages.append(_interrupted_message(ts))
                                continue
                            sys_tool = _is_system_injection(raw_text)
                            if sys_tool:
                                inp = {'name': _parse_skill_name(raw_text)} if sys_tool == 'Skill' else {'text': text}
                                messages.append({'role': 'tool_use', 'tool': sys_tool, 'input': inp, 'id': '', 'ts': ts})
                            else:
                                match = _match_queued(messages, text)
                                if match:
                                    match.pop('_queued', None)
                                else:
                                    messages.append({'role': 'user', 'text': text, 'ts': ts})

                elif role == 'assistant':
                    if isinstance(content, list):
                        for block in content:
                            if not isinstance(block, dict):
                                continue
                            btype = block.get('type', '')
                            if btype == 'text':
                                text = block.get('text', '').strip()
                                if text:
                                    messages.append({'role': 'assistant', 'text': text, 'ts': ts})
                            elif btype == 'tool_use':
                                messages.append({
                                    'role': 'tool_use',
                                    'tool': block.get('name', ''),
                                    'input': block.get('input', {}),
                                    'id': block.get('id', ''),
                                    'ts': ts,
                                })
                    elif isinstance(content, str) and content.strip():
                        messages.append({'role': 'assistant', 'text': content.strip(), 'ts': ts})

    except Exception:
        pass

    return messages


def extract_plan_text(_transcript_path: str) -> Optional[str]:
    """Return the most recently modified plan file under ~/.claude/plans/.

    ExitPlanMode always fires right after the plan file is written,
    so the newest .md in that directory is the current plan.
    """
    plans_dir = Path.home() / '.claude' / 'plans'
    if not plans_dir.exists():
        return None
    try:
        files = sorted(plans_dir.glob('*.md'), key=lambda p: p.stat().st_mtime, reverse=True)
        if files:
            return files[0].read_text(encoding='utf-8').strip()
    except Exception:
        pass
    return None


def extract_model(path: str) -> Optional[str]:
    """Extract model name from latest assistant message in transcript."""
    if not path:
        return None
    model = None
    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                msg = entry.get('message', {})
                if msg.get('role') == 'assistant' and msg.get('model'):
                    model = msg['model']
    except Exception:
        pass
    return model


def parse_codex_transcript(path: str, session_id: str | None = None) -> list[dict]:
    """Parse a Codex JSONL transcript into dashboard message format.

    Handles two formats:
    - Rollout format: entries with 'type' and 'payload' fields
    - History format: entries with 'session_id', 'ts', 'text' fields (codex history.jsonl)
    """
    messages = []
    if not path:
        return messages

    is_history_format = path.endswith('/.codex/history.jsonl')

    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue

                # History format (codex history.jsonl): filter by session_id
                if is_history_format:
                    if entry.get('session_id') != session_id:
                        continue
                    text = entry.get('text', '').strip()
                    if not text:
                        continue
                    ts = entry.get('ts')
                    if isinstance(ts, (int, float)):
                        ts = int(ts * 1000) if ts > 1e12 else int(ts * 1000)
                    else:
                        ts = None
                    _append_codex_user_text_with_context(messages, text, ts)
                    continue

                # Rollout format
                entry_type = entry.get('type', '')
                payload = entry.get('payload', {})
                ts_raw = entry.get('timestamp')
                ts = None
                if ts_raw:
                    try:
                        if isinstance(ts_raw, (int, float)):
                            ts = int(ts_raw)
                        else:
                            dt = datetime.fromisoformat(str(ts_raw).replace('Z', '+00:00'))
                            ts = int(dt.timestamp() * 1000)
                    except Exception:
                        pass

                if entry_type == 'event_msg' and payload.get('type') == 'turn_aborted':
                    messages.append(_interrupted_message(ts))
                    continue

                if entry_type == 'event_msg' and payload.get('type') == 'error':
                    stream_disconnect = _stream_disconnect_text(payload.get('message'))
                    if stream_disconnect:
                        messages.append(_stream_disconnect_message(stream_disconnect, ts))
                    continue

                if entry_type != 'response_item':
                    continue

                ptype = payload.get('type', '')

                if ptype == 'message':
                    role = payload.get('role', '')
                    content = payload.get('content', [])
                    if isinstance(content, list):
                        text = '\n'.join(
                            b.get('text', '') for b in content
                            if isinstance(b, dict) and b.get('type') in ('input_text', 'output_text')
                        )
                    else:
                        text = str(content).strip()
                    text = text.strip()
                    if not text:
                        continue
                    if role == 'user':
                        if _is_codex_turn_aborted_message(text):
                            continue
                        _append_codex_user_text_with_context(messages, text, ts)
                    elif role == 'assistant':
                        messages.append({'role': 'assistant', 'text': text, 'ts': ts})

                elif ptype in ('function_call', 'custom_tool_call'):
                    if ptype == 'custom_tool_call':
                        decoded_tools = decode_codex_custom_tool_inputs(payload)
                    else:
                        args_str = payload.get('arguments', '{}')
                        try:
                            args = json.loads(args_str) if isinstance(args_str, str) else args_str
                        except json.JSONDecodeError:
                            args = {'raw': args_str}
                        decoded_tools = [_decode_codex_direct_tool(payload.get('name', ''), args)]
                    call_id = payload.get('call_id', '')
                    for index, (tool_name, args) in enumerate(decoded_tools):
                        messages.append({
                            'role': 'tool_use',
                            'tool': tool_name,
                            'input': args,
                            'id': call_id if index == 0 else f'{call_id}:inner:{index}',
                            'ts': ts,
                        })

                elif ptype in ('function_call_output', 'custom_tool_call_output'):
                    output = _codex_tool_output_text(payload.get('output', ''))
                    messages.append({
                        'role': 'tool_result',
                        'tool_use_id': payload.get('call_id', ''),
                        'content': _truncate_tool_output(output),
                        'is_error': False,
                        'ts': ts,
                    })

    except Exception:
        pass

    return _collapse_interrupted_before_user(messages)
db: Optional[Database] = None
ws_clients: set = set()


def _is_persistent_session(session: dict) -> bool:
    return str(session.get('name') or '').lower() in Database.FIXED_ROLES


def _tmux_pane_states() -> Optional[dict[str, bool]]:
    try:
        result = subprocess.run(
            ['tmux', 'list-panes', '-a', '-F',
             '#{pane_id} #{session_name}:#{window_index}.#{pane_index} #{pane_dead}'],
            capture_output=True,
            text=True,
            timeout=2,
        )
    except Exception as exc:
        logger.warning(f"[SWEEP] tmux list-panes failed: {exc}")
        return None
    if result.returncode != 0:
        logger.warning(f"[SWEEP] tmux list-panes returned {result.returncode}: {result.stderr.strip()}")
        return None
    states: dict[str, bool] = {}
    for line in result.stdout.splitlines():
        parts = line.strip().split(maxsplit=2)
        if not parts:
            continue
        pane_id = parts[0]      # absolute: %N
        pane_rel = parts[1] if len(parts) > 1 else None  # relative: session:window.pane
        pane_dead = len(parts) > 2 and parts[2] == '1'
        states[pane_id] = pane_dead
        if pane_rel:
            states[pane_rel] = pane_dead
    return states


def _sweep_dead_sessions_once() -> list[tuple[str, str]]:
    if db is None:
        return []
    sessions = db.get_sessions_for_sweep()
    if not sessions:
        return []
    pane_states = _tmux_pane_states()
    changed: list[tuple[str, str]] = []
    for session in sessions:
        session_id = session['id']
        if (
            session.get('status') == 'running'
            and _is_codex_transcript_path(session.get('transcript_path'))
            and _terminal_codex_event(session.get('transcript_path') or '')
        ):
            db.end_session(session_id, status='stopped')
            changed.append((session_id, 'stopped'))
            continue

        if pane_states is None:
            continue
        pane = session.get('tmux_pane')
        if not pane:
            continue
        pane_dead = pane not in pane_states or pane_states[pane]
        if not pane_dead:
            continue
        if _is_persistent_session(session):
            if session.get('status') != 'stopped':
                db.end_session(session_id, status='stopped')
                changed.append((session_id, 'stopped'))
        else:
            if session.get('status') != 'ended':
                db.end_session(session_id, status='ended')
                changed.append((session_id, 'ended'))
    return changed


def _run_session_sweeper(stop_event: threading.Event) -> None:
    while not stop_event.wait(SESSION_SWEEP_INTERVAL_SECONDS):
        changed = _sweep_dead_sessions_once()
        if not changed:
            continue
        logger.info(f"[SWEEP] updated sessions={changed}")
        broadcast_event({
            'type': 'event',
            'data': {
                'event_type': 'SessionSweep',
                'changes': [{'id': session_id, 'status': status} for session_id, status in changed],
            },
        })


class PendingPermission:
    """Holds a PermissionRequest waiting for browser decision."""
    def __init__(self, request_id: str, payload: dict):
        self.request_id = request_id
        self.payload = payload
        self.event = threading.Event()
        self.decision: Optional[dict] = None


pending_permissions: dict[str, PendingPermission] = {}
pending_permissions_lock = threading.Lock()


def _dashboard_tmux_session_name() -> str | None:
    """Resolve the tmux session that owns this Dashboard process."""
    if PROJECT_DIR:
        state_path = PROJECT_DIR / '.vibegame' / 'team' / 'state.json'
        try:
            state = json.loads(state_path.read_text(encoding='utf-8'))
            session_name = str(state.get('session_name') or '').strip()
            if session_name:
                return session_name
        except (OSError, json.JSONDecodeError):
            pass
    if os.environ.get('TMUX'):
        try:
            result = subprocess.run(
                ['tmux', 'display-message', '-p', '#S'],
                capture_output=True,
                text=True,
                timeout=2,
            )
            session_name = result.stdout.strip()
            if result.returncode == 0 and session_name:
                return session_name
        except Exception:
            pass
    return None


def _tmux_session_target(session_name: str) -> str:
    return session_name if session_name.startswith('=') else f'={session_name}'


def _shutdown_dashboard_process(server: ThreadingHTTPServer, session_name: str | None) -> None:
    time.sleep(0.2)
    if session_name:
        try:
            subprocess.run(['tmux', 'kill-session', '-t', _tmux_session_target(session_name)], timeout=5)
            return
        except Exception as exc:
            logger.warning(f"[SHUTDOWN] tmux kill-session failed: {exc}")
    server.shutdown()


class DashboardRequestHandler(BaseHTTPRequestHandler):
    """HTTP request handler for Dashboard API and static files."""

    def log_message(self, format, *args):
        """Suppress default logging."""
        pass

    def _handle_websocket_stream(self):
        """Upgrade this connection to a WebSocket and hand it to the broadcaster.

        Serving the stream on the HTTP port keeps it same-origin: the client
        derives the URL from the page it loaded, so it stays correct behind port
        mappings, tunnels and proxies. Ported from ccs, which does the same.
        """
        import base64
        import hashlib

        key = self.headers.get('Sec-WebSocket-Key', '')
        if self.headers.get('Upgrade', '').lower() != 'websocket' or not key:
            self.send_error(400, 'Expected WebSocket upgrade')
            return

        accept = base64.b64encode(
            hashlib.sha1((key + '258EAFA5-E914-47DA-95CA-C5AB0DC85B11').encode()).digest()
        ).decode()
        conn = self.connection
        try:
            conn.sendall(
                'HTTP/1.1 101 Switching Protocols\r\n'
                'Upgrade: websocket\r\n'
                'Connection: Upgrade\r\n'
                f'Sec-WebSocket-Accept: {accept}\r\n\r\n'.encode()
            )
            conn.sendall(create_ws_frame(json.dumps({
                'type': 'initial', 'data': _dashboard_sessions(limit=50),
            })))
        except OSError:
            return

        # Registered for broadcast_event; block this thread until the peer goes
        # away, since returning would let the HTTP server close the socket.
        ws_clients.add(conn)
        try:
            while conn.recv(4096):
                pass
        except OSError:
            pass
        finally:
            ws_clients.discard(conn)
            self.close_connection = True

    def _send_json(self, data: Any, status: int = 200):
        """Send JSON response."""
        body = json.dumps(data).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Content-Length', len(body))
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path: Path, content_type: str = 'text/html'):
        """Send file response."""
        if not path.exists():
            self.send_error(404)
            return
        body = path.read_bytes()
        self.send_response(200)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', len(body))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        """Handle CORS preflight."""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_GET(self):
        """Handle GET requests."""
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        # Static files
        if path == '/' or path == '/index.html':
            self._send_file(STATIC_PATH / 'index.html')
            return

        # Game preview, served from the dashboard's own origin. A separate
        # server on its own port cannot be reached from inside a container (the
        # published host port differs from the one the game binds), and locally
        # it capped concurrent previews at the size of a port range.
        if path == PLAY_PREFIX or path.startswith(PLAY_PREFIX + '/'):
            if not PROJECT_DIR:
                self.send_error(404, 'No project directory configured')
                return
            rel = path[len(PLAY_PREFIX):].lstrip('/')
            if rel in ('', 'index.html'):
                body = _play_index_html(PROJECT_DIR)
                if body is None:
                    self.send_error(404, 'Game has no index.html')
                    return
                self.send_response(200)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.send_header('Content-Length', str(len(body)))
                self.send_header('Cache-Control', 'no-store')
                self.end_headers()
                self.wfile.write(body)
                return
            target = _validate_play_path(PROJECT_DIR, rel)
            if target is None:
                self.send_error(404)
                return
            body = target.read_bytes()
            self.send_response(200)
            self.send_header('Content-Type', _guess_content_type(target))
            self.send_header('Content-Length', str(len(body)))
            # A preview must reflect the edit that just happened.
            self.send_header('Cache-Control', 'no-store, must-revalidate')
            self.end_headers()
            self.wfile.write(body)
            return

        # Editor JS/CSS modules
        if path.startswith('/editor/'):
            rel = path[8:]  # strip '/editor/'
            file_path = (STATIC_PATH / 'editor' / rel).resolve()
            if not str(file_path).startswith(str((STATIC_PATH / 'editor').resolve())):
                self.send_error(403)
                return
            if file_path.is_file():
                ct = _guess_content_type(file_path)
                body = file_path.read_bytes()
                self.send_response(200)
                self.send_header('Content-Type', ct)
                self.send_header('Content-Length', len(body))
                self.send_header('Cache-Control', 'no-store, must-revalidate')
                self.end_headers()
                self.wfile.write(body)
                return
            self.send_error(404)
            return

        # WebSocket on the HTTP port (same origin), so any port mapping, SSH
        # tunnel or reverse proxy that reaches the page also reaches the stream.
        if path == '/stream':
            self._handle_websocket_stream()
            return

        # API: Get sessions list
        if path == '/sessions':
            status = query.get('status', [None])[0]
            self._send_json([
                _apply_terminal_transcript_status(db, session)
                for session in _dashboard_sessions(status=status)
            ])
            return

        # API: List files in session working_dir matching prefix
        if path.startswith('/sessions/') and path.endswith('/files'):
            session_id = unquote(path[10:].rsplit('/', 1)[0])
            session = db.get_session(session_id)
            if not session:
                self._send_json({'error': 'Session not found'}, 404)
                return
            working_dir = session.get('working_dir')
            logger.debug(f"[files] session_id={session_id} working_dir={working_dir}")
            if not working_dir:
                self._send_json({'files': []})
                return
            prefix = query.get('prefix', [''])[0]
            base = Path(working_dir)
            if not base.exists():
                self._send_json({'files': []})
                return
            pattern = f'*{prefix}*' if prefix else '*'
            try:
                matches = sorted(base.glob(pattern), key=lambda p: (len(p.name), p.name))
                files = [str(p.relative_to(base)) for p in matches[:20]]
            except Exception:
                files = []
            self._send_json({'files': files})
            return

        # API: Get single session with parsed transcript
        if path.startswith('/sessions/'):
            session_id = unquote(path[10:])
            session = db.get_session(session_id)
            if not session:
                self._send_json({'error': 'Session not found'}, 404)
                return
            raw_id = session.get('session_id', '')
            transcript_path = session.get('transcript_path')
            allow_backfill = _should_backfill_session_metadata(session)
            # Fallback: scan ~/.claude/projects/ and ~/.codex/ if path not stored
            if not transcript_path and allow_backfill:
                transcript_path = find_transcript(raw_id)
                if transcript_path:
                    db.upsert_session(
                        session['source_app'], raw_id,
                        transcript_path=transcript_path,
                    )
                    session['transcript_path'] = transcript_path
            # Parse based on transcript path format, not source_app, since Claude Code
            # sessions can write to .codex/sessions/ rollouts and vice versa.
            is_codex_transcript = _is_codex_transcript_path(transcript_path)
            if is_codex_transcript:
                messages = parse_codex_transcript(transcript_path, session_id=raw_id)
            else:
                messages = parse_transcript(transcript_path)
            token_usage = extract_token_usage(transcript_path, is_codex_transcript)
            # Extract & cache model from transcript (latest assistant msg)
            model = extract_model(transcript_path)
            if model and allow_backfill:
                db.upsert_session(session['source_app'], raw_id, model=model)
                session['model'] = model
            session['messages'] = messages
            session['token_usage'] = token_usage
            session['event_count'] = len(messages)
            session['tool_count'] = sum(1 for m in messages if m['role'] == 'tool_use')
            # If last message is interrupted, session is stopped
            if messages and messages[-1].get('tool') == 'interrupted':
                db.end_session(session['id'], status='stopped')
                session['status'] = 'stopped'
            if is_codex_transcript:
                session = _apply_terminal_transcript_status(db, session)
            self._send_json(session)
            return

        # API: Server status
        if path == '/status':
            self._send_json({
                'status': 'running',
                'port': self.server.server_port,
                'project': PROJECT_DIR.name if PROJECT_DIR else None,
            })
            return

        # API: Project review context
        if path == '/api/review':
            self._send_json(build_review_payload(PROJECT_DIR))
            return

        # API: List pending permission requests (for browser reconnect)
        if path == '/permission':
            with pending_permissions_lock:
                pending_list = [
                    {
                        'request_id': p.request_id,
                        'tool_name': p.payload.get('tool_name', ''),
                        'tool_input': p.payload.get('tool_input', {}),
                        'permission_suggestions': p.payload.get('permission_suggestions', []),
                        'permission_mode': p.payload.get('permission_mode', ''),
                        'cwd': p.payload.get('cwd', ''),
                        'session_id': p.payload.get('session_id', ''),
                    }
                    for p in pending_permissions.values()
                ]
            self._send_json(pending_list)
            return

        # API: Preview supported local files under project/worktree roots
        if path == '/api/preview-file':
            raw_path = query.get('path', [''])[0]
            file_path = _resolve_preview_file_path(raw_path)
            if not file_path:
                self._send_json({'error': 'Preview file not found'}, 404)
                return
            body = file_path.read_bytes()
            self.send_response(200)
            self.send_header('Content-Type', _guess_content_type(file_path))
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store, must-revalidate')
            self.end_headers()
            self.wfile.write(body)
            return

        # API: Reveal file in Finder
        if path == '/api/reveal-file':
            raw_path = query.get('path', [''])[0]
            if not raw_path:
                self._send_json({'error': 'Missing path'}, 400)
                return
            candidate = Path(raw_path)
            if not candidate.is_absolute():
                self._send_json({'error': 'Path must be absolute'}, 400)
                return
            try:
                resolved = candidate.resolve()
            except Exception:
                self._send_json({'error': 'Invalid path'}, 400)
                return
            if not resolved.exists():
                self._send_json({'error': 'File not found'}, 404)
                return
            import subprocess as _sp
            # `open -R <path>` activates Finder, opens the containing folder,
            # and selects the target inside it. For a file this lands on the
            # parent dir with the file highlighted; for a dir, on the grandparent
            # with the dir highlighted. Previous code passed the parent to -R
            # which double-jumped (grandparent of file), losing the target.
            try:
                _sp.run(['open', '-R', str(resolved)], timeout=5)
                self._send_json({'success': True})
            except Exception as e:
                self._send_json({'error': str(e)}, 500)
            return

        # API: Node tree for reusable .node.json templates
        if path == '/api/nodes/tree':
            if not PROJECT_DIR:
                self._send_json({'error': 'No project directory configured'}, 400)
                return
            self._send_json(_build_node_tree(PROJECT_DIR))
            return

        # API: Resolve a manifest texture key for Objects preview
        if path == '/api/nodes/resolve-texture':
            if not PROJECT_DIR:
                self._send_json({'error': 'No project directory configured'}, 400)
                return
            key = query.get('key', [''])[0]
            resolved = _resolve_manifest_texture(key)
            if not resolved:
                self._send_json({'error': f'Texture key not found: {key}'}, 404)
                return
            self._send_json(resolved)
            return

        # API: Read a .node.json file under entities/ or nodes/
        if path.startswith('/api/nodes/'):
            if not PROJECT_DIR:
                self._send_json({'error': 'No project directory configured'}, 400)
                return
            rel = unquote(path[len('/api/nodes/'):])
            node_path = _validate_node_path(rel)
            if not node_path:
                self._send_json({'error': 'Invalid node path'}, 400)
                return
            if not node_path.is_file():
                self._send_json({'error': 'Node file not found'}, 404)
                return
            try:
                data = json.loads(node_path.read_text(encoding='utf-8'))
            except json.JSONDecodeError as e:
                self._send_json({'error': f'Invalid JSON: {e}'}, 400)
                return
            self._send_json({'path': str(node_path.relative_to(PROJECT_DIR)), 'data': data})
            return

        # API: Asset tree for game project
        if path == '/api/assets/tree':
            if not PROJECT_DIR:
                self._send_json({'error': 'No project directory configured'}, 400)
                return
            assets_dir = PROJECT_DIR / 'assets'
            if not assets_dir.is_dir():
                self._send_json({'name': 'assets', 'type': 'folder', 'children': []})
                return
            root_param = query.get('root', [''])[0] if query else ''
            if root_param:
                root_path = _validate_asset_path(root_param)
                if not root_path or not root_path.is_dir():
                    self._send_json({'error': f'Invalid directory: {root_param}'}, 400)
                    return
                self._send_json(_build_asset_tree(root_path, PROJECT_DIR))
            else:
                self._send_json(_build_asset_tree(assets_dir, PROJECT_DIR, skip_dirs={'artifacts'}))
            return

        # API: Raw manifest.json for a specific folder
        if path == '/api/assets/manifest-raw':
            if not PROJECT_DIR:
                self._send_json({'error': 'No project directory configured'}, 400)
                return
            folder = query.get('folder', [''])[0]
            if not folder or folder == 'assets':
                folder_path = PROJECT_DIR / 'assets'
            else:
                folder_path = _validate_asset_path(folder)
                if folder_path is None:
                    self._send_json({'error': 'Invalid folder'}, 400)
                    return
            if not folder_path.is_dir():
                self._send_json({'error': 'Not a directory'}, 400)
                return
            manifest = folder_path / 'manifest.json'
            if not manifest.exists():
                self._send_json({})
                return
            self._send_json(json.loads(manifest.read_text(encoding='utf-8')))
            return

        # API: Play status
        # Serve game project files at /assets/... (mirrors `python -m http.server` root serving).
        # Frontend assets panel uses img src="/${f.path}" where f.path is "assets/bat/flap.png".
        if path.startswith('/assets/'):
            if not PROJECT_DIR:
                self.send_error(404)
                return
            rel = path[8:]  # strip '/assets/' -> 'bat/flap.png'
            file_path = _validate_asset_path(f'assets/{rel}')
            if not file_path or not file_path.is_file():
                self.send_error(404)
                return
            ct = _guess_content_type(file_path)
            body = file_path.read_bytes()
            self.send_response(200)
            self.send_header('Content-Type', ct)
            self.send_header('Content-Length', len(body))
            self.send_header('Cache-Control', 'no-store, must-revalidate')
            self.end_headers()
            self.wfile.write(body)
            return

        self._send_json({'error': 'Not found'}, 404)

    def do_POST(self):
        """Handle POST requests."""
        parsed = urlparse(self.path)
        path = parsed.path

        # Receive event from hook
        if path == '/events':
            try:
                content_length = int(self.headers.get('Content-Length', 0))
                body = self.rfile.read(content_length)
                event = json.loads(body)

                source_app = event.get('source_app')
                session_id = event.get('session_id')
                event_type = event.get('hook_event_type') or event.get('event_type')

                if not all([source_app, session_id, event_type]):
                    self._send_json({'error': 'Missing required fields'}, 400)
                    return

                if not _event_belongs_to_project(event):
                    logger.info(
                        "[EVENT] rejected_foreign_project event=%s session=%s name=%s cwd=%s",
                        event_type,
                        f"{source_app}:{session_id}",
                        event.get('name'),
                        event.get('cwd'),
                    )
                    self._send_json({'error': 'Event does not belong to this Dashboard project'}, 409)
                    return

                # The pane heuristic guards against panes from another project. It
                # cannot judge worktree agents, whose pane sits in the project dir
                # while cwd is the sibling worktree, so a token-authenticated event
                # skips it rather than being dropped.
                event_pane = event.get('tmux_pane')
                if (event_pane and not _event_is_token_authenticated(event)
                        and not _tmux_pane_matches_working_dir(event_pane, event.get('cwd'))):
                    logger.warning(
                        "[EVENT] rejected_mismatched_pane event=%s session=%s pane=%s cwd=%s",
                        event_type, f"{source_app}:{session_id}", event_pane, event.get('cwd'),
                    )
                    self._send_json({'error': 'tmux pane does not belong to the event working directory'}, 409)
                    return

                composite_id = f"{source_app}:{session_id}"

                # StatusLine events only carry context-window usage. Do not touch
                # lifecycle / row creation — just update the context column on the
                # row that already exists (created by SessionStart hook).
                if event_type == 'StatusLine':
                    ctx_block = event.get('context') or {}
                    try:
                        pct = float(ctx_block.get('used_percentage'))
                    except (TypeError, ValueError):
                        pct = None
                    if pct is not None and db.update_context(composite_id, pct):
                        broadcast_event({
                            'type': 'context_update',
                            'data': {
                                'id': composite_id,
                                'context_pct': pct,
                                'context_updated_at': int(time.time() * 1000),
                            },
                        })
                    self._send_json({'ok': True})
                    return

                logger.info(f"[EVENT] {event_type} session={composite_id} name={event.get('name')}")

                # Merge a provisional pending session into the real session row.
                if not source_app.endswith('-pending'):
                    db.merge_pending(event.get('tmux_pane'), composite_id, event.get('name'))

                db.upsert_session(
                    source_app, session_id,
                    name=event.get('name'),
                    transcript_path=event.get('transcript_path'),
                    working_dir=event.get('cwd'),
                    tmux_pane=event.get('tmux_pane'),
                    model=event.get('model'),
                )

                _apply_session_lifecycle(db, composite_id, event_type, session_id, event)

                result = {
                    'session_id': composite_id,
                    'event_type': event_type,
                    'timestamp': event.get('timestamp', int(time.time() * 1000)),
                }
                broadcast_event({'type': 'event', 'data': result})
                self._send_json(result)

            except json.JSONDecodeError:
                self._send_json({'error': 'Invalid JSON'}, 400)
            except Exception as e:
                print(f"Error processing event: {e}", file=sys.stderr)
                self._send_json({'error': str(e)}, 500)
            return

        # Send prompt to session via tmux
        if path.startswith('/sessions/') and path.endswith('/send'):
            session_id = unquote(path[10:-5])
            session = db.get_session(session_id)
            if not session:
                self._send_json({'error': 'Session not found'}, 404)
                return
            pane = session.get('tmux_pane')
            if not pane:
                self._send_json({'error': 'No tmux pane for this session'}, 400)
                return
            if not _tmux_pane_matches_working_dir(pane, session.get('working_dir')):
                logger.warning(
                    "[SEND] rejected_mismatched_pane session=%s pane=%s cwd=%s",
                    session_id, pane, session.get('working_dir'),
                )
                self._send_json({'error': 'Session tmux pane no longer belongs to its working directory'}, 409)
                return
            try:
                content_length = int(self.headers.get('Content-Length', 0))
                body = self.rfile.read(content_length)
                data = json.loads(body)
                try:
                    prompt = _format_dashboard_prompt(
                        data.get('prompt', ''),
                        source_app=session.get('source_app'),
                    )
                except ValueError as exc:
                    self._send_json({'error': str(exc)}, 400)
                    return
                if not prompt:
                    self._send_json({'error': 'Empty prompt'}, 400)
                    return
                formatted_prompt = prompt
                # Interrupt if agent is running or in stop hook (waiting); skip if stopped/idle
                if session.get('status') in ('running', 'waiting'):
                    _run_tmux_send_command(
                        "interrupt",
                        ['tmux', 'send-keys', '-t', pane, 'C-c'],
                        timeout=5,
                    )
                    time.sleep(0.5)
                _tmux_send_prompt(pane, prompt)
                self._send_json({'success': True, 'formatted_prompt': formatted_prompt})
            except json.JSONDecodeError:
                self._send_json({'error': 'Invalid JSON'}, 400)
            except Exception as e:
                self._send_json({'error': str(e)}, 500)
            return

        if path.startswith('/sessions/') and path.endswith('/interrupt'):
            session_id = unquote(path[10:-10])
            session = db.get_session(session_id)
            if not session:
                self._send_json({'error': 'Session not found'}, 404)
                return
            pane = session.get('tmux_pane')
            if not pane:
                self._send_json({'error': 'No tmux pane for this session'}, 400)
                return
            if not _tmux_pane_matches_working_dir(pane, session.get('working_dir')):
                logger.warning(
                    "[SEND] rejected_mismatched_interrupt_pane session=%s pane=%s cwd=%s",
                    session_id, pane, session.get('working_dir'),
                )
                self._send_json({'error': 'Session tmux pane no longer belongs to its working directory'}, 409)
                return
            try:
                _run_tmux_send_command(
                    "interrupt",
                    ['tmux', 'send-keys', '-t', pane, 'C-c'],
                    timeout=5,
                )
                self._send_json({'success': True})
            except Exception as exc:
                self._send_json({'error': str(exc)}, 500)
            return

        # Permission request from hook (blocks until browser decides or 55s timeout)
        if path == '/permission':
            try:
                content_length = int(self.headers.get('Content-Length', 0))
                body = self.rfile.read(content_length)
                payload = json.loads(body)

                request_id = uuid.uuid4().hex[:12]
                pending = PendingPermission(request_id, payload)

                with pending_permissions_lock:
                    pending_permissions[request_id] = pending

                tool_name = payload.get('tool_name', '')
                logger.info(f"[PERM] tool={tool_name} mode={payload.get('permission_mode')!r} cwd={payload.get('cwd')!r}")
                plan_text = None
                if tool_name == 'ExitPlanMode':
                    plan_text = extract_plan_text(payload.get('transcript_path', ''))

                broadcast_event({
                    'type': 'permission_request',
                    'data': {
                        'request_id': request_id,
                        'tool_name': tool_name,
                        'tool_input': payload.get('tool_input', {}),
                        'permission_suggestions': payload.get('permission_suggestions', []),
                        'permission_mode': payload.get('permission_mode', ''),
                        'cwd': payload.get('cwd', ''),
                        'session_id': payload.get('session_id', ''),
                        'plan_text': plan_text,
                    }
                })

                decided = pending.event.wait(timeout=55)

                with pending_permissions_lock:
                    pending_permissions.pop(request_id, None)

                if decided and pending.decision:
                    self._send_json(pending.decision)
                else:
                    self._send_json({'timeout': True})

            except json.JSONDecodeError:
                self._send_json({'error': 'Invalid JSON'}, 400)
            except Exception as e:
                self._send_json({'error': str(e)}, 500)
            return

        # Browser submits permission decision
        if path.startswith('/permission/') and path.endswith('/decide'):
            request_id = path[len('/permission/'):-len('/decide')]
            try:
                content_length = int(self.headers.get('Content-Length', 0))
                body = self.rfile.read(content_length)
                decision_data = json.loads(body)

                with pending_permissions_lock:
                    pending = pending_permissions.get(request_id)

                if not pending:
                    self._send_json({'error': 'Not found or expired'}, 404)
                    return

                pending.decision = decision_data
                pending.event.set()

                broadcast_event({
                    'type': 'permission_resolved',
                    'data': {'request_id': request_id, 'behavior': decision_data.get('behavior', 'deny')}
                })
                self._send_json({'success': True})

            except json.JSONDecodeError:
                self._send_json({'error': 'Invalid JSON'}, 400)
            except Exception as e:
                self._send_json({'error': str(e)}, 500)
            return

        # API: Close Dashboard and its owning tmux session
        if path == '/api/dashboard/shutdown':
            session_name = _dashboard_tmux_session_name()
            logger.info(f"[SHUTDOWN] requested session={session_name or '-'}")
            threading.Thread(
                target=_shutdown_dashboard_process,
                args=(self.server, session_name),
                daemon=True,
            ).start()
            self._send_json({'ok': True, 'session': session_name})
            return

        # Upload pasted image: POST /upload-image with session_id + image file
        if path == '/upload-image':
            try:
                content_type = self.headers.get('Content-Type', '')
                if 'multipart/form-data' not in content_type:
                    self._send_json({'error': 'Expected multipart/form-data'}, 400)
                    return
                # Extract boundary from Content-Type header
                boundary = None
                for part in content_type.split(';'):
                    part = part.strip()
                    if part.startswith('boundary='):
                        boundary = part[9:].strip('"')
                if not boundary:
                    self._send_json({'error': 'Missing boundary'}, 400)
                    return

                content_length = int(self.headers.get('Content-Length', 0))
                body = self.rfile.read(content_length)

                # Parse multipart body to extract session_id and image data
                session_id = None
                image_data = None
                image_name = None
                # Split by boundary (--boundary)
                parts = body.split(('--' + boundary).encode())
                for i, part in enumerate(parts):
                    if not part or part in (b'', b'--', b'--\r\n'):
                        continue
                    # Each part has headers + blank line + content
                    header_end = part.find(b'\r\n\r\n')
                    if header_end == -1:
                        continue
                    headers_block = part[:header_end].decode()
                    content = part[header_end + 4:]
                    # Remove trailing \r\n from content
                    if content.endswith(b'\r\n'):
                        content = content[:-2]
                    # Extract disposition fields
                    disp = {}
                    for line in headers_block.split('\r\n'):
                        if ':' in line:
                            k, v = line.split(':', 1)
                            disp[k.strip().lower()] = v.strip()
                    content_disp = disp.get('content-disposition', '')
                    if 'name="session_id"' in content_disp:
                        session_id = content.decode().strip()
                    elif 'name="image"' in content_disp:
                        # Extract filename if present
                        fname_start = content_disp.find('filename="')
                        if fname_start != -1:
                            fname_end = content_disp.find('"', fname_start + 10)
                            image_name = content_disp[fname_start + 10:fname_end]
                        image_data = content

                if not session_id:
                    self._send_json({'error': 'Missing session_id'}, 400)
                    return
                if not image_data:
                    self._send_json({'error': 'Missing image data'}, 400)
                    return

                session = db.get_session(session_id)
                if not session:
                    self._send_json({'error': 'Session not found'}, 404)
                    return

                img_uuid = str(uuid.uuid4())
                # Preserve original extension from filename, default to .png
                ext = '.png'
                if image_name:
                    # Extract last extension (e.g., .png, .jpg, .gif)
                    if '.' in image_name:
                        ext = '.' + image_name.rsplit('.', 1)[1].lower()
                        if ext not in ('.png', '.jpg', '.jpeg', '.gif', '.webp'):
                            ext = '.png'
                img_path = Path('/tmp') / (img_uuid + ext)
                img_path.write_bytes(image_data)

                # Return the path that CC can resolve: @/abs/path
                self._send_json({'path': '@' + str(img_path)})
            except Exception as e:
                self._send_json({'error': str(e)}, 500)
            return

        self._send_json({'error': 'Not found'}, 404)

    def do_PUT(self):
        """Handle PUT requests."""
        parsed = urlparse(self.path)
        path = parsed.path

        # PUT .node.json for Objects editor
        if path.startswith('/api/nodes/'):
            if not PROJECT_DIR:
                self._send_json({'error': 'No project directory configured'}, 400)
                return
            rel = unquote(path[len('/api/nodes/'):])
            node_path = _validate_node_path(rel)
            if not node_path:
                self._send_json({'error': 'Invalid node path'}, 400)
                return
            if not node_path.is_file():
                self._send_json({'error': 'Node file not found'}, 404)
                return
            try:
                content_length = int(self.headers.get('Content-Length', 0))
                body = json.loads(self.rfile.read(content_length))
                if not isinstance(body, dict):
                    self._send_json({'error': 'Payload must be a JSON object'}, 400)
                    return
                data = body.get('data') if isinstance(body.get('data'), dict) else body
                if not isinstance(data, dict):
                    self._send_json({'error': 'Node data must be a JSON object'}, 400)
                    return
                old_data = json.loads(node_path.read_text(encoding='utf-8'))
                if not isinstance(old_data, dict):
                    self._send_json({'error': 'Existing node file is not a JSON object'}, 400)
                    return
                changes = body.get('changes')
                if not isinstance(changes, list):
                    changes = _diff_json(old_data, data)
                node_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
                rel_path = str(node_path.relative_to(PROJECT_DIR))
                _append_user_operation_log({
                    'ts': datetime.now().astimezone().isoformat(),
                    'source': 'dashboard.objects',
                    'action': body.get('action') or 'save',
                    'path': rel_path,
                    'changes': changes,
                })
                logger.info(f'[NODES] Updated: {node_path}')
                self._send_json({'ok': True, 'path': rel_path, 'changes': changes})
            except json.JSONDecodeError:
                self._send_json({'error': 'Invalid JSON'}, 400)
            except Exception as e:
                self._send_json({'error': str(e)}, 500)
            return

        # PUT manifest.json for a folder
        if path == '/api/assets/manifest-raw':
            if not PROJECT_DIR:
                self._send_json({'error': 'No project directory configured'}, 400)
                return
            try:
                content_length = int(self.headers.get('Content-Length', 0))
                body = json.loads(self.rfile.read(content_length))
                folder = body.get('folder', '')
                data = body.get('data', {})
                if not folder or folder == 'assets':
                    folder_path = PROJECT_DIR / 'assets'
                else:
                    folder_path = _validate_asset_path(folder)
                    if folder_path is None:
                        self._send_json({'error': 'Invalid folder'}, 400)
                        return
                if not folder_path.is_dir():
                    self._send_json({'error': 'Not a directory'}, 404)
                    return
                manifest = folder_path / 'manifest.json'
                manifest.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')
                logger.info(f'[MANIFEST] Updated: {manifest}')
                self._send_json({'ok': True})
            except json.JSONDecodeError:
                self._send_json({'error': 'Invalid JSON'}, 400)
            except Exception as e:
                self._send_json({'error': str(e)}, 500)
            return

        self._send_json({'error': 'Not found'}, 404)

    def do_DELETE(self):
        """Handle DELETE requests."""
        parsed = urlparse(self.path)
        path = parsed.path

        # Delete all sessions
        if path == '/sessions':
            count = db.delete_all_sessions()
            broadcast_event({'type': 'sessions_cleared', 'data': {'count': count}})
            self._send_json({'success': True, 'count': count})
            return

        # Delete a session
        if path.startswith('/sessions/'):
            session_id = unquote(path[10:])  # Remove /sessions/ and URL-decode
            if db.delete_session(session_id):
                broadcast_event({'type': 'session_deleted', 'data': {'id': session_id}})
                self._send_json({'success': True, 'id': session_id})
            else:
                self._send_json({'error': 'Session not found'}, 404)
            return

        self._send_json({'error': 'Not found'}, 404)


def create_ws_frame(message: str) -> bytes:
    """Create a WebSocket text frame."""
    import struct
    frame = bytearray()
    frame.append(0x81)  # FIN + text frame
    length = len(message)
    if length <= 125:
        frame.append(length)
    elif length <= 65535:
        frame.append(126)
        frame.extend(struct.pack('!H', length))
    else:
        frame.append(127)
        frame.extend(struct.pack('!Q', length))
    frame.extend(message.encode())
    return bytes(frame)


def broadcast_event(message: dict):
    """Push a message to every client attached to /stream."""
    frame = create_ws_frame(json.dumps(message))
    for client in list(ws_clients):
        try:
            client.send(frame)
        except (BrokenPipeError, ConnectionResetError, OSError):
            ws_clients.discard(client)


def run_server(
    host: str,
    port: int,
    db_path: Path | None = None,
    log_file: Path | None = None,
    reset_db: bool = False,
):
    """Run HTTP server."""
    global db
    runtime_db_path = db_path or _default_db_path(PROJECT_DIR)
    runtime_log_file = log_file or (Path.home() / '.vibegame' / 'dashboard.log')
    runtime_log_file.parent.mkdir(parents=True, exist_ok=True)
    db = Database(runtime_db_path)

    # Write our PID so _kill_dashboard can reliably kill this process (not just the shell)
    if PROJECT_DIR:
        pid_dir = PROJECT_DIR / ".vibegame" / "team" / "pids"
        pid_dir.mkdir(parents=True, exist_ok=True)
        (pid_dir / "server.pid").write_text(str(os.getpid()))

    if reset_db:
        cleared = db.delete_all_sessions()
        logger.info(f"[RESET] cleared {cleared} existing sessions from {runtime_db_path}")

    # File logging
    file_handler = logging.FileHandler(runtime_log_file)
    file_handler.setFormatter(logging.Formatter('%(asctime)s %(name)s %(message)s'))
    logging.getLogger().addHandler(file_handler)

    server = ThreadingHTTPServer((host, port), DashboardRequestHandler)
    server.server_host = host

    # No separate WebSocket listener: /stream is served on this same port,
    # which keeps the client's URL valid behind port mappings and proxies.

    sweep_stop_event = threading.Event()
    sweep_thread = threading.Thread(
        target=_run_session_sweeper,
        args=(sweep_stop_event,),
        daemon=True,
    )
    sweep_thread.start()

    print(f"Log file: {runtime_log_file}")

    print(f"VibeGame Dashboard running on http://{host}:{port}")
    print(f"Event stream on ws://{host}:{port}/stream")
    print(f"Database: {runtime_db_path}")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        sweep_stop_event.set()
        server.shutdown()
        db.close()


def main():
    parser = argparse.ArgumentParser(description='VibeGame Dashboard')
    subparsers = parser.add_subparsers(dest='command', help='Commands')

    server_parser = subparsers.add_parser('server', help='Start dashboard server')
    server_parser.add_argument('--port', type=int, required=True,
                               help='HTTP port to listen on')
    server_parser.add_argument('--host', default=DEFAULT_HOST,
                               help=f'Host (default: {DEFAULT_HOST})')
    server_parser.add_argument('--project', type=str, default=None,
                               help='Game project directory (enables asset/node browsing)')
    server_parser.add_argument('--db', type=str, default=None, help='SQLite database path')
    server_parser.add_argument('--log-file', type=str, default=None, help='Log file path')
    server_parser.add_argument('--dashboard-token', type=str, default=None, help='Project-scoped Dashboard event token')
    server_parser.add_argument('--reset-db', action='store_true', help='Clear existing session rows before serving')

    args = parser.parse_args()

    if args.command == 'server':
        global PROJECT_DIR, DASHBOARD_TOKEN
        if args.project:
            PROJECT_DIR = Path(args.project).resolve()
            logger.info(f"Project directory: {PROJECT_DIR}")
        DASHBOARD_TOKEN = args.dashboard_token
        logging.basicConfig(level=logging.INFO, format='%(asctime)s %(name)s %(message)s')
        run_server(
            args.host,
            args.port,
            db_path=Path(args.db).resolve() if args.db else None,
            log_file=Path(args.log_file).resolve() if args.log_file else None,
            reset_db=args.reset_db,
        )
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
