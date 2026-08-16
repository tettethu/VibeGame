# Entity Guide

Goal: create gameplay entities (characters, enemies, items, platforms).

---

## NodeDef Structure

Each node in a scene tree follows this shape:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | yes | Node identifier within its siblings |
| `script` | string | no | Script class name (`"PlayerController"` loads `scripts/PlayerController.js`) |
| `config` | object | no | Arbitrary data passed to the script; read via `this.config` |
| `visual` | VisualDef | no | Declarative visual — engine creates Phaser object before `ready()` |
| `visualTransform` | object | no | Visual alignment relative to the node transform/physics host |
| `animations` | AnimationsDef | no | Clip library for engine-driven playback. See [animation-guide.md](./animation-guide.md). |
| `animator` | AnimatorDef | no | Parameter-driven state machine over `animations`. See [animation-guide.md](./animation-guide.md). |
| `collider` | ColliderDef | no | Physics body — engine configures before `ready()`. See [collision-guide.md](./collision-guide.md). |
| `src` | string | no | Path to a `.node.json` file; inline `config` merges on top |
| `children` | NodeDef[] | no | Child nodes |
| `tags` | string[] | no | Tags for `findByTag()` lookup |
| `id` | string | no | Explicit ID (auto-generated if omitted) |
| `enabled` | boolean | no | Default true. Disabled nodes skip lifecycle (no `ready`/`update`), have no `visualObject`/`gameObject`, and are excluded from `findByTag`. Their `children` are not built either — the whole subtree stays unbuilt. They remain in the scene tree as inert data containers (useful for script registration and `src` template caching). This is a **build-time** switch, not a runtime one: a node disabled at build never gets a gameObject, so flipping `enabled` later cannot activate it. For runtime on/off of an already-built collider, use the `Collider` child-node script's `startEnabled` config and `enable()`/`disable()` methods. |

**Key rules:**
- No `type` field — behavior comes entirely from `script`.
- `config` is flat: position, speed, HP, etc. all together. The script decides what to read.
- `visual` and `collider` are engine-processed. Do NOT re-create them in `ready()`.
- `ready()` may be async; the engine awaits it.

---

## Declarative vs Manual Mode

| Mode | When | What happens |
|------|------|-------------|
| **Declarative** (preferred) | NodeDef has `visual` and/or `collider` | Engine creates visual object and body/physics host before `ready()`. Script writes only gameplay logic. |
| **Manual** (escape hatch) | NodeDef omits `visual`/`collider` | Script creates Phaser objects in `ready()`. Use only when visual requires dynamic construction. |

Modes can be mixed: `visual` declarative + manual physics, or vice versa.

> **Pitfall**: When `visual` is present, the engine-created object already exists when `ready()` runs. Never call `this.scene.add.sprite()` etc. to re-create it. Use `this.getVisualObject()` for display work and `this.getPhysicsObject()` for movement/collision when the distinction matters.

---

## VisualDef

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `type` | string | yes | `"rect"`, `"image"`, `"spritesheet"`, `"atlas"` |
| `width` | number | varies | Display width (px); use with `height` |
| `height` | number | varies | Display height (px); use with `width` |
| `ratio` | number | no | Uniform scale from the source texture or frame size |

Size can be expressed in exactly one way:

- `width` + `height`: explicit layout size in world pixels.
- `ratio`: source texture/frame size multiplied by this value.

Do not combine `ratio` with `width`/`height`. `vibegame check` rejects mixed size definitions. Runtime still runs mixed data for debugging and prioritizes `width`/`height`.

**Multi-frame contract.** When the node has `animations`, `width` / `height` apply only to the first real animation frame and establish the sprite scale inherited by later frames. Concretely:

- `width` / `height`: first-frame target size. Later frames keep the same scale, so wider or taller source bboxes render wider or taller in game.
- `ratio`: per-frame multiplier on that frame's native bbox.

This means **source frames must be scale-consistent** across the asset (same intrinsic pixels-per-unit across all clips and facings). `width`/`height` no longer normalizes each frame into the same rectangle; it only picks the base scale. `ratio` still scales each current frame from its native bbox.

### rect — colored rectangle (no asset needed)

| Field | Required | Description |
|-------|----------|-------------|
| `color` | yes | Hex color e.g. `"0x4a6741"` |

```json
"visual": { "type": "rect", "width": 32, "height": 48, "color": "0x3388ff" }
```

### image — static texture

| Field | Required | Description |
|-------|----------|-------------|
| `texture` | yes | Asset key from manifest.json |

```json
"visual": { "type": "image", "texture": "sword", "width": 28, "height": 8 }
```

