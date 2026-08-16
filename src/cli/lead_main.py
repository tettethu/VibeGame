#!/usr/bin/env python3
"""Lead command handlers. Invoked by `vibegame lead` typer wrapper.

Bootstrap is done by the caller (cli/lead.py) which adds the user project's
.vibegame/ to sys.path before importing this module, so the team.* imports
below resolve to the user-project's shipped team package.
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess as sp
import sys
import time
import urllib.request
from pathlib import Path

from team.messages import (  # noqa: E402
    append_message,
    mark_agent_inbound_read,
    mark_all_inbound_read,
    read_agent_messages,
    unread_inbound,
)
from team.logger import get_logger  # noqa: E402
from team.launch import (  # noqa: E402
    build_launch_script_command,
    build_initial_prompt_command,
    launch_env_parts,
    prepare_launch,
)
from team import context_config as teammate_context  # noqa: E402
from team.paths import default_session_name, ensure_team_dir, workspace_root  # noqa: E402
from team.settings import resolve_agent_settings  # noqa: E402
from team.state import (  # noqa: E402
    init_state,
    is_state_error,
    load_state,
    register_agent,
    remove_agent,
    require_agent,
    save_state,
    update_agent,
)
from team.tmux import (  # noqa: E402
    TmuxError,
    capture_pane,
    current_session_name,
    create_session,
    graceful_kill_pane,
    kill_pane,
    kill_session,
    new_window,
    pane_dead,
    pane_exists,
    send_keys,
    session_exists,
    set_remain_on_exit,
    should_send_trust_enter,
    split_window,
    window_exists,
    window_index_exists,
    window_pane_ids,
)

AGENT_WINDOW = "agents"
AGENT_WINDOW_INDEX = 2


def _visible_pane_text(target: str) -> str:
    result = sp.run(["tmux", "capture-pane", "-t", target, "-p"], capture_output=True, text=True)
    if result.returncode != 0:
        return ""
    return result.stdout


def _looks_like_trust_prompt(text: str) -> bool:
    lowered = text.lower()
    return (
        "yes, i trust this folder" in lowered
        or "do you trust" in lowered
        or ("trust" in lowered and "folder" in lowered and "yes" in lowered)
    )


def _trust_prompt_keys(text: str) -> list[str]:
    lowered = text.lower()
    if _looks_like_trust_prompt(text) and any(marker in lowered for marker in ("1.", "1)", "[1]")):
        return ["1", "Enter"]
    return ["Enter"]


def send_trust_enter(target: str, attempts: int = 10, interval: float = 1.0) -> None:
    """Accept workspace trust prompts that can appear late during CLI startup."""
    blind_attempts = 4
    for attempt in range(attempts):
        time.sleep(interval)
        pane_text = _visible_pane_text(target)
        if _looks_like_trust_prompt(pane_text):
            for key in _trust_prompt_keys(pane_text):
                sp.run(["tmux", "send-keys", "-t", target, key], capture_output=True)
                if key != "Enter":
                    time.sleep(0.1)
            return
        if attempt < blind_attempts:
            sp.run(["tmux", "send-keys", "-t", target, "Enter"], capture_output=True)


def _validate_agent_name_for_task_context(agent_type: str | None, agent_name: str) -> str | None:
    effective_type = teammate_context.detect_agent_type(agent_name, agent_type or "")
    if effective_type not in teammate_context.REQUIRE_TASK_DIR:
        return None
    _, error = teammate_context.validate_task_agent_name(effective_type, agent_name)
    return error


def _resolve_task_dir_for_agent(agent_type: str | None, agent_name: str, runtime_dir: str) -> str | None:
    effective_type = teammate_context.detect_agent_type(agent_name, agent_type or "")
    if effective_type not in teammate_context.REQUIRE_TASK_DIR:
        return None
    task_name, name_error = teammate_context.validate_task_agent_name(effective_type, agent_name)
    if name_error or not task_name:
        return None
    repo_root = str(workspace_root(runtime_dir))
    task = teammate_context.find_task(teammate_context.read_tasks(repo_root), task_name)
    if not task:
        return None
    workspace = teammate_context.get_workspace_root(repo_root, task)
    task_dir = os.path.join(workspace, task.get("dir", ""))
    return task_dir if os.path.isdir(task_dir) else None


def _append_general_teammate_call_log(
    runtime_dir: str,
    *,
    name: str,
    agent_type: str | None,
    prompt: str,
    workdir: str,
    cli: str,
    model: str,
) -> None:
    task_dir = _resolve_task_dir_for_agent(agent_type, name, runtime_dir)
    payload = {
        "source": "lead.py agent",
        "name": name,
        "agent_type": agent_type,
        "cli": cli,
        "model": model,
        "workdir": workdir,
        "prompt": prompt,
    }
    try:
        teammate_context.append_teammate_call_log(task_dir, payload)
    except Exception:
        pass


def _extract_transcript_texts(entry: dict) -> list[str]:
    msg = entry.get("message", {})
    content = msg.get("content", "")
    texts: list[str] = []
    if isinstance(content, str) and content:
        return [content]
    if not isinstance(content, list):
        return texts
    for block in content:
        if not isinstance(block, dict):
            continue
        text = block.get("text", "")
        if isinstance(text, str) and text:
            texts.append(text)
        if block.get("type") == "tool_use":
            inp = block.get("input", {})
            if isinstance(inp, dict):
                for field in ("content", "text", "summary"):
                    value = inp.get(field, "")
                    if isinstance(value, str) and value:
                        texts.append(value)
        if block.get("type") == "tool_result":
            result_content = block.get("content", "")
            if isinstance(result_content, str) and result_content:
                texts.append(result_content)
    return texts




def _read_transcript_tail(transcript_path: str | None, limit: int) -> str | None:
    if not transcript_path:
        return None
    path = Path(transcript_path)
    if not path.exists():
        return None
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return None
    entries: list[str] = []
    for line in reversed(lines):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            entry = json.loads(stripped)
        except json.JSONDecodeError:
            continue
        texts = [text for text in _extract_transcript_texts(entry) if text.strip()]
        if texts:
            entries.append("\n".join(texts))
        if len(entries) >= limit:
            break
    if not entries:
        return None
    return "\n\n".join(reversed(entries))


def _runtime_dir() -> Path:
    return ensure_team_dir()


def _require_not_mate() -> None:
    if os.environ.get("VIBEGAME_ROLE") == "mate":
        raise PermissionError("vibegame lead is not available inside a mate session — use vibegame mate report instead.")
    if os.environ.get("VIBEGAME_MATE_NAME"):
        raise PermissionError("vibegame lead is not available when VIBEGAME_MATE_NAME is set.")


def _live_session_name(team_dir: str) -> str | None:
    session_name = load_state(team_dir).get("session_name")
    if not session_name:
        return None
    if not session_exists(session_name):
        return None
    return session_name


def _wait_for_pane_exit(pane_id: str | None, timeout: float = 2.0) -> bool:
    if not pane_id:
        return True
    deadline = time.time() + timeout
    while time.time() < deadline:
        if not pane_exists(pane_id):
            return True
        time.sleep(0.05)
    return not pane_exists(pane_id)


def _assert_pane_booted(pane_id: str, *, role: str, timeout: float = 2.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if pane_dead(pane_id):
            output = capture_pane(pane_id, lines=80).strip()
            print(f"[lead] {role} pane boot failed: {pane_id}", file=sys.stderr)
            if output:
                print(output, file=sys.stderr)
            assert False, f"{role} pane {pane_id} exited during boot"
        if pane_exists(pane_id):
            return
        time.sleep(0.05)
    print(f"[lead] {role} pane missing after boot wait: {pane_id}", file=sys.stderr)
    assert False, f"{role} pane {pane_id} missing after boot wait"


def _ensure_agents_window(session_name: str) -> None:
    if window_index_exists(session_name, AGENT_WINDOW_INDEX):
        return
    new_window(session_name, name=AGENT_WINDOW, index=AGENT_WINDOW_INDEX)


def _preregister_with_dashboard(pane_id: str, name: str, workdir: str, runtime_dir: str) -> None:
    """POST a pending session to the dashboard before the agent pane launches.

    Must be called before send_keys so merge_pending always has a row to clean up.
    """
    state = load_state(runtime_dir)
    port = state.get("dashboard_port")
    if not port:
        return
    event = {
        "source_app": "claude-pending",
        "session_id": f"pending-{name}",
        "hook_event_type": "SessionStart",
        "timestamp": int(time.time() * 1000),
        "name": name,
        "tmux_pane": pane_id,
        "cwd": workdir,
    }
    # Worktree-isolated agents have cwd outside PROJECT_DIR, so the server's
    # _event_belongs_to_project falls back on dashboard_token. Without it the
    # SessionStart is rejected and the agent never registers.
    token = state.get("dashboard_token")
    if token:
        event["dashboard_token"] = token
    payload = json.dumps(event).encode("utf-8")
    try:
        urllib.request.urlopen(
            urllib.request.Request(
                f"http://localhost:{port}/events",
                data=payload,
                headers={"Content-Type": "application/json"},
            ),
            timeout=1,
        )
    except Exception:
        pass


def _sync_resumed_with_dashboard(
    pane_id: str,
    name: str,
    workdir: str,
    runtime_dir: str,
    *,
    cli: str | None,
    session_id: str | None,
    transcript_path: str | None,
) -> None:
    """POST a real SessionSync after resume because Codex may not emit SessionStart."""
    if not session_id:
        return
    state = load_state(runtime_dir)
    port = state.get("dashboard_port")
    if not port:
        return
    source_app = "codex" if cli == "codex" else "claude"
    event = {
        "source_app": source_app,
        "session_id": session_id,
        "hook_event_type": "SessionSync",
        "timestamp": int(time.time() * 1000),
        "name": name,
        "tmux_pane": pane_id,
        "cwd": workdir,
        "transcript_path": transcript_path,
    }
    token = state.get("dashboard_token")
    if token:
        event["dashboard_token"] = token
    payload = json.dumps(event).encode("utf-8")
    try:
        urllib.request.urlopen(
            urllib.request.Request(
                f"http://localhost:{port}/events",
                data=payload,
                headers={"Content-Type": "application/json"},
            ),
            timeout=1,
        )
    except Exception:
        pass


def _notify_dashboard_ended(agent: dict, name: str, runtime_dir: str) -> None:
    """POST a Stop event to the dashboard for a forcefully killed agent."""
    import urllib.request as _req
    session_id = agent.get("session_id")
    if not session_id:
        return
    state = load_state(runtime_dir)
    port = state.get("dashboard_port")
    if not port:
        return
    cli = agent.get("cli", "claude")
    source_app = "codex" if cli == "codex" else "claude"
    event = {
        "source_app": source_app,
        "session_id": session_id,
        "hook_event_type": "Stop",
        "timestamp": int(time.time() * 1000),
        "name": name,
        "cwd": agent.get("workdir", ""),
    }
    token = state.get("dashboard_token")
    if token:
        event["dashboard_token"] = token
    payload = json.dumps(event).encode("utf-8")
    try:
        _req.urlopen(
            _req.Request(
                f"http://localhost:{port}/events",
                data=payload,
                headers={"Content-Type": "application/json"},
            ),
            timeout=1,
        )
    except Exception:
        pass


def cmd_start(args: argparse.Namespace) -> int:
    log = get_logger()
    session_name = current_session_name() or default_session_name(str(_runtime_dir()))
    if not session_exists(session_name):
        try:
            create_session(session_name)
        except TmuxError as exc:
            log.command("lead", "start", f"failed: {exc}")
            print(f"Failed to start tmux session: {exc}", file=sys.stderr)
            return 1
    init_state(session_name, str(_runtime_dir()))
    _ensure_agents_window(session_name)
    log.command("lead", "start", f"session={session_name}")
    print(f"Team started. session={session_name}")
    print(f"team_dir={_runtime_dir()}")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    runtime_dir = str(_runtime_dir())
    data = load_state(runtime_dir)
    session_name = data.get("session_name")
    session_alive = bool(session_name and session_exists(session_name))
    changed = False
    if session_name and not session_alive:
        data["session_name"] = None
        session_name = None
        changed = True
    stale_agents = []
    for name, agent in data.get("agents", {}).items():
        pane_id = agent.get("pane_id") or "-"
        if pane_id != "-" and not pane_exists(pane_id):
            stale_agents.append(name)
    if stale_agents:
        for name in stale_agents:
            data.setdefault("agents", {}).pop(name, None)
        changed = True
    if changed:
        save_state(data, runtime_dir)
        data = load_state(runtime_dir)
        session_name = data.get("session_name")
        session_alive = bool(session_name and session_exists(session_name))
    agents = data.get("agents", {})
    unread_count = len(unread_inbound(runtime_dir))
    workspace = data.get("root") or str(workspace_root(runtime_dir))
    overall_status = "running" if session_alive else "stopped"
    if unread_count:
        overall_status = f"{overall_status}, unread={unread_count}"

    print(f"root: {workspace}")
    print(f"status: {overall_status}")
    print("agents:")

    if not agents:
        print("  (none)")
        return 0

    for name, agent in sorted(agents.items()):
        pane_id = agent.get("pane_id") or "-"
        pane_alive = bool(pane_id != "-" and pane_exists(pane_id))
        pane_suffix = f" pane={pane_id}" if pane_id != "-" else ""
        if pane_id != "-" and not pane_alive:
            pane_suffix = f"{pane_suffix} (dead)"
        print(f"  - {name}: {agent.get('status', 'unknown')}{pane_suffix}")
    return 0


def cmd_agent(args: argparse.Namespace) -> int:
    log = get_logger()
    runtime_dir = str(_runtime_dir())
    data = load_state(runtime_dir)
    session_name = _live_session_name(runtime_dir)
    if not session_name:
        stale = data.get("session_name")
        if stale:
            print(
                f"Run 'vibegame lead start' first. "
                f"state.json points to stale session '{stale}'.",
                file=sys.stderr,
            )
        else:
            print("Run 'vibegame lead start' first.", file=sys.stderr)
        return 1
    resolved_name, resolved_cli, resolved_model = resolve_agent_settings(
        name=args.name,
        agent=args.agent_type,
        model=args.model,
        explicit_team_dir=runtime_dir,
    )
    if not resolved_name:
        print("Agent name is required. Use --name or --agent-type.", file=sys.stderr)
        return 1
    name_error = _validate_agent_name_for_task_context(args.agent_type, resolved_name)
    if name_error:
        print(name_error, file=sys.stderr)
        return 1
    ctx_module = teammate_context
    resolved_task: dict | None = None
    eff_type = ctx_module.detect_agent_type(resolved_name, args.agent_type or "")
    if eff_type is None:
        supported = ", ".join(sorted(ctx_module.AGENTS_SUPPORTED))
        attempted = args.agent_type or resolved_name
        print(
            f"Agent type '{attempted}' is not supported. Supported types: {supported}",
            file=sys.stderr,
        )
        return 1
    if eff_type in ctx_module.REQUIRE_TASK_DIR:
        t_name, _ = ctx_module.validate_task_agent_name(eff_type, resolved_name)
        if t_name:
            repo_root = str(workspace_root(runtime_dir))
            resolved_task = ctx_module.find_task(ctx_module.read_tasks(repo_root), t_name)
            if not resolved_task:
                print(
                    f"Task '{t_name}' not found in .vibegame/tasks/.",
                    file=sys.stderr,
                )
                return 1
    if not args.resume and not args.prompt.strip():
        print("Agent prompt is required.", file=sys.stderr)
        return 1
    if not resolved_cli:
        # settings.json["agents"] is looked up by --agent-type first, then --name.
        # When the two diverge, the user thinks they configured `--name` but the
        # resolver actually checked `--agent-type` — surface the mismatch.
        looked_up = args.agent_type or resolved_name
        if args.name and args.agent_type and args.name != args.agent_type:
            print(
                f"No CLI resolved for agent. settings.json[\"agents\"] was looked up "
                f"by --agent-type='{args.agent_type}' (not --name='{args.name}'), and no "
                f"'{args.agent_type}' entry was found. Either add it, drop --agent-type "
                f"to look up '{args.name}' instead, or pass --model.",
                file=sys.stderr,
            )
        else:
            print(
                f"No CLI resolved for agent '{looked_up}'. "
                f"Add settings.json[\"agents\"][\"{looked_up}\"] or pass --model.",
                file=sys.stderr,
            )
        return 1
    team_root = str(workspace_root(runtime_dir))
    if args.workdir is not None:
        workdir = str(Path(args.workdir).resolve())
    elif resolved_task is not None:
        workdir = ctx_module.get_workspace_root(team_root, resolved_task)
    else:
        workdir = team_root
    existing = data.get("agents", {}).get(resolved_name)
    if existing is not None:
        pane_id = existing.get("pane_id")
        if pane_id and not pane_exists(pane_id):
            remove_agent(resolved_name, runtime_dir)
            data = load_state(runtime_dir)
        else:
            # Live agent with same name. Idempotent path: if agent_type matches
            # (or caller didn't specify), treat the spawn as a no-op success so
            # "ensure persistent teammates" semantics work across both start.py
            # and orchestrator startup without racing. Type mismatch is still
            # an error (genuine name collision).
            existing_type = existing.get("agent_type")
            requested_type = args.agent_type
            if requested_type and existing_type and existing_type != requested_type:
                pane_desc = pane_id or "-"
                print(
                    f"Agent '{resolved_name}' already exists with agent_type='{existing_type}', "
                    f"cannot reuse for agent_type='{requested_type}'. pane={pane_desc}. "
                    f"Kill it first with: vibegame lead kill --name {shlex.quote(resolved_name)}",
                    file=sys.stderr,
                )
                return 1
            status = existing.get("status", "unknown")
            print(f"Agent started. name={resolved_name} pane={pane_id}")
            print(f"report_cmd_in_mate=vibegame mate report 'summary'")
            print(
                f"# (idempotent no-op: agent already alive, status={status}; "
                f"use 'vibegame lead send --name {shlex.quote(resolved_name)} \"...\"' to send a new prompt)",
                file=sys.stderr,
            )
            log.command(
                "lead",
                f"agent --name {resolved_name} --agent-type {requested_type or existing_type or ''} (idempotent reuse)",
                f"pane={pane_id}",
            )
            return 0
    # artist/designer/reviewer stay in window 0 with the orchestrator; others go to window 1
    agent_types_in_main = {"artist", "designer", "reviewer"}
    effective_type = args.agent_type or resolved_name
    if effective_type in agent_types_in_main:
        split_target = session_name
    else:
        _ensure_agents_window(session_name)
        split_target = f"{session_name}:{AGENT_WINDOW_INDEX}"
    try:
        pane_id = split_window(split_target, layout="even-horizontal")
    except TmuxError as exc:
        print(f"Failed to create pane: {exc}", file=sys.stderr)
        return 1
    debug_mode = os.environ.get("VIBEGAME_DEBUG") == "1"
    set_remain_on_exit(pane_id, "on" if debug_mode else "off")
    # Pre-register before launching so merge_pending always finds the pending row
    _preregister_with_dashboard(pane_id, resolved_name, workdir, runtime_dir)
    try:
        launch_cmd, config, resolved_model = prepare_launch(
            resolved_cli,
            resolved_model,
            args.agent_type,
            resolved_name,
            team_root=team_root,
        )
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    fresh_launch_cmd = launch_cmd

    # Append --resume if requested (passthrough to CLI, not used by lead.py itself)
    if args.resume:
        resume_keyword = config.get("resume")
        if resume_keyword:
            resume_cmd = f"{launch_cmd} {resume_keyword} {shlex.quote(args.resume)}"
            if resolved_cli.startswith("claude"):
                fallback_prompt = f"From lead:\n{args.prompt}" if args.prompt else ""
                fallback_cmd = build_initial_prompt_command(
                    fresh_launch_cmd,
                    fallback_prompt,
                    config,
                )
                fallback_notice = shlex.quote(
                    f"Claude resume failed for {resolved_name}; starting a fresh session."
                )
                launch_cmd = (
                    f"{resume_cmd} || {{ echo {fallback_notice} >&2; "
                    f"exec {fallback_cmd}; }}"
                )
            else:
                launch_cmd = resume_cmd

    # Build injected context using shared module functions
    raw_prompt = "" if args.resume else args.prompt
    if not args.resume:
        effective_type = ctx_module.detect_agent_type(resolved_name, args.agent_type or "")
        if effective_type:
            task_dir = _resolve_task_dir_for_agent(args.agent_type, resolved_name, runtime_dir)
            content_root = ctx_module.get_workspace_root(team_root, resolved_task)
            entries = ctx_module.get_inject_entries(effective_type, task_dir)
            context_parts = [ctx_module.inject_entry(e, content_root, team_root, task_dir) for e in entries]
            context_blocks = [p for p in context_parts if p]
            workspace_lines = ctx_module.build_workspace_lines(effective_type, team_root, resolved_task, task_dir)
            workflow_lines = ctx_module.build_injection_workflow(effective_type)
            context_text = "\n".join(context_blocks) or None
            workspace_text = ctx_module.format_bullet_lines(workspace_lines) or None
            workflow_text = ctx_module.format_bullet_lines(workflow_lines) or None
            injected = ctx_module.compose_prompt(
                context_text=context_text,
                workspace_text=workspace_text,
                workflow_text=workflow_text,
                task_text=raw_prompt,
            )
            if injected:
                raw_prompt = injected

    prefixed_prompt = f"From Lead (report when done):\n{raw_prompt}" if raw_prompt else ""
    if prefixed_prompt:
        launch_cmd = build_initial_prompt_command(launch_cmd, prefixed_prompt, config)

    env_parts = launch_env_parts(runtime_dir, resolved_name, workdir, config, resolved_model)
    if args.agent_type:
        env_parts.append(f"VIBEGAME_MATE_AGENT_TYPE={shlex.quote(args.agent_type)}")
    launch = build_launch_script_command(workdir, env_parts, launch_cmd, resolved_name)
    # Register before send_keys so session-start.py hook can write session_id via update_agent.
    try:
        register_agent(
            resolved_name,
            workdir,
            launch_cmd,
            pane_id,
            runtime_dir,
            cli=resolved_cli,
            model=resolved_model,
            agent_type=args.agent_type,
        )
    except ValueError:
        graceful_kill_pane(pane_id)
        existing = load_state(runtime_dir).get("agents", {}).get(resolved_name, {})
        status = existing.get("status", "unknown")
        pane_desc = existing.get("pane_id") or "-"
        print(
            f"Agent '{resolved_name}' already exists. "
            f"status={status} pane={pane_desc}. "
            f"Kill it first with: vibegame lead kill --name {shlex.quote(resolved_name)}",
            file=sys.stderr,
        )
        return 1
    if args.resume:
        update_agent(
            resolved_name,
            runtime_dir,
            session_id=args.resume,
            transcript_path=existing.get("transcript_path") if existing else None,
        )
    send_keys(pane_id, launch)
    if should_send_trust_enter(config):
        send_trust_enter(pane_id)
    _assert_pane_booted(pane_id, role=resolved_name)
    if args.resume:
        _sync_resumed_with_dashboard(
            pane_id,
            resolved_name,
            workdir,
            runtime_dir,
            cli=resolved_cli,
            session_id=args.resume,
            transcript_path=existing.get("transcript_path") if existing else None,
        )
    _append_general_teammate_call_log(
        runtime_dir,
        name=resolved_name,
        agent_type=args.agent_type,
        prompt=args.prompt,
        workdir=workdir,
        cli=resolved_cli,
        model=resolved_model,
    )
    if prefixed_prompt and config.get("initial_prompt_mode") != "argument":
        send_keys(pane_id, prefixed_prompt)
        update_agent(resolved_name, runtime_dir, status="working", last_sent=time.time())
        append_message(
            from_role="lead",
            to_name=resolved_name,
            sender_name="lead",
            message_type="send",
            content=prefixed_prompt,
            explicit_team_dir=runtime_dir,
        )
    elif prefixed_prompt:
        update_agent(resolved_name, runtime_dir, status="working", last_sent=time.time())
        append_message(
            from_role="lead",
            to_name=resolved_name,
            sender_name="lead",
            message_type="send",
            content=prefixed_prompt,
            explicit_team_dir=runtime_dir,
        )
    print(f"Agent started. name={resolved_name} pane={pane_id}")
    print(f"report_cmd_in_mate=vibegame mate report 'summary'")
    log.command("lead", f"agent --name {resolved_name} --agent-type {args.agent_type}", f"pane={pane_id}")
    return 0


def cmd_send(args: argparse.Namespace) -> int:
    try:
        agent = require_agent(args.name, str(_runtime_dir()))
    except KeyError:
        print(f"Agent '{args.name}' not found.", file=sys.stderr)
        return 1
    pane_id = agent.get("pane_id")
    if not pane_id:
        print(f"Agent '{args.name}' has no pane.", file=sys.stderr)
        return 1
    prefixed = f"From Lead (report when done):\n{args.message}"
    send_keys(pane_id, prefixed, double_enter=True)
    update_agent(args.name, str(_runtime_dir()), status="working", last_sent=time.time())
    append_message(
        from_role="lead",
        to_name=args.name,
        sender_name="lead",
        message_type="send",
        content=prefixed,
        explicit_team_dir=str(_runtime_dir()),
    )
    print(f"Message sent to '{args.name}'.")
    return 0


def cmd_inbox(args: argparse.Namespace) -> int:
    """Show which agents have unread messages (not content)."""
    messages = unread_inbound(str(_runtime_dir()))
    if not messages:
        print("No unread agent messages.")
        return 0
    # Count by agent name
    from collections import Counter
    counts = Counter(msg.get("name") for msg in messages)
    for name, count in sorted(counts.items()):
        print(f"{name}: {count} message(s)")
    return 0


def cmd_read(args: argparse.Namespace) -> int:
    """Read messages. Use --name ALL to read all unread agent messages."""
    runtime_dir = str(_runtime_dir())
    if args.name.upper() == "ALL":
        # Read all unread agent messages
        messages = unread_inbound(runtime_dir)
        if not messages:
            print("No unread messages.")
            return 0
        for msg in messages:
            print(f"[{msg.get('name')}] {msg.get('content')}")
        marked = mark_all_inbound_read(runtime_dir)
        print(f"\nMarked {marked} message(s) as read.")
        return 0
    # Read specific agent
    messages = read_agent_messages(
        args.name,
        unread_only=True,
        explicit_team_dir=runtime_dir,
    )
    if not messages:
        print("No messages.")
        return 0
    for msg in messages:
        print(f"[{msg.get('from')}/{msg.get('type')}] {msg.get('content')}")
    mark_agent_inbound_read(args.name, runtime_dir)
    return 0


def cmd_log(args: argparse.Namespace) -> int:
    try:
        agent = require_agent(args.name, str(_runtime_dir()))
    except KeyError:
        print(f"Agent '{args.name}' not found.", file=sys.stderr)
        return 1
    pane_id = agent.get("pane_id")

    # --tmux is explicit: the transcript shows what the agent produced, the pane
    # shows what its process printed (API errors, stalls). Which one answers the
    # question is the caller's call, not a heuristic here.
    if args.tmux:
        if not pane_id:
            print(f"Agent '{args.name}' has no pane.", file=sys.stderr)
            return 1
        print(capture_pane(pane_id, lines=args.lines))
        return 0

    transcript_text = _read_transcript_tail(agent.get("transcript_path"), args.lines)
    if transcript_text:
        print(transcript_text)
        return 0
    print(
        f"No transcript for '{args.name}'. Use --tmux to read its pane output.",
        file=sys.stderr,
    )
    return 1


def cmd_kill(args: argparse.Namespace) -> int:
    try:
        agent = require_agent(args.name, str(_runtime_dir()))
    except KeyError:
        if args.force:
            remove_agent(args.name, str(_runtime_dir()))
            print(f"Agent '{args.name}' force-removed.")
            return 0
        print(f"Agent '{args.name}' not found.", file=sys.stderr)
        return 1
    pane_id = agent.get("pane_id")
    if pane_id:
        graceful_kill_pane(pane_id)
        if not _wait_for_pane_exit(pane_id) and not args.force:
            print(f"Agent '{args.name}' pane {pane_id} is still alive after kill request.", file=sys.stderr)
            return 1
    _notify_dashboard_ended(agent, args.name, str(_runtime_dir()))
    remove_agent(args.name, str(_runtime_dir()))
    if args.force:
        print(f"Agent '{args.name}' force-removed.")
    else:
        print(f"Agent '{args.name}' removed.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Workspace-local team lead runtime")
    sub = parser.add_subparsers(dest="command", required=True)

    start = sub.add_parser("start")
    start.set_defaults(func=cmd_start)

    status = sub.add_parser("status")
    status.set_defaults(func=cmd_status)

    agent = sub.add_parser(
        "agent",
        description=(
            "Start one teammate pane.\n"
            "Required: --prompt.\n"
            "Identity: provide --agent-type, or provide --name, or both.\n"
            "Default: --name falls back to --agent-type, and --workdir falls back to the workspace root."
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    agent.add_argument(
        "--name",
        default=None,
        help="Optional teammate instance name. Defaults to --agent-type when omitted.",
    )
    agent.add_argument(
        "--workdir",
        default=None,
        help="Optional workdir for the teammate. Defaults to the workspace root.",
    )
    agent.add_argument(
        "--model",
        default=None,
        help="Optional model override. Otherwise load from .vibegame/settings.json.",
    )
    agent.add_argument(
        "--agent-type",
        "--agent_type",
        dest="agent_type",
        default=None,
        help="Optional agent template name from .claude/agents and settings.json.",
    )
    agent.add_argument(
        "--prompt",
        required=True,
        help="Required initial task prompt sent to the teammate.",
    )
    agent.add_argument(
        "--resume",
        default=None,
        help="Resume a previous Claude/Codex session by session ID.",
    )
    agent.set_defaults(func=cmd_agent)

    send = sub.add_parser("send")
    send.add_argument("--name", required=True)
    send.add_argument("message")
    send.set_defaults(func=cmd_send)

    inbox = sub.add_parser("inbox")
    inbox.set_defaults(func=cmd_inbox)

    read = sub.add_parser("read")
    read.add_argument("--name", required=True)
    read.set_defaults(func=cmd_read)

    log = sub.add_parser("log")
    log.add_argument("--name", required=True)
    log.add_argument("--lines", type=int, default=60)
    log.add_argument("--tmux", action="store_true", help="read the tmux pane instead of the transcript")
    log.set_defaults(func=cmd_log)

    kill = sub.add_parser("kill")
    kill.add_argument("--name", required=True)
    kill.add_argument("-f", "--force", action="store_true")
    kill.set_defaults(func=cmd_kill)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        _require_not_mate()
    except PermissionError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    try:
        return args.func(args)
    except RuntimeError as exc:
        if is_state_error(exc):
            print(str(exc), file=sys.stderr)
            return 1
        raise


if __name__ == "__main__":
    raise SystemExit(main())
