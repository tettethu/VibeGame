# Collision Guide

Goal: set up collision and physics interaction between entities.

---

## ColliderDef Fields

When present in a NodeDef, engine calls `physics.add.existing()` and configures the body before `ready()`.
Requires `visual` to be set. By default the body attaches to the visual object; with `host: "separate"` it attaches to an invisible physics host.

By default, the collider body is attached to the visual object. For animation frames with very different source sizes or per-frame visual offsets, use `host: "separate"` to create an invisible stable physics host; then `gameObject` / `physicsObject` is the body host and `visualObject` is only for display and animation. Use the NodeDef-level `visualTransform` field to offset the sprite from that host, and `FrameRef.offset` for one-frame visual corrections.

Collider transform support is intentionally small. Parent-child transform inheritance updates `x`, `y`, `displayWidth`, and `displayHeight`, then refreshes the Arcade body. A child with `config.flipWithParent: true` also mirrors `offsetX` and an explicit horizontal `pivot`. Box colliders remain axis-aligned; `rotation` / `angle` does not rotate the collision shape.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `shape` | string | `"box"` | `"box"` or `"circle"` |
| `body` | string | `"dynamic"` | `"dynamic"` or `"static"` |
| `host` | string | visual object | `"separate"` creates an invisible physics host instead of attaching body to the visual |
| `width` | number | visual width | Collision box width (px). `box` only. |
| `height` | number | visual height | Collision box height (px). `box` only. |
| `radius` | number | — | Collision circle radius (px). `circle` only. |
| `pivot` | [number, number] | inherits from visual origin | Where on the collider box the anchor sits, `[x, y]` in `0..1`. Default makes the collider anchor at the same point as the sprite's pivot — no manual offset needed for ground characters. See [Pivot](#pivot). |
| `offsetX` | number | 0 | Additional X offset on top of the auto-computed pivot offset (world px) |
| `offsetY` | number | 0 | Additional Y offset on top of the auto-computed pivot offset (world px) |
| `gravity` | boolean | true | Affected by world gravity |
| `immovable` | boolean | false | Dynamic body not pushed by collisions (e.g. paddles) |
| `worldBounds` | boolean | false | Collide with world edges |
| `bounce` | `{x, y}` | `{x:0,y:0}` | Bounce factor (1.0 = full bounce) |
| `oneWay` | boolean | false | One-way platform: blocks from above only |

**Omission rules:** `width`/`height` omitted → inherited from `visual`. `pivot` omitted → inherited from visual sprite's resolved origin (i.e., the result of [animation-guide.md#pivot](./animation-guide.md#pivot) cascade). `collider` omitted entirely → no physics body (visual-only node).

### Defaults you get for free

When you omit `collider.width` / `collider.height`, the engine reads the visual's actual `displayWidth` / `displayHeight` at body creation. **This works for every visual type** — `rect`, `circle`, `image`, `atlas`, `sprite`. The collider matches whatever the visual draws.

```json
// Floor: collider matches the rect exactly. Do NOT repeat 800x40.
"visual":   { "type": "rect", "width": 800, "height": 40, "color": "0x4a6741" },
"collider": { "body": "static" }
```

```json
// Character: collider matches the sprite frame. Do NOT repeat 32x48.
"visual":   { "type": "atlas", "texture": "hero", "width": 32, "height": 48 },
"collider": { "body": "dynamic", "gravity": true }
```

Only set `collider.width` / `collider.height` when you need a **different** size from the visual — a tight hitbox inside a larger sprite, an oversized hurtbox, a footprint smaller than the artwork. When in doubt, **omit them**; the inherited default is usually what you want.

**Units:** `collider.width` / `collider.height` / `radius` / `offsetX` / `offsetY` are **world px** — the same units as `visual.width`/`height`, i.e. what you see on screen. The engine converts to Phaser's pre-scale body coords internally, so this holds no matter how the visual got its size (`width`/`height`, `ratio`, or atlas frames) — never do source-image-size math yourself. For the same reason, do not call Phaser `body.setSize()` directly in scripts: that API takes pre-scale texture coords and your world-px value would be scaled twice.

