import { Node } from '/engine/Node.js'

export default class OneShotFx extends Node {
  ready() {
    this.kind = this.config.kind
    this.lifetime = Number(this.config.lifetime) || 0
    this.initialLifetime = this.lifetime
    this.maxLifetime = Math.max(this.lifetime, Number(this.config.maxLifetime) || 0)
    this.baseAlpha = Number.isFinite(this.config.alpha) ? this.config.alpha : 1
    const facing = Number(this.config.facing) || 1
    this.visualObject?.setFlipX?.(facing < 0)
    this.visualObject?.setAlpha?.(this.baseAlpha)
    this.playAnim(this.kind, { restart: true })
  }

  update(dt) {
    this.lifetime -= dt
    this.maxLifetime -= dt
    this.visualObject?.setAlpha?.(this.baseAlpha)
    if (this._isAnimationComplete() || this.maxLifetime <= 0) this.removeSelf()
  }

  _isAnimationComplete() {
    const player = this.animationPlayer
    if (!player?.currentClip) return this.lifetime <= 0
    const clip = player.currentClip
    if (clip.loop !== false) return this.lifetime <= 0
    const frames = Array.isArray(clip.frames) ? clip.frames : []
    if (frames.length <= 1) return true
    return player.isFinished?.() === true
  }

  runtimeState() {
    return {
      kind: this.kind,
      lifetime: this.lifetime,
      initialLifetime: this.initialLifetime,
      maxLifetime: this.maxLifetime,
      texture: this.animationPlayer?.currentClip?.source?.texture || null,
      displayWidth: this.visualObject?.displayWidth ?? null,
      displayHeight: this.visualObject?.displayHeight ?? null
    }
  }
}
