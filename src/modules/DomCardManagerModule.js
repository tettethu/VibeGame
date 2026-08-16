import { Node } from '/engine/Node.js'

/**
 * DomCardManagerModule — reusable DOM hand frontend for card games.
 *
 * Static config lives in node.config:
 *   cardAtlas: texture key registered in assets/manifest.json, default 'cards'
 *   logicalWidth/logicalHeight: design-space size, default 960x540
 *   scaleMode: 'fit' or 'stretch', default 'fit'
 *   layout: 'flat' or 'arc'. flat uses xSpread/handRootW/handRootH. arc uses arcCenterX/Y/radius/angle values.
 *   cardW/cardH/xSpread/handRootW/handRootH: logical layout values
 *   hoverScale/hoverLift/neighborShift/hitboxPad/snapBackDuration: interaction tuning
 *   arrowColor/arrowChevronSpacing/arrowChevronLength/arrowChevronWidth/arrowChevronStroke/arrowSpring: drag chevron arrow tuning
 *   enemyTargetEffects: effect names that should target 'enemy'
 *   targets: [{ id:'enemy', tag:'enemy' }, { id:'self', tag:'player' }]
 *
 * Runtime input:
 *   setState({ cards, energy, phase, locked }) or refresh(cards, energy, phase, locked)
 *
 * Runtime output:
 *   emits 'card_play_requested' and calls setCardPlayCallback callback with (index, target).
 */
export default class DomCardManagerModule extends Node {
  ready() {
    const c = this.config ?? {}
    this.logicalWidth = c.logicalWidth ?? 960
    this.logicalHeight = c.logicalHeight ?? 540
    this.scaleMode = c.scaleMode ?? 'fit'
    this.cardAtlas = c.cardAtlas ?? 'cards'
    this.cardW = c.cardW ?? 118
    this.cardH = c.cardH ?? 170
    this.layout = c.layout ?? 'flat'
    this.xSpread = c.xSpread ?? 92
    this.handRootW = c.handRootW ?? 760
    this.handRootH = c.handRootH ?? 190
    this.arcCenterX = c.arcCenterX ?? this.logicalWidth / 2
    this.arcCenterY = c.arcCenterY ?? 820
    this.arcRadius = c.arcRadius ?? 405
    this.arcCenterAngleDeg = c.arcCenterAngleDeg ?? -90
    this.arcAngleStepDeg = c.arcAngleStepDeg ?? 6
    this.arcMaxAngleDeg = c.arcMaxAngleDeg ?? 18
    this.hoverGapAngleDeg = c.hoverGapAngleDeg ?? 4
    this.hoverScale = c.hoverScale ?? 1.18
    this.hoverLift = c.hoverLift ?? 36
    this.neighborShift = c.neighborShift ?? 28
    this.hitboxPad = c.hitboxPad ?? 32
    this.snapBackDuration = c.snapBackDuration ?? 180
    this.arrowColor = c.arrowColor ?? '#00f5ff'
    this.arrowChevronSpacing = c.arrowChevronSpacing ?? 30
    this.arrowChevronLength = c.arrowChevronLength ?? 18
    this.arrowChevronWidth = c.arrowChevronWidth ?? 46
    this.arrowChevronStroke = c.arrowChevronStroke ?? 8
    this.arrowSpring = c.arrowSpring ?? 6
    this.showCostBadge = c.showCostBadge ?? false

    this.enemyTargetEffects = new Set(c.enemyTargetEffects ?? [
      'damage', 'damage_x2', 'attack', 'bash', 'twin_strike', 'vuln_enemy'
    ])
    this.targets = c.targets ?? [
      { id: 'enemy', tag: 'enemy' },
      { id: 'self', tag: 'player' },
    ]

    this._selfCheck(c)

    this.container = document.getElementById(c.containerId ?? 'game-container')
    if (!this.container) {
      console.error('DomCardManagerModule: #game-container not found')
      return
    }

    this.cards = []
    this.energy = 0
    this.phase = 'init'
    this.locked = false
    this.cardEls = []
    this.hoveredIdx = null
    this.draggingEl = null
    this.draggingIdx = null
    this.dragOffX = 0
    this.dragOffY = 0
    this.dragOriginX = 0
    this.dragOriginY = 0
    this.playCallback = null
    this.scaleX = 1
    this.scaleY = 1
    this.offsetX = 0
    this.offsetY = 0
    this.lastContainerW = 0
    this.lastContainerH = 0

    this._injectStyles()
    this._buildDom()
    this._syncScale(true)

    this._boundMouseMove = (e) => this._onMouseMove(e)
    this._boundMouseUp = (e) => this._onMouseUp(e)
    document.addEventListener('mousemove', this._boundMouseMove)
    document.addEventListener('mouseup', this._boundMouseUp)
  }

