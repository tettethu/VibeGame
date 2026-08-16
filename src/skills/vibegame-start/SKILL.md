---
name: vibegame-start
description: Resume a VibeGame orchestrator session after vibegame start. Use at the beginning of a Claude or Codex session to inspect team runtime state, repair missing persistent members, load goal and GDD context, inspect tasks, and ask the user what to do next.
---

# VibeGame Start

`vibegame start` already starts the team runtime. Your job is to inspect the existing team state, repair missing persistent members if needed, load project context, and ask the user what to do next.

## Startup Checks

1. Check team status:

```sh
vibegame lead status
```

2. If the team is stopped or no tmux session exists, report that `vibegame start` did not complete and ask the user to restart with `vibegame start`. Do not create a separate team manually from `vibegame-start`.
3. Check whether persistent members are present:
   - `designer`
   - `artist`
4. If `designer` or `artist` is missing, start only the missing member. Use the matching command(s):

```sh
vibegame lead agent --agent-type designer --name designer --prompt "You are the persistent designer. Stand by for design work. Do not start work until the lead gives you a task."
vibegame lead agent --agent-type artist --name artist --prompt "You are the persistent artist. Stand by for art work. Do not start work until the lead gives you a task."
```

Do not wait for designer or artist to reply that they are ready. Their startup can finish asynchronously while you continue.

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
