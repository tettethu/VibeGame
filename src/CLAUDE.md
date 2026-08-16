## Vibegame Project

1. This project uses **Phaser 3 (CE)**. Never use Phaser 2 APIs.
2. Read the relevant files before acting on the game project. Do not guess game state or asset inventory.
  - `.vibegame/GDD.md` — Game design document (mechanics, characters, art needs)
  - `.vibegame/assets.md` — Asset inventory (registered sprites, tilesets, audio)
  - `.vibegame/spec/` — Engine guides, system specs, design theory
  - `index.html` — Game entry point
3. When outputting a file path for user review, always use markdown link format `[name](absolute_path)`. Do not use relative paths or `[name](file://absolute_path)`
4. Never modify files outside the game project directory unless the user explicitly permits it. When deleting files, prefer recoverable methods (e.g. `trash` on macOS) over `rm`.

## User Interaction

You must interact with the user in this way:
1. **Always** respond and write docs in: **{{language_name}}**. File names, identifiers, code, and engine vocabulary stay in English.
2. **DO NOT** use `AskUserQuestion` or other equaliant tools. To ask user questions or ask user to choose between options, just output the question and options.


## Glossary

Canonical vocabulary used by all agents when talking to the user and to each other. Use these terms; avoid synonyms. Do not switch terminology between turns. When introducing a term to a non-developer user, give a plain-language analogy on first mention, then use the canonical term consistently after.

### Engine primitives
- **node** — A unit in the scene tree, optionally driven by a script. A node can be placed at scene load time (declared in scene JSON) **or spawned at runtime** via `instantiate()` — both are equally first-class. Bullets, enemies, pickups, projectiles, particles are normally runtime-spawned, not pre-placed. Similar in concept to a Unity GameObject or a Godot Node, but the API is different — do not call it `entity`, `actor`, `GameObject`, or `prefab`.
- **scene** — A `.scene.json` file containing the initial node tree plus startup configuration. The runtime loads one scene at a time. Runtime-spawned nodes are added on top of this initial tree.
- **`.node.json` template** — A reusable node definition file (visual + collider + script + config defaults). The vibegame equivalent of a prefab. Used with `instantiate()` to spawn dynamic content (bullets, enemies, pickups). Procedural content **must** use a template — never assemble nodes from raw objects.
- **instantiate** — The runtime action of spawning a `.node.json` template as a child of an existing node: `await this.instantiate('entities/bullet.node.json', { x, y })`. The standard way to create anything dynamic.
- **script** — A JS file under `scripts/` that extends `Node` (from `engine/Node.js`) and drives one node's behavior. Scripts used by runtime-instantiated nodes must be registered (manually or via a disabled placeholder node) so the engine can find them. Not a Unity MonoBehaviour.
- **project** — A user game directory rooted at `project.json`. Contains scenes, scripts, assets, and config.

