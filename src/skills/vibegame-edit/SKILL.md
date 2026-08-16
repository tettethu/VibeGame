---
name: vibegame-edit
description: Iterate broadly on an existing game, on top of vibegame-build. Use when the user asks to change an existing game's art style, genre, or core rules. Not for local tuning such as numbers or game feel. Orchestrator only.
---

# VibeGame Edit

For reworking an existing game, for example:

- **Style migration**: pixel art to hand-drawn, or one IP to another.
- **Genre migration**: real-time combat to turn-based tactics.
- **Rule migration**: changing a core rule, such as swapping the player and boss roles.

An edit is not a local substitution bounded by file type. Start from game design, and keep the reworked mechanics, controls, feedback, and art adding up to one coherent experience. Change whatever that requires — code, assets, config, project structure.

## Phase 1: Establish a baseline

Before editing:

1. Run `vibegame check` and record the existing project's static check results.
2. Commit the existing project files, saving the pre-edit state as a baseline commit.

Do not start a playtest, runtime API test, or review pass just to establish the baseline.

## Phase 2: Enter the general build workflow

Invoke the `vibegame-build` SKILL and follow its plan-run workflow for planning, implementation, testing, and review. Do not build a separate approval, implementation, or verification flow for edits.

In `vibegame-build`'s Plan phase, inspect the current project and understand the existing design this request touches, and how its parts connect: core loop, rules, controls, character behavior, animation, collision, feedback, UI, art style.

Ask follow-up questions grounded in that existing design and the direction the user gave, until the preferences and goals that shape the approach are clear. When different choices produce materially different experiences, do not decide for the user. Before executing, make sure the user shares your expectation of the reworked game and of the main design choices.

Work out which interdependent parts each major change touches, and fold the necessary companion changes into the same plan. For example:

- Changing a character action also means revisiting controls, states, animation, collision, effects, and hit feedback.
- Migrating a visual style or IP also means revisiting how characters, maps, items, animation, effects, and UI read together.
- Changing a rule also means revisiting goals, win/lose conditions, character behavior, UI feedback, and the AI involved.

Theme, IP, and genre are design directions, not a boundary that limits the edit to swapping assets. Design the characters, abilities, presentation, and rule adjustments that fit. Do not claim an edit is assets-only, code-free, or gameplay-preserving before inspecting the project.

To reproduce the multi-stage generation behind an existing asset or animation, check the generation records in `assets/artifacts/raw` and `.vibegame/logs/imagegen.jsonl`.
