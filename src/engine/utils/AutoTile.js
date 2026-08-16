/**
 * Auto-tile bitmask resolver.
 * Given a semantic grid and tileset definition, resolves each cell to a tile index.
 * Supports bitmask-4 (top/right/bottom/left).
 */

export const AutoTile = {
  /**
   * Resolve an entire semantic grid to numeric tile indices.
   * @param {(string|null)[][]} semanticGrid - 2D array of tile type names
   * @param {object} tilesetDef - tileset.json content
   * @returns {number[][]} - 2D array of resolved tile indices (-1 for null)
   */
  resolve(semanticGrid, tilesetDef) {
    const height = semanticGrid.length
    if (height === 0) return []

    const width = semanticGrid[0].length
    const result = []

    for (let y = 0; y < height; y++) {
      const row = []
      for (let x = 0; x < width; x++) {
        row.push(this._resolveCell(semanticGrid, tilesetDef, x, y, width, height))
      }
      result.push(row)
    }

    return result
  },

  /**
   * Resolve a single cell and its 4 neighbors (for incremental updates).
   * Returns an array of { x, y, index } entries to apply.
   * @param {(string|null)[][]} grid - semantic grid
   * @param {object} tilesetDef - tileset definition
   * @param {number} x - cell column
   * @param {number} y - cell row
   * @returns {{ x: number, y: number, index: number }[]}
   */
  resolveLocal(grid, tilesetDef, x, y) {
    const height = grid.length
    const width = grid[0]?.length || 0
    const updates = []

    // The cell itself + 4 cardinal neighbors
    const coords = [
      [x, y],
      [x, y - 1],
      [x + 1, y],
      [x, y + 1],
      [x - 1, y],
    ]

    for (const [cx, cy] of coords) {
      if (cx < 0 || cy < 0 || cx >= width || cy >= height) continue
      updates.push({
        x: cx,
        y: cy,
        index: this._resolveCell(grid, tilesetDef, cx, cy, width, height),
      })
    }

    return updates
  },

  /**
   * Resolve a single cell to its tile index.
   * @private
   */
  _resolveCell(grid, tilesetDef, x, y, width, height) {
    const typeName = grid[y][x]
    if (!typeName) return -1

    const tileDef = tilesetDef.tiles?.[typeName]
    if (!tileDef) return -1

    const baseIndex = tileDef.index

    // If no autotile mode, just return the base index
    if (!tileDef.autotile) return baseIndex

    const autotileMode = tileDef.autotile
    const autotileDef = tilesetDef.autotile?.[autotileMode]
    if (!autotileDef) return baseIndex

    // Compute bitmask-4: top/right/bottom/left
    const top    = this._isSameType(grid, typeName, x, y - 1, width, height) ? '1' : '0'
    const right  = this._isSameType(grid, typeName, x + 1, y, width, height) ? '1' : '0'
    const bottom = this._isSameType(grid, typeName, x, y + 1, width, height) ? '1' : '0'
    const left   = this._isSameType(grid, typeName, x - 1, y, width, height) ? '1' : '0'

    const bitmask = `${top}${right}${bottom}${left}`
    const offset = autotileDef.offsets?.[bitmask] ?? 0

    return baseIndex + offset
  },

  /**
   * Check if a neighbor cell has the same tile type.
   * @private
   */
  _isSameType(grid, typeName, x, y, width, height) {
    if (x < 0 || y < 0 || x >= width || y >= height) return false
    return grid[y][x] === typeName
  },
}
