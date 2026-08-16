"""Promote one verified game-project prior into the VibeGame source checkout."""

from __future__ import annotations

import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path

import typer
from PIL import Image, UnidentifiedImageError

from cli.router import app


SOURCE_DIR = Path(__file__).resolve().parent.parent
EVOLVE_KINDS = ("skeleton", "module", "contract")
SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
MODULE_PATTERN = re.compile(r"^[A-Z][A-Za-z0-9]*Module$")
PRIVATE_PATH_PATTERNS = (
    re.compile(r"/Users/[^/\s]+/"),
    re.compile(r"/home/[^/\s]+/"),
    re.compile(r"[A-Za-z]:\\Users\\[^\\\s]+\\"),
)
TEXT_SUFFIXES = {".html", ".js", ".json", ".md", ".py"}
REFERENCE_IMAGE_SUFFIXES = {".jpeg", ".jpg", ".png", ".webp"}
SKELETON_ROOT_FILES = (
    "project.json",
    "index.html",
    "index.md",
    "art-pack.md",
    "errors.md",
)
SKELETON_DIRECTORY_PATTERNS = {
    "config": ("*.json",),
    "scenes": ("*.scene.json",),
    "entities": ("*.node.json",),
    "scripts": ("*.js",),
    "art-pack-assets": ("*.png", "*.jpg", "*.jpeg", "*.webp"),
}


@dataclass(frozen=True)
class PromotionPlan:
    kind: str
    name: str
    project_root: Path
    source_dir: Path
    candidate: Path
    destinations: tuple[Path, ...]
    managed_destinations: tuple[Path, ...]
    files: tuple[Path, ...]
    not_copied: tuple[Path, ...]
    index_destination: Path


def _validate_source_checkout(source_dir: Path) -> Path:
    source_dir = source_dir.resolve()
    source_root = source_dir.parent
    required = (
        source_root / "config" / "registry.json",
        source_dir / "modules",
        source_dir / "modules" / "check",
        source_dir / "modules" / "index.md",
        source_dir / "skeletons",
        source_dir / "skeletons" / "index.md",
        source_dir / ".vibegame" / "spec" / "contracts",
        source_dir / ".vibegame" / "spec" / "contracts" / "index.md",
    )
    missing = [path for path in required if not path.exists()]
    if missing:
        details = ", ".join(str(path) for path in missing)
        raise ValueError(
            f"VibeGame source checkout not found from installed CLI: {details}"
        )
    for path in required:
        _ensure_no_symlink(path, source_root)
    return source_dir


def _validate_name(kind: str, name: str) -> None:
    if kind not in EVOLVE_KINDS:
        raise ValueError(f"kind must be one of: {', '.join(EVOLVE_KINDS)}")
    if kind == "module":
        if not MODULE_PATTERN.fullmatch(name):
            raise ValueError(
                "module name must use PascalCase and end with Module, "
                "for example SwipeSlashModule"
            )
        return
    if not SLUG_PATTERN.fullmatch(name):
        raise ValueError(
            f"{kind} name must be lowercase kebab-case, "
            "for example swipe-slice-arcade"
        )


def _destination_paths(
    source_dir: Path,
    kind: str,
    name: str,
) -> tuple[tuple[Path, ...], Path]:
    if kind == "skeleton":
        return (
            (source_dir / "skeletons" / name,),
            source_dir / "skeletons" / "index.md",
        )
    if kind == "module":
        return (
            (
                source_dir / "modules" / f"{name}.js",
                source_dir / "modules" / "check" / f"{name}.check.py",
            ),
            source_dir / "modules" / "index.md",
        )
    return (
        (source_dir / ".vibegame" / "spec" / "contracts" / f"{name}.md",),
        source_dir / ".vibegame" / "spec" / "contracts" / "index.md",
    )


def _ensure_no_destination_conflict(destinations: tuple[Path, ...]) -> None:
    conflicts = [
        path for path in destinations if path.exists() or path.is_symlink()
    ]
    if conflicts:
        details = "\n".join(f"  - {path}" for path in conflicts)
        raise ValueError(
            "Source prior already exists. Resolve the conflict manually:\n"
            f"{details}"
        )


def _ensure_no_symlink(path: Path, boundary: Path) -> None:
    boundary = boundary.resolve()
    try:
        relative = path.absolute().relative_to(boundary)
    except ValueError as exc:
        raise ValueError(f"Selected file is outside candidate: {path}") from exc

    current = boundary
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise ValueError(f"Symlink is not allowed for selected content: {current}")


