"""Message log for the local team runtime."""

from __future__ import annotations

import json
import time

from .locks import file_lock
from .paths import ensure_team_dir, lock_path, messages_path


def _now() -> float:
    return time.time()


def _read_messages_unlocked(explicit_team_dir: str | None = None) -> list[dict]:
    path = messages_path(explicit_team_dir)
    if not path.exists():
        return []
    messages = []
    with open(path, encoding="utf-8") as handle:
        for raw in handle:
            raw = raw.strip()
            if not raw:
                continue
            try:
                messages.append(json.loads(raw))
            except json.JSONDecodeError:
                continue
    return messages


def read_messages(explicit_team_dir: str | None = None) -> list[dict]:
    ensure_team_dir(explicit_team_dir)
    with file_lock(lock_path(explicit_team_dir)):
        return _read_messages_unlocked(explicit_team_dir)


def append_message(
    *,
    from_role: str,
    to_name: str,
    sender_name: str,
    message_type: str,
    content: str,
    explicit_team_dir: str | None = None,
) -> dict:
    ensure_team_dir(explicit_team_dir)
    msg = {
        "from": from_role,
        "to": to_name,
        "name": sender_name,
        "type": message_type,
        "content": content,
        "read": from_role == "lead",
        "timestamp": _now(),
    }
    with file_lock(lock_path(explicit_team_dir)):
        with open(messages_path(explicit_team_dir), "a", encoding="utf-8") as handle:
            handle.write(json.dumps(msg, ensure_ascii=False) + "\n")
    return msg


def unread_inbound(explicit_team_dir: str | None = None) -> list[dict]:
    return [
        msg for msg in read_messages(explicit_team_dir)
        if not msg.get("read") and msg.get("from") == "agent"
    ]


def read_agent_messages(
    name: str,
    *,
    unread_only: bool,
    explicit_team_dir: str | None = None,
) -> list[dict]:
    messages = read_messages(explicit_team_dir)
    results = []
    for msg in messages:
        related = msg.get("name") == name or msg.get("to") == name
        if not related:
            continue
        if unread_only and not (msg.get("from") == "agent" and not msg.get("read")):
            continue
        results.append(msg)
    return results


def mark_agent_inbound_read(name: str, explicit_team_dir: str | None = None) -> None:
    ensure_team_dir(explicit_team_dir)
    with file_lock(lock_path(explicit_team_dir)):
        messages = _read_messages_unlocked(explicit_team_dir)
        changed = False
        for msg in messages:
            if msg.get("from") != "agent":
                continue
            if msg.get("name") != name:
                continue
            if msg.get("read"):
                continue
            msg["read"] = True
            changed = True
        if changed:
            with open(messages_path(explicit_team_dir), "w", encoding="utf-8") as handle:
                for msg in messages:
                    handle.write(json.dumps(msg, ensure_ascii=False) + "\n")


def mark_all_inbound_read(explicit_team_dir: str | None = None) -> int:
    """Mark all unread agent messages as read. Returns count marked."""
    ensure_team_dir(explicit_team_dir)
    with file_lock(lock_path(explicit_team_dir)):
        messages = _read_messages_unlocked(explicit_team_dir)
        changed = False
        count = 0
        for msg in messages:
            if msg.get("from") != "agent":
                continue
            if msg.get("read"):
                continue
            msg["read"] = True
            changed = True
            count += 1
        if changed:
            with open(messages_path(explicit_team_dir), "w", encoding="utf-8") as handle:
                for msg in messages:
                    handle.write(json.dumps(msg, ensure_ascii=False) + "\n")
    return count
