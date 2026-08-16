// DOM-based minimap: renders room layout and exploration state
const MINIMAP_ASSETS = {
  'panel': 'minimap_panel_pixel',
  'room-current': 'minimap_room_current_pixel',
  'room-explored': 'minimap_room_explored_pixel',
  'room-adjacent': 'minimap_room_adjacent_pixel',
  'room-hidden': 'minimap_room_hidden_pixel',
  'role-start': 'minimap_room_start_pixel',
  'role-boss': 'minimap_room_boss_pixel',
  'conn-h': 'minimap_conn_h_pixel',
  'conn-v': 'minimap_conn_v_pixel',
}

const ROOM_W = 22
const ROOM_H = 17
const GAP_X = 24
const GAP_Y = 20
const PAD = 6

export default class Minimap {
  constructor(parentEl, ui) {
    if (!ui) throw new Error('Minimap requires sceneTree.ui')
    this._ui = ui
    this._el = document.createElement('div')
    this._el.id = 'minimap'
    this._el.className = 'minimap-pixel'
    this._rooms = []
    this._connections = []
    this._roomData = null
    this._applyAssetVars()
    parentEl.appendChild(this._el)
  }

  _applyAssetVars() {
    for (const [name, key] of Object.entries(MINIMAP_ASSETS)) {
      const url = this._ui.assetUrl(key)
      this._el.style.setProperty(`--minimap-${name}`, `url(${JSON.stringify(url)})`)
    }
  }

  init(layout, roomData) {
    this._roomData = roomData
    this._el.innerHTML = ''

    // Calculate grid extents
    let maxCol = 0, maxRow = 0
    for (const rd of roomData) {
      if (rd.gridCol > maxCol) maxCol = rd.gridCol
      if (rd.gridRow > maxRow) maxRow = rd.gridRow
    }

    // Container size
    const cw = (maxCol + 1) * ROOM_W + maxCol * GAP_X + PAD * 2
    const ch = (maxRow + 1) * ROOM_H + maxRow * GAP_Y + PAD * 2
    this._el.style.width = cw + 'px'
    this._el.style.height = ch + 'px'

    // Draw connections first (behind rooms)
    this._connections = []
    for (let i = 0; i < roomData.length; i++) {
      for (let j = i + 1; j < roomData.length; j++) {
        const a = roomData[i], b = roomData[j]
        const dc = Math.abs(a.gridCol - b.gridCol)
        const dr = Math.abs(a.gridRow - b.gridRow)
        if ((dc === 1 && dr === 0) || (dc === 0 && dr === 1)) {
          this._addConnection(a, b)
        }
      }
    }

    // Draw room divs
    this._rooms = []
    for (let i = 0; i < roomData.length; i++) {
      const rd = roomData[i]
      const div = document.createElement('div')
      div.className = 'minimap-room room-hidden'
      div.dataset.roomIndex = String(i)
      div.dataset.roomRole = i === 0 ? 'start' : (i === roomData.length - 1 ? 'boss' : 'normal')
      div.style.left = (rd.gridCol * (ROOM_W + GAP_X) + PAD) + 'px'
      div.style.top = (rd.gridRow * (ROOM_H + GAP_Y) + PAD) + 'px'
      div.style.width = ROOM_W + 'px'
      div.style.height = ROOM_H + 'px'
      this._el.appendChild(div)
      this._rooms.push(div)
    }

    // Initial state: only start room + adjacent visible
    const explored = new Set([0])
    this.update(0, explored)
  }

  _addConnection(a, b) {
    const line = document.createElement('div')
    const isHorizontal = a.gridRow === b.gridRow
    line.className = `minimap-connection ${isHorizontal ? 'conn-horizontal' : 'conn-vertical'}`
    const leftCol = Math.min(a.gridCol, b.gridCol)
    const topRow = Math.min(a.gridRow, b.gridRow)

    if (isHorizontal) {
      const x = leftCol * (ROOM_W + GAP_X) + ROOM_W + PAD
      const y = a.gridRow * (ROOM_H + GAP_Y) + ROOM_H / 2 + PAD - 1
      line.style.left = x + 'px'
      line.style.top = y + 'px'
      line.style.width = GAP_X + 'px'
      line.style.height = '2px'
    } else {
      const x = a.gridCol * (ROOM_W + GAP_X) + ROOM_W / 2 + PAD - 1
      const y = topRow * (ROOM_H + GAP_Y) + ROOM_H + PAD
      line.style.left = x + 'px'
      line.style.top = y + 'px'
      line.style.width = '2px'
      line.style.height = GAP_Y + 'px'
    }

    line.dataset.from = a.index
    line.dataset.to = b.index
    this._el.appendChild(line)
    this._connections.push(line)
  }

  update(currentRoom, exploredRooms) {
    if (!this._roomData) return

    const adjacent = this._getAdjacentRooms(exploredRooms)
    const visible = new Set([...exploredRooms, ...adjacent])

    for (let i = 0; i < this._rooms.length; i++) {
      const div = this._rooms[i]
      const hidden = !visible.has(i)
      const current = i === currentRoom
      const explored = exploredRooms.has(i)
      const role = div.dataset.roomRole

      div.className = 'minimap-room'
      if (hidden) {
        div.classList.add('room-hidden')
      } else if (current) {
        div.classList.add('room-current')
      } else if (explored) {
        div.classList.add('room-explored')
      } else {
        div.classList.add('room-adjacent')
      }

      if (!hidden && !current && role === 'start') div.classList.add('role-start')
      if (!hidden && !current && role === 'boss') div.classList.add('role-boss')
    }

    // Update connection visibility
    for (const line of this._connections) {
      const from = parseInt(line.dataset.from, 10)
      const to = parseInt(line.dataset.to, 10)
      line.style.display = (visible.has(from) && visible.has(to)) ? '' : 'none'
    }
  }

  _getAdjacentRooms(exploredRooms) {
    const result = new Set()
    for (const idx of exploredRooms) {
      const rd = this._roomData[idx]
      if (!rd) continue
      for (let j = 0; j < this._roomData.length; j++) {
        if (exploredRooms.has(j)) continue
        const other = this._roomData[j]
        const dc = Math.abs(rd.gridCol - other.gridCol)
        const dr = Math.abs(rd.gridRow - other.gridRow)
        if ((dc === 1 && dr === 0) || (dc === 0 && dr === 1)) {
          result.add(j)
        }
      }
    }
    return result
  }

  destroy() {
    this._el?.remove()
    this._el = null
    this._ui = null
  }
}
