"""`vibegame lead` and nested `vibegame lead task` typer sub-app.

Bootstraps the user project's .vibegame/ onto sys.path on the first command
invocation (NOT at module import), then defers to the argparse-based command
handlers in lead_main.py / task_main.py. Lazy bootstrap so that running an
unrelated subcommand like `vibegame art ...` from outside a vibegame project
does not crash on team-path resolution.
"""

from __future__ import annotations

import os
from types import SimpleNamespace
from typing import List, Optional

import typer

from cli._bootstrap import ensure_team_on_path


_bootstrapped = False
_lead_main = None
_task_main = None


def _reject_inside_mate() -> None:
    """Mirror lead_main.main()'s _require_not_mate gate.

    The typer wrappers call lead_main's cmd_* helpers directly, which bypasses
    lead_main.main()'s entrypoint check. Without this gate, a mate process
    could invoke `vibegame lead ...` and corrupt the lead's state.
    """
    if os.environ.get("VIBEGAME_ROLE") == "mate":
        typer.echo(
            "vibegame lead is not available inside a mate session — "
            "use `vibegame mate report` to send updates to the lead.",
            err=True,
        )
        raise typer.Exit(1)
    if os.environ.get("VIBEGAME_MATE_NAME"):
        typer.echo(
            "vibegame lead is not available when VIBEGAME_MATE_NAME is set.",
            err=True,
        )
        raise typer.Exit(1)


def _bootstrap() -> None:
    """Add the project's .vibegame/ to sys.path and lazily import command modules."""
    global _bootstrapped, _lead_main, _task_main
    if _bootstrapped:
        return
    ensure_team_on_path()
    from cli import lead_main as _lm
    from cli import task_main as _tm
    _lead_main = _lm
    _task_main = _tm
    _bootstrapped = True


lead_app = typer.Typer(
    name="lead",
    help="Team lead runtime: start the team, spawn teammates, send messages, kill panes.",
    no_args_is_help=True,
    add_completion=False,
    rich_markup_mode=None,
)

task_app = typer.Typer(
    name="task",
    help="Task lifecycle: create / init / modify / list / archive.",
    no_args_is_help=True,
    add_completion=False,
    rich_markup_mode=None,
)
lead_app.add_typer(task_app, name="task")


@lead_app.callback()
def _lead_callback():
    """Reject mate-role invocations then bootstrap the team path."""
    _reject_inside_mate()
    _bootstrap()


def _exit(rc: int) -> None:
    if rc != 0:
        raise typer.Exit(rc)


# =============================================================================
# Lead subcommands
# =============================================================================


@lead_app.command("start")
def cmd_start():
    """Start the team's tmux session."""
    _exit(_lead_main.cmd_start(SimpleNamespace()))


@lead_app.command("status")
def cmd_status():
    """Show team and agent status."""
    _exit(_lead_main.cmd_status(SimpleNamespace()))


@lead_app.command("agent")
def cmd_agent(
    prompt: str = typer.Option("", "--prompt", help="Initial task prompt for the teammate. Required unless --resume is given."),
    name: Optional[str] = typer.Option(None, "--name", help="Optional teammate instance name. Defaults to --agent-type."),
    workdir: Optional[str] = typer.Option(None, "--workdir", help="Optional workdir. Defaults to the workspace root."),
    model: Optional[str] = typer.Option(None, "--model", help="Optional model override."),
    agent_type: Optional[str] = typer.Option(None, "--agent-type", "--agent_type", help="Optional agent template name."),
    resume: Optional[str] = typer.Option(None, "--resume", help="Resume previous Claude/Codex session by id."),
):
    """Spawn a teammate in a new tmux pane."""
    _exit(_lead_main.cmd_agent(SimpleNamespace(
        prompt=prompt, name=name, workdir=workdir, model=model,
        agent_type=agent_type, resume=resume,
    )))


@lead_app.command("send")
def cmd_send(
    name: str = typer.Option(..., "--name", help="Target agent name."),
    message: str = typer.Argument(..., help="Message body."),
):
    """Send a message to a teammate."""
    _exit(_lead_main.cmd_send(SimpleNamespace(name=name, message=message)))


@lead_app.command("inbox")
def cmd_inbox():
    """Show unread message counts per agent."""
    _exit(_lead_main.cmd_inbox(SimpleNamespace()))


@lead_app.command("read")
def cmd_read(
    name: str = typer.Option(..., "--name", help="Agent name, or 'ALL' for every unread message."),
):
    """Read messages and mark them as read."""
    _exit(_lead_main.cmd_read(SimpleNamespace(name=name)))


@lead_app.command("log")
def cmd_log(
    name: str = typer.Option(..., "--name", help="Agent name."),
    lines: int = typer.Option(60, "--lines", help="Tail length."),
    tmux: bool = typer.Option(False, "--tmux", help="Read the tmux pane instead of the transcript."),
):
    """Read an agent's transcript, or its tmux pane with --tmux."""
    _exit(_lead_main.cmd_log(SimpleNamespace(name=name, lines=lines, tmux=tmux)))


@lead_app.command("kill")
def cmd_kill(
    name: str = typer.Option(..., "--name", help="Agent to kill."),
    force: bool = typer.Option(False, "-f", "--force", help="Force-remove even if pane is still alive."),
):
    """Kill a teammate pane and remove its state entry."""
    _exit(_lead_main.cmd_kill(SimpleNamespace(name=name, force=force)))


# =============================================================================
# Task subcommands  (vibegame lead task ...)
# =============================================================================


@task_app.command("create")
def cmd_task_create(
    description: str = typer.Argument(..., help="Task description."),
    name: Optional[str] = typer.Option(None, "--name", "-n", help="Task name (auto-generated from description if omitted)."),
    blocked_by: Optional[List[str]] = typer.Option(None, "--blocked-by", help="Task names this depends on. Pass multiple times."),
):
    """Create a new task entry in tasks.jsonl."""
    _exit(_task_main.cmd_create(SimpleNamespace(
        description=description, name=name, blocked_by=blocked_by or [],
    )))


@task_app.command("init")
def cmd_task_init(
    name: str = typer.Argument(..., help="Task name to initialize."),
    use_worktree: bool = typer.Option(False, "--use-worktree", help="Create a git worktree for this task."),
):
    """Initialize a task dir (prd.md from stdin, context.json seeded from defaults)."""
    _exit(_task_main.cmd_init(SimpleNamespace(name=name, use_worktree=use_worktree)))


@task_app.command("modify")
def cmd_task_modify(
    name: str = typer.Argument(..., help="Task name."),
    key: str = typer.Option(..., "--key", "-k", help="Field to modify (e.g. status)."),
    value: List[str] = typer.Option(..., "--value", "-v", help="New value(s)."),
):
    """Modify an arbitrary task field. Auto-unlocks dependents when status=done."""
    _exit(_task_main.cmd_modify(SimpleNamespace(name=name, key=key, value=value)))


@task_app.command("list")
def cmd_task_list():
    """List all tasks."""
    _exit(_task_main.cmd_list(SimpleNamespace()))


@task_app.command("archive")
def cmd_task_archive(
    name: Optional[str] = typer.Argument(None, help="Task name. Omit when --all is used."),
    all_done: bool = typer.Option(False, "--all", help="Archive every task that still needs archiving."),
):
    """Archive one task, or all tasks that still need archiving."""
    _exit(_task_main.cmd_archive(SimpleNamespace(name=name, all=all_done)))
