"""Minimal tmux backend for macOS and Linux."""

from __future__ import annotations

import functools
import os
import re
import shutil
import subprocess
import sys
import time
from collections.abc import Callable


class TmuxError(RuntimeError):
    """Raised when tmux command execution fails."""


@functools.lru_cache(maxsize=1)
def tmux_bin() -> str:
    """Absolute path to tmux, resolved once.

    Callers that build a shell snippet need the path rather than the bare name,
    and `vibegame start` runs before any session exists, so a missing tmux has
    to fail here with something readable instead of a bare ENOENT.
    """
    found = shutil.which("tmux")
    if not found:
        raise TmuxError("tmux not found on PATH. Install tmux (brew install tmux / apt install tmux).")
    return found


def _run(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(cmd, capture_output=True, text=True)
    if check and result.returncode != 0:
        raise TmuxError(result.stderr.strip() or f"Command failed: {' '.join(cmd)}")
    return result


def _exact_session_target(name: str) -> str:
    return name if name.startswith("=") else f"={name}"


def _exact_target(target: str) -> str:
    if not target or target.startswith(("=", "%", "@", "$")):
        return target
    if ":" in target:
        session, rest = target.split(":", 1)
        if not session:
            return target
        return f"{_exact_session_target(session)}:{rest}"
    return _exact_session_target(target)


def _exact_split_target(target: str) -> str:
    if not target or target.startswith(("%", "@", "$")):
        return target
    if target.startswith("="):
        return target if ":" in target else f"{target}:0"
    if ":" in target:
        return _exact_target(target)
    return f"{_exact_session_target(target)}:0"


def session_target(name: str) -> str:
    """tmux exact-match target for a session, so a name cannot match by prefix."""
    return _exact_session_target(name)


def window_target(session_name: str, window_index: int) -> str:
    return f"{_exact_session_target(session_name)}:{window_index}"


def session_exists(name: str) -> bool:
    return _run([tmux_bin(), "has-session", "-t", _exact_session_target(name)], check=False).returncode == 0


def current_session_name() -> str | None:
    if not os.environ.get("TMUX"):
        return None
    result = _run([tmux_bin(), "display-message", "-p", "#S"], check=False)
    if result.returncode != 0:
        return None
    name = result.stdout.strip()
    return name or None


def create_session(name: str) -> str:
    if session_exists(name):
        raise TmuxError(f"Session '{name}' already exists")
    result = _run([tmux_bin(), "new-session", "-d", "-s", name, "-P", "-F", "#{pane_id}"])
    return result.stdout.strip()


def new_window(session_name: str, *, name: str | None = None, index: int | None = None) -> str:
    target = f"{_exact_session_target(session_name)}:{index}" if index is not None else _exact_session_target(session_name)
    cmd = [tmux_bin(), "new-window", "-d", "-t", target, "-P", "-F", "#{pane_id}"]
    if name:
        cmd.extend(["-n", name])
    result = _run(cmd)
    return result.stdout.strip()


def window_exists(session_name: str, window_name: str) -> bool:
    result = _run(
        [tmux_bin(), "list-windows", "-t", _exact_session_target(session_name), "-F", "#{window_name}"],
        check=False,
    )
    if result.returncode != 0:
        return False
    return window_name in result.stdout.strip().splitlines()


def window_index_exists(session_name: str, index: int) -> bool:
    """Check if a window at the given index exists in the session."""
    result = _run(
        [tmux_bin(), "list-windows", "-t", _exact_session_target(session_name), "-F", "#{window_index}"],
        check=False,
    )
    if result.returncode != 0:
        return False
    return str(index) in result.stdout.strip().splitlines()


def window_pane_ids(target: str) -> list[str]:
    result = _run([tmux_bin(), "list-panes", "-t", _exact_target(target), "-F", "#{pane_id}"], check=False)
    if result.returncode != 0:
        return []
    return [p for p in result.stdout.strip().splitlines() if p]


def split_window(target: str, layout: str = "main-vertical") -> str:
    exact_target = _exact_split_target(target)
    result = _run([tmux_bin(), "split-window", "-t", exact_target, "-h", "-P", "-F", "#{pane_id}"])
    _run([tmux_bin(), "select-layout", "-t", exact_target, layout], check=False)
    return result.stdout.strip()


def send_keys(target: str, text: str, enter: bool = True, double_enter: bool = False) -> None:
    if text:
        _run([tmux_bin(), "send-keys", "-t", target, "-l", text])
    if enter:
        time.sleep(0.3)
        _run([tmux_bin(), "send-keys", "-t", target, "Enter"])
        if double_enter:
            time.sleep(0.3)
            _run([tmux_bin(), "send-keys", "-t", target, "Enter"])


PROMPT_SUBMIT_DELAYS = (0.05, 0.35)
# Confirmed submission retries Enter until the CLI's UserPromptSubmit hook acknowledges it.
CONFIRMED_SUBMIT_DELAYS = (0.05, 0.35, 0.6, 0.6)
ACK_POLL_INTERVAL = 0.15
ACK_POLL_TIMEOUT = 0.5
ACK_WINDOW = 4.0


def _wait_for_ack(acknowledged: Callable[[], bool], timeout: float) -> bool:
    deadline = time.monotonic() + timeout
    while True:
        if acknowledged():
            return True
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return False
        time.sleep(min(ACK_POLL_INTERVAL, remaining))


def paste_prompt(target: str, text: str, acknowledged: Callable[[], bool] | None = None) -> None:
    """Deliver one prompt to a CLI pane as a single message.

    `send-keys -l` replays a newline as Enter, so a multi-line prompt submits
    line by line and the agent receives fragments. A private buffer pasted with
    `-p` (bracketed paste) arrives as one block; the trailing Enter submits it
    once. Same mechanism the dashboard uses to send prompts.

    With `acknowledged`, the CLI is idle and must confirm the submission through its
    UserPromptSubmit hook; Enter is retried and TmuxError is raised if it never confirms.
    Without it the CLI may be mid-turn and queue the prompt, so submission is blind.
    """
    if not text:
        return
    body = text[:-1] if text.endswith("\n") else text
    # A trailing @mention opens the file picker, which would take the Enter.
    prepared = body + (" \n" if re.search(r"(?:^|\s)@\S*$", body) else "\n")
    buffer_name = f"vibegame-prompt-{os.urandom(8).hex()}"
    try:
        result = subprocess.run(
            [tmux_bin(), "load-buffer", "-b", buffer_name, "-"],
            input=prepared, capture_output=True, text=True,
        )
        if result.returncode != 0:
            raise TmuxError(result.stderr.strip() or "tmux load-buffer failed")
        started = time.monotonic()
        _run([tmux_bin(), "paste-buffer", "-p", "-r", "-b", buffer_name, "-t", target])
        for attempt, delay in enumerate(CONFIRMED_SUBMIT_DELAYS if acknowledged else PROMPT_SUBMIT_DELAYS, 1):
            time.sleep(delay)
            _run([tmux_bin(), "send-keys", "-t", target, "Enter"])
            if acknowledged and _wait_for_ack(acknowledged, ACK_POLL_TIMEOUT):
                print(f"Prompt submitted to {target}: confirmed after Enter #{attempt}", file=sys.stderr)
                return
        if acknowledged and not _wait_for_ack(acknowledged, ACK_WINDOW - (time.monotonic() - started)):
            raise TmuxError(f"Prompt pasted into {target} but not confirmed by its UserPromptSubmit hook within {ACK_WINDOW:g}s.")
    finally:
        _run([tmux_bin(), "delete-buffer", "-b", buffer_name], check=False)


def capture_pane(target: str, lines: int = 80) -> str:
    return _run([tmux_bin(), "capture-pane", "-t", target, "-p", "-S", f"-{lines}"]).stdout


def set_remain_on_exit(target: str, mode: str = "failed") -> None:
    _run([tmux_bin(), "set-option", "-p", "-t", target, "remain-on-exit", mode], check=False)


def pane_dead(pane_id: str | None) -> bool:
    if not pane_id:
        return False
    result = _run([tmux_bin(), "display-message", "-p", "-t", pane_id, "#{pane_dead}"], check=False)
    if result.returncode != 0:
        return False
    return result.stdout.strip() == "1"


def kill_pane(pane_id: str) -> None:
    _run([tmux_bin(), "kill-pane", "-t", pane_id], check=False)


def graceful_kill_pane(pane_id: str, interrupts: int = 2, wait: float = 2.0) -> None:
    """Send Ctrl+C to let the process exit, then kill the pane."""
    for _ in range(interrupts):
        _run([tmux_bin(), "send-keys", "-t", pane_id, "C-c"], check=False)
        time.sleep(0.3)
    time.sleep(wait)
    _run([tmux_bin(), "kill-pane", "-t", pane_id], check=False)


def kill_session(name: str) -> None:
    if session_exists(name):
        _run([tmux_bin(), "kill-session", "-t", _exact_session_target(name)], check=False)


def pane_exists(pane_id: str | None) -> bool:
    if not pane_id:
        return False
    result = _run([tmux_bin(), "list-panes", "-a", "-F", "#{pane_id}"], check=False)
    if result.returncode != 0:
        return False
    return pane_id in result.stdout.strip().splitlines()


def resolve_pane_id(pane_ref: str) -> str:
    """Canonical %id for a pane reference. Raises if tmux cannot resolve it."""
    result = _run([tmux_bin(), "display-message", "-p", "-t", pane_ref, "#{pane_id}"], check=False)
    resolved = result.stdout.strip()
    if result.returncode != 0 or not resolved:
        raise TmuxError(f"Unable to resolve tmux pane id for {pane_ref}")
    return resolved


def pane_in_session(session_name: str | None, pane_id: str | None) -> bool:
    """Whether a pane still belongs to a session. False for missing arguments."""
    if not session_name or not pane_id:
        return False
    result = _run(
        [tmux_bin(), "list-panes", "-s", "-t", _exact_session_target(session_name), "-F", "#{pane_id}"],
        check=False,
    )
    if result.returncode != 0:
        return False
    return pane_id in result.stdout.strip().splitlines()
