import { Node } from '/engine/Node.js'

export default class PlayerCharacter extends Node {
  ready() {
    this._destroyed = false
  }

  destroy() { this._destroyed = true }

  /** Trigger FSM animation and callback after the engine AnimationPlayer finishes. */
  triggerAnim(animName, callback) {
    let called = false

    const done = () => {
      if (called || this._destroyed) return
      called = true
      if (animName !== 'die') {
        this.playAnim?.('idle', { restart: true, force: true })
        if (this.animator) this.animator.currentState = 'idle'
      }
      callback?.()
    }

    const played = this.playAnim?.(animName, { restart: true, force: true })
    if (this.animator) this.animator.currentState = animName
    if (!played) {
      if (!played) callback?.()
      return
    }

    const tick = () => {
      if (called || this._destroyed) return
      const currentClip = this.animationPlayer?.getCurrentClip?.()
      if (currentClip === animName && this.animationPlayer?.isFinished?.()) {
        done()
        return
      }

      this.scene.time.delayedCall(16, tick)
    }
    this.scene.time.delayedCall(16, tick)
  }

  getHeadPosition() {
    const go = this.getVisualObject()
    if (!go) return { x: 220, y: 160 }
    return { x: go.x, y: go.y - go.displayHeight - 30 }
  }

  runtimeState() {
    return { animState: this.animator?.getState() ?? this.getCurrentAnim?.() ?? 'idle' }
  }
}
