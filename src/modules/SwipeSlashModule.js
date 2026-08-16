import { Node } from '/engine/Node.js'

/**
 * SwipeSlashModule — runtime pointer-swipe slash.
 *
 * Bundles three things every swipe/slash/draw game needs:
 *   1. Pointer capture (down / move / up) into a per-swipe point path.
 *   2. A glowing vector trail rendered with Phaser Graphics (wide soft glow line
 *      + thin bright core), age-faded over `trailMs`. No sprite asset needed.
 *   3. Continuous SEGMENT-circle hit detection against tagged targets, with
 *      per-swipe dedup and per-category hit counts (combo).
 *
 * Why segment-based, not a per-frame point test: a fast pointer jumps a large
 * distance between two sampled frames, so a point-in-circle test on each sampled
 * position misses any target the path swept across (the "tunneling" problem).
 * Testing the line SEGMENT from the previous to the current pointer position
 * against each target circle catches them. It is cheap — one segment-to-center
 * distance per moved step, throttled by `minDistance`.
 *
 * Wire-up: add a node with `script: "SwipeSlashModule"` to the scene (no visual
 * needed). It finds a host node by tag (`config.hostTag`, default 'game') and
 * drives these OPTIONAL host hooks (each a no-op if the host omits it):
 *   host.canSlash() -> boolean          gate hit registration (e.g. only while playing)
 *   host.onSwipePointerDown(point)      pointer pressed (host may start/restart game)
 *   host.onSwipeStart(slash)            a new swipe began
 *   host.onSwipeHit(info)               one target hit: { category, target, slashId, count }
 *   host.onSwipeEnd(slash)              swipe released: { slashId, counts }
 * On each hit it also calls the TARGET's own method (`group.method`, e.g. 'slice'
 * / 'hitBySlash') with meta { controller: host, module, slashId, category, count,
 * counts }. A target is skipped if it exposes a truthy `sliced` / `missed` / `hit`
 * field or `armed === false`.
 *
 * The module registers itself on the host as `host.swipe` so the host can read
 * `activeSlashSummary()` (used in debug/runtime state).
 *
 * config: {
 *   hostTag?: string = 'game',
 *   minDistance?: number = 6,     // px before a new trail point / hit segment is taken
 *   hitPadding?: number = 7,      // added to every target radius for forgiveness
 *   trailMs?: number = 190,       // trail point lifetime and fade window
 *   depth?: number = 220,
 *   glowColor?: number = 0x8be9ff, glowWidth?: number = 10, glowAlpha?: number = 0.36,
 *   coreColor?: number = 0xffffff, coreWidth?: number = 3,  coreAlpha?: number = 0.9,
 *   groups?: Array<{ tag, method, category?, defaultRadius?, stopOnHit? }>
 *            = [{ tag: 'sliceable', method: 'slice', category: 'slice' }]
 * }
 * public: activeSlashSummary() -> { active, pointCount, counts } | null
 */

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value))
}

function numberOr(value, fallback) {
  const n = Number(value)
  return Number.isFinite(n) ? n : fallback
}

export default class SwipeSlashModule extends Node {
  ready() {
    this.hostTag = String(this.config.hostTag || 'game')
    this.minDistance = numberOr(this.config.minDistance, 6)
    this.hitPadding = numberOr(this.config.hitPadding, 7)
    this.trailMs = numberOr(this.config.trailMs, 190)
    this.depth = numberOr(this.config.depth, 220)
    this.glowColor = numberOr(this.config.glowColor, 0x8be9ff)
    this.glowWidth = numberOr(this.config.glowWidth, 10)
    this.glowAlpha = numberOr(this.config.glowAlpha, 0.36)
    this.coreColor = numberOr(this.config.coreColor, 0xffffff)
    this.coreWidth = numberOr(this.config.coreWidth, 3)
    this.coreAlpha = numberOr(this.config.coreAlpha, 0.9)
    this.groups = this.normalizeGroups(this.config.groups)

    this.host = this.findByTag(this.hostTag)[0] || null
    if (this.host) this.host.swipe = this

    this.activeSlash = null
    this.nextSlashId = 1
    this.trailPoints = []

    this.graphics = this.scene.add.graphics()
    this.graphics.setDepth(this.depth)

    this.bindPointerInput()
  }

  destroy() {
    this.unbindPointerInput()
    if (this.graphics) this.graphics.destroy()
    this.graphics = null
    if (this.host?.swipe === this) this.host.swipe = null
  }

  update() {
    this.pruneTrail()
    this.renderTrail()
  }

  normalizeGroups(groups) {
    const list = Array.isArray(groups) && groups.length
      ? groups
      : [{ tag: 'sliceable', method: 'slice', category: 'slice' }]
    return list
      .filter(g => g && g.tag && g.method)
      .map(g => ({
        tag: String(g.tag),
        method: String(g.method),
        category: String(g.category || g.tag),
        defaultRadius: numberOr(g.defaultRadius, 24),
        stopOnHit: Boolean(g.stopOnHit),
      }))
  }

  bindPointerInput() {
    this.pointerDownHandler = pointer => this.onPointerDown(pointer)
    this.pointerMoveHandler = pointer => this.onPointerMove(pointer)
    this.pointerUpHandler = pointer => this.onPointerUp(pointer)
    this.scene.input.on('pointerdown', this.pointerDownHandler)
    this.scene.input.on('pointermove', this.pointerMoveHandler)
    this.scene.input.on('pointerup', this.pointerUpHandler)
    this.scene.input.on('pointerupoutside', this.pointerUpHandler)
  }