  _selfCheck(config) {
    const tag = `DomCardManagerModule[${this.name || this.id || 'unnamed'}]`
    const errors = []
    const warns = []
    const positive = [
      ['logicalWidth', this.logicalWidth], ['logicalHeight', this.logicalHeight],
      ['cardW', this.cardW], ['cardH', this.cardH],
      ['hoverScale', this.hoverScale], ['hitboxPad', this.hitboxPad],
      ['snapBackDuration', this.snapBackDuration],
    ]
    for (const [key, value] of positive) {
      if (!Number.isFinite(Number(value)) || Number(value) <= 0) errors.push(`config.${key} must be a positive number`)
    }
    if (!['fit', 'stretch'].includes(this.scaleMode)) errors.push('config.scaleMode must be "fit" or "stretch"')
    if (!['flat', 'arc'].includes(this.layout)) errors.push('config.layout must be "flat" or "arc"')
    if (this.layout === 'arc') {
      for (const [key, value] of [['arcRadius', this.arcRadius], ['arcAngleStepDeg', this.arcAngleStepDeg], ['arcMaxAngleDeg', this.arcMaxAngleDeg]]) {
        if (!Number.isFinite(Number(value)) || Number(value) <= 0) errors.push(`config.${key} must be a positive number for arc layout`)
      }
    }
    if (!Array.isArray(config?.targets) && config?.targets !== undefined) errors.push('config.targets must be an array')
    for (const target of this.targets) {
      if (!target?.id || !target?.tag) warns.push('each config.targets entry should include id and tag')
    }
    if (!this.cardAtlas) errors.push('config.cardAtlas is required')
    for (const e of errors) console.error(`${tag}: ${e}`)
    for (const w of warns) console.warn(`${tag}: ${w}`)
  }

  update() {
    this._syncScale(false)
  }

  setCardPlayCallback(fn) {
    this.playCallback = fn
  }

  setState(state = {}) {
    this.cards = state.cards ?? this.cards
    this.energy = state.energy ?? this.energy
    this.phase = state.phase ?? this.phase
    this.locked = !!state.locked
    this._render()
  }

  refresh(cards, energyOrState, phase, isResolvingAction = false) {
    if (energyOrState && typeof energyOrState === 'object') {
      this.setState({ cards, ...energyOrState })
      return
    }
    this.setState({
      cards,
      energy: energyOrState,
      phase,
      locked: isResolvingAction,
    })
  }

  destroy() {
    document.removeEventListener('mousemove', this._boundMouseMove)
    document.removeEventListener('mouseup', this._boundMouseUp)
    this.viewport?.remove()
  }

