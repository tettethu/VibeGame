import { Node } from '/engine/Node.js'

/**
 * GameOverlayModule — DOM-based pause / death / victory / custom menu overlay.
 *
 * Renders a set of full-screen dimmed backdrops with a centered panel + buttons,
 * declared via config.menus. Pause integration is correct by construction: when
 * `showMenu` is called and the menu has `pausesGame: true`, the module halts BOTH
 * `sceneTree.running` AND `scene.scene.pause()` (Phaser physics / anims / timers).
 *
 * Why DOM and not Phaser.Text: cleaner CSS styling, no Phaser font preload, no canvas
 * text rasterization, and pause / resume keyboard handling works while Phaser scene
 * is paused (DOM events fire regardless of game loop state).
 *
 * Config:
 *   menus: [
 *     {
 *       id: 'pause',
 *       title: 'PAUSED',
 *       subtitle?: '...',
 *       pausesGame: true,           // halt scene+sceneTree while shown
 *       toggleKey?: 'Escape',       // key that toggles this menu open / closed
 *       buttons: [
 *         { label: 'Resume',  action: 'resume' },
 *         { label: 'Restart', action: 'restart' },
 *         { label: 'Quit',    action: 'quit' }
 *       ]
 *     },
 *     { id: 'death',   title: 'YOU DIED', buttons: [...] },
 *     { id: 'victory', title: 'VICTORY',  subtitle: '...', buttons: [...] }
 *   ]
 *   style: {
 *     panelTexture?:  'ui_panel',          // asset key for panel background image
 *     buttonIdleTex?: 'ui_button_idle',
 *     buttonHoverTex?:'ui_button_hover',   // if absent, hover uses CSS filter brightness
 *     fontFamily?:    "system-ui, sans-serif",
 *     titleColor?:    '#e8d5a3',
 *     subtitleColor?: '#aaa',
 *     panelWidth?:    300,
 *     panelHeight?:   480,
 *     containerId?:   'game-container',    // DOM element to mount overlays into
 *     hurtFlashColor?:'rgba(255,50,50,0.35)'
 *   }
 *
 * Built-in actions: 'resume', 'restart' (window.location.reload), 'quit'
 * (window.location.reload). Custom action: pass a function `action: (overlay) => {...}`
 * instead of a string.
 *
 * Public API:
 *   showMenu(id)
 *   hideMenu(id?)         — id omitted: hide all
 *   isMenuVisible(id) => bool
 *   flashHurt()           — brief red overlay (~150ms)
 *
 * Pairs with contract `dom-overlay-with-phaser-pause` Pattern in game_overlay.md.
 */
export default class GameOverlayModule extends Node {
  ready() {
    const cfg = this.config || {}
    const style = cfg.style || {}

    this._containerId = style.containerId || 'game-container'
    this._container = document.getElementById(this._containerId)
    if (!this._container) {
      console.error(`GameOverlayModule: container #${this._containerId} not found`)
      return
    }

    this._style = {
      panelTexture:    style.panelTexture    || null,
      buttonIdleTex:   style.buttonIdleTex   || null,
      buttonHoverTex:  style.buttonHoverTex  || null,
      fontFamily:      style.fontFamily      || 'serif',
      titleColor:      style.titleColor      || '#e8d5a3',
      subtitleColor:   style.subtitleColor   || '#aaa',
      panelWidth:      Number.isFinite(style.panelWidth)  ? style.panelWidth  : 300,
      panelHeight:     Number.isFinite(style.panelHeight) ? style.panelHeight : 480,
      hurtFlashColor:  style.hurtFlashColor  || 'rgba(255,50,50,0.35)',
    }

    this._menuConfigs = cfg.menus || []
    this._menuDivs = new Map()
    this._toggleKeyMap = new Map()

    this._hurtFlashDiv = this._makeDiv('vg-hurt-flash',
      `position:absolute;inset:0;background:${this._style.hurtFlashColor};pointer-events:none;display:none;z-index:10;`)

    for (const menu of this._menuConfigs) {
      const div = this._buildMenu(menu)
      this._menuDivs.set(menu.id, { div, config: menu })
      if (menu.toggleKey) this._toggleKeyMap.set(menu.toggleKey, menu.id)
    }

    this._onKeyDown = (e) => {
      const menuId = this._toggleKeyMap.get(e.key)
      if (menuId) this._toggleMenu(menuId)
    }
    window.addEventListener('keydown', this._onKeyDown)
  }

  showMenu(id) {
    const entry = this._menuDivs.get(id)
    if (!entry) return
    if (entry.config.pausesGame) this._pauseGame()
    entry.div.style.display = 'flex'
  }

  hideMenu(id) {
    if (id === undefined) {
      for (const [_, entry] of this._menuDivs) {
        entry.div.style.display = 'none'
      }
      this._resumeGame()
      return
    }
    const entry = this._menuDivs.get(id)
    if (!entry) return
    entry.div.style.display = 'none'
    if (entry.config.pausesGame) this._resumeGame()
  }

