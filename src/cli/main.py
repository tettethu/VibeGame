"""
VibeGame CLI - Game development tool

Usage:
  vibegame setup                       # Interactive setup wizard (first-time)
  vibegame init [path]                 # Init project config
  vibegame start [path]                # Launch Dashboard + agent sessions
  vibegame run [path]                  # Start server + visible runtime session
  vibegame run [path] --activate       # Start runtime paused at frame 0
  vibegame run [path] --debug          # Show physics debug bodies
  vibegame run [path] --shot logs/run.mp4 # Record runtime browser video
  vibegame run [path] --headless       # Start server + headless runtime session
  vibegame run [path] -b               # Start server in background
  vibegame run [path] --logs           # Show runtime server logs
  vibegame close [path]                # Stop tracked runtime session
  vibegame art                         # Art tools
  vibegame evolve <kind> -n <name>     # Promote one shared prior
  vibegame --help                      # Help

Deploy:
  Push the game project to GitHub Pages - no export needed.
  index.html uses relative paths and works as a static site directly.

Runtime server management:
  vibegame run                         # Visible Playwright Chrome + runtime API
  vibegame run --activate              # Visible runtime API, paused before first gameplay frame
  vibegame run --debug                 # Visible runtime with physics debug bodies
  vibegame run --shot logs/run.mp4     # Record runtime browser video until close
  vibegame run --headless              # Headless Playwright Chrome + runtime API
  vibegame run -b --activate           # Background runtime API, paused before first gameplay frame
  vibegame run -b --debug              # Background runtime with physics debug bodies
  vibegame run -b                      # Background start (no runtime session)
  vibegame run -b --port 3000          # Custom port
  vibegame run --status                # Show server status (launcher/server PID, address)
  vibegame run --logs                  # Last 50 lines of .vibegame/logs/runtime/server-<port>.log
  vibegame close                       # Stop via PID (cross-platform)
  vibegame close path/to/project       # Stop runtime for specific project

Release:
  vibegame release                     # Generate pure release branch for deployment
  vibegame release --dry-run           # Validate without writing
  vibegame release -b production       # Custom branch name

Files: .vibegame/logs/runtime/servers.json (launcher/server PID+host+port+background), .vibegame/logs/runtime/server-<port>.log (stdout/stderr, foreground and background)
"""

import os
import re
import sys
import json
import shutil
import subprocess as sp
import questionary
from pathlib import Path
from typing import Literal
import typer

from cli.router import app
import cli.run  # noqa: F401
import cli.play  # noqa: F401
import cli.release  # noqa: F401
import cli.start  # noqa: F401
import cli.evolve  # noqa: F401


# Allowed text file types for copying with template replacement / append.
TEXT_FILE_EXTENSIONS = {".md", ".json", ".py", ".txt", ".yaml", ".yml", ".js", ".html", ".css", ".toml"}

ACTION_SKIP = "skip"
ACTION_OVERWRITE = "overwrite"
ACTION_APPEND = "append"
InitChoice = Literal["ask", "skip", "overwrite"]


def _ask_conflict(rel_path: str) -> tuple[str, bool]:
    """Ask user how to handle existing file, returns (action, is_always)."""
    try:
        choice = questionary.select(
            f"File already exists: {rel_path}",
            choices=[
                questionary.Choice("skip", value=(ACTION_SKIP, False)),
                questionary.Choice("overwrite", value=(ACTION_OVERWRITE, False)),
                questionary.Choice("append", value=(ACTION_APPEND, False)),
                questionary.Choice("always skip", value=(ACTION_SKIP, True)),
                questionary.Choice("always overwrite", value=(ACTION_OVERWRITE, True)),
                questionary.Choice("always append", value=(ACTION_APPEND, True)),
            ],
        ).ask()
    except KeyboardInterrupt:
        raise typer.Exit(1)
    if choice is None:
        raise typer.Exit(1)
    return choice


def _strip_yaml_frontmatter(content: str) -> str:
    """Strip leading YAML frontmatter when present."""
    lines = content.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        return content
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            return "".join(lines[index + 1:]).lstrip()
    return content