def _resolve_inside_assets(path: Path, assets_root: Path, label: str) -> Path:
    resolved = path.resolve()
    try:
        resolved.relative_to(assets_root.resolve())
    except ValueError as exc:
        raise ValueError(f"{label} must remain under assets/: {path}") from exc
    return path


def _read_json_object(path: Path, label: str) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Invalid JSON in {label}: {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"{label} must contain a JSON object: {path}")
    return data


def _collect_manifest_files(candidate: Path, selected: set[Path]) -> None:
    project_file = candidate / "project.json"
    project = _read_json_object(project_file, "project.json")
    manifest_names = project.get("manifests", ["assets/manifest.json"])
    if (
        not isinstance(manifest_names, list)
        or not manifest_names
        or not all(isinstance(name, str) and name for name in manifest_names)
    ):
        raise ValueError(
            "project.json.manifests must be a non-empty array of strings"
        )

    assets_root = candidate / "assets"
    for manifest_name in manifest_names:
        manifest_path = _resolve_inside_assets(
            candidate / manifest_name,
            assets_root,
            f"Manifest {manifest_name}",
        )
        _ensure_no_symlink(manifest_path, candidate)
        if not manifest_path.is_file():
            raise ValueError(f"Manifest not found: {manifest_path}")

        manifest = _read_json_object(manifest_path, "manifest")
        selected.add(manifest_path)
        for key, entry in manifest.items():
            if not isinstance(entry, dict):
                continue
            for field in ("path", "image"):
                value = entry.get(field)
                if value is None:
                    continue
                if not isinstance(value, str) or not value:
                    raise ValueError(
                        f'Manifest entry "{key}" field "{field}" must be a non-empty string'
                    )
                asset_path = _resolve_inside_assets(
                    manifest_path.parent / value,
                    assets_root,
                    f'Manifest entry "{key}" field "{field}"',
                )
                _ensure_no_symlink(asset_path, candidate)
                if not asset_path.is_file():
                    raise ValueError(
                        f'Manifest asset not found for "{key}" field "{field}": '
                        f"{asset_path}"
                    )
                selected.add(asset_path)


def _candidate_content(candidate: Path) -> set[Path]:
    content: set[Path] = set()
    for root, dirs, filenames in os.walk(candidate, followlinks=False):
        root_path = Path(root)
        for dirname in dirs:
            directory = root_path / dirname
            if directory.is_symlink():
                content.add(directory)
        for filename in filenames:
            content.add(root_path / filename)
    return content


def _collect_skeleton_files(candidate: Path) -> tuple[tuple[Path, ...], tuple[Path, ...]]:
    if candidate.is_symlink():
        raise ValueError(f"Symlink is not allowed: {candidate}")
    if not candidate.is_dir():
        raise ValueError(f"Skeleton candidate not found: {candidate}")

    selected: set[Path] = set()
    missing = [name for name in SKELETON_ROOT_FILES if not (candidate / name).is_file()]
    if missing:
        raise ValueError(
            f"Skeleton is missing required files: {', '.join(missing)}"
        )

    for name in SKELETON_ROOT_FILES:
        selected.add(candidate / name)

    for directory_name, patterns in SKELETON_DIRECTORY_PATTERNS.items():
        directory = candidate / directory_name
        if not directory.is_dir() or directory.is_symlink():
            continue
        for pattern in patterns:
            selected.update(path for path in directory.rglob(pattern) if path.is_file())

    _collect_manifest_files(candidate, selected)
    for path in selected:
        _ensure_no_symlink(path, candidate)

    all_content = _candidate_content(candidate)
    return tuple(sorted(selected)), tuple(sorted(all_content - selected))


def _collect_single_file(candidate: Path, boundary: Path, label: str) -> tuple[Path, ...]:
    _ensure_no_symlink(candidate, boundary)
    if not candidate.is_file():
        raise ValueError(f"{label} candidate not found: {candidate}")
    return (candidate,)


def _validate_selected_files(
    files: tuple[Path, ...],
    project_root: Path,
    candidate_boundary: Path,
) -> None:
    project_text = str(project_root.resolve())
    for path in files:
        _ensure_no_symlink(path, candidate_boundary)
        if path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError(f"Text file is not UTF-8: {path}") from exc

        if project_text in text:
            raise ValueError(
                f"Private or project-local path found in {path}: {project_text}"
            )
        for pattern in PRIVATE_PATH_PATTERNS:
            match = pattern.search(text)
            if match:
                raise ValueError(
                    f"Private or project-local path found in {path}: {match.group(0)}"
                )

        if path.suffix.lower() == ".json":
            try:
                json.loads(text)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON: {path}: {exc}") from exc