  isMenuVisible(id) {
    const entry = this._menuDivs.get(id)
    return !!entry && entry.div.style.display !== 'none'
  }

  flashHurt() {
    if (!this._hurtFlashDiv) return
    this._hurtFlashDiv.style.display = 'block'
    this.scene.time.delayedCall(150, () => {
      if (this._hurtFlashDiv) this._hurtFlashDiv.style.display = 'none'
    })
  }

  // === Internal ===

  _toggleMenu(id) {
    if (this.isMenuVisible(id)) this.hideMenu(id)
    else this.showMenu(id)
  }

  _pauseGame() {
    this.sceneTree.running = false
    this.scene.scene.pause()
  }

  _resumeGame() {
    this.scene.scene.resume()
    this.sceneTree.running = true
  }

  _buildMenu(menu) {
    const outer = document.createElement('div')
    outer.id = `vg-menu-${menu.id}-outer`
    outer.style.cssText = 'position:absolute;inset:0;background:rgba(0,0,0,0.72);' +
      'display:none;justify-content:center;align-items:center;z-index:20;'
    this._container.appendChild(outer)

    const inner = document.createElement('div')
    inner.id = `vg-menu-${menu.id}-panel`
    const panelBg = this._style.panelTexture ? `background-image:url('assets/${this._style.panelTexture}');background-size:100% 100%;` : 'background:#111;border:2px solid #555;'
    inner.style.cssText = [
      panelBg.replace(/;$/, ''),
      `width:${this._style.panelWidth}px`,
      `height:${this._style.panelHeight}px`,
      'display:flex',
      'flex-direction:column',
      'align-items:center',
      'justify-content:center',
      'gap:14px',
      'padding:20px',
      'box-sizing:border-box'
    ].join(';')
    outer.appendChild(inner)

    if (menu.title) {
      const h = document.createElement('h2')
      h.textContent = menu.title
      h.style.cssText = `font-family:${this._style.fontFamily};font-size:26px;letter-spacing:3px;color:${this._style.titleColor};margin:0 0 8px;text-align:center;`
      inner.appendChild(h)
    }
    if (menu.subtitle) {
      const p = document.createElement('p')
      p.textContent = menu.subtitle
      p.style.cssText = `font-family:${this._style.fontFamily};font-size:12px;color:${this._style.subtitleColor};margin:0 0 10px;text-align:center;`
      inner.appendChild(p)
    }

    for (const btn of (menu.buttons || [])) {
      inner.appendChild(this._makeButton(menu.id, btn))
    }
    return outer
  }

  _makeButton(menuId, btn) {
    const el = document.createElement('button')
    el.textContent = btn.label
    const bg = this._style.buttonIdleTex
      ? `background-image:url('assets/${this._style.buttonIdleTex}');background-size:100% 100%;background-color:transparent;`
      : 'background:#333;border:1px solid #777;'
    el.style.cssText = [
      bg.replace(/;$/, ''),
      'border:none',
      'width:200px',
      'height:58px',
      `font-family:${this._style.fontFamily}`,
      'font-size:14px',
      'letter-spacing:1px',
      `color:${this._style.titleColor}`,
      'cursor:pointer',
      'transition:filter 120ms ease-out',
      'filter:brightness(1)'
    ].join(';')
    el.addEventListener('mouseenter', () => {
      el.style.filter = 'brightness(1.35) drop-shadow(0 0 6px rgba(120,200,230,0.55))'
    })
    el.addEventListener('mouseleave', () => { el.style.filter = 'brightness(1)' })
    el.addEventListener('click', () => this._handleAction(menuId, btn.action))
    return el
  }

  _handleAction(menuId, action) {
    if (typeof action === 'function') return action(this)
    switch (action) {
      case 'resume':  return this.hideMenu(menuId)
      case 'restart': return window.location.reload()
      case 'quit':    return window.location.reload()
      default:        console.warn(`GameOverlayModule: unknown action '${action}'`)
    }
  }

  _makeDiv(id, style) {
    const d = document.createElement('div')
    d.id = id
    d.style.cssText = style
    this._container.appendChild(d)
    return d
  }

  runtimeState() {
    const visible = {}
    for (const [id, entry] of this._menuDivs) {
      visible[id] = entry.div.style.display !== 'none'
    }
    return { visible, hurtFlashVisible: this._hurtFlashDiv?.style.display === 'block' }
  }

  destroy() {
    if (this._onKeyDown) window.removeEventListener('keydown', this._onKeyDown)
    this._hurtFlashDiv?.remove()
    for (const [_, entry] of this._menuDivs) entry.div?.remove()
    this._menuDivs.clear()
    this._toggleKeyMap.clear()
  }
}
