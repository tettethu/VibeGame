# Runtime

Complete contract for starting, controlling, testing, and closing a VibeGame runtime. Use Runtime API instead of Playwright or `agent-browser` for in-game testing. Browser automation is only for non-runtime pages or browser chrome behavior.

## Start and close

```bash
vibegame run <path:-.> [--host <HOST>] [-b] [--headless] [--port <N|auto>] [--activate] [--debug] [--renderer auto|webgl|canvas] [--fps <N>] [--shot <file>] [--bot <path>] [--max-seconds <N>] [-- k=v ...]
vibegame close <path:-.> [--port <N>|--all]
```

Rules:

- Run `vibegame run`, matching `vibegame play`, and `vibegame close` from the same project or worktree root. `vibegame play` discovers servers through that root's `.vibegame/logs/runtime/servers.json`; `--port` does not switch roots.
- Always stop a runtime with `vibegame close`. Do not use `pkill`, `pgrep`, or manual process kills; tracked children such as Chromium may survive.
- Do not use Runtime API with a plain static server such as `python3 -m http.server`.
- Agent-run automated verification MUST pass `--headless`. Bot video, Runtime API screenshots, and refresh work headlessly. Omit it only when the user explicitly asks to watch or interact with the browser window.

### Parameters

| Parameter | Default | Use |
|---|---|---|
| `<path>` | `.` | Game project root. Use `.` unless task metadata gives a worktree path. |
| `--host <HOST>` | `127.0.0.1` | Bind address. Keep the default for local testing; use `0.0.0.0` only when another machine or container must connect. |
| `-b`, `--background` | off | Start the server in background and return. Use for agent verification. This does not imply headless. |
| `--headless` | off | Hide the browser window. Mandatory for automated agent testing. |
| `--port <N\|auto>` | `8765` | `auto` scans from `8765`; explicit `N` requires that exact port. Pass the selected port to `vibegame play --port <N> ...` when multiple runtimes exist. |
| `--activate` | off | Enable runtime control and pause at frame 0. Use when startup can move, damage, time out, or skip required state. |
| `--debug` | off | Show Phaser Arcade bodies for collider, hitbox, hurtbox, platform, wall, pickup, or sensor evidence. Does not edit `project.json`. |
| `--renderer <auto\|webgl\|canvas>` | `auto` | `webgl` fails loud when GPU/WebGL is unavailable. Use `canvas` only for screenshot compatibility. |
| `--fps <N>` | project `settings.fpsLimit`, else `60` | `0` is uncapped. Use `30` to reduce render cost; use `0` only to measure display-rate behavior. |
| `--shot <file>` | none, except bot default | Record the browser view. Relative paths resolve from project root. `.mp4` needs ffmpeg; `.webm` uses Playwright recording. |
| `--bot <path>` | none | Run a Python realtime bot and exit with its verdict. See `## Runtime bot`. |
| `--max-seconds <N>` | `10` | Override the bot's `META["max_seconds"]`. Applies only with `--bot`. |

`--activate` and `--debug` are independent:

```bash
vibegame run . -b --headless --activate --debug
```

Runtime screenshots use Playwright `page.screenshot`. The runtime asks Chromium on macOS to use ANGLE Metal. Use `--renderer canvas` only when the local WebGL stack produces bad screenshots.

### URL parameters

```bash
vibegame run . -b --headless -- preset=boss seed=42
```

Tokens after `--` must be `key=value`. The game reads them through `new URLSearchParams(location.search)`. Reserved keys `runtime`, `activate`, `debug`, `physicsDebug`, `renderer`, and `fps` are rejected. Bot `META["params"]` uses the same path.

### Lifecycle operations

| Command | Meaning |
|---|---|
| `vibegame run . --status` | List tracked servers, ports, alive state, foreground/background mode, PID, and address. |
| `vibegame run . --logs [--port <N>]` | Print the last 50 lines of `.vibegame/logs/runtime/server-<port>.log`. |
| `vibegame close . --port <N>` | Stop one server. Required when multiple ports run from the same root. |
| `vibegame close . --all` | Stop every tracked server for this root. |

`vibegame run -b` may be called repeatedly for the same root and port. It starts when absent, replaces a previous VibeGame server on that port, and fails if another process owns the port.

## Runtime control

`vibegame play` auto-discovers the runtime for the current project/worktree. If that root has multiple servers, put `--port` before the subcommand:

```bash
vibegame play --port "$PORT" snapshot
vibegame play --port "$PORT" screenshot -o frame.png
```

### Core commands

