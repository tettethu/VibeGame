import Enemy from './Enemy.js'

// Bat: fast flying enemy that chases player
export default class BatEnemy extends Enemy {
  ready() {
    const c = this.config
    this.contactDamage = c.contactDamage || c.damage || 8
    this.speed = c.speed || 150

    this.gameObject.setDepth(7)
    this._initEnemy(c)
    this._attackCooldown = 0
    this.playAnim('flap')
  }

  update(dt) {
    if (this._dead || !this.gameObject?.body?.enable) return
    this._tickHpBar()

    const players = this.findByTag('player')
    if (players.length > 0 && players[0].gameObject) {
      const p = players[0].gameObject
      const angle = Phaser.Math.Angle.Between(
        this.gameObject.x, this.gameObject.y,
        p.x, p.y
      )
      this.gameObject.body.setVelocity(
        Math.cos(angle) * this.speed,
        Math.sin(angle) * this.speed
      )
      this.gameObject.setFlipX(p.x < this.gameObject.x)
    }

    this._attackCooldown = Math.max(0, this._attackCooldown - dt)
  }

  onContactPlayer(player) {
    if (this._dead || this._attackCooldown > 0) return
    this._attackCooldown = 0.5
    player.takeDamage(this.contactDamage)
  }

  _die() {
    if (this._dead) return
    super._die()
  }
}
