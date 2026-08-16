"""
Unified debug logger for vibegame agent framework.

Reads .vibegame/global.json "debug" field to toggle logging.
All hook log output goes to the primary git root's logs/hook.log.
Non-debug mode: all methods are no-op with zero overhead.

Usage:
    from team.logger import get_logger
    log = get_logger()
    log.hook("session-start.py", {"session_id": "abc"}, {"result": "ok"})
    log.command("lead", "agent --name architect-boss", "started")
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import traceback
from io import StringIO
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


def _find_repo_root() -> Path | None:
    """Walk up from cwd to find directory containing .vibegame/."""
    current = Path.cwd()
    while current != current.parent:
        if (current / ".vibegame").is_dir():
            return current
        current = current.parent
    return None


def _find_git_root() -> Path | None:
    """Return the primary git root, resolving linked worktrees to the main checkout."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
            capture_output=True,
            text=True,
            cwd=os.getcwd(),
        )
    except Exception:
        return None
    if result.returncode != 0:
        return None
    common_dir = Path(result.stdout.strip()).resolve()
    if common_dir.name == ".git":
        return common_dir.parent
    return common_dir.parent if common_dir.exists() else None


def hook_log_path() -> Path:
    """Central hook log location, independent of current cwd/worktree."""
    root = _find_git_root() or _find_repo_root() or Path.cwd()
    return root / "logs" / "hook.log"


def _is_debug_enabled(repo_root: Path) -> bool:
    """Read debug flag from global.json."""
    global_json = repo_root / ".vibegame" / "global.json"
    if not global_json.exists():
        return False
    try:
        data = json.loads(global_json.read_text(encoding="utf-8"))
        return data.get("debug", False) is True
    except (json.JSONDecodeError, OSError):
        return False


class _NullLogger:
    """No-op logger for non-debug mode."""

    def hook(self, script: str, input_data: dict | None, output_data: dict | None) -> None:
        pass

    def command(self, source: str, cmd_args: str, result: str = "") -> None:
        pass


class Logger:
    """Debug logger that writes to logs/hook.log."""

    def __init__(self, log_path: Path):
        self._log_path = log_path
        log_path.parent.mkdir(parents=True, exist_ok=True)

    def _write(self, prefix: str, message: str) -> None:
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
        line = f"[{ts}] {prefix} {message}\n"
        try:
            with open(self._log_path, "a", encoding="utf-8") as f:
                f.write(line)
        except OSError:
            pass

    @staticmethod
    def _safe_json(data: Any) -> str:
        try:
            return json.dumps(data, ensure_ascii=False, default=str)
        except (TypeError, ValueError):
            return str(data)

    def hook(self, script: str, input_data: dict | None, output_data: dict | None) -> None:
        in_str = self._safe_json(input_data) if input_data else "{}"
        out_str = self._safe_json(output_data) if output_data else "{}"
        self._write(f"[HOOK] {script}", f"| IN: {in_str} | OUT: {out_str}")

    def command(self, source: str, cmd_args: str, result: str = "") -> None:
        tag = "[LEAD]" if source in ("lead.py", "lead") else "[MATE]"
        msg = f"{cmd_args}"
        if result:
            msg += f" | {result}"
        self._write(f"{tag} {source}", msg)


_instance: Logger | _NullLogger | None = None


def get_logger() -> Logger | _NullLogger:
    """Get singleton logger instance. Reads global.json debug config on first call."""
    global _instance
    if _instance is not None:
        return _instance

    repo_root = _find_repo_root()
    if repo_root is None or not _is_debug_enabled(repo_root):
        _instance = _NullLogger()
    else:
        _instance = Logger(hook_log_path())

    return _instance


def _parse_hook_input(raw: str) -> dict | None:
    try:
        data = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def log_hook_error(
    script: str,
    exc: BaseException,
    *,
    input_raw: str = "",
    input_data: dict | None = None,
    context: str = "unhandled_exception",
) -> None:
    """Always append hook errors to logs/hook.log, independent of debug mode."""
    payload = {
        "kind": "hook_error",
        "script": script,
        "context": context,
        "error_type": type(exc).__name__,
        "error": str(exc),
        "input_raw": input_raw,
        "input": input_data,
        "traceback": traceback.format_exc(),
    }
    path = hook_log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    line = f"[{datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S')}] [HOOK_ERROR] {json.dumps(payload, ensure_ascii=False, default=str)}\n"
    try:
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(line)
    except OSError:
        pass


def run_hook(script: str, main_func: Callable[[], int | None]) -> None:
    """Run a hook main function and log failures once to logs/hook.log."""
    raw = sys.stdin.read()
    input_data = _parse_hook_input(raw)
    sys.stdin = StringIO(raw)
    try:
        result = main_func()
    except SystemExit as exc:
        if exc.code not in (0, None):
            log_hook_error(script, exc, input_raw=raw, input_data=input_data, context="system_exit")
        raise
    except Exception as exc:
        log_hook_error(script, exc, input_raw=raw, input_data=input_data)
        raise SystemExit(1) from exc
    if isinstance(result, int):
        if result != 0:
            exc = SystemExit(result)
            log_hook_error(script, exc, input_raw=raw, input_data=input_data, context="return_code")
        raise SystemExit(result)