When runtime code must inspect a circle collider after creation, do not treat Phaser `body.radius` as world-space: Phaser stores that field in pre-scale body coordinates. Use the declarative `collider.radius` as the authoritative value; for runtime measurement use `body.width / 2` (`body.halfWidth` floors fractional radii).

**Runtime resizing:** `setDisplaySize()` (and `displayWidth`/`displayHeight` assignment) changes the visual scale; a `dynamic` body tracks scale automatically each frame, so the collider follows proportionally. A `static` body does not — call `refreshBody()` / `body.updateFromGameObject()` after resizing (the engine already does this for parent-inherited resizes).

## Pivot

`collider.pivot` is a fractional anchor on the collider box, `[x, y]` in `0..1` (`[0,0]` = top-left). The engine auto-computes Phaser `body.setOffset` so that the collider's pivot point in world space coincides with the gameObject's origin point. Cascade:

1. `colliderDef.pivot` — explicit
2. visual sprite's resolved origin (i.e., the value Sprint 1's pivot cascade produced) — inheritance
3. `[0.5, 0.5]` — when no visual exists, or for `shape: "circle"`

**Behavior by mode:**

| Mode | What happens |
|---|---|
| Same-object (default) | `body.setOffset` auto-computed so collider's pivot aligns with sprite origin. For a ground char with sprite pivot `[0.5, 1]` and a smaller hitbox, body bottom lands on feet line automatically — no manual `offsetY` needed. |
| Separate-host (`host: "separate"`) | The invisible host rect's `setOrigin` is set to the cascade result (defaults to visual sprite origin). Body inherits, so visual sprite and physics body share the same anchor. `visualTransform` typically unnecessary — leave it off. |
| `shape: "circle"` | Default pivot is `[0.5, 0.5]` regardless of visual (circles have no "feet" semantics). Override with explicit `colliderDef.pivot` if needed. |

`colliderDef.offsetX/Y` still works — applied ADDITIVELY on top of the auto-computed pivot offset. Use it for fine-tune adjustments only (e.g., hitbox biased to one side).

```json
// Ground character — no offset needed, collider inherits visual pivot [0.5,1]
"visual": { "type": "atlas", "texture": "hero", "width": 32, "height": 48 },
"collider": { "body": "dynamic", "width": 20, "height": 40, "gravity": true }
// body bottom auto-aligns to sprite feet at sprite.y

// Hitbox biased forward
"collider": { "body": "static", "width": 28, "height": 24, "offsetX": 14 }
// pivot still inherits visual; offsetX shifts body to the right by 14px

// Explicit override (rare)
"collider": { "body": "dynamic", "width": 20, "height": 40, "pivot": [0.5, 0.5] }
// body centered on sprite origin, regardless of visual pivot
```

```json
// Dynamic character (smaller hitbox than visual)
"collider": { "body": "dynamic", "width": 20, "height": 40, "offsetY": 4, "gravity": true, "worldBounds": true }

// Dynamic character with stable physics host, useful for atlas animations with variable frame sizes
// (visualTransform usually not needed — collider.pivot inheritance handles feet alignment)
"collider": { "body": "dynamic", "host": "separate", "width": 20, "height": 40, "gravity": true, "worldBounds": true }

// Static ground
"collider": { "body": "static" }

// One-way platform (thin top-only collision)
"collider": { "body": "static", "height": 6, "offsetY": -5, "oneWay": true }

// Immovable paddle (moved by script velocity, not pushed by collisions)
"collider": { "body": "dynamic", "immovable": true, "gravity": false, "worldBounds": true }

// Bouncing ball (circle, no gravity)
"collider": { "shape": "circle", "radius": 5, "body": "dynamic", "bounce": {"x":1,"y":1}, "gravity": false, "worldBounds": true }
```

---

## Three-Level Collision API