### Assets
- **sprite** — A single 2D image, usually one PNG.
- **sprite sheet** — A PNG containing multiple frames laid out in a grid (animation frames or direction variants in one image).
- **animation** — A timed sequence of frames, typically sliced from a sprite sheet.
- **tileset** — A set of equal-sized tile images plus tile metadata (collision, auto-tile rules). One PNG paired with one `.tileset.json`.
- **tilemap** — A grid-based level authored with a tileset. One `.tilemap.json`. Distinct from a free-placed sprite scene.
- **manifest** — `assets/manifest.json`. Declares which assets the runtime should preload.
- **pivot** — Fractional anchor `[x, y]` in `0..1`, `[0,0]` = top-left. Applies to both visual (sprite/atlas) and collider. **Visual pivot** (in manifest or `animations.clips.<n>.pivot`) determines Phaser sprite origin so per-frame bbox size changes don't visually shift the character; default `[0.5, 1]` (bottom-center). Cascade: clip-level > manifest sprite-level (`<asset>.sprites.<frame>.pivot`) > manifest group-level (`<asset>.pivot`) > default. **Collider pivot** (`collider.pivot` in node.json) determines where on the collider box the anchor sits; defaults to inherit the visual sprite's resolved origin, so feet-anchored sprites get feet-aligned bodies for free. Cascade: explicit `colliderDef.pivot` > visual sprite origin > `[0.5, 0.5]`. Circle shape defaults to `[0.5, 0.5]` regardless. See [animation-guide.md#pivot](.vibegame/spec/engine/animation-guide.md) and [collision-guide.md#pivot](.vibegame/spec/engine/collision-guide.md).

### Behavior
- **collider** — A shape (`box` or `circle`) attached to a node for physics and overlap detection. Modes: `static` (Arcade StaticBody: not velocity/gravity driven and not pushed by collisions; intended for walls, ground, one-way platforms) or `dynamic` (Arcade Body: can move by velocity/gravity and can be pushed unless `immovable`; intended for player, enemy, projectile, moving hitbox). A `static` collider is still positioned from its node transform at creation, and child transform inheritance refreshes the body when the parent moves. If a script directly moves a static body host, call `body.updateFromGameObject()` / `refreshBody()`, or prefer `dynamic` + `immovable` for moving platforms and moving hitboxes. Set on the node via the `collider` field.
- **collision** — The runtime event when two colliders meet. The interaction style is chosen *per pair* at script time, not on the collider itself:
  - **block** (`physics.add.collider`) — the two bodies cannot overlap; they push each other apart. For walls, ground, solid enemies.
  - **trigger** (`physics.add.overlap`) — the bodies pass through each other; a callback fires while they overlap. For pickups, damage zones, sensor areas.
  Use `trackCollider` / `trackOverlap` when scripts need precise enter/exit events instead of per-frame callbacks.
- **hitbox** — An extra collision area attached as a child `Collider` node, separate from the parent's main body. Used for attack ranges, pickup zones, and sensors (a Phaser game object allows only one body, so additional zones live as child colliders).
- **one-way platform** — A `static` collider with `oneWay: true`. Blocks only from above. For platformer drop-through platforms.
- **tag** — A string label on a node (`"tags": ["enemy"]` in scene JSON). Scripts find nodes by tag via `findByTag('enemy')`. Prefer tags over hardcoded names.
- **input-map** — `config/input-map.json`. Maps physical keys to semantic actions (e.g. `Space → "jump"`). Scripts react to actions, not raw keys.

### Workflow
- **agent** — A specialist sub-process with a defined role. Persistent: `designer`, `artist`, `reviewer`. Spawned per task: `architect`, `programmer`, `auditor`, `player`. For one-shot codebase exploration the orchestrator uses Claude Code's built-in Task tool with the `Explore` subagent (or Codex equivalent) — the team backbone is reserved for stateful, multi-turn task work.
- **task** — A bounded unit of feature work tracked under `.vibegame/tasks/<name>/`. Created and initialized by the orchestrator via `vibegame lead task create` / `vibegame lead task init`. Pipeline: orchestrator writes `prd.md` → `architect` produces `plan.md` and configures the per-task `context.json` → `programmer` writes code → `auditor` does static review → `player` runtime-verifies (state assertions + screenshots) → orchestrator accepts. Optionally runs in its own git worktree for isolation.
- **prd.md** — A task's product specification. Owned by the orchestrator. User-visible outcome, entry conditions, boundaries, acceptance notes. Never holds implementation detail.
- **plan.md** — A task's technical plan. Owned by `architect`. Lists files to touch, technical decisions, reuse points, constraints. The contract `programmer` and `auditor` execute against.
- **log.md** — A task's append-only work record. Owned by downstream sprint agents. Each phase appends one H1 section (`# Programmer`, `# Auditor`, `# Player`) containing files modified, decisions, validation results, evidence pointers. H1 reflects the phase, not the agent identity — Route A `architect` writes `# Programmer` when it self-implements. Multi-round rework appends additional sections rather than overwriting.
- **context.json (per task)** — `<task_dir>/context.json` holds `{file, reason}` lists keyed by `all / programmer / auditor / player`. Seeded from source `config/context.json:default_config` at `vibegame lead task init`, edited by `architect` to add task-specific specs. Path resolver tries the task dir first, then the workspace root.