  _buildDom() {
    this.viewport = document.createElement('div')
    this.viewport.className = 'vg-card-manager-viewport'
    this.container.appendChild(this.viewport)

    this.logicalRoot = document.createElement('div')
    this.logicalRoot.className = 'vg-card-manager-logical'
    this.logicalRoot.style.width = `${this.logicalWidth}px`
    this.logicalRoot.style.height = `${this.logicalHeight}px`
    this.viewport.appendChild(this.logicalRoot)

    this.handRoot = document.createElement('div')
    this.handRoot.className = 'vg-card-hand-root'
    this.handRoot.style.width = `${this.handRootW}px`
    this.handRoot.style.height = `${this.handRootH}px`
    this.logicalRoot.appendChild(this.handRoot)

    this.tooltip = document.createElement('div')
    this.tooltip.className = 'vg-card-tooltip'
    this.tooltip.style.display = 'none'
    this.logicalRoot.appendChild(this.tooltip)

    this.arrow = document.createElementNS('http://www.w3.org/2000/svg', 'svg')
    this.arrow.classList.add('vg-card-drag-arrow')
    this.arrow.style.display = 'none'
    this.logicalRoot.appendChild(this.arrow)

    this.targetBox = document.createElement('div')
    this.targetBox.className = 'vg-card-target-box'
    this.targetBox.style.display = 'none'
    this.logicalRoot.appendChild(this.targetBox)
  }

  _syncScale(force) {
    if (!this.container || !this.logicalRoot) return
    const r = this.container.getBoundingClientRect()
    if (!force && r.width === this.lastContainerW && r.height === this.lastContainerH) return
    this.lastContainerW = r.width
    this.lastContainerH = r.height

    const sx = r.width / this.logicalWidth
    const sy = r.height / this.logicalHeight
    if (this.scaleMode === 'stretch') {
      this.scaleX = sx
      this.scaleY = sy
      this.offsetX = 0
      this.offsetY = 0
    } else {
      const s = Math.min(sx, sy)
      this.scaleX = s
      this.scaleY = s
      this.offsetX = (r.width - this.logicalWidth * s) * 0.5
      this.offsetY = (r.height - this.logicalHeight * s) * 0.5
    }

    this.logicalRoot.style.transform = `translate(${this.offsetX}px, ${this.offsetY}px) scale(${this.scaleX}, ${this.scaleY})`
  }

  _clientToLogical(clientX, clientY) {
    const r = this.container.getBoundingClientRect()
    return {
      x: (clientX - r.left - this.offsetX) / this.scaleX,
      y: (clientY - r.top - this.offsetY) / this.scaleY,
    }
  }

  _render() {
    if (!this.handRoot) return
    this.handRoot.innerHTML = ''
    this._hideTooltip()
    this.cardEls = []
    this.hoveredIdx = null

    const n = this.cards.length
    if (n === 0) return

    this.cards.forEach((card, i) => {
      const layout = this._layoutForIndex(i, null)
      const el = this._renderCard(card, i, layout)
      this._applyLayout(el, layout)
      this.handRoot.appendChild(el)
      this.cardEls.push(el)
    })
  }

  _renderCard(card, index, layout) {
    const el = document.createElement('div')
    el.className = `vg-card ${this._categoryClass(card)}`
    el.style.width = `${this.cardW}px`
    el.style.height = `${this.cardH}px`
    el.style.left = `${layout.left}px`
    el.style.top = `${layout.top}px`
    el.style.bottom = 'auto'
    el.style.zIndex = String(index + 1)
    el.style.setProperty('--card-name-size', `${Math.max(13, Math.round(this.cardH * 0.105))}px`)
    el.style.setProperty('--card-type-size', `${Math.max(9, Math.round(this.cardH * 0.072))}px`)
    el.style.setProperty('--card-desc-size', `${Math.max(11, Math.round(this.cardH * 0.09))}px`)

    const playable = this._isPlayable(card)
    if (!playable) el.classList.add('is-unplayable')

    const art = this._cardArtHtml(card, index)
    const cost = this.showCostBadge ? `<div class="vg-card-cost">${card.cost ?? 0}</div>` : ''
    el.innerHTML = `
      ${art}
      ${cost}
      <div class="vg-card-name">${this._escape(card.name ?? card.id ?? 'CARD')}</div>
      <div class="vg-card-type">${this._escape(card.type ?? '')}</div>
      <div class="vg-card-desc">${this._escape(card.desc ?? '')}</div>
    `

    el.addEventListener('mouseenter', () => {
      if (this.draggingEl || !playable) return
      this._setHover(index)
      this._showTooltip(card, el)
    })
    el.addEventListener('mouseleave', () => {
      if (this.draggingEl) return
      this._clearHover()
      this._hideTooltip()
    })
    if (playable) {
      el.addEventListener('mousedown', (e) => {
        e.preventDefault()
        this._startDrag(el, index, e.clientX, e.clientY)
      })
    }
    return el
  }

