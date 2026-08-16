# Project Setup

Goal: from empty directory to a running game.

---

## How the Engine Reads Your Game

Three main layers:

1. `project.json` — entry point: canvas settings, start scene, physics, optional input map
2. `*.scene.json` — one scene as a tree of nodes (object hierarchy per level)
3. `NodeDef` — one gameplay object: visual, collider, script, config, children

Supporting files:
- `manifest.json` — asset preload declarations (textures, spritesheets, atlases). Listed in `project.json.manifests`, defaults to `assets/manifest.json`.
- `input-map.json` — action → key bindings, read via `sceneTree.inputMap`
- `*.node.json` — reusable NodeDefs referenced via `src`

The whole game structure is explicit data — it can be generated, diffed, and refactored by agents and editors.

### Runtime Flow

1. Read `project.json`
2. Load all manifests listed in `project.json.manifests` (defaults to `assets/manifest.json`) and merge
3. Open `startScene`
4. Build node tree — for each node: create visual object, configure body/physics host (collider), init animation helpers
5. Call `ready()` post-order: children first, then parent
6. Each frame: call `update(dt)` pre-order: parent first, then children; advance animator + clip playback

**Boot ownership rules:**
- `boot()` must run unconditionally when the page loads.
- DOM UI may gate gameplay, but must not gate, bypass, replace, or delay engine boot.
- Any title screen, start button, loading UI, or overlay must control the already-booted runtime, not create a second startup flow.
- Page-level code must not create its own `PhaserHost`, `SceneTree`, or debug connection outside the engine boot path.

