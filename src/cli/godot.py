"""Godot engine support for VibeGame (experimental).

The Phaser runtime is the default engine. This module adds a self-contained
Godot 4 companion that lives beside it:

    vibegame godot init    scaffold a Godot project
    vibegame godot run     launch the game plus the runtime bridge adapter
    vibegame godot check   static checks, GDScript parse, headless boot
    vibegame godot doctor  locate and report the Godot binary

`vibegame play` works unchanged against a running Godot project because the
adapter exposes the same `/api/runtime/*` REST surface as the Phaser runtime.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import typer

GODOT_TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "godot_template"
VIBEGAME_SRC_DIR = Path(__file__).resolve().parent.parent
# Copied from src/.vibegame when present.
SUPPORT_DOCS = (".vibegame/GDD.md", ".vibegame/assets.md")
TEXT_SUFFIXES = {
    ".cfg",
    ".gd",
    ".godot",
    ".import",
    ".json",
    ".md",
    ".svg",
    ".tres",
    ".tscn",
    ".txt",
}
LANGUAGE_NAMES = {
    "en": "English",
    "zh-CN": "Chinese",
    "ja": "Japanese",
    "ko": "Korean",
    "es": "Spanish",
    "fr": "French",
    "de": "German",
    "pt": "Portuguese",
    "ru": "Russian",
    "ar": "Arabic",
}

godot_app = typer.Typer(
    name="godot",
    no_args_is_help=True,
    help="Godot engine support (experimental): init, run, check, doctor",
    rich_markup_mode=None,
    pretty_exceptions_enable=False,
)


def project_engine(project_path: Path) -> str:
    """Return the `engine` value from project.json, or an empty string."""
    try:
        data = json.loads((project_path / "project.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ""
    value = data.get("engine")
    return value if isinstance(value, str) else ""


def is_godot_project(project_path: Path) -> bool:
    return project_engine(project_path).startswith("godot@")


def find_godot_binary(explicit: str | None = None) -> str | None:
    """Locate the Godot executable without assuming a package manager."""
    candidates: list[str] = []
    if explicit:
        candidates.append(explicit)
    env_bin = os.environ.get("GODOT_BIN")
    if env_bin:
        candidates.append(env_bin)
    which_bin = shutil.which("godot")
    if which_bin:
        candidates.append(which_bin)
    home = Path.home()
    candidates.extend(
        [
            "/Applications/Godot.app/Contents/MacOS/Godot",
            str(home / "Applications/Godot.app/Contents/MacOS/Godot"),
            r"C:\Program Files\Godot\Godot.exe",
            str(home / "Godot.app/Contents/MacOS/Godot"),
        ]
    )
    for candidate in candidates:
        path = Path(candidate).expanduser()
        if path.is_file() and os.access(path, os.X_OK):
            return str(path)
    return None


def require_godot_binary(explicit: str | None = None) -> str:
    binary = find_godot_binary(explicit)
    if binary:
        return binary
    typer.echo(
        "Godot was not found.\n"
        "Install Godot 4.x, or set GODOT_BIN to the executable path.\n"
        "  macOS:  brew install --cask godot\n"
        "  Linux:  download from https://godotengine.org/download\n"
        "  Windows: install from https://godotengine.org/download",
        err=True,
    )
    raise typer.Exit(1)


IMPORT_TIMEOUT_S = 300


class GodotImportError(RuntimeError):
    """`godot --import` failed or did not finish."""


def import_assets(binary: str, project_path: Path) -> None:
    """Import new or changed assets, as the editor does when it opens the project.

    A project launched from the command line never imports, so an image added
    since the last import fails to load with "No loader found for resource".
    """
    command = [binary, "--headless", "--path", str(project_path), "--import"]
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=IMPORT_TIMEOUT_S)
    except subprocess.TimeoutExpired as exc:
        raise GodotImportError(
            f"asset import did not finish within {IMPORT_TIMEOUT_S}s: {' '.join(command)}"
        ) from exc
    if result.returncode != 0:
        tail = ((result.stdout or "") + (result.stderr or "")).strip().splitlines()[-5:]
        raise GodotImportError(
            f"asset import exited {result.returncode}: {' '.join(command)}\n" + "\n".join(tail)
        )


def godot_version(binary: str) -> tuple[int, int, int] | None:
    try:
        result = subprocess.run(
            [binary, "--version"],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    output = (result.stdout or "") + (result.stderr or "")
    match = re.search(r"(\d+)\.(\d+)(?:\.(\d+))?", output)
    if not match:
        return None
    return (int(match.group(1)), int(match.group(2)), int(match.group(3) or 0))


def _default_language() -> str:
    defaults_path = VIBEGAME_SRC_DIR / ".vibegame" / "defaults.json"
    try:
        data = json.loads(defaults_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return "en"
    language = data.get("language")
    return language if language in LANGUAGE_NAMES else "en"


def _replace_placeholders(text: str, replacements: dict[str, str]) -> str:
    for key, value in replacements.items():
        text = text.replace("{{" + key + "}}", str(value))
    return text


def _template_files(source: Path) -> list[Path]:
    return [
        path
        for path in sorted(source.rglob("*"))
        if path.is_file() and "__pycache__" not in path.parts and path.name != ".DS_Store"
    ]


def _copy_template_tree(
    source: Path, target: Path, replacements: dict[str, str]
) -> list[str]:
    """Copy a template tree, substituting placeholders in text files."""
    written: list[str] = []
    for path in _template_files(source):
        relative = path.relative_to(source)
        destination = target / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        if path.suffix in TEXT_SUFFIXES or path.name == ".gitignore":
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                shutil.copy2(path, destination)
            else:
                destination.write_text(
                    _replace_placeholders(text, replacements), encoding="utf-8"
                )
        else:
            shutil.copy2(path, destination)
        written.append(relative.as_posix())
    return written


def _copy_support_doc(relative: str, target: Path) -> bool:
    source = VIBEGAME_SRC_DIR / relative
    if not source.is_file():
        return False
    destination = target / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    return True


@godot_app.command("init")
def init(
    path: str = typer.Argument(default=".", help="Project path (default: current directory)"),
    lang: str | None = typer.Option(None, "--lang", help="Language: zh-CN / en / ..."),
    name: str | None = typer.Option(None, "--name", help="Game name (default: directory name)"),
    force: bool = typer.Option(
        False, "--force", help="Overwrite existing scaffold files: template files, CLAUDE.md, AGENTS.md, .vibegame docs"
    ),
    godot_bin: str | None = typer.Option(None, "--godot", help="Path to the Godot executable"),
):
    """Initialize a Godot 4 game project."""
    project_path = Path(path).expanduser().resolve()
    project_path.mkdir(parents=True, exist_ok=True)
    template_root = GODOT_TEMPLATE_DIR / "project"
    planned = [
        *(path.relative_to(template_root).as_posix() for path in _template_files(template_root)),
        "CLAUDE.md",
        "AGENTS.md",
        *(relative for relative in SUPPORT_DOCS if (VIBEGAME_SRC_DIR / relative).is_file()),
        ".vibegame/global.json",
    ]
    existing = [relative for relative in planned if (project_path / relative).exists()]
    if existing and not force:
        typer.echo(
            f"Error: init would overwrite existing files in {project_path}. Use --force to overwrite them:\n  "
            + "\n  ".join(existing),
            err=True,
        )
        raise typer.Exit(1)

    if lang is not None and lang not in LANGUAGE_NAMES:
        typer.echo(
            f"--lang must be one of: {', '.join(LANGUAGE_NAMES)}", err=True
        )
        raise typer.Exit(1)
    language = lang or _default_language()
    project_name = name or project_path.name

    binary = find_godot_binary(godot_bin)
    version = godot_version(binary) if binary else None
    if version is None:
        version = (4, 7, 2)
        typer.echo(
            "Warning: Godot not found; scaffolding with engine id godot@4.7.2. "
            "Install Godot or set GODOT_BIN before running the project.",
            err=True,
        )
    engine_id = f"godot@{version[0]}.{version[1]}.{version[2]}"
    width, height = 1280, 720
    replacements = {
        "PROJECT_NAME": project_name,
        "ENGINE_ID": engine_id,
        "GODOT_FEATURE": f"{version[0]}.{version[1]}",
        "WIDTH": str(width),
        "HEIGHT": str(height),
        "LANGUAGE": language,
        "language_name": LANGUAGE_NAMES[language],
        "language_code": language,
    }

    written = _copy_template_tree(template_root, project_path, replacements)
    claude_text = _replace_placeholders(
        (GODOT_TEMPLATE_DIR / "CLAUDE.md").read_text(encoding="utf-8"), replacements
    )
    (project_path / "CLAUDE.md").write_text(claude_text, encoding="utf-8")
    (project_path / "AGENTS.md").write_text(claude_text, encoding="utf-8")
    written.extend(["CLAUDE.md", "AGENTS.md"])

    for relative in SUPPORT_DOCS:
        if _copy_support_doc(relative, project_path):
            written.append(relative)

    global_json = {
        "project_root": str(project_path),
        "project": project_name,
        "language": language,
        "engine": "godot",
        "debug": False,
    }
    global_path = project_path / ".vibegame" / "global.json"
    global_path.parent.mkdir(parents=True, exist_ok=True)
    global_path.write_text(json.dumps(global_json, indent=2) + "\n", encoding="utf-8")
    written.append(".vibegame/global.json")

    for directory in (
        "assets",
        "config",
        "scenes",
        "scripts",
        ".vibegame/tasks",
        ".vibegame/logs/runtime",
        ".vibegame/spec/godot",
    ):
        (project_path / directory).mkdir(parents=True, exist_ok=True)

    typer.echo("=== VibeGame Godot Init ===")
    typer.echo(f"  Project: {project_path}")
    typer.echo(f"  Engine:  {engine_id}")
    typer.echo(f"  Language: {language}")
    typer.echo(f"  Files:   {len(written)} written")
    typer.echo("")
    typer.echo("Next steps:")
    typer.echo(f"  cd {project_path}")
    typer.echo("  vibegame godot check")
    typer.echo("  vibegame godot run --port auto")


@godot_app.command("run")
def run(
    path: str = typer.Argument(default=".", help="Game project path (default: current directory)"),
    host: str = typer.Option("127.0.0.1", "--host", help="Runtime API host"),
    port: str = typer.Option("8765", "--port", "-p", help="Runtime API port, or auto"),
    background: bool = typer.Option(False, "--background", "-b", help="Run the runtime in the background"),
    headless: bool = typer.Option(False, "--headless", help="Run Godot headless (no window, no screenshots)"),
    godot_bin: str | None = typer.Option(None, "--godot", help="Path to the Godot executable"),
    logs: bool = typer.Option(False, "--logs", help="Show the runtime log for the resolved port"),
    status: bool = typer.Option(False, "--status", help="Show tracked runtime status"),
):
    """Launch a Godot game with the VibeGame runtime API."""
    from cli.godot_runtime import run_godot

    run_godot(
        project_path=Path(path).expanduser().resolve(),
        host=host,
        port=port,
        background=background,
        headless=headless,
        godot_bin=godot_bin,
        logs=logs,
        status=status,
    )


@godot_app.command("check")
def check(
    path: str = typer.Argument(default=".", help="Game project path (default: current directory)"),
    godot_bin: str | None = typer.Option(None, "--godot", help="Path to the Godot executable"),
    no_boot: bool = typer.Option(False, "--no-boot", help="Skip the headless boot check"),
):
    """Validate a Godot project: files, GDScript parse, headless boot."""
    from cli.godot_check import check_godot_project

    project_path = Path(path).expanduser().resolve()
    if not (project_path / "project.json").is_file():
        typer.echo(f"Error: {project_path} is not a game project (no project.json)", err=True)
        raise typer.Exit(1)
    if not is_godot_project(project_path):
        typer.echo(
            f"Error: {project_path} is not a Godot project "
            f"(engine={project_engine(project_path) or 'missing'})",
            err=True,
        )
        raise typer.Exit(1)

    issues = check_godot_project(
        project_path,
        godot_bin=find_godot_binary(godot_bin),
        boot_check=not no_boot,
    )
    errors = [issue for issue in issues if issue.level == "error"]
    warnings = [issue for issue in issues if issue.level == "warning"]
    for issue in issues:
        typer.echo(str(issue))
    if not issues:
        typer.echo("Godot project check passed.")
    else:
        typer.echo(
            f"\n{len(errors)} error(s), {len(warnings)} warning(s)."
        )
    raise typer.Exit(1 if errors else 0)


@godot_app.command("doctor")
def doctor(
    godot_bin: str | None = typer.Option(None, "--godot", help="Path to the Godot executable"),
):
    """Report the Godot toolchain and template status."""
    binary = find_godot_binary(godot_bin)
    typer.echo("=== VibeGame Godot Doctor ===")
    typer.echo(f"  Template: {GODOT_TEMPLATE_DIR}")
    typer.echo(f"  Template present: {GODOT_TEMPLATE_DIR.is_dir()}")
    if not binary:
        typer.echo("  Godot:   NOT FOUND")
        typer.echo("")
        typer.echo("Install Godot 4.x or set GODOT_BIN.")
        raise typer.Exit(1)
    version = godot_version(binary)
    typer.echo(f"  Godot:   {binary}")
    typer.echo(
        "  Version: " + (".".join(str(part) for part in version) if version else "unknown")
    )
    project_path = Path.cwd()
    if (project_path / "project.json").is_file():
        engine = project_engine(project_path) or "missing"
        typer.echo(f"  Project: {project_path} (engine={engine})")
    else:
        typer.echo("  Project: not a game project (run `vibegame godot init`)")
    raise typer.Exit(0)
