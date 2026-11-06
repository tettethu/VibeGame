# Prototype / Polish Contract

The default workflow for building a game from scratch (greenfield): implement the complete gameplay with placeholder assets, then integrate real art in a polish task. Real-art-from-day-one tasks and disposable experiments need not use it.

The [engine guide](../engine/index.md#assets-and-polish) owns manifest formats, world-size authoring and art replacement. Its [animation section](../engine/index.md#animation) owns the animation setup. Each agent's system prompt already defines the basic workflow and the split of responsibilities. This contract only adds the workflow decisions and handoffs that are specific to this workflow.

## Pattern 1: Basic

### When to use

Default workflow for greenfield projects that have no existing asset pack.

### Responsibility

#### Orchestrator

- Organize development into two tasks: prototype, then polish.
- Assets that can be decided in advance: the artist can produce them in parallel with the prototype task.
- The full shape of the game is unknown until the prototype is done, and it may change during development. New asset needs can therefore appear during development. Handle them flexibly.
- Make sure that all required assets are complete before the polish task starts. New asset needs can also appear during the polish task. Route them to the artist.
- By default, the polish task reuses the task agents of the prototype task, so that they keep their context.

---

#### Architect/Programmer

- Prototype task:
  - Organize the visuals so that they are easy to migrate to real assets. For example, placeholder art registered in `manifest.json` is easier to migrate in the polish task than placeholders drawn outside the manifest.
  - Animation frame counts in the prototype are placeholders only. Use 4 by default, and later change them to the frame counts of the delivered assets.
- Polish task:
  - The delivered real assets can differ from the proportions and sizes planned in the prototype. Follow the **delivered assets**: asset production is unpredictable, and it is much easier to change code than to change assets.
  - Report missing assets promptly. If a missing asset affects further planning or implementation, report with `--over` and wait while the orchestrator arranges the asset production. The orchestrator then sends a message that tells you to continue planning or implementation.
- Make sure that no placeholder entries remain.

#### Player

- Prototype task: placeholders are allowed. Focus first on functional correctness and visual layout.
- Polish task: distinguish debug-mode bboxes from placeholders. Debug bboxes are for reviewing object properties. Placeholders are not allowed in the polish task.