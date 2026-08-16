/**
 * TileMap Node script. Loads tileset + tilemap data, creates Phaser tilemap,
 * applies auto-tile, and builds collision bodies from collisionShapes.
 */

import { Node } from '../Node.js'
import { AutoTile } from '../utils/AutoTile.js'

export default class TileMap extends Node {
  // Phaser objects
  _phaserMap = null
  _phaserTileset = null
  _phaserLayers = {}       // layerName -> Phaser TilemapLayer
  _collisionGroups = {}    // layerName -> StaticGroup
  _collisionBodies = {}    // "layerName:x:y" -> [GameObjects]

  // Parsed data
  _tilesetDef = null
  _semanticLayers = {}     // layerName -> string[][] (semantic grid)
  _mapWidth = 0
  _mapHeight = 0
  _tileSize = 0
  _initialized = false

  ready() {
    const c = this.config

    // Resolve tileset (required for all modes)
    const tilesetName = c.tileset || c.tilesetDef?.name
    if (tilesetName) {
      this._tilesetDef = this.sceneTree.tilesets?.[tilesetName]
    }
    // Inline tilesetDef fallback
    if (!this._tilesetDef && c.tilesetDef) {
      this._tilesetDef = c.tilesetDef
      this.sceneTree.tilesets[this._tilesetDef.name] = this._tilesetDef
    }

    // External file or inline layers: initialize immediately
    const tilemapData = this._loadTilemapData(c)
    if (tilemapData) {
      // A .tilemap.json names its own tileset, so `config.src` alone is enough;
      // config.tileset stays available to point one map file at another tileset.
      if (!this._tilesetDef && tilemapData.tileset) {
        this._tilesetDef = this.sceneTree.tilesets?.[tilemapData.tileset]
      }
      if (!this._tilesetDef) {
        console.warn(`TileMap: tileset "${c.tileset || tilemapData.tileset}" not found in sceneTree.tilesets`)
        return
      }
      this._initFromData(tilemapData)
    } else if (!this._tilesetDef) {
      console.warn('TileMap: provide src, inline layers, or tileset for deferred init')
    }
    // else: tileset-only mode -- script calls init() later

    this.gameObject = this.scene.add.container(0, 0)
  }

  /**
   * Initialize or re-initialize the map with given dimensions.
   * For procedural generation: call after ready() with runtime-determined size.
   * @param {number} width - Map width in tiles
   * @param {number} height - Map height in tiles
   * @param {object} [options] - Optional settings
   * @param {string} [options.defaultLayer='default'] - Name for the initial blank layer
   */
  init(width, height, options) {
    if (!this._tilesetDef) {
      console.warn('TileMap.init(): no tileset loaded')
      return
    }

    // Destroy existing Phaser objects if re-initializing
    if (this._initialized) {
      for (const group of Object.values(this._collisionGroups)) group.destroy(true)
      this._collisionGroups = {}
      this._collisionBodies = {}
      for (const layer of Object.values(this._phaserLayers)) { if (layer) layer.destroy() }
      this._phaserLayers = {}
      this._semanticLayers = {}
      if (this._phaserMap) { this._phaserMap.destroy(); this._phaserMap = null }
    }

    const layers = Array.isArray(options?.layers) && options.layers.length > 0
      ? options.layers
      : [{ name: options?.defaultLayer || 'default', z: 0, collision: true }]

    this._tileSize = this.config.tileSize || this._tilesetDef.tileSize || 16
    this._mapWidth = width
    this._mapHeight = height
    this._ensureColorTexture()
    this._createPhaserMap()
    for (const layerDef of layers) {
      this._processLayer({
        ...layerDef,
        data: Array.from({ length: height }, () => Array(width).fill(null)),
      })
    }
    this._initialized = true
  }

  /** @private Initialize from loaded tilemap data (src or inline layers). */
  _initFromData(tilemapData) {
    this._tileSize = tilemapData.tileSize || this._tilesetDef.tileSize || 16
    this._mapWidth = tilemapData.width || tilemapData.layers?.[0]?.data?.[0]?.length || 0
    this._mapHeight = tilemapData.height || tilemapData.layers?.[0]?.data?.length || 0
    this._ensureColorTexture()
    this._createPhaserMap()
    for (const layerDef of tilemapData.layers || []) {
      this._processLayer(layerDef)
    }
    this._initialized = true
  }