### Level 1: Phaser one-liner (simple blocking / trigger)

Use when you only need blocking or a per-frame callback. No enter/exit distinction.

```javascript
ready() {
  const grounds = this.findByTag('ground')
  for (const g of grounds) {
    // Block movement
    this.scene.physics.add.collider(this.gameObject, g.gameObject)

    // Trigger overlap (no blocking, callback every frame while overlapping)
    this.scene.physics.add.overlap(this.gameObject, g.gameObject, () => {
      this.onPickup(g)
    })
  }
}
```

### Level 2: trackCollider / trackOverlap (enter/exit events)

Use when you need to know the exact moment contact starts or ends.

```javascript
ready() {
  const grounds = this.findByTag('ground')
  for (const g of grounds) {
    this.trackCollider(g.gameObject, g)   // emits 'collision_enter' / 'collision_exit'
    // or: this.trackOverlap(g.gameObject, g)  // emits 'overlap_enter' / 'overlap_exit'
  }

  this.on('collision_enter', ({ other }) => {
    if (other.tags.includes('ground')) this.isGrounded = true
  })
  this.on('collision_exit', ({ other }) => {
    if (other.tags.includes('ground')) this.isGrounded = false
  })
}
```

Event data: `{ other: Node }`. When the event bubbles to a parent, `source` (the emitting node) is added automatically.

**When to use which:**
- Simple collision (block movement): `physics.add.collider(a, b)`
- Simple overlap (trigger): `physics.add.overlap(a, b, callback)`
- Need enter/exit detection: `trackCollider(a, node)` or `trackOverlap(a, node)`

### Level 3: Collider child node (extra collision area)

Phaser allows only one body per game object. For attack hitboxes, sensor zones, pickup ranges, use the built-in `Collider` script as a child node. It creates an invisible Phaser object that follows parent position. For moving hitboxes, prefer `body: "dynamic"` with `immovable: true`.

```json
{
  "name": "Player",
  "script": "PlayerController",
  "visual": { "type": "spritesheet", "texture": "hero", "width": 32, "height": 48 },
  "collider": { "body": "dynamic", "width": 20, "height": 40, "gravity": true },
  "children": [{
    "name": "AttackArea",
    "script": "Collider",
    "collider": { "body": "dynamic", "width": 28, "height": 24, "offsetX": 14, "gravity": false, "immovable": true },
    "config": { "startEnabled": false, "flipWithParent": true }
  }]
}
```

Collider config:

| Field | Default | Description |
|-------|---------|-------------|
| `startEnabled` | true | Initial enabled state |
| `flipWithParent` | false | Mirror this child's local X, visual, and collider `offsetX` with its direct parent |

Use one positive or negative `offsetX` for a directional hitbox and enable `flipWithParent`. Do not author duplicate left and right hitboxes. The source collider definition stays unchanged when the effective offset is mirrored at runtime.

> **Note**: There is no `sensor` config. Collider creates a physics body that always physically blocks. For overlap-only (no blocking) use `physics.add.overlap` or `trackOverlap` against the child Collider's `gameObject` directly. For moving child hitboxes, `dynamic` + `immovable: true` is the safer default.

```javascript
ready() {
  this.attackArea = this.getChild('AttackArea')

  // Overlap-only (no blocking): use physics.add.overlap against attackArea.gameObject
  for (const e of this.findByTag('enemy')) {
    this.scene.physics.add.overlap(this.attackArea.gameObject, e.gameObject, () => {
      e.emit('hit', { damage: 1 })
    })
  }
}

attack() {
  this.attackArea.enable()
  this.scene.time.delayedCall(200, () => this.attackArea.disable())
}
```

Methods: `enable()`, `disable()`, `isEnabled()`.

---

## Event Bubbling

Events bubble upward through the tree. Siblings communicate via their shared parent.

