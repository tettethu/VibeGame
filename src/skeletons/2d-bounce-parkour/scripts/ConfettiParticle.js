import { Node } from '/engine/Node.js'

/**
 * Short-lived confetti particle. Spawned via instantiate() at balloon-pop /
 * goal-reached moments. Picks a random frame from config.frameNames, fires off
 * in a random direction with upward bias + gravity, fades alpha over lifetime,
 * removes self when lifetime expires. No collider — pure visual.
 */
export default class ConfettiParticle extends Node {
  ready() {
    const c = this.config || {}
    const frames = c.frameNames || []
    if (this.gameObject?.setFrame && frames.length > 0) {
      const frame = frames[Math.floor(Math.random() * frames.length)]
      this.gameObject.setFrame(frame)
      // setFrame resets width via setSizeToFrame — re-assert display size.
      const size = c.displaySize
      this.gameObject.displayWidth = size
      this.gameObject.displayHeight = size
    }
    const angle = Math.random() * Math.PI * 2
    const speed = c.speedMin + Math.random() * (c.speedMax - c.speedMin)
    this._vx = Math.cos(angle) * speed
    this._vy = Math.sin(angle) * speed - c.upBias
    this._gravity = c.gravity
    this._life = c.lifetime
    this._t = 0
    this._rot = (Math.random() - 0.5) * 12
    if (this.gameObject) this.gameObject.depth = 50
  }

  update(dt) {
    if (!this.gameObject) return
    this._t += dt
    this._vy += this._gravity * dt
    this.gameObject.x += this._vx * dt
    this.gameObject.y += this._vy * dt
    this.gameObject.rotation += this._rot * dt
    this.gameObject.alpha = Math.max(0, 1 - this._t / this._life)
    if (this._t >= this._life) this.removeSelf()
  }
}