def _generate_codex_roles(project_path: Path) -> list[str]:
    """Generate static Codex role docs from project role sources."""
    roles_dir = project_path / ".codex" / "roles"
    roles_dir.mkdir(parents=True, exist_ok=True)

    sources: dict[str, Path] = {}

    agents_dir = project_path / ".claude" / "agents"
    if agents_dir.is_dir():
        for agent_file in sorted(agents_dir.glob("*.md")):
            sources[agent_file.stem] = agent_file

    written: list[str] = []
    for role, source_path in sorted(sources.items()):
        content = _strip_yaml_frontmatter(source_path.read_text(encoding="utf-8"))
        destination = roles_dir / f"{role}.md"
        destination.write_text(content, encoding="utf-8")
        written.append(f"✓ .codex/roles/{role}.md")

    return written


def _parse_version_tuple(text: str) -> tuple[int, int, int] | None:
    match = re.search(r"(\d+)\.(\d+)\.(\d+)", text)
    if not match:
        return None
    return tuple(int(part) for part in match.groups())


def _codex_hooks_feature_key() -> str:
    """Return Codex hooks feature key compatible with the installed CLI."""
    try:
        result = sp.run(["codex", "--version"], capture_output=True, text=True, timeout=5)
    except (OSError, sp.SubprocessError):
        return "hooks"
    version = _parse_version_tuple(f"{result.stdout} {result.stderr}")
    if version is not None and version <= (0, 128, 0):
        return "codex_hooks"
    return "hooks"


# ============================================================================
# File Installation System
# ============================================================================

from dataclasses import dataclass

CONFLICT_SKIP = "skip"  # Skip if exists (user files)
CONFLICT_ASK = "ask"    # Ask user on conflict


@dataclass
class _FileTask:
    """Represents a single file to install."""
    src: Path
    dst: Path
    rel_path: str
    onConflict: str          # skip | ask
    has_template: bool     # Has {{var}} to replace

    # Computed at runtime
    exists: bool = False


def _validate_registry_sources(registry: dict, src_root: Path) -> None:
    """Fail before installation when an active registry source is missing."""
    missing: list[str] = []

    for src_path_str, entry in registry.items():
        if src_path_str in ("_comment", "_deprecated"):
            continue
        if not isinstance(entry, dict) or entry.get("moveTo") == "deprecated":
            continue

        source_rel = entry.get("src", src_path_str)
        src_path = src_root / source_rel
        entry_type = entry.get("type")
        source_exists = (
            src_path.is_file()
            if entry_type == "file"
            else src_path.is_dir()
            if entry_type == "dir"
            else src_path.exists()
        )
        if not source_exists:
            missing.append(source_rel)
            continue

        if entry_type != "dir" or "scan" in entry:
            continue
        for file_info in entry.get("content", []):
            filename = (
                file_info.get("file")
                if isinstance(file_info, dict)
                else file_info
            )
            if not filename or not (src_path / filename).is_file():
                missing.append(f"{source_rel}/{filename or '<missing file name>'}")

    if missing:
        details = "\n".join(f"  - {path}" for path in sorted(set(missing)))
        raise FileNotFoundError(f"Active registry sources missing:\n{details}")


