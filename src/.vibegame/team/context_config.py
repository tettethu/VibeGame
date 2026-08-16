"""Load teammate context configuration and build teammate launch context."""

from __future__ import annotations

import os
import json
from datetime import datetime
from pathlib import Path


SPRINT_AGENTS = ("architect", "programmer", "auditor", "player")
DOWNSTREAM_AGENTS = ("programmer", "auditor", "player")  # consume per-task context.json
NON_SPRINT_AGENTS = ("designer", "artist", "reviewer")  # source-only inject_config


def _candidate_paths() -> list[Path]:
    here = Path(__file__).resolve()
    return [
        here.parent.parent / "config" / "context.json",
        here.parents[3] / "config" / "context.json",
    ]


def load_context_config() -> dict:
    for path in _candidate_paths():
        if not path.is_file():
            continue
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
    return {}


_CONFIG = load_context_config()

INJECT_CONFIG: dict[str, list[dict]] = _CONFIG.get("inject_config", {})
DEFAULT_CONFIG: dict[str, list[dict]] = _CONFIG.get("default_config", {})
REQUIRE_TASK_DIR = set(_CONFIG.get("require_task_dir", []))
TASK_AGENT_PREFIXES: dict[str, str] = _CONFIG.get("task_agent_prefixes", {})
ROLE_PREFIXES = [
    (entry.get("prefix", ""), entry.get("agent_type", ""))
    for entry in _CONFIG.get("role_prefixes", [])
    if entry.get("prefix") and entry.get("agent_type")
]
AGENTS_SUPPORTED = tuple(set(INJECT_CONFIG.keys()) | set(SPRINT_AGENTS))

VIBEGAME_DIR = ".vibegame"


def format_file_ref(file_path: str, reason: str = "") -> str:
    if reason:
        return f"@{file_path} : {reason}"
    return f"@{file_path}"


def format_bullet_lines(lines: list[str]) -> str:
    return "\n".join(f"- {line}" for line in lines if line)


def compose_prompt(
    context_text: str | None = None,
    workspace_text: str | None = None,
    workflow_text: str | None = None,
    task_text: str | None = None,
) -> str:
    parts: list[str] = []

    if context_text:
        parts.append("Read these files as your basic context:")
        parts.append(context_text)
        parts.append("")

    bullet_blocks = [block for block in (workflow_text, workspace_text) if block]
    if bullet_blocks:
        parts.append("\n".join(bullet_blocks))
        parts.append("")

    if task_text:
        parts.append("Instruction from the team lead:")
        parts.append(task_text)

    return "\n".join(parts).strip()


def _resolve_file(file_path: str, content_root: str, task_dir: str | None) -> tuple[str, str] | None:
    """Resolve a file path. Try task_dir first, then workspace root. Returns (full_path, display_path) or None."""
    if not file_path:
        return None
    if os.path.isabs(file_path):
        return (file_path, file_path) if os.path.isfile(file_path) else None
    if task_dir:
        task_candidate = os.path.join(task_dir, file_path)
        if os.path.isfile(task_candidate):
            return (task_candidate, task_candidate)
    ws_candidate = os.path.join(content_root, file_path)
    if os.path.isfile(ws_candidate):
        return (ws_candidate, file_path)
    return None


def inject_entry(entry: dict, content_root: str, repo_root: str, task_dir: str | None) -> str:
    file_path = entry.get("file", "")
    if not file_path:
        return ""
    # Project-level jsonl auto-expansion: a .jsonl entry referenced from source defaults
    # gets each of its rows inlined as a separate file reference (preserves the legacy
    # designer/design.jsonl pattern without needing a source field).
    if file_path.endswith(".jsonl") and not task_dir:
        return inject_project_jsonl(entry, repo_root)
    resolved = _resolve_file(file_path, content_root, task_dir)
    if resolved is None:
        return ""
    full_path, display_path = resolved
    return format_file_ref(display_path, entry.get("reason", ""))


