# Tilemaps and tilesets

Use TileMap for editable semantic grids. For a generated raster background, use an image plus independent colliders as described in [the main guide](index.md). Tileset production belongs to the [map contract](../contracts/map.md#pattern-3-tilemap).

## Register the tileset

Register the PNG and tile definitions together in assets/manifest.json. There is no separate .tileset.json file. The manifest key is the tileset name and its Phaser texture key. Paths are relative to the manifest directory.

~~~json
{
  "dungeon": {
    "type": "tileset",
    "path": "tilesets/dungeon.png",
    "tileSize": 16,
    "tiles": {
      "floor": {"index": 0},
      "wall": {"index": 1, "collision": true, "autotile": "walls"},
      "spike": {
        "index": 17,
        "collision": true,
        "collisionShapes": [{"type": "rect", "x": 2, "y": 8, "width": 12, "height": 8}],
        "properties": {"damage": 1}
      }
    },
    "autotile": {
      "walls": {
        "offsets": {
          "0000": 0, "1000": 1, "0100": 2, "1100": 3,
          "0010": 4, "1010": 5, "0110": 6, "1110": 7,
          "0001": 8, "1001": 9, "0101": 10, "1101": 11,
          "0011": 12, "1011": 13, "0111": 14, "1111": 15
        }
      }
    },
    "stamps": {
      "pillar": {"width": 1, "height": 2, "data": [["wall"], ["wall"]]}
    }
  }
}
~~~

Field -> Meaning:
- type, tileSize, tiles: Required; type is tileset; tileSize is the square cell size
- path: Required for real art; omit for color placeholders
- tiles[name].index: Zero-based cell index in the PNG
- tiles[name].collision: Solid tile, default false
- tiles[name].collisionShapes: Rectangles in tile-local px; requires collision: true
- tiles[name].autotile: Key in the entry's autotile object
- tiles[name].properties: Gameplay metadata; the engine does not apply damage or movement effects
- tiles[name].color: Placeholder CSS color when no PNG is loaded
- autotile[rule].offsets: Bitmask string to offset added to the tile's base index
- stamps[name]: Composite with width, height in cells and a rectangular data array
- categories: Optional authoring metadata; not read by the engine

The PNG grid and collision shapes must match tileSize. Changing it changes how the image is sliced, not just how large the old cells appear on screen. A solid tile without collisionShapes gets a full-cell static body. Multiple rectangles produce multiple static bodies. Other shape types are not supported here.

For prototypes, omit path and give every tile a color. The engine generates a color texture; semantic names and collision rules remain unchanged when art arrives.

Autotile masks test equal semantic tile names in top/right/bottom/left order. For example, 1010 means matching tiles above and below. Supply all 16 offsets for a four-neighbor rule. Stamps contain tile names or null, not PNG indices.

## Define the map

An external maps/room.tilemap.json contains a rectangular grid per layer:

~~~json
{
  "tileset": "dungeon",
  "width": 5,
  "height": 4,
  "layers": [
    {
      "name": "ground", "z": 0,
      "data": [
        ["floor", "floor", "floor", "floor", "floor"],
        ["floor", "floor", "floor", "floor", "floor"],
        ["floor", "floor", "floor", "floor", "floor"],
        ["floor", "floor", "floor", "floor", "floor"]
      ]
    },
    {
      "name": "walls", "z": 1,
      "data": [
        ["wall", "wall", "wall", "wall", "wall"],
        ["wall", null, null, null, "wall"],
        ["wall", null, null, null, "wall"],
        ["wall", "wall", "wall", "wall", "wall"]
      ]
    }
  ]
}
~~~

Reference it from a scene node:

~~~json
{"id": "map", "name": "Map", "script": "TileMap", "config": {"src": "maps/room.tilemap.json"}}
~~~

Each layer has name, data, optional z (default 0), optional collision (default true), and optional stamps: [{"stamp": "pillar", "x": 2, "y": 1}]. Coordinates are zero-based cells. Null means empty. Stamp placements merge into data before autotiling; out-of-bounds cells are clipped.

Set layer collision: false to omit its physical bodies. Note that isPassable still checks semantic solids on ALL layers, including decorative layers. If navigation should ignore a roof layer, query the gameplay layers yourself.

Two other setups use the same TileMap script:

- Small inline map: config contains tileset and layers; dimensions derive from the first layer's data.
- Procedural map: config contains only tileset; call init after ready. A parent node's ready runs after its children, so it can initialize a child map.

~~~js
ready() {
  const map = this.getNode('Map')
  map.init(20, 15, { defaultLayer: 'walls' })
  map.fill('walls', 'wall')
  map.fillRect('walls', 1, 1, 18, 13, null)
  this.scene.physics.add.collider(
    this.getNode('Hero').physicsObject,
    map.getCollisionLayer('walls')
  )
}
~~~

Add maps/ to project.json.releaseExtraRoots when using external map files. It is not one of the default [release roots](deployment.md#release-payload).

## TileMap API

All x/y parameters below are cell coordinates, not world px. For a map at the origin, convert world coordinates with floor(world / tileSize). Connect physics explicitly using the returned static groups.

Method -> Result or effect:
- init(width, height, options?): Reset a map; options.layers selects layer definitions, otherwise options.defaultLayer names one blank layer
- getTile(layer, x, y): Semantic tile name or null
- getTileProperties(layer, x, y): The tile definition's properties or null
- isPassable(x, y): False outside the map or if any layer contains a solid tile
- getCollisionLayer(layerName?): StaticGroup; omitted name selects the first collision group
- setTile(layer, x, y, type): Set a cell to a tile name or null, update neighbors and collisions
- fill(layer, type): Fill a whole layer
- fillRect(layer, x1, y1, x2, y2, type): Fill inclusive endpoints, reordered and clipped to map bounds
- placeStamp(layer, x, y, name): Write the named stamp's cells, including nulls
- removeStamp(layer, x, y, name): Clear its footprint to null; does not restore previous terrain
- toJSON(): Current tileset, width, height and layers with resolved semantic data

Each collision body's gameObject carries Phaser data fields tileType, tileX and tileY. Use them in a collision callback to apply tile-specific behavior. Map edits update the affected cells' physical bodies.

toJSON does not preserve stamp instances or layer collision flags. Save these separately if your editor needs to round-trip authoring metadata.

## AutoTile utility

For direct grid processing from a game script:

~~~js
import { AutoTile } from '../engine/utils/AutoTile.js'

const indices = AutoTile.resolve(grid, tilesetDef)
const changed = AutoTile.resolveLocal(grid, tilesetDef, x, y)
~~~

resolve returns number[][] with -1 for empty cells. resolveLocal returns [{x, y, index}, ...] for the cell and its four in-bounds neighbors.
