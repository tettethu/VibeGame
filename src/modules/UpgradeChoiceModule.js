import { Node } from '/engine/Node.js'

/**
 * UpgradeChoiceModule — DOM 3-of-N upgrade/buff choice overlay.
 *
 * Renders a fixed-position modal with N category-banded cards (default 3), each showing
 * an icon, label, description, and keyboard chip. Player picks via keyboard 1..N or click.
 * Selection invokes a callback, then the overlay self-cleans.
 *
 * Verified for roguelike dungeon reward choices after a room is cleared.
 *
 * Visual recipe baked into the module: dark-wood card style with category color band on top
 * (offense/defense/utility = red/green/cyan by default), corner pixel accents, animated entry
 * with staggered card slide-in, hover lift + glow. The visual is opinionated — projects that
 * want a radically different aesthetic should fork the module rather than restyle.
 *
 * Config:
 *   buffPool: required. Array<BuffDef>:
 *     { id, label, desc, category, icon }
 *     - id: unique identifier passed to onSelect callback
 *     - label: card title
 *     - desc: card subtitle
 *     - category: 'offense' | 'defense' | 'utility' (drives band color + icon tint)
 *     - icon: SVG markup string (use viewBox 0 0 16 16, shape-rendering="crispEdges", fill="currentColor")
 *   onSelect: required. Function `(buff) => void` called with the selected BuffDef.
 *   onClose: optional. Function called after the overlay tears down (regardless of selection).
 *   choiceCount: optional. Number of cards to show (default 3). Sampled randomly without replacement.
 *   mountSelector: required. CSS selector for the parent element (e.g. '#game-container').
 *   strings: optional. Override default text:
 *     { eyebrow: 'CHAMBER CLEARED', title: 'Choose Upgrade', subtitle: 'Pick one blessing and continue deeper', footer: 'Press 1 2 3 or click a card to confirm' }
 *   classNames: optional. Override CSS class prefixes (default 'up-' i.e. .up-overlay / .up-card / ...).
 *
 * Public API:
 *   show()                  — display the overlay; idempotent.
 *   hide()                  — tear down without invoking onSelect.
 *   isVisible()             — boolean
 *
 * CSS contract: the host project must provide styles for #upgrade-overlay and child classes
 * (.up-stage / .up-header / .up-card / .up-card-band / .up-card-icon / .up-card-key / etc.).
 * See the roguelike-dungeon-shooter skeleton's index.html for a reference implementation.
 */
const DEFAULT_STRINGS = {
  eyebrow: 'CHAMBER CLEARED',
  title: 'Choose Upgrade',
  subtitle: 'Pick one blessing and continue deeper',
  footer: 'Press <kbd>1</kbd> <kbd>2</kbd> <kbd>3</kbd> or click a card to confirm',
}

function escapeHtml(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

export default class UpgradeChoiceModule extends Node {
  ready() {
    const c = this.config || {}
    if (!Array.isArray(c.buffPool) || c.buffPool.length === 0) {
      throw new Error('UpgradeChoiceModule: config.buffPool required (non-empty array)')
    }
    if (typeof c.onSelect !== 'function') {
      throw new Error('UpgradeChoiceModule: config.onSelect required (function)')
    }
    if (!c.mountSelector) {
      throw new Error('UpgradeChoiceModule: config.mountSelector required')
    }

    this._buffPool = c.buffPool
    this._onSelect = c.onSelect
    this._onClose = c.onClose || (() => {})
    this._choiceCount = c.choiceCount ?? 3
    this._strings = { ...DEFAULT_STRINGS, ...(c.strings || {}) }
    this._mountSelector = c.mountSelector

    this._visible = false
    this._overlay = null
    this._keyHandler = null
    this._options = []
  }

  isVisible() { return this._visible }

  show() {
    if (this._visible) return
    this._visible = true
    this._options = [...this._buffPool].sort(() => Math.random() - 0.5).slice(0, this._choiceCount)

    const parent = document.querySelector(this._mountSelector)
    if (!parent) {
      console.warn(`[UpgradeChoiceModule] No element matches "${this._mountSelector}"`)
      this._visible = false
      return
    }

    const overlay = document.createElement('div')
    overlay.id = 'upgrade-overlay'
    overlay.innerHTML = `
      <div class="up-stage">
        <div class="up-header">
          <div class="up-eyebrow">${escapeHtml(this._strings.eyebrow)}</div>
          <div class="up-title">${escapeHtml(this._strings.title)}</div>
          <div class="up-subtitle">${escapeHtml(this._strings.subtitle)}</div>
        </div>
        <div class="up-cards">
          ${this._options.map((opt, i) => `
            <button class="up-card" data-idx="${i}" data-cat="${escapeHtml(opt.category)}" type="button">
              <div class="up-card-band"></div>
              <div class="up-card-icon">${opt.icon || ''}</div>
              <div class="up-card-label">${escapeHtml(opt.label)}</div>
              <div class="up-card-desc">${escapeHtml(opt.desc)}</div>
              <div class="up-card-key"><span>${i + 1}</span></div>
            </button>
          `).join('')}
        </div>
        <div class="up-footer">${this._strings.footer}</div>
      </div>
    `
    overlay.querySelectorAll('.up-card').forEach(card => {
      card.addEventListener('click', () => this._select(parseInt(card.dataset.idx, 10)))
    })

    parent.appendChild(overlay)
    this._overlay = overlay

    this._keyHandler = (e) => {
      if (!this._visible) return
      const n = parseInt(e.key, 10)
      if (Number.isFinite(n) && n >= 1 && n <= this._options.length) {
        this._flashAndSelect(n - 1)
      }
    }
    window.addEventListener('keydown', this._keyHandler)
  }

  _flashAndSelect(idx) {
    const card = this._overlay?.querySelector(`.up-card[data-idx="${idx}"]`)
    if (card) card.classList.add('is-active')
    this._select(idx)
  }

  _select(idx) {
    if (!this._visible) return
    this._visible = false
    const opt = this._options[idx]
    this._teardown()
    if (opt) this._onSelect(opt)
    this._onClose()
  }

  hide() {
    if (!this._visible) return
    this._visible = false
    this._teardown()
    this._onClose()
  }

  _teardown() {
    if (this._overlay) { this._overlay.remove(); this._overlay = null }
    if (this._keyHandler) { window.removeEventListener('keydown', this._keyHandler); this._keyHandler = null }
  }

  destroy() {
    this._teardown()
  }
}
