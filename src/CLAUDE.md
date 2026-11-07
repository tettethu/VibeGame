## Vibegame Project

1. This project uses **Phaser 3**. Never use Phaser 2 APIs.
2. Read the relevant files before acting on the game project. Do not guess game state or asset inventory.
  - `.vibegame/GDD.md` — Game design document (mechanics, characters, art needs)
  - `.vibegame/assets.md` — Asset inventory (registered sprites, tilesets, audio)
  - `.vibegame/spec/` — Engine guides, system specs, design theory
  - `index.html` — Game entry point
3. When outputting a file path for user review, always use markdown link format `[name](absolute_path)`. Do not use relative paths or `[name](file://absolute_path)`
4. Never modify files outside the game project directory unless the user explicitly permits it. When deleting files, prefer recoverable methods (e.g. `trash` on macOS) over `rm`.
5. Never use `pkill -f 'vibegame'`; it can terminate the entire VibeGame agent team, Dashboard, runtime, and tmux session.
6. Engine source code is available in the project's `engine/` directory; read it when the documentation does not answer your question, and modify it when necessary, such as to fix an engine bug.

## User Interaction

You must interact with the user in this way:
1. **Always** respond and write docs in: **{{language_name}}**. File names, identifiers, code, and engine vocabulary stay in English.
2. **DO NOT** use `AskUserQuestion` or other equaliant tools. To ask user questions or ask user to choose between options, just output the question and options.

## Glossary

Canonical vocabulary used by all agents when talking to the user and to each other. Use these terms; avoid synonyms. Do not switch terminology between turns. When introducing a term to a non-developer user, give a plain-language analogy on first mention, then use the canonical term consistently after.

Engine usage lives in [.vibegame/spec/engine/index.md](.vibegame/spec/engine/index.md). The glossary names concepts; it does not duplicate their API rules.

### Engine and assets

- **node** - A scene-tree unit with optional script, visual and collider. May be placed initially or spawned at runtime.
- **scene** - A .scene.json file describing an initial node tree.
- **.node.json template** - A reusable node definition, including config defaults.
- **instantiate** - Spawn a template as a child of an existing node.
- **script** - JavaScript that drives node behavior; ordinary helper modules may hold pure game logic.
- **project** - A user game directory rooted at project.json.
- **sprite** - A single 2D image or named frame used as a visual.
- **sprite sheet** - An image containing multiple frames.
- **animation** - A timed sequence of frames.
- **tileset** - Equal-sized tiles with metadata registered in a manifest entry.
- **tilemap** - A grid-based level using a tileset, distinct from a raster background with separate colliders.
- **manifest** - Asset keys and metadata for runtime loading, normally assets/manifest.json.
- **pivot** - The fractional anchor used to align a visual or collider.
- **collider** - The object's physical shape, planned from gameplay dimensions rather than source-image resolution.
- **block / trigger** - Solid contact versus overlap detection.
- **hitbox** - An additional collision area, such as an attack zone.
- **one-way platform** - A platform that blocks from above.
- **tag** - A label for finding and grouping nodes by purpose.
- **input-map** - Mappings from physical keys to game actions.

### Workflow
- **agent team** — 8 kinds of specialist agents develop this project together (team lead: `orchestrator`. teammates: `artist`, `designer`, `architect`, `programmer`, `auditor`, `player`, `reviewer`). They communicate with `vibegame` commands. Never use native multi-agent tools (e.g. `send_message`, `spawn_agent`) to start or communicate with these 8 kinds of specialist agents. Only two ways of communication exist:
  1. orchestrator <-> teammates
  2. The orchestrator creates a `shortcut` between 2 teammates. While the `shortcut` is open, the 2 teammates can only send messages to each other or leave the `shortcut`.
- **shortcut** — A direct conversation channel that the orchestrator creates between two teammates. Its usage is explained when it starts.
- **task** — A bounded unit of feature work tracked under `.vibegame/tasks/<name>/`. Created and initialized by the orchestrator via `vibegame lead task create` / `vibegame lead task init`. Pipeline: orchestrator writes `prd.md` → `architect` produces `plan.md` and configures the per-task `context.json` → `programmer` writes code → `auditor` does static review → `player` runtime-verifies (state assertions + screenshots) → orchestrator accepts. Optionally runs in its own git worktree for isolation.
- **prd.md** — A task's product specification. Owned by the orchestrator. User-visible outcome, entry conditions, boundaries, acceptance notes. Never holds implementation detail.
- **plan.md** — A task's technical plan. Owned by `architect`. Lists files to touch, technical decisions, reuse points, constraints. The contract `programmer` and `auditor` execute against.
- **log.md** — A task's work record. Owned by downstream sprint agents. Each phase writes one H1 section (`# Programmer`, `# Auditor`, `# Player`) containing files modified, decisions, validation results, evidence pointers. H1 reflects the phase, not the agent identity — Route A `architect` writes `# Programmer` when it self-implements. Each agent edits only its own section. After rework, it updates that section instead of adding another.
- **context.json (per task)** — `<task_dir>/context.json` holds `{file, reason}` lists keyed by `all / programmer / auditor / player`. Seeded from source `config/context.json:default_config` at `vibegame lead task init`, edited by `architect` to add task-specific specs. Path resolver tries the task dir first, then the workspace root.