def _validate_reference_images(candidate: Path, files: tuple[Path, ...]) -> None:
    reference_root = candidate / "art-pack-assets"
    for path in files:
        if path.suffix.lower() not in REFERENCE_IMAGE_SUFFIXES:
            continue
        try:
            path.relative_to(reference_root)
        except ValueError:
            continue
        try:
            with Image.open(path) as image:
                image.verify()
        except (OSError, UnidentifiedImageError) as exc:
            raise ValueError(f"Invalid reference image: {path}: {exc}") from exc


def _build_plan(
    project_root: Path,
    source_dir: Path,
    kind: str,
    name: str,
) -> PromotionPlan:
    project_root = project_root.resolve()
    source_dir = _validate_source_checkout(source_dir)
    _validate_name(kind, name)
    if not (project_root / "project.json").is_file():
        raise ValueError(f"Not a game project: {project_root}")

    managed_destinations, index_destination = _destination_paths(
        source_dir, kind, name
    )
    _ensure_no_destination_conflict(managed_destinations)

    if kind == "skeleton":
        candidate = project_root / "skeletons" / name
        _ensure_no_symlink(candidate, project_root)
        files, not_copied = _collect_skeleton_files(candidate)
        candidate_boundary = candidate
        _validate_reference_images(candidate, files)
    elif kind == "module":
        candidate = project_root / "modules" / f"{name}.js"
        files_list = list(
            _collect_single_file(candidate, project_root, "Module")
        )
        check = project_root / "modules" / "check" / f"{name}.check.py"
        if check.exists() or check.is_symlink():
            files_list.extend(
                _collect_single_file(check, project_root, "Module check")
            )
        files = tuple(files_list)
        not_copied = ()
        candidate_boundary = project_root
    else:
        candidate = project_root / ".vibegame" / "spec" / "contracts" / f"{name}.md"
        files = _collect_single_file(candidate, project_root, "Contract")
        not_copied = ()
        candidate_boundary = project_root

    _validate_selected_files(files, project_root, candidate_boundary)
    destinations = (
        managed_destinations[: len(files)]
        if kind == "module"
        else managed_destinations
    )
    return PromotionPlan(
        kind=kind,
        name=name,
        project_root=project_root,
        source_dir=source_dir,
        candidate=candidate,
        destinations=destinations,
        managed_destinations=managed_destinations,
        files=files,
        not_copied=not_copied,
        index_destination=index_destination,
    )


def _copy_plan_to_stage(plan: PromotionPlan, staging: Path) -> tuple[Path, ...]:
    staging.mkdir(parents=True, exist_ok=True)
    if plan.kind == "skeleton":
        staged_target = staging / "prior"
        for source in plan.files:
            relative = source.relative_to(plan.candidate)
            target = staged_target / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        return (staged_target,)

    if plan.kind == "module":
        staged_module = staging / f"{plan.name}.js"
        shutil.copy2(plan.files[0], staged_module)
        staged = [staged_module]
        if len(plan.files) == 2:
            staged_check = staging / f"{plan.name}.check.py"
            shutil.copy2(plan.files[1], staged_check)
            staged.append(staged_check)
        return tuple(staged)

    staged_contract = staging / f"{plan.name}.md"
    shutil.copy2(plan.files[0], staged_contract)
    return (staged_contract,)


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.bind(("127.0.0.1", 0))
        return int(server.getsockname()[1])


