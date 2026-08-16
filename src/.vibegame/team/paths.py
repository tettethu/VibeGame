"""Path helpers for the local team runtime."""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path


def primary_repo_root(start: str | Path | None = None) -> Path | None:
    if start is None:
        cwd = os.getcwd()
    else:
        cwd = str(Path(start).resolve())
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
            capture_output=True,
            text=True,
            cwd=cwd,
        )
    except Exception:
        return None
    if result.returncode != 0:
        return None
    common_dir = Path(result.stdout.strip()).resolve()
    if common_dir.name == ".git":
        return common_dir.parent
    return None


def team_dir(explicit: str | None = None) -> Path:
    if explicit:
        return Path(explicit).resolve()
    env_dir = os.environ.get("VIBEGAME_TEAM_DIR")
    if env_dir:
        return Path(env_dir).resolve()
    primary_root = primary_repo_root()
    if primary_root is not None:
        return primary_root / ".vibegame" / "team"
    # Search from CWD upward (not __file__, which follows symlinks to src repo)
    found = find_team_dir(os.getcwd())
    if found:
        return found
    return Path(__file__).resolve().parent


def state_path(explicit: str | None = None) -> Path:
    return team_dir(explicit) / "state.json"


def messages_path(explicit: str | None = None) -> Path:
    return team_dir(explicit) / "messages.jsonl"


def lock_path(explicit: str | None = None) -> Path:
    return team_dir(explicit) / "lock"


def settings_path(explicit: str | None = None) -> Path:
    return team_dir(explicit).parent / "settings.json"


def ensure_team_dir(explicit: str | None = None) -> Path:
    path = team_dir(explicit)
    path.mkdir(parents=True, exist_ok=True)
    return path


def find_team_dir(start: str | Path | None) -> Path | None:
    if start is None:
        return None
    current = Path(start).resolve()
    search_roots = [current, *current.parents] if current.exists() else [current, *current.parents]
    for root in search_roots:
        candidate = root / ".vibegame" / "team"
        if candidate.is_dir():
            return candidate
    return None


def workspace_root(explicit: str | None = None) -> Path:
    return team_dir(explicit).parent.parent.resolve()


def workspace_slug(explicit: str | None = None) -> str:
    name = workspace_root(explicit).name.strip().lower() or "workspace"
    slug = re.sub(r"[^a-z0-9._-]+", "-", name).strip("-")
    return slug or "workspace"


def default_session_name(explicit: str | None = None) -> str:
    return f"vibegame-{workspace_slug(explicit)}"
