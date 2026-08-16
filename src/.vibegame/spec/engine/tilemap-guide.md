# Tilemap System Reference

Complete reference for the tilemap pipeline: tileset registration in manifest, tilemap data, and the TileMap Node script API.

---

## manifest.json: tileset type

Tilesets are registered inline in `manifest.json`. No separate `.tileset.json` file is needed -- all tile definitions, collision shapes, and auto-tile rules live directly in the manifest entry.

```json
{
  "forest": {
    "type": "tileset",
    "path": "tilesets/forest.png",
    "tileSize": 16,
    "tiles": {
      "grass": { "index": 0, "collision": false },
      "wall":  { "index": 16, "collision": true, "autotile": "bitmask-4" },
      "spike": { "index": 48, "collision": true, "collisionShapes": [{ "type": "rect", "x": 2, "y": 8, "width": 12, "height": 8 }], "properties": { "damage": 1 } }
    },
    "autotile": {
      "bitmask-4": {
        "offsets": { "0000": 0, "1000": 1, "0100": 2, "1100": 3, "0010": 4, "1010": 5, "0110": 6, "1110": 7, "0001": 8, "1001": 9, "0101": 10, "1101": 11, "0011": 12, "1011": 13, "0111": 14, "1111": 15 }
      }
    },
    "stamps": {
      "tree": { "width": 2, "height": 2, "data": [["tree_top_l","tree_top_r"],["tree_bot_l","tree_bot_r"]] }
    }
  }
}
```

### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `type` | `"tileset"` | yes | Asset type |
| `path` | string | yes | Path to tileset PNG, relative to manifest's folder |
| `tileSize` | number | yes | Display tile size in pixels (square tiles) |
| `tiles` | object | yes | `{ semanticName: TileDef }` map |
| `autotile` | object | no | Auto-tile rule definitions |
| `stamps` | object | no | `{ stampName: StampDef }` composite tile structures |
| `categories` | object | no | `{ categoryName: [tileName, ...] }` for grouping. Authoring metadata for agents and tools; the engine does not read it |

The manifest key (e.g. `"forest"`) serves as both the tileset identifier and the Phaser texture key.

### How it works

1. Boot: engine extracts tileset entries from manifest into `sceneTree.tilesets[key]`
2. Preload: PhaserHost loads the `path` as a Phaser texture keyed by the manifest entry name
3. Runtime: TileMap script reads `sceneTree.tilesets[tilesetName]` for tile definitions

---

## TileDef (each entry in `tiles`)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `index` | number | yes | Base tile index in the tileset image (grid position) |
| `collision` | boolean | no | Whether this tile type has collision (default false) |
| `collisionShapes` | CollisionShape[] | no | Custom collision regions within the tile |
| `autotile` | string | no | Auto-tile rule name (e.g. "bitmask-4") |
| `properties` | object | no | Arbitrary properties (damage, slowFactor, etc.) |

### CollisionShape

| Field | Type | Description |
|-------|------|-------------|
| `type` | `"rect"` | Shape type (only rect supported currently) |
| `x` | number | X offset from tile's top-left corner (px) |
| `y` | number | Y offset from tile's top-left corner (px) |
| `width` | number | Shape width (px) |
| `height` | number | Shape height (px) |

Collision shape rules:
- `collisionShapes` defined: engine creates independent static bodies per shape
- `collision: true` without `collisionShapes`: full-tile collision body
- `collision: false` or omitted: no collision
- Multiple shapes per tile are supported (creates one body per shape)

### Auto-tile rules (bitmask-4)

4-bit bitmask checking top/right/bottom/left neighbors for same type.
The resolved index = `tiles[type].index + autotile.offsets[bitmask]`.

```json
{
  "autotile": {
    "bitmask-4": {
      "offsets": {
        "0000": 0, "1000": 1, "0100": 2, "1100": 3,
        "0010": 4, "1010": 5, "0110": 6, "1110": 7,
        "0001": 8, "1001": 9, "0101": 10, "1101": 11,
        "0011": 12, "1011": 13, "0111": 14, "1111": 15
      }
    }
  }
}
```

### StampDef

A composite tile structure -- multiple tiles that are always placed together as a unit.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `width` | number | yes | Stamp width in tiles |
| `height` | number | yes | Stamp height in tiles |
| `data` | (string\|null)[][] | yes | 2D array of tile type names |

---

## Tilemap Data (*.tilemap.json)

Map data using semantic tile type names. Can be external file or inlined in scene JSON config.

### Top-level structure

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `tileset` | string | yes | Tileset name (matches manifest entry key) |
| `width` | number | yes | Map width in tiles |
| `height` | number | yes | Map height in tiles |
| `layers` | LayerDef[] | yes | Array of layer definitions |

### LayerDef

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | yes | Layer identifier |
| `z` | number | no | Depth/z-index for rendering order (default 0) |
| `data` | (string\|null)[][] | yes | 2D array of tile type names. `null` = empty cell. |
| `collision` | boolean | no | Build collision bodies for this layer's solid tiles (default `true`). Set `false` for decorative layers such as a wall roof. |
| `stamps` | StampPlacement[] | no | Pre-placed stamp instances. The engine writes them into this layer's `data` before auto-tiling, so stamped edges auto-tile against their neighbours. |

### StampPlacement

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `stamp` | string | yes | Stamp name from the tileset's `stamps` |
| `x` | integer | yes | Top-left tile X |
| `y` | integer | yes | Top-left tile Y |

Cells that fall outside the map are dropped rather than growing it. For stamps placed at runtime, call `placeStamp(layer, x, y, name)` instead.