**Lifecycle order to remember:**
- `ready()`: children first → parent (parent can rely on children being initialized)
- `update(dt)`: parent first → children (children react to parent's frame state)

---

## project.json

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | yes | Display name |
| `version` | string | yes | Semantic version |
| `engine` | string | yes | Engine identifier (e.g. `"vibegame@0.1.0"`) |
| `settings` | object | yes | Phaser game settings |
| `startScene` | string | yes | Relative path to initial scene JSON |
| `manifests` | string[] | no | Manifest paths to load and merge. Defaults to `["assets/manifest.json"]` |
| `inputMap` | string | no | Relative path to input-map.json |
| `runtimeDefaults` | object | no | Environment-specific runtime config for dev/deploy |
| `releaseExtraRoots` | string[] | no | Additional roots to include in release branch (e.g. `["server/src/"]`) |

### settings

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `width` | number | 800 | Canvas width (px) |
| `height` | number | 600 | Canvas height (px) |
| `scaleMode` | string | `"FIT"` | Phaser scale mode: `NONE`, `FIT`, `RESIZE`, `ENVELOP`, `WIDTH_CONTROLS_HEIGHT`, `HEIGHT_CONTROLS_WIDTH` |
| `pixelArt` | boolean | false | Nearest-neighbor scaling |
| `transparent` | boolean | false | Transparent canvas background |
| `backgroundColor` | string | `"#000000"` | CSS hex (ignored when `transparent: true`) |
| `physics.gravity` | `{x, y}` | `{x:0, y:0}` | World gravity px/s^2 |
| `physics.debug` | boolean | false | Physics debug overlay |

### runtimeDefaults

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `dev.appBasePath` | string | `""` | URL path prefix for local dev |
| `dev.apiBaseUrl` | string | `""` | Business API base URL for local dev |
| `deploy.appBasePath` | string | `""` | URL path prefix for production |
| `deploy.apiBaseUrl` | string | `""` | Business API base URL for production |

See `deployment.md` for the full injection flow and API URL priority chain.

```json
{
  "name": "Demo Game",
  "version": "0.1.0",
  "engine": "vibegame@0.1.0",
  "settings": {
    "width": 800, "height": 600,
    "scaleMode": "FIT",
    "pixelArt": true, "backgroundColor": "#1a1a2e",
    "physics": { "gravity": { "x": 0, "y": 980 }, "debug": false }
  },
  "startScene": "scenes/level-1.scene.json",
  "inputMap": "config/input-map.json",
  "runtimeDefaults": {
    "dev": { "appBasePath": "", "apiBaseUrl": "http://127.0.0.1:3001" },
    "deploy": { "appBasePath": "", "apiBaseUrl": "" }
  }
}
```

---

## manifest.json

Declare all assets here. Runtime loads each manifest listed in `project.json.manifests` and merges them. Defaults to `["assets/manifest.json"]` if not specified.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `type` | string | yes | `"image"`, `"spritesheet"`, `"atlas"`, `"placeholder_atlas"`, `"placeholder_image"`, `"tileset"` |
| `path` | string | image/spritesheet/atlas/tileset | Relative to the manifest file's directory |
| `frameWidth` | number | spritesheet | Frame width (px) |
| `frameHeight` | number | spritesheet | Frame height (px) |
| `sprites` | object | atlas | `{ name: { bbox: [x, y, w, h] } }` |
| `frames` | string[] | placeholder_atlas | Semantic frame names mapped onto the built-in placeholder sheet |
| `shape` | string | placeholder_image | Placeholder-only source shape: `"rectangle"`, `"circle"`, or `"hex"`; invalid for real image / atlas |
| `color` | string | placeholder_image | Placeholder-only fill color, e.g. `"#ff3366"` or `"0xff3366"`; invalid for real image / atlas |

```json
{
  "hero": { "type": "spritesheet", "path": "hero.png", "frameWidth": 32, "frameHeight": 48 },
  "terrain": {
    "type": "atlas",
    "path": "terrain.png",
    "sprites": {
      "grass": { "bbox": [0, 0, 32, 32] },
      "dirt":  { "bbox": [32, 0, 32, 32] }
    }
  },
  "hero_idle": {
    "type": "placeholder_atlas",
    "frames": ["idle_0", "idle_1", "idle_2", "idle_3"],
    "pivot": [0.5, 1]
  },
  "sword_proto": {
    "type": "placeholder_image",
    "shape": "rectangle",
    "color": "#ff3366",
    "pivot": [0.5, 0.5]
  },
  "sword": { "type": "image", "path": "sword.png" },
  "forest": { "type": "tileset", "path": "tilesets/forest.png", "tileSize": 16, "tiles": {} }
}
```

**atlas**: variable-size frames in a packed sprite sheet. No separate atlas JSON needed — `bbox [x, y, w, h]` defined inline. Reference frames by name: `sprite.setTexture('terrain', 'grass')`.

**placeholder_atlas**: prototype-only atlas-shaped entry. It has no `path`; the engine maps semantic frame names onto the built-in `__placeholder_atlas__` image, so node.json can use `visual.type: "atlas"` from day one. Polish replaces this manifest entry with a real `atlas` entry using the same key and frame names.

**placeholder_image**: prototype-only image-shaped entry. It has no `path`; the engine registers the semantic key as a generated Phaser texture and also resolves it as a generated PNG data URL through `sceneTree.ui`. `shape` and `color` are placeholder-only source appearance hints, not runtime size. `shape: "circle"` and `shape: "hex"` still produce a rectangular source texture with the shape drawn inside its smallest flat bounding rectangle. Use scene / node visual size or CSS to set display size. Polish replaces this manifest entry with a real `image` entry using the same key and removes placeholder-only fields.

**tileset**: points to a PNG with inline tile metadata in the same manifest entry. See [tilemap-guide.md](./tilemap-guide.md).

---

## input-map.json

Maps logical action names to Phaser key codes (`Phaser.Input.Keyboard.KeyCodes` property names).

```json
{
  "move_left":  ["LEFT", "A"],
  "move_right": ["RIGHT", "D"],
  "jump":       ["SPACE", "UP", "W"],
  "attack":     ["J"],
  "interact":   ["E"],
  "pause":      ["ESC"]
}
```

Common key names: `LEFT`, `RIGHT`, `UP`, `DOWN`, `SPACE`, `ESC`, `ENTER`, `SHIFT`, `CTRL`, `A`-`Z`, `ZERO`-`NINE`, `F1`-`F12`.

Scripts read input via `this.sceneTree.inputMap` — see [entity-guide.md](./entity-guide.md).

---

## Cross-File Dependencies

| Dependency | Rule |
|-----------|------|
| `project.json -> startScene` | Must point to a real `*.scene.json` |
| `project.json -> inputMap` | Optional; if set, must point to a real `input-map.json` |
| `visual.texture` / `animations.clips` source | Texture key must exist in merged manifest |
| `src` in NodeDef | Must point to a real `*.node.json` |
| `script` in NodeDef | Class name (not path); file must be `scripts/<Name>.js` |
| `animator.states[*].clip` | Must reference a clip defined in `animations.clips` |

---

## Directory Layout

```
game-root/
  project.json
  scenes/
    level-1.scene.json
  entities/                     # reusable node definitions
    hero.node.json
    weapons/
      sword.node.json
  scripts/
    PlayerController.js
    SlimeAI.js
  maps/
    level1.tilemap.json
  config/
    input-map.json
  assets/
    manifest.json
    sprites/
      hero.png
      terrain.png
    tilesets/
      forest.tileset.json
      forest.png
    audio/
```

---

## Minimal Runnable Walkthrough

From empty directory to running game. Five files, no assets needed (rect visuals only).

**project.json** — entry point:

```json
{
  "name": "My Game",
  "version": "0.1.0",
  "engine": "vibegame@0.1.0",
  "settings": {
    "width": 800, "height": 600,
    "backgroundColor": "#1a1a2e",
    "physics": { "gravity": { "x": 0, "y": 980 } }
  },
  "startScene": "scenes/main.scene.json",
  "inputMap": "config/input-map.json"
}
```

**config/input-map.json** — key bindings:

```json
{ "move_left": ["LEFT", "A"], "move_right": ["RIGHT", "D"] }
```

**assets/manifest.json** — no assets for rect-only game:

```json
{}
```

**scenes/main.scene.json** — player on a ground:

```json
{
  "name": "Main",
  "root": {
    "name": "Root",
    "children": [
      {
        "name": "Player",
        "script": "Player",
        "visual": { "type": "rect", "width": 32, "height": 48, "color": "0x3388ff" },
        "collider": { "body": "dynamic", "gravity": true, "worldBounds": true },
        "config": { "x": 100, "y": 300, "speed": 200 }
      },
      {
        "name": "Ground",
        "visual": { "type": "rect", "width": 800, "height": 40, "color": "0x4a6741" },
        "collider": { "body": "static" },
        "config": { "x": 400, "y": 580 }
      }
    ]
  }
}
```

**scripts/Player.js** — move left/right:

```javascript
import { Node } from '/engine/Node.js'

export default class Player extends Node {
  ready() {
    this.speed = this.config.speed
  }

  update(dt) {
    const input = this.sceneTree.inputMap
    if (!input || !this.gameObject?.body) return
    const vx = input.isHeld('move_left') ? -this.speed
             : input.isHeld('move_right') ? this.speed : 0
    this.gameObject.body.setVelocityX(vx)
  }
}
```

The engine reads `project.json`, loads all manifests from `project.json.manifests` (or the default `assets/manifest.json`), builds the node tree, calls `ready()` (children first), then runs `update(dt)` every frame (parent first). Open the project in the editor and press Play.
