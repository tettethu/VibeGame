"""Peer connections for the review/fix loop: one starter, one peer."""

from __future__ import annotations

import re
import sys

from .state import load_state, mutate_state, prompt_acknowledgement
from .tmux import TmuxError, pane_dead, pane_exists, paste_prompt

NOTICE = re.compile(r"<vibegame_notice>.*?</vibegame_notice>", re.DOTALL)

RULES = (
    "1. Use `vibegame mate report --to {mate} [--over]` to send a message to the other teammate. "
    "`--over` means that your work is done: you stop and wait for the reply of the other teammate.\n"
    "2. Use `vibegame mate report --over --close-shortcut` to explain your progress and your reason for leaving to the lead. "
    "This also makes you leave the shortcut."
)
INVITE = (
    "The lead created a shortcut. It lets you communicate directly with another teammate, `{mate}`, "
    "so that you can iterate quickly without the lead. You cannot send messages to the lead until you leave the shortcut. "
    "Follow these rules:\n"
    + RULES + "\n"
    "3. During the fast iteration, focus on functionality, code and visuals. "
    "Update documents only after the iteration ends and the work meets the requirements.\n\n"
    "{role} You and the other teammate are responsible for this task:\n\n{message}"
)
ROLES = {
    "starter": "You are the starter in the shortcut. You start the work first.",
    "peer": (
        "You are the peer in the shortcut. This message is only a notice. Do not reply to it or report on it. "
        "If you have work in progress, continue it. If not, wait for the starter's first message."
    ),
}
CLOSED = (
    "`{mate}` has stopped the shortcut. The shortcut is closed. You can no longer use `vibegame mate report --to {mate}`. "
    "You can now use `vibegame mate report` to send messages to the lead. This message is only a notice. Do not reply to it or report on it."
)


def notice(text: str) -> str:
    """Wrap text that informs a teammate without asking for a report."""
    return f"<vibegame_notice>\n{text}\n</vibegame_notice>"


def has_work(prompt: str) -> bool:
    """A prompt made only of notices asks for no report."""
    return bool(NOTICE.sub("", prompt).strip())


def invite(role: str, mate: str, message: str) -> str:
    return INVITE.format(mate=mate, role=ROLES[role], message=message)


def rules(mate: str) -> str:
    return RULES.format(mate=mate)


def closed(mate: str) -> str:
    return notice(CLOSED.format(mate=mate))


def _live(agent: dict) -> bool:
    pane = agent.get("pane_id")
    return pane_exists(pane) and not pane_dead(pane)


def connect(starter: str, peer: str, team_dir: str) -> None:
    if starter == peer or "lead" in (starter, peer):
        raise ValueError("A shortcut connects two different teammates.")

    def change(state: dict) -> None:
        agents = state["agents"]
        for name in (starter, peer):
            if name not in agents:
                raise ValueError(f"Agent '{name}' is not registered.")
            if not _live(agents[name]):
                raise ValueError(f"Agent '{name}' has no live pane.")
            if agents[name].get("shortcut_peer"):
                raise ValueError(f"Agent '{name}' is already in a shortcut with '{agents[name]['shortcut_peer']}'.")
        agents[starter].update(shortcut_peer=peer, shortcut_role="starter")
        agents[peer].update(shortcut_peer=starter, shortcut_role="peer")

    mutate_state(change, team_dir)


def close(name: str, team_dir: str) -> str | None:
    """Close the shortcut of `name`, from either side; return the other teammate."""
    def change(state: dict) -> str | None:
        agents = state["agents"]
        mate = agents[name].get("shortcut_peer")
        agents[name].update(shortcut_peer=None, shortcut_role=None)
        if mate in agents:
            agents[mate].update(shortcut_peer=None, shortcut_role=None)
        return mate

    return mutate_state(change, team_dir)[1]


def require_peer(name: str, peer: str, team_dir: str) -> dict:
    agents = load_state(team_dir)["agents"]
    if peer not in agents:
        raise ValueError(f"Agent '{peer}' is not registered.")
    if agents[name].get("shortcut_peer") != peer or agents[peer].get("shortcut_peer") != name:
        raise ValueError(f"No shortcut connects '{name}' and '{peer}'. Ask the lead to connect them.")
    if not _live(agents[peer]):
        raise ValueError(f"Agent '{peer}' has no live pane. Report the blocker to the lead.")
    return agents[peer]


def deliver(name: str, text: str, team_dir: str) -> None:
    """Paste one message into a teammate's pane, like `lead send`."""
    pane = load_state(team_dir)["agents"][name].get("pane_id")
    print(f"Shortcut delivery to {name}: team={team_dir}, pane={pane}", file=sys.stderr)
    if not pane_exists(pane) or pane_dead(pane):
        raise TmuxError(f"Agent '{name}' has no live pane {pane!r}.")
    paste_prompt(pane, text, acknowledged=prompt_acknowledgement(name, team_dir))
