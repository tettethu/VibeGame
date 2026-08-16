import { Node } from '/engine/Node.js'

// Door system: manages doors in 4 directions across all rooms
export default class DoorManager extends Node {
  ready() {
    this.tags = ['door_manager']
    const roomData = this.config.roomData || []

    this._doors = []
    this._roomDoors = roomData.map(() => [])
    this._tilemap = this.findByTag('tilemap')?.[0] || null
    this._doorTopLayer = 'door_roof'
    this._doorFaceLayer = 'door_body'

    for (const room of roomData) {
      // Right wall door
      if (room.hasRightDoor) {
        const cells = []
        for (let gy = room.rightDoorY[0]; gy <= room.rightDoorY[1]; gy++) cells.push({ x: room.x1 + 1, y: gy })
        this._createDoor(cells)
        this._roomDoors[room.index].push(this._doors.length - 1)
      }
      // Left wall door
      if (room.hasLeftDoor) {
        const cells = []
        for (let gy = room.leftDoorY[0]; gy <= room.leftDoorY[1]; gy++) cells.push({ x: room.x0 - 1, y: gy })
        this._createDoor(cells)
        this._roomDoors[room.index].push(this._doors.length - 1)
      }
      // Down wall door: width should follow vertical corridor width (CS), not corridor length (CW)
      if (room.hasDownDoor) {
        const cells = []
        for (let gx = room.downDoorX[0]; gx <= room.downDoorX[1]; gx++) cells.push({ x: gx, y: room.y1 + 1 })
        this._createDoor(cells)
        this._roomDoors[room.index].push(this._doors.length - 1)
      }
      // Up wall door: width should follow vertical corridor width (CS), not corridor length (CW)
      if (room.hasUpDoor) {
        const cells = []
        for (let gx = room.upDoorX[0]; gx <= room.upDoorX[1]; gx++) cells.push({ x: gx, y: room.y0 - 1 })
        this._createDoor(cells)
        this._roomDoors[room.index].push(this._doors.length - 1)
      }
    }
  }

  _createDoor(cells) {
    this._doors.push({ cells, isOpen: true })
  }

  openDoor(roomIndex) {
    const indices = this._roomDoors[roomIndex]
    if (!indices) return
    indices.forEach(i => this._setDoorOpen(i))
  }

  closeDoor(roomIndex) {
    const indices = this._roomDoors[roomIndex]
    if (!indices) return
    indices.forEach(i => this._setDoorClose(i))
  }

  _setDoorOpen(index) {
    const door = this._doors[index]
    if (!door) return
    this._applyDoorTiles(door, true)
    door.isOpen = true
  }

  _setDoorClose(index) {
    const door = this._doors[index]
    if (!door) return
    this._applyDoorTiles(door, false)
    door.isOpen = false
  }

  _applyDoorTiles(door, isOpen) {
    if (!this._tilemap) return
    for (const cell of door.cells || []) {
      this._tilemap.setTile(this._doorTopLayer, cell.x, cell.y - 1, isOpen ? null : 'door_top')
      this._tilemap.setTile(this._doorFaceLayer, cell.x, cell.y, isOpen ? null : 'door_face')
    }
  }

  destroy() {
    this._doors = []
    super.destroy?.()
  }
}
