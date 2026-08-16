# SideviewFighter Contract

## What it is

`SideviewFighterModule` is a player-side sideview combat controller. It reads input, drives an Animator state machine, manages hitbox child nodes, and handles movement physics. Module only controls animation playback and collider enable/disable — it does not own game logic (damage, HP, overlap detection).

## When to use

Side-scrolling action games where the player character has: directional movement, jump, dash, guard, attack with combo, and optionally deathblow finisher. Works with any art style — only requires atlas sprites per state.

Do **not** use when: the character is top-down, turn-based, or has no physics body.

## Three layers of configuration

Using this module requires setup in three places:

### 1. manifest (assets)

Register atlas textures for each animation state in `assets/manifest.json`. Each atlas is a sprite sheet with per-frame `bbox`. Module doesn't care about art content — only that texture keys referenced in clips exist.

### 2. node.json (data)

Declare in a single `.node.json` file:
- `visual` / `collider` / `children` — engine creates these
- `animations.clips` — one clip per animation state, referencing manifest textures
- `animator` — state machine: states map to clips, transitions define when to switch, parameters are set by module. This is standard engine data, not module-invented.
- `config` — tuning parameters. Module reads these but invents only one structure: `config.attacks`, which maps animator state names to hitbox child names + active frame indices.

### 3. project code (game logic)

Module handles: input → trigger → state transition → animation playback → hitbox enable/disable.

Project layer must handle everything else:
- **Overlap registration**: `scene.physics.add.overlap(hitboxGO, enemyGO, callback)` — module enables the hitbox, project detects the hit
- **Damage / HP / posture**: project owns combat state, module doesn't track health
- **Combat resolution**: deflect/guard/hit outcomes, knockback, VFX spawning
- **Win/lose conditions**: module emits `player_victory` after deathblow, project decides what to do with it

## node.json fields the module reads

| Field | Required | What module does with it |
|---|---|---|
| `animator` | yes | State machine — module sets bool/trigger, animator picks transitions |
| `animations.clips` | yes | AnimationPlayer plays clips selected by animator states |
| `collider` (body: dynamic) | yes | Physics body for movement, grounded detection |
| `children` (Collider nodes) | if attacks | Hitbox child nodes, module enable/disable by frame index |
| `config` | yes | All tuning parameters (see below) |

### config

```json
{
  "moveSpeed": 200,
  "runSpeed": 400,
  "guardSpeed": 100,
  "jumpForce": 520,
  "dashSpeed": 500,
  "dashDuration": 0.2,
  "comboWindowRatio": [0.6, 0.95],
  "deflectWindowMs": 150,
  "attacks": {
    "attack1": { "hitbox": "SwordHitbox1", "activeFrames": [1, 2] },
    "attack2": { "hitbox": "SwordHitbox2", "activeFrames": [1, 2] }
  },
  "deathblowSheatheDuration": 0.4,
  "deathblowIaiDuration": 0.3,
  "deathblowThroughDuration": 0.13,
  "deathblowTeleportOffset": 200,
  "deathblowArriveFinishDuration": 0.214,
  "afterimageCount": 3,
  "afterimageFadeDuration": 0.3,
  "deathblowWindowDuration": 8.0
}
```

All optional with defaults. Deathblow fields only needed if deathblow is used.

### input-map actions the module reads

| Action | Method | Used for |
|---|---|---|
| `move_left` / `move_right` | `isHeld` | Movement + facing |
| `run` | `isHeld` | Run speed toggle |
| `jump` | `isPressed` | Jump trigger |
| `attack` | `isPressed` | Attack / combo / deathblow trigger |
| `dash` | `isPressed` | Dash trigger |
| `guard` | `isHeld` | Guard / defense_walk toggle |

### animator requirements

Required parameters: `moving` (bool), `grounded` (bool).

Required states: `idle`, `walk`.

Transition priority (top = highest): die > hurt > dash > airSlash > attack1 > combo > jump > deflect > guard/defense_walk > locomotion > hasExitTime fallbacks.

`deathblow` state must have no clip and no outgoing transitions — module takes direct animation control during deathblow.

### State vocabulary and what each unlocks

State names are **fixed by the module** — you must use these exact names in the animator. Adding a state to the animator activates the corresponding module behavior. Not adding it disables that behavior (module sets triggers harmlessly, nothing matches).