| Command | Meaning |
|---|---|
| `vibegame play status` | Show controller status. |
| `vibegame play activate` | Activate runtime control and pause immediately. A runtime started with `--activate` is already active. |
| `vibegame play deactivate` | Deactivate control and reset the controller. |
| `vibegame play pause` | Pause immediately. |
| `vibegame play play` | Resume free-running playback. |
| `vibegame play continue [-f N]` | Advance `N` frames and pause. Default `60`; status is `completed`, `breakpoint`, or `paused`. |
| `vibegame play snapshot` | Print the structured runtime state as JSON. |
| `vibegame play screenshot [-o FILE]` | Capture the composed viewport. Default output is a temporary file. |
| `vibegame play refresh` | Reload after code or asset changes. Works in headless and headed sessions. |
| `vibegame play console [-l LEVEL] [-s SEQ] [--clear]` | Read or clear console entries; level is `error`, `warn`, `info`, or `log`. |
| `vibegame play network [--clear]` | Read or clear network entries. |

### Input and mutation

| Command | Meaning |
|---|---|
| `vibegame play input -a ACTION [--held] [--release]` | Inject an action from `input-map.json`. |
| `vibegame play key -c CODE [-t press\|down\|up]` | Inject a raw keyboard event. Prefer mapped actions. |
| `vibegame play click -x N -y N` | Click game-world coordinates. |
| `vibegame play mousemove -x N -y N` | Move to game-world coordinates. |
| `vibegame play drag --from-x N --from-y N --to-x N --to-y N` | Drag between game-world coordinates. |
| `vibegame play set -n NODE -p PATH -v VALUE` | Set a runtime property; value parses as JSON, then string. |

```bash
vibegame play input -a move_right --held
vibegame play continue -f 30
vibegame play input -a move_right --release
vibegame play set -n player -p config.hp -v 5
```

### Snapshot

```json
{
  "frame": 120,
  "mode": "paused",
  "nodes": {
    "player": {
      "name": "Player",
      "tags": ["player"],
      "enabled": true,
      "config": {"hp": 3},
      "transform": {"x": 100, "y": 250, "scaleX": 1, "scaleY": 1, "flipX": false},
      "physics": {"vx": 0, "vy": 0, "blocked": {"down": true}},
      "runtime": {"isGrounded": true, "combo": 2}
    }
  }
}
```

`config` is node config; `transform` and `physics` appear when available. `runtime` is opt-in data returned by the script's `runtimeState()`.

### Eval

`vibegame play eval [CODE]` evaluates JavaScript in the live engine. It injects `sceneTree`, `host`, and `runtime` into an async function. Use `return` to produce a result; `undefined` becomes `null`.

Do not inspect gameplay through `window.__vibegameRuntime`; it is browser bridge plumbing, not the scene tree.

```bash
vibegame play eval 'return [...sceneTree.nodes.keys()]'
vibegame play eval 'return sceneTree.nodes.get("node_17")?.name ?? null'
vibegame play eval < code.js
```

For multiline code:

```bash
vibegame play eval <<'EOF'
const nodes = [...sceneTree.nodes.values()];
return nodes.map(n => ({id: n.id, name: n.name, tags: n.tags}));
EOF
```

### Batch

`vibegame play batch` runs many commands in one process, avoiding roughly 0.5s of Python startup per command. Use batch for known scenarios and step-by-step commands when each result determines the next action.

```bash
vibegame play --port "$PORT" batch <<'OPS'
activate
eval const b=sceneTree.nodes.get('ball'); b.resetForTest(160,40); return b.runtimeState().y
continue -f 20
snapshot
OPS

vibegame play --port "$PORT" batch @ops.txt
```

Lines may start with `run ` or `vibegame play `. Blank lines and comments are skipped. Everything after `eval` is raw JavaScript; `eval @file.js` loads a file. Batch stops at the first failure, reports the operation and current snapshot, and exits non-zero.

## Runtime bot

Use one of these canonical modes:

- Step debug: `vibegame run -b --headless --port <N> --debug`, then inspect with `vibegame play --port <N> ...`.
- Realtime bot: `vibegame run -b --headless --bot <path>`, which records video, trace, result, and stdout. A bot may return `breakpoint` to switch into step debug.

Bot output defaults to `.vibegame/logs/bot/<run-id>/`, where `<run-id>` is `YYYYMMDD-HHMMSS-<bot-basename>`:

```text
video.webm  trace.jsonl  result.json  stdout.log
```

Use `--shot <file>` to override the video path. Each trace line is `{tick, t, action, state}`. `result.json` uses:

```json
{"ok": true, "status": "done|fail|timeout|crash|breakpoint", "reason": "...", "setup_s": 2.7, "duration_s": 4.83, "decision_count": 28, "bot_file": "...", "bot_meta": {}, "error": null, "console_errors": []}
```

`ok` is true only for `status="done"`. Read `trace.jsonl` before accepting a pass; `done` alone does not prove the intended phases ran.

### Bot contract

```python
def decide(snap, ctx): ...
META = {"name": str, "purpose": str, "max_seconds": int,
        "params": {str: str}}  # optional
def compact(snap, ctx) -> dict: ...  # optional
```

The bot runs inside the runner. Do not import Playwright. It may import project helpers and stdlib. `snap` has the same shape as `vibegame play snapshot`.

`ctx` exposes:

```python
ctx.KEY       # semantic action to KeyboardEvent.code
ctx.scratch   # persistent dict
ctx.elapsed_s # bot-loop seconds, excluding setup
ctx.tick      # decide() call count
```