  _categoryClass(card) {
    const key = String(card.category || card.type || '').toLowerCase()
    if (key.includes('attack') || key.includes('offense')) return 'is-attack'
    if (key.includes('skill') || key.includes('defense')) return 'is-skill'
    if (key.includes('power') || key.includes('utility')) return 'is-power'
    return 'is-neutral'
  }

  _isPlayable(card) {
    return (Number(card.cost) || 0) <= this.energy && this.phase === 'playerTurn' && !this.locked
  }

  _cardArtHtml(card, index = 0) {
    const fi = this._getFrameRawInfo(card.id)
    if (!fi) return ''
    const scale = this.cardW / fi.frameW
    const imgW = Math.round(fi.atlasW * scale)
    const imgH = Math.round(fi.atlasH * scale)
    const imgL = -Math.round(fi.frameX * scale)
    const imgT = -Math.round(fi.frameY * scale)
    return `<img class="vg-card-art" src="${fi.url}" draggable="false" style="left:${imgL}px;top:${imgT}px;width:${imgW}px;height:${imgH}px;">`
  }

  _getFrameRawInfo(frameName) {
    const tex = this.scene?.textures?.get?.(this.cardAtlas)
    if (!tex) return null
    const frame = tex.get(frameName)
    if (!frame || frame.realWidth <= 0) return null
    const manifestPath = this.sceneTree?.assetManifest?.[this.cardAtlas]?.path
    const base = String(window.__APP_CONFIG__?.appBasePath || '').replace(/\/+$/, '')
    const url = manifestPath ? `${base}/assets/${manifestPath}` : frame.source?.image?.src
    if (!url) return null
    return {
      url,
      atlasW: frame.source.width,
      atlasH: frame.source.height,
      frameX: frame.cutX ?? frame.x ?? 0,
      frameY: frame.cutY ?? frame.y ?? 0,
      frameW: frame.realWidth,
      frameH: frame.realHeight,
    }
  }

  _setHover(index) {
    this.hoveredIdx = index
    this.cardEls.forEach((el, i) => {
      const layout = this._layoutForIndex(i, index)
      this._applyLayout(el, layout)
      if (i === index) {
        el.classList.add('is-hover')
      } else {
        el.classList.remove('is-hover')
      }
    })
  }

  _clearHover() {
    this.hoveredIdx = null
    this.cardEls.forEach((el, i) => {
      const layout = this._layoutForIndex(i, null)
      this._applyLayout(el, layout)
      el.classList.remove('is-hover')
    })
  }

  _layoutForIndex(index, hoveredIndex = null) {
    return this.layout === 'arc'
      ? this._arcLayoutForIndex(index, hoveredIndex)
      : this._flatLayoutForIndex(index, hoveredIndex)
  }

  _flatLayoutForIndex(index, hoveredIndex = null) {
    const n = this.cards.length
    const pos = index - (n - 1) / 2
    const centerLeft = this.handRootW / 2 - this.cardW / 2
    let left = centerLeft + pos * this.xSpread
    let top = this.handRootH - this.cardH
    let transform = 'rotate(0deg)'
    let z = index + 1
    if (hoveredIndex !== null) {
      if (index === hoveredIndex) {
        transform = `translateY(-${this.hoverLift}px) scale(${this.hoverScale}) rotate(0deg)`
        z = 100
      } else if (index < hoveredIndex) {
        transform = `translateX(-${this.neighborShift}px) rotate(0deg)`
      } else {
        transform = `translateX(${this.neighborShift}px) rotate(0deg)`
      }
    }
    return { left, top, transform, z, origin: '50% 50%' }
  }

