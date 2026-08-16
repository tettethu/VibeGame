import Enemy from './Enemy.js'
import Bullet from './Bullet.js'
import { generateId } from '/engine/Node.js'

// Skeleton archer: holds position, shoots at the player on a timer.
export default class ArcherEnemy extends Enemy {
  ready() {
    const c = this.config
    this.shootInterval = c.shootInterval || 2.0
    this.bulletSpeed = c.bulletSpeed || 200
    this.bulletDamage = c.bulletDamage || 15
    this.bulletStyle = c.bulletStyle || 'archer'

    // engine creates gameObject from visual/collider defs
    this._baseScaleX = this.gameObject.scaleX
    this._baseScaleY = this.gameObject.scaleY
    this.gameObject.setDepth(7)

    this._initEnemy(c)
    this._shootTimer = this.shootInterval * 0.5
    this._attackTimer = 0
  }

  update(dt) {
    if (this._dead || !this.gameObject?.body?.enable) return
    this._tickHpBar()

    this._shootTimer -= dt
    if (this._shootTimer <= 0) {
      this._shootTimer = this.shootInterval
      this._shoot()
    }

    // Restore the idle texture after the attack frame
    if (this._attackTimer > 0) {
      this._attackTimer -= dt
      if (this._attackTimer <= 0) this.gameObject.setTexture('archer_idle')
    }

    // Face the player
    const players = this.findByTag('player')
    if (players.length > 0 && players[0].gameObject) {
      const px = players[0].gameObject.x
      this.gameObject.setFlipX(px < this.gameObject.x)
    }
  }

  _shoot() {
    const players = this.findByTag('player')
    if (players.length === 0) return
    const p = players[0]
    if (!p.gameObject) return

    const gm = this.findByTag('game_manager')[0]
    if (!gm) return

    this.gameObject.setTexture('archer_attack')
    this._attackTimer = 0.3

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
      style: this.bulletStyle
    }
    gm.addChild(bullet)
  }

  _die() {
    if (this._dead) return
    this.gameObject.setTexture('archer_die')
    super._die()
  }
}