  destroy() {
    // Destroy collision bodies
    for (const group of Object.values(this._collisionGroups)) {
      group.destroy(true)
    }
    this._collisionGroups = {}
    this._collisionBodies = {}

    // Destroy Phaser tilemap layers
    for (const layer of Object.values(this._phaserLayers)) {
      if (layer) layer.destroy()
    }
    this._phaserLayers = {}

    // Destroy the map itself
    if (this._phaserMap) {
      this._phaserMap.destroy()
      this._phaserMap = null
    }

    if (this.gameObject) {
      this.gameObject.destroy()
      this.gameObject = null
    }
  }

  // === Public API ===

  /**
   * Check if a grid cell is passable (no collision tile on any layer).
   * @returns {boolean}
   */
  isPassable(x, y) {
    if (x < 0 || y < 0 || x >= this._mapWidth || y >= this._mapHeight) return false
    for (const [, grid] of Object.entries(this._semanticLayers)) {
      const typeName = grid[y]?.[x]
      if (!typeName) continue
      const tileDef = this._tilesetDef.tiles?.[typeName]
      if (tileDef?.collision) return false
    }
    return true
  }

  /**
   * Get tile type name at position.
   * @returns {string|null}
   */
  getTile(layer, x, y) {
    const grid = this._semanticLayers[layer]
    if (!grid || y < 0 || y >= grid.length || x < 0 || x >= grid[0].length) return null
    return grid[y][x]
  }

  /**
   * Get tile properties from tileset definition.
   * @returns {object|null}
   */
  getTileProperties(layer, x, y) {
    const typeName = this.getTile(layer, x, y)
    if (!typeName) return null
    return this._tilesetDef.tiles?.[typeName]?.properties || null
  }

  /**
   * Get the collision StaticGroup for a layer.
   * If layerName omitted, returns the first collision group found.
   * @returns {Phaser.Physics.Arcade.StaticGroup|null}
   */
  getCollisionLayer(layerName) {
    if (layerName) return this._collisionGroups[layerName] || null
    // Return first available
    const keys = Object.keys(this._collisionGroups)
    return keys.length > 0 ? this._collisionGroups[keys[0]] : null
  }

  /**
   * Set a single tile and update auto-tile neighbors + collision.
   */
  setTile(layer, x, y, tileType) {
    const grid = this._semanticLayers[layer]
    if (!grid || y < 0 || y >= grid.length || x < 0 || x >= grid[0].length) return

    grid[y][x] = tileType

    // Resolve auto-tile for this cell + neighbors
    const updates = AutoTile.resolveLocal(grid, this._tilesetDef, x, y)
    const phaserLayer = this._phaserLayers[layer]

    for (const upd of updates) {
      if (phaserLayer) {
        if (upd.index >= 0) {
          phaserLayer.putTileAt(upd.index, upd.x, upd.y)
        } else {
          phaserLayer.removeTileAt(upd.x, upd.y)
        }
      }
      // Rebuild collision for each updated cell
      this._rebuildCellCollision(layer, upd.x, upd.y)
    }
  }

  /**
   * Fill entire layer with a tile type.
   */
  fill(layer, tileType) {
    const grid = this._semanticLayers[layer]
    if (!grid) return

    for (let y = 0; y < grid.length; y++) {
      for (let x = 0; x < grid[0].length; x++) {
        grid[y][x] = tileType
      }
    }
    this._rebuildRegion(layer, 0, 0, grid[0].length - 1, grid.length - 1)
  }

  /**
   * Fill a rectangular region with a tile type.
   */
  fillRect(layer, x1, y1, x2, y2, tileType) {
    const grid = this._semanticLayers[layer]
    if (!grid) return

    const minX = Math.max(0, Math.min(x1, x2))
    const maxX = Math.min(grid[0].length - 1, Math.max(x1, x2))
    const minY = Math.max(0, Math.min(y1, y2))
    const maxY = Math.min(grid.length - 1, Math.max(y1, y2))

    for (let y = minY; y <= maxY; y++) {
      for (let x = minX; x <= maxX; x++) {
        grid[y][x] = tileType
      }
    }
    this._rebuildRegion(layer, minX, minY, maxX, maxY)
  }

