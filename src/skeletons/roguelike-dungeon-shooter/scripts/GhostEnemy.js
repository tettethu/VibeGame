import Enemy from './Enemy.js'
import Bullet from './Bullet.js'
import { generateId } from '/engine/Node.js'

// Ghost: stationary shooter with idle animation and sin-wave float, fires laser bullets
export default class GhostEnemy extends Enemy {
  ready() {
    const c = this.config
    this.shootInterval = c.shootInterval || 3.0
    this.bulletSpeed = c.bulletSpeed || 160
    this.bulletDamage = c.bulletDamage || 20
    this.bulletStyle = c.bulletStyle || 'ghost_laser'

    this.gameObject.setDepth(7)
    this._initEnemy(c)
    this._shootTimer = this.shootInterval * 0.6

    // Frame animation
    this._frameIdx = 0
    this._frameTimer = 0
    this._frameInterval = 0.3
    this._frames = ['idle_0', 'idle_1', 'idle_2', 'idle_3']

    // Sin-wave float
    this._baseY = this.gameObject.y
    this._floatTime = Math.random() * Math.PI * 2  // random phase offset
  }

  update(dt) {
    if (this._dead || !this.gameObject?.body?.enable) return
    this._tickHpBar()

    // Frame animation
    this._frameTimer += dt
    if (this._frameTimer >= this._frameInterval) {
      this._frameTimer = 0
      this._frameIdx = (this._frameIdx + 1) % this._frames.length
      this._setFrame(this._frames[this._frameIdx])
    }

    // Sin-wave float
    this._floatTime += dt * 2
    const floatOffset = Math.sin(this._floatTime) * 0.5 * dt * 60
    this.gameObject.y += floatOffset

    this._shootTimer -= dt
    if (this._shootTimer <= 0) {
      this._shootTimer = this.shootInterval
      this._shoot()
    }

    const players = this.findByTag('player')
    if (players.length > 0 && players[0].gameObject) {
      const px = players[0].gameObject.x
      this.gameObject.setFlipX(px < this.gameObject.x)
    }
  }

  _setFrame(frame) {
    if (this.gameObject) this.gameObject.setTexture('ghost_idle', frame)
  }

  _shoot() {
    const players = this.findByTag('player')
    if (players.length === 0) return
    const p = players[0]
    if (!p.gameObject) return

    const gm = this.findByTag('game_manager')[0]
    if (!gm) return

    const angle = Phaser.Math.Angle.Between(
      this.gameObject.x, this.gameObject.y,
      p.gameObject.x, p.gameObject.y
    )
    const vx = Math.cos(angle) * this.bulletSpeed
    const vy = Math.sin(angle) * this.bulletSpeed

    const bullet = new Bullet()
    bullet.id = generateId()
    bullet.config = {
      x: this.gameObject.x,
      y: this.gameObject.y,
      vx, vy,
      damage: this.bulletDamage,
      isEnemy: true,
      texKey: 'bullet_laser',
      style: this.bulletStyle
    }
    gm.addChild(bullet)
  }

  _die() {
    if (this._dead) return
    super._die()
  }
}
