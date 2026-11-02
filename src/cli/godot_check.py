"""Static and parse checks for VibeGame Godot projects."""

from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class GodotIssue:
    level: str  # "error" or "warning"
    file: str
    message: str

    def __str__(self) -> str:
        tag = "ERROR" if self.level == "error" else "WARN"
        return f"  [{tag}] {self.file}: {self.message}"


def _error(file: str, message: str) -> GodotIssue:
    return GodotIssue("error", file, message)


def _warning(file: str, message: str) -> GodotIssue:
    return GodotIssue("warning", file, message)


def _load_project_json(project: Path) -> tuple[dict | None, list[GodotIssue]]:
    path = project / "project.json"
    if not path.is_file():
        return None, [_error("project.json", "file not found")]
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return None, [_error("project.json", f"invalid JSON: {exc}")]
    if not isinstance(data, dict):
        return None, [_error("project.json", "top-level value must be an object")]
    return data, []


def _res_path(project: Path, value: str) -> Path:
    relative = value.removeprefix("res://")
    return project / relative


def _parse_error_lines(output: str) -> list[str]:
    """Extract the useful error line from Godot's compiler output."""
    found: list[str] = []
    for line in output.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if (
            "SCRIPT ERROR" in stripped
            or "Parse Error" in stripped
            or "Failed to load script" in stripped
        ):
            found.append(stripped[:300])
    return found


def check_godot_project(
    project: Path,
    *,
    godot_bin: str | None = None,
    boot_check: bool = True,
) -> list[GodotIssue]:
    """Validate a Godot project without launching a visible window."""
    project = project.resolve()
    issues: list[GodotIssue] = []
    data, load_issues = _load_project_json(project)
    issues.extend(load_issues)
    if data is None:
        return issues

    engine = data.get("engine")
    if not isinstance(engine, str) or not engine.startswith("godot@"):
        issues.append(
            _error(
                "project.json",
                f'engine must be "godot@<version>", got {engine!r}',
            )
        )

    settings = data.get("settings", {})
    if not isinstance(settings, dict):
        issues.append(_error("project.json", "settings must be an object"))
    else:
        for key in ("width", "height"):
            value = settings.get(key)
            if not isinstance(value, int) or value <= 0:
                issues.append(_error("project.json", f"settings.{key} must be a positive integer"))

    project_godot = project / "project.godot"
    project_text = ""
    if not project_godot.is_file():
        issues.append(_error("project.godot", "file not found"))
    else:
        try:
            project_text = project_godot.read_text(encoding="utf-8")
        except OSError as exc:
            issues.append(_error("project.godot", f"cannot read: {exc}"))
        if "config_version=5" not in project_text:
            issues.append(_error("project.godot", "expected config_version=5 (Godot 4 project)"))
        run_main = re.search(r'^run/main_scene\s*=\s*"([^"]+)"', project_text, re.MULTILINE)
        if not run_main:
            issues.append(_error("project.godot", "missing run/main_scene"))
        else:
            main_scene = _res_path(project, run_main.group(1))
            if not main_scene.is_file():
                issues.append(
                    _error("project.godot", f"run/main_scene points at a missing file: {run_main.group(1)}")
                )
        start_scene = data.get("startScene")
        if isinstance(start_scene, str) and start_scene:
            scene_path = _res_path(project, start_scene)
            if not scene_path.is_file():
                issues.append(
                    _error("project.json", f"startScene points at a missing file: {start_scene}")
                )
            elif run_main and _res_path(project, run_main.group(1)).resolve() != scene_path.resolve():
                issues.append(
                    _warning(
                        "project.json",
                        "startScene and project.godot run/main_scene differ; the engine uses project.godot",
                    )
                )

    bridge_file = project / "addons" / "vibegame_bridge" / "bridge.gd"
    if not bridge_file.is_file():
        issues.append(
            _error(
                "addons/vibegame_bridge/bridge.gd",
                "runtime bridge missing; `vibegame play` will not work",
            )
        )
    if "VibeGameBridge" not in project_text:
        issues.append(
            _error(
                "project.godot",
                'missing autoload: VibeGameBridge="*res://addons/vibegame_bridge/bridge.gd"',
            )
        )

    scripts = sorted(
        path
        for path in project.rglob("*.gd")
        if ".godot" not in path.parts and not any(part.startswith(".") for part in path.relative_to(project).parts)
    )
    if not scripts:
        issues.append(_warning("scripts/", "no .gd scripts found"))

    if godot_bin is None:
        issues.append(
            _warning(
                "godot",
                "Godot binary not found; skipped GDScript parse and headless boot checks",
            )
        )
        return issues

    def add_parse_issues(relative: str, output: str) -> None:
        for line in _parse_error_lines(output):
            issues.append(_error(relative, line))

    # `--check-only --script` parses a script without the project's autoloads,
    # so any script using an autoload reports a false "Identifier not found".
    # The headless boot below compiles scripts in the real project context
    # instead, autoloads included.

    if boot_check:
        env = dict(os.environ)
        env["VIBEGAME_GODOT_BRIDGE_DISABLE"] = "1"
        try:
            result = subprocess.run(
                [
                    godot_bin,
                    "--headless",
                    "--path",
                    str(project),
                    "--quit-after",
                    "3",
                ],
                capture_output=True,
                text=True,
                timeout=60,
                env=env,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            issues.append(_warning("boot", f"headless boot did not complete: {exc}"))
        else:
            add_parse_issues("boot", (result.stdout or "") + (result.stderr or ""))
            if result.returncode != 0:
                detail = (result.stderr or result.stdout or "").strip().splitlines()
                issues.append(
                    _warning(
                        "boot",
                        f"headless boot exited {result.returncode}"
                        + (f": {detail[-1][:300]}" if detail else ""),
                    )
                )

    return issues
