"""Generate or refresh a pure release branch for direct deployment.

Usage:
    vibegame release
    vibegame release --dry-run
    vibegame release --branch production

Rebuilds the release branch from an allowlist of runtime roots plus
manifest-selected assets. Fails fast on artifact-backed entries or
missing files.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

import typer

# Default runtime roots: standard vibegame project files
DEFAULT_RUNTIME_ROOTS: list[str] = [
    "index.html",
    "project.json",
    "config/",
    "scenes/",
    "scripts/",
    "engine/",
]

# Release-specific .gitignore
RELEASE_GITIGNORE = """\
node_modules/
logs/
server/saves/
.env
__pycache__/
*.png.tmp
"""


def _git(*args: str, cwd: Path | None = None, check: bool = True) -> str:
    r = subprocess.run(
        ["git", *args], check=check, capture_output=True, text=True, cwd=cwd
    )
    return r.stdout.strip()


def _resolve_repo_root(path: Path) -> Path:
    return Path(_git("rev-parse", "--show-toplevel", cwd=path))


def _get_current_branch(repo: Path) -> str:
    return _git("branch", "--show-current", cwd=repo)


def _get_head_sha(repo: Path) -> str:
    return _git("rev-parse", "HEAD", cwd=repo)


def _collect_manifest_assets(
    manifest: dict,
    asset_root: Path,
    manifest_files: list[Path],
) -> tuple[list[Path], list[tuple[str, str]], list[tuple[str, str]]]:
    """Return (deployable_paths, blocked_artifact_entries, missing_files)."""
    files = list(manifest_files)
    blocked: list[tuple[str, str]] = []
    missing: list[tuple[str, str]] = []

    for key, entry in manifest.items():
        if not isinstance(entry, dict):
            continue
        for field in ("path", "image"):
            rel = entry.get(field)
            if not rel or not isinstance(rel, str):
                continue
            norm = rel.strip().lstrip("/")
            full = (asset_root / norm).resolve()
            try:
                asset_rel = full.relative_to(asset_root)
            except ValueError as exc:
                raise ValueError(
                    f'manifest entry "{key}" {field} escapes assets/: {rel}'
                ) from exc
            if asset_rel.parts and asset_rel.parts[0] == "artifacts":
                blocked.append((key, asset_rel.as_posix()))
                continue
            if full not in files:
                files.append(full)
            if not full.exists():
                missing.append((key, asset_rel.as_posix()))

    return files, blocked, missing


def _validate_manifest(
    manifest: dict,
    asset_root: Path,
    manifest_files: list[Path],
) -> list[Path]:
    """Validate manifest and return deployable asset paths."""
    files, blocked, missing = _collect_manifest_assets(
        manifest, asset_root, manifest_files
    )

    if blocked:
        print("ERROR: manifest entries point into assets/artifacts:")
        for key, path in blocked:
            print(f"  - {key}: assets/{path}")
        raise typer.Exit(4)

    if missing:
        print("ERROR: manifest-selected asset files missing:")
        for key, path in missing:
            print(f"  - {key}: assets/{path}")
        raise typer.Exit(3)

    return files


def _is_release_checked_out(repo: Path, branch: str) -> str | None:
    """Return worktree path if release branch is checked out in an active worktree."""
    out = _git("worktree", "list", "--porcelain", cwd=repo)
    current_wt = ""
    for line in out.splitlines():
        if line.startswith("worktree "):
            current_wt = line[len("worktree "):]
        if line.startswith(f"branch refs/heads/{branch}"):
            return current_wt
    return None


def _load_project_config(repo: Path) -> dict:
    proj_path = repo / "project.json"
    project = json.loads(proj_path.read_text(encoding="utf-8"))
    if not isinstance(project, dict):
        raise ValueError("project.json must contain a JSON object")
    return project


def _load_project_roots(project: dict) -> list[str]:
    roots = project.get("releaseExtraRoots", [])
    if not isinstance(roots, list) or not all(isinstance(root, str) for root in roots):
        raise ValueError("project.json.releaseExtraRoots must be an array of strings")
    return roots


def _load_manifests(
    repo: Path,
    project: dict,
) -> tuple[dict, list[Path]]:
    """Load manifests in order and prefix asset paths relative to assets/."""
    manifest_names = project.get("manifests", ["assets/manifest.json"])
    if (
        not isinstance(manifest_names, list)
        or not manifest_names
        or not all(isinstance(name, str) and name for name in manifest_names)
    ):
        raise ValueError("project.json.manifests must be a non-empty array of strings")

    asset_root = (repo / "assets").resolve()
    merged: dict = {}
    manifest_files: list[Path] = []
    for name in manifest_names:
        path = (repo / name).resolve()
        try:
            manifest_rel = path.relative_to(asset_root)
        except ValueError as exc:
            raise ValueError(f"manifest must be under assets/: {name}") from exc
        if not path.exists():
            raise FileNotFoundError(f"manifest not found: {path}")

        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError(f"manifest must contain a JSON object: {path}")

        manifest_files.append(path)
        prefix = manifest_rel.parent
        for key, entry in data.items():
            if not isinstance(entry, dict):
                merged[key] = entry
                continue
            normalized = dict(entry)
            for field in ("path", "image"):
                value = normalized.get(field)
                if isinstance(value, str) and prefix != Path("."):
                    normalized[field] = (prefix / value).as_posix()
            merged[key] = normalized

    return merged, manifest_files


def _build_release_payload(
    source: Path,
    release_wt: Path,
    manifest: dict,
    manifest_files: list[Path],
    extra_roots: list[str],
) -> int:
    """Copy runtime roots + manifest assets into release worktree.

    Returns asset_count.
    """
    real_assets = (source / "assets").resolve()

    # 1. Remove everything except .git
    for item in release_wt.iterdir():
        if item.name == ".git":
            continue
        if item.is_dir():
            shutil.rmtree(item)
        else:
            item.unlink()

    # 2. Copy runtime roots (default + extras)
    all_roots = DEFAULT_RUNTIME_ROOTS + extra_roots
    for root in all_roots:
        src = source / root
        dst = release_wt / root
        if root.endswith("/"):
            if src.is_dir():
                shutil.copytree(src, dst)
        else:
            if src.exists():
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)

    # 3. Validate and collect manifest assets
    asset_files = _validate_manifest(manifest, real_assets, manifest_files)

    # 4. Copy manifest + assets into release worktree
    assets_dst = release_wt / "assets"
    assets_dst.mkdir(exist_ok=True)

    for asset_path in asset_files:
        rel = asset_path.relative_to(real_assets)
        target = assets_dst / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(asset_path, target)

    # 5. Write release-specific .gitignore
    (release_wt / ".gitignore").write_text(RELEASE_GITIGNORE)

    return len(asset_files)


def _commit_release(
    release_wt: Path,
    source_branch: str,
    source_sha: str,
    asset_count: int,
    dry_run: bool = False,
) -> str | None:
    """Stage and commit in the release worktree. Returns commit sha or None."""
    # Stage all changes
    _git("add", "-A", cwd=release_wt)

    # Force-add assets (ignored by source repo .gitignore patterns)
    assets_dir = release_wt / "assets"
    if assets_dir.exists():
        subprocess.run(
            ["git", "add", "-f", "assets/"],
            cwd=release_wt, check=False, capture_output=True, text=True,
        )

    # Check if there is anything to commit
    status = _git("status", "--porcelain", cwd=release_wt)
    if not status:
        return None

    if dry_run:
        print("[dry-run] Would commit with changes:")
        for line in status.splitlines():
            print(f"  {line}")
        return None

    msg = (
        f"release: {source_branch}@{source_sha[:8]}\n\n"
        f"source: {source_branch}\n"
        f"sha: {source_sha}\n"
        f"assets: {asset_count}"
    )
    _git("commit", "-m", msg, cwd=release_wt)
    return _git("rev-parse", "HEAD", cwd=release_wt)


def do_release(
    path: str = ".",
    branch: str = "release",
    dry_run: bool = False,
) -> int:
    """Core release logic. Returns exit code."""
    project_path = Path(path).resolve()
    if not (project_path / "project.json").exists():
        print(f"Error: {project_path} is not a game project (no project.json)")
        return 1

    repo = _resolve_repo_root(project_path)
    source_branch = _get_current_branch(repo)
    source_sha = _get_head_sha(repo)

    if not source_branch:
        print("ERROR: cannot determine current branch (detached HEAD?)")
        return 1

    print(f"Source: {source_branch} @ {source_sha[:8]}")

    try:
        project = _load_project_config(repo)
        manifest, manifest_files = _load_manifests(repo, project)
        extra_roots = _load_project_roots(project)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"ERROR: invalid game release configuration: {exc}")
        return 2

    real_assets = (repo / "assets").resolve()

    # Early artifact check
    try:
        _, blocked, _ = _collect_manifest_assets(
            manifest, real_assets, manifest_files
        )
    except ValueError as exc:
        print(f"ERROR: invalid game release configuration: {exc}")
        return 2
    if blocked:
        print("ERROR: manifest entries point into assets/artifacts:")
        for key, p in blocked:
            print(f"  - {key}: assets/{p}")
        return 4

    if extra_roots:
        print(f"Extra roots: {', '.join(extra_roots)}")

    # Check if release branch is checked out in another worktree
    conflict_path = _is_release_checked_out(repo, branch)
    if conflict_path:
        print(f"ERROR: {branch} branch is checked out in worktree: {conflict_path}")
        return 1

    branch_exists = bool(_git("branch", "--list", branch, cwd=repo))

    if dry_run:
        with tempfile.TemporaryDirectory(prefix="release-") as tmp:
            tmp_path = Path(tmp) / "wt"
            _git("worktree", "add", "--detach", str(tmp_path), "HEAD", cwd=repo)
            try:
                asset_count = _build_release_payload(
                    repo, tmp_path, manifest, manifest_files, extra_roots
                )
                _commit_release(tmp_path, source_branch, source_sha, asset_count, dry_run=True)
                print(f"\n[dry-run] Payload ready: {asset_count} assets")
                print(f"[dry-run] No changes written to {branch}")
            finally:
                _git("worktree", "remove", str(tmp_path), "--force", cwd=repo)
        return 0

    # Real run: create or reuse the release branch
    with tempfile.TemporaryDirectory(prefix="release-") as tmp:
        tmp_path = Path(tmp) / "wt"

        if not branch_exists:
            _git("worktree", "add", "--detach", str(tmp_path), "HEAD", cwd=repo)
            _git("checkout", "-b", branch, cwd=tmp_path)
        else:
            _git("worktree", "add", str(tmp_path), branch, cwd=repo)

        try:
            asset_count = _build_release_payload(
                repo, tmp_path, manifest, manifest_files, extra_roots
            )
            release_sha = _commit_release(
                tmp_path, source_branch, source_sha, asset_count
            )

            if release_sha:
                action = "created" if not branch_exists else "updated"
                print(f"\nRelease branch {action}: {branch} @ {release_sha[:8]}")
                print(f"  assets: {asset_count}")
                print(f"  source: {source_branch} @ {source_sha[:8]}")
            else:
                print(f"\nRelease branch {branch} is already up to date")

        finally:
            _git("worktree", "remove", str(tmp_path), "--force", cwd=repo)

    return 0


def register(app):
    """Register release command on the typer app."""

    @app.command("release")
    def release_cmd(
        path: str = typer.Argument(default=".", help="Game project path"),
        branch: str = typer.Option("release", "-b", "--branch", help="Target release branch name"),
        dry_run: bool = typer.Option(False, "--dry-run", help="Validate without writing"),
    ):
        """Generate or refresh a pure release branch for deployment"""
        code = do_release(path=path, branch=branch, dry_run=dry_run)
        raise typer.Exit(code)