  _arcLayoutForIndex(index, hoveredIndex = null) {
    const n = this.cards.length
    const basePos = index - (n - 1) / 2
    let angleOffset = basePos * this.arcAngleStepDeg
    if (hoveredIndex !== null && index !== hoveredIndex) {
      angleOffset += index < hoveredIndex ? -this.hoverGapAngleDeg : this.hoverGapAngleDeg
    }
    angleOffset = this._clamp(angleOffset, -this.arcMaxAngleDeg, this.arcMaxAngleDeg)
    const angleDeg = this.arcCenterAngleDeg + angleOffset
    const angle = angleDeg * Math.PI / 180
    const pivotX = this.arcCenterX + Math.cos(angle) * this.arcRadius
    let pivotY = this.arcCenterY + Math.sin(angle) * this.arcRadius
    let rotation = angleOffset
    let scale = 1
    let z = index + 1
    if (hoveredIndex === index) {
      pivotY -= this.hoverLift
      rotation = 0
      scale = this.hoverScale
      z = 100
    }
    const left = pivotX - this.cardW / 2
    const top = pivotY
    return { left, top, transform: `rotate(${rotation.toFixed(2)}deg) scale(${scale})`, z, origin: '50% 0%' }
  }

  _applyLayout(el, layout) {
    el.style.left = `${layout.left}px`
    el.style.top = `${layout.top}px`
    el.style.bottom = 'auto'
    el.style.transformOrigin = layout.origin
    el.style.transform = layout.transform
    el.style.zIndex = String(layout.z)
  }

  _clamp(value, min, max) {
    return Math.max(min, Math.min(max, value))
  }

  _startDrag(cardEl, cardIdx, clientX, clientY) {
    this._syncScale(true)
    cardEl.style.transition = 'none'
    this._clearHover()
    this._hideTooltip()

    const p = this._clientToLogical(clientX, clientY)
    const cr = cardEl.getBoundingClientRect()
    const containerRect = this.container.getBoundingClientRect()
    const startLeft = (cr.left - containerRect.left - this.offsetX) / this.scaleX
    const startTop = (cr.top - containerRect.top - this.offsetY) / this.scaleY

    this.dragOffX = startLeft - p.x
    this.dragOffY = startTop - p.y

    const originLayout = this._layoutForIndex(cardIdx, null)
    this.dragOriginX = originLayout.left
    this.dragOriginY = originLayout.top

    cardEl.remove()
    cardEl.style.position = 'absolute'
    cardEl.style.left = `${startLeft}px`
    cardEl.style.top = `${startTop}px`
    cardEl.style.bottom = 'auto'
    cardEl.classList.add('is-dragging')
    this.logicalRoot.appendChild(cardEl)

    this.draggingEl = cardEl
    this.draggingIdx = cardIdx
  }

  _onMouseMove(e) {
    if (!this.draggingEl) return
    const p = this._clientToLogical(e.clientX, e.clientY)
    const left = p.x + this.dragOffX
    const top = p.y + this.dragOffY
    this.draggingEl.style.left = `${left}px`
    this.draggingEl.style.top = `${top}px`

    const ax1 = this.dragOriginX + this.cardW / 2
    const ay1 = this.dragOriginY + this.cardH / 2
    const ax2 = left + this.cardW / 2
    const ay2 = top + this.cardH / 2
    this._updateArrow(ax1, ay1, ax2, ay2)
    this._updateTargetBox(p)
  }

