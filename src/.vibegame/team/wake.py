"""Report notices pasted into the orchestrator pane, whatever the orchestrator is doing."""

from __future__ import annotations

import sys
import time

from .locks import file_lock
from .messages import unread_inbound
from .paths import ensure_team_dir
from .state import load_state, stop_record, submission_check, update_lead
from .tmux import TmuxError, pane_dead, pane_exists, paste_prompt

WAKE_PROMPT = "New teammate reports. Run `vibegame lead read --name ALL`, then continue the task."


def _log(team_dir: str, event: str, detail: str) -> None:
    print(f"Orchestrator notice: {event}; team={team_dir}; {detail}", file=sys.stderr)


def _notice_lock(team_dir: str):
    return file_lock(ensure_team_dir(team_dir) / "orchestrator-wake.lock")


def working_agents(state: dict) -> list[str]:
    # "waiting" counts as in-flight: the mate stopped but its background jobs are still running.
    return sorted(name for name, agent in state["agents"].items() if agent.get("status") in ("working", "waiting"))


def mark_stopped(team_dir: str) -> bool:
    """Record an approved orchestrator stop, unless a report arrived first.

    Shares the notice lock: a report lands either before this check (the stop is blocked)
    or after the record (its notice goes to an idle pane and must be confirmed).
    """
    with _notice_lock(team_dir):
        if unread_inbound(team_dir):
            return False
        update_lead(team_dir, stopped=stop_record())
    return True


def record_prompt(team_dir: str) -> None:
    update_lead(team_dir, last_user_prompt_at=time.time())


def notify_orchestrator(team_dir: str) -> None:
    """Paste one notice per report; an idle orchestrator must confirm it."""
    with _notice_lock(team_dir):
        pane = load_state(team_dir)["lead"].get("pane_id")
        try:
            if not pane_exists(pane) or pane_dead(pane):
                raise TmuxError(f"Orchestrator pane {pane!r} is not live.")
            acknowledged = submission_check(lambda: load_state(team_dir)["lead"], "last_user_prompt_at")
            _log(team_dir, "delivery start", f"pane={pane}; confirmed={acknowledged is not None}")
            paste_prompt(pane, WAKE_PROMPT, acknowledged=acknowledged)
        except TmuxError as exc:
            error = f"Orchestrator notice failed: {exc} The report stays in the lead inbox."
            _log(team_dir, "delivery failed", error)
            raise TmuxError(error) from exc
    _log(team_dir, "delivered", f"pane={pane}")
