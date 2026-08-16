---
name: vibegame-build
description: Run VibeGame's standard end-to-end game development workflow with reviewer gates. Use when the user wants to create a game from zero or evolve an existing game across multiple stages.
---

# VibeGame Build

This is a **long-running delegation workflow**. The lead sets a multi-stage implementation plan (potentially hours of work), delegates to teammates, and supervises execution. The lead **does not implement directly** — only tiny local edits qualify as self-service.

Core lead responsibilities in this mode:
- **Understand**: rebuild context from code, specs, and live verification
- **Architect**: design the multi-stage plan before any execution
- **Supervise**: delegate, track progress, and course-correct through teammates

---

## Phase 1: Plan

Clarify the goal until it is concrete and actionable. Do not proceed to execution or use `create_goal` tool until the goal is aligned.

`.vibegame/goal.md` `## User Input` holds the user's verbatim request, written there by a hook when this build was invoked. Confirm it is non-empty before anything else; if empty, paste the user's original words in yourself, unedited. GDD, `prd.md` and the final review all answer to it.

1. Use at most 3 Task-tool subagents (Claude Code `Explore` / Codex equivalent — NOT teammates spawned via `vibegame lead`) to inspect three discovery surfaces in parallel:
   - **Current codebase** — existing files, patterns, specs, implementation status.
   - **`modules/index.md`** — catalog of installed `*Module.js` Node scripts (one-line description + interface per module). Anything you can wire in directly via `script: "XxxModule"` or extend by subclassing is work the team does not have to redo.
   - **`skeletons/index.md`** — catalog of available sub-genre skeletons. For any slug whose row matches the request, open `skeletons/<slug>/index.md` and summarize what `scripts/`, `entities/`, and `scenes/` could be cherry-picked into the new project. Treat the skeleton as a head start, not a constraint.
2. If gameplay mechanics are involved (movement, combat, enemies, bosses, HUD, hit feedback, death, pacing — basically anything beyond a static viewer), **commission `designer` to fill the design-layer gaps before decomposing tasks** and update `GDD.md` for user to review.
   - Whenever GDD changes — designer's handoff or your own edit — check it against the verbatim request before moving on:
     ```sh
     cat .vibegame/goal.md .vibegame/GDD.md > /tmp/gdd-fidelity.md
     vibegame vlm -t /tmp/gdd-fidelity.md -s "You compare a game design document against the user's verbatim request. List every requirement the GDD omits, weakens, or contradicts. Quote both sides. If none, reply exactly: NO DEVIATION."
     ```
   - Anything but `NO DEVIATION` goes back to `designer` with the quoted lines. This check is mandatory; your own read of the GDD does not replace it — you wrote the brief it was derived from.
3. If visual elements are involved:
   - If user does not provide concept/reference image, commission `artist` to produce a **project reference image** (see artist.md → "Reference image"): a restrained single image showing the **actual in-game look** from the GDD (not concept art / mood board / poster), containing only the key elements that belong in the same real gameplay view. Later asset tasks use this image as the reference so generated player, enemy, UI, prop, and scene assets match the approved elements.
   - The reference image may contradict or extend the GDD. The lead owns the design decision and must unify them before execution: either ask `artist` to redraw the reference to match the GDD, or update the GDD to explicitly accept UI / HUD / layout / prop choices introduced by the reference image.
   - Use this reference image to validate visual direction with the user. Iterate until approved.
   - DO NOT specify frame counts or animation details - that is artist's responsibility
4. Break the goal into macro stages. Each stage should have:
   - The project state reached when the stage completes
   - How that stage outcome can be tested
   - Which earlier stages must finish first
   - Tasks that can launch together once the stage is ready
5. **Within each stage, choose independent tasks that can run in parallel.** For each task:
   - Single bounded deliverable with clear ownership
   - Clear acceptance criteria
   - No hidden dependency on another task in the same stage
   - If proposed sibling tasks share an unstable core interface, state model, scene structure, or core files, merge them into one task