| State name | What module does when active | Animator parameter to add | Config to tune | input-map action |
|---|---|---|---|---|
| `idle` | **required** — default state | `moving` (bool) | — | — |
| `walk` | **required** — moves at moveSpeed | `moving` (bool) | `moveSpeed` | `move_left`, `move_right` |
| `run` | moves at runSpeed | `running` (bool) | `runSpeed` | `run` |
| `jump` | applies -jumpForce as velocityY on enter | `jump` (trigger), `grounded` (bool) | `jumpForce` | `jump` |
| `fall` | no special logic, typically entered from jump via hasExitTime | `grounded` (bool) | — | — |
| `attack1` | enables hitbox child by frame index, opens combo window | `attack` (trigger) | `attacks.attack1`, `comboWindowRatio` | `attack` |
| `attack2` | enables hitbox child by frame index (combo follow-up) | `comboAttack` (trigger) | `attacks.attack2` | `attack` (during combo window) |
| `airSlash` | enables hitbox child by frame index (air attack) | `attack` (trigger), `grounded` (bool, eq: false) | `attacks.airSlash` | `attack` |
| `dash` | forces velocity = dashSpeed * facing for dashDuration | `dash` (trigger) | `dashSpeed`, `dashDuration` | `dash` |
| `guard` | reduces speed to guardSpeed, starts deflect window timer | `guarding` (bool), `grounded` (bool) | `guardSpeed`, `deflectWindowMs` | `guard` |
| `defense_walk` | guard + movement at guardSpeed | `guarding` (bool), `moving` (bool), `grounded` (bool) | `guardSpeed` | `guard` + `move_left`/`move_right` |
| `deflect` | entered via tryDeflect() or external setTrigger | `deflect` (trigger) | `deflectWindowMs` | — |
| `hurt` | blocks movement | `hurt` (trigger) | — | — (set externally) |
| `die` | blocks all input processing | `die` (trigger) | — | — (set externally) |
| `deathblow` | no clip, no outgoing transitions, module takes over animation/physics | `deathblow` (trigger) | `deathblowSheatheDuration`, `deathblowIaiDuration`, `deathblowThroughDuration`, `deathblowTeleportOffset`, `afterimageCount`, `afterimageFadeDuration` | `attack` (when deathblow window open) |

### What you can configure vs what is fixed

**Configurable** (via config):
- Speeds, forces, durations (all numeric tuning)
- Which hitbox child to activate per attack state (`config.attacks`)
- Which frames are active per attack (`activeFrames`)
- Combo window timing (`comboWindowRatio`)
- Deflect window timing (`deflectWindowMs`)
- Deathblow choreography timing and offset

**Configurable** (via animator transitions):
- Which states exist (add/omit freely, except idle and walk)
- Transition conditions and priority order
- Whether attacks require grounded
- Whether guard requires grounded

**Fixed by module** (cannot change without modifying module code):
- State names — must use the exact names above
- Combo is always attack1 → attack2 via comboAttack trigger
- Grounded is always read from body.blocked.down
- Facing is always determined by move_left/move_right input
- Hitbox activation is always frame-index based
- Deathblow sequence: sheathe → iai → arrive → finish → victory (phase order and frame indices)
- input-map action names: `move_left`, `move_right`, `jump`, `attack`, `dash`, `guard`, `run`

## Output

### Properties project layer can read

| Property | Type | Meaning |
|---|---|---|
| `facing` | 1 or -1 | Current facing direction |
| `_dashTimer` | number | >0 means currently dashing |
| `_dashDir` | 1 or -1 | Dash direction |
| `animator.getState()` | string | Current animator state name |

### Methods project layer can call

| Method | What it does |
|---|---|
| `enableDeathblow(target)` | Open deathblow window, next attack input triggers deathblow on target |
| `disableDeathblow()` | Close deathblow window |
| `tryDeflect()` | Returns true + triggers deflect if in guard within deflect window |

### Events the module emits

| Event | When | Emitted on |
|---|---|---|
| `player_victory` | Deathblow sequence completes | `this.parent` |

### What module does NOT do

