import { Node } from '/engine/Node.js'

function worldGravityY(scene) {
  return Number(scene?.physics?.world?.gravity?.y ?? 300)
}
function round(value) {
  return Math.round(value * 100) / 100
}

export default class FruitHalf extends Node {
  ready() {
    this.fruitType = String(this.config.fruitType || 'apple')
    this.side = String(this.config.side || 'left')
    // radius here is the source whole-fruit radius (reporting field, decoupled
    // from this half's own collider radius); GameController forwards it every
    // spawn, so a missing/non-finite value means an upstream bug, not a
    // legitimate default.
    this.radius = Number(this.config.radius)
    if (!Number.isFinite(this.radius)) throw new Error('FruitHalf: config.radius missing; GameController must forward the source fruit radius')
    this.spin = Number(this.config.spin || 0)
    this.weight = Number(this.config.weight || 1)
    this.cleanupMargin = Number(this.config.cleanupMargin || 140)
    this.age = 0

    // ttl is single-declared in the per-type .node.json template (Self Check
    // C3): no script default, so a stale literal here can never diverge from
    // the template's authoritative value.
    this.ttl = Number(this.config.ttl)
    if (!Number.isFinite(this.ttl)) throw new Error('FruitHalf: config.ttl missing; declare it in the .node.json template')
    if (!Number.isFinite(this.config.depth)) throw new Error('FruitHalf: config.depth missing; declare it in the .node.json template')
    if (!Number.isFinite(this.config.tiltAngle)) throw new Error('FruitHalf: config.tiltAngle missing; declare it in the .node.json template')
    // popGravityBoost is shared with GameController.gravitySummary() and is
    // only authoritatively declared in fruit-roster.json; the half template
    // itself never carries a default, so GameController must forward it.
    if (!Number.isFinite(this.config.popGravityBoost)) throw new Error('FruitHalf: config.popGravityBoost missing; GameController must forward fruit-roster.json halfPopGravityBoost')

    this.setupVisual()
    this.setupPhysics()
  }

  update(dt) {
    this.age += dt
    const obj = this.getVisualObject()
    if (obj) obj.rotation += this.spin * dt
    if (this.age > this.ttl || this.isOffscreen()) this.removeSelf()
  }

  setupVisual() {
    const visual = this.getVisualObject()
    if (!visual) return
    // Side-driven texture swap is a legitimate runtime exception (approved):
    // left/right is decided at spawn time, not a static size/collider fact.
    if (typeof visual.setTexture === 'function' && this.config.texture && this.scene.textures.exists(this.config.texture)) {
      visual.setTexture(this.config.texture)
    }
    // Size/collider are declared by this per-type .node.json template; no
    // script override needed. Depth and tilt have no native schema field, so
    // they are read from config (declared once per template).
    if (typeof visual.setDepth === 'function') visual.setDepth(this.config.depth)
    visual.rotation = (this.side === 'left' ? -1 : 1) * Number(this.config.tiltAngle)
  }

  setupPhysics() {
    const body = this.gameObject?.body
    if (!body) return
    // Collider radius is declared by the .node.json template; only runtime
    // motion facts (gravity/velocity) are set here.
    if (typeof body.setAllowGravity === 'function') body.setAllowGravity(true)
    if (typeof body.setGravityY === 'function') body.setGravityY((this.weight - 1) * worldGravityY(this.scene) + Number(this.config.popGravityBoost))
    if (typeof body.setVelocity === 'function') {
      const vx = Number(this.config.velocityX)
      const vy = Number(this.config.velocityY)
      if (!Number.isFinite(vx) || !Number.isFinite(vy)) throw new Error('FruitHalf: config.velocityX/velocityY missing; GameController must forward computed pop velocity')
      body.setVelocity(vx, vy)
    }
  }

  isOffscreen() {
    const margin = this.cleanupMargin
    const width = Number(this.scene.scale?.width || this.scene.game?.config?.width || 960)
    const height = Number(this.scene.scale?.height || this.scene.game?.config?.height || 540)
    return this.x < -margin || this.x > width + margin || this.y > height + margin
  }

  get x() {
    return this.gameObject?.x ?? Number(this.config.x || 0)
  }

  get y() {
    return this.gameObject?.y ?? Number(this.config.y || 0)
  }

  textureKey() {
    return String(this.getVisualObject()?.texture?.key || this.config.texture || '')
  }

  runtimeState() {
    const body = this.gameObject?.body
    const bodyGravityY = round(body?.gravity?.y ?? 0)
    const worldY = round(worldGravityY(this.scene))
    const fallAccelerationY = round(worldY + bodyGravityY)
    return {
      fruitType: this.fruitType,
      side: this.side,
      radius: this.radius,
      weight: this.weight,
      age: round(this.age),
      ttl: this.ttl,
      spin: round(this.spin),
      texture: this.textureKey(),
      gravity: {
        worldY,
        bodyY: bodyGravityY,
        totalY: fallAccelerationY,
      },
      fallAccelerationY,
      velocity: {
        vx: round(body?.velocity?.x ?? 0),
        vy: round(body?.velocity?.y ?? 0),
      },
    }
  }
}