def _collect_file_tasks(
    registry: dict,
    src_root: Path,
    project_path: Path,
) -> list[_FileTask]:
    """Collect all file tasks from registry."""
    tasks: list[_FileTask] = []

    for src_path_str, entry in registry.items():
        if src_path_str in ("_comment", "_deprecated"):
            continue
        if entry.get("moveTo") == "deprecated":
            continue

        # Allow "src" override (key can be a unique ID, src is the actual source dir)
        src_path = src_root / entry.get("src", src_path_str)
        if not src_path.exists():
            raise FileNotFoundError(f"Active registry source missing: {src_path}")

        dst_path = project_path / entry["moveTo"]
        entry_type = entry.get("type")

        # Determine strategy at entry level
        entry_onConflict = entry.get("onConflict", CONFLICT_ASK)
        entry_has_template = entry.get("hasTemplate", False)

        if entry_type == "file":
            task = _FileTask(
                src=src_path,
                dst=dst_path,
                rel_path=entry["moveTo"],
                onConflict=entry_onConflict,
                has_template=entry_has_template,
                exists=dst_path.exists(),
            )
            tasks.append(task)

        elif entry_type == "dir":
            dst_path.mkdir(parents=True, exist_ok=True)

            # Build the file list: either dynamic scan via `scan` patterns,
            # or the explicit `content` array. Mutually exclusive.
            if "scan" in entry:
                if "content" in entry:
                    raise ValueError(
                        f"registry entry '{src_path_str}': cannot have both 'scan' and 'content'"
                    )
                patterns = entry["scan"] if isinstance(entry["scan"], list) else [entry["scan"]]
                matched: set[str] = set()
                for pat in patterns:
                    for f in src_path.glob(pat):
                        if f.is_file():
                            matched.add(str(f.relative_to(src_path)))
                file_iter = [{"file": n} for n in sorted(matched)]
            else:
                file_iter = entry.get("content", [])

            for file_info in file_iter:
                if isinstance(file_info, dict):
                    filename = file_info.get("file")
                    # File-level overrides
                    file_onConflict = file_info.get("onConflict", entry_onConflict)
                else:
                    filename = file_info
                    file_onConflict = entry_onConflict

                src_file = src_path / filename
                dst_file = dst_path / filename

                if not src_file.exists():
                    raise FileNotFoundError(
                        f"Active registry source missing: {src_file}"
                    )

                # Multi-segment filenames (e.g. "scripts/Hero.js") need parent dirs created.
                dst_file.parent.mkdir(parents=True, exist_ok=True)

                task = _FileTask(
                    src=src_file,
                    dst=dst_file,
                    rel_path=f"{entry['moveTo']}/{filename}",
                    onConflict=file_onConflict,
                    has_template=entry_has_template,
                    exists=dst_file.exists(),
                )
                tasks.append(task)

    return tasks


def _prepare_content(task: _FileTask,
                     lang_preset: dict, project_name: str, project_root: Path) -> str:
    """Read source file and apply template replacements."""
    content = task.src.read_text(encoding="utf-8")

    if task.has_template:
        content = content.replace("{{language_code}}", lang_preset["code"])
        content = content.replace("{{language_name}}", lang_preset["name"])
        content = content.replace("{{project}}", project_name)
        content = content.replace("{{project_root}}", str(project_root))
        content = content.replace("{{codex_hooks_feature_key}}", _codex_hooks_feature_key())
        if task.src.name == "project.json":
            content = content.replace("{{project_name}}", project_name)

    return content


def _is_text_task(task: _FileTask) -> bool:
    return task.src.suffix.lower() in TEXT_FILE_EXTENSIONS


def _write_file_task(
    task: _FileTask,
    lang_preset: dict,
    project_name: str,
    project_root: Path,
) -> None:
    task.dst.parent.mkdir(parents=True, exist_ok=True)
    if _is_text_task(task):
        content = _prepare_content(task, lang_preset, project_name, project_root)
        task.dst.write_text(content, encoding="utf-8")
    else:
        shutil.copyfile(task.src, task.dst)