  /**
   * Serialize back to tilemap.json format.
   */
  toJSON() {
    const layers = []
    for (const [name, grid] of Object.entries(this._semanticLayers)) {
      const phaserLayer = this._phaserLayers[name]
      layers.push({
        name,
        z: phaserLayer?.depth ?? 0,
        data: grid.map(row => [...row]),
      })
    }

    return {
      tileset: this._tilesetDef?.name || '',
      width: this._mapWidth,
      height: this._mapHeight,
      layers,
    }
  }

  /**
   * Place a composite stamp at tile position (x, y).
   * Expands stamp definition into individual setTile calls.
   * @param {string} layer - layer name
   * @param {number} x - top-left tile X
   * @param {number} y - top-left tile Y
   * @param {string} stampName - stamp name from tileset.stamps
   */
  placeStamp(layer, x, y, stampName) {
    const stampDef = this._tilesetDef?.stamps?.[stampName]
    if (!stampDef) {
      console.warn(`TileMap: stamp "${stampName}" not found in tileset`)
      return
    }

    for (let sy = 0; sy < stampDef.height; sy++) {
      for (let sx = 0; sx < stampDef.width; sx++) {
        const tileType = stampDef.data[sy]?.[sx]
        if (tileType !== undefined) {
          this.setTile(layer, x + sx, y + sy, tileType)
        }
      }
    }
  }

  /**
   * Write a layer's pre-placed stamps into its semantic grid.
   *
   * Load-time counterpart of placeStamp: the Phaser layer does not exist yet, so
   * this edits the raw grid instead of going through setTile. Cells outside the
   * grid are dropped rather than growing it — the map size is authored.
   * @private
   * @param {(string|null)[][]} grid - semantic grid, mutated in place
   * @param {{stamp: string, x: number, y: number}[]} [stamps]
   */
  _expandStamps(grid, stamps) {
    for (const placement of stamps || []) {
      const stampDef = this._tilesetDef?.stamps?.[placement.stamp]
      if (!stampDef) {
        console.warn(`TileMap: stamp "${placement.stamp}" not found in tileset`)
        continue
      }
      for (let sy = 0; sy < stampDef.height; sy++) {
        const row = grid[placement.y + sy]
        if (!row) continue
        for (let sx = 0; sx < stampDef.width; sx++) {
          const tileType = stampDef.data[sy]?.[sx]
          if (tileType === undefined) continue
          const x = placement.x + sx
          if (x < 0 || x >= row.length) continue
          row[x] = tileType
        }
      }
    }
  }

  /**
   * Remove a previously placed stamp (set all covered cells to null).
   * @param {string} layer - layer name
   * @param {number} x - top-left tile X
   * @param {number} y - top-left tile Y
   * @param {string} stampName - stamp name from tileset.stamps
   */
  removeStamp(layer, x, y, stampName) {
    const stampDef = this._tilesetDef?.stamps?.[stampName]
    if (!stampDef) {
      console.warn(`TileMap: stamp "${stampName}" not found in tileset`)
      return
    }

    for (let sy = 0; sy < stampDef.height; sy++) {
      for (let sx = 0; sx < stampDef.width; sx++) {
        this.setTile(layer, x + sx, y + sy, null)
      }
    }
  }

  // === Internal methods ===

  /**
   * Generate a canvas-based texture from tile color definitions.
   * Skips if the texture already exists or no tiles define colors.
   * @private
   */
  _ensureColorTexture() {
    const texName = this._tilesetDef.name
    if (this.scene.textures.exists(texName)) return

    // Build index -> color mapping
    const indexColors = new Map()
    for (const [, tileDef] of Object.entries(this._tilesetDef.tiles || {})) {
      if (!tileDef.color) continue
      const indices = [tileDef.index]
      // Include all autotile variant indices
      if (tileDef.autotile) {
        const autoDef = this._tilesetDef.autotile?.[tileDef.autotile]
        if (autoDef?.offsets) {
          for (const offset of Object.values(autoDef.offsets)) {
            indices.push(tileDef.index + offset)
          }
        }
      }
      for (const idx of indices) indexColors.set(idx, tileDef.color)
    }
    if (indexColors.size === 0) return

    const maxIndex = Math.max(...indexColors.keys())
    const ts = this._tileSize
    const cols = Math.ceil(Math.sqrt(maxIndex + 1))
    const rows = Math.ceil((maxIndex + 1) / cols)

    const canvas = document.createElement('canvas')
    canvas.width = cols * ts
    canvas.height = rows * ts
    const ctx = canvas.getContext('2d')

    for (const [idx, color] of indexColors) {
      ctx.fillStyle = color
      const col = idx % cols
      const row = Math.floor(idx / cols)
      ctx.fillRect(col * ts, row * ts, ts, ts)
    }

    this.scene.textures.addCanvas(texName, canvas)
  }