`META["params"]` loads the game with the same query parameters as `vibegame run -- k=v`. `--max-seconds N` overrides `META["max_seconds"]`. Setup time is recorded separately as `result.setup_s`.

### Actions

Actions are `(kind, payload, duration, reason)` tuples:

| Kind | Payload | Behavior |
|---|---|---|
| `wait` | `None` | Wait for duration. |
| `tap`, `hold` | key or keys | Press/release automatically, then wait. |
| `down`, `up` | key or keys | Change key state; the bot must pair them. |
| `mousemove` | `{x,y}` or `[x,y]` | Move the pointer. |
| `click` | `{x,y,button?}` or `[x,y]` | Click the pointer. |
| `drag` | `{from,to,steps?,button?}` | Perform a drag. |
| `breakpoint` | `None` | Pause, activate runtime control, keep recording, and wait for Ctrl+C. Exits with `ok=false`. |
| `done`, `fail` | `None` | Exit with `ok=true` or `ok=false`. |

Keys may be lists for simultaneous input. Game-world pointer coordinates are converted through `gameToClient`; add `space: "client"` only for a DOM overlay.

```python
META = {"name": "io_basic", "max_seconds": 5}
def decide(snap, ctx):
    if ctx.elapsed_s < 1.0: return ("hold", ctx.KEY["move_right"], 0.5, "right")
    if ctx.elapsed_s < 2.0: return ("hold", ctx.KEY["move_left"], 0.5, "left")
    if ctx.elapsed_s < 3.0: return ("tap", ctx.KEY["attack"], 0.2, "swing")
    return ("done", None, 0, "io exercised")
```

Do not mix `if ctx.tick == N` phases with elapsed-time early returns; ticks advance while time guards wait, causing skipped phases and false passes. Use one elapsed timeline or `ctx.scratch["phase"]`.

## Record and replay

`vibegame play record` records discrete Runtime API commands into an editable replay script. This differs from realtime bot recording.

```bash
vibegame play activate
vibegame play record player_walk
# Run input, continue, snapshot, screenshot, and other play commands.
vibegame play record --stop
```

This creates `.vibegame/traces/player_walk/play.sh`. Activate before recording. `record --stop` appends `deactivate`; each command is appended after it runs; screenshots become `$TRACE_DIR/logs/step_NNN.png` on replay.

Replay with `bash .vibegame/traces/player_walk/play.sh`. Evidence appears under its `logs/` directory:

```text
output.log  step_001.png  step_002.png
```

Clean exploratory steps before sharing a trace. A recorded `play.sh` can also run through `vibegame play batch @<path>`.

## Testing workflow

1. Start from the correct root: `vibegame run . -b --headless`, adding `--activate` or `--debug` when needed.
2. Check `vibegame play status`; activate if control is not already active.
3. Clear console/network buffers.
4. Inject input or set state, then advance exact frames.
5. Capture snapshot assertions and screenshots at decisive states.
6. Read console/network output and bot traces before declaring success.
7. Store reusable traces and evidence, then run `vibegame close` from the same root.

## Script integration

`breakpoint(reason?)` pauses an active runtime controller:

```js
if (hp <= 0) this.breakpoint('player died');
```

`runtimeState()` returns JSON-serializable state included under the snapshot's `runtime` field:

```js
runtimeState() {
  return {hp: this.hp, selectedUnitId: this.selectedUnitId, panel: this._activePanel};
}
```

For state implemented outside Node scripts, expose it through a host Node's `runtimeState()`.

## REST API Reference

Advanced tools may call `http://localhost:<port>` directly.

| Endpoint | Method | Description |
|---|---|---|
| `/api/runtime/activate` | POST | Activate and pause. |
| `/api/runtime/deactivate` | POST | Deactivate control. |
| `/api/runtime/continue` | POST | Advance frames, e.g. `{"frames": 60}`. |
| `/api/runtime/pause` | POST | Pause immediately. |
| `/api/runtime/play` | POST | Resume free-running. |
| `/api/runtime/snapshot` | GET | Structured runtime state. |
| `/api/runtime/screenshot` | GET | Full page PNG. |
| `/api/runtime/refresh` | POST | Reload the page. |
| `/api/runtime/input` | POST | Inject mapped input. |
| `/api/runtime/set` | POST | Set a node property. |
| `/api/runtime/click` | POST | Click coordinates. |
| `/api/runtime/mousemove` | POST | Move pointer. |
| `/api/runtime/drag` | POST | Drag between coordinates. |
| `/api/runtime/key` | POST | Inject keyboard event. |
| `/api/runtime/eval` | POST | Execute JavaScript. |
| `/api/runtime/status` | GET | Controller status. |
| `/api/runtime/console` | GET | Console entries. |
| `/api/runtime/console/clear` | POST | Clear console buffer. |
| `/api/runtime/network` | GET | Network entries. |
| `/api/runtime/network/clear` | POST | Clear network buffer. |
