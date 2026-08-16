import { Node, generateId } from '/engine/Node.js'
import Player from './Player.js'
import SlimeEnemy from './SlimeEnemy.js'
import ArcherEnemy from './ArcherEnemy.js'
import MageEnemy from './MageEnemy.js'
import Bullet from './Bullet.js'
import WeaponDrop from './WeaponDrop.js'
import CoinOrb from './CoinOrb.js'
import ManaOrb from './ManaOrb.js'
import WeaponVisual from './WeaponVisual.js'
import RoomManager from './RoomManager.js'
import HUD from './HUD.js'
import LevelUpManager from './LevelUpManager.js'
import UpgradeUI from './UpgradeUI.js'
import BatEnemy from './BatEnemy.js'
import GhostEnemy from './GhostEnemy.js'
import SkeletonHandEnemy from './SkeletonHandEnemy.js'
import BossEnemy from './BossEnemy.js'
import WraithShardEnemy from './WraithShardEnemy.js'
import DoorManager from './DoorManager.js'
import Chest from './Chest.js'

// Global state management: init/pause/win-lose/collision
export default class GameManager extends Node {
  ready() {
    this.tags = ['game_manager']
    this.isPaused = true
    this._startTime = Date.now()
    this._killCount = 0
    this._initialized = false
    this._pendingStart = false
    this._sessionStarted = false
    this._menuPaused = false
    this._pauseKeyHandler = null

    this.sceneTree.scriptClasses['Player'] = Player
    this.sceneTree.scriptClasses['SlimeEnemy'] = SlimeEnemy
    this.sceneTree.scriptClasses['ArcherEnemy'] = ArcherEnemy
    this.sceneTree.scriptClasses['MageEnemy'] = MageEnemy
    this.sceneTree.scriptClasses['Bullet'] = Bullet
    this.sceneTree.scriptClasses['WeaponDrop'] = WeaponDrop
    this.sceneTree.scriptClasses['CoinOrb'] = CoinOrb
    this.sceneTree.scriptClasses['ManaOrb'] = ManaOrb
    this.sceneTree.scriptClasses['WeaponVisual'] = WeaponVisual
    this.sceneTree.scriptClasses['BatEnemy'] = BatEnemy
    this.sceneTree.scriptClasses['GhostEnemy'] = GhostEnemy
    this.sceneTree.scriptClasses['SkeletonHandEnemy'] = SkeletonHandEnemy
    this.sceneTree.scriptClasses['BossEnemy'] = BossEnemy
    this.sceneTree.scriptClasses['WraithShardEnemy'] = WraithShardEnemy
    this.sceneTree.scriptClasses['Chest'] = Chest

    this._installStartHook()
    this._installPauseHotkey()
    this._init()
  }

  _installStartHook() {
    window.__vibegameStartRun = () => this.startRun()
  }

  _installPauseHotkey() {
    this._pauseKeyHandler = (e) => {
      if (e.key !== 'Escape') return
      if (!this._initialized || !this._sessionStarted) return
      if (document.getElementById('upgrade-overlay')) return
      if (document.getElementById('end-overlay')) return
      e.preventDefault()

      if (this._menuPaused) {
        this.resumeFromMenuPause()
      } else {
        this.pauseForMenu()
      }
    }
    window.addEventListener('keydown', this._pauseKeyHandler)
  }

