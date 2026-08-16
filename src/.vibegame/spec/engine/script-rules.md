# Script Writing Rules

Conventions for writing game scripts. For full examples and patterns, see the guide files.

---

## File Structure

```javascript
import { Node } from '/engine/Node.js'

export default class MyScript extends Node {
  ready() {}      // init: scene, config, sceneTree available. visual/physics objects set if declared.
  update(dt) {}   // per-frame, dt in seconds
  destroy() {}    // cleanup (engine handles declarative visual/collider automatically)
}
```

- One class per file; filename matches class name (`Paddle.js` → `class Paddle`)
- `"script": "Paddle"` in NodeDef → loads `scripts/Paddle.js`
- Built-in scripts (`TileMap`, `Collider`, `MountPoint`) resolve from `/engine/scripts/`
- Files in `scripts/` MUST NOT end with `Module` — that suffix is reserved for shipped reusable modules in `modules/`. See [modules.md](./modules.md).
- `*.node.json` files: live anywhere in project; `src` field uses relative path

---

## Declarative vs Manual

When `visual`/`collider` fields are present in NodeDef: engine creates the visual object and body/physics host before `ready()`. Script writes only gameplay logic. With `collider.host: "separate"`, `gameObject` points at the physics host and `visualObject` points at the sprite/image.

When absent: script creates Phaser objects manually in `ready()`.

See [entity-guide.md](./entity-guide.md) for full explanation, patterns, and examples.

---

## Core Rules

1. **Extend Node, override lifecycle** — `ready()`, `update(dt)`, `destroy()`
2. **Read all params from `this.config`** — never hardcode gameplay values
3. **Set `this.gameObject`** — required for editor selection; engine sets it in declarative mode. Use `getVisualObject()` for animation/display and `getPhysicsObject()` for movement/collision when separation matters.
4. **Access input via `this.sceneTree.inputMap`** — guard: `if (!input) return`
5. **Cross-node events via `emit`/`on`** — events bubble up; siblings listen on `this.parent`
6. **Node lookup via `findByTag()`** — don't rely on names for cross-tree lookups
7. **Cleanup in `destroy()`** — only manually-created Phaser objects; engine cleans up declarative ones

## Transform Rules

Parent transform object changes propagate to children for `x`, `y`, `displayWidth`, and `displayHeight`. Horizontal flip also propagates when the child explicitly sets `config.flipWithParent: true`; this mirrors local X, visual `flipX`, and collider `offsetX`. Each parent-child edge opts in independently, and authored flip combines with inherited flip using XOR. Rotation, angle, scale fields, and `flipY` are not inherited.

Inheritance is **delta-based**: each frame, the parent's movement since the previous frame is re-applied to every child. Data flows one way only — the parent drives its children. Never write the parent's transform from a child's current position inside `update()`: the inheritance re-applies that movement to the child as a parent delta, compounding the child's displacement every frame. Either move the parent and let children inherit, or keep the parent static and let children move themselves (reading child positions is fine; writing them back to the parent is not).

`visualTransform.offsetX/Y` aligns separated visuals relative to their transform/physics host. The engine applies it automatically when syncing `visualObject` to `physicsObject`.

Arcade Physics colliders stay simple: inherited movement/resizing refreshes the body, but rotated box collision is not supported.

---

## Import Path Rules

| Context | Style | Example |
|---------|-------|---------|
| Engine modules | Absolute `/engine/` | `import { Node } from '/engine/Node.js'` |
| Between game scripts | Relative `./` | `import MapGen from './MapGen.js'` |
| Fetch config/data files | appBasePath helper | `fetchJson('config/levels.json')` |

Do not use `/game/...` anywhere in game code. `vibegame run` serves project files at the same URLs as a plain static server, so `/assets/...`, `/config/...`, `/scripts/...` are project files at root, not under `/game`.

For custom fetches or DOM image paths, prefer the engine URL helpers:

```javascript
import { assetUrl, fetchJson } from '../engine/url.js'

const config = await fetchJson('config/levels.json')
icon.src = assetUrl('ui/icon_heart.svg')
```

Do not hardcode root project resource paths such as `/assets/...` in gameplay scripts. They work only when the game is hosted at domain root and break when `appBasePath` is non-empty.

`assetBasePath` only affects manifest asset loading, not arbitrary script imports or custom fetch calls.

For page-level startup rules, see [project-setup.md](./project-setup.md). UI may gate gameplay, but must not bypass or replace engine boot.

---

## API Requests

When scripts need to call a backend API (e.g. save game state, AI turn, multiplayer):

