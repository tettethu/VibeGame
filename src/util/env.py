"""Unified .env management utility.

Priority for os.environ values: shell > game project .env > source code .env.

- Game project root: git main repo root containing CWD (worktree-safe)
- Source code root: git main repo root containing this file
- If CWD is not in a git repo, game project falls back to source code root

Config groups: keys sharing a common prefix (IMAGE_, VIDEO_, VLM_, QWEN_) are
treated as one semantic unit. If game .env defines any key in a group, the
entire group becomes game-owned and source's values for that group are dropped.
This prevents source's IMAGE_BASE_URL leaking through when the game project
switches to a different provider that uses its own default base URL.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path


CONFIG_GROUPS: tuple[str, ...] = ("IMAGE_", "VIDEO_", "VLM_", "QWEN_")


def _drop_owned_groups(source: dict[str, str], game: dict[str, str]) -> dict[str, str]:
    """Return source minus any group that game owns (touches any key of)."""
    owned = {p for p in CONFIG_GROUPS if any(k.startswith(p) for k in game)}
    if not owned:
        return source
    return {k: v for k, v in source.items() if not any(k.startswith(p) for p in owned)}


def _git_root(cwd: Path) -> Path | None:
    """Main repo root via --git-common-dir (returns main repo even from worktree)."""
    result = subprocess.run(
        ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
        capture_output=True,
        text=True,
        cwd=str(cwd),
    )
    if result.returncode != 0:
        return None
    return Path(result.stdout.strip()).parent


def get_source_code_root() -> Path | None:
    """Git root of the vibegame source tree (from this file's location)."""
    return _git_root(Path(__file__).resolve().parent)


def get_game_project_root() -> Path | None:
    """Git root containing current working directory."""
    return _git_root(Path.cwd())


def get_git_root() -> Path | None:
    """Preferred root: game project if in git, else source code root."""
    return get_game_project_root() or get_source_code_root()


def get_vibegame_root() -> Path | None:
    """Alias of get_git_root() for .vibegame/ placement."""
    return get_git_root()


def get_git_root_env_path() -> Path | None:
    """.env path under preferred root."""
    root = get_git_root()
    return root / ".env" if root else None


def parse_env_file(path: Path) -> dict[str, str]:
    """Parse a .env file into a dict (no os.environ mutation)."""
    if not path.exists():
        return {}

    values: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        key = key.strip()
        val = val.strip()
        if len(val) >= 2 and val[0] == val[-1] and val[0] in {"'", '"'}:
            val = val[1:-1]
        if key:
            values[key] = val
    return values


def load_unified_env(override: bool = False) -> bool:
    """Load .env into os.environ with priority shell > game project > source code.

    Args:
        override: if True, .env values override shell vars (default False).

    Returns:
        True if at least one .env file was found.
    """
    source_root = get_source_code_root()
    game_root = get_game_project_root()

    source_env = parse_env_file(source_root / ".env") if source_root else {}
    if game_root and game_root != source_root:
        game_env = parse_env_file(game_root / ".env")
    else:
        game_env = {}

    merged = {**_drop_owned_groups(source_env, game_env), **game_env}

    loaded = False
    for key, val in merged.items():
        if override or key not in os.environ:
            os.environ[key] = val
        loaded = True
    return loaded