  unbindPointerInput() {
    if (!this.scene?.input) return
    if (this.pointerDownHandler) this.scene.input.off('pointerdown', this.pointerDownHandler)
    if (this.pointerMoveHandler) this.scene.input.off('pointermove', this.pointerMoveHandler)
    if (this.pointerUpHandler) {
      this.scene.input.off('pointerup', this.pointerUpHandler)
      this.scene.input.off('pointerupoutside', this.pointerUpHandler)
    }
  }

  onPointerDown(pointer) {
    const point = this.pointerPoint(pointer)
    this.host?.onSwipePointerDown?.(point)
    if (this.host?.canSlash?.() === false) return

    this.activeSlash = {
      id: this.nextSlashId,
      points: [point],
      hitIds: new Set(),
      counts: {},
    }
    this.nextSlashId += 1
    this.host?.onSwipeStart?.(this.activeSlash)
    this.addTrailPoint(point)
  }

  onPointerMove(pointer) {
    if (!this.activeSlash) return
    if (pointer.isDown === false && pointer.buttons === 0) return

    const point = this.pointerPoint(pointer)
    const points = this.activeSlash.points
    const prev = points[points.length - 1]
    if (this.distance(prev, point) < this.minDistance) return

    points.push(point)
    this.addTrailPoint(point)
    this.hitTestSegment(prev, point)
  }

  onPointerUp(pointer) {
    if (!this.activeSlash) return
    const points = this.activeSlash.points
    if (points.length) {
      const point = this.pointerPoint(pointer)
      const prev = points[points.length - 1]
      if (this.distance(prev, point) >= 1) this.hitTestSegment(prev, point)
      this.addTrailPoint(point)
    }
    this.finishSlash()
  }

  finishSlash() {
    const slash = this.activeSlash
    if (!slash) return
    this.activeSlash = null
    this.host?.onSwipeEnd?.({ slashId: slash.id, counts: { ...slash.counts } })
  }

  // A stopOnHit target (e.g. hazard) ended the run; drop the swipe without
  // firing onSwipeEnd so the host does not also award a combo for it.
  endSlashSilently() {
    this.activeSlash = null
  }

  hitTestSegment(a, b) {
    const slash = this.activeSlash
    if (!slash) return
    if (this.host?.canSlash?.() === false) return

    for (const group of this.groups) {
      const targets = this.findByTag(group.tag).filter(node => this.isHittable(node))
      for (const target of targets) {
        if (!this.activeSlash || slash.hitIds.has(target.id)) continue
        const radius = numberOr(target.radius ?? target.config?.radius, group.defaultRadius) + this.hitPadding
        if (!this.segmentCircleHit(a, b, target.x, target.y, radius)) continue

        slash.hitIds.add(target.id)
        const count = (slash.counts[group.category] || 0) + 1
        slash.counts[group.category] = count
        const meta = {
          controller: this.host,
          module: this,
          slashId: slash.id,
          category: group.category,
          count,
          counts: { ...slash.counts },
        }
        const ok = target[group.method]?.(meta)
        if (ok === false) {
          slash.counts[group.category] = count - 1
          continue
        }
        this.host?.onSwipeHit?.({ category: group.category, target, slashId: slash.id, count })
        if (group.stopOnHit) {
          this.endSlashSilently()
          return
        }
      }
    }
  }

  isHittable(node) {
    return Boolean(
      node &&
      node.enabled !== false &&
      node.gameObject &&
      !node.sliced &&
      !node.missed &&
      !node.hit &&
      node.armed !== false,
    )
  }

  pointerPoint(pointer) {
    return {
      x: Number(pointer.worldX ?? pointer.x ?? 0),
      y: Number(pointer.worldY ?? pointer.y ?? 0),
      t: this.scene.time.now,
    }
  }

  addTrailPoint(point) {
    this.trailPoints.push({ ...point, t: this.scene.time.now })
    this.pruneTrail()
    this.renderTrail()
  }

  pruneTrail() {
    const now = this.scene.time.now
    this.trailPoints = this.trailPoints.filter(p => now - p.t <= this.trailMs)
  }

  renderTrail() {
    if (!this.graphics) return
    const g = this.graphics
    g.clear()
    if (this.trailPoints.length < 2) return

    const now = this.scene.time.now
    for (let i = 1; i < this.trailPoints.length; i += 1) {
      const a = this.trailPoints[i - 1]
      const b = this.trailPoints[i]
      const age = clamp((now - b.t) / this.trailMs, 0, 1)
      const alpha = 1 - age
      g.lineStyle(this.glowWidth * alpha + 2, this.glowColor, alpha * this.glowAlpha)
      g.beginPath()
      g.moveTo(a.x, a.y)
      g.lineTo(b.x, b.y)
      g.strokePath()
      g.lineStyle(this.coreWidth, this.coreColor, alpha * this.coreAlpha)
      g.beginPath()
      g.moveTo(a.x, a.y)
      g.lineTo(b.x, b.y)
      g.strokePath()
    }
  }

  segmentCircleHit(a, b, cx, cy, radius) {
    const abx = b.x - a.x
    const aby = b.y - a.y
    const lenSq = abx * abx + aby * aby
    if (lenSq <= 0.0001) return this.distance(a, { x: cx, y: cy }) <= radius
    const t = clamp(((cx - a.x) * abx + (cy - a.y) * aby) / lenSq, 0, 1)
    const px = a.x + abx * t
    const py = a.y + aby * t
    const dx = cx - px
    const dy = cy - py
    return dx * dx + dy * dy <= radius * radius
  }

  distance(a, b) {
    const dx = b.x - a.x
    const dy = b.y - a.y
    return Math.sqrt(dx * dx + dy * dy)
  }

  activeSlashSummary() {
    if (!this.activeSlash) return null
    return {
      active: true,
      pointCount: this.activeSlash.points.length,
      counts: { ...this.activeSlash.counts },
    }
  }
}
