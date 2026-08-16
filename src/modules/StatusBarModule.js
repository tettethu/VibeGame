import { Node } from '/engine/Node.js'

function clamp01(value) {
  if (!Number.isFinite(value)) return 1
  return Math.max(0, Math.min(1, value))
}

function textureSize(scene, key) {
  const tex = scene.textures.get(key)
  const source = tex?.getSourceImage?.()
  return {
    width: source?.width || tex?.source?.[0]?.width || 1,
    height: source?.height || tex?.source?.[0]?.height || 1,
  }
}

export default class StatusBarModule extends Node {
  ready() {
    const cfg = this.config || {}
    const slotKey = cfg.slot
    const barKey = cfg.bar
    const bbox = cfg.bbox || {}

    if (!slotKey || !barKey || !bbox) {
      console.error('StatusBarModule requires config: icon, slot, bar, bbox')
      return
    }

    this._slotKey = slotKey
    this._barKey = barKey
    this._bbox = {
      x: Number(bbox.x) || 0,
      y: Number(bbox.y) || 0,
      w: Number(bbox.w) || 1,
      h: Number(bbox.h) || 1,
    }

    const x = Number(cfg.x) || 0
    const y = Number(cfg.y) || 0
    const scale = Number.isFinite(cfg.scale) ? cfg.scale : 1
    const depth = Number.isFinite(cfg.depth) ? cfg.depth : 100
    // HUD: screen-fixed by default so the bar stays put while the camera scrolls.
    this._scrollFactor = Number.isFinite(cfg.scrollFactor) ? cfg.scrollFactor : 0

    this.container = this.scene.add.container(x, y)
    this.container.setScale(scale)
    this.container.setDepth(depth)
    this.container.setScrollFactor(this._scrollFactor)
    this.gameObject = this.container

    // Override placeholder texture size when its logical footprint differs.
    const slotSizeOverride = cfg.slotSize
    const slotSize = slotSizeOverride
      ? { width: Number(slotSizeOverride.width) || 1, height: Number(slotSizeOverride.height) || 1 }
      : textureSize(this.scene, slotKey)
    const barSize = textureSize(this.scene, barKey)
    const slotLeft = -slotSize.width / 2
    const slotTop = -slotSize.height / 2

    const barX = slotLeft + this._bbox.x
    const barY = slotTop + this._bbox.y
    const barScaleX = this._bbox.w / barSize.width
    const barScaleY = this._bbox.h / barSize.height

    this.barImage = this.scene.add.image(barX, barY, barKey)
    this.barImage.setOrigin(0, 0)
    this.barImage.setScale(barScaleX, barScaleY)

    this.slotImage = this.scene.add.image(0, 0, slotKey)
    this.slotImage.setOrigin(0.5, 0.5)
    if (slotSizeOverride) this.slotImage.setDisplaySize(slotSize.width, slotSize.height)

    const children = [this.slotImage, this.barImage]
    const iconKey = cfg.icon || null
    if (iconKey) {
      const iconGap = Number.isFinite(cfg.iconGap) ? cfg.iconGap : 18
      const iconSize = textureSize(this.scene, iconKey)
      const iconDisplayHeight = slotSize.height * 0.85
      const iconScale = iconDisplayHeight / iconSize.height
      const iconX = slotLeft - iconGap - (iconSize.width * iconScale) / 2

      this.iconImage = this.scene.add.image(iconX, 0, iconKey)
      this.iconImage.setOrigin(0.5, 0.5)
      this.iconImage.setScale(iconScale)
      children.push(this.iconImage)
    }

    this.container.add(children)
    // Re-apply after children exist so the whole HUD (container + images) is screen-fixed.
    this.container.setScrollFactor(this._scrollFactor, this._scrollFactor, true)
    this._barSourceWidth = barSize.width
    this._barSourceHeight = barSize.height
    this._labelConfig = cfg.label || null
    this._labelLogical = null
    this._labelOverlay = null
    this._labelEl = this._labelConfig ? this._createDomLabel(this._labelConfig, x, y, scale) : null
    this._onResize = this._labelEl ? () => this._syncDomLabel() : null
    if (this._onResize) window.addEventListener('resize', this._onResize)
    this._syncDomLabel()
    this.leftRate = cfg.leftRate === undefined ? 1 : Number(cfg.leftRate)
  }

  get leftRate() {
    return this._leftRate ?? 1
  }

  set leftRate(value) {
    this.setLeftRate(value)
  }

  setLeftRate(value) {
    this._leftRate = clamp01(Number(value))
    this._applyCrop()
    return this._leftRate
  }

  _applyCrop() {
    if (!this.barImage) return

    const cropWidth = Math.round(this._barSourceWidth * this._leftRate)
    if (cropWidth <= 0) {
      this.barImage.setVisible(false)
      return
    }

    this.barImage.setVisible(true)
    this.barImage.setCrop(0, 0, cropWidth, this._barSourceHeight)
  }

