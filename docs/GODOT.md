# Godot Engine Support (Experimental)

VibeGame's primary engine is Phaser. This document covers the experimental
**Godot 4** companion: a self-contained `vibegame godot` command group that
scaffolds, runs and verifies Godot projects without touching the existing
Phaser workflow.

## What works

| Capability | Status |
|---|---|
| `vibegame godot init` | Scaffolds a Godot 4 project with the runtime bridge |
| `vibegame godot run` | Launches Godot + a `/api/runtime/*` adapter |
| `vibegame play ...` | Works unchanged: snapshot, screenshot, click, key, eval, pause, continue |
| `vibegame godot check` | Required files, project.godot, headless boot and GDScript parse |
| `vibegame close` | Stops a tracked Godot runtime |
| `vibegame godot doctor` | Locates the Godot binary and reports versions |

Not implemented yet:

- The multi-agent `/vibegame-build` workflow and art pipeline are Phaser-oriented.
  Godot projects are currently driven directly by the user or an agent editing
  `.gd` / `.tscn` files.
- `vibegame release` / HTML5 export packaging.
- Dashboard asset preview.
- Deterministic frame stepping parity with the Phaser `RuntimeClock` (the Godot
  bridge steps the real scene tree instead of a fake clock).

## Requirements

- Godot 4.7 or newer on `PATH`, or `GODOT_BIN` set, or `--godot <path>`.
- Python 3.12+ (the same `vibegame` install used for Phaser).

```sh
# macOS
brew install --cask godot

# verify
vibegame godot doctor
```

## Quick start

```sh
mkdir carrot-defense && cd carrot-defense
vibegame godot init --name "Carrot Defense" --lang zh-CN
vibegame godot check
vibegame godot run --port auto
```

In another terminal:

```sh
vibegame play snapshot
vibegame play screenshot -o /tmp/shot.png
vibegame play click -x 640 -y 360
vibegame play continue -f 60
vibegame close
```

Background mode is meant for automation:

```sh
vibegame godot run --port auto -b
vibegame godot run --status
vibegame godot run --logs
vibegame close
```

## Project layout

```
project.godot              Godot settings; run/main_scene + VibeGameBridge autoload
project.json               VibeGame metadata: engine "godot@<version>", canvas size, start scene
scenes/main.tscn           Entry scene
scripts/main.gd            Entry script
addons/vibegame_bridge/    TCP JSON runtime bridge (autoload)
assets/                    Imported textures, audio, fonts
.vibegame/                 GDD, assets, Godot spec, runtime logs
```

`project.json` is the only file shared with the Phaser layout. The CLI routes
`vibegame godot ...` commands by reading `engine`. `vibegame run` refuses a Godot
project with a pointer to `vibegame godot run`, so a Playwright runtime never
tries to load a `.tscn` project.

## Runtime architecture

```
vibegame play  --HTTP-->  godot_runtime.py  --TCP JSON-->  bridge.gd (in game)
```

- The bridge autoload listens on `127.0.0.1:<port>`. The CLI passes the port via
  Godot user args: `--path . -- --vibegame-bridge=35700`.
- `godot_runtime.py` exposes the same `/api/runtime/*` endpoints that the Phaser
  runtime exposes, so `vibegame play` and its traces need no Godot-specific code.
- The runtime is tracked in `.vibegame/logs/runtime/servers.json`, which is what
  `vibegame close` and `--status` read.

### Bridge commands

| Command | Purpose |
|---|---|
| `ping` / `status` | Liveness, paused state, frame count, remaining step frames |
| `snapshot` | Scene tree, node positions, visibility, `vibegame_state()` |
| `screenshot` | Viewport PNG as base64 |
| `eval` | Evaluate a GDScript `Expression` against the current scene |
| `set` | Set a node property by node id and dotted path |
| `click` / `mousemove` / `drag` | Mouse input in viewport coordinates |
| `key` | Keyboard input (`Space`, `ArrowLeft`, `KeyA`, `Digit1`, ...) |
| `input` | `InputEventAction` by action name |
| `activate` / `deactivate` | Control mode: pause at frame 0 / resume |
| `pause` / `play` / `continue` | Freeze, resume, advance N frames then pause |
| `refresh` | Reload the current scene |
| `console_get` / `console_clear` | Messages written with `VibeGameBridge.log_line()` |
| `network_get` / `network_clear` | Empty compatibility endpoints |

Game code reports state for automated checks:

```gdscript
func vibegame_state() -> Dictionary:
    return {"gold": gold, "wave": wave, "carrot_hp": carrot_hp}
```

`vibegame play snapshot` includes that dictionary under the node's `state` key.

## Checking

`vibegame godot check` verifies:

- `project.json` shape and `engine: "godot@x.y.z"`.
- `project.godot` exists, uses `config_version=5`, and has `run/main_scene`.
- The entry scene and the `VibeGameBridge` autoload exist.
- Every `.gd` file is under the project and the project boots headless
  (`godot --headless --path . --quit-after 3`), which compiles scripts with
  autoloads in scope. Parse errors are reported as errors.
- Missing Godot binary is a warning; install Godot or pass `--godot`.

`vibegame check` auto-detects a Godot project and runs the same checks.

## Limits worth knowing

- **Screenshots need a visible window.** `--headless` cannot render the viewport;
  the adapter returns a clear 500 error instead of a blank image.
- **`eval` is GDScript, not JavaScript.** It uses Godot's `Expression` parser, so
  it evaluates expressions, not statements. Use `snapshot` for state.
- **Pause ownership.** The bridge uses `get_tree().paused` for control mode. Game
  code should keep its own pause flag instead of toggling the tree.
- **Scene reload.** `refresh` reloads the current scene; it does not restart the
  Godot process. Restart the runtime if you need autoload state reset.
- **Packaging.** Like the Phaser engine, the Godot template lives in the VibeGame
  checkout; the supported installation is editable (`./setup.sh`). A non-editable
  wheel is not self-contained.
