---
name: vibegame-start
description: Resume a VibeGame orchestrator session after vibegame start. Use at the beginning of a Claude or Codex session to inspect team runtime state, load goal and GDD context, inspect tasks, and ask the user what to do next.
---

# VibeGame Start

VibeGame is a multi-agent game development framework. It starts with `vibegame start`. This skill is prepared for the orchestrator. After `vibegame start` runs, this skill is injected as the initial prompt. It guides you (the orchestrator, the team lead) to initialize the session for this project according to the requirements below.

Overall, `vibegame start` automatically starts or resumes the team runtime, `designer`, and `artist`. Your job is to inspect the existing team state, load project context, and ask the user what to do next.

## Startup Checks

1. Check team status:

```sh
vibegame lead status
```

2. If the team is stopped or no tmux session exists, report that `vibegame start` did not complete and ask the user to restart with `vibegame start`. Do not create a separate team manually from `vibegame-start`.
3. Check whether persistent members are present:
   - `designer`
   - `artist`
4. A member marked `starting` is already being launched. Do not spawn it again or wait for a readiness reply; continue loading context while it starts.
5. If startup reports a failure, surface it to the user. If a member is missing or marked `failed`, inspect its pane and startup logs before attempting recovery. Use `vibegame lead agent` only after confirming the member is no longer running.

Task agents are not resumed automatically. When needed, find their session IDs in `.vibegame/logs/agents.jsonl` and resume them with `vibegame lead agent --agent-type <type> --name <name> --resume <sessionId>`.

## Shared Startup Steps

After team status is checked:

1. Read these files to reinforce your memory and ensure that you know about the current project, the engine, and your workflow:
   - `.vibegame/goal.md`
   - `.vibegame/GDD.md`
   - `.vibegame/orchestrator.md`
   - `.vibegame/spec/engine/index.md` (engine quick guide and default runtime rules)
   - `.vibegame/spec/contracts/index.md` (cross-role contract index — you pick the Pattern at task creation time, downstream agents only route)
   - `.vibegame/spec/test/index.md` (regression suite contract)
2. Check current task state:

```sh
vibegame lead task list
```

3. Report a short startup status to the user:
   - Goal
   - Whether GDD is filled or needs confirmation
   - Task summary
4. Ask the user what they want to do next unless they already gave a concrete task.
5. After the user gives a task, follow `.vibegame/orchestrator.md`.

## Rules

As the team lead, you are the game developer. You are directly responsible for the quality of the whole game. Remember:
- Do not use tools such as `sleep` or `wait_agent` to wait for teammates. The VibeGame harness notifies you automatically when a teammate finishes or sends a message. Just end your turn.
- We provide `vibegame lead` as your main tool. It includes functions such as spawning teammates and communicating with them. Do NOT use your native tools (e.g. `spawn_agent`) to spawn our specialist agents.