```javascript
// Ball emits:
this.emit('score', { scorer: 'player' })

// ScoreBoard (sibling of Ball) — listen on shared parent:
this.parent.on('score', ({ scorer, source }) => {
  // source = the Ball node that emitted
  if (scorer === 'player') this.playerScore++
})
```

---

## Manual Physics (escape hatch)

When `collider` is absent, set up physics in `ready()`:

```javascript
ready() {
  // Static body
  this.scene.physics.add.existing(this.gameObject, true)

  // Dynamic body
  this.scene.physics.add.existing(this.gameObject, false)
  this.gameObject.body.setCollideWorldBounds(true)
  this.gameObject.body.setImmovable(true)      // paddle pattern
  this.gameObject.body.setAllowGravity(false)  // no gravity
}
```

---

## Bouncing World Bounds

```javascript
ready() {
  this.gameObject.body.onWorldBounds = true
  this.scene.physics.world.on('worldbounds', (body, up, down, left, right) => {
    if (body === this.gameObject.body) { /* react */ }
  })
}
```

---

## Complete Example: Player + Ground + Attack Hitbox

```json
{
  "name": "Level",
  "root": {
    "name": "Root",
    "children": [
      {
        "name": "Player", "script": "PlayerController",
        "visual": { "type": "spritesheet", "texture": "hero", "width": 32, "height": 48 },
        "collider": { "body": "dynamic", "width": 20, "height": 40, "gravity": true, "worldBounds": true },
        "config": { "x": 100, "y": 400, "speed": 200 },
        "children": [{
          "name": "AttackArea", "script": "Collider",
          "collider": { "body": "dynamic", "width": 28, "height": 24, "offsetX": 14, "gravity": false, "immovable": true },
          "config": { "startEnabled": false }
        }]
      },
      {
        "name": "Ground", "tags": ["ground"],
        "visual": { "type": "rect", "width": 800, "height": 40, "color": "0x4a6741" },
        "collider": { "body": "static" },
        "config": { "x": 400, "y": 580 }
      },
      {
        "name": "Enemy", "tags": ["enemy"],
        "visual": { "type": "rect", "width": 24, "height": 36, "color": "0xff4444" },
        "collider": { "body": "dynamic", "gravity": true },
        "config": { "x": 400, "y": 400 }
      }
    ]
  }
}
```

```javascript
import { Node } from '/engine/Node.js'

export default class PlayerController extends Node {
  ready() {
    this.isGrounded = false
    this.attackArea = this.getChild('AttackArea')

    // Ground collision
    for (const g of this.findByTag('ground')) {
      this.trackCollider(g.gameObject, g)
    }
    this.on('collision_enter', ({ other }) => {
      if (other.tags.includes('ground')) this.isGrounded = true
    })
    this.on('collision_exit', ({ other }) => {
      if (other.tags.includes('ground')) this.isGrounded = false
    })

    // Attack hitbox vs enemies
    for (const e of this.findByTag('enemy')) {
      this.scene.physics.add.overlap(this.attackArea.gameObject, e.gameObject, () => {
        e.emit('hit', { damage: 1 })
      })
    }
  }

  attack() {
    this.attackArea.enable()
    this.scene.time.delayedCall(200, () => this.attackArea.disable())
  }
}
```

## Coordinate systems: body vs physicsObject

Phaser Arcade Physics uses two coordinate systems. Mixing them up causes position bugs (e.g. spawning effects at the wrong height).

| | What | Coordinate meaning |
|---|---|---|
| `body.x / body.y` | Arcade body position | **Top-left** of bounding box. Ignores origin/pivot. Used internally by physics engine. |
| `physicsObject.x / physicsObject.y` | Game object position | **Origin** position, affected by `setOrigin()` / pivot. With pivot `[0.5, 1]`, y = bottom-center (feet). |

Relation: `body.y = physicsObject.y - body.height` (when pivot y = 1).

**Rule: always use `physicsObject.x/y` (or `getPhysicsObject().x/y`) for game logic** — spawning entities, `body.reset()`, position comparisons. Only Phaser internals should read `body.x/y`.