  async _init() {
    // Load configs
    this.elementsConfig = await this._loadJson('config/elements.json')
    this.playerSpawnConfig = await this._loadJson('config/player.json')
    this.weaponsConfig = await this._loadJson('config/weapons.json')
    this.wavesConfig = await this._loadJson('config/waves.json')
    this.dungeonConfig = await this._loadJson('config/dungeon.json')
    this.doorConfig = await this._loadJson('config/door.json')

    // Load layouts and pick one randomly
    const layoutsData = await this._loadJson('config/layouts.json')
    const layouts = layoutsData.layouts || []
    const chosen = layouts[Math.floor(Math.random() * layouts.length)]

    // Compute room data from chosen layout
    const roomData = this._computeRoomData(chosen)
    this._roomData = roomData
    this._chosenLayout = chosen

    // Preload entity definitions
    const playerNodeDef = await this._loadJson('entities/player.node.json')
    this.sceneTree.nodeDefinitions['entities/player.node.json'] = playerNodeDef
    for (const type of ['slime', 'archer', 'mage', 'bat', 'ghost', 'skeleton_hand']) {
      const def = await this._loadJson(`entities/${type}.node.json`)
      this.sceneTree.nodeDefinitions[`entities/${type}.node.json`] = def
    }
    const bossDef = await this._loadJson('entities/boss.node.json')
    this.sceneTree.nodeDefinitions['entities/boss.node.json'] = bossDef
    const shardDef = await this._loadJson('entities/wraith_shard.node.json')
    this.sceneTree.nodeDefinitions['entities/wraith_shard.node.json'] = shardDef
    const chestDef = await this._loadJson('entities/chest.node.json')
    this.sceneTree.nodeDefinitions['entities/chest.node.json'] = chestDef

    // Background & walls using 2D layout
    this._createBackground(roomData)

    // Create DoorManager with precomputed room data
    const dm = new DoorManager()
    dm.id = generateId()
    dm.config = { roomData, dungeonConfig: this.dungeonConfig, doorConfig: this.doorConfig }
    this.addChild(dm)
    this.doorManager = dm

    // Create HUD
    const hud = new HUD()
    hud.id = generateId()
    hud.config = {}
    this.hud = hud
    this.addChild(hud)

    // Create Upgrade UI
    const upgradeUI = new UpgradeUI()
    upgradeUI.id = generateId()
    upgradeUI.config = {}
    this.addChild(upgradeUI)

    // Create LevelUpManager
    const lm = new LevelUpManager()
    lm.id = generateId()
    lm.config = {}
    this.addChild(lm)

    // Spawn player at first room center
    const startRoom = roomData[0]
    const player = await this.instantiate('entities/player.node.json', {
      ...(playerNodeDef.config || {}),
      x: startRoom.centerX - 60,
      y: startRoom.centerY
    })
    this.player = player

    // Weapon granted by chest in start room - no initial weapon
    hud.updateHP(player.hp, player.maxHP)
    hud.updateShield(player.shield, player.maxShield)
    hud.updateMana(Math.floor(player.mana), player.maxMana)
    hud.updateCoins(player.coins)

    // Camera follow player
    if (player.gameObject) {
      this.scene.cameras.main.startFollow(player.gameObject, true, 0.08, 0.08)
      this.addWallCollision(player.gameObject)
    }

    // Create room manager with precomputed room data
    const rm = new RoomManager()
    rm.id = generateId()
    rm.config = { roomData, wavesConfig: this.wavesConfig }
    this.addChild(rm)
    this.roomManager = rm

    // Spawn chest in start room with random weapon
    const weaponPool = ['pistol', 'shotgun', 'rifle', 'rocket']
    const startWeapon = weaponPool[Math.floor(Math.random() * weaponPool.length)]
    const chestX = startRoom.centerX
    const chestY = startRoom.centerY
    await this.instantiate('entities/chest.node.json', { x: chestX, y: chestY, weaponType: startWeapon })

    // Init minimap after HUD is ready
    hud.initMinimap(chosen, roomData)

    this.scene.physics.pause()
    this._initialized = true
    if (this._pendingStart) {
      this._pendingStart = false
      this.startRun()
    }
  }

  startRun() {
    if (this._sessionStarted) return
    if (!this._initialized) {
      this._pendingStart = true
      return
    }
    this._sessionStarted = true
    this.isPaused = false
    this._menuPaused = false
    this.sceneTree.running = true
    this._startTime = Date.now()
    this.player?.suspendFireUntilPointerUp?.()
    this.scene.physics.resume()
    this.roomManager?.startRun?.()
    this.hud?.showIntroGuide?.(2400)
  }

