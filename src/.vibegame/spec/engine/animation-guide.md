# Animation Guide

Goal: add animations to entities.

---

## Three Ways to Animate

| Method | When to use | How |
|--------|------------|-----|
| `visual.animations` | Quick prototyping, simple entities (legacy style) | Inline in `visual`, play via `this.getVisualObject().play(name)` |
| `animations.clips` + `playAnim()` | Most cases — recommended | Top-level `animations` on NodeDef, call `this.playAnim(name)` |
| `animations` + `animator` state machine | Complex characters with many transitions | Set parameters, engine picks clip automatically |

---

## Method 1: visual.animations (old style, still supported)

Define clips inline in the `visual` field. Works with `spritesheet` and `atlas` types only.

```json
"visual": {
  "type": "spritesheet", "texture": "hero", "width": 32, "height": 48,
  "animations": {
    "idle": { "frames": [0, 1, 2, 3], "frameRate": 6, "loop": true },
    "run":  { "frames": [4, 5, 6, 7, 8, 9], "frameRate": 10, "loop": true },
    "jump": { "frames": [10, 11], "frameRate": 8, "loop": false }
  }
}
```

AnimDef fields (spritesheet): `frames` (number[]), `frameRate`, `loop`.
AtlasAnimDef fields (atlas): `frames` (string[] — frame names), `frameRate`, `loop`.

Play from script:

```javascript
this.getVisualObject()?.play('run')    // string name only (engine rewrites play() to auto-prefix)
```

> **Pitfall**: Engine rewrites `sprite.play()` to auto-prefix the texture name — only pass a string, not an object. Phaser registers these as global animation keys; name collisions possible in multi-entity projects. Prefer Method 2 for new projects.

---

## Method 2: animations.clips + playAnim() (recommended)

Top-level `animations` field on NodeDef. Engine creates an `AnimationPlayer`, accessible via `this.animationPlayer`.

### AnimationsDef fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `default` | string | no | Clip name to autoplay on init (when no animator present) |
| `clips` | object | yes | `{ clipName: ClipDef }` |