  _onMouseUp(e) {
    if (!this.draggingEl) return
    const card = this.cards[this.draggingIdx]
    if (!card) {
      this._snapBack(this.draggingEl)
      this.draggingEl = null
      this._clearArrow()
      this._clearTargetBox()
      return
    }

    const p = this._clientToLogical(e.clientX, e.clientY)
    const need = this._targetForCard(card)
    const hit = this._getTargetAtPoint(p)
    this._clearArrow()
    this._clearTargetBox()

    const el = this.draggingEl
    const idx = this.draggingIdx
    this.draggingEl = null
    if (hit === need) this._playCard(el, idx, hit, e)
    else this._snapBack(el)
  }

  _targetForCard(card) {
    return this.enemyTargetEffects.has(card.effect) ? 'enemy' : 'self'
  }

  _targetEntry(id) {
    return this.targets.find(t => t.id === id) || null
  }

  _targetNode(id) {
    const entry = this._targetEntry(id)
    if (!entry?.tag) return null
    return this.findByTag(entry.tag)[0] ?? null
  }

  _getTargetAtPoint(p) {
    for (const target of this.targets) {
      const node = this._targetNode(target.id)
      const sprite = node?.getVisualObject?.()
      if (!sprite) continue
      const b = sprite.getBounds()
      const pad = this.hitboxPad
      if (p.x >= b.left - pad && p.x <= b.right + pad && p.y >= b.top - pad && p.y <= b.bottom + pad) {
        return target.id
      }
    }
    return null
  }

  _playCard(cardEl, cardIdx, target, e) {
    const card = this.cards[cardIdx]
    cardEl.remove()
    this.draggingIdx = null
    const event = {
      index: cardIdx,
      card,
      target,
      pointer: { clientX: e.clientX, clientY: e.clientY },
    }
    this.emit?.('card_play_requested', event)
    this.playCallback?.(cardIdx, target, event)
  }

  _snapBack(cardEl) {
    cardEl.classList.remove('is-dragging')
    cardEl.style.transition = `left ${this.snapBackDuration}ms ease, top ${this.snapBackDuration}ms ease`
    cardEl.style.left = `${this.dragOriginX}px`
    cardEl.style.top = `${this.dragOriginY}px`
    setTimeout(() => {
      cardEl.remove()
      this._render()
      this.draggingIdx = null
    }, this.snapBackDuration + 20)
  }

  _updateArrow(x1, y1, x2, y2) {
    this.arrow.style.display = 'block'
    const dx = x2 - x1
    const dy = y2 - y1
    const dist = Math.sqrt(dx * dx + dy * dy)
    if (dist < 18) { this.arrow.innerHTML = ''; return }

    const nx = dx / dist
    const ny = dy / dist
    const px = -ny
    const py = nx
    const spacing = this.arrowChevronSpacing
    const count = Math.min(18, Math.max(2, Math.floor(dist / spacing)))
    const startPad = Math.min(24, dist * 0.18)
    const endPad = Math.min(30, dist * 0.16)
    const usable = Math.max(1, dist - startPad - endPad)
    const color = this.arrowColor
    const phase = Date.now() / 130
    let html = `
      <defs>
        <filter id="vg-card-arrow-glow" x="-50%" y="-50%" width="200%" height="200%">
          <feGaussianBlur stdDeviation="2.4" result="blur"/>
          <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
        </filter>
      </defs>
    `

    for (let i = 0; i < count; i++) {
      const t = count === 1 ? 1 : i / (count - 1)
      const along = startPad + usable * t
      const spring = Math.sin(t * Math.PI * 2.2 + phase) * this.arrowSpring * (0.35 + t * 0.65)
      const cx = x1 + nx * along + px * spring
      const cy = y1 + ny * along + py * spring
      const armLen = this.arrowChevronWidth * (0.76 + t * 0.28)
      const forward = this.arrowChevronLength * (0.72 + t * 0.28)
      const band = this.arrowChevronStroke * (0.8 + t * 0.25)
      const tipX = cx + nx * forward
      const tipY = cy + ny * forward
      const leftX = cx - nx * forward * 0.42 + px * armLen * 0.5
      const leftY = cy - ny * forward * 0.42 + py * armLen * 0.5
      const rightX = cx - nx * forward * 0.42 - px * armLen * 0.5
      const rightY = cy - ny * forward * 0.42 - py * armLen * 0.5
      const op = (0.24 + t * 0.76).toFixed(2)
      html += this._arrowBand(leftX, leftY, tipX, tipY, band, color, op)
      html += this._arrowBand(rightX, rightY, tipX, tipY, band, color, op)
    }
    this.arrow.innerHTML = html
  }

