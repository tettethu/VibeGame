import Enemy from './Enemy.js'

// State machine
const S = { EMERGING: 0, ACTIVE: 1 }

// SkeletonHand: slow melee enemy with emergence animation
export default class SkeletonHandEnemy extends Enemy {
  ready() {
    const c = this.config
    this.contactDamage = c.contactDamage || c.damage || 12
    this.attackInterval = c.attackInterval || 2.5
    this.attackRange = c.attackRange || 80

    this.gameObject.setDepth(7)
    this._initEnemy(c)
    this._attackCooldown = 0
    this._attacking = false

    // State machine
    this._state = S.EMERGING
    this._emergeTimer = 1.0
    this._emergeFrameIndex = 0
    this._emergeFrameTimer = 0
    this._setFrame('emerge_0')
  }

  update(dt) {
    if (this._dead) return
    this._tickHpBar()

    switch (this._state) {
      case S.EMERGING:
        this._updateEmerging(dt)
        break
      case S.ACTIVE:
        this._updateActive(dt)
        break
    }
  }

  _updateEmerging(dt) {
    this._emergeTimer -= dt
    this._emergeFrameTimer += dt

    // Frame switch every 0.25s: 0 -> 1 -> 2 -> 3
    if (this._emergeFrameTimer >= 0.25) {
      this._emergeFrameTimer = 0
      this._emergeFrameIndex++
      if (this._emergeFrameIndex <= 3) {
        this._setFrame(`emerge_${this._emergeFrameIndex}`)
      }
    }

    // After 1.0s, enter ACTIVE
    if (this._emergeTimer <= 0) {
      this._enterActive()
    }
  }

  _enterActive() {
    this._state = S.ACTIVE
    this._setFrame('emerge_3')
  }

  _updateActive(dt) {
    this._attackCooldown = Math.max(0, this._attackCooldown - dt)

    const players = this.findByTag('player')
    if (players.length > 0 && players[0].gameObject) {
      const p = players[0].gameObject
      const dist = Phaser.Math.Distance.Between(
        this.gameObject.x, this.gameObject.y,
        p.x, p.y
      )

      if (dist <= this.attackRange && this._attackCooldown <= 0 && !this._attacking) {
        this._attack(players[0])
      }
    }
  }

  _attack(player) {
    this._attacking = true
    this._attackCooldown = this.attackInterval

    // Flash effect
    this.gameObject.setTint(0xffffff)
    this.scene.time.delayedCall(100, () => {
      if (this.gameObject && !this._dead) {
        this.gameObject.clearTint()
        if (player && player.gameObject) {
          const dist = Phaser.Math.Distance.Between(
            this.gameObject.x, this.gameObject.y,
            player.gameObject.x, player.gameObject.y
          )
          if (dist <= this.attackRange) {
            player.takeDamage(this.contactDamage)
          }
        }
      }
      this._attacking = false
    })
  }

  _setFrame(frame) {
    if (this.gameObject) this.gameObject.setTexture('sk_hand_emerge', frame)
  }

  onContactPlayer(player) {
    // No contact damage during EMERGING
    if (this._state === S.EMERGING) return
    // Damage handled by _attack() based on range
  }

  _die() {
    if (this._dead) return
    super._die()
  }
}
