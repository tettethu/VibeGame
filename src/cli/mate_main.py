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
from team.shortcut import close, closed, deliver, require_peer
from team.tmux import TmuxError
from team.wake import notify_orchestrator
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
    if name != os.environ.get("VIBEGAME_MATE_NAME"):
        print("Mate name must match VIBEGAME_MATE_NAME.", file=sys.stderr)
        return 1
    try:
        require_agent(name, str(_runtime_dir()))
    except KeyError:
        print(f"Agent '{name}' not registered in team state.", file=sys.stderr)
        return 1
    content = args.content
    if content is not None:
        content = content.strip()
    if content is None:
        content = sys.stdin.read().strip()
    if not content:
        print("No report content provided.", file=sys.stderr)
        return 1
    if args.over and args.wait:
        print("--over and --wait are mutually exclusive.", file=sys.stderr)
        return 1
    recipient = args.to
    team_dir = str(_runtime_dir())
    if recipient != "lead":
        try:
            require_peer(name, recipient, team_dir)
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 1
    mate = require_agent(name, team_dir).get("shortcut_peer")
    if args.close_shortcut and not (mate and recipient == "lead" and args.over):
        print("--close-shortcut needs --over, no --to, and an open shortcut.", file=sys.stderr)
        return 1
    # Only an explicit close lets a teammate in a shortcut report to the lead.
    if recipient == "lead" and mate and not args.close_shortcut:
        print(f"You are in a shortcut with '{mate}'. Message it with `vibegame mate report --to {mate} [--over]`, "
              "or leave the shortcut with `vibegame mate report --over --close-shortcut`.", file=sys.stderr)
        return 1
    # status only changes on --over (can-stop) or --wait (waiting); a plain report keeps it
    updates = {"last_report": content}
    report_mode = "working"
    if args.over:
        updates["status"] = "can-stop"
        report_mode = "over"
    elif args.wait:
        updates["status"] = "waiting"
        report_mode = "wait"
    append_message(
        from_role="agent",
        to_name=recipient,
        sender_name=name,
        message_type="report",
        content=content,
        report_mode=report_mode,
        explicit_team_dir=team_dir,
    )
    update_agent(name, team_dir, **updates)
    failures = []
    if recipient != "lead":
        try:
            deliver(recipient, f"From `{name}`:\n{content}", team_dir)
        except TmuxError as exc:
            update_agent(name, team_dir, status="working")
            failures.append(f"Shortcut delivery failed: {name} -> {recipient}: {exc}. Undelivered message:\n{content}")
        else:
            update_agent(recipient, team_dir, status="working")
    elif args.close_shortcut:
        close(name, team_dir)
        text = closed(name)
        try:
            deliver(mate, text, team_dir)
        except TmuxError as exc:
            failures.append(f"Shortcut close notice failed: {name} -> {mate}: {exc}.")
        else:
            append_message(from_role="agent", to_name=mate, sender_name=name, message_type="notice", content=text, explicit_team_dir=team_dir)
    if failures:
        failure = "\n".join(failures)
        append_message(from_role="agent", to_name="lead", sender_name=name, message_type="report", content=failure, explicit_team_dir=team_dir)
        print(failure, file=sys.stderr)
    if recipient == "lead" or failures:
        try:
            notify_orchestrator(team_dir)
        except TmuxError as exc:
            print(str(exc), file=sys.stderr)
            return 1
    if failures:
        return 1
    status_hint = " (status -> can-stop)" if args.over else (" (status -> waiting)" if args.wait else "")
    flags = ' --over' if args.over else (' --wait' if args.wait else '')
    log.command("mate", f"report --name {name} --to {recipient}{flags}", "sent")
    print(f"Report sent from '{name}' to '{recipient}'{status_hint}.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Workspace-local team mate runtime")
    sub = parser.add_subparsers(dest="command", required=True)

    report = sub.add_parser("report")
    report.add_argument("--name", default=None)
    report.add_argument("--to", default="lead")
    report.add_argument("--wait", action="store_true")
    report.add_argument("--over", action="store_true", help="current work is over, ready for next instruction")
    report.add_argument("--close-shortcut", action="store_true", help="with --over to the lead, leave your shortcut")
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
