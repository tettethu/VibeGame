import Enemy from './Enemy.js'

// Boss minion: simple chase + contact damage, no exp, no wave count
export default class WraithShardEnemy extends Enemy {
  ready() {
    const c = this.config
    this._isBossMinion = true
    this.speed = c.speed || 120
    this.contactDamage = c.contactDamage || 5
    this.contactCooldownTime = c.contactCooldown || 1.0
    this._contactCooldown = 0

    this.gameObject.setDepth(6)
    this.gameObject.setTint(0x44ddff)
    this._initEnemy(c)
  }

  update(dt) {
    if (this._dead) return
    this._tickHpBar()
    this._contactCooldown = Math.max(0, this._contactCooldown - dt)

    const player = this._getPlayer()
    if (!player) return

    const angle = Phaser.Math.Angle.Between(
      this.gameObject.x, this.gameObject.y, player.x, player.y
    )
    this.gameObject.body.setVelocity(
      Math.cos(angle) * this.speed,
      Math.sin(angle) * this.speed
    )
  }

  onContactPlayer(player) {
    if (this._dead || this._contactCooldown > 0) return
    if (player._invincible || player._rolling || (player._rollGraceTimer && player._rollGraceTimer > 0)) return
    this._contactCooldown = this.contactCooldownTime
    player.takeDamage(this.contactDamage)
  }

  _getPlayer() {
    const players = this.findByTag('player')
    if (players.length === 0 || !players[0].gameObject) return null
    return players[0].gameObject
  }
}
