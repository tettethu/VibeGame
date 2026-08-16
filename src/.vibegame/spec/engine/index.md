# Engine Quick Guide

This is the first engine document to read for game-code tasks.

Read this before touching runtime code, scenes, or game testing.

## What This Engine Provides

Vibegame is a thin game framework on top of **Phaser 3 (CE)**.

It exists to provide a few stable primitives for AI-driven game development:

1. Node tree and lifecycle.
   - All game scripts extend `Node`.
   - Runtime order is stable: `ready()`, `update(dt)`, `destroy()`.

2. Declarative scene building.
   - Scene JSON describes nodes, visuals, colliders, scripts, and config.
   - The engine instantiates the scene tree and wires the runtime automatically.

3. Declarative visual and physics setup.
   - `visual` creates `visualObject` before `ready()`.
   - `collider` creates and configures the physics body before `ready()`.
   - `collider.host: "separate"` creates a stable physics host plus a separate visual object. Use this when animation frames vary a lot in size.
   - `visualTransform` offsets the visual object relative to the node transform/physics host.

4. Reusable node definitions.
   - `.node.json` files can be reused through `"src"`.
   - Prefer this over duplicating scene fragments.

5. Asset preload and project boot.
   - `project.json` defines the project entry.
   - `project.json.manifests` (or `assets/manifest.json`) defines preload assets.
   - `config/input-map.json` defines logical input actions.

6. Built-in runtime testing.
   - `vibegame run` starts the runtime with the runtime bridge.
   - `vibegame play` CLI wraps Runtime API for frame control, input injection, snapshots, screenshots, eval, console, and more.

7. Runtime config injection.
   - `project.json.runtimeDefaults` declares dev/deploy defaults (`appBasePath`, `apiBaseUrl`).
   - Server injects `window.__APP_CONFIG__` into `index.html` at serve time.
   - `boot.js` reads `appBasePath` to resolve resource paths; game scripts read `apiBaseUrl` for API requests.
   - `vibegame run` does not provide a `/game/...` static alias; project files use the same URLs as `python -m http.server`.
   - Priority: query param > scene config > injected config > same-origin fallback.

8. Release branch generation.
   - `vibegame release` generates a pure deployment branch from allowlisted runtime roots + manifest-selected assets.
   - Uses temporary git worktree (no pollution of dev branch).
   - Fails fast on `assets/artifacts` references.
   - Projects can extend roots via `project.json.releaseExtraRoots`.

## Default Rules

- Reuse engine primitives first. Do not rebuild systems the engine already owns.
- Prefer scene data and declarative fields over manual Phaser setup.
- Keep gameplay logic in scripts. Keep structure in scene and config files.
- Use `vibegame run` for runtime verification.
- Use Runtime API for game testing instead of direct browser automation.

## Node vs Non-Node

Not everything should be a `Node`.

Use `Node` when the code needs engine-owned lifecycle or world integration:
- it needs `ready()`, `update(dt)`, or `destroy()`
- it belongs in the scene tree
- it owns or depends on `gameObject`, `collider`, transform, camera, or scene events
- it should be discoverable through scene queries, tags, or Runtime API snapshots

Use plain JS modules when the code is mostly logic:
- AI decision logic
- pure UI state machines
- data transforms, reducers, formatters, validation
- economy, combat, pathfinding, or other pure rules
- API clients, persistence adapters, or utility services

The rule is not "everything is a Node".
The real rule is "everything important must stay observable".

If non-Node code controls user-visible or acceptance-critical state, expose that state back to the engine through a host Node.

Preferred pattern:
- keep the logic in plain JS
- let a host Node own lifecycle and wiring
- return important values from `runtimeState()`

Examples of state that should be exposed:
- active panel or modal
- selected entity or command target
- current tutorial step
- HUD values that matter for acceptance
- AI mode, phase, or pending action

## How To Use The Engine

### 1. Put data in the right layer

- `project.json`: game boot config, start scene, physics, canvas size, runtimeDefaults, releaseExtraRoots.
- `scenes/*.scene.json`: node tree and per-node config.
- `nodes/*.node.json`: reusable node definitions referenced by `"src"`.
- `scripts/*.js`: gameplay logic that extends `Node`.
- `assets/manifest.json` (or `project.json.manifests`): preloadable assets.
- `config/input-map.json`: action names used by gameplay and Runtime API.
- `index.html`: page entry point with `window.__APP_CONFIG__` fallback.

