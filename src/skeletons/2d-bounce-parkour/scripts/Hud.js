import { Node } from '/engine/Node.js'

/**
 * HUD overlay (Route 1 — DOM + CSS in the engine UI Layer).
 * Reads StageManager.runtimeState() each frame and updates 3 anchored divs:
 *   top-left = Stage label
 *   top-right = Tries / Best (multi-line)
 *   center = clear popup / final overlay (HTML supports <br> for multi-line)
 * Uses Press Start 2P pixel web font, monospace fallback.
 */

const PIXEL_FONT = "'Press Start 2P', monospace"
const STAGE_LABELS = {
  stage1: 'Stage 1',
  stage2: 'Stage 2',
  stage3: 'Stage 3',
}

export default class Hud extends Node {
  ready() {
    const ui = this.sceneTree.ui
    if (!ui) throw new Error('Hud requires sceneTree.ui')
    this._root = document.createElement('div')
    Object.assign(this._root.style, {
      position: 'absolute',
      top: '0', left: '0', right: '0', bottom: '0',
      pointerEvents: 'none',
      fontFamily: PIXEL_FONT,
      color: '#ffffff',
      textShadow: '2px 2px 0 rgba(0,0,0,0.85)',
      letterSpacing: '0',
      zIndex: '10',
    })

    this._stage = document.createElement('div')
    Object.assign(this._stage.style, {
      position: 'absolute', top: '12px', left: '16px',
      fontSize: '16px',
    })
    this._stage.textContent = ''

    this._tries = document.createElement('div')
    Object.assign(this._tries.style, {
      position: 'absolute', top: '12px', right: '16px',
      fontSize: '11px', textAlign: 'right', lineHeight: '1.6',
    })

    this._center = document.createElement('div')
    Object.assign(this._center.style, {
      position: 'absolute',
      top: '50%', left: '50%',
      transform: 'translate(-50%, -50%)',
      fontSize: '14px',
      textAlign: 'center', lineHeight: '1.8',
      padding: '16px 28px',
      background: 'rgba(0,0,0,0.55)',
      borderRadius: '6px',
      display: 'none',
    })

    this._root.appendChild(this._stage)
    this._root.appendChild(this._tries)
    this._root.appendChild(this._center)
    ui.mount(this._root)

    this._lastStage = null
    this._lastTriesHtml = ''
    this._lastCenterHtml = ''
  }

  update(dt) {
    const mgr = this.parent
    if (!mgr || typeof mgr.runtimeState !== 'function') return
    const s = mgr.runtimeState()

    const label = STAGE_LABELS[s.stage] || ''
    if (label !== this._lastStage) {
      this._stage.textContent = label
      this._lastStage = label
    }

    const bestText = s.best != null ? s.best : '-'
    const triesHtml = `Tries: ${s.tries}<br>Best: ${bestText}`
    if (triesHtml !== this._lastTriesHtml) {
      this._tries.innerHTML = triesHtml
      this._lastTriesHtml = triesHtml
    }

    // centerHtml wins over centerText (used for multi-line final overlay).
    const html = s.centerHtml || (s.centerText ? this._escape(s.centerText) : '')
    if (html !== this._lastCenterHtml) {
      this._center.innerHTML = html
      this._center.style.display = html ? 'block' : 'none'
      this._lastCenterHtml = html
    }
  }

  _escape(str) {
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
  }

  destroy() {
    if (this._root?.parentNode) this._root.parentNode.removeChild(this._root)
    this._root = null
  }
}
