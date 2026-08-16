import { Node } from '/engine/Node.js'

function worldGravityY(scene) {
  return Number(scene?.physics?.world?.gravity?.y ?? 300)
}
function round(value) {
  return Math.round(value * 100) / 100
}

export default class Bomb extends Node {
  ready() {
    this.weight = Number(this.config.weight || 1.1)
    this.missY = Number(this.config.missY || 620)
    this.cleanupMargin = Number(this.config.cleanupMargin || 120)
    this.armed = this.config.armed !== false
    this.hit = false
    this.spin = Number(this.config.spin || 1.6)
    this.age = 0
    this.texture = String(this.config.texture || 'bomb_idle')
    this.warningTexture = String(this.config.warningTexture || 'bomb_warning')
    this.currentTexture = null
    this.controller = this.findController()
    if (!Number.isFinite(this.config.depth)) throw new Error('Bomb: config.depth missing; declare it in entities/bomb.node.json')
    if (!Number.isFinite(this.config.warningBlinkHz)) throw new Error('Bomb: config.warningBlinkHz missing; declare it in entities/bomb.node.json')

    this.setupVisual()
    this.setupPhysics()

    // Radius is consumed from the already-built declarative collider
    // (entities/bomb.node.json collider.radius), never re-derived.
    // NOTE: body.radius is Phaser's pre-scale storage (never corrected for
    // scaleX/scaleY); body.halfWidth is the world-space value Phaser itself
    // recomputes (sourceWidth * scaleX / 2), matching the declared radius.
    this.radius = this.gameObject.body.halfWidth
    if (!Number.isFinite(this.radius)) throw new Error('Bomb: collider body has no finite radius; check .node.json collider.radius')
  }

  update(dt) {
    this.age += dt
    const visual = this.getVisualObject()
    if (visual) {
      visual.rotation += this.spin * dt
      this.updateWarningTexture(visual)
    }
    if (!this.hit && this.y > this.missY) this.removeSelf()
  }

  hitBySlash(meta = {}) {
    if (!this.armed || this.hit) return false
    this.hit = true
    this.armed = false
    this.controller = meta.controller || this.controller || this.findController()
    this.controller?.onBombHit?.(this, meta)
    this.removeSelf()
    return true
  }

  setupVisual() {
    const visual = this.getVisualObject()
    if (!visual) return
    // Texture and size are declared by entities/bomb.node.json; no script
    // override needed. Depth has no native schema field, so it is read from
    // config (single declaration, single reader).
    this.applyTexture(visual, this.texture)
    if (typeof visual.setDepth === 'function') visual.setDepth(this.config.depth)
  }

  updateWarningTexture(visual) {
    const warningLoaded = this.scene.textures.exists(this.warningTexture)
    const nextTexture = warningLoaded && Math.floor(this.age * Number(this.config.warningBlinkHz)) % 2 === 1 ? this.warningTexture : this.texture
    this.applyTexture(visual, nextTexture)
  }

  applyTexture(visual, texture) {
    if (!texture || texture === this.currentTexture) return
    if (typeof visual.setTexture === 'function' && this.scene.textures.exists(texture)) {
      visual.setTexture(texture)
      this.currentTexture = texture
    }
  }

  setupPhysics() {
    const body = this.gameObject?.body
    if (!body) return
    // Collider radius is declared by entities/bomb.node.json; only runtime
    // motion facts (gravity/velocity) are set here.
    if (typeof body.setAllowGravity === 'function') body.setAllowGravity(true)
    if (typeof body.setGravityY === 'function') body.setGravityY((this.weight - 1) * worldGravityY(this.scene))
    if (typeof body.setVelocity === 'function') {
      const vx = Number(this.config.velocityX)
      const vy = Number(this.config.velocityY)
      if (!Number.isFinite(vx) || !Number.isFinite(vy)) throw new Error('Bomb: config.velocityX/velocityY missing; GameController must forward computed launch velocity')
      body.setVelocity(vx, vy)
    }
  }

  findController() {
    if (this.parent?.onBombHit) return this.parent
    return this.findByTag('game')[0] || null
  }

  get x() {
    return this.gameObject?.x ?? Number(this.config.x || 0)
  }

  get y() {
    return this.gameObject?.y ?? Number(this.config.y || 0)
  }

  runtimeState() {
    const body = this.gameObject?.body
    return {
      armed: this.armed,
      hit: this.hit,
      radius: this.radius,
      weight: this.weight,
      texture: this.currentTexture || this.texture,
      velocity: {
        vx: round(body?.velocity?.x ?? 0),
        vy: round(body?.velocity?.y ?? 0),
      },
    }
  }
}
