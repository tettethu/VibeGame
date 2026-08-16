"""State storage for the local team runtime."""

from __future__ import annotations

import json
import os
import tempfile
import time
from pathlib import Path
from typing import Callable, TypeVar

from .locks import file_lock
from .paths import ensure_team_dir, lock_path, state_path

T = TypeVar("T")
STATE_ERROR_PREFIX = "Team state error:"


def _now() -> float:
    return time.time()


def _state_error(path: Path, detail: str) -> RuntimeError:
    return RuntimeError(f"{STATE_ERROR_PREFIX} {path}: {detail}")


def is_state_error(exc: BaseException) -> bool:
    return isinstance(exc, RuntimeError) and str(exc).startswith(STATE_ERROR_PREFIX)


def _default_state(base_dir: Path) -> dict:
    return {
        "version": 1,
        "root": str(base_dir.parent.parent.resolve()),
        "team_dir": str(base_dir.resolve()),
        "session_name": None,
        "lead": {
            "started_at": None,
        },
        "agents": {},
    }


def _load_state_unlocked(base_dir: Path) -> dict:
    path = state_path(str(base_dir))
    if not path.exists():
        return _default_state(base_dir)
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise _state_error(path, f"cannot read file: {exc}") from exc
    raw = raw.strip()
    if not raw:
        raise _state_error(path, "file is empty")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        detail = f"invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}"
        raise _state_error(path, detail) from exc
    if not isinstance(data, dict):
        raise _state_error(path, f"expected top-level object, got {type(data).__name__}")
    data.setdefault("version", 1)
    data.setdefault("root", str(base_dir.parent.parent.resolve()))
    data.setdefault("team_dir", str(base_dir.resolve()))
    data.setdefault("session_name", None)
    data.setdefault("lead", {"started_at": None, "last_teammate_message_at": None})
    data.setdefault("agents", {})
    if not isinstance(data["lead"], dict):
        raise _state_error(path, f"expected 'lead' to be an object, got {type(data['lead']).__name__}")
    if not isinstance(data["agents"], dict):
        raise _state_error(path, f"expected 'agents' to be an object, got {type(data['agents']).__name__}")
    return data


def _save_state_unlocked(base_dir: Path, data: dict) -> dict:
    path = state_path(str(base_dir))
    payload = json.dumps(data, indent=2)
    fd, tmp_path = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, path)
    except OSError as exc:
        try:
            Path(tmp_path).unlink(missing_ok=True)
        except OSError:
            pass
        raise _state_error(path, f"cannot write file: {exc}") from exc
    return data


def load_state(explicit_team_dir: str | None = None) -> dict:
    base_dir = ensure_team_dir(explicit_team_dir)
    with file_lock(lock_path(str(base_dir))):
        return _load_state_unlocked(base_dir)


def save_state(data: dict, explicit_team_dir: str | None = None) -> dict:
    base_dir = ensure_team_dir(explicit_team_dir)
    with file_lock(lock_path(str(base_dir))):
        return _save_state_unlocked(base_dir, data)


def mutate_state(
    mutator: Callable[[dict], T],
    explicit_team_dir: str | None = None,
) -> tuple[dict, T]:
    base_dir = ensure_team_dir(explicit_team_dir)
    with file_lock(lock_path(str(base_dir))):
        state = _load_state_unlocked(base_dir)
        result = mutator(state)
        _save_state_unlocked(base_dir, state)
        return state, result


def init_state(session_name: str | None, explicit_team_dir: str | None = None) -> dict:
    def _mutate(state: dict) -> None:
        if session_name:
            state["session_name"] = session_name
        state["lead"]["started_at"] = _now()
    return mutate_state(_mutate, explicit_team_dir)[0]


def register_agent(
    name: str,
    workdir: str,
    command: str,
    pane_id: str | None,
    explicit_team_dir: str | None = None,
    *,
    cli: str | None = None,
    model: str | None = None,
    agent_type: str | None = None,
) -> dict:
    def _mutate(state: dict) -> None:
        agents = state.setdefault("agents", {})
        if name in agents:
            raise ValueError(f"Agent '{name}' already exists in team state.")
        agents[name] = {
            "status": "idle",
            "workdir": workdir,
            "command": command,
            "cli": cli,
            "model": model,
            "agent_type": agent_type,
            "pane_id": pane_id,
            "session_id": None,
            "transcript_path": None,
            "last_transcript_at": None,
            "created_at": _now(),
            "last_report": None,
            "last_sent": None,
        }
    return mutate_state(_mutate, explicit_team_dir)[0]


def update_lead(explicit_team_dir: str | None = None, **fields) -> dict:
    """Update fields on the lead/orchestrator entry in state."""
    def _mutate(state: dict) -> None:
        lead = state.setdefault("lead", {})
        lead.update(fields)
    return mutate_state(_mutate, explicit_team_dir)[0]


def update_agent(
    name: str,
    explicit_team_dir: str | None = None,
    **fields,
) -> dict:
    def _mutate(state: dict) -> None:
        agent = state.setdefault("agents", {}).get(name)
        if agent is None:
            raise KeyError(name)
        agent.update(fields)
    return mutate_state(_mutate, explicit_team_dir)[0]


def remove_agent(name: str, explicit_team_dir: str | None = None) -> dict:
    def _mutate(state: dict) -> None:
        state.setdefault("agents", {}).pop(name, None)
    return mutate_state(_mutate, explicit_team_dir)[0]


def set_dashboard_port(port: int, explicit_team_dir: str | None = None, token: str | None = None) -> dict:
    """Write the dashboard dashboard endpoint to state.json."""
    def _mutate(state: dict) -> None:
        state["dashboard_port"] = port
        if token is not None:
            state["dashboard_token"] = token
    return mutate_state(_mutate, explicit_team_dir)[0]


def touch_teammate_message(explicit_team_dir: str | None = None) -> dict:
    def _mutate(state: dict) -> None:
        state.setdefault("lead", {})["last_teammate_message_at"] = _now()
    return mutate_state(_mutate, explicit_team_dir)[0]


def require_agent(name: str, explicit_team_dir: str | None = None) -> dict:
    data = load_state(explicit_team_dir)
    agent = data.get("agents", {}).get(name)
    if agent is None:
        raise KeyError(name)
    return agent
