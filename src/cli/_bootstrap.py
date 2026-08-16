"""Locate a vibegame project's .vibegame/ directory and add it to sys.path.

Used by the lead/mate CLI commands so that `from team.X import Y` resolves to
the user project's shipped team package. Order of resolution:

  1. VIBEGAME_TEAM_DIR env var (set by lead.py when launching mate processes)
  2. git rev-parse --show-toplevel from cwd
  3. Walk up from cwd looking for .vibegame/team/

Raises SystemExit with a clear message if no project is found.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def _looks_like_team_dir(team_dir: Path) -> bool:
    """A real (post-`vibegame init`) team dir has the source modules, not just
    runtime artifacts like state.json or lock. Probe a known-stable module."""
    return (team_dir / "messages.py").is_file()


def find_project_vibegame_dir() -> Path:
    env = os.environ.get("VIBEGAME_TEAM_DIR")
    if env:
        candidate = Path(env).parent
        if _looks_like_team_dir(candidate / "team"):
            return candidate
    try:
        r = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=False,
        )
        if r.returncode == 0:
            candidate = Path(r.stdout.strip()) / ".vibegame"
            if _looks_like_team_dir(candidate / "team"):
                return candidate
    except Exception:
        pass
    current = Path.cwd()
    while current != current.parent:
        candidate = current / ".vibegame"
        if _looks_like_team_dir(candidate / "team"):
            return candidate
        current = current.parent
    raise SystemExit(
        "Not in a vibegame project: no .vibegame/team/ with the team package "
        "found via VIBEGAME_TEAM_DIR env, git root, or cwd ancestors. "
        "Run `vibegame init` in a project first."
    )


def ensure_team_on_path() -> Path:
    """Add the project's .vibegame/ to sys.path. Returns the .vibegame/ Path."""
    vibegame_dir = find_project_vibegame_dir()
    if str(vibegame_dir) not in sys.path:
        sys.path.insert(0, str(vibegame_dir))
    return vibegame_dir