def _install_files(
    tasks: list[_FileTask],
    lang_preset: dict,
    project_name: str,
    project_root: Path,
    choice: InitChoice = "ask",
) -> tuple[list[str], list[str]]:
    """
    Install files by onConflict:
    - skip -> auto skip if exists (user config files)
    - ask -> prompt user on conflict (all other files), unless `choice` overrides it

    Returns (written, skipped) lists.
    """
    written: list[str] = []
    skipped: list[str] = []

    # Group by onConflict
    skip_tasks = [t for t in tasks if t.onConflict == CONFLICT_SKIP]
    ask_tasks = [t for t in tasks if t.onConflict == CONFLICT_ASK]

    # --- Batch 1: skip (user config files) ---
    for task in skip_tasks:
        # Special handling for global.json: merge instead of skip
        if task.rel_path == ".vibegame/global.json" and task.dst.exists():
            try:
                existing = json.loads(task.dst.read_text(encoding="utf-8"))
                # Merge new values
                existing["language"] = lang_preset["code"]
                existing["project"] = project_name
                existing["project_root"] = str(project_root)
                existing.pop("user_mode", None)
                existing.pop("team_mode", None)
                existing.pop("developer", None)
                task.dst.write_text(json.dumps(existing, indent=2, ensure_ascii=False), encoding="utf-8")
                written.append(f"✓ {task.rel_path} (merged)")
                continue
            except (json.JSONDecodeError, KeyError):
                pass  # Fall through to normal handling

        if task.dst.exists():
            skipped.append(f"⊙ {task.rel_path} (user file)")
        else:
            _write_file_task(task, lang_preset, project_name, project_root)
            written.append(f"✓ {task.rel_path}")

    # --- Show skip results before asking ---
    if skipped:
        print("\nSkipped user files (auto-protected):")
        for s in skipped:
            print(f"  {s}")

    # --- Batch 2: ask (prompt user on conflict) ---
    ask_results: list[str] = []
    always_action: str | None = None
    for task in ask_tasks:
        if not task.dst.exists():
            _write_file_task(task, lang_preset, project_name, project_root)
            written.append(f"✓ {task.rel_path}")
            ask_results.append(f"✓ {task.rel_path} (created)")
            continue

        # File exists, need to decide
        if choice != "ask":
            action = choice
        elif always_action is not None:
            action = always_action
        else:
            action, is_always = _ask_conflict(task.rel_path)
            if is_always:
                always_action = action

        if action == ACTION_OVERWRITE:
            _write_file_task(task, lang_preset, project_name, project_root)
            written.append(f"✓ {task.rel_path}")
            ask_results.append(f"✓ {task.rel_path} (overwritten)")
        elif action == ACTION_APPEND:
            if not _is_text_task(task):
                skipped.append(f"⊙ {task.rel_path}")
                ask_results.append(f"⊙ {task.rel_path} (binary append unsupported)")
                continue
            content = _prepare_content(task, lang_preset, project_name, project_root)
            existing = task.dst.read_text(encoding="utf-8")
            with open(task.dst, "a", encoding="utf-8") as f:
                if existing and not existing.endswith("\n"):
                    f.write("\n")
                f.write(content)
            written.append(f"✓ {task.rel_path}")
            ask_results.append(f"✓ {task.rel_path} (appended)")
        else:  # skip
            skipped.append(f"⊙ {task.rel_path}")
            ask_results.append(f"⊙ {task.rel_path} (skipped)")

    # --- Show ask results ---
    if ask_results:
        print("\nConflict resolution:")
        for r in ask_results:
            print(f"  {r}")

    return written, skipped


def _install_engine(src_root: Path, project_path: Path) -> list[str]:
    """Install engine code to project directory. Returns description lines."""
    engine_src = src_root / "engine"
    engine_dst = project_path / "engine"
    results: list[str] = []

    if not engine_src.is_dir():
        return [f"engine source not found: {engine_src}"]

    if engine_dst.is_symlink():
        engine_dst.unlink()
    elif engine_dst.is_dir():
        shutil.rmtree(engine_dst)
    shutil.copytree(
        engine_src, engine_dst,
        ignore=shutil.ignore_patterns("*.pyc", "__pycache__", ".DS_Store"),
    )
    results.append("✓ engine/ (copied)")

    return results


def _append_gitignore(project_path: Path):
    """Append vibegame-specific entries to .gitignore."""
    entries = [
        "/.env",
        "/.vibegame/settings.json",
        "/.vibegame/tasks/",
        "/.vibegame/dashboard/",
        "/.vibegame/team/pids/",
        "/assets/",
        "/skeletons/",
        "tests/**/evidence/",
        "**/node_modules/",
        "**/__pycache__/",
        "logs/",
    ]
    gitignore = project_path / ".gitignore"
    existing = gitignore.read_text(encoding="utf-8") if gitignore.exists() else ""
    existing_lines = set(line.strip() for line in existing.splitlines())
    lines_to_add = [e for e in entries if e not in existing_lines]
    if lines_to_add:
        with open(gitignore, "a", encoding="utf-8") as f:
            if existing and not existing.endswith("\n"):
                f.write("\n")
            f.write("# vibegame\n")
            for line in lines_to_add:
                f.write(line + "\n")



