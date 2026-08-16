"""`vibegame mate` typer sub-app — used from inside mate processes to report back.

Bootstrap is lazy (on first command invocation), so that loading the CLI in
non-vibegame contexts (e.g. `vibegame art ...` outside a project) does not
fail on team-path resolution.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Optional

import typer

from cli._bootstrap import ensure_team_on_path


_bootstrapped = False
_mate_main = None


def _bootstrap() -> None:
    global _bootstrapped, _mate_main
    if _bootstrapped:
        return
    ensure_team_on_path()
    from cli import mate_main as _mm
    _mate_main = _mm
    _bootstrapped = True


mate_app = typer.Typer(
    name="mate",
    help="Mate runtime: report progress / completion back to the lead.",
    no_args_is_help=True,
    add_completion=False,
    rich_markup_mode=None,
)


@mate_app.callback()
def _mate_callback():
    _bootstrap()


def _exit(rc: int) -> None:
    if rc != 0:
        raise typer.Exit(rc)


@mate_app.command("report")
def cmd_report(
    content: Optional[str] = typer.Argument(None, help="Report content. Reads from stdin if omitted."),
    name: Optional[str] = typer.Option(None, "--name", help="Mate name. Defaults to $VIBEGAME_MATE_NAME."),
    over: bool = typer.Option(False, "--over", help="Mark current work as over; status -> can-stop."),
):
    """Send a progress or completion report from a mate back to the lead."""
    _exit(_mate_main.cmd_report(SimpleNamespace(content=content, name=name, over=over)))
