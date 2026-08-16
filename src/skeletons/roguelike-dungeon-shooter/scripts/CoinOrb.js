import { Node } from '/engine/Node.js'

// Coin orb: dropped on kill, magnet-collected
export default class CoinOrb extends Node {
  ready() {
    const c = this.config
    const orbCfg = this.findByTag('game_manager')[0]?.elementsConfig?.expOrb || {}
    this.coinValue = c.coinValue || 1
    const x = c.x || 0
    const y = c.y || 0
    this.tags = ['coin_orb']
    this._radius = orbCfg.radius || 6
    this._glowRadius = orbCfg.glowRadius || 9
    this._magnetRange = orbCfg.magnetRange || 150
    this._maxSpeed = orbCfg.maxSpeed || 600
    this._acceleration = orbCfg.acceleration || 800

    this.gameObject = this.scene.add.image(x, y, 'icon_coin')
    this.gameObject.setDisplaySize(16, 16)
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
    if (dist < 0.001) return

    if (dist < this._magnetRange) {
      this._speed = Math.min(this._maxSpeed, this._speed + this._acceleration * dt)
      const step = this._speed * dt
      const nx = dx / dist, ny = dy / dist
      const newX = this.gameObject.x + nx * step
      const newY = this.gameObject.y + ny * step
      this.gameObject.setPosition(newX, newY)
    } else {
      this._speed = 0
    }
  }

  destroy() {
    if (this.gameObject) { this.gameObject.destroy(); this.gameObject = null }
  }
}