def _git_commit_init(project_path: Path) -> None:
    """Ensure git repo exists and commit vibegame init files so worktrees inherit them."""
    import subprocess as sp

    git_dir = project_path / ".git"
    if not git_dir.exists():
        sp.run(["git", "init"], cwd=project_path, capture_output=True)
        print("git init: repo created")

    # Unstage any previously staged files to avoid polluting our commit
    sp.run(["git", "reset", "HEAD"], cwd=project_path, capture_output=True)

    # Stage framework files plus the runnable baseline required in worktrees.
    for target in [
        ".vibegame",
        ".claude",
        ".codex",
        ".gitignore",
        "CLAUDE.md",
        "AGENTS.md",
        "project.json",
        "index.html",
        "scenes/main.scene.json",
        "config/input-map.json",
        "engine",
        "modules",
    ]:
        path = project_path / target
        if path.exists():
            sp.run(["git", "add", target], cwd=project_path, capture_output=True)

    # Check if there's anything to commit
    ret = sp.run(["git", "diff", "--cached", "--quiet"], cwd=project_path, capture_output=True)
    if ret.returncode != 0:
        commit = sp.run(
            ["git", "commit", "-m", "chore: vibegame init"],
            cwd=project_path, capture_output=True, text=True,
        )
        if commit.returncode != 0:
            # Task worktrees branch from this commit. Without it the repo has no
            # HEAD, `git worktree add` checks out an empty tree, and task agents
            # run without .vibegame/hooks/ -- so they never register and the
            # failure only surfaces hours later as a missing agent. Report it
            # here, while it is still one command away from being fixed.
            detail = (commit.stderr or commit.stdout).strip().splitlines()
            print("git: commit FAILED — task worktrees will be empty until this is fixed")
            for line in detail[:4]:
                print(f"  {line}")
        else:
            print("git: committed vibegame init files")


LANGUAGE_PRESETS: dict[str, dict[str, str]] = {
    "en": {"code": "en", "name": "English"},
    "zh-CN": {"code": "zh-CN", "name": "Chinese"},
    "ja": {"code": "ja", "name": "Japanese"},
    "ko": {"code": "ko", "name": "Korean"},
    "es": {"code": "es", "name": "Spanish"},
    "fr": {"code": "fr", "name": "French"},
    "de": {"code": "de", "name": "German"},
    "pt": {"code": "pt", "name": "Portuguese"},
    "ru": {"code": "ru", "name": "Russian"},
    "ar": {"code": "ar", "name": "Arabic"},
}