  /**
   * Load tilemap data from external file or inline config.
   * Returns null for tileset-only mode (deferred init via init()).
   * @private
   */
  _loadTilemapData(config) {
    if (config.src) {
      const data = this.sceneTree.tilemaps?.[config.src]
      if (!data) {
        console.warn(`TileMap: tilemap data "${config.src}" not found in sceneTree.tilemaps`)
      }
      return data || null
    }

    if (config.layers) {
      return {
        tileset: config.tileset || config.tilesetDef?.name,
        width: config.layers[0]?.data?.[0]?.length || 0,
        height: config.layers[0]?.data?.length || 0,
        tileSize: config.tileSize,
        layers: config.layers,
      }
    }

    return null
  }

  /**
   * Create the underlying Phaser tilemap.
   * @private
   */
  _createPhaserMap() {
    const tilesetName = this._tilesetDef.name
    const ts = this._tileSize

    const mapData = new Phaser.Tilemaps.MapData({
      width: this._mapWidth,
      height: this._mapHeight,
      tileWidth: ts,
      tileHeight: ts,
    })
    this._phaserMap = new Phaser.Tilemaps.Tilemap(this.scene, mapData)

    this._phaserTileset = this._phaserMap.addTilesetImage(
      tilesetName, tilesetName, ts, ts
    )
  }

  /**
   * Process a single layer: store semantic data, resolve auto-tile, create visuals + collision.
   * @private
   */
  _processLayer(layerDef) {
    const name = layerDef.name

    // Store semantic grid (deep copy)
    const semanticGrid = layerDef.data.map(row => [...row])
    // Stamps are expanded before auto-tiling so the resolver sees the finished
    // layout, exactly as if the stamped cells had been written into `data`.
    this._expandStamps(semanticGrid, layerDef.stamps)
    this._semanticLayers[name] = semanticGrid

    // Resolve semantic -> numeric via auto-tile
    const numericGrid = AutoTile.resolve(semanticGrid, this._tilesetDef)

    // Create Phaser tilemap layer
    const phaserLayer = this._phaserMap.createBlankLayer(name, this._phaserTileset)
    if (phaserLayer && layerDef.z !== undefined) {
      phaserLayer.setDepth(layerDef.z)
    }
    this._phaserLayers[name] = phaserLayer

    // (no scale needed: tileset tileSize is used directly as Phaser tile size)


    // Fill the Phaser layer with resolved indices
    for (let y = 0; y < numericGrid.length; y++) {
      for (let x = 0; x < numericGrid[y].length; x++) {
        const idx = numericGrid[y][x]
        if (idx >= 0 && phaserLayer) {
          phaserLayer.putTileAt(idx, x, y)
        }
      }
    }

    // Build collision bodies for this layer (skip if layer opts out)
    if (layerDef.collision !== false) {
      this._buildLayerCollision(name, semanticGrid)
    }
  }

  /**
   * Build collision bodies for an entire layer from semantic data.
   * @private
   */
  _buildLayerCollision(layerName, semanticGrid) {
    const group = this.scene.physics.add.staticGroup()
    this._collisionGroups[layerName] = group

    for (let y = 0; y < semanticGrid.length; y++) {
      for (let x = 0; x < semanticGrid[y].length; x++) {
        this._createCellCollision(layerName, x, y, group)
      }
    }
  }

  /**
   * Create collision bodies for a single cell.
   * @private
   */
  _createCellCollision(layerName, x, y, group) {
    const typeName = this._semanticLayers[layerName]?.[y]?.[x]
    if (!typeName) return

    const tileDef = this._tilesetDef.tiles?.[typeName]
    if (!tileDef || !tileDef.collision) return

    const worldX = x * this._tileSize
    const worldY = y * this._tileSize
    const key = `${layerName}:${x}:${y}`
    const bodies = []

    if (tileDef.collisionShapes && tileDef.collisionShapes.length > 0) {
      // Custom collision shapes
      for (const shape of tileDef.collisionShapes) {
        if (shape.type === 'rect') {
          const body = this._createRectBody(
            group, worldX, worldY, shape, typeName, x, y
          )
          bodies.push(body)
        }
      }
    } else {
      // Full-tile collision body
      const body = this._createRectBody(
        group, worldX, worldY,
        { x: 0, y: 0, width: this._tileSize, height: this._tileSize },
        typeName, x, y
      )
      bodies.push(body)
    }

    if (bodies.length > 0) {
      this._collisionBodies[key] = bodies
    }
  }