  // Compute world coordinates from grid-based layout
  _computeRoomData(layout) {
    const WALL = 1
    const dc = this.dungeonConfig || {}
    const RW = dc.roomWidth || 21
    const RH = dc.roomHeight || 15
    const CL = dc.corridorWidth || 9
    const CS = dc.corridorHeight || 5
    const TS = dc.tileSize || 32
    const CR = Math.floor(RH / 2) - Math.floor(CS / 2)
    const CC = Math.floor(RW / 2) - Math.floor(CS / 2)

    const rooms = layout.rooms.map((pos, i) => {
      const x0 = WALL + pos.col * (RW + CL)
      const y0 = WALL + pos.row * (RH + CL)
      return {
        index: i, gridCol: pos.col, gridRow: pos.row,
        x0, y0, x1: x0 + RW - 1, y1: y0 + RH - 1
      }
    })

    // Compute neighbors and door positions
    for (const room of rooms) {
      const hasNeighbor = (dc, dr) => rooms.some(r =>
        r.gridCol === room.gridCol + dc && r.gridRow === room.gridRow + dr)
      room.hasRightDoor = hasNeighbor(1, 0)
      room.hasLeftDoor = hasNeighbor(-1, 0)
      room.hasDownDoor = hasNeighbor(0, 1)
      room.hasUpDoor = hasNeighbor(0, -1)
      room.rightDoorY = room.hasRightDoor ? [room.y0 + CR, room.y0 + CR + CS - 1] : null
      room.leftDoorY = room.hasLeftDoor ? [room.y0 + CR, room.y0 + CR + CS - 1] : null
      room.downDoorX = room.hasDownDoor ? [room.x0 + CC, room.x0 + CC + CS - 1] : null
      room.upDoorX = room.hasUpDoor ? [room.x0 + CC, room.x0 + CC + CS - 1] : null
      room.centerX = (room.x0 + RW / 2) * TS
      room.centerY = (room.y0 + RH / 2) * TS
      room.xMin = room.x0 * TS
      room.xMax = (room.x1 + 1) * TS
      room.yMin = room.y0 * TS
      room.yMax = (room.y1 + 1) * TS
    }
    return rooms
  }

  _createBackground(roomData) {
    const TS = 32
    this.scene.cameras.main.setBackgroundColor('#0d1117')
    this._tileLayers = {
      ground: 'ground',
      wallRoof: 'wall_roof',
      wallBody: 'wall_body',
      doorRoof: 'door_roof',
      doorBody: 'door_body',
    }

    const dc = this.dungeonConfig || {}
    const RW = dc.roomWidth || 21
    const RH = dc.roomHeight || 15
    const CL = dc.corridorWidth || 9
    const CS = dc.corridorHeight || 5
    const WALL = 1
    const CR = Math.floor(RH / 2) - Math.floor(CS / 2)
    const CC = Math.floor(RW / 2) - Math.floor(CS / 2)

    // Compute grid extents
    let maxCol = 0, maxRow = 0
    for (const rd of roomData) {
      if (rd.gridCol > maxCol) maxCol = rd.gridCol
      if (rd.gridRow > maxRow) maxRow = rd.gridRow
    }
    const totalW = WALL + (maxCol + 1) * RW + maxCol * CL + WALL
    const totalH = WALL + (maxRow + 1) * RH + maxRow * CL + WALL

    // Compute corridors between adjacent rooms
    const corridors = []
    for (let i = 0; i < roomData.length; i++) {
      for (let j = i + 1; j < roomData.length; j++) {
        const a = roomData[i], b = roomData[j]
        const dc = a.gridCol - b.gridCol
        const dr = a.gridRow - b.gridRow
        if (dc === -1 && dr === 0) {
          // Horizontal corridor: a is left of b
          corridors.push({
            x0: a.x1 + 1, x1: b.x0 - 1,
            y0: a.y0 + CR, y1: a.y0 + CR + CS - 1,
            dir: 'horizontal'
          })
        } else if (dc === 0 && dr === -1) {
          // Vertical corridor: a is above b
          corridors.push({
            x0: a.x0 + CC, x1: a.x0 + CC + CS - 1,
            y0: a.y1 + 1, y1: b.y0 - 1,
            dir: 'vertical'
          })
        }
      }
    }

    // Build tile grid
    const grid = []
    for (let y = 0; y < totalH; y++) {
      const row = []
      for (let x = 0; x < totalW; x++) {
        let tile = null
        // Check rooms
        for (const room of roomData) {
          if (x >= room.x0 && x <= room.x1 && y >= room.y0 && y <= room.y1) {
            tile = this._pickFloorTile(x, y, room.index)
            break
          }
        }
        // Check corridors
        if (!tile) {
          for (const c of corridors) {
            if (x >= c.x0 && x <= c.x1 && y >= c.y0 && y <= c.y1) {
              tile = 'floor_01'
              break
            }
          }
        }
        row.push(tile)
      }
      grid.push(row)
    }

    this._tileGrid = grid

    // Feed grid to TileMap node
    const tilemapNode = this.findByTag('tilemap')?.[0]
    if (tilemapNode) {
      tilemapNode.init(totalW, totalH, {
        layers: [
          { name: this._tileLayers.ground, z: 0, collision: false },
          { name: this._tileLayers.wallBody, z: 7, collision: true },
          { name: this._tileLayers.wallRoof, z: 8, collision: false },
          { name: this._tileLayers.doorBody, z: 7, collision: true },
          { name: this._tileLayers.doorRoof, z: 8, collision: false },
        ],
      })
      for (let y = 0; y < totalH; y++) {
        for (let x = 0; x < totalW; x++) {
          if (grid[y][x]) tilemapNode.setTile(this._tileLayers.ground, x, y, grid[y][x])
        }
      }
    }

    // Build walls for each room
    for (const room of roomData) {
      this._buildRoomWalls(tilemapNode, room, {
        leftDoorY: room.leftDoorY,
        rightDoorY: room.rightDoorY,
        upDoorX: room.upDoorX,
        downDoorX: room.downDoorX
      })
    }

    for (const corridor of corridors) {
      this._buildCorridorWalls(tilemapNode, corridor)
    }

    // Set physics world bounds
    this.scene.physics.world.setBounds(0, 0, totalW * TS, totalH * TS)
    this.scene.cameras.main.setBounds(0, 0, totalW * TS, totalH * TS + 64)

    if (this.player?.gameObject) {
      this.addWallCollision(this.player.gameObject)
    }
  }

