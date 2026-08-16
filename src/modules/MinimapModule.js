import { Node } from '/engine/Node.js'

/**
 * MinimapModule — DOM-based grid minimap for room-based games.
 *
 * Renders a fixed-position panel showing room positions on a grid, exploration state
 * (hidden / adjacent / explored / current), and per-room roles (start / boss / normal).
 * Connections between orthogonally-adjacent rooms are auto-drawn.
 *
 * Verified for a roguelike dungeon layout where rooms live on a discrete grid and
 * exploration reveals adjacent rooms.
 *
 * Config:
 *   mountSelector: required. CSS selector for the parent element (e.g. '#game-container').
 *   assetUrlForKey: required. Function `(assetKey) => url-string-or-empty`.
 *                   Caller's URL resolver — accounts for appBasePath / deploy prefix.
 *                   Module sets CSS custom properties from this; missing assets render as 'none'.
 *   assetKeys: optional. Map of slot → manifest key. Defaults to:
 *     {
 *       panel:        'minimap_panel_pixel',
 *       roomCurrent:  'minimap_room_current_pixel',
 *       roomExplored: 'minimap_room_explored_pixel',
 *       roomAdjacent: 'minimap_room_adjacent_pixel',
 *       roomHidden:   'minimap_room_hidden_pixel',
 *       roleStart:    'minimap_room_start_pixel',
 *       roleBoss:     'minimap_room_boss_pixel',
 *       connH:        'minimap_conn_h_pixel',
 *       connV:        'minimap_conn_v_pixel',
 *     }
 *   style: optional. Geometry overrides:
 *     { roomW: 22, roomH: 17, gapX: 24, gapY: 20, padding: 6 }
 *   elementId: optional. DOM id for the panel (default 'minimap').
 *   className: optional. Class on the panel (default 'minimap-pixel').
 *
 * Public API:
 *   setRoomData(roomData)
 *     roomData: Array<{ gridCol, gridRow, index? }>
 *     Lays out the room grid; first room is "start", last is "boss".
 *   setCurrentRoom(currentIdx, exploredSet)
 *     exploredSet: Set<number> of room indices the player has entered.
 *     Updates room cell classes (hidden/adjacent/explored/current) and connection visibility.
 *
 * CSS contract: the host project must style `.minimap-pixel`, `.minimap-room.room-*`,
 * `.minimap-room.role-*`, `.minimap-connection.conn-{horizontal,vertical}`. The module
 * sets CSS custom properties `--minimap-{slot}` from `assetUrlForKey`; project CSS reads
 * them via `background-image: var(--minimap-room-current)` etc.
 */
const DEFAULT_KEYS = {
  panel:        'minimap_panel_pixel',
  roomCurrent:  'minimap_room_current_pixel',
  roomExplored: 'minimap_room_explored_pixel',
  roomAdjacent: 'minimap_room_adjacent_pixel',
  roomHidden:   'minimap_room_hidden_pixel',
  roleStart:    'minimap_room_start_pixel',
  roleBoss:     'minimap_room_boss_pixel',
  connH:        'minimap_conn_h_pixel',
  connV:        'minimap_conn_v_pixel',
}

const SLOT_TO_CSS = {
  panel:        'panel',
  roomCurrent:  'room-current',
  roomExplored: 'room-explored',
  roomAdjacent: 'room-adjacent',
  roomHidden:   'room-hidden',
  roleStart:    'role-start',
  roleBoss:     'role-boss',
  connH:        'conn-h',
  connV:        'conn-v',
}

const DEFAULT_STYLE = { roomW: 22, roomH: 17, gapX: 24, gapY: 20, padding: 6 }

export default class MinimapModule extends Node {
  ready() {
    const c = this.config || {}
    const mountSelector = c.mountSelector
    if (!mountSelector) throw new Error('MinimapModule: config.mountSelector required')
    const parentEl = document.querySelector(mountSelector)
    if (!parentEl) throw new Error(`MinimapModule: no element matches "${mountSelector}"`)

    this._assetUrlForKey = c.assetUrlForKey || (() => '')
    this._assetKeys = { ...DEFAULT_KEYS, ...(c.assetKeys || {}) }
    this._style = { ...DEFAULT_STYLE, ...(c.style || {}) }
    this._rooms = []
    this._connections = []
    this._roomData = null

    this._el = document.createElement('div')
    this._el.id = c.elementId || 'minimap'
    this._el.className = c.className || 'minimap-pixel'
    this._applyAssetVars()
    parentEl.appendChild(this._el)
  }

  _applyAssetVars() {
    for (const [slot, manifestKey] of Object.entries(this._assetKeys)) {
      const url = this._assetUrlForKey(manifestKey)
      const cssSlot = SLOT_TO_CSS[slot] || slot
      if (!url) console.warn(`[MinimapModule] Missing asset key: ${manifestKey}`)
      this._el.style.setProperty(`--minimap-${cssSlot}`, url ? `url("${url}")` : 'none')
    }
  }