  /**
   * Create a single rectangular static body at the given position.
   * @private
   */
  _createRectBody(group, worldX, worldY, shape, typeName, tileX, tileY) {
    // Position: center of the collision rectangle
    const cx = worldX + shape.x + shape.width / 2
    const cy = worldY + shape.y + shape.height / 2

    const rect = this.scene.add.rectangle(cx, cy, shape.width, shape.height)
    rect.setVisible(false)
    this.scene.physics.add.existing(rect, true) // true = static

    // Store metadata
    rect.setData('tileType', typeName)
    rect.setData('tileX', tileX)
    rect.setData('tileY', tileY)

    group.add(rect)
    return rect
  }

  /**
   * Destroy and recreate collision for a single cell.
   * @private
   */
  _rebuildCellCollision(layerName, x, y) {
    const key = `${layerName}:${x}:${y}`
    const existing = this._collisionBodies[key]
    if (existing) {
      for (const body of existing) {
        body.destroy()
      }
      delete this._collisionBodies[key]
    }

    const group = this._collisionGroups[layerName]
    if (group) {
      this._createCellCollision(layerName, x, y, group)
    }
  }

  /**
   * Incremental rebuild for a changed region: auto-tile visuals + collision.
   * Covers the region + 1-cell border for auto-tile neighbor resolution.
   * @private
   */
  _rebuildRegion(layerName, minX, minY, maxX, maxY) {
    const grid = this._semanticLayers[layerName]
    if (!grid) return
    const phaserLayer = this._phaserLayers[layerName]
    const w = grid[0].length
    const h = grid.length

    // Auto-tile: resolve expanded region (border cells may change visuals)
    const exMinX = Math.max(0, minX - 1)
    const exMinY = Math.max(0, minY - 1)
    const exMaxX = Math.min(w - 1, maxX + 1)
    const exMaxY = Math.min(h - 1, maxY + 1)

    const seen = new Set()
    for (let y = exMinY; y <= exMaxY; y++) {
      for (let x = exMinX; x <= exMaxX; x++) {
        const updates = AutoTile.resolveLocal(grid, this._tilesetDef, x, y)
        for (const upd of updates) {
          const key = `${upd.x},${upd.y}`
          if (seen.has(key)) continue
          seen.add(key)
          if (phaserLayer) {
            if (upd.index >= 0) phaserLayer.putTileAt(upd.index, upd.x, upd.y)
            else phaserLayer.removeTileAt(upd.x, upd.y)
          }
        }
      }
    }

    // Collision: rebuild only changed cells
    for (let y = minY; y <= maxY; y++) {
      for (let x = minX; x <= maxX; x++) {
        this._rebuildCellCollision(layerName, x, y)
      }
    }
  }

  /**
   * Rebuild all visuals for a layer from semantic data.
   * @private
   */
  _rebuildLayerVisuals(layerName) {
    const grid = this._semanticLayers[layerName]
    if (!grid) return

    const numericGrid = AutoTile.resolve(grid, this._tilesetDef)
    const phaserLayer = this._phaserLayers[layerName]
    if (!phaserLayer) return

    for (let y = 0; y < numericGrid.length; y++) {
      for (let x = 0; x < numericGrid[y].length; x++) {
        const idx = numericGrid[y][x]
        if (idx >= 0) {
          phaserLayer.putTileAt(idx, x, y)
        } else {
          phaserLayer.removeTileAt(x, y)
        }
      }
    }
  }

  /**
   * Rebuild all collision bodies for a layer.
   * @private
   */
  _rebuildLayerCollision(layerName) {
    // Clear body references for this layer
    for (const key of Object.keys(this._collisionBodies)) {
      if (key.startsWith(`${layerName}:`)) {
        delete this._collisionBodies[key]
      }
    }

    // Destroy the group (also destroys all children)
    const oldGroup = this._collisionGroups[layerName]
    if (oldGroup) {
      oldGroup.destroy(true)
      delete this._collisionGroups[layerName]
    }

    const grid = this._semanticLayers[layerName]
    if (grid) {
      this._buildLayerCollision(layerName, grid)
    }
  }
}