  _arrowBand(x1, y1, x2, y2, width, color, opacity) {
    const dx = x2 - x1
    const dy = y2 - y1
    const dist = Math.max(1, Math.sqrt(dx * dx + dy * dy))
    const px = -dy / dist * width / 2
    const py = dx / dist * width / 2
    const points = [
      `${(x1 + px).toFixed(1)},${(y1 + py).toFixed(1)}`,
      `${(x2 + px).toFixed(1)},${(y2 + py).toFixed(1)}`,
      `${(x2 - px).toFixed(1)},${(y2 - py).toFixed(1)}`,
      `${(x1 - px).toFixed(1)},${(y1 - py).toFixed(1)}`,
    ].join(' ')
    return `<polygon points="${points}" fill="${color}" opacity="${opacity}" filter="url(#vg-card-arrow-glow)"/>`
  }

  _clearArrow() {
    this.arrow.style.display = 'none'
    this.arrow.innerHTML = ''
  }

  _updateTargetBox(pointerLogical) {
    const card = this.cards[this.draggingIdx]
    if (!card) { this.targetBox.style.display = 'none'; return }
    const need = this._targetForCard(card)
    const node = this._targetNode(need)
    const sprite = node?.getVisualObject?.()
    if (!sprite) { this.targetBox.style.display = 'none'; return }
    const b = sprite.getBounds()
    const pad = this.hitboxPad
    const inside = pointerLogical.x >= b.left - pad && pointerLogical.x <= b.right + pad && pointerLogical.y >= b.top - pad && pointerLogical.y <= b.bottom + pad
    if (!inside) { this.targetBox.style.display = 'none'; return }
    Object.assign(this.targetBox.style, {
      display: 'block',
      left: `${b.left - pad}px`,
      top: `${b.top - pad}px`,
      width: `${b.width + pad * 2}px`,
      height: `${b.height + pad * 2}px`,
    })
  }

  _clearTargetBox() {
    this.targetBox.style.display = 'none'
  }

  _showTooltip(card, cardEl) {
    this.tooltip.innerHTML = `
      <div class="vg-card-tooltip-title">${this._escape(card.name ?? card.id ?? 'CARD')} <span>${Number(card.cost) || 0} energy</span></div>
      <div class="vg-card-tooltip-body">${this._escape(card.desc ?? '')}</div>
    `
    const left = parseFloat(cardEl.style.left) + this.cardW / 2 - 90
    const top = Math.max(4, parseFloat(cardEl.style.top) - 92)
    this.tooltip.style.left = `${Math.max(4, left)}px`
    this.tooltip.style.top = `${Math.max(4, top)}px`
    this.tooltip.style.display = 'block'
  }

  _hideTooltip() {
    if (this.tooltip) this.tooltip.style.display = 'none'
  }

