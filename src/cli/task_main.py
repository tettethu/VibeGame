#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Task command handlers. Invoked by `vibegame lead task` typer wrapper.

State: .vibegame/tasks/tasks.jsonl (one JSON object per line). Per-task dir
holds prd.md, plan.md (architect writes), log.md (downstream agents append),
context.json (architect edits), evidence/ (player writes).

Bootstrap is done by the caller (cli/lead.py) which adds the project's
.vibegame/ to sys.path before importing this module.
"""

from __future__ import annotations

import os
import sys
import argparse
import json
import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

# =============================================================================
# Configuration
# =============================================================================

VIBEGAME_DIR = ".vibegame"
TASKS_DIR = f"{VIBEGAME_DIR}/tasks"
TASKS_JSONL = f"{TASKS_DIR}/tasks.jsonl"
ARCHIVE_DIR = f"{TASKS_DIR}/archive"
CONTEXT_CONFIG = f"{VIBEGAME_DIR}/config/context.json"

# =============================================================================
# Colors
# =============================================================================

class Colors:
    RED    = "\033[0;31m"
    GREEN  = "\033[0;32m"
    YELLOW = "\033[1;33m"
    BLUE   = "\033[0;34m"
    CYAN   = "\033[0;36m"
    DIM    = "\033[2m"
    NC     = "\033[0m"


def colored(text: str, color: str) -> str:
    return f"{color}{text}{Colors.NC}"


# =============================================================================
# Helpers
# =============================================================================

def get_repo_root() -> Path:
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print(colored("Error: Not in a git repository", Colors.RED), file=sys.stderr)
        sys.exit(1)
    return Path(result.stdout.strip())


def get_primary_repo_root(current_root: Path | None = None) -> Path:
    cwd = str(current_root or Path.cwd())
    result = subprocess.run(
        ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
        capture_output=True, text=True, cwd=cwd,
    )
    if result.returncode != 0:
        return current_root or get_repo_root()

    common_dir = Path(result.stdout.strip()).resolve()
    if common_dir.name == ".git":
        return common_dir.parent

    return current_root or get_repo_root()


def _slugify(title: str) -> str:
    result = title.lower()
    result = re.sub(r"[^a-z0-9]", "-", result)
    result = re.sub(r"-+", "-", result)
    return result.strip("-")


def _read_json(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None


def _write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


# =============================================================================
# tasks.jsonl helpers
# =============================================================================

def read_tasks(repo_root: Path) -> list[dict]:
    path = repo_root / TASKS_JSONL
    if not path.exists():
        return []
    tasks = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            tasks.append(json.loads(line))
    return tasks


def write_tasks(repo_root: Path, tasks: list[dict]) -> None:
    path = repo_root / TASKS_JSONL
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(t, ensure_ascii=False) for t in tasks]
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def find_task(tasks: list[dict], task_name: str) -> dict | None:
    """Find task by name or display reference."""
    normalized = task_name.strip()
    task_id = int(normalized) if normalized.isdigit() else None

    for t in tasks:
        display_id = f"{t.get('id', 0):03d}"
        display_refs = {
            t["name"],
            f"{display_id}-{t['name']}",
            f"{display_id} {t['name']}",
            f"<{display_id}> {t['name']}",
        }
        if normalized in display_refs:
            return t
        if task_id is not None and t.get("id") == task_id:
            return t
    return None


def get_next_id(tasks: list[dict]) -> int:
    """Get next task ID (auto-increment, 3-digit: 001, 002...)"""
    max_id = 0
    for t in tasks:
        if "id" in t and isinstance(t["id"], int):
            max_id = max(max_id, t["id"])
    return max_id + 1


def update_task(tasks: list[dict], task_name: str, updates: dict) -> list[dict]:
    return [{**t, **updates} if t["name"] == task_name else t for t in tasks]


def is_ready(task: dict, tasks: list[dict]) -> bool:
    """Task is ready when all blockedBy tasks are done."""
    for dep_name in task.get("blockedBy", []):
        dep = find_task(tasks, dep_name)
        if dep is None or dep.get("status") != "done":
            return False
    return True


def ensure_worktree_symlink(target: Path, link_path: Path) -> str | None:
    """Ensure link_path points to target. Returns a status message if changed or skipped."""
    target = target.resolve()
    if link_path.is_symlink():
        try:
            if link_path.resolve() == target:
                return None
        except FileNotFoundError:
            pass
        link_path.unlink()
    elif link_path.exists():
        return f"{link_path.name}/ already exists in worktree (skipping symlink)"

    link_path.parent.mkdir(parents=True, exist_ok=True)
    link_path.symlink_to(target, target_is_directory=target.is_dir())
    return f"Symlinked {link_path.name}/ to worktree"


# =============================================================================
# Command: create
# =============================================================================

def cmd_create(args: argparse.Namespace) -> int:
    """Create task entry in tasks.jsonl only."""
    repo_root = get_repo_root()

    name = args.name or _slugify(args.description)
    if not name:
        print(colored("Error: could not generate name", Colors.RED), file=sys.stderr)
        return 1

    tasks = read_tasks(repo_root)
    if find_task(tasks, name):
        print(colored(f"Error: task '{name}' already exists", Colors.RED), file=sys.stderr)
        return 1

    # Auto-increment ID
    task_id = get_next_id(tasks)

    # Determine initial status
    blocked_by = args.blocked_by or []
    initial_status = "blocked" if blocked_by else "ready"

    new_task: dict = {
        "name":           name,
        "id":             task_id,
        "description":    args.description,
        "status":         initial_status,
        "blockedBy":      blocked_by,
        "createdAt":      datetime.now().strftime("%Y-%m-%d"),
        "dir":            f"{TASKS_DIR}/{task_id:03d}-{name}",
        "worktree":       None,
        "decomposeReason": None,
        "children":       [],
    }

    tasks.append(new_task)
    write_tasks(repo_root, tasks)

    print(colored(f"Created task: {name} (ID: {task_id:03d})", Colors.GREEN), file=sys.stderr)
    print(name)  # stdout: consumed by callers
    return 0


# =============================================================================
# Command: init
# =============================================================================

def cmd_init(args: argparse.Namespace) -> int:
    """Initialize task directory and update task status."""
    repo_root = get_primary_repo_root(get_repo_root())
    tasks = read_tasks(repo_root)
    task = find_task(tasks, args.name)

    if task is None:
        print(colored(f"Error: task '{args.name}' not found in tasks.jsonl", Colors.RED), file=sys.stderr)
        return 1

    if task.get("status") == "in_progress":
        print(colored(f"Error: task '{args.name}' is already in_progress", Colors.RED), file=sys.stderr)
        return 1

    if task.get("status") == "blocked":
        waiting = [d for d in task.get("blockedBy", []) if (find_task(tasks, d) or {}).get("status") != "done"]
        print(colored(f"Error: task '{args.name}' is blocked by: {', '.join(waiting)}", Colors.RED), file=sys.stderr)
        return 1

    task_dir = repo_root / task["dir"]
    task_dir.mkdir(parents=True, exist_ok=True)

    # Create worktree if requested
    if args.use_worktree:
        worktree_path = repo_root.parent / f"vibegame-worktree-{repo_root.name}-{args.name}"
        result = subprocess.run(
            ["git", "worktree", "add", str(worktree_path), "-b", f"task/{task['id']:03d}-{args.name}"],
            cwd=str(repo_root),
            capture_output=True, text=True,
        )
        if result.returncode == 0:
            task["worktree"] = os.path.relpath(worktree_path, repo_root)
            print(colored(f"Created worktree: {task['worktree']}", Colors.GREEN), file=sys.stderr)
            # Copy .env to worktree
            src_env = repo_root / ".env"
            dst_env = worktree_path / ".env"
            if src_env.exists() and not dst_env.exists():
                shutil.copy(src_env, dst_env)
                print(colored(f"Copied .env to worktree", Colors.DIM), file=sys.stderr)
            # Share assets/ and .vibegame/tasks/ into the worktree
            shared_dirs = [
                (repo_root / "assets", worktree_path / "assets"),
                (repo_root / TASKS_DIR, worktree_path / TASKS_DIR),
            ]
            for shared_src, shared_dst in shared_dirs:
                if not shared_src.exists():
                    continue
                message = ensure_worktree_symlink(shared_src, shared_dst)
                if message:
                    print(colored(message, Colors.DIM), file=sys.stderr)
        else:
            print(colored(f"Warning: worktree creation failed: {result.stderr}", Colors.YELLOW), file=sys.stderr)

    prd_path = task_dir / "prd.md"
    prd_content = ""
    if not sys.stdin.isatty():
        prd_content = sys.stdin.read().strip()

    if prd_path.exists() and prd_content:
        print(
            colored(
                "Error: prd.md already exists. Run `vibegame lead task init <name>` without stdin, then edit the existing prd.md directly.",
                Colors.RED,
            ),
            file=sys.stderr,
        )
        return 1

    if prd_content:
        prd_path.write_text(prd_content, encoding="utf-8")

    # Seed per-task context.json from config/context.json:default_config.
    # Contains {all, programmer, auditor, player} inject lists; architect
    # is not seeded here (architect reads source default_config.architect
    # directly at spawn since it's the AUTHOR of per-task context).
    from team.context_config import seed_task_context_file
    seed_task_context_file(str(task_dir))

    # Multiple tasks may be in progress at the same time.
    task["status"] = "in_progress"
    write_tasks(repo_root, tasks)

    print(colored(f"Initialized task: {args.name}", Colors.GREEN), file=sys.stderr)
    print(colored(f"  Dir: {task['dir']}", Colors.BLUE), file=sys.stderr)
    if task.get("worktree"):
        print(colored(f"  Worktree: {task['worktree']}", Colors.BLUE), file=sys.stderr)
        print(colored("  Task artifacts are shared into the worktree via .vibegame/tasks/ symlink", Colors.BLUE), file=sys.stderr)
    print(colored("  Task workflow: architect -> programmer -> auditor -> player", Colors.CYAN), file=sys.stderr)
    print(
        colored(
            f"  Mark done: vibegame lead task modify \"{args.name}\" --key status --value done",
            Colors.CYAN,
        ),
        file=sys.stderr,
    )
    return 0


# =============================================================================
# Command: modify
# =============================================================================

def cmd_modify(args: argparse.Namespace) -> int:
    """Modify arbitrary task fields. Auto-unlocks dependent tasks when status becomes done."""
    current_root = get_repo_root()
    primary_root = get_primary_repo_root(current_root)
    tasks = read_tasks(primary_root)
    task = find_task(tasks, args.name)

    # Fall back to worktree-local tasks if not found in primary
    if task is None and current_root != primary_root:
        current_tasks = read_tasks(current_root)
        current_task = find_task(current_tasks, args.name)
        if current_task is not None:
            tasks = current_tasks
            task = current_task
            primary_root = current_root

    if task is None:
        print(colored(f"Error: task '{args.name}' not found", Colors.RED), file=sys.stderr)
        return 1

    if not args.key:
        print(colored("Error: --key is required", Colors.RED), file=sys.stderr)
        return 1

    # Handle list values
    if len(args.value) == 1:
        value = args.value[0]
    else:
        value = args.value

    tasks = update_task(tasks, args.name, {args.key: value})
    updated_task = find_task(tasks, args.name)

    # Auto-unlock dependent tasks when status becomes done
    if args.key == "status" and value == "done":
        print(colored(f"Task '{args.name}' marked as done", Colors.GREEN), file=sys.stderr)
        for t in tasks:
            if t.get("status") == "blocked" and args.name in t.get("blockedBy", []):
                if is_ready(t, tasks):
                    t["status"] = "ready"
                    print(colored(f"  Auto-unlocked: {t['name']}", Colors.CYAN), file=sys.stderr)

    # Write state in the primary repo. Worktrees see the same tasks dir via symlink.
    write_tasks(primary_root, tasks)

    print(colored(f"Modified '{args.name}': {args.key} = {value}", Colors.GREEN), file=sys.stderr)
    return 0


# =============================================================================
# Command: list
# =============================================================================

def cmd_list(args: argparse.Namespace) -> int:
    """List all tasks."""
    repo_root = get_repo_root()
    tasks = read_tasks(repo_root)

    if not tasks:
        print("  (no tasks)")
        return 0

    # Group
    active   = [t for t in tasks if t.get("status") not in ("done", "decomposed", "archived")]
    done     = [t for t in tasks if t.get("status") == "done"]
    decomped = [t for t in tasks if t.get("status") == "decomposed"]

    def format_task_prefix(t: dict) -> str:
        return f"{t.get('id', 0):03d}:"

    def fmt(t: dict) -> str:
        ready_str = "" if t.get("status") in ("done", "decomposed") else (
            "" if is_ready(t, tasks) else f" [waiting: {','.join(t.get('blockedBy',[]))}]"
        )
        worktree_str = f" wt:{t['worktree']}" if t.get("worktree") else ""
        return (f"  {format_task_prefix(t)} "
                f"[{t.get('status','?'):12}] [{t.get('type') or '-':6}] "
                f"{t['name']:25}"
                f"{ready_str}{worktree_str}")

    if active:
        print(colored("Active:", Colors.BLUE))
        for t in active:
            print(fmt(t))
        print()
    if decomped:
        print(colored("Decomposed:", Colors.CYAN))
        for t in decomped:
            children = ", ".join(t.get("children", []))
            reason = t.get("decomposeReason", "")
            print(f"  {format_task_prefix(t)} [decomposed   ] [-     ] {t['name']:25} children={children}")
            if reason:
                print(f"    Reason: {reason}")
        print()
    if done:
        print(colored(f"Done: {len(done)} task(s)", Colors.GREEN))

    return 0


# =============================================================================
# Command: archive
# =============================================================================

def archive_task(repo_root: Path, task: dict) -> bool:
    """Archive a single task in place. Returns True when state changed."""
    changed = False
    if task.get("status") != "archived":
        task["status"] = "archived"
        changed = True

    task_dir = repo_root / task["dir"]
    if not task_dir.exists():
        return changed

    year_month = datetime.now().strftime("%Y-%m")
    archive_dest = repo_root / ARCHIVE_DIR / year_month / task_dir.name
    archive_dest.parent.mkdir(parents=True, exist_ok=True)
    if task_dir.resolve() == archive_dest.resolve():
        return changed
    archive_dest.parent.mkdir(parents=True, exist_ok=True)
    task_dir.rename(archive_dest)
    task["dir"] = str(archive_dest.relative_to(repo_root))
    return True


def needs_archive(task: dict) -> bool:
    """Return True when a task should be moved into the archive tree."""
    status = task.get("status")
    task_dir = str(task.get("dir", ""))
    if status == "done":
        return True
    if status == "archived" and not task_dir.startswith(f"{ARCHIVE_DIR}/"):
        return True
    return False


def cmd_archive(args: argparse.Namespace) -> int:
    """Archive one task, or all tasks that still need archiving."""
    repo_root = get_repo_root()
    tasks = read_tasks(repo_root)

    if args.all:
        target_tasks = [task for task in tasks if needs_archive(task)]
        if not target_tasks:
            print(colored("No tasks need archiving.", Colors.YELLOW), file=sys.stderr)
            return 0

        archived_names = []
        for task in target_tasks:
            archive_task(repo_root, task)
            archived_names.append(task["name"])

        write_tasks(repo_root, tasks)
        print(colored(f"Archived {len(archived_names)} task(s).", Colors.GREEN), file=sys.stderr)
        for name in archived_names:
            print(colored(f"  - {name}", Colors.DIM), file=sys.stderr)
        return 0

    if not args.name:
        print(colored("Error: task name is required unless --all is used", Colors.RED), file=sys.stderr)
        return 1

    task = find_task(tasks, args.name)
    if task is None:
        print(colored(f"Error: task '{args.name}' not found", Colors.RED), file=sys.stderr)
        return 1

    if task.get("status") != "done":
        print(colored(f"Warning: task '{args.name}' is not done (status: {task.get('status')})", Colors.YELLOW), file=sys.stderr)

    archive_task(repo_root, task)
    write_tasks(repo_root, tasks)

    print(colored(f"Archived: {args.name}", Colors.GREEN), file=sys.stderr)
    return 0


# =============================================================================
# Command: log (parse and display stream-json log)
# =============================================================================

# =============================================================================
# Main
# =============================================================================

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Task Management Script for vibegame",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command")

    # create
    p = sub.add_parser("create", help="Create new task entry in tasks.jsonl")
    p.add_argument("description", help="Task description")
    p.add_argument("--name", "-n", help="Task name (auto-generated if omitted)")
    p.add_argument("--blocked-by", nargs="+", metavar="NAME", default=[], help="Task names this task depends on")

    # init
    p = sub.add_parser("init", help="Initialize task directory")
    p.add_argument("name", help="Task name")
    p.add_argument("--use-worktree", action="store_true", help="Create git worktree")

    # modify
    p = sub.add_parser("modify", help="Modify arbitrary task field")
    p.add_argument("name", help="Task name")
    p.add_argument("--key", "-k", required=True, help="Field to modify")
    p.add_argument("--value", "-v", nargs="+", required=True, help="New value(s)")

    # list
    sub.add_parser("list", help="List all tasks")

    # archive
    p = sub.add_parser("archive", help="Archive a done task")
    p.add_argument("name", nargs="?", help="Task name")
    p.add_argument("--all", action="store_true", help="Archive all tasks that still need archiving")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return 1

    cmds = {
        "create":      cmd_create,
        "init":        cmd_init,
        "modify":      cmd_modify,
        "list":        cmd_list,
        "archive":     cmd_archive,
    }
    return cmds[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
