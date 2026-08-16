import Enemy from './Enemy.js'

// Jump state machine
const S = { IDLE: 0, WINDUP: 1, AIR: 2, LAND: 3 }

// Slime: hop toward player instead of smooth tracking
// Cycle: IDLE (rest) → WINDUP (crouch) → AIR (flying) → LAND (squash) → repeat
export default class SlimeEnemy extends Enemy {
  ready() {
    const c = this.config
    this.contactDamage = c.contactDamage || c.damage || 10
    this.jumpSpeed     = c.jumpSpeed || 220

    // engine creates gameObject from visual/collider defs
    this._baseScaleX = this.gameObject.scaleX
    this._baseScaleY = this.gameObject.scaleY
    this.gameObject.setDepth(7)

    this._initEnemy(c)
    this._attackCooldown = 0

    // State machine
    this._state = S.IDLE
    this._timer = 0.3 + Math.random() * 0.4  // stagger spawns
    this._jumpDirX = 1
    this._jumpDirY = 0
  }

  update(dt) {
    if (this._dead || !this.gameObject?.body?.enable) return
    this._tickHpBar()
    this._timer -= dt

    switch (this._state) {
      case S.IDLE:
        if (this._timer <= 0) this._enterWindup()
        break
      case S.WINDUP:
        if (this._timer <= 0) this._enterAir()
        break
      case S.AIR: {
        // Show rising frame first half, falling frame second half
        const progress = 1 - this._timer / 0.5
        this._setFrame(progress < 0.5 ? 'jump_2' : 'jump_3')
        if (this._timer <= 0) this._enterLand()
        break
      }
      case S.LAND:
        if (this._timer <= 0) this._enterIdle()
        break
    }

    this._attackCooldown = Math.max(0, this._attackCooldown - dt)
  }

  _enterIdle() {
    this._state = S.IDLE
    this._timer = 0.6
    this.gameObject.body.setVelocity(0, 0)
    this._setFrame('jump_0')
  }

  _enterWindup() {
    this._state = S.WINDUP
    this._timer = 0.2
    this.gameObject.body.setVelocity(0, 0)
    this._setFrame('jump_1')
    // Lock jump direction toward player
    const players = this.findByTag('player')
    if (players.length > 0 && players[0].gameObject) {
      const angle = Phaser.Math.Angle.Between(
        this.gameObject.x, this.gameObject.y,
        players[0].gameObject.x, players[0].gameObject.y
      )
      this._jumpDirX = Math.cos(angle)
      this._jumpDirY = Math.sin(angle)
      if (typeof this.gameObject?.setFlipX === 'function') this.gameObject.setFlipX(this._jumpDirX < 0)
    }
  }

  _enterAir() {
    this._state = S.AIR
    this._timer = 0.5
    this.gameObject.body.setVelocity(this._jumpDirX * this.jumpSpeed, this._jumpDirY * this.jumpSpeed)
    this._setFrame('jump_2')
  }

  _enterLand() {
    this._state = S.LAND
    this._timer = 0.2
    this.gameObject.body.setVelocity(0, 0)
    this._setFrame('jump_4')
  }

  _setFrame(frame) {
    if (typeof this.gameObject?.setTexture === 'function') this.gameObject.setTexture('slime_jump', frame)
  }

  onContactPlayer(player) {
    if (this._dead || this._attackCooldown > 0) return
    this._attackCooldown = 0.5
    player.takeDamage(this.contactDamage)
  }

  _die() {
    if (this._dead) return
    if (typeof this.gameObject?.setTexture === 'function') this.gameObject.setTexture('slime_die')
    if (typeof this.gameObject?.setScale === 'function') this.gameObject.setScale(this._baseScaleX, this._baseScaleY)
    super._die()
  }
}