def _run_boot_smoke(staged_candidate: Path) -> None:
    """Boot the staged skeleton in the real runtime and stop every process started."""
    try:
        from playwright.sync_api import Error as PlaywrightError
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise ValueError(
            "Staged runtime smoke check requires Playwright"
        ) from exc

    port = _free_port()
    runtime_server = Path(__file__).resolve().parent / "runtime_server.py"
    log_path = staged_candidate.parent / "runtime-smoke.log"
    command = [
        sys.executable,
        str(runtime_server),
        str(staged_candidate),
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
    ]
    print(f"Running staged runtime smoke check: {staged_candidate}")
    with log_path.open("w", encoding="utf-8") as log_file:
        process = subprocess.Popen(
            command,
            cwd=staged_candidate.parent,
            stdin=subprocess.DEVNULL,
            stdout=log_file,
            stderr=subprocess.STDOUT,
        )

    try:
        base_url = f"http://127.0.0.1:{port}"
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            if process.poll() is not None:
                break
            try:
                with urllib.request.urlopen(f"{base_url}/api/project", timeout=1):
                    break
            except OSError:
                time.sleep(0.25)
        else:
            raise ValueError("Staged runtime server did not become ready within 15 seconds")

        if process.poll() is not None:
            raise ValueError(
                f"Staged runtime server exited with code {process.returncode}"
            )

        page_errors: list[str] = []
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                page = browser.new_page()
                page.on("pageerror", lambda error: page_errors.append(str(error)))
                response = page.goto(base_url, wait_until="domcontentloaded", timeout=30000)
                if response is None or not response.ok:
                    status = "no response" if response is None else str(response.status)
                    raise ValueError(f"Staged runtime page failed to load: {status}")
                page.wait_for_function(
                    "window.__vibegame_ready === true",
                    timeout=30000,
                )
            finally:
                browser.close()
        if page_errors:
            raise ValueError(
                "Staged runtime page errors:\n"
                + "\n".join(f"  - {error}" for error in page_errors)
            )
    except (OSError, PlaywrightError, ValueError) as exc:
        try:
            log_lines = log_path.read_text(encoding="utf-8").splitlines()[-40:]
        except OSError as log_exc:
            log_lines = [f"Could not read runtime log: {log_exc}"]
        log_text = "\n".join(log_lines) or "(runtime log is empty)"
        raise ValueError(
            f"Staged runtime smoke check failed: {exc}\n"
            f"Runtime log from {log_path}:\n{log_text}"
        ) from exc
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)

    print("Staged runtime smoke check passed.")


def _validate_staged_skeleton(staged_candidate: Path) -> None:
    from cli.check import check_project

    print(f"Running vibegame check on staged skeleton: {staged_candidate}")
    errors = [
        issue for issue in check_project(staged_candidate) if issue.level == "error"
    ]
    if errors:
        details = "\n".join(str(issue) for issue in errors)
        raise ValueError(f"vibegame check failed for staged skeleton:\n{details}")
    _run_boot_smoke(staged_candidate)


def _apply_new_files(
    staged: tuple[Path, ...],
    destinations: tuple[Path, ...],
    managed_destinations: tuple[Path, ...],
) -> None:
    _ensure_no_destination_conflict(managed_destinations)
    written: list[tuple[Path, Path]] = []
    try:
        for source, destination in zip(staged, destinations, strict=True):
            os.replace(source, destination)
            written.append((destination, source))
    except Exception:
        for destination, source in reversed(written):
            os.replace(destination, source)
        raise


def _print_plan(plan: PromotionPlan) -> None:
    print(f"Project candidate: {plan.candidate}")
    print(f"Source checkout: {plan.source_dir.parent}")
    print("Destinations:")
    for destination in plan.destinations:
        print(f"  + {destination}")
    print("Copied files:")
    for path in plan.files:
        print(f"  + {path.relative_to(plan.project_root)}")
    if plan.not_copied:
        print("Not copied:")
        for path in plan.not_copied:
            print(f"  - {path.relative_to(plan.project_root)}")


def promote_prior(
    *,
    project: str,
    kind: str,
    name: str,
    dry_run: bool = False,
    source_dir: Path | None = None,
) -> PromotionPlan:
    plan = _build_plan(Path(project), source_dir or SOURCE_DIR, kind, name)
    _print_plan(plan)

    source_root = plan.source_dir.parent
    with tempfile.TemporaryDirectory(
        prefix=".vibegame-evolve-",
        dir=source_root,
    ) as temporary:
        staged = _copy_plan_to_stage(plan, Path(temporary) / "staging")
        if plan.kind == "skeleton":
            _validate_staged_skeleton(staged[0])

        if dry_run:
            print("[dry-run] Validation passed. Source checkout was not changed.")
            print("After promotion, this source index will require a manual edit:")
            print(f"  {plan.index_destination}")
            return plan

        _apply_new_files(staged, plan.destinations, plan.managed_destinations)

    print(f"Promotion completed: {plan.kind} {plan.name}")
    print("Source index requires a manual edit:")
    print(f"  {plan.index_destination}")
    print("Source files changed but not committed.")
    return plan


@app.command("evolve")
def evolve_cmd(
    kind: str = typer.Argument(
        help="Prior type: skeleton, module, or contract",
    ),
    name: str = typer.Option(
        ...,
        "-n",
        "--name",
        help="Prior name",
    ),
    project: str = typer.Option(
        ".",
        "--project",
        help="Game project path",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Validate and show changes without writing",
    ),
) -> None:
    """Promote one verified project prior into the VibeGame source checkout."""
    try:
        promote_prior(
            project=project,
            kind=kind,
            name=name,
            dry_run=dry_run,
        )
    except (OSError, ValueError) as exc:
        print(f"Error: {exc}")
        raise typer.Exit(1) from exc
