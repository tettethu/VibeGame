import { Node } from '/engine/Node.js'

// Exp orb: homes in on the player within 150px, collected on contact
export default class ExpOrb extends Node {
  ready() {
    const c = this.config
    const orbCfg = this.findByTag('game_manager')[0]?.elementsConfig?.expOrb || {}
    this.expValue = c.expValue || 10
    const x = c.x || 0
    const y = c.y || 0
    this.tags = ['exp_orb']
    this._radius = orbCfg.radius
    this._glowRadius = orbCfg.glowRadius
    this._magnetRange = orbCfg.magnetRange
    this._maxSpeed = orbCfg.maxSpeed
    this._acceleration = orbCfg.acceleration

    this.gameObject = this.scene.add.circle(x, y, this._radius, 0xaaff00, 1)
    this._glow = this.scene.add.circle(x, y, this._glowRadius, 0x88ff00, 0.3).setDepth(1)
    this.scene.physics.add.existing(this.gameObject, true)
    this.gameObject.setDepth(2)
    this._speed = 0
  }

  update(dt) {
    const player = this.findByTag('player')[0]
    if (!player?.gameObject || !this.gameObject) return

    const dx = player.gameObject.x - this.gameObject.x
    const dy = player.gameObject.y - this.gameObject.y
    const dist = Math.sqrt(dx * dx + dy * dy)

    if (dist < this._magnetRange) {
      this._speed = Math.min(this._maxSpeed, this._speed + this._acceleration * dt)
      const step = this._speed * dt
      const nx = dx / dist, ny = dy / dist
      const newX = this.gameObject.x + nx * step
      const newY = this.gameObject.y + ny * step
      this.gameObject.setPosition(newX, newY)
      if (this._glow) this._glow.setPosition(newX, newY)
    } else {
      this._speed = 0
    }
  }

  destroy() {
    if (this._glow) { this._glow.destroy(); this._glow = null }
    if (this.gameObject) { this.gameObject.destroy(); this.gameObject = null }
  }
}