Or use uniform source-size scaling:

```json
"visual": { "type": "image", "texture": "sword", "ratio": 2 }
```

Pivot is read from the manifest entry (`<asset>.pivot`). See [Pivot](./animation-guide.md#pivot).

### spritesheet — uniform frame grid

| Field | Required | Description |
|-------|----------|-------------|
| `texture` | yes | Asset key (manifest must have `frameWidth`/`frameHeight`) |
| `frame` | no | Initial frame index (default 0) |
| `animations` | no | `{ name: AnimDef }` inline clips (old style; prefer top-level `animations`) |

```json
"visual": { "type": "spritesheet", "texture": "hero", "width": 32, "height": 48 }
```

```json
"visual": { "type": "spritesheet", "texture": "hero", "ratio": 2 }
```

> **Pitfall**: `sprite.width`/`height` return texture size, not rendered size. Use `sprite.displayWidth`/`displayHeight` for collision math. Use `setDisplaySize(w, h)` to resize; do not modify source asset files.

### atlas — variable-size named frames

| Field | Required | Description |
|-------|----------|-------------|
| `texture` | yes | Asset key (manifest must have `sprites` bbox map) |
| `frame` | no | Initial frame name. Omitting it shows entire texture (usually wrong). |

```json
"visual": { "type": "atlas", "texture": "hero_atlas", "frame": "idle_0", "width": 32, "height": 48 }
```

```json
"visual": { "type": "atlas", "texture": "hero_atlas", "frame": "idle_0", "ratio": 2 }
```

Pivot cascade: manifest sprite-level `pivot` > manifest group-level `pivot` > engine default `[0.5, 1]`. See [Pivot](./animation-guide.md#pivot) for the full rules including clip-level override.

When atlas frames vary a lot in size, prefer a separated collider host:

```json
"collider": { "body": "dynamic", "host": "separate", "width": 20, "height": 40 }
```

Sprite-to-physics-host alignment is automatic: collider pivot inherits from the visual sprite's resolved origin (see [collision-guide.md#pivot](./collision-guide.md#pivot)), so feet on the sprite land on body bottom without manual `visualTransform`. Use `visualTransform` only when you need an explicit node-wide visual offset on top. Use `FrameRef.offset` for one animation frame occurrence. If a collider exists and any frame uses `offset`, keep `collider.host: "separate"`.

```json
"visualTransform": { "offsetX": 0, "offsetY": -8 }
```

This makes the node use:

- `visualObject` for sprite frames and animation
- `gameObject` / `physicsObject` for stable movement and collision
- automatic post-physics visual syncing by the engine

`visualTransform` fields:

| Field | Default | Description |
|-------|---------|-------------|
| `offsetX` | 0 | Visual X offset from the transform/physics host |
| `offsetY` | 0 | Visual Y offset from the transform/physics host |

---

## Script Template

```javascript
import { Node } from '/engine/Node.js'

export default class MyScript extends Node {
  ready() {}      // init (visual/physics objects exist if declared)
  update(dt) {}   // per-frame, dt in seconds
  destroy() {}    // cleanup manually-created objects only
}
```

One class per file; filename matches class name. Use `ready()` for init, not constructor (`this.scene` is null in constructor). See [script-rules.md](./script-rules.md) for full conventions.

---

## Node Lifecycle & Engine-Injected Properties

| Property | Type | Description |
|----------|------|-------------|
| `scene` | Phaser.Scene | Direct access to Phaser API |
| `sceneTree` | SceneTree | The scene tree managing this node |
| `gameObject` | Phaser.GameObject\|null | Primary runtime object. With `collider.host: "separate"`, this is the physics host |
| `visualObject` | Phaser.GameObject\|null | Visual object created from `visual`, when present |
| `physicsObject` | Phaser.GameObject\|null | Physics host object, when collider is attached |
| `config` | object | The `config` block from scene JSON |
| `parent` | Node\|null | Parent node |
| `children` | Node[] | Direct children |
| `tags` | string[] | Tags from NodeDef |
| `animationPlayer` | AnimationPlayer\|null | Frame-based playback from `animations` |
| `animator` | Animator\|null | State machine from `animator` |

```javascript
ready()       // Post-order: children first, then parent. May be async (engine awaits it).
              // visual object and body/physics host already exist if visual/collider declared.
update(dt)    // Pre-order: parent first, then children. dt in seconds.
              // Only called when sceneTree.running === true.
destroy()     // Called when node removed. Engine handles declarative cleanup.
```

## Transform Inheritance

The node tree is a lightweight gameplay hierarchy, not a full Unity-style transform system. When a parent node has a transform object (`physicsObject` / `gameObject`, falling back to `visualObject`), the engine propagates only these parent changes to direct children:

- `x`
- `y`
- `displayWidth`
- `displayHeight`
- `flipX`, only across an edge whose child sets `config.flipWithParent: true`

The propagation is delta-based: after initial placement, moving or resizing a parent moves and resizes child transform objects by the same parent delta. This continues down the tree. Child scripts can still make their own per-frame adjustments after the parent delta has been applied.

Horizontal flip is opt-in per direct parent-child edge. With `config.flipWithParent: true`, the engine mirrors the child's local X around its parent, flips its visual, and mirrors collider `offsetX`. Authored child flip and inherited flip compose with XOR. The rule repeats at every level, while an edge without the option cuts flip inheritance below that parent. The default is `false`, so existing children keep their authored layout. Rotation and `flipY` are not inherited.

Physics follows the same simple rule: when a child transform object is moved or resized by transform inheritance, its Arcade body is refreshed. If the child uses `collider.host: "separate"`, the visual object follows the physics host position plus `visualTransform` offset and is resized by the same delta. `visualTransform.offsetX/Y` also scale by the same parent resize ratio. Arcade Physics bodies remain axis-aligned; rotated box colliders are not supported.

---

## Tree Operations

```javascript
getChild(name)              // Direct child by name → Node|null
getNode(path)               // Path: "Child", "..", "Group/Child", "../Sibling" → Node|null
findByTag(tag)              // All ENABLED nodes with tag in scene → Node[] (disabled placeholder/template nodes are filtered)
addChild(node)              // Async. Add child, sets parent/sceneTree, awaits ready().
removeSelf()                // Remove this node and children, calls destroy() recursively.
instantiate(src, config?)   // Async. Load .node.json, add as child of this node.
changeScene(name)           // Destroy current scene, load new one.
```

---

## Input

```javascript
update(dt) {
  const input = this.sceneTree.inputMap
  if (!input) return                      // guard: inputMap may not be set
  if (input.isHeld('move_left'))  { /* ... */ }
  if (input.isPressed('jump'))    { /* ... */ }
  if (input.isReleased('attack')) { /* ... */ }
}
```

`isPressed` = just pressed this frame. `isHeld` = currently held. `isReleased` = just released. Returns `false` when a UI input element has focus.

`this.sceneTree.running`: false = edit mode, true = play mode (no `update()` calls).

---

## Dynamic Node Instantiation

> **Procedural entities MUST use `.node.json` templates.** "Procedural" means "spawned at runtime via code" — it does NOT mean "created without template files." Always define the entity's visual, collider, and config defaults in a `.node.json`, then spawn instances via `instantiate()`. The template IS the entity definition; `instantiate()` is how you place it programmatically.

```javascript
// Instantiate a .node.json as a child of this node at runtime
const bullet = await this.instantiate('entities/bullet.node.json', { x: 100, y: 200 })
```

Scripts used by dynamically instantiated nodes must be registered before instantiation:

```javascript
// Option A: manual registration in ready()
import Bullet from './Bullet.js'
ready() {
  this.sceneTree.scriptClasses['Bullet'] = Bullet
}

// Option B: disabled placeholder node in scene JSON (collectScripts discovers it at load time)
{ "name": "_BulletTemplate", "script": "Bullet", "enabled": false }

// Option B also preloads the .node.json for instantiate():
// { "name": "_BulletTemplate", "src": "entities/bullet.node.json", "enabled": false }
// This registers the script AND caches the template in sceneTree.nodeDefinitions in one node.
```

> **Pitfall**: Do NOT call `sceneTree._buildNode()`. It is private. Use `instantiate()` or `addChild()` — they attach the node correctly and await `ready()`.

> **Pitfall**: `instantiate(src)` throws if `src` was never preloaded. Boot discovers templates by scanning scene JSON for `src` references — a path that only appears as a string in script code is invisible to that scan. Keep the disabled placeholder in the scene (Option B above), or fetch and register the definition into `sceneTree.nodeDefinitions` yourself before instantiating. `vibegame check` warns about unpreloaded `instantiate()` literals.

---

## Node Reuse via src

Save any NodeDef as a `.node.json` file, reference from any scene:

```json
{
  "name": "Hero",
  "script": "PlayerController",
  "visual": { "type": "spritesheet", "texture": "hero", "width": 32, "height": 48 },
  "collider": { "body": "dynamic", "width": 20, "height": 40, "gravity": true },
  "config": { "speed": 200, "jumpForce": 420 }
}
```

```json
{ "src": "entities/hero.node.json", "config": { "x": 100, "y": 400 } }
{ "src": "entities/hero.node.json", "config": { "x": 300, "y": 400, "speed": 300 } }
```

Resolution order: load file → deep clone → merge inline `config` on top → inline `name`/`tags`/`enabled` override loaded values. Other fields (`visual`, `collider`, `script`, `children`) come from file.

---

## MountPoint (built-in component)

A child node that follows parent position with configurable offset. Use for weapon slots, equipment, followers.

```json
{
  "name": "Player",
  "script": "PlayerController",
  "visual": { "type": "spritesheet", "texture": "hero", "width": 32, "height": 48 },
  "children": [{
    "name": "WeaponSlot",
    "script": "MountPoint",
    "config": { "offsetX": 10, "offsetY": -2, "aimRotation": true, "flipWithParent": true }
  }]
}
```

MountPoint config:

| Field | Default | Description |
|-------|---------|-------------|
| `offsetX` | 0 | X offset from parent position |
| `offsetY` | 0 | Y offset from parent position |
| `aimRotation` | false | Rotate toward aim direction (mouse/stick) |
| `flipWithParent` | true | Mirror offsetX when parent is flipped |

```javascript
ready() {
  this.weaponSlot = this.getChild('WeaponSlot')
  await this.weaponSlot.mount('entities/weapons/sword.node.json')
}

async onPickup(weaponSrc) {
  await this.weaponSlot.mount(weaponSrc)  // replaces previous mount
}
```

Methods: `mount(src)` → Node, `unmount()`, `getMounted()` → Node|null.

---

## AI Behavior Patterns

Use `config` to switch between player and AI control on the same script:

```javascript
ready()    { this.isAI = this.config.isAI || false }
update(dt) { this.isAI ? this.updateAI() : this.updatePlayer() }

updateAI() {
  const target = this.findByTag('ball')[0]
  if (!target?.gameObject) return
  const diff = target.gameObject.y - this.gameObject.y
  if (Math.abs(diff) > 10) {
    this.gameObject.body.setVelocityY(Math.sign(diff) * this.speed * this.aiReaction * 10)
  } else {
    this.gameObject.body.setVelocityY(0)
  }
}
```

---

## Complete Example: Platformer

**scene.json:**

```json
{
  "name": "Level 1",
  "root": {
    "name": "Root",
    "children": [
      { "src": "entities/hero.node.json", "config": { "x": 100, "y": 400 } },
      {
        "name": "Ground", "tags": ["ground"],
        "visual": { "type": "rect", "width": 800, "height": 40, "color": "0x4a6741" },
        "collider": { "body": "static" },
        "config": { "x": 400, "y": 580 }
      },
      {
        "name": "Coin", "tags": ["pickup"],
        "visual": { "type": "rect", "width": 16, "height": 16, "color": "0xffd700" },
        "collider": { "body": "static" },
        "config": { "x": 300, "y": 450 }
      }
    ]
  }
}
```

**entities/hero.node.json:**

```json
{
  "name": "Hero",
  "script": "PlayerController",
  "visual": { "type": "spritesheet", "texture": "hero", "width": 32, "height": 48 },
  "collider": { "body": "dynamic", "width": 20, "height": 40, "gravity": true, "worldBounds": true },
  "config": { "speed": 200, "jumpForce": 420 }
}
```

**scripts/PlayerController.js:**

```javascript
import { Node } from '/engine/Node.js'

export default class PlayerController extends Node {
  ready() {
    this.speed = this.config.speed
    this.jumpForce = this.config.jumpForce
    this.isGrounded = false

    for (const g of this.findByTag('ground')) {
      this.trackCollider(g.gameObject, g)
    }
    this.on('collision_enter', ({ other }) => {
      if (other.tags.includes('ground')) this.isGrounded = true
    })
    this.on('collision_exit', ({ other }) => {
      if (other.tags.includes('ground')) this.isGrounded = false
    })

    // Pickup: overlap (no blocking), destroy on contact
    for (const p of this.findByTag('pickup')) {
      this.scene.physics.add.overlap(this.gameObject, p.gameObject, () => {
        p.removeSelf()
      })
    }
  }

  update(dt) {
    const input = this.sceneTree.inputMap
    if (!input || !this.gameObject?.body) return

    const vx = input.isHeld('move_left') ? -this.speed
             : input.isHeld('move_right') ? this.speed : 0
    this.gameObject.body.setVelocityX(vx)

    if (input.isPressed('jump') && this.isGrounded) {
      this.gameObject.body.setVelocityY(-this.jumpForce)
    }
  }
}
```
