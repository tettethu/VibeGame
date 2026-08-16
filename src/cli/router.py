import os
import sys

import typer

from artist.cli import art_app
from cli.vlm import cmd_vlm

from cli.play import play_app

app = typer.Typer(
    name="vibegame",
    help="VibeGame CLI - Game development tool command-line interface",
    add_completion=False,
    no_args_is_help=True,
    rich_markup_mode=None,
    pretty_exceptions_enable=False,
)

app.add_typer(art_app, name="art", help="Game art asset processing toolkit")
app.command("vlm")(cmd_vlm)
app.add_typer(play_app, name="play", help="Runtime API CLI wrapper")


def _register_team_cli() -> None:
    """Lazily register vibegame lead/mate. They bootstrap by walking up to find
    the user project's .vibegame/, so loading them at module import time would
    crash whenever the user invokes a non-team command outside a vibegame
    project (e.g. `vibegame art ...`). Defer until the subcommand is dispatched.
    """
    from cli.lead import lead_app
    from cli.mate import mate_app
    app.add_typer(lead_app, name="lead", help="Team lead runtime")
    app.add_typer(mate_app, name="mate", help="Mate runtime (called from inside teammate processes)")


_register_team_cli()


@app.command(
    "python",
    context_settings={"allow_extra_args": True, "ignore_unknown_options": True},
    help="Run Python with vibegame's bundled interpreter (PIL, numpy, etc. available)",
)
def cmd_python(ctx: typer.Context):
    os.execv(sys.executable, [sys.executable, *ctx.args])


@app.callback(invoke_without_command=True)
def callback(ctx: typer.Context):
    """VibeGame CLI - Game development tool command-line interface"""
    if ctx.invoked_subcommand is None:
        print("Please specify a command. Use --help to see available commands.")