- Register overlap between hitbox and enemies — project layer (ArenaManager) does this
- Track vitality / posture / HP — project layer owns combat state
- Decide damage amounts — project layer's CombatCore
- Know who the enemy is — only receives target via `enableDeathblow(target)`
- Emit hit events — hitbox overlap callbacks are registered by project layer

## Check

Two layers: runtime self-check (JS, in-game) and static check with visual preview (Python, CLI).

### Runtime self-check (JS)

Runs automatically in `ready()`. Reports to browser console.

| Level | Check |
|---|---|
| error | animator missing |
| error | required state `idle` or `walk` missing |
| error | required parameter `moving` or `grounded` missing |
| error | state references clip not in `animations.clips` |
| error | physics body missing |
| error | `config.attacks.<state>.hitbox` child node not found |
| warn | `config.attacks.<state>.activeFrames` is empty |
| warn | no nodes with tag `"ground"` in scene |
| pass | `SideviewFighterModule[name]: self-check passed` |

### Static check + visual preview (CLI)

Implementation: `src/modules/check/SideviewFighterModule.check.py`, auto-discovered by `vibegame check` when it sees `script: "SideviewFighterModule"` in a node.json.

#### Usage

```bash
# Basic: static validation + all previews
vibegame check entities/wolf.node.json

# Only specific attacks
vibegame check entities/wolf.node.json --states=attack1,attack2

# Custom output path
vibegame check entities/wolf.node.json -o assets/artifacts/my-check

# Higher preview scale (default: 1.0 = source resolution)
vibegame check entities/wolf.node.json --scale=2.0

# Validation only, no preview images
vibegame check entities/wolf.node.json --preview=false
```

#### Parameters

| CLI arg | node.json `config.check` | Default | Meaning |
|---|---|---|---|
| `--preview` | `preview` | `true` | Generate preview images |
| `-o`, `--preview_dir` | `preview_dir` | `assets/artifacts/module-check` | Output directory |
| `--states` | `states` | all in `config.attacks` | Which attack states to preview |
| `--scale` | `scale` | `1.0` (source resolution) | Preview render scale |

Priority: CLI args > `node.config.check` > defaults.

#### Static checks

| Level | What | Why it matters |
|---|---|---|
| error | animator missing | Module cannot function |
| error | `idle` or `walk` state missing | Minimum viable state machine |
| error | `moving` or `grounded` parameter missing | Module sets these every frame |
| error | State references clip not in `animations.clips` | Animation will fail |
| error | Physics body missing (no `collider`) | Movement and grounded detection fail |
| error | `config.attacks.<state>.hitbox` child not found | Hitbox enable will silently fail |
| error | Clip texture not in manifest | Asset won't load |
| warn | `activeFrames` is empty | Hitbox configured but never activates |
| warn | No `"ground"` tagged nodes in scene | `grounded` always false |

#### Preview images

**1. Idle + collider: `<name>_idle_collider.png`**

Shows the idle animation's first frame with the body collider overlaid.

Content:
- Sprite rendered at source resolution (or `--scale`)
- Green box = collider bounds, positioned using pivot alignment rules:
  - Collider pivot inherits from visual if not specified (default `[0.5, 1]` = bottom-center)
  - Box position = `(origin + offset - size * pivot)`, same formula as dashboard Objects panel
- Yellow dot = origin point (pivot position on sprite)

What to look for:
- Collider should cover the character's solid body (torso + legs), not head/weapon extensions
- If collider has no explicit `width`/`height`, it defaults to visual display size — collider covers the entire sprite
- Origin should be at the character's feet (for pivot `[0.5, 1]`)

**2. Attack + hitbox: `<name>_<attack>_hitbox.png`**

Shows all frames of an attack animation in a horizontal strip, with the hitbox collider drawn on active frames.

Content:
- All frames laid out left-to-right, bottom-aligned (standing on same ground line)
- Each frame centered in a fixed-width cell (widest frame + hitbox width), so hitbox position is consistent across frames
- Frame labels (`f00`, `f01`, ...) below each frame; active frames in red, inactive in gray
- On active frames: red box = hitbox bounds, positioned using child collider rules:
  - Child pivot defaults to `[0.5, 0.5]` (center)
  - Box position = `(cell_center + offset - size * pivot)`, relative to physicsObject origin (ground-center)
- On inactive frames (windup/recovery): no hitbox drawn