@app.command("init")
def init(
    path: str = typer.Argument(default=".", help="Project path (default: current dir)"),
    lang: str | None = typer.Option(None, "--lang", help="Language: zh-CN / en"),
    engine: bool = typer.Option(True, "--engine/--no-engine", "-e", help="Copy engine code to project dir (default: yes)"),
    choice: InitChoice = typer.Option(
        "ask",
        "--choice",
        help="Conflict handling for prompted files: ask, skip, or overwrite (default: ask)",
    ),
    no_commit: bool = typer.Option(
        False,
        "--no-commit",
        help="Skip the final 'chore: vibegame init' git commit (and the staging that prepares it)",
    ),
):
    """Initialize vibegame game project structure"""
    if lang is not None and lang not in LANGUAGE_PRESETS:
        print(f"--lang must be one of: {', '.join(LANGUAGE_PRESETS)}")
        raise typer.Exit(1)

    try:
        project_path = Path(path).resolve()
        if not project_path.exists():
            print(f"Error: Path not found: {project_path}")
            raise typer.Exit(1)
        if not project_path.is_dir():
            print(f"Error: Not a directory: {project_path}")
            raise typer.Exit(1)

        # src/.claude and src/.vibegame are the template sources
        src_root = Path(__file__).parent.parent  # src/
        claude_tpl = src_root / ".claude"
        vibegame_tpl = src_root / ".vibegame"

        for tpl, name in [(claude_tpl, "src/.claude"), (vibegame_tpl, "src/.vibegame")]:
            if not tpl.exists():
                print(f"Error: Template dir not found: {tpl} ({name})")
                raise typer.Exit(1)

        # Read defaults from setup wizard (src/.vibegame/defaults.json)
        defaults_path = src_root / ".vibegame" / "defaults.json"
        repo_defaults: dict = {}
        if defaults_path.exists():
            try:
                repo_defaults = json.loads(defaults_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass

        # Ask language if not specified via CLI or defaults
        if lang is None and "language" in repo_defaults:
            lang = repo_defaults["language"]
        if lang is None:
            lang = questionary.select(
                "Select language:",
                choices=[
                    questionary.Choice("English", value="en"),
                    questionary.Choice("Chinese", value="zh-CN"),
                    questionary.Choice("Japanese", value="ja"),
                    questionary.Choice("Korean", value="ko"),
                    questionary.Choice("Spanish", value="es"),
                    questionary.Choice("French", value="fr"),
                    questionary.Choice("German", value="de"),
                    questionary.Choice("Portuguese", value="pt"),
                    questionary.Choice("Russian", value="ru"),
                    questionary.Choice("Arabic", value="ar"),
                ],
            ).ask()
            if lang is None:
                raise typer.Exit(0)

        lang_preset = LANGUAGE_PRESETS[lang]

        # Load registry
        registry_path = src_root.parent / "config" / "registry.json"
        if not registry_path.exists():
            print(f"Error: registry.json not found: {registry_path}")
            raise typer.Exit(1)
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
        _validate_registry_sources(registry, src_root)

        # Process deprecated entries: remove stale files from project
        for src_path_str, entry in registry.items():
            if src_path_str == "_comment":
                continue
            if not isinstance(entry, dict) or entry.get("moveTo") != "deprecated":
                continue
            target = project_path / src_path_str
            if target.exists() or target.is_symlink():
                target.unlink()
                print(f"Removed deprecated file: {src_path_str}")

        # === Unified installation (copy-only mode) ===
        project_name = project_path.name

        # Collect all file tasks from registry
        tasks = _collect_file_tasks(registry, src_root, project_path)

        # Install files by onConflict order (always -> once -> ask)
        written, skipped = _install_files(
            tasks, lang_preset, project_name, project_path, choice
        )

        # Create required directories
        for extra_dir in ["assets/artifacts", "assets/concepts", "config", ".vibegame/tasks", "scenes", "tests/bot"]:
            (project_path / extra_dir).mkdir(parents=True, exist_ok=True)

        # Install engine if requested
        engine_results: list[str] = []
        if engine:
            engine_results = _install_engine(src_root, project_path)

        # Copy .env from git root (setup wizard is the only entry point)
        git_root_env = src_root.parent / ".env"
        project_env_path = project_path / ".env"
        if not project_env_path.exists() and git_root_env.exists():
            shutil.copy(git_root_env, project_env_path)
            written.append(".env (from git root)")

        _append_gitignore(project_path)
        written.extend(_generate_codex_roles(project_path))

        # Build summary
        skip_note = f"\nSkipped: {len(skipped)}" if skipped else ""
        summary = f"Copied: {len(written)}{skip_note}\n"
        if written:
            summary += "\nCopied files:\n" + "\n".join(f"  {w}" for w in written)
        if engine_results:
            summary += "\n\nEngine:\n" + "\n".join(f"  {r}" for r in engine_results)

        launch_hint = "vibegame start"
        print("=== Vibegame Init Success ===")
        print(f"  Game project initialized (copy mode)\n")
        print(f"  Project path: {project_path}")
        print(f"  Language: {lang}\n")
        print(f"  {summary}\n")
        print(f"  Start session: {launch_hint}")
        print(f"  Suggested first message: use the `vibegame-start` skill")
        if no_commit:
            print("git: skipped vibegame init commit (--no-commit)")
        else:
            _git_commit_init(project_path)

    except Exception as e:
        print(f"Error: {e}")
        raise typer.Exit(1)


@app.command("check", context_settings={"allow_extra_args": True, "ignore_unknown_options": True})
def check(
    ctx: typer.Context,
    path: str = typer.Argument(default=".", help="Game project path or .node.json file"),
    api: bool = typer.Option(False, "--api", help="Also run paid VLM and image generation API smoke checks"),
):
    """Validate game project or a specific .node.json (static check, no engine needed)

    When path is a .node.json file: runs module-specific check + visual preview.
    Extra args are parsed as --key=value and passed to the module check function.

    Examples:
      vibegame check                              # check whole project
      vibegame check examples/sekiro-module       # check whole project
      vibegame check --api                        # static check + paid API smoke checks
      vibegame check entities/wolf.node.json      # check single node
      vibegame check entities/wolf.node.json --scale=0.5 --states=attack1,attack2
    """
    target = Path(path).resolve()

    if target.name.endswith(".node.json") and target.is_file():
        if api:
            raise typer.BadParameter("--api is only supported for project checks")
        _check_node_file(target, ctx.args)
        return

    # Project --help
    if "--help" in ctx.args:
        print("Project check\n\nUsage: vibegame check [PROJECT] [--api]\nValidates project.json, scenes, manifests, scripts, input-map. --api also runs paid VLM and image generation smoke checks.")
        return

    from cli.check import check_project, print_report
    project_path = target
    if not (project_path / "project.json").exists():
        print(f"Error: {project_path} is not a game project (no project.json)")
        raise typer.Exit(1)

    print(f"Checking {project_path} ...")
    issues = check_project(project_path)
    exit_code = print_report(issues)
    if api:
        from cli.api_check import print_api_smoke_report, run_api_smoke_checks

        api_exit_code = print_api_smoke_report(run_api_smoke_checks(project_path))
        exit_code = max(exit_code, api_exit_code)
    raise typer.Exit(exit_code)


def _check_node_file(node_path: Path, extra_args: list[str]):
    """Check a single .node.json file. Module .check.py overrides generic logic."""
    import importlib.util
    import json as _json

    node = _json.loads(node_path.read_text())
    script = node.get("script", "")

    # Find project root (walk up to project.json). Resolve first: on a relative
    # path `Path('.').parent` is `.` again, so the walk would never terminate.
    project = node_path.resolve().parent
    while project != project.parent:
        if (project / "project.json").exists():
            break
        project = project.parent
    else:
        print("Could not find project.json in parent directories")
        raise typer.Exit(1)

    opts = _parse_extra_args(extra_args)

    # --info: show context-specific usage (--help is intercepted by typer)
    if opts.get("info"):
        _show_node_help(script, project)
        return

    # Try module-specific check (overrides generic)
    if script.endswith("Module"):
        check_file = project / "modules" / "check" / f"{script}.check.py"
        if check_file.exists():
            spec = importlib.util.spec_from_file_location(f"{script}_check", check_file)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            check_fn = getattr(mod, "check", None)
            if check_fn:
                print(f"Checking {node_path.relative_to(project)} ({script}) ...")
                msgs = check_fn(project, node_path, opts)
                _print_check_msgs(msgs)
                return

    # Generic node check
    print(f"Checking {node_path.relative_to(project)} ...")
    if opts.get("anim"):
        from cli.node_check import check_node_anim
        msgs = check_node_anim(project, node_path, opts)
    else:
        from cli.node_check import check_node_generic
        msgs = check_node_generic(project, node_path, opts)
    _print_check_msgs(msgs)


def _show_node_help(script: str, project: Path):
    """Show help based on node type."""
    import importlib.util

    # Try module USAGE
    if script.endswith("Module"):
        check_file = project / "modules" / "check" / f"{script}.check.py"
        if check_file.exists():
            spec = importlib.util.spec_from_file_location(f"{script}_help", check_file)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            usage = getattr(mod, "USAGE", None)
            if usage:
                print(usage)
                return

    # Generic USAGE
    from cli.node_check import USAGE
    print(USAGE)


def _parse_extra_args(extra_args: list[str]) -> dict:
    opts = {}
    i = 0
    while i < len(extra_args):
        arg = extra_args[i]
        if arg.startswith("--"):
            key = arg[2:]
            if "=" in key:
                k, v = key.split("=", 1)
                opts[k] = _parse_arg_value(v)
            elif i + 1 < len(extra_args) and not extra_args[i + 1].startswith("--"):
                opts[key] = _parse_arg_value(extra_args[i + 1])
                i += 1
            else:
                opts[key] = True
        elif arg == "-o" and i + 1 < len(extra_args):
            opts["o"] = extra_args[i + 1]
            i += 1
        i += 1
    return opts


def _print_check_msgs(msgs: list[str]):
    has_error = False
    for m in msgs:
        if m.startswith("ERROR"):
            print(f"  [ERROR] {m[7:]}")
            has_error = True
        elif m.startswith("WARN"):
            print(f"  [WARN]  {m[6:]}")
        elif m.startswith("PREVIEW"):
            print(f"  {m}")
        elif m.startswith("PASS"):
            print(f"  {m}")
    if has_error:
        raise typer.Exit(1)


def _parse_arg_value(v: str):
    if v.lower() in ("true", "yes"):
        return True
    if v.lower() in ("false", "no"):
        return False
    if "," in v:
        return [s.strip() for s in v.split(",")]
    try:
        return float(v) if "." in v else int(v)
    except ValueError:
        return v


# Register external command modules
from cli.release import register as _register_release
_register_release(app)


@app.command("status")
def status(
    path: str = typer.Argument(default=".", help="Game project path (default: current dir)"),
):
    """Show current game project status"""
    import subprocess as sp

    project_path = Path(path).resolve()
    vibegame_dir = project_path / ".vibegame"

    if not vibegame_dir.exists():
        print("Error: not a vibegame project (.vibegame/ not found)")
        raise typer.Exit(1)

    # goal.md
    goal_title = ""
    goal_file = vibegame_dir / "goal.md"
    if goal_file.exists():
        for line in goal_file.read_text().splitlines():
            if line.startswith("# "):
                goal_title = line[2:]
                break

    # tasks
    active_tasks: list[str] = []
    try:
        tasks = json.loads(f"[{','.join((vibegame_dir / 'tasks' / 'tasks.jsonl').read_text().splitlines())}]")
        active_tasks = [
            t["name"]
            for t in tasks
            if t.get("status") not in ("done", "decomposed", "archived")
        ]
    except Exception:
        pass

    # git info
    git_info = "unavailable"
    try:
        branch = sp.run(["git", "branch", "--show-current"], capture_output=True, text=True, cwd=project_path).stdout.strip()
        dirty = sp.run(["git", "status", "--porcelain"], capture_output=True, text=True, cwd=project_path).stdout.strip()
        count = len([l for l in dirty.splitlines() if l.strip()]) if dirty else 0
        git_info = f"{branch} | {count} uncommitted" if branch else "not a git repo"
    except Exception:
        pass

    lines = [
        f"Project:    {project_path.name}",
    ]
    if goal_title:
        lines.append(f"Goal:       {goal_title}")
    if active_tasks:
        preview = ", ".join(active_tasks[:3])
        if len(active_tasks) > 3:
            preview += f" (+{len(active_tasks) - 3})"
        lines.append(f"Active:     {preview}")
    lines.append(f"Git:        {git_info}")

    print("=== Vibegame Status ===")
    for line in lines:
        print(f"  {line}")


def _find_repo_root(path: Path) -> Path | None:
    current = path.resolve()
    while True:
        if (current / "pyproject.toml").exists():
            return current
        parent = current.parent
        if parent == current:
            return None
        current = parent


def _install_codex_hooks_or_exit() -> None:
    from cli.codex_hooks import install_global_codex_hooks

    try:
        result = install_global_codex_hooks()
    except Exception as exc:
        print(f"Failed to install Codex hooks: {exc}")
        raise typer.Exit(1) from exc

    action = "updated" if result.changed else "already up to date"
    print(f"Codex hooks: {action} ({result.path})")


@app.command("setup")
def setup(
    repo_root: str = typer.Argument(default=".", help="Repo root directory, or 'codex-hooks'"),
):
    """Interactive setup wizard for AI providers and project defaults"""
    if repo_root == "codex-hooks":
        _install_codex_hooks_or_exit()
        return

    from cli.setup import run_wizard

    root = _find_repo_root(Path(repo_root))
    if root is None:
        print(f"Cannot find repo root (no pyproject.toml from {Path(repo_root).resolve()})")
        raise typer.Exit(1)

    run_wizard(root)


def main():
    """CLI entry point"""
    app()


if __name__ == "__main__":
    main()