### StampPlacement

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `stamp` | string | yes | Stamp name (from tileset `stamps`) |
| `x` | number | yes | Top-left tile X coordinate |
| `y` | number | yes | Top-left tile Y coordinate |

### Example

```json
{
  "tileset": "forest",
  "width": 10,
  "height": 8,
  "layers": [
    {
      "name": "ground",
      "z": 0,
      "data": [
        ["grass", "grass", "grass", null, null, null, null, "grass", "grass", "grass"],
        ["grass", "grass", "grass", "grass", "grass", "grass", "grass", "grass", "grass", "grass"]
      ]
    },
    {
      "name": "walls",
      "z": 1,
      "data": [
        ["wall", "wall", null, null, null, null, null, null, "wall", "wall"],
        ["wall", null, null, null, null, null, null, null, null, "wall"]
      ]
    }
  ]
}
```

### TileMap Node in scene JSON

```json
{
  "name": "Map",
  "script": "TileMap",
  "tags": ["tilemap"],
  "config": { "src": "maps/level1.tilemap.json" }
}
```

Inline variant (small maps):
```json
{
  "name": "Map",
  "script": "TileMap",
  "config": {
    "tileset": "forest",
    "layers": [
      { "name": "ground", "z": 0, "data": [["grass","grass"],["grass","grass"]] }
    ]
  }
}
```

Empty map (procedural generation):
```json
{
  "name": "Map",
  "script": "TileMap",
  "config": { "tileset": "forest" }
}
```
Only loads the tileset. Call `init(width, height)` from your script to create the map at runtime, then build with `fill`/`setTile`/`placeStamp`:
```javascript
ready() {
  const map = this.getNode('../Map')
  map.init(20, 15)              // creates blank 20x15 "default" layer
  map.fill('default', 'wall')   // fill all with wall
  map.fillRect('default', 1, 1, 18, 13, 'floor')  // carve out rooms
}
```

---

## TileMap Node API

`script: "TileMap"` in scene JSON (loaded as engine script)

A Node script that manages semantic tilemaps. Agent writes tile type names ("grass", "wall"),
the engine resolves them to visual tile indices via auto-tile and builds collision bodies
from tileset-defined collision shapes.

### Data requirements

- Tileset must be registered in manifest.json with `type: "tileset"`
- Tileset image is auto-loaded by the engine from the manifest `path` field
- Three config modes:
  1. **External file**: `config.src` points to a `.tilemap.json` file
  2. **Inline layers**: `config.tileset` + `config.layers` with data arrays
  3. **Tileset only**: `config.tileset` alone -- tileset loaded, map deferred. Call `init(width, height)` from script.

### Read methods

```javascript
isPassable(x, y)
    // Check if a grid cell is passable (no collision tile on any layer).
    // Returns false for out-of-bounds cells.
    // Checks ALL layers -- if any tile at (x,y) has collision: true, returns false.

getTile(layer, x, y)
    // Returns tile type name (e.g. "grass") or null.

getTileProperties(layer, x, y)
    // Returns the properties object from the tileset definition, or null.
    // Example: { damage: 1, slowFactor: 0.5 }

getCollisionLayer(layerName?)
    // Returns Phaser.Physics.Arcade.StaticGroup containing collision bodies.
    // If layerName is omitted, returns the first collision group found.
    // Each body's gameObject has data: tileType, tileX, tileY.
```

### Write methods

```javascript
init(width, height, options?)
    // Initialize the map with given dimensions (for procedural generation).
    // Call after ready() when config only specifies tileset.
    // options.defaultLayer: name for the initial blank layer (default "default").
    // Can be called again to re-initialize (destroys existing layers/collision).

setTile(layer, x, y, tileType)
    // Update a single tile. Auto-resolves the cell + 4 neighbors.
    // Rebuilds collision bodies for affected cells.

fill(layer, tileType)
    // Fill an entire layer with a tile type.

fillRect(layer, x1, y1, x2, y2, tileType)
    // Fill a rectangular region.
```

### Stamp methods

```javascript
placeStamp(layer, x, y, stampName)
    // Place a composite tile structure at position (x, y).
    // Expands the stamp definition from the tileset into individual setTile calls.
    // Auto-resolves affected cells and rebuilds collision bodies.

removeStamp(layer, x, y, stampName)
    // Remove a previously placed stamp (sets all covered cells to null).
```

### Serialization

```javascript
toJSON()
    // Returns tilemap.json format: { tileset, width, height, layers: [...] }
```

### Usage from other scripts

```javascript
ready() {
  const map = this.getNode('../Map')

  // Physics collision
  const wallBodies = map.getCollisionLayer('walls')
  this.scene.physics.add.collider(this.sprite, wallBodies)

  // Query terrain
  const tile = map.getTile('ground', tileX, tileY)
  const props = map.getTileProperties('ground', tileX, tileY)
  if (props?.slowFactor) this.speed *= props.slowFactor

  // Modify terrain at runtime
  map.setTile('walls', 5, 3, null)  // remove a wall

  // Stamps
  map.placeStamp('objects', 5, 3, 'tree')   // place a tree at tile (5,3)
  map.removeStamp('objects', 5, 3, 'tree')  // remove it
}
```

---

## AutoTile Utility

`import { AutoTile } from '/engine/utils/AutoTile.js'`

```javascript
AutoTile.resolve(semanticGrid, tilesetDef)
// semanticGrid: (string|null)[][] - 2D array of tile type names
// tilesetDef: manifest tileset entry content
// Returns number[][] - resolved tile indices (-1 for null cells)

AutoTile.resolveLocal(grid, tilesetDef, x, y)
// Resolve a single cell + its 4 neighbors (incremental update).
// Returns [{ x, y, index }, ...]
```
