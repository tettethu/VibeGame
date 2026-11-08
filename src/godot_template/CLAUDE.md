# Godot Project

1. This project uses **Godot 4.x with GDScript**. Do not use Phaser, JavaScript engine APIs, `index.html`, or `.scene.json` files here.
2. Read the relevant files before acting. Do not guess project state or asset inventory.
   - `.vibegame/GDD.md` — Game design document (mechanics, characters, art needs)
   - `.vibegame/assets.md` — Asset inventory
   - `.vibegame/spec/godot/` — Godot engine guide and runtime bridge contract
   - `project.godot` — entry scene, autoloads, display settings
3. The game entry point is the scene named by `run/main_scene` in `project.godot` (normally `res://scenes/main.tscn`). Scene files use the `.tscn` format; scripts use `.gd`.
4. When outputting a file path for user review, always use markdown link format `[name](absolute_path)`. Do not use relative paths or `[name](file://absolute_path)`.
5. Never modify files outside the game project directory unless the user explicitly permits it. When deleting files, prefer recoverable methods (e.g. `trash` on macOS) over `rm`.
6. The `VibeGameBridge` autoload (`res://addons/vibegame_bridge/bridge.gd`) is the runtime-control channel used by README workflows. Keep it intact unless the task is explicitly about the bridge.

## User Interaction

You must interact with the user in this way:
1. **Always** respond and write docs in: **{{language_name}}**. File names, identifiers, code, and engine vocabulary stay in English.
2. **DO NOT** use `AskUserQuestion` or other equivalent tools. To ask the user questions or ask them to choose between options, just output the question and options.

## Engine Vocabulary

- **scene** — a `.tscn` file; the unit Godot loads.
- **node** — the building block of a scene tree. Nodes have a type (`Node2D`, `Sprite2D`, `Control`, ...) and optional script.
- **script** — a `.gd` file attached to a node. `_ready()` runs once; `_process(delta)` runs per frame.
- **autoload** — a global singleton registered in `project.godot`. This project uses `VibeGameBridge`.
- **CanvasItem drawing** — `_draw()` plus `queue_redraw()` for immediate-mode 2D rendering without texture assets.
- **runtime bridge** — the line-delimited JSON TCP server in `addons/vibegame_bridge/bridge.gd`; `vibegame play` uses it for snapshots, screenshots, input and frame stepping.

## Verification

Use the CLI from the project root:

```sh
vibegame godot check
vibegame godot run --port auto
vibegame play screenshot -o /tmp/shot.png
vibegame play snapshot
vibegame play click -x 640 -y 360
```

`vibegame play` commands work for Godot projects through the runtime bridge. Screenshots require a visible Godot window; `--headless` runs cannot capture the viewport.