What to look for:
- **Hitbox should appear only on damage frames** — the frames where the blade/fist/effect visually connects. Typically the middle frames of the animation, not the windup (first) or recovery (last).
- **Hitbox edge should align with the attack's visual reach** — the red box's far edge should match where the blade tip or slash effect reaches. If the hitbox extends beyond the visual, enemies get hit by invisible attacks. If it's too short, visible hits don't register.
- **Hitbox vertical coverage should match the attack arc** — a horizontal slash hitbox should be wide and short; an overhead slam should be narrow and tall.
- **Hitbox position should be consistent across active frames** — the red box must be in the same position for all active frames (it follows the physicsObject, not the sprite). If it appears to shift between frames, the preview is wrong.

**Typical hitbox sizing convention**: for a sideview fighter, the hitbox extends from the character's center toward the attack direction. A reasonable starting point: width ≈ visual display width * 1.2, height ≈ visual display height * 0.5, offsetX ≈ width * 0.3 (forward), offsetY ≈ -height * 0.3 (sword height). Adjust by running `vibegame check` and comparing the red box to the attack animation visuals.

#### Discovery mechanism

Any module can participate in `vibegame check` by placing `<ModuleName>.check.py` under `src/modules/check/`.

```
src/modules/
├── SideviewFighterModule.js
├── StatusBarModule.js
├── check/
│   ├── SideviewFighterModule.check.py    ← auto-discovered
│   └── StatusBarModule.check.py          ← (future)
└── ...
```

`vibegame check` discovers them by:
1. Reading the node.json's `script` field
2. If it ends with `Module`, looking for `modules/check/<Script>.check.py`
3. Calling `check(project: Path, node_path: Path, opts: dict | None) -> list[str]`
4. Parsing returned strings by prefix: `ERROR:` / `WARN:` / `PREVIEW:` / `PASS:`

## Usage: node.json template

```json
{
  "name": "Player",
  "script": "SideviewFighterModule",
  "tags": ["player"],
  "visual": { "type": "atlas", "texture": "char_idle", "frame": "f00", "width": 89, "height": 141 },
  "collider": { "body": "dynamic", "host": "separate", "pivot": [0.5, 1], "worldBounds": true },
  "config": { "moveSpeed": 200, "jumpForce": 520, "attacks": { "attack1": { "hitbox": "HitboxA", "activeFrames": [1, 2] } } },
  "children": [
    { "name": "HitboxA", "script": "Collider", "collider": { "body": "dynamic", "gravity": false, "immovable": true, "width": 80, "height": 60, "offsetX": 24 }, "config": { "startEnabled": false, "flipWithParent": true } }
  ],
  "animations": { "default": "idle", "clips": { "idle": { "...": "..." }, "walk": { "...": "..." }, "attack1": { "...": "..." } } },
  "animator": {
    "defaultState": "idle",
    "parameters": { "moving": "bool", "grounded": "bool", "attack": "trigger" },
    "states": { "idle": { "clip": "idle" }, "walk": { "clip": "walk" }, "attack1": { "clip": "attack1" } },
    "transitions": [
      { "from": "Any", "to": "attack1", "when": [{ "trigger": "attack" }, { "param": "grounded", "eq": true }] },
      { "from": "idle", "to": "walk", "when": [{ "param": "moving", "eq": true }] },
      { "from": "walk", "to": "idle", "when": [{ "param": "moving", "eq": false }] },
      { "from": "attack1", "to": "idle", "hasExitTime": true }
    ]
  }
}
```

## Usage: project layer wiring (ArenaManager example)

```js
ready() {
  this.player = this.findByTag('player')[0]
  this.enemy = this.findByTag('enemy')[0]

  // Wire hitbox overlap — module enables/disables, project detects + resolves
  for (const child of this.player.children) {
    if (child.config?.startEnabled === undefined) continue
    const hitboxGO = child.gameObject
    if (!hitboxGO) continue
    this.scene.physics.add.overlap(hitboxGO, this.enemy.getPhysicsObject(), () => {
      this._resolveHit(this.player, this.enemy)
    })
  }

  // Deathblow trigger
  this.on('enemy_posture_break', () => {
    this.player.enableDeathblow(this.enemy)
  })
}
```
