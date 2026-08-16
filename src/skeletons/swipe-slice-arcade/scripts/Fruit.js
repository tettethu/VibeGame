import { Node } from '/engine/Node.js'

function worldGravityY(scene) {
  return Number(scene?.physics?.world?.gravity?.y ?? 300)
}
function round(value) {
  return Math.round(value * 100) / 100
}

export default class Fruit extends Node {
  ready() {
    this.fruitType = String(this.config.fruitType || 'apple')
    this.label = String(this.config.label || this.fruitType)
    this.score = Number(this.config.score || 0)
    this.spawnIndex = Number(this.config.spawnIndex || 0)
    this.weight = Number(this.config.weight || 1)
    this.missY = Number(this.config.missY || 620)
    this.cleanupMargin = Number(this.config.cleanupMargin || 120)
    this.sliced = Boolean(this.config.sliced)
    this.missed = false
    this.hasEnteredPlayfield = false
    this.readableTime = 0
    // Fairness window is real gameplay tuning read once here; the per-type
    // .node.json template is its sole declared source, no script default.
    this.minReadableTimeForMiss = Number(this.config.minReadableTimeForMiss)
    if (!Number.isFinite(this.minReadableTimeForMiss)) throw new Error('Fruit: config.minReadableTimeForMiss missing; declare it in the .node.json template')
    this.controller = this.findController()

    this.setupVisual()
    this.setupPhysics()

    // Radius is consumed from the already-built declarative collider (this
    // per-type .node.json template's collider.radius), never re-derived.
    // NOTE: Arcade circle bodies store body.radius pre-scale (Phaser never
    // corrects it for scaleX/scaleY); body.halfWidth is the value Phaser
    // itself recomputes in world space (sourceWidth * scaleX / 2), so it is
    // the only body property that matches the declared world-space radius.
    this.radius = this.gameObject.body.halfWidth
    if (!Number.isFinite(this.radius)) throw new Error('Fruit: collider body has no finite radius; check .node.json collider.radius')
  }

  update(dt = 0) {
    if (this.sliced || this.missed) return
    if (this.isInReadablePlayfield()) {
      this.hasEnteredPlayfield = true
      this.readableTime += Math.max(0, Number(dt || 0))
    }
    if (this.y > this.missY) {
      this.missed = true
      if (this.readableTime >= this.minReadableTimeForMiss) this.controller?.onFruitMiss?.(this)
      this.removeSelf()
    }
  }

  slice(meta = {}) {
    if (this.sliced || this.missed) return false
    this.sliced = true
    this.controller = meta.controller || this.controller || this.findController()
    this.controller?.onFruitSliced?.(this, meta)
    this.removeSelf()
    return true
  }

  setupVisual() {
    const visual = this.getVisualObject()
    if (!visual) return
    // Texture and size are declared by this fruit type's own .node.json
    // template (visual.texture / visual.width / visual.height); no script
    // override needed. Depth has no native schema field, so it is read from
    // config (declared once per template, single reader, no fallback).
    if (!Number.isFinite(this.config.depth)) throw new Error('Fruit: config.depth missing; declare it in the .node.json template')
    if (typeof visual.setDepth === 'function') visual.setDepth(this.config.depth)
  }

  setupPhysics() {
    const body = this.gameObject?.body
    if (!body) return
    // Collider radius is declared by the .node.json template; only runtime
    // motion facts (gravity/velocity) are set here.
    if (typeof body.setAllowGravity === 'function') body.setAllowGravity(true)
    if (typeof body.setGravityY === 'function') body.setGravityY((this.weight - 1) * worldGravityY(this.scene))
    if (typeof body.setVelocity === 'function') {
      // GameController always forwards a computed launch velocity per spawn;
      // a missing/non-finite value is an upstream bug, not a legitimate
      // default, so this fails loudly instead of silently falling back.
      const vx = Number(this.config.velocityX)
      const vy = Number(this.config.velocityY)
      if (!Number.isFinite(vx) || !Number.isFinite(vy)) throw new Error('Fruit: config.velocityX/velocityY missing; GameController must forward computed launch velocity')
      body.setVelocity(vx, vy)
    }
  }

  findController() {
    if (this.parent?.onFruitSliced) return this.parent
    return this.findByTag('game')[0] || null
  }

  get x() {
    return this.gameObject?.x ?? Number(this.config.x || 0)
  }

  get y() {
    return this.gameObject?.y ?? Number(this.config.y || 0)
  }

  isInReadablePlayfield() {
    const width = Number(this.scene.scale?.width || this.scene.game?.config?.width || 960)
    const height = Number(this.scene.scale?.height || this.scene.game?.config?.height || 540)
    return (
      this.x >= this.radius &&
      this.x <= width - this.radius &&
      this.y >= this.radius &&
      this.y <= height - this.radius
    )
  }

  textureKey() {
    return String(this.getVisualObject()?.texture?.key || this.config.wholeTexture || '')
  }

  runtimeState() {
    const body = this.gameObject?.body
    const bodyGravityY = round(body?.gravity?.y ?? 0)
    const worldY = round(worldGravityY(this.scene))
    const fallAccelerationY = round(worldY + bodyGravityY)
    return {
      fruitType: this.fruitType,
      label: this.label,
      sliced: this.sliced,
      missed: this.missed,
      hasEnteredPlayfield: this.hasEnteredPlayfield,
      readableTime: round(this.readableTime),
      minReadableTimeForMiss: this.minReadableTimeForMiss,
      radius: this.radius,
      score: this.score,
      spawnIndex: this.spawnIndex,
      weight: this.weight,
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