  _pickFloorTile(x, y, roomIdx) {
    const r = ((x * 7 + y * 13 + roomIdx * 31) % 100)
    if (r < 55) return 'floor_01'
    if (r < 70) return 'floor_02'
    if (r < 80) return 'floor_03'
    if (r < 87) return 'floor_04'
    if (r < 92) return 'floor_05'
    if (r < 95) return 'floor_06'
    if (r < 97) return 'floor_07'
    if (r < 99) return 'floor_08'
    return 'floor_09'
  }

  // Build wall tiles around a room with 4-direction door support
  _buildRoomWalls(tilemapNode, room, doors) {
    const { x0, x1, y0, y1 } = room
    const L = this._tileLayers

    // Top row
    for (let gx = x0 - 1; gx <= x1 + 1; gx++) {
      if (doors.upDoorX && gx >= doors.upDoorX[0] && gx <= doors.upDoorX[1]) continue
      const alt = this._useAltWall(gx, y0 - 1, room.index)
      this._setWallColumn(
        tilemapNode,
        L.wallRoof,
        L.wallBody,
        gx,
        y0 - 1,
        alt ? 'wall_top_alt' : 'wall_top',
        alt ? 'wall_face_alt' : 'wall_face'
      )
    }
    // Bottom row
    for (let gx = x0 - 1; gx <= x1 + 1; gx++) {
      if (doors.downDoorX && gx >= doors.downDoorX[0] && gx <= doors.downDoorX[1]) continue
      const alt = this._useAltWall(gx, y1 + 1, room.index + 17)
      this._setWallColumn(
        tilemapNode,
        L.wallRoof,
        L.wallBody,
        gx,
        y1 + 1,
        alt ? 'wall_top_alt' : 'wall_top',
        alt ? 'wall_face_alt' : 'wall_face'
      )
    }
    // Left side
    for (let gy = y0; gy <= y1; gy++) {
      if (doors.leftDoorY && gy >= doors.leftDoorY[0] && gy <= doors.leftDoorY[1]) continue
      this._setWallColumn(tilemapNode, L.wallRoof, L.wallBody, x0 - 1, gy, 'wall_top', 'wall_face')
    }
    // Right side
    for (let gy = y0; gy <= y1; gy++) {
      if (doors.rightDoorY && gy >= doors.rightDoorY[0] && gy <= doors.rightDoorY[1]) continue
      this._setWallColumn(tilemapNode, L.wallRoof, L.wallBody, x1 + 1, gy, 'wall_top', 'wall_face')
    }
  }

  _buildCorridorWalls(tilemapNode, corridor) {
    const L = this._tileLayers

    if (corridor.dir === 'horizontal') {
      for (let gx = corridor.x0; gx <= corridor.x1; gx++) {
        const topAlt = this._useAltWall(gx, corridor.y0 - 1, 61)
        const bottomAlt = this._useAltWall(gx, corridor.y1 + 1, 79)
        this._setWallColumn(
          tilemapNode,
          L.wallRoof,
          L.wallBody,
          gx,
          corridor.y0 - 1,
          topAlt ? 'wall_top_alt' : 'wall_top',
          topAlt ? 'wall_face_alt' : 'wall_face'
        )
        this._setWallColumn(
          tilemapNode,
          L.wallRoof,
          L.wallBody,
          gx,
          corridor.y1 + 1,
          bottomAlt ? 'wall_top_alt' : 'wall_top',
          bottomAlt ? 'wall_face_alt' : 'wall_face'
        )
      }
      return
    }

    for (let gy = corridor.y0; gy <= corridor.y1; gy++) {
      this._setWallColumn(tilemapNode, L.wallRoof, L.wallBody, corridor.x0 - 1, gy, 'wall_top', 'wall_face')
      this._setWallColumn(tilemapNode, L.wallRoof, L.wallBody, corridor.x1 + 1, gy, 'wall_top', 'wall_face')
    }
  }

