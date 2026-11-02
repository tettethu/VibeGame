# Godot Engine Guide

This project runs on **Godot 4.x** with **GDScript**. It is not a Phaser/web project: there is no `index.html`, no `engine/*.js`, no `.scene.json` and no `modules/` catalogue. Use Godot scenes (`*.tscn`), scripts (`*.gd`) and resources (`*.tres`) instead.

## Project layout

```
project.godot              Engine settings, entry scene, autoloads
project.json               VibeGame metadata (engine, canvas size, start scene)
scenes/main.tscn           Entry scene (run/main_scene)
scripts/main.gd            Entry script
scripts/                   Gameplay scripts
scenes/                    Additional scenes
assets/                    Imported textures, audio, fonts
config/input-map.json      Optional action-name metadata for agents
addons/vibegame_bridge/    Runtime control bridge (do not rewrite)
.vibegame/                 GDD, specs, runtime logs
```

`project.json` is the only VibeGame-specific file at the project root. The engine identifier is `godot@<version>`; the CLI uses it to choose the Godot runtime instead of the Phaser runtime.

## Scene and script rules

- Every `.gd` file starts with `extends <Type>`. A script attached to a node must extend that node's type or a compatible base.
- Lifecycle: `_ready()` once after entering the tree; `_process(delta)` per rendered frame; `_physics_process(delta)` per physics tick; `_unhandled_input(event)` for gameplay input after UI.
- Use `@onready var foo: Node = $Path` for scene references. Do not look up nodes by string every frame.
- Prefer typed variables (`var speed: float = 220.0`) and typed function signatures. Typed GDScript catches errors at parse time and runs faster.
- Signals are the default decoupling tool: `signal died(enemy)` / `died.emit(self)` / `enemy.died.connect(_on_enemy_died)`.
- Keep gameplay state on the owning node and expose a `vibegame_state() -> Dictionary` method. The runtime snapshot includes it, which is how automated verification reads game state.
- Never call `get_tree().quit()` from gameplay code unless the task is explicitly about exiting.
- Do not use `get_tree().paused` for a game's own pause menu; the runtime bridge owns that flag for frame stepping. Use a local `game_paused` flag and return early from update logic.

## Drawing without assets

The starter and many prototypes draw with `CanvasItem`:

```gdscript
func _process(_delta: float) -> void:
    queue_redraw()

func _draw() -> void:
    draw_circle(Vector2(100, 100), 24.0, Color("#ffb347"))
    draw_rect(Rect2(20, 20, 80, 40), Color.WHITE, true)
    draw_string(ThemeDB.fallback_font, Vector2(20, 200), "Hello", HORIZONTAL_ALIGNMENT_LEFT, -1, 20, Color.WHITE)
```

Call `queue_redraw()` whenever drawn state changes. For animated visuals, call it once per frame in `_process`.

For CJK text, use a `SystemFont` so the game does not need a bundled font:

```gdscript
var font := SystemFont.new()
font.font_names = PackedStringArray(["PingFang SC", "Hiragino Sans GB", "Noto Sans CJK SC", "Microsoft YaHei"])
```

Use the font in `draw_string` and on `Label`/`Button` `theme_override_fonts/font`.

## UI

- `Control` nodes are the UI layer. Set anchors and offsets in the `.tscn`; do not hardcode pixel positions for layouts that must scale.
- Buttons: use `Button` + `pressed` signal for real UI; draw custom buttons in `_draw()` only when the game has a fully custom art direction, and implement hit rectangles in `_unhandled_input`.
- The default Godot theme is acceptable for prototypes. For a shipped look, set a project-wide `Theme` resource on the root `Control`.
- HUD text must use a font that covers the project language. The default font does not include CJK glyphs.

## Input

- Real game input actions belong in `project.godot` `[input]` and are read with `Input.is_action_pressed("move_left")`.
- The runtime bridge can inject actions by name (`vibegame play input --action move_left`). The name must exist in `project.godot` `[input]`; `config/input-map.json` documents the names for agents.
- Mouse/touch: `_unhandled_input(event)` receives `InputEventMouseButton` and `InputEventScreenTouch` after UI consumes its events.

## Runtime bridge

`addons/vibegame_bridge/bridge.gd` is an autoload that listens on `127.0.0.1:<port>` and speaks line-delimited JSON. The CLI passes the port with `--vibegame-bridge=<port>` after `--`:

```sh
godot --path . -- --vibegame-bridge=35700
```

`vibegame godot run` starts both the game and a small HTTP adapter, then `vibegame play` talks to the adapter exactly as it does for Phaser projects.

Supported bridge commands:

| Command | Purpose |
|---|---|
| `ping` | Liveness and Godot version |
| `status` | `{active, paused, frame, stepRemaining}` |
| `snapshot` | Scene tree, node positions/visibility, `vibegame_state()` |
| `screenshot` | Viewport PNG as base64 (visible window required) |
| `eval` | Evaluate a GDScript `Expression` against the current scene |
| `set` | Set a node property (`nodeId`, dotted `path`, `value`) |
| `click` / `mousemove` / `drag` | Mouse events in viewport coordinates |
| `key` | Keyboard events (`Space`, `ArrowLeft`, `KeyA`, `Digit1`, ...) |
| `input` | `InputEventAction` by action name |
| `activate` / `deactivate` | Runtime control mode (pause at frame 0) |
| `pause` / `play` / `continue` | Freeze, resume, or advance N frames then pause |
| `refresh` | Reload the current scene |
| `console_get` / `console_clear` | Ring buffer fed by `VibeGameBridge.log_line()` |

Game code can log:

```gdscript
VibeGameBridge.log_line("wave 3 started")
```

### Frame stepping caveats

- The bridge pauses via `get_tree().paused`. Nodes with the default `PROCESS_MODE_INHERIT` stop processing; nodes marked `PROCESS_MODE_ALWAYS` keep running.
- `continue --frames N` resumes the tree for N frames, then pauses.
- Screenshots are captured from the viewport texture, so they need a real rendered window. `vibegame godot run --headless` is for logic/CI only; use the visible runtime for visual verification.

## Verification workflow

From the project root:

```sh
vibegame godot check                 # static checks + GDScript parse + headless boot
vibegame godot run --port auto       # visible game + runtime API
vibegame play snapshot               # structured state
vibegame play screenshot -o /tmp/shot.png
vibegame play click -x 640 -y 360
vibegame play continue -f 120        # advance two seconds at 60 fps
```

Use `vibegame godot run --background` for automation; `vibegame close` stops it. Runtime logs live in `.vibegame/logs/runtime/server-<port>.log`.

## Performance rules

- Do not call `get_node()` or `find_child()` in `_process`; cache references in `_ready()`.
- Prefer `_physics_process` for movement that must be frame-rate independent; use `delta` consistently.
- Avoid per-frame allocations in hot loops (string concatenation, array literals, `JSON.stringify`). Reuse arrays/dictionaries where practical.
- For many bullets/enemies, keep objects as plain `Node2D`s with `_draw()` and update arrays in one manager rather than deep scene trees.
- Cap particle/effect counts; a few dozen is enough for 2D game feel.

## Assets

- Import files through `assets/`. Godot `.import` files are generated and must not be hand-edited.
- Pixel art: set the texture filter to nearest in the import dock or via `ProjectSettings` (`rendering/textures/canvas_textures/default_texture_filter=0`).
- Audio: use `AudioStreamPlayer` for SFX and `AudioStreamPlayer` with looping for music.
- Register every runtime-relevant asset in `.vibegame/assets.md` when it becomes part of the shipped game.