def inject_project_jsonl(entry: dict, repo_root: str) -> str:
    jsonl_path = os.path.join(repo_root, entry["file"])
    if not os.path.isfile(jsonl_path):
        return ""
    parts = []
    try:
        with open(jsonl_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                item = json.loads(line)
                spec_path = item.get("file", "")
                if not spec_path:
                    continue
                full_path = os.path.join(repo_root, spec_path)
                if os.path.isfile(full_path):
                    parts.append(format_file_ref(spec_path, item.get("reason", "")))
    except Exception:
        pass
    return "\n".join(parts)


def load_task_context(task_dir: str) -> dict:
    """Read <task_dir>/context.json. Returns empty dict if missing."""
    path = os.path.join(task_dir, "context.json")
    if not os.path.isfile(path):
        return {}
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def get_inject_entries(agent_type: str, task_dir: str | None) -> list[dict]:
    """Return the ordered list of {file, reason} entries to inject for the given agent.

    Resolution rules:
      - inject_config agents (designer/artist/reviewer): source inject_config[agent]
      - architect: source default_config.architect (architect is the AUTHOR of per-task
        context.json, not a consumer of it)
      - downstream sprint agents (programmer/auditor/player): per-task context.json's
        inject_config.all + inject_config.<agent>
    """
    if agent_type in INJECT_CONFIG:
        return list(INJECT_CONFIG[agent_type])
    if agent_type == "architect":
        return list(DEFAULT_CONFIG.get("architect", []))
    if agent_type in DOWNSTREAM_AGENTS:
        if not task_dir:
            return []
        task_ctx = load_task_context(task_dir)
        ic = task_ctx.get("inject_config", {})
        return list(ic.get("all", [])) + list(ic.get(agent_type, []))
    return []


def read_tasks(repo_root: str) -> list[dict]:
    tasks_path = os.path.join(repo_root, VIBEGAME_DIR, "tasks", "tasks.jsonl")
    if not os.path.isfile(tasks_path):
        return []
    tasks: list[dict] = []
    try:
        with open(tasks_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    tasks.append(json.loads(line))
    except Exception:
        return []
    return tasks


def find_task(tasks: list[dict], task_name: str) -> dict | None:
    for task in tasks:
        if task.get("name") == task_name:
            return task
    return None


def get_workspace_root(repo_root: str, task: dict | None) -> str:
    if not task:
        return repo_root
    worktree_rel = task.get("worktree")
    if isinstance(worktree_rel, str) and worktree_rel:
        return os.path.join(repo_root, worktree_rel)
    return repo_root


def build_workspace_lines(agent_type: str, repo_root: str, task: dict | None, task_dir: str | None) -> list[str]:
    workspace_root = get_workspace_root(repo_root, task)
    task_dir_display = task_dir or "(missing task dir)"

    role_rules = {
        "architect": "Must do codebase research, spec/doc updates, and task document edits in the worktree.",
        "programmer": "Must do all code changes, related doc/spec edits, checks, and tests in the worktree.",
        "auditor": "Must do review, fixes, validation, and tests in the worktree.",
        "player": "Must do visual verification in the worktree.",
    }
    role_rule = role_rules.get(agent_type, "Must do all task work in the worktree.")

    lines = [f"Workspace root: `{workspace_root}`"]

    if task:
        lines.append(f"Task dir: `{task_dir_display}`")

    if task and task.get("worktree"):
        lines.append(role_rule)
        lines.append(f"For Bash, always start with: `cd '{workspace_root}' && <command>`")
    elif task:
        lines.append("This task works directly in the repo root. Do all task work there.")
    else:
        lines.append("Use this repo root as the default workspace.")
    return lines


def build_injection_workflow(agent_type: str) -> list[str]:
    return [
        "Follow your agent role and workflow in the system prompt; the task below is task-specific scope, not a role redefinition.",
    ]


def append_teammate_call_log(task_dir: str | None, payload: dict) -> None:
    if not task_dir:
        return
    try:
        log_path = Path(task_dir) / ".teammate-call.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "payload": payload,
        }
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:
        pass


def detect_agent_type(name: str, subagent_type: str) -> str | None:
    if subagent_type in AGENTS_SUPPORTED:
        return subagent_type
    name_lower = name.lower()
    for prefix, agent_type in ROLE_PREFIXES:
        if name_lower.startswith(prefix):
            return agent_type
    return None


def task_agent_name_example(agent_type: str) -> str:
    prefix = TASK_AGENT_PREFIXES.get(agent_type, f"{agent_type}-")
    return f"{prefix}boss-code"


def validate_task_agent_name(agent_type: str, name: str) -> tuple[str | None, str | None]:
    expected_prefix = TASK_AGENT_PREFIXES.get(agent_type)
    if not expected_prefix:
        return None, None
    if not name:
        return None, (
            f"{agent_type} agent must be explicitly named '{expected_prefix}<task-name>' "
            f"(e.g. '{task_agent_name_example(agent_type)}')."
        )
    if not name.lower().startswith(expected_prefix):
        return None, (
            f"Agent '{name}' (type: {agent_type}) must be named '{expected_prefix}<task-name>' "
            f"(e.g. '{task_agent_name_example(agent_type)}')."
        )
    task_name = name[len(expected_prefix):]
    if not task_name:
        return None, (
            f"Agent '{name}' (type: {agent_type}) must include a task name after '{expected_prefix}'. "
            f"Example: '{task_agent_name_example(agent_type)}'."
        )
    return task_name, None


def seed_task_context_file(task_dir: str) -> str:
    """Write <task_dir>/context.json seeded from default_config.{all,programmer,auditor,player}.

    Returns the absolute path to the written file.
    """
    inject = {
        "all": list(DEFAULT_CONFIG.get("all", [])),
        "programmer": list(DEFAULT_CONFIG.get("programmer", [])),
        "auditor": list(DEFAULT_CONFIG.get("auditor", [])),
        "player": list(DEFAULT_CONFIG.get("player", [])),
    }
    payload = {"inject_config": inject}
    path = Path(task_dir) / "context.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return str(path)
