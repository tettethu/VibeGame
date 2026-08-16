# Engine Internals Reference

Internal engine classes for integrating vibegame into a custom host environment.
**Not injected into game agent context by default.** Game scripts do not need to import or call these directly.

---

## SceneTree

`import { SceneTree } from '/engine/SceneTree.js'`

Manages the node tree lifecycle. Created by the editor/host, not by game scripts.

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `nodes` | Map<string, Node> | All registered nodes by ID |
| `root` | Node\|null | Root node of current scene |
| `phaserScene` | Phaser.Scene | The Phaser scene instance |
| `scriptClasses` | object | `{ scriptName: class }` registry |
| `nodeDefinitions` | object | `{ srcPath: nodeDef }` loaded `.node.json` registry |
| `inputMap` | InputMap\|null | The input map instance |
| `running` | boolean | false = edit mode (no update), true = play mode |
| `tilesets` | object | `{ tilesetName: tilesetJSON }` preloaded tileset definitions |
| `tilemaps` | object | `{ srcPath: tilemapJSON }` preloaded tilemap data |

### Methods

```javascript
async load(sceneJson)
    // Replace the current tree, build from scene JSON, await ready(), and bind scene postupdate sync.

async loadScript(name, url)
    // Dynamically import a script module and register its default export.

async propagateReady(node)
    // Await ready() post-order (children first, then parent).

propagateUpdate(node, dt)
    // Call update() pre-order (parent first, then children). Skips disabled nodes.

update(time, delta)
    // Frame callback from PhaserHost. delta in ms; converted to seconds internally.
    // Only propagates when running === true.

register(node)
    // Add a node to the nodes Map.

removeNode(node)
    // Recursively destroy children, call destroy(), remove from parent and Map.

findByTag(tag)
    // Return all ENABLED nodes whose tags include the given tag.
    // Disabled nodes are excluded — they have no gameObject so returning
    // them would break callers that immediately do physics/render work.

async instantiateNode(nodeSrc, configOverride, parent)
    // Load .node.json, deep-clone, merge config, build, register, and await ready().

changeScene(sceneName)
    // Destroy current root and unbind scene postupdate sync. Caller loads new JSON and calls load().

destroyAll()
    // Destroy root, clear the nodes Map, and unbind scene postupdate sync.

static collectScripts(nodeDef, scripts?)
    // Recursively collect all script names referenced in a scene definition.
    // Returns Set<string>. Used for dynamic script loading before scene load.
```

> `_buildNode(def, parent)` is private. Do not call from gameplay scripts. Use `node.instantiate()` or `node.addChild()` instead.

### Dynamic script registration

`collectScripts()` only discovers scripts referenced in the scene JSON. Scripts used by dynamically created nodes must be registered manually first, otherwise `_buildNode()` falls back to base `Node` and logs an explicit error.

**Option A — manual registration in ready():**

```javascript
import Bullet from './Bullet.js'

ready() {
  this.sceneTree.scriptClasses['Bullet'] = Bullet
}
```

**Option B — disabled placeholder node in scene JSON:**

```json
{ "name": "_BulletTemplate", "script": "Bullet", "enabled": false }
```

The `enabled: false` node is never initialized, but `collectScripts()` discovers its script name and preloads the class.

---

## PhaserHost

`import { PhaserHost } from '/engine/PhaserHost.js'`

Creates and manages the Phaser.Game instance. Thin wrapper that delegates update calls to SceneTree.

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `game` | Phaser.Game\|null | The Phaser game instance |
| `sceneTree` | SceneTree\|null | Assigned externally; receives update calls |
| `phaserScene` | Phaser.Scene\|null | Set during Phaser create callback |
| `assetManifest` | object\|null | Contents of manifest.json. Set before `init()`. |
| `assetBasePath` | string | Base URL for asset files (default: `/assets`; normally set by `boot.js` from `appBasePath`) |
| `onReady` | function\|null | Callback invoked when Phaser scene is created |

### Asset Preloading

`onPreload()` iterates `assetManifest` entries and calls the appropriate Phaser loader:

| Type | Loader | Notes |
|------|--------|-------|
| `spritesheet` | `load.spritesheet()` | Needs `frameWidth`, `frameHeight` |
| `atlas` | `load.atlas({ atlasData })` | Converts `sprites` bbox `[x,y,w,h]` to Phaser atlas JSON inline |
| `image` / other | `load.image()` | Fallback |

### Methods

```javascript
init(container, projectConfig)
    // Create a Phaser.Game instance.
    // container: HTMLElement to render into.
    // projectConfig: contents of project.json.
    // Disables global keyboard capture so UI inputs work.

destroy()
    // Destroy the Phaser game instance and null the reference.
```

### Typical Initialization Flow

```javascript
const host = new PhaserHost()
const tree = new SceneTree()

host.onReady = async (phaserScene) => {
  tree.phaserScene = phaserScene
  // load scripts, input map, scene JSON...
  await tree.load(sceneJson)
  tree.running = true
}
host.sceneTree = tree
host.assetManifest = manifestJson
host.init(containerElement, projectJson)
```
