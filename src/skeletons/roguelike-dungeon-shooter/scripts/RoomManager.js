import { Node } from '/engine/Node.js'

// Room-based combat with 2D layout support
const ROOM_CONFIGS = [
  { type: 'start', enemies: [] },
  { type: 'combat', enemies: [
    { type: 'slime', count: 4 },
    { type: 'bat', count: 2 }
  ]},
  { type: 'combat', enemies: [
    { type: 'slime', count: 2 },
    { type: 'bat', count: 2 },
    { type: 'archer', count: 2 }
  ]},
  { type: 'combat', enemies: [
    { type: 'bat', count: 2 },
    { type: 'archer', count: 1 },
    { type: 'ghost', count: 1 },
    { type: 'mage', count: 1 }
  ]},
  { type: 'boss', enemies: [] }
]

export default class RoomManager extends Node {
  ready() {
    this.tags = ['wave_manager']

    const roomData = this.config.roomData || []
    this._rooms = roomData.map((rd, i) => ({
      xMin: rd.xMin, xMax: rd.xMax,
      yMin: rd.yMin, yMax: rd.yMax,
      centerX: rd.centerX, centerY: rd.centerY,
      type: ROOM_CONFIGS[i]?.type || 'combat',
      enemies: ROOM_CONFIGS[i]?.enemies || [],
      state: 'idle'
    }))

    const gm = this.findByTag('game_manager')[0]
    this._gm = gm
    this._bossConfig = gm?.wavesConfig?.boss || null

    this._currentRoom = -1
    this._aliveCount = 0
    this._exploredRooms = new Set()
  }

  startRun() {
    this._preSpawnAllRooms()
  }

  async _preSpawnAllRooms() {
    const gm = this._gm
    if (!gm) return
    const margin = 64
    for (let i = 0; i < this._rooms.length; i++) {
      const room = this._rooms[i]
      if (room.type !== 'combat') { room.enemyNodes = []; continue }
      const xMin = room.xMin + margin
      const xMax = room.xMax - margin
      const yMin = room.yMin + margin
      const yMax = room.yMax - margin
      const nodes = []
      for (const group of room.enemies) {
        const path = `entities/${group.type}.node.json`
        const nodeDef = this.sceneTree.nodeDefinitions[path] || {}
        const cfg = { ...(nodeDef.config || {}) }
        for (let j = 0; j < group.count; j++) {
          const x = xMin + Math.random() * (xMax - xMin)
          const y = yMin + Math.random() * (yMax - yMin)
          const node = await gm.instantiate(path, { ...cfg, x, y, roomIndex: i, roomBounds: { xMin: room.xMin, xMax: room.xMax, yMin: room.yMin, yMax: room.yMax } })
          if (node?.gameObject) {
            gm.addWallCollision(node.gameObject)
            node._dormant = true
            if (node.gameObject.body) node.gameObject.body.enable = false
          }
          nodes.push(node)
        }
      }
      room.enemyNodes = nodes
    }
  }

  update(dt) {
    const gm = this._gm
    if (!gm || gm.isPaused) return

    const player = this.findByTag('player')[0]
    if (!player?.gameObject) return

    const px = player.gameObject.x
    const py = player.gameObject.y

    for (let i = 0; i < this._rooms.length; i++) {
      const room = this._rooms[i]
      if (px >= room.xMin && px <= room.xMax && py >= room.yMin && py <= room.yMax) {
        if (i !== this._currentRoom && room.state === 'idle') {
          this._onEnterRoom(i)
        }
        break
      }
    }
  }

  _onEnterRoom(index) {
    const room = this._rooms[index]
    room.state = 'active'
    this._currentRoom = index
    this._exploredRooms.add(index)

    // Update minimap
    const hud = this.findByTag('hud')[0]
    if (hud) hud.updateMinimap(index, this._exploredRooms)

    if (room.type === 'start') {
      room.state = 'cleared'
      return
    }

    const dm = this.findByTag('door_manager')[0]
    if (dm) dm.closeDoor(index)

    if (room.type === 'boss') {
      this._spawnBoss(index)
    } else {
      this._activateRoomEnemies(index)
    }

    if (hud) {
      if (room.type === 'boss') {
        hud.showBossPhase()
        hud.showNotify('BOSS 来了!', 2000)
      } else {
        hud.showNotify(`战斗开始! 战斗房 ${index}/${this._rooms.length - 2}`, 2000)
      }
    }
  }

  _activateRoomEnemies(index) {
    const room = this._rooms[index]
    const nodes = room.enemyNodes || []
    this._aliveCount = 0
    for (const node of nodes) {
      if (!node || node._dead) continue
      this._aliveCount++
      node._dormant = false
      if (node.gameObject?.body) node.gameObject.body.enable = true
    }
    if (this._aliveCount === 0) this._onRoomClear()
  }

  _spawnBoss(index) {
    const room = this._rooms[index]
    const gm = this._gm
    if (!gm) return

    this._aliveCount = 1

    const x = room.centerX
    const y = room.yMin + 150

    const bossDef = this.sceneTree.nodeDefinitions['entities/boss.node.json']
    const cfg = {
      ...(this._bossConfig || {}),  // waves.json as base (lower priority)
      ...(bossDef?.config || {}),   // node.json overrides
      x, y
    }
    gm.instantiate('entities/boss.node.json', cfg).then(boss => {
      if (boss?.gameObject) gm.addWallCollision(boss.gameObject)
    }).catch(e => console.error('boss spawn failed', e))
  }

  onEnemyDied() {
    this._aliveCount = Math.max(0, this._aliveCount - 1)
    if (this._aliveCount === 0) {
      const room = this._rooms[this._currentRoom]
      const nodes = room?.enemyNodes || []
      const stillAlive = nodes.filter(n => n && !n._dead)
      if (stillAlive.length === 0) {
        this._onRoomClear()
      }
    }
  }

  _onRoomClear() {
    const room = this._rooms[this._currentRoom]
    if (!room || room.state !== 'active') return

    room.state = 'cleared'

    const dm = this.findByTag('door_manager')[0]
    if (dm) dm.openDoor(this._currentRoom)

    if (room.type === 'boss') {
      this.scene.time.delayedCall(800, () => {
        const gm = this.findByTag('game_manager')[0]
        if (gm) gm.onGameWin()
      })
    } else {
      this._spawnRewardChest(room)
      this._triggerUpgrade()
    }
  }

  _spawnRewardChest(room) {
    const gm = this.findByTag('game_manager')[0]
    if (!gm) return
    const weapons = ['pistol', 'shotgun', 'rifle', 'rocket']
    const weaponType = weapons[Math.floor(Math.random() * weapons.length)]
    gm.instantiate('entities/chest.node.json', {
      x: room.centerX,
      y: room.centerY,
      weaponType
    })
  }

  _triggerUpgrade() {
    const lm = this.findByTag('level_manager')[0]
    if (lm && lm.triggerRoomUpgrade) {
      lm.triggerRoomUpgrade()
    }
  }

  getCurrentLayer() { return 1 }
  getCurrentWave() { return this._currentRoom }
}