### ClipDef fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `source.type` | string | no | `"spritesheet"` or `"atlas"`. Inferred from `visual.type` if omitted. |
| `source.texture` | string | no | Texture key. Inferred from `visual.texture` if omitted. For prototype-polish work, prefer manifest `type: "placeholder_atlas"` so clips use atlas-style semantic frame names from day one. The built-in atlas key `__placeholder_atlas__` exists for low-level tests, but task agents should usually create semantic manifest keys instead. |
| `frames` | FrameRef[] | no | Frame indices (spritesheet) or frame names (atlas). See [FrameRef](#frameref). |
| `frameRate` | number | no | Playback speed in frames per second. Defaults to 10. Mutually exclusive with `duration`; if both set, `duration` wins. |
| `duration` | number | no | Total clip length in seconds; per-frame duration = `duration / frames.length`. Prefer over `frameRate` when frame count may change between prototype and polish - the total length stays stable. |
| `loop` | boolean | no | Default true |
| `onFinish` | string | no | Non-loop behavior: `"hold"` (default) or `"first"` |
| `pivot` | [number, number] | no | Override manifest pivot for this clip's frames. `[x, y]` in `0..1`. See [Pivot](#pivot). |

### FrameRef

`ClipDef.frames` accepts either shorthand frame ids or object frame refs:

```json
"frames": [
  "f0",
  { "frame": "f1", "offset": [0, 18] }
]
```

Rules:

- `string | number` is shorthand for `{ "frame": value }`.
- `offset` is optional `[x, y]` in world/display px.
- `offset` is visual-only. It moves the rendered `visualObject` for this one frame occurrence; it does not move the node transform or collider.
- If a node has a collider and any frame uses `offset`, set `collider.host: "separate"`. Same-object collider plus frame offset is invalid and fails `vibegame check`.
- Do not use `pivot` to fix per-frame drawing drift. `pivot` decides which point stays fixed; `FrameRef.offset` decides where this occurrence is drawn relative to that fixed point.
- `duration` is not part of `FrameRef`. Use existing `frameDurations` for timing.

Single texture (source inferred from visual):

```json
"animations": {
  "default": "idle",
  "clips": {
    "idle":   { "frames": [0, 1, 2, 3], "frameRate": 6 },
    "run":    { "frames": [4, 5, 6, 7, 8, 9], "frameRate": 10 },
    "attack": { "frames": [10, 11, 12], "frameRate": 12, "loop": false, "onFinish": "hold" }
  }
}
```

Multi-texture (per-clip source override):

```json
"visual": { "type": "spritesheet", "texture": "hero_idle", "width": 32, "height": 48 },
"animations": {
  "default": "idle",
  "clips": {
    "idle":   { "frames": [0, 1, 2, 3], "frameRate": 6 },
    "run":    { "source": { "texture": "hero_run" }, "frames": [0, 1, 2, 3], "frameRate": 10 },
    "attack": { "source": { "texture": "hero_attack", "type": "atlas" }, "frames": ["atk_0", "atk_1", "atk_2"], "frameRate": 12, "loop": false }
  }
}
```

When `source` is set on a clip, it overrides the visual defaults for that clip only. Other clips without `source` still use `visual.texture`.

### Playback API

```javascript
this.playAnim('run')                      // play, RESTART from frame 0
this.playAnim('run', { restart: false })  // play, but no-op if 'run' is already current
this.stopAnim()                           // stop, hold current frame
this.getCurrentAnim()                     // returns current clip name, or null
```

Playback uses real elapsed time (dt-driven), not render frame count.

#### `restart` option

`playAnim(name, options)` accepts `{ restart: false }`. The option controls what happens when the clip you ask for is **already the current clip**:

- `restart: true` (default) — always reset `currentFrameIndex` to 0 and play from the start, even if `name` matches the current clip.
- `restart: false` — if `name` is already the current clip, do nothing; otherwise switch and start from frame 0.

When in doubt, prefer `restart: false`. It is idempotent under repeated calls, which matches how scripts naturally express animation state ("I want to be in `run` right now"). The default `restart: true` is for cases where you explicitly want the animation to retrigger (e.g. fire a hit-flash on every collision).

> **Warning — calling `playAnim(sameName)` every frame freezes the animation on frame 0.**
>
> If `update(dt)` unconditionally calls `this.playAnim('run')`, the default `restart: true` resets `currentFrameIndex` to 0 *every tick*. The animation never advances past frame 0, looking broken even though the system is "playing".
>
> This is a common pitfall when an `update`-style script wants to express "be in `run` while moving". Two correct patterns:
>
> ```javascript
> // 1. Pass restart:false so repeated calls are idempotent (preferred)
> update(dt) {
>   this.playAnim(this.isMoving ? 'run' : 'idle', { restart: false })
> }
>
> // 2. Guard on state change explicitly
> update(dt) {
>   const next = this.isMoving ? 'run' : 'idle'
>   if (this.getCurrentAnim() !== next) this.playAnim(next)
> }
> ```
>
> Use the default `restart: true` only at discrete event moments (collision, button press), never on every frame.

---

## Method 3: animator state machine

Layer on top of `animations.clips`. Script sets parameters; engine picks the right clip automatically.

### AnimatorDef fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `defaultState` | string | yes | State to enter on init |
| `parameters` | object | no | `{ name: "bool" \| "trigger" }` |
| `states` | object | yes | `{ stateName: { clip: string } }` |
| `transitions` | TransitionDef[] | yes | Ordered list — first match wins |

### TransitionDef fields

| Field | Type | Description |
|-------|------|-------------|
| `from` | string or string[] | Source state, source states, or `"Any"` |
| `to` | string | Destination state |
| `when` | ConditionDef[] | All conditions must match |
| `hasExitTime` | boolean | Current clip must finish before transition fires |

### ConditionDef shapes

```json
{ "param": "isMoving", "eq": true }   // bool comparison
{ "trigger": "attack" }               // trigger consumed when transition fires
```

### Example

```json
"animator": {
  "defaultState": "idle",
  "parameters": { "isMoving": "bool", "attack": "trigger" },
  "states": {
    "idle": { "clip": "idle" },
    "run": { "clip": "run" },
    "attack": { "clip": "attack" }
  },
  "transitions": [
    { "from": "idle",   "to": "run",    "when": [{ "param": "isMoving", "eq": true }] },
    { "from": "run",    "to": "idle",   "when": [{ "param": "isMoving", "eq": false }] },
    { "from": "Any",    "to": "attack", "when": [{ "trigger": "attack" }] },
    { "from": "attack", "to": "idle",   "hasExitTime": true }
  ]
}
```

Drive from script:

```javascript
update(dt) {
  const moving = this.gameObject.body.velocity.x !== 0
  this.animator.setBool('isMoving', moving)
}

onAttack() {
  this.animator.setTrigger('attack')  // consumed automatically when transition fires
}
```

Animator script API:

```javascript
this.animator.setBool('isMoving', true)   // set a bool parameter
this.animator.getBool('isMoving')         // read a bool parameter
this.animator.setTrigger('attack')        // set a trigger (auto-resets after transition)
this.animator.resetTrigger('attack')      // manually reset a trigger
this.animator.getState()                  // returns current state name
```

> **Pitfall**: There is no `setParam()` method. Use `setBool()` for bool parameters and `setTrigger()` for triggers. Calling a non-existent method will silently do nothing.

Update order is:

```txt
node.update(dt)
-> animator.update(dt)          // evaluates transitions, selects the clip
-> animationPlayer.update(dt)   // advances frames of the current clip
```

> **No frame events.** An animator state only selects a clip. To fire something at a point inside a clip (hitbox on at frame 2), do it in the script: remember the previous `currentFrameIndex` and act on frames *crossed* since last tick — a low-fps tick can skip frames, so testing `=== n` misses them. Reset on state exit too: an interrupted clip never reaches its later frames.

---

## Complete Example: Hero with Animated States

**assets/manifest.json:**

```json
{
  "hero": { "type": "spritesheet", "path": "hero.png", "frameWidth": 32, "frameHeight": 48 }
}
```

**entities/hero.node.json:**

```json
{
  "name": "Hero",
  "script": "PlayerController",
  "visual": { "type": "spritesheet", "texture": "hero", "width": 32, "height": 48 },
  "collider": { "body": "dynamic", "width": 20, "height": 40, "gravity": true },
  "animations": {
    "default": "idle",
    "clips": {
      "idle":   { "frames": [0, 1, 2, 3], "frameRate": 6 },
      "run":    { "frames": [4, 5, 6, 7, 8, 9], "frameRate": 10 },
      "attack": { "frames": [10, 11, 12], "frameRate": 12, "loop": false }
    }
  },
  "animator": {
    "defaultState": "idle",
    "parameters": { "isMoving": "bool", "attack": "trigger" },
    "states": {
      "idle":   { "clip": "idle" },
      "run":    { "clip": "run" },
      "attack": { "clip": "attack" }
    },
    "transitions": [
      { "from": "idle",   "to": "run",    "when": [{ "param": "isMoving", "eq": true }] },
      { "from": "run",    "to": "idle",   "when": [{ "param": "isMoving", "eq": false }] },
      { "from": "Any",    "to": "attack", "when": [{ "trigger": "attack" }] },
      { "from": "attack", "to": "idle",   "hasExitTime": true }
    ]
  },
  "config": { "speed": 200 }
}
```

**scripts/PlayerController.js (animation section):**

```javascript
update(dt) {
  const input = this.sceneTree.inputMap
  if (!input) return

  const moving = input.isHeld('move_left') || input.isHeld('move_right')
  this.animator.setBool('isMoving', moving)

  if (input.isPressed('attack')) {
    this.animator.setTrigger('attack')
  }
}
```

## Pivot

Every animated visual has a `pivot` — a fractional anchor `[x, y]` in `0..1` (`[0,0]` = top-left). When atlas frames vary in size between animation frames, a centered origin causes the character to "float" mid-air because each frame's bbox center sits at a different world position. The pivot resolves to Phaser's `setOrigin(x, y)` and is re-applied on every frame change, keeping a stable reference point (e.g., feet center) across all frames.

### Default

`[0.5, 1]` — bottom-center. Correct for ground-anchored characters (player, enemies, NPCs). Tight-cropped sprite bboxes have their bottom edge at the character's lowest pixel, so `[0.5, 1]` lands at the feet.

### Cascade (high to low)

1. `animations.clips.<name>.pivot` — clip-level override in node.json
2. manifest `<asset>.sprites.<frame>.pivot` — per-frame override in manifest
3. manifest `<asset>.pivot` — group-level default in manifest
4. `[0.5, 1]` — engine default

### When to override

| Asset type | Where | Value |
|---|---|---|
| Ground character / enemy | omit | (default `[0.5, 1]` is correct) |
| Centered VFX (explosion, shockwave, projectile) | manifest group `pivot` or clip `pivot` | `[0.5, 0.5]` |
| Floating / airborne entity (flying enemy) | manifest group | `[0.5, 0.5]` |
| Top-anchored (banner, hanging icon) | manifest group | `[0.5, 0]` |
| Same image, different anchor per animation | node.json `clip.pivot` | per-clip |

### Example

Manifest group default:

```json
"slam": {
  "type": "atlas", "path": "slam.png",
  "pivot": [0.5, 0.5],
  "sprites": { "slam_c0": { "bbox": [0, 0, 200, 100] } }
}
```

Clip-level override (when the same image needs different anchors per animation):

```json
"animations": {
  "clips": {
    "stand_hit":  { "frames": ["hit_0"], "frameRate": 8 },
    "knockdown":  { "frames": ["hit_0"], "frameRate": 6, "pivot": [0.5, 0.5] }
  }
}
```

### Relation to `visualTransform.offsetX/Y` and `collider.pivot`

- `visual` / `manifest.pivot` = where on the **image** the anchor sits (image-intrinsic, drives sprite origin).
- `collider.pivot` = where on the **collider box** the anchor sits. Defaults to inherit the visual sprite's resolved origin, so feet-anchored sprites get feet-aligned bodies for free — no manual `collider.offsetX/Y` or `visualTransform.offsetY` needed. See [collision-guide.md#pivot](./collision-guide.md#pivot).
- `visualTransform.offsetX/Y` = explicit extra visual offset relative to the transform/physics host. With `collider.pivot` defaulting to inherit visual pivot, most cases need zero `visualTransform`. Use it only when you want the visual visibly offset from the body anchor.
- `FrameRef.offset` = per-animation-frame visual correction. It stacks after `visualTransform` and affects only that frame occurrence.

All three are orthogonal and stack additively.

---

## Animation Design Rules

Image generation models often produce only a single frame per action. Knowing how to use these frames correctly is critical for natural-looking animation.

### Single-frame continuous actions (run, walk, swim, fly)

A single frame representing a continuous, repeating motion should **not** be held static. Instead, alternate it with the idle frame to create a 2-frame loop:

```json
"clips": {
  "idle": { "frames": [0], "frameRate": 4 },
  "run":  { "frames": [0, 1], "frameRate": 6 }
}
```

Here frame 0 is idle and frame 1 is the run pose. The oscillation between them creates visible motion — a character "pumping" their legs or shifting weight. Without this, the character appears frozen mid-stride.

### Multi-frame actions (attack, jump, hurt, die)

When the artist provided multiple frames for an action, use them as a complete sequence:

```json
"clips": {
  "attack": { "frames": [0, 1, 2, 3], "frameRate": 10, "loop": false, "onFinish": "hold" },
  "hurt":   { "frames": [0, 1], "frameRate": 8, "loop": false }
}
```

### Quick reference

| Action type | Frames available | Clip design |
|---|---|---|
| Continuous motion (run, walk) | 1 frame | `[idle, action]` 2-frame loop |
| Continuous motion | 2+ frames | Use all frames as-is, loop |
| One-shot (attack, jump, hurt, die) | 1 frame | `[idle, action]` or `[action, idle]`, loop false |
| One-shot | 2+ frames | Use all frames, loop false |