  setRoomData(roomData) {
    this._roomData = roomData
    this._el.innerHTML = ''
    this._rooms = []
    this._connections = []

    const { roomW, roomH, gapX, gapY, padding } = this._style
    let maxCol = 0, maxRow = 0
    for (const rd of roomData) {
      if (rd.gridCol > maxCol) maxCol = rd.gridCol
      if (rd.gridRow > maxRow) maxRow = rd.gridRow
    }

    const cw = (maxCol + 1) * roomW + maxCol * gapX + padding * 2
    const ch = (maxRow + 1) * roomH + maxRow * gapY + padding * 2
    this._el.style.width = cw + 'px'
    this._el.style.height = ch + 'px'

    // Draw connections first so rooms paint on top
    for (let i = 0; i < roomData.length; i++) {
      for (let j = i + 1; j < roomData.length; j++) {
        const a = roomData[i], b = roomData[j]
        const dc = Math.abs(a.gridCol - b.gridCol)
        const dr = Math.abs(a.gridRow - b.gridRow)
        if ((dc === 1 && dr === 0) || (dc === 0 && dr === 1)) {
          this._addConnection(a, b, i, j)
        }
      }
    }

    for (let i = 0; i < roomData.length; i++) {
      const rd = roomData[i]
      const div = document.createElement('div')
      div.className = 'minimap-room room-hidden'
      div.dataset.roomIndex = String(i)
      div.dataset.roomRole = i === 0 ? 'start' : (i === roomData.length - 1 ? 'boss' : 'normal')
      div.style.left = (rd.gridCol * (roomW + gapX) + padding) + 'px'
      div.style.top = (rd.gridRow * (roomH + gapY) + padding) + 'px'
      div.style.width = roomW + 'px'
      div.style.height = roomH + 'px'
      this._el.appendChild(div)
      this._rooms.push(div)
    }

    // Initial render: only start room
    this.setCurrentRoom(0, new Set([0]))
  }

  _addConnection(a, b, ai, bi) {
    const { roomW, roomH, gapX, gapY, padding } = this._style
    const line = document.createElement('div')
    const isHorizontal = a.gridRow === b.gridRow
    line.className = `minimap-connection ${isHorizontal ? 'conn-horizontal' : 'conn-vertical'}`
    const leftCol = Math.min(a.gridCol, b.gridCol)
    const topRow = Math.min(a.gridRow, b.gridRow)

    if (isHorizontal) {
      line.style.left = (leftCol * (roomW + gapX) + roomW + padding) + 'px'
      line.style.top  = (a.gridRow * (roomH + gapY) + roomH / 2 + padding - 1) + 'px'
      line.style.width = gapX + 'px'
      line.style.height = '2px'
    } else {
      line.style.left = (a.gridCol * (roomW + gapX) + roomW / 2 + padding - 1) + 'px'
      line.style.top  = (topRow * (roomH + gapY) + roomH + padding) + 'px'
      line.style.width = '2px'
      line.style.height = gapY + 'px'
    }

    line.dataset.from = ai
    line.dataset.to = bi
    this._el.appendChild(line)
    this._connections.push(line)
  }

  setCurrentRoom(currentIdx, exploredSet) {
    if (!this._roomData) return
    const adjacent = this._getAdjacentRooms(exploredSet)
    const visible = new Set([...exploredSet, ...adjacent])

    for (let i = 0; i < this._rooms.length; i++) {
      const div = this._rooms[i]
      const hidden = !visible.has(i)
      const current = i === currentIdx
      const explored = exploredSet.has(i)
      const role = div.dataset.roomRole

      div.className = 'minimap-room'
      if (hidden) div.classList.add('room-hidden')
      else if (current) div.classList.add('room-current')
      else if (explored) div.classList.add('room-explored')
      else div.classList.add('room-adjacent')

      if (!hidden && !current && role === 'start') div.classList.add('role-start')
      if (!hidden && !current && role === 'boss') div.classList.add('role-boss')
    }

    for (const line of this._connections) {
      const from = parseInt(line.dataset.from, 10)
      const to = parseInt(line.dataset.to, 10)
      line.style.display = (visible.has(from) && visible.has(to)) ? '' : 'none'
    }
  }

  _getAdjacentRooms(exploredSet) {
    const result = new Set()
    for (const idx of exploredSet) {
      const rd = this._roomData[idx]
      if (!rd) continue
      for (let j = 0; j < this._roomData.length; j++) {
        if (exploredSet.has(j)) continue
        const other = this._roomData[j]
        const dc = Math.abs(rd.gridCol - other.gridCol)
        const dr = Math.abs(rd.gridRow - other.gridRow)
        if ((dc === 1 && dr === 0) || (dc === 0 && dr === 1)) result.add(j)
      }
    }
    return result
  }

  destroy() {
    this._el?.remove()
    this._el = null
  }
}
