"""Helpers for telling root agent hook events apart from subagent events."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

SUBAGENT_HOOK_EVENTS = {"SubagentStart", "SubagentStop"}


def read_first_transcript_entry(transcript_path: str | None, retries: int = 5, delay: float = 0.02) -> dict | None:
    if not transcript_path:
        return None
    path = Path(transcript_path)
    for _ in range(retries):
        try:
            with path.open("r", encoding="utf-8") as f:
                line = f.readline().strip()
            if not line:
                time.sleep(delay)
                continue
            entry = json.loads(line)
            return entry if isinstance(entry, dict) else None
        except FileNotFoundError:
            time.sleep(delay)
        except json.JSONDecodeError:
            time.sleep(delay)
        except OSError:
            return None
    return None


def _source_has_subagent(source: Any) -> bool:
    return isinstance(source, dict) and isinstance(source.get("subagent"), dict)


def has_codex_subagent_source(payload: dict | None) -> bool:
    if not isinstance(payload, dict):
        return False
    return _source_has_subagent(payload.get("source"))


def is_codex_subagent_transcript(transcript_path: str | None) -> bool:
    entry = read_first_transcript_entry(transcript_path)
    payload = entry.get("payload") if isinstance(entry, dict) else None
    return has_codex_subagent_source(payload)


def is_claude_subagent_event(payload: dict | None) -> bool:
    if not isinstance(payload, dict):
        return False
    if payload.get("hook_event_name") in SUBAGENT_HOOK_EVENTS:
        return True
    return bool(payload.get("agent_id"))


def is_subagent_event(payload: dict | None) -> bool:
    if not isinstance(payload, dict):
        return False
    if is_claude_subagent_event(payload):
        return True
    if has_codex_subagent_source(payload):
        return True
    return is_codex_subagent_transcript(payload.get("transcript_path"))


def is_main_agent_event(payload: dict | None) -> bool:
    return not is_subagent_event(payload)
