import Enemy from './Enemy.js'
import Bullet from './Bullet.js'
import { generateId } from '/engine/Node.js'

// Shadow mage: teleports on a timer, then fires an 8-bullet ring.
export default class MageEnemy extends Enemy {
  ready() {
    const c = this.config
    this.teleportInterval = c.teleportInterval || 4.0
    this.teleportMargin = c.teleportMargin || 60
    this.teleportAttempts = c.teleportAttempts || 10
    this.teleportMinDistance = c.teleportMinDistance || 100
    this.teleportMaxDistance = c.teleportMaxDistance || 350
    this.bulletCount = c.bulletCount || 8
    this.bulletSpeed = c.bulletSpeed || 180
    this.bulletDamage = c.bulletDamage || 25
    this.bulletStyle = c.bulletStyle || 'mage'

    // engine creates gameObject from visual/collider defs
    this._baseScaleX = this.gameObject.scaleX
    this._baseScaleY = this.gameObject.scaleY
    this.gameObject.setDepth(7)

    this._initEnemy(c)
    this._teleportTimer = this.teleportInterval * 0.7
  }

  update(dt) {
    if (this._dead || !this.gameObject?.body?.enable) return
    this._tickHpBar()

    this._teleportTimer -= dt
    if (this._teleportTimer <= 0) {
      this._teleportTimer = this.teleportInterval
      this._teleport()
    }

    // Face the player
    const players = this.findByTag('player')
    if (players.length > 0 && players[0].gameObject) {
      const px = players[0].gameObject.x
      this.gameObject.setFlipX(px < this.gameObject.x)
    }
  }

  _teleport() {
    const margin = this.teleportMargin
    const bounds = this._getTeleportBounds()

    const players = this.findByTag('player')
    let nx = this.gameObject.x
    let ny = this.gameObject.y
    for (let i = 0; i < this.teleportAttempts; i++) {
      nx = bounds.xMin + Math.random() * Math.max(1, bounds.xMax - bounds.xMin)
      ny = bounds.yMin + Math.random() * Math.max(1, bounds.yMax - bounds.yMin)
      if (players.length > 0 && players[0].gameObject) {
        const p = players[0].gameObject
        const dx = nx - p.x
        const dy = ny - p.y
        const dist = Math.sqrt(dx * dx + dy * dy)
        if (dist >= this.teleportMinDistance && dist <= this.teleportMaxDistance) break
      } else {
        break
      }
    }

    // Teleport texture + blink
    this.gameObject.setTexture('mage_teleport')
    this.gameObject.setAlpha(0.3)
    this.scene.time.delayedCall(100, () => {
      if (!this.gameObject) return
      this.gameObject.x = nx
      this.gameObject.y = ny
      this.gameObject.body.reset(nx, ny)
      this.gameObject.setAlpha(1)
      this.gameObject.setTexture('mage_attack')
      this._shootRing()
      this.scene.time.delayedCall(300, () => {
        if (this.gameObject && !this._dead) this.gameObject.setTexture('mage_idle')
      })
    })
  }

  _getTeleportBounds() {
    const roomBounds = this.config.roomBounds
    if (roomBounds) {
      return this._shrinkBounds(roomBounds, this.teleportMargin)
    }

    const rm = this.findByTag('wave_manager')[0]
    const rooms = rm?._rooms || []
    const x = this.gameObject.x
    const y = this.gameObject.y
    const room = rooms.find(r => x >= r.xMin && x <= r.xMax && y >= r.yMin && y <= r.yMax)
    if (room) {
      return this._shrinkBounds(room, this.teleportMargin)
    }

    const wb = this.scene.physics.world.bounds
    return {
      xMin: this.teleportMargin,
      xMax: wb.width - this.teleportMargin,
      yMin: this.teleportMargin,
      yMax: wb.height - this.teleportMargin
    }
  }

  _shrinkBounds(bounds, margin) {
    const xMin = bounds.xMin + margin
    const xMax = bounds.xMax - margin
    const yMin = bounds.yMin + margin
    const yMax = bounds.yMax - margin
    if (xMin < xMax && yMin < yMax) return { xMin, xMax, yMin, yMax }

    const cx = (bounds.xMin + bounds.xMax) / 2
    const cy = (bounds.yMin + bounds.yMax) / 2
    return {
      xMin: cx - 1,
      xMax: cx + 1,
      yMin: cy - 1,
      yMax: cy + 1
    }
  }

  _shootRing() {
    const gm = this.findByTag('game_manager')[0]
    if (!gm || this._dead) return
    const cx = this.gameObject.x
    const cy = this.gameObject.y
    for (let i = 0; i < this.bulletCount; i++) {
      const a = (Math.PI * 2 / this.bulletCount) * i
      const vx = Math.cos(a) * this.bulletSpeed
      const vy = Math.sin(a) * this.bulletSpeed
      const bullet = new Bullet()
      bullet.id = generateId()
      bullet.config = {
        x: cx, y: cy,
        vx, vy,
        damage: this.bulletDamage,
        isEnemy: true,
        style: this.bulletStyle
      }
      gm.addChild(bullet)
    }
  }

  _die() {
    if (this._dead) return
    this.gameObject.setTexture('mage_die')
    super._die()
  }
}