  _setTileVisual(tilemapNode, layerName, x, y, tileType) {
    if (!tilemapNode || x < 0 || y < 0) return
    tilemapNode.setTile(layerName, x, y, tileType)
  }

  _setWallColumn(tilemapNode, topLayer, faceLayer, x, y, topTile, faceTile) {
    this._setTileVisual(tilemapNode, topLayer, x, y - 1, topTile)
    this._setTileVisual(tilemapNode, faceLayer, x, y, faceTile)
  }

  _useAltWall(x, y, seed = 0) {
    return ((x * 17 + y * 31 + seed * 13) % 9) === 0
  }

  spawnWeaponDrop(type, data, x, y) {
    const drop = new WeaponDrop()
    drop.id = generateId()
    drop.config = { weaponType: type, weaponData: data, name: data?.name || type, x, y }
    this.addChild(drop)
  }

  _getTerrainCollisionGroups() {
    const tilemapNode = this.findByTag('tilemap')?.[0]
    if (!tilemapNode) return []
    return [
      tilemapNode.getCollisionLayer(this._tileLayers.wallBody),
      tilemapNode.getCollisionLayer(this._tileLayers.doorBody),
    ].filter(Boolean)
  }

  addWallCollision(gameObject, onCollide = null) {
    if (!gameObject) return
    const callback = onCollide || undefined
    for (const group of this._getTerrainCollisionGroups()) {
      this.scene.physics.add.collider(gameObject, group, callback)
    }
  }

  _aabbOverlap(a, b) {
    const aw = a.body ? a.body.halfWidth : (a.displayWidth || a.width) / 2
    const ah = a.body ? a.body.halfHeight : (a.displayHeight || a.height) / 2
    const bw = b.body ? b.body.halfWidth : (b.displayWidth || b.width) / 2
    const bh = b.body ? b.body.halfHeight : (b.displayHeight || b.height) / 2
    return Math.abs(a.x - b.x) < aw + bw && Math.abs(a.y - b.y) < ah + bh
  }

  update(dt) {
    if (!this._initialized) return
    if (this.isPaused) return
    this._checkCollisions()
  }

  _checkCollisions() {
    const players = this.findByTag('player')
    if (players.length === 0) return
    const player = players[0]
    if (!player.gameObject || player._dead) return

    const enemies = this.findByTag('enemy')
    const allNodes = [...this.sceneTree.nodes.values()]
    const bullets = allNodes.filter(n => n.constructor?.name === 'Bullet' && n.gameObject && !n._destroyed)

    const playerBullets = bullets.filter(n => !n.isEnemy)
    for (const bullet of playerBullets) {
      if (!bullet.gameObject) continue
      for (const enemy of enemies) {
        if (!enemy.gameObject || enemy._dead) continue
        if (this._aabbOverlap(bullet.gameObject, enemy.gameObject)) {
          const baseDmg = bullet.damage || 10
          const dmg = bullet.isCrit ? baseDmg * 2 : baseDmg
          const wasAlive = !enemy._dead
          if (!enemy._dead) enemy.takeDamage(dmg, bullet.isCrit)
          if (wasAlive && enemy._dead) this._killCount++
          bullet.onHit()
        }
      }
    }

    const enemyBullets = bullets.filter(n => n.isEnemy)
    for (const bullet of enemyBullets) {
      if (!bullet.gameObject) continue
      if (this._aabbOverlap(bullet.gameObject, player.gameObject)) {
        if (player.isRollInvincible && player.isRollInvincible()) continue
        player.takeDamage(bullet.damage || 10)
        bullet.onHit()
      }
    }

    const slimes = this.findByTag('slime')
    for (const slime of slimes) {
      if (!slime.gameObject || slime._dead) continue
      if (this._aabbOverlap(slime.gameObject, player.gameObject)) {
        if (player.isRollInvincible && player.isRollInvincible()) continue
        slime.onContactPlayer(player)
      }
    }

    const bats = this.findByTag('bat')
    for (const bat of bats) {
      if (!bat.gameObject || bat._dead) continue
      if (this._aabbOverlap(bat.gameObject, player.gameObject)) {
        if (player.isRollInvincible && player.isRollInvincible()) continue
        bat.onContactPlayer(player)
      }
    }

    const bosses = this.findByTag('boss')
    for (const boss of bosses) {
      if (!boss.gameObject || boss._dead) continue
      if (!boss.onContactPlayer) continue
      if (this._aabbOverlap(boss.gameObject, player.gameObject)) {
        if (player.isRollInvincible && player.isRollInvincible()) continue
        boss.onContactPlayer(player)
      }
    }

    const minions = this.findByTag('boss_minion')
    for (const minion of minions) {
      if (!minion.gameObject || minion._dead) continue
      if (!minion.onContactPlayer) continue
      if (this._aabbOverlap(minion.gameObject, player.gameObject)) {
        if (player.isRollInvincible && player.isRollInvincible()) continue
        minion.onContactPlayer(player)
      }
    }

    const crystals = this.findByTag('crystal')
    for (const bullet of bullets) {
      if (!bullet.gameObject || bullet._destroyed) continue
      for (const crystal of crystals) {
        if (!crystal.gameObject) continue
        if (this._aabbOverlap(bullet.gameObject, crystal.gameObject)) {
          bullet.onHit()
          break
        }
      }
    }
  }