### 2. Follow the preferred implementation order

When adding a feature, check in this order:

1. Can this be expressed in scene JSON or node config.
2. Can `visual` or `collider` handle it declaratively.
3. Can an existing node be reused via `"src"`.
4. Does gameplay logic belong in a `Node` script.
5. Only if the above cannot solve it, inspect deeper engine specs.

### 3. Test the game the engine way

Use:

```bash
vibegame run .          # start runtime
vibegame play activate  # pause and take control
```

For runtime validation:

- use `vibegame play snapshot` to inspect state
- use `vibegame play input -a <action>` to simulate actions
- use `vibegame play continue -f N` to advance frames
- use `vibegame play screenshot` for visual evidence
- use `vibegame play eval <code>` to inspect engine internals
- use `vibegame play refresh` to reload after code changes

Do not use Playwright or `agent-browser` to test in-game behavior directly.

## Do Not

- Do not create a parallel runtime boot flow.
- Do not bypass `vibegame run` when testing the game.
- Do not recreate `gameObject` / `visualObject` if `visual` already exists.
- Do not recreate physics bodies if `collider` already exists.
- Do not duplicate reusable nodes instead of using `"src"`.
- Do not use Phaser 2 APIs. This engine runs on Phaser 3. Common mistakes: `game.add.sprite()` (v2) vs `this.scene.add.sprite()` (v3), `game.physics.arcade` (v2) vs `this.scene.physics` (v3).
- Do not build custom solutions for things the engine already provides (spawning, collision, animation, tilemap). Read the matching guide first; only roll your own when the engine genuinely cannot cover it.

## Engine Spec Reference

Read the guide that matches your task BEFORE writing code. Every guide below describes an engine feature you should use instead of reinventing.

| File | Covers | When to read |
|------|--------|--------------|
| `entity-guide.md` | NodeDef structure, declarative visuals/colliders, lifecycle, `instantiate()`, `src` reuse, MountPoint | Creating ANY gameplay entity (player, enemy, item, projectile, NPC) or using `instantiate()` to spawn at runtime |
| `collision-guide.md` | ColliderDef, body types, overlap, collision events, attack hitbox pattern | Adding physics, hitboxes, or collision response to any entity |
| `animation-guide.md` | Clip libraries, `playAnim()`, animator state machines | Adding sprite animations or animation-driven behavior |
| `modules.md` | `modules/` directory, `Module` filename-suffix routing, when to use modules vs scripts, subclassing and composition | Using a shipped module like `StatusBarModule` from scene JSON, subclassing a module, or writing one |
| `ui.md` | DOM UI Layer coordinates, manifest-key assets, the three UI routes, and the `Phaser.Text` ban | Planning or building any HUD, menu, score / HP indicator, or in-game UI element |
| `script-rules.md` | Script conventions, `ready()`/`update()`/`destroy()` lifecycle, declarative vs manual mode, import rules | Writing any script that extends `Node` |
| `project-setup.md` | Three-layer file structure (`project.json` → scene → NodeDef), directory layout, boot flow | Setting up a new project or understanding how files connect |
| `runtime.md` | Runtime startup and shutdown, `vibegame play`, bot testing, frame control, input, snapshots, screenshots, eval, and trace recording | Running, testing, verifying, or automating any in-game behavior |
| `deployment.md` | `runtimeDefaults`, config injection, release branch generation, server deployment | Deploying or configuring runtime environments |
| `engine-internals.md` | SceneTree, `_buildNode()`, PhaserHost internals | Integrating vibegame into a custom host (NOT for game scripts) |
| (runtime AI) | `engine/ai/Vlm.js` is the readable browser-side interface for connecting an LLM/VLM to an AI-Native Game. The shared runtime boundary and verified production Pattern live in `spec/contracts/runtime-ai.md` | Building a game with a runtime LLM/VLM |
| `tilemap-guide.md` | Tileset entry in manifest, `*.tilemap.json` format, `TileMap` Node API, `AutoTile` utility | Building a tile-grid level (Celeste-style platformer, top-down dungeon, procedural map) |

Cross-role production contracts that coordinate artist + programmer + player work (level / arena layout, status bars, overlays, ability animation packs, etc.) live separately in `../contracts/`. Start with the `contracts/` index to pick a Pattern; engine guides like `tilemap-guide.md` describe the underlying runtime API the chosen Pattern depends on.
