#!/usr/bin/env python3
"""Mate command handlers. Invoked by `vibegame mate` typer wrapper.

Bootstrap is done by the caller (cli/mate.py) which adds the user project's
.vibegame/ to sys.path before importing this module.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from team.messages import append_message  # noqa: E402
from team.paths import ensure_team_dir  # noqa: E402
from team.state import is_state_error, require_agent, update_agent  # noqa: E402
from team.logger import get_logger  # noqa: E402


def _runtime_dir() -> Path:
    return ensure_team_dir()


def _require_mate_role() -> None:
    role = os.environ.get("VIBEGAME_ROLE")
    if role != "mate":
        raise PermissionError("vibegame mate requires VIBEGAME_ROLE=mate (set by the lead when spawning teammates).")


def _mate_name(value: str | None) -> str:
    return value or os.environ.get("VIBEGAME_MATE_NAME", "")


def cmd_report(args: argparse.Namespace) -> int:
    log = get_logger()
    try:
        _require_mate_role()
    except PermissionError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    name = _mate_name(args.name)
    if not name:
        print("Mate name required.", file=sys.stderr)
        return 1
    try:
        require_agent(name, str(_runtime_dir()))
    except KeyError:
        print(f"Agent '{name}' not registered in team state.", file=sys.stderr)
        return 1
    content = args.content
    if not content:
        content = sys.stdin.read().strip()
    if not content:
        print("No report content provided.", file=sys.stderr)
        return 1
    # only update status to can-stop when --over is set
    updates = {"last_report": content}
    if args.over:
        updates["status"] = "can-stop"
    update_agent(name, str(_runtime_dir()), **updates)
    append_message(
        from_role="agent",
        to_name="lead",
        sender_name=name,
        message_type="report",
        content=content,
        explicit_team_dir=str(_runtime_dir()),
    )
    status_hint = " (status -> can-stop)" if args.over else ""
    log.command("mate", f"report --name {name}{' --over' if args.over else ''}", f"sent")
    print(f"Report sent from '{name}'{status_hint}.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Workspace-local team mate runtime")
    sub = parser.add_subparsers(dest="command", required=True)

    report = sub.add_parser("report")
    report.add_argument("--name", default=None)
    report.add_argument("--over", action="store_true", help="current work is over, ready for next instruction")
    report.add_argument("content", nargs="?")
    report.set_defaults(func=cmd_report)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return args.func(args)
    except RuntimeError as exc:
        if is_state_error(exc):
            print(str(exc), file=sys.stderr)
            return 1
        raise


if __name__ == "__main__":
    raise SystemExit(main())