6. Fill in `.vibegame/goal.md`: `## Task Breakdown` (stage plan and tasks) and `## Done When` (goal-specific, checkable outcomes — not "the game runs"). Never edit `## User Input`; when the user overrides an earlier requirement, express it in `## Done When`.
7. **Give the files for user to review. Wait for explicit user approval before execution.** The user may direct you to merge / split / drop tasks at this stage — accept their direction. Task scope is the user's decision, not yours.

Examples:

- Coherent first playable plus parallel art:
  - Stage 0: `vertical-slice` builds the playable loop; `art-pack` produces final runtime assets.
  - Stage 1: `visual-integration` swaps assets in, tunes composition, and removes temporary visuals.
  - Stage 2: `final-review` verifies the complete goal.
- Interface-first parallel systems:
  - Stage 0: Orchestrator writes stable scene, event, collision, and data interfaces into the task specs; `player`, `boss`, and `map` implement fully parallel systems against those interfaces; each task includes a standalone test scene.
  - Stage 1: `system-integration` connects the systems and resolves cross-system feel.
  - Stage 2: `asset-replacement` swaps placeholder visuals for final assets.

> DO NOT spawn reviewer in this stage, otherwise you cannot stop and request for user approval.

---

## Phase 2: Run

Delegate to teammates and supervise through to completion.

1. Spawn a reviewer agent as a **persistent team member** in the VibeGame build workflow. This reviewer stays alive for the entire session -- do NOT spawn a new reviewer per stage or per request. All review requests go to this same instance. Tell it: "You are in the VibeGame build workflow, the user's goal is ..." and reviewer need to do:
   1. Create `.vibegame/review-lock.json` with `{"locked": true}`, and never release it before final goal is achieved
   2. Learn about the detailed goal and plan from `.vibegame/goal.md`, `.vibegame/GDD.md`, and relevant specs to understand the goal before any review begins.
   3. Learn about the current codebase and wait for the final review request.
2. For each stage:
   - Create and initialize all tasks with `vibegame lead task create / init`
   - **Spawn parallel programmer agents for independent tasks** -- do NOT wait for one to finish before starting the next if they have no dependencies. Use `--blocked-by` to declare dependencies.
   - Follow `.vibegame/orchestrator.md` for the full task pipeline (architect → programmer → auditor → player)
   - After the stage is complete, update the progress checklist in `.vibegame/goal.md`
3. After all stages are complete, notify the reviewer that all tasks are done and request final review. Use the review request message format in `src/.vibegame/orchestrator.md` `## Use reviewer for final quality gate`.
4. Wait for the reviewer verdict. After done, read the verdict via `vibegame lead read --name reviewer`. The reviewer will release the lock after approving the final goal. If rejected, address feedback and request review again (same message format, updated evidence). Remember the reviewer always has to review all final quality gates instead of just checking new fixes.

---

## Rules

- **Never implement directly** unless the change is a trivial few-line edit.
  - Lead owns understanding, architecture, and supervision — not code.
- **Reviewer is persistent**: spawn it ONCE at session start, send all review requests to the same instance. Never spawn a second reviewer.
  - Reviewer does **not** do per-stage reviews. It only reviews once at the end after all tasks are done.
  - review-lock.json is owned by the reviewer agent, not the lead.
  - Keep stages macro-level. Detailed implementation belongs to architect and programmer agents.
- **Maximize parallelism**: spawn independent programmer agents simultaneously. Waiting sequentially for tasks that could run in parallel wastes the team's capacity.
- Use `vibegame lead task create --blocked-by` to declare dependencies. Tasks without blockers should start immediately.
- Follow `.vibegame/orchestrator.md` once execution begins.

## Useful Commands

```sh
vibegame lead task create "<description>" --name <name>
vibegame lead task init "<name>" --use-worktree
```

## review-lock.json

This file is created by the reviewer on spawn and is released only after the final goal is approved. It is not a stage-gate mechanism.
