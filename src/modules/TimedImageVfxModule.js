import { Node } from '/engine/Node.js'

/**
 * TimedImageVfxModule — a fire-and-forget transient sprite effect.
 *
 * Spawn it at a position (via instantiate of a .node.json template that sets
 * `script: "TimedImageVfxModule"`); over its lifetime `ttl` it autonomously
 * moves, spins, scales and fades, optionally swapping textures along a timeline,
 * then removes itself. It mutates no game state and fires no callbacks — it is a
 * pure one-way visual primitive. Use it for any short-lived effect: hit sparks,
 * dust, liquid splashes, explosions, pickup shines, score pops.
 *
 * Inputs (config on the instantiated node; x/y come from node placement):
 *   texture?: string                  single texture key
 *   textureSequence?: [{texture, at}] timeline of texture swaps (at = seconds;
 *                                     e.g. explosion frames at 0 / 0.14 / ...)
 *   ttl?: number = 0.55               lifetime in seconds (self-destroys after)
 *   width?: number, height?: number   base display size in px (default 64)
 *   velocityX?: number, velocityY?: number  drift in px/s (default 0)
 *   spin?: number = 0                 rotation in rad/s
 *   alphaStart?: number = 0.95, alphaEnd?: number = 0      fade tween
 *   scaleStart?: number = 1, scaleEnd?: number = 1         scale tween (multiplier)
 *   depth?: number = 95
 *   angle? / rotation? / flipX? / flipY?                    initial orientation
 *   kind?: string = 'vfx', label?: string                  free-form tags for runtimeState
 *
 * Output: the animated on-screen sprite, automatic removeSelf() at ttl, and
 * runtimeState() = { kind, label, texture, age, ttl, width, height,
 * displayWidth, displayHeight, scaleStart, scaleEnd, velocity, spin, alpha,
 * done, missingTextureKeys } for runtime verification.
 *
 * The node template must carry an image `visual` so there is a game object to
 * drive; the module retextures / resizes it from config.
 */

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value))
}

function lerp(a, b, t) {
  return a + (b - a) * t
}

function round(value) {
  return Math.round(value * 100) / 100
}

function numberOr(value, fallback) {
  const n = Number(value)
  return Number.isFinite(n) ? n : fallback
}

export default class TimedImageVfxModule extends Node {
  ready() {
    this.kind = String(this.config.kind || 'vfx')
    this.label = this.config.label != null ? String(this.config.label) : null
    this.age = 0
    this.ttl = Math.max(0.05, numberOr(this.config.ttl, 0.55))
    this.done = false
    this.textureSequence = this.normalizeSequence(this.config.textureSequence)
    this.texture = this.textureSequence[0]?.texture || String(this.config.texture || '')
    this.currentTexture = null
    this.missingTextureKeys = []
    this.velocityX = numberOr(this.config.velocityX, 0)
    this.velocityY = numberOr(this.config.velocityY, 0)
    this.spin = numberOr(this.config.spin, 0)
    this.alphaStart = clamp(numberOr(this.config.alphaStart, 0.95), 0, 1)
    this.alphaEnd = clamp(numberOr(this.config.alphaEnd, 0), 0, 1)
    this.scaleStart = Math.max(0.01, numberOr(this.config.scaleStart, 1))
    this.scaleEnd = Math.max(0.01, numberOr(this.config.scaleEnd, 1))
    this.width = Math.max(1, numberOr(this.config.width, this.getVisualObject()?.displayWidth || 64))
    this.height = Math.max(1, numberOr(this.config.height, this.getVisualObject()?.displayHeight || 64))

    this.setupVisual()
  }

  update(dt) {
    if (this.done) return
    this.age += dt
    const t = clamp(this.age / this.ttl, 0, 1)
    this.applySequence()
    this.applyMotion(dt)
    this.applyTween(t)
    if (this.age >= this.ttl) {
      this.done = true
      this.removeSelf()
    }
  }

  setupVisual() {
    const visual = this.getVisualObject()
    if (!visual) return
    this.applyTexture(this.texture)
    if (typeof visual.setDepth === 'function') visual.setDepth(numberOr(this.config.depth, 95))
    if (typeof visual.setAlpha === 'function') visual.setAlpha(this.alphaStart)
    else visual.alpha = this.alphaStart
    if (typeof visual.setDisplaySize === 'function') visual.setDisplaySize(this.width * this.scaleStart, this.height * this.scaleStart)
    else {
      visual.displayWidth = this.width * this.scaleStart
      visual.displayHeight = this.height * this.scaleStart
    }
    if (this.config.angle !== undefined) visual.angle = numberOr(this.config.angle, 0)
    if (this.config.rotation !== undefined) visual.rotation = numberOr(this.config.rotation, 0)
    if (this.config.flipX !== undefined && typeof visual.setFlipX === 'function') visual.setFlipX(Boolean(this.config.flipX))
    if (this.config.flipY !== undefined && typeof visual.setFlipY === 'function') visual.setFlipY(Boolean(this.config.flipY))
  }

  normalizeSequence(sequence) {
    if (!Array.isArray(sequence)) return []
    return sequence
      .map(item => ({ texture: String(item?.texture || ''), at: Math.max(0, numberOr(item?.at, 0)) }))
      .filter(item => item.texture)
      .sort((a, b) => a.at - b.at)
  }

  applySequence() {
    let texture = this.texture
    for (const item of this.textureSequence) {
      if (this.age >= item.at) texture = item.texture
    }
    this.applyTexture(texture)
  }

  applyTexture(texture) {
    if (!texture || texture === this.currentTexture) return
    if (!this.scene?.textures?.exists(texture)) {
      this.noteMissingTexture(texture)
      return
    }
    const visual = this.getVisualObject()
    if (visual && typeof visual.setTexture === 'function') {
      visual.setTexture(texture)
      this.currentTexture = texture
      this.texture = texture
    }
  }

  applyMotion(dt) {
    const visual = this.getVisualObject()
    if (!visual) return
    visual.x += this.velocityX * dt
    visual.y += this.velocityY * dt
    if (this.spin) visual.rotation += this.spin * dt
  }

  applyTween(t) {
    const visual = this.getVisualObject()
    if (!visual) return
    const alpha = lerp(this.alphaStart, this.alphaEnd, t)
    const scale = lerp(this.scaleStart, this.scaleEnd, t)
    if (typeof visual.setAlpha === 'function') visual.setAlpha(alpha)
    else visual.alpha = alpha
    if (typeof visual.setDisplaySize === 'function') visual.setDisplaySize(this.width * scale, this.height * scale)
    else {
      visual.displayWidth = this.width * scale
      visual.displayHeight = this.height * scale
    }
  }

  noteMissingTexture(texture) {
    if (!this.missingTextureKeys.includes(texture)) this.missingTextureKeys.push(texture)
  }

  runtimeState() {
    const visual = this.getVisualObject()
    return {
      kind: this.kind,
      label: this.label,
      texture: this.currentTexture || this.texture,
      age: round(this.age),
      ttl: this.ttl,
      width: this.width,
      height: this.height,
      displayWidth: round(visual?.displayWidth ?? this.width),
      displayHeight: round(visual?.displayHeight ?? this.height),
      scaleStart: round(this.scaleStart),
      scaleEnd: round(this.scaleEnd),
      velocity: {
        vx: round(this.velocityX),
        vy: round(this.velocityY),
      },
      spin: round(this.spin),
      alpha: round(visual?.alpha ?? this.alphaEnd),
      done: this.done,
      missingTextureKeys: [...this.missingTextureKeys],
    }
  }
}
