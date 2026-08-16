import { Node } from '/engine/Node.js'

/**
 * Balloon — sin-wave float + breath scaling.
 * Variants (red / blue / gold) share this script via config:
 *   variantKey: "red" | "blue" | "gold" — used to restore idle frame on reset()
 *   bounceMultiplier: applied to Hero bounceForce (read by Hero._tryStomp)
 *   displayWidth / displayHeight: rendered size (must match visual.width/height)
 *   popHideMs: delay between pop animation start and visible=false
 *
 * pop() plays the 4-frame pop clip (engine-driven via playAnim) and hides the
 * sprite after popHideMs. reset() restores idle frame + size + body for respawn.
 * Hero owns the stomp judgement (top-contact detection lives there).
 */
export default class Balloon extends Node {
  ready() {
    const c = this.config || {}
    this.floatPeriod = c.floatPeriod
    this.amplitude = c.amplitude
    this.breathPeriod = c.breathPeriod
    this.breathAmount = c.breathAmount
    this._phase = c.phase
    this.variantKey = c.variantKey || 'red'
    this.bounceMultiplier = (typeof c.bounceMultiplier === 'number') ? c.bounceMultiplier : 1.0
    this._displayW = c.displayWidth
    this._displayH = c.displayHeight
    this._popHideMs = c.popHideMs

    this._popped = false
    this._popping = false
    this._popTimer = null
    this._time = this._phase

    if (this.gameObject) {
      this._baseX = this.gameObject.x
      this._baseY = this.gameObject.y
    } else {
      this._baseX = c.x || 0
      this._baseY = c.y || 0
    }

    // Balloon is script-driven (sin float). Arcade body should NOT integrate or
    // write back to gameObject.y — overlap detection works fine without `moves`.
    // After respawn-time `body.updateFromGameObject()` jumps body.position by ~3
    // (gameObject was mid-sin, then snapped to baseY), Phaser's body integration
    // interpolates this delta over subsequent frames, fighting balloon.update()'s
    // per-frame y assignment and producing visible shake.
    if (this.gameObject?.body) this.gameObject.body.moves = false
  }

  pop() {
    if (this._popped) return
    this._popped = true
    this._popping = true
    if (this.gameObject?.body) this.gameObject.body.enable = false
    // Engine swaps texture to balloons_pop and walks frames.
    this.playAnim?.('pop', { restart: true })
    if (this._popTimer) {
      this._popTimer.remove(false)
      this._popTimer = null
    }
    this._popTimer = this.scene?.time?.delayedCall(this._popHideMs, () => {
      if (!this._popped) return
      if (this.gameObject) this.gameObject.visible = false
      this._popping = false
      this._popTimer = null
    }) || null
  }

  reset() {
    this._popped = false
    this._popping = false
    if (this._popTimer) {
      this._popTimer.remove(false)
      this._popTimer = null
    }
    this._time = this._phase
    if (!this.gameObject) return
    this.gameObject.visible = true
    this.gameObject.x = this._baseX
    this.gameObject.y = this._baseY
    // Restore idle frame from variantKey. setTexture resets width via setSizeToFrame,
    // so re-apply display size right after.
    this.gameObject.setTexture('balloons_idle', this.variantKey)
    if (this._displayW) this.gameObject.displayWidth = this._displayW
    if (this._displayH) this.gameObject.displayHeight = this._displayH
    // Stop residual pop animation so update's breathe sizing wins again.
    this.stopAnim?.()
    if (this.gameObject.body) {
      this.gameObject.body.enable = true
      this.gameObject.body.updateFromGameObject()
    }
  }

  destroy() {
    if (this._popTimer) {
      this._popTimer.remove(false)
      this._popTimer = null
    }
  }

  update(dt) {
    if (this._popped || !this.gameObject) return
    this._time += dt
    const yOff = Math.sin(this._time * Math.PI * 2 / this.floatPeriod) * this.amplitude
    const breath = 1 + Math.sin(this._time * Math.PI * 2 / this.breathPeriod) * this.breathAmount
    this.gameObject.x = this._baseX
    this.gameObject.y = this._baseY + yOff
    if (this._displayW) this.gameObject.displayWidth = this._displayW * breath
    if (this._displayH) this.gameObject.displayHeight = this._displayH * breath
    if (this.gameObject.body) this.gameObject.body.updateFromGameObject()
  }

  runtimeState() {
    return {
      alive: !this._popped,
      variant: this.variantKey,
      popping: this._popping,
    }
  }
}
