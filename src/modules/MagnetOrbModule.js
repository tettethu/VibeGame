import { Node } from '/engine/Node.js'

/**
 * MagnetOrbModule — collectible orb that gravitates toward a target tag (default: player).
 *
 * Verified for roguelike dungeon pickups where dropped rewards accelerate toward the player
 * after entering a magnet range.
 *
 * The orb only handles MAGNETISM (movement toward target). Pickup detection is the caller's job:
 * watch for overlap with the orb's pickup tag, grant `orb.value`, then `orb.destroy()`.
 *
 * Config (all optional except `visual`):
 *   visual: required. One of two shapes:
 *     { type: 'circle', radius: number, color: number, glowRadius?: number, glowColor?: number, glowAlpha?: number }
 *     { type: 'image',  texture: string, displaySize?: [w, h] }
 *   value:        number — resource amount (default 1). Exposed as `this.value` for caller's pickup handler.
 *   pickupTag:    string — tag to add for overlap detection (default 'magnet_orb').
 *                          Caller queries `findByTag(pickupTag)` and checks overlap.
 *   targetTag:    string — tag of the magnet target (default 'player').
 *   magnetRange:  number — pixel distance within which gravity engages (default 150).
 *   maxSpeed:     number — px/s cap once magnetized (default 600).
 *   acceleration: number — px/s² ramp-up while magnetized (default 800).
 *   depth:        number — render depth (default 2).
 *   x, y:         number — spawn position (default 0,0).
 *
 * Public API:
 *   this.value — resource amount, read by pickup handler.
 *   destroy()  — call from pickup handler after granting the resource.
 *
 * Example scene JSON instantiation (typically via `instantiate()` from a runtime spawner):
 *   {
 *     "name": "ExpOrb",
 *     "script": "MagnetOrbModule",
 *     "config": {
 *       "visual":   { "type": "circle", "radius": 6, "color": 0xaaff00, "glowRadius": 9, "glowColor": 0x88ff00, "glowAlpha": 0.3 },
 *       "pickupTag": "exp_orb",
 *       "value":    10,
 *       "x": 200, "y": 300
 *     }
 *   }
 */
export default class MagnetOrbModule extends Node {
  ready() {
    const c = this.config || {}
    const x = c.x || 0
    const y = c.y || 0

    this.value = c.value ?? 1
    this.tags = [c.pickupTag || 'magnet_orb']
    this._targetTag = c.targetTag || 'player'
    this._magnetRange = c.magnetRange ?? 150
    this._maxSpeed = c.maxSpeed ?? 600
    this._acceleration = c.acceleration ?? 800
    this._speed = 0

    const v = c.visual
    if (!v) throw new Error('MagnetOrbModule: config.visual is required')

    if (v.type === 'circle') {
      this.gameObject = this.scene.add.circle(x, y, v.radius, v.color, 1)
      if (v.glowRadius && v.glowColor !== undefined) {
        this._glow = this.scene.add.circle(x, y, v.glowRadius, v.glowColor, v.glowAlpha ?? 0.3).setDepth(1)
      }
    } else if (v.type === 'image') {
      this.gameObject = this.scene.add.image(x, y, v.texture)
      if (v.displaySize) this.gameObject.setDisplaySize(v.displaySize[0], v.displaySize[1])
    } else {
      throw new Error(`MagnetOrbModule: unknown visual.type "${v.type}"`)
    }

    this.scene.physics.add.existing(this.gameObject, true)
    this.gameObject.setDepth(c.depth ?? 2)
  }

  update(dt) {
    const target = this.findByTag(this._targetTag)[0]
    if (!target?.gameObject || !this.gameObject) return

    const dx = target.gameObject.x - this.gameObject.x
    const dy = target.gameObject.y - this.gameObject.y
    const dist = Math.sqrt(dx * dx + dy * dy)
    if (dist < 0.001) return

    if (dist < this._magnetRange) {
      this._speed = Math.min(this._maxSpeed, this._speed + this._acceleration * dt)
      const step = this._speed * dt
      const nx = dx / dist
      const ny = dy / dist
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
