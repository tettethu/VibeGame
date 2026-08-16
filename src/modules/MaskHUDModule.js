import { Node } from '/engine/Node.js'

/**
 * MaskHUDModule — discrete N-pip icon meter (mask / heart / pip).
 *
 * Renders `slotCount` copies of a single icon texture in a horizontal row pinned to
 * screen-space (no camera scroll). `setValue(n)` dims the trailing icons (`alpha = dimAlpha`)
 * while keeping the leading ones fully opaque. Use for player HP where life is a small
 * integer count (1..10ish), not a continuous bar. For continuous fill use StatusBarModule.
 *
 * Config (all values used at ready() time):
 *   iconKey:   string  — texture key for one pip (required)
 *   slotCount: number  — total pip count (default 5)
 *   size:      number  — display size in px per pip (default 32)
 *   gap:       number  — gap between pips in px (default 8)
 *   anchorX:   number  — left padding from viewport left edge (default 16)
 *   anchorY:   number  — top  padding from viewport top  edge (default 16)
 *   depth:     number  — Phaser depth (default 90)
 *   dimAlpha:  number  — alpha for empty slots (default 0.25)
 *
 * Public API:
 *   setValue(n)        — set how many pips are full (clamped to [0, slotCount])
 *   getValue() => n
 *
 * Pairs with contract `discrete-icon-meter` Pattern in status_bar.md.
 */
export default class MaskHUDModule extends Node {
  ready() {
    const cfg = this.config || {}
    if (!cfg.iconKey) {
      console.error('MaskHUDModule requires config.iconKey')
      return
    }

    this._slotCount = Number.isFinite(cfg.slotCount) ? cfg.slotCount : 5
    this._dimAlpha = Number.isFinite(cfg.dimAlpha) ? cfg.dimAlpha : 0.25
    this._value = this._slotCount

    const size = Number.isFinite(cfg.size) ? cfg.size : 32
    const gap = Number.isFinite(cfg.gap) ? cfg.gap : 8
    const anchorX = Number.isFinite(cfg.anchorX) ? cfg.anchorX : 16
    const anchorY = Number.isFinite(cfg.anchorY) ? cfg.anchorY : 16
    const depth = Number.isFinite(cfg.depth) ? cfg.depth : 90

    const startX = anchorX + size / 2
    const y = anchorY + size / 2

    this._icons = []
    for (let i = 0; i < this._slotCount; i++) {
      const img = this.scene.add.image(startX + i * (size + gap), y, cfg.iconKey)
      img.setScrollFactor(0)
      img.setDepth(depth)
      img.setDisplaySize(size, size)
      this._icons.push(img)
    }
  }

  setValue(n) {
    this._value = Math.max(0, Math.min(this._slotCount, Math.floor(Number(n) || 0)))
    for (let i = 0; i < this._slotCount; i++) {
      this._icons[i]?.setAlpha(i < this._value ? 1.0 : this._dimAlpha)
    }
    return this._value
  }

  getValue() {
    return this._value
  }

  runtimeState() {
    return {
      slotCount: this._slotCount,
      value: this._value,
      iconKey: this.config?.iconKey || null,
    }
  }

  destroy() {
    for (const img of this._icons) img?.destroy()
    this._icons = []
  }
}
