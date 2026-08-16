"""Install Vibegame Codex global hooks."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class CodexHookSpec:
    event: str
    filename: str
    args: tuple[str, ...] = ()
    matcher: str | None = None
    timeout: int = 5
    status_message: str | None = None
    identity_args: tuple[tuple[str, str], ...] = ()
    legacy_without_identity_args: bool = False


@dataclass(frozen=True)
class CodexHooksInstallResult:
    path: Path
    changed: bool
    managed_hooks: int
    removed_hooks: int


VIBEGAME_CODEX_HOOK_SPECS: tuple[CodexHookSpec, ...] = (
    CodexHookSpec(
        event="SessionStart",
        filename="session-start.py",
        args=("--source-app", "codex"),
        matcher="startup|resume",
        timeout=10,
        status_message="Vibegame session setup",
        identity_args=(("--source-app", "codex"),),
        legacy_without_identity_args=True,
    ),
    CodexHookSpec(
        event="SessionStart",
        filename="web_hook.py",
        args=("--source-app", "codex", "--event-type", "SessionStart"),
        matcher="startup|resume",
        timeout=5,
        status_message="Vibegame dashboard sync",
        identity_args=(("--source-app", "codex"), ("--event-type", "SessionStart")),
    ),
    CodexHookSpec(
        event="PreToolUse",
        filename="web_hook.py",
        args=("--source-app", "codex", "--event-type", "PreToolUse"),
        timeout=5,
        status_message="Vibegame dashboard sync",
        identity_args=(("--source-app", "codex"), ("--event-type", "PreToolUse")),
    ),
    CodexHookSpec(
        event="UserPromptSubmit",
        filename="goal-capture.py",
        args=("--source-app", "codex"),
        timeout=5,
        status_message="Vibegame goal capture",
        identity_args=(("--source-app", "codex"),),
    ),
    CodexHookSpec(
        event="UserPromptSubmit",
        filename="user-prompt-submit.py",
        args=("--source-app", "codex"),
        timeout=5,
        status_message="Vibegame prompt tracking",
        identity_args=(("--source-app", "codex"),),
        legacy_without_identity_args=True,
    ),
    CodexHookSpec(
        event="UserPromptSubmit",
        filename="web_hook.py",
        args=("--source-app", "codex", "--event-type", "UserPromptSubmit"),
        timeout=5,
        status_message="Vibegame dashboard sync",
        identity_args=(("--source-app", "codex"), ("--event-type", "UserPromptSubmit")),
    ),
    CodexHookSpec(
        event="Stop",
        filename="agent-team-stop.py",
        args=("--source-app", "codex"),
        timeout=360,
        status_message="Vibegame stop gate",
        identity_args=(("--source-app", "codex"),),
    ),
)


def default_codex_hooks_path() -> Path:
    return Path.home() / ".codex" / "hooks.json"


def _arg_pattern(name: str, value: str) -> re.Pattern[str]:
    escaped_name = re.escape(name)
    escaped_value = re.escape(value)
    return re.compile(
        rf"(?:^|[\s;]){escaped_name}(?:=|\s+)(['\"]?){escaped_value}\1(?=$|[\s;])"
    )


def _command_has_arg(command: str, name: str, value: str) -> bool:
    return bool(_arg_pattern(name, value).search(command))


def _command_has_option(command: str, name: str) -> bool:
    return bool(re.search(rf"(?:^|[\s;]){re.escape(name)}(?:=|\s|$)", command))


def _is_vibegame_codex_hook(item: Any, spec: CodexHookSpec) -> bool:
    if not isinstance(item, dict):
        return False
    if item.get("type") != "command":
        return False
    command = item.get("command")
    if not isinstance(command, str):
        return False
    if f".vibegame/hooks/{spec.filename}" not in command:
        return False
    if all(_command_has_arg(command, name, value) for name, value in spec.identity_args):
        return True
    if spec.legacy_without_identity_args and not (
        _command_has_option(command, "--source-app") or _command_has_option(command, "--event-type")
    ):
        return True
    return False


def _build_command(spec: CodexHookSpec) -> str:
    args = f" {' '.join(spec.args)}" if spec.args else ""
    return (
        'root="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"; '
        f'hook="$root/.vibegame/hooks/{spec.filename}"; '
        f'if test -f "$hook"; then python3 "$hook"{args}; fi'
    )


def _build_hook_item(spec: CodexHookSpec) -> dict[str, Any]:
    item: dict[str, Any] = {
        "type": "command",
        "command": _build_command(spec),
        "timeout": spec.timeout,
    }
    if spec.status_message:
        item["statusMessage"] = spec.status_message
    return item


def _build_hook_group(specs: list[CodexHookSpec]) -> dict[str, Any]:
    group: dict[str, Any] = {"hooks": [_build_hook_item(spec) for spec in specs]}
    matcher = specs[0].matcher
    if matcher is not None:
        group["matcher"] = matcher
    return group


def _load_hooks_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"hooks": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    hooks = data.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        raise ValueError(f"{path} field 'hooks' must be a JSON object")
    return data


def _event_specs() -> dict[str, list[CodexHookSpec]]:
    grouped: dict[str, list[CodexHookSpec]] = {}
    for spec in VIBEGAME_CODEX_HOOK_SPECS:
        grouped.setdefault(spec.event, []).append(spec)
    return grouped


def build_codex_hooks_config(existing: dict[str, Any]) -> tuple[dict[str, Any], int]:
    """Return config with exactly one managed Vibegame group per event."""
    data = json.loads(json.dumps(existing))
    hooks = data.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        raise ValueError("field 'hooks' must be a JSON object")

    removed = 0
    for event, specs in _event_specs().items():
        raw_groups = hooks.get(event, [])
        if raw_groups is None:
            raw_groups = []
        if not isinstance(raw_groups, list):
            raise ValueError(f"hooks.{event} must be a list")

        kept_groups: list[Any] = []
        for group in raw_groups:
            if not isinstance(group, dict):
                kept_groups.append(group)
                continue
            raw_items = group.get("hooks", [])
            if not isinstance(raw_items, list):
                kept_groups.append(group)
                continue

            kept_items = []
            for item in raw_items:
                if any(_is_vibegame_codex_hook(item, spec) for spec in specs):
                    removed += 1
                else:
                    kept_items.append(item)

            extra_group_keys = set(group) - {"hooks", "matcher"}
            if kept_items or extra_group_keys:
                new_group = dict(group)
                new_group["hooks"] = kept_items
                kept_groups.append(new_group)

        kept_groups.append(_build_hook_group(specs))
        hooks[event] = kept_groups

    return data, removed


def install_global_codex_hooks(path: Path | None = None) -> CodexHooksInstallResult:
    """Write ~/.codex/hooks.json with idempotent Vibegame project-local hooks."""
    hooks_path = path or default_codex_hooks_path()
    hooks_path = hooks_path.expanduser()
    existing = _load_hooks_config(hooks_path)
    updated, removed = build_codex_hooks_config(existing)
    changed = updated != existing
    if changed:
        hooks_path.parent.mkdir(parents=True, exist_ok=True)
        hooks_path.write_text(json.dumps(updated, indent=2) + "\n", encoding="utf-8")
    return CodexHooksInstallResult(
        path=hooks_path,
        changed=changed,
        managed_hooks=len(VIBEGAME_CODEX_HOOK_SPECS),
        removed_hooks=removed,
    )