  async _loadJson(path) {
    const cfg = window.__APP_CONFIG__ || {}
    const basePath = String(cfg.appBasePath || '').replace(/\/$/, '')
    const candidates = [
      basePath ? `${basePath}/${path}` : `/${path}`
    ]
    const uniqueCandidates = [...new Set(candidates)]
    for (const url of uniqueCandidates) {
      try {
        const resp = await fetch(`${url}?t=${Date.now()}`)
        if (resp.ok) return await resp.json()
      } catch {}
    }
    console.error(`Failed to load ${path}`)
    return {}
  }

  pauseForUpgrade() {
    this.isPaused = true
    this.sceneTree.running = false
    this.scene.physics.pause()
  }

  resumeFromUpgrade() {
    this.isPaused = false
    this.sceneTree.running = true
    this.player?.suspendFireUntilPointerUp?.()
    this.scene.physics.resume()
    document.getElementById('game-container')?.focus?.()
  }

  pauseForMenu() {
    if (this._menuPaused) return
    this._menuPaused = true
    this.isPaused = true
    this.scene.physics.pause()
    this.sceneTree.running = false
    this.hud?.showPauseOverlay?.(() => this.resumeFromMenuPause())
  }

  resumeFromMenuPause() {
    if (!this._menuPaused) return
    this._menuPaused = false
    this.isPaused = false
    this.sceneTree.running = true
    this.player?.suspendFireUntilPointerUp?.()
    this.scene.physics.resume()
    this.hud?.hidePauseOverlay?.()
    document.getElementById('game-container')?.focus?.()
  }

  onPlayerDied() {
    this.hud?.hidePauseOverlay?.()
    this.isPaused = true
    this._menuPaused = false
    this.scene.physics.pause()
    this._showGameOver(false)
  }

  onGameWin() {
    this.hud?.hidePauseOverlay?.()
    this.isPaused = true
    this._menuPaused = false
    this.scene.physics.pause()
    this._showGameOver(true)
  }

  _showGameOver(won) {
    const title = won ? '胜利' : '失败'
    const titleColor = won ? '#00ff88' : '#ff4444'

    const overlay = document.createElement('div')
    overlay.id = 'end-overlay'
    overlay.innerHTML = `
      <div class="end-title" style="color:${titleColor}">${title}</div>
      <button class="end-btn">重新开始</button>
    `
    overlay.querySelector('.end-btn').addEventListener('click', () => window.location.reload())
    this.sceneTree.ui.mount(overlay)
  }

  destroy() {
    if (this._pauseKeyHandler) {
      window.removeEventListener('keydown', this._pauseKeyHandler)
      this._pauseKeyHandler = null
    }
    if (this._backdrop) { this._backdrop.destroy(); this._backdrop = null }
    if (this._floorGraphics) { this._floorGraphics.destroy(); this._floorGraphics = null }
    if (this._floorTile) { this._floorTile.destroy(); this._floorTile = null }
    if (this._frame) { this._frame.destroy(); this._frame = null }
  }
}