  _createDomLabel(label, x, y, scale) {
    const parent = this.scene?.game?.canvas?.parentElement
    if (!parent) {
      console.error('StatusBarModule label requires a canvas parent element')
      return null
    }

    const offsetX = Number(label.offsetX) || 0
    const offsetY = Number(label.offsetY) || 0
    this._labelLogical = {
      x: x + offsetX * scale,
      y: y + offsetY * scale,
      originX: Number.isFinite(label.originX) ? Number(label.originX) : 0.5,
      originY: Number.isFinite(label.originY) ? Number(label.originY) : 0.5,
      fontSize: Number(label.fontSize) || 14,
    }

    this._labelOverlay = document.createElement('div')
    this._labelOverlay.style.position = 'absolute'
    this._labelOverlay.style.pointerEvents = 'none'
    this._labelOverlay.style.overflow = 'hidden'
    this._labelOverlay.style.zIndex = String(Number.isFinite(label.zIndex) ? label.zIndex : 10)
    parent.appendChild(this._labelOverlay)

    const el = document.createElement('div')
    el.textContent = label.text || ''
    el.style.position = 'absolute'
    el.style.margin = '0'
    el.style.fontFamily = label.fontFamily || 'sans-serif'
    el.style.fontWeight = label.fontWeight || 'normal'
    el.style.color = label.color || '#ffffff'
    el.style.textAlign = label.align || 'center'
    el.style.whiteSpace = label.whiteSpace || 'nowrap'
    el.style.pointerEvents = label.pointerEvents || 'none'
    el.style.zIndex = String(Number.isFinite(label.zIndex) ? label.zIndex : 10)
    if (Number.isFinite(label.letterSpacing)) el.style.letterSpacing = `${label.letterSpacing}px`
    if (label.textTransform) el.style.textTransform = label.textTransform
    if (Array.isArray(label.shadows) && label.shadows.length) {
      el.style.textShadow = label.shadows.map(shadow => {
        const sx = Number(shadow.offsetX) || 0
        const sy = Number(shadow.offsetY) || 0
        const blur = Number(shadow.blur) || 0
        const color = shadow.color || 'rgba(0,0,0,0.75)'
        return `${sx}px ${sy}px ${blur}px ${color}`
      }).join(', ')
    }
    this._labelOverlay.appendChild(el)
    this._syncDomLabel(el)
    return el
  }

  _syncDomLabel(labelEl = this._labelEl) {
    if (!labelEl || !this._labelOverlay || !this._labelLogical) return
    const canvas = this.scene?.game?.canvas
    const parent = canvas?.parentElement
    if (!canvas || !parent) return

    const canvasRect = canvas.getBoundingClientRect()
    const parentRect = parent.getBoundingClientRect()
    const logicalW = Number(this.scene.game.config.width) || 1
    const logicalH = Number(this.scene.game.config.height) || 1
    const sx = canvasRect.width / logicalW
    const sy = canvasRect.height / logicalH

    this._labelOverlay.style.left = `${canvasRect.left - parentRect.left}px`
    this._labelOverlay.style.top = `${canvasRect.top - parentRect.top}px`
    this._labelOverlay.style.width = `${canvasRect.width}px`
    this._labelOverlay.style.height = `${canvasRect.height}px`

    labelEl.style.left = `${(this._labelLogical.x / logicalW) * 100}%`
    labelEl.style.top = `${(this._labelLogical.y / logicalH) * 100}%`
    labelEl.style.fontSize = `${this._labelLogical.fontSize * Math.min(sx, sy)}px`
    labelEl.style.transform = `translate(${-this._labelLogical.originX * 100}%, ${-this._labelLogical.originY * 100}%)`
  }

  update() {
    this._syncDomLabel()
  }

  runtimeState() {
    return {
      leftRate: this.leftRate,
      icon: this.config?.icon || null,
      slot: this._slotKey,
      bar: this._barKey,
      bbox: this._bbox,
      label: this._labelConfig ? {
        exists: !!this._labelEl,
        text: this._labelEl?.textContent || '',
        pointerEvents: this._labelEl?.style?.pointerEvents || '',
        x: this._labelLogical ? this._labelLogical.x / this.scene.game.config.width : null,
        y: this._labelLogical ? this._labelLogical.y / this.scene.game.config.height : null,
      } : null,
    }
  }

  destroy() {
    if (this._onResize) window.removeEventListener('resize', this._onResize)
    this._labelOverlay?.remove()
    this._onResize = null
    this._labelOverlay = null
    this._labelEl = null
    this._labelConfig = null
    this._labelLogical = null
    this.container?.destroy(true)
    this.container = null
    this.iconImage = null
    this.slotImage = null
    this.barImage = null
  }
}