1. **Read `apiBaseUrl` from `this.sceneTree.apiBaseUrl`** — engine resolves it from injected config at boot.
2. **Construct URLs**: `this.sceneTree.apiBaseUrl + '/api/your-endpoint'`
3. **Never hardcode `location.origin`** — in dev mode the page comes from `vibegame run` (port 8765) but the API is elsewhere.

```javascript
ready() {
  const base = this.sceneTree.apiBaseUrl
  fetch(`${base}/api/game/new`, { method: 'POST' })
}
```

**API URL priority** (handled by engine at boot, scripts just use `sceneTree.apiBaseUrl`):
1. URL query `?serverUrl=` (emergency override)
2. Scene config `serverUrl` (per-scene override)
3. `window.__APP_CONFIG__.apiBaseUrl` (injected from project.json runtimeDefaults)
4. `location.origin` (same-origin fallback)

---

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Re-creating `gameObject` / `visualObject` in `ready()` when `visual` declared | Engine already created it. Use `this.getVisualObject()` or `this.gameObject`. |
| Re-creating physics body when `collider` declared | Engine already configured `this.gameObject.body`. Just use it. |
| Expecting child rotation or rotated colliders to follow parent | Only `x`, `y`, `displayWidth`, and `displayHeight` are inherited. Arcade box colliders stay axis-aligned. |
| Destroying engine-created objects in `destroy()` | Engine handles cleanup for declarative visual/collider. |
| Using constructor for Phaser objects | `this.scene` is null in constructor. Use `ready()`. |
| Hardcoding numbers in scripts | Read from `this.config`. |
| Not setting `this.gameObject` in manual mode | Editor can't select/drag. Set it in `ready()`. |
| Listening on a sibling directly | Listen on `this.parent` — events bubble up, not sideways. |
| `sceneTree.inputMap` without guard | `if (!input) return` in case inputMap is not set. |
| `body.setAllowGravity(false)` forgotten (manual) | Use `"gravity": false` in `collider` field instead. |
| Creating colliders before target nodes are ready | `ready()` is post-order. Parent can safely reference children's `gameObject`. |
| `sprite.width`/`height` for collision math | Use `displayWidth`/`displayHeight` for rendered dimensions. Resize via `setDisplaySize()`, don't modify source asset files. |
| Parent script "follows" a child's position each frame | Feedback loop: the child's movement becomes a parent delta, which inheritance re-applies to the child — displacement compounds every frame. Move the parent and let children inherit, or keep the parent static and read the child's position. |
| Calling Phaser `body.setSize()` / `setCircle()` / `setOffset()` in scripts | Collision-box geometry belongs in the declarative `collider` field (world px; the engine converts to Phaser's pre-scale coords and auto-aligns the pivot offset). Raw calls take **pre-scale texture coords** (scaled again on a resized visual) and bypass the pivot alignment. For per-state hitboxes (crouch, morph), toggle child `Collider` nodes via `enable()`/`disable()` instead of resizing one body. |
| Sibling `ready()` order wrong | Children array order = `ready()` order. Put listeners before emitters. |
| Depth layering problems | Convention: 0-9 terrain, 10-49 bg, 50 full-screen hitArea, 60+ interactive. Clickable objects need depth > 50 when hitArea exists. |
| `pointer.x/y` inside Container | Those are screen coords. Add container offset for world coords. |
| Hardcoding `location.origin` for API calls | Use `this.sceneTree.apiBaseUrl`. In dev mode the page and API are on different ports. |
| Hardcoding `/game/...` resource URLs | Use `assetUrl()`, `resourceUrl()`, or `fetchJson()` from `engine/url.js`. |
| Extending Node for pure data | Extend Node only when you need lifecycle (`update()`, events). Use plain class for pure data/algorithms. |

---

## Phaser Pitfalls

Known Phaser 3 issues that are NOT engine bugs but will bite you:

| Pitfall | Symptom | Workaround |
|---------|---------|------------|
| Graphics.fillPoints inside Container | Fill is invisible even with high depth and alpha. strokePoints works fine. | Don't use Graphics fill to overlay on Images inside a Container. Use `scene.add.image` + RenderTexture/generateTexture with tint + alpha instead. |
| setInterval network requests | `vibegame run` Playwright page load hangs (timeout 30s). | Never use `setInterval` + `fetch` during init. Use chained `setTimeout` (next call after previous completes), and delay first call by 3s+. |

---

See [entity-guide.md](./entity-guide.md) for entity creation and AI patterns, [collision-guide.md](./collision-guide.md) for physics, [animation-guide.md](./animation-guide.md) for animations, and [runtime.md](./runtime.md) for runtime startup, testing, and automation.