  _escape(value) {
    return String(value).replace(/[&<>"]/g, (ch) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[ch]))
  }

  _injectStyles() {
    if (document.getElementById('vg-card-manager-style')) return
    const style = document.createElement('style')
    style.id = 'vg-card-manager-style'
    style.textContent = `
      .vg-card-manager-viewport{position:absolute;inset:0;pointer-events:none;overflow:hidden;z-index:25;}
      .vg-card-manager-logical{position:absolute;left:0;top:0;transform-origin:0 0;pointer-events:none;}
      .vg-card-hand-root{position:absolute;inset:0;pointer-events:none;}
      .vg-card{position:absolute;border-radius:14px;background:#141827;border:1px solid rgba(180,220,255,.35);color:#ddd;pointer-events:all;cursor:pointer;overflow:hidden;user-select:none;font-family:'Rajdhani',system-ui,sans-serif;transition:left .16s ease,top .16s ease,transform .16s ease,box-shadow .12s ease,border-color .12s ease;box-shadow:0 4px 16px rgba(0,0,0,.42);}
      .vg-card::after{content:'';position:absolute;inset:0;border-radius:14px;background:linear-gradient(to bottom,rgba(0,0,0,0) 0%,rgba(0,0,0,0) 35%,rgba(0,0,0,.55) 66%,rgba(0,0,0,.88) 100%);pointer-events:none;z-index:1;}
      .vg-card.is-hover{box-shadow:0 0 20px 4px rgba(0,220,255,.75),0 8px 24px rgba(0,0,0,.6);border-color:#0df;z-index:20!important;}
      .vg-card.is-unplayable{opacity:.42;cursor:not-allowed;pointer-events:none;filter:saturate(.55);}
      .vg-card.is-dragging{transition:none!important;cursor:grabbing;z-index:100!important;box-shadow:0 8px 28px rgba(0,0,0,.65),0 0 24px rgba(0,220,255,.55);}
      .vg-card-art{position:absolute;z-index:0;pointer-events:none;}
      .vg-card-cost{position:absolute;left:7px;top:7px;z-index:3;width:24px;height:24px;border-radius:50%;background:#ffcc00;color:#111;display:flex;align-items:center;justify-content:center;font-size:15px;font-weight:700;text-shadow:none;box-shadow:0 0 8px rgba(255,204,0,.65),0 1px 2px #000;}
      .vg-card-name{position:absolute;top:34px;left:10px;right:10px;z-index:2;font-size:var(--card-name-size);font-weight:700;color:#ffcc00;text-transform:uppercase;letter-spacing:.05em;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;text-shadow:0 1px 3px rgba(0,0,0,.9);}
      .vg-card-type{position:absolute;top:8px;right:8px;max-width:58px;text-align:right;z-index:3;font-size:var(--card-type-size);font-weight:700;color:#dcecff;letter-spacing:.06em;text-transform:uppercase;text-shadow:0 1px 3px rgba(0,0,0,.9);}
      .vg-card-desc{position:absolute;bottom:8px;left:10px;right:10px;z-index:2;font-size:var(--card-desc-size);line-height:1.2;color:#ddd;text-transform:none;font-weight:600;text-shadow:0 1px 2px #000;}
      .vg-card.is-attack{border-color:rgba(255,110,90,.45);}
      .vg-card.is-skill{border-color:rgba(0,220,255,.45);}
      .vg-card.is-power{border-color:rgba(210,110,255,.48);}
      .vg-card-drag-arrow{position:absolute;inset:0;pointer-events:none;z-index:50;overflow:visible;}
      .vg-card-target-box{position:absolute;border:4px solid #0ff;box-shadow:0 0 14px 2px rgba(0,255,255,.45);border-radius:4px;pointer-events:none;z-index:55;}
      .vg-card-tooltip{position:absolute;background:rgba(8,12,26,.97);border:1px solid #0df;border-radius:6px;padding:8px 10px;width:184px;pointer-events:none;z-index:60;font-family:'Rajdhani',system-ui,sans-serif;color:#ccc;}
      .vg-card-tooltip-title{font-size:13px;color:#0df;margin-bottom:5px;font-weight:700;text-transform:uppercase;}
      .vg-card-tooltip-title span{color:#888;font-size:10px;}
      .vg-card-tooltip-body{font-size:11px;color:#ccc;line-height:1.4;text-transform:none;font-weight:600;}
    `
    document.head.appendChild(style)
  }
}
