import { Node } from '/engine/Node.js'
import { extractFrameDataUrl } from './AtlasUtils.js'

export default class HudRenderer extends Node {
  ready() {
    const container = document.getElementById('game-container')
    const c = this.config ?? {}
    this._container = container
    this._logicalWidth = c.logicalWidth ?? Number(this.scene?.game?.config?.width) ?? 960
    this._logicalHeight = c.logicalHeight ?? Number(this.scene?.game?.config?.height) ?? 540
    this._scaleMode = c.scaleMode ?? 'stretch'
    this._lastContainerW = 0
    this._lastContainerH = 0
    this._intentOffsetX = c.intentOffsetX ?? -55
    this._intentOffsetY = c.intentOffsetY ?? -36
    this._enemyStatusOffsetX = c.enemyStatusOffsetX ?? -30
    this._enemyStatusOffsetY = c.enemyStatusOffsetY ?? 4
    this._enemyHpOffsetX = c.enemyHpOffsetX ?? -90
    this._enemyHpOffsetY = c.enemyHpOffsetY ?? -8
    this._enemyHpWidth = c.enemyHpWidth ?? 180
    this._enemyHpScale = c.enemyHpScale ?? 0.5
    this._enemyIntentGap = c.enemyIntentGap ?? 12
    this._enemyIntentSideOffsetY = c.enemyIntentSideOffsetY ?? 14
    this._playerCombatOffsetX = c.playerCombatOffsetX ?? -55

    // Extract all HUD icon data URLs from the hud_icons atlas
    const I = {}
    const ICON_KEYS = [
      'heart_hp', 'coin_eds', 'intent_attack', 'intent_defense',
      'energy_crystal', 'status_vulnerable', 'status_block',
      'portrait_player', 'settings_gear'
    ]
    for (const k of ICON_KEYS) {
      I[k] = extractFrameDataUrl(this.scene, 'hud_icons', k, 28)
    }
    // Portrait needs larger extraction for the 44px circle
    const portraitUrl = extractFrameDataUrl(this.scene, 'hud_icons', 'portrait_player', 80)
    this._iconUrls = I

    this._overlay = document.createElement('div')
    this._overlay.id = 'hud-overlay'
    this._root = document.createElement('div')
    this._root.id = 'hud-logical-root'
    this._root.style.width = `${this._logicalWidth}px`
    this._root.style.height = `${this._logicalHeight}px`
    this._root.innerHTML = `
      <div id="hud-player-info">
        <div id="hud-portrait">
          <img src="${portraitUrl}" style="width:80px;height:80px;border-radius:50%;object-fit:cover;">
        </div>
        <div id="hud-player-stats">
          <div id="hud-hp-text">
            <img src="${I.heart_hp}" style="height:32px;width:auto;vertical-align:middle;margin-right:6px;">
            <span id="hud-hp-value">80/80</span>
          </div>
          <div id="hud-eds-text">
            <img src="${I.coin_eds}" style="height:32px;width:auto;vertical-align:middle;margin-right:6px;">
            <span id="hud-eds-value">0</span>
          </div>
          <div id="hud-status-row"></div>
        </div>
      </div>
      <div id="hud-gear" title="Settings">
        <img src="${I.settings_gear}" style="width:22px;height:22px;">
      </div>
      <div id="hud-player-combat-status"></div>
      <div id="hud-enemy-intent"></div>
      <div id="hud-enemy-status"></div>
      <div id="hud-enemy-hp">
        <div id="hud-enemy-name">ENEMY</div>
        <div id="hud-enemy-hp-bar"><div id="hud-enemy-hp-fill"></div><span id="hud-enemy-hp-text">200/200</span></div>
      </div>
      <div id="hud-energy">
        <div id="hud-energy-row">
          <img src="${I.energy_crystal}" style="height:22px;width:auto;vertical-align:middle;margin-right:5px;">
          <span id="hud-energy-value">3/3</span>
        </div>
        <div id="hud-energy-label">ENERGY</div>
        <div id="hud-draw-count">5 DRAW</div>
      </div>
      <div id="hud-turn-info">
        <div id="hud-turn-label">TURN 1</div>
        <button id="hud-end-turn">END TURN</button>
        <div id="hud-discard-count">DISCARD 0</div>
      </div>

    `
    this._overlay.appendChild(this._root)
    container.appendChild(this._overlay)
    this._syncScale(true)

    this._endTurnBtn = this._overlay.querySelector('#hud-end-turn')
    if (this._endTurnCallback === undefined) this._endTurnCallback = null
    this._endTurnBtn.addEventListener('click', () => {
      if (!this._endTurnBtn.disabled) this._endTurnCallback?.()
    })
  }

  setEndTurnCallback(fn) { this._endTurnCallback = fn }

  update() {
    this._syncScale(false)
  }

  refresh(state) {
    const o = this._overlay
    if (!o) return

    o.querySelector('#hud-hp-value').textContent       = `${state.hp}/${state.hpMax}`
    o.querySelector('#hud-eds-value').textContent      = String(state.gold)
    o.querySelector('#hud-energy-value').textContent   = `${state.energy}/${state.energyMax}`
    o.querySelector('#hud-draw-count').textContent     = `${state.deckCount} DRAW`
    o.querySelector('#hud-discard-count').textContent  = `DISCARD ${state.discardCount}`
    o.querySelector('#hud-turn-label').textContent     = `TURN ${state.turn}`

    // Player top-left status badges stay empty; combat badges live near the characters.
    const statusRow = o.querySelector('#hud-status-row')
    statusRow.innerHTML = ''

    const playerCombatEl = o.querySelector('#hud-player-combat-status')
    const playerBadges = []
    if (state.block > 0) {
      playerBadges.push(`<span class="hud-combat-badge hud-block"><img src="${this._iconUrls.status_block}" style="height:28px;vertical-align:middle;margin-right:4px;">${state.block}</span>`)
    }
    if (state.vulnerable > 0) {
      playerBadges.push(`<span class="hud-combat-badge"><img src="${this._iconUrls.status_vulnerable}" style="height:28px;vertical-align:middle;margin-right:4px;">${state.vulnerable}</span>`)
    }
    playerCombatEl.innerHTML = playerBadges.join('')

    // END TURN button gating
    this._endTurnBtn.disabled = state.gamePhase !== 'playerTurn' || !!state.isResolvingAction

    // Enemy HP bar
    const enemyHpFill = o.querySelector('#hud-enemy-hp-fill')
    const enemyHpText = o.querySelector('#hud-enemy-hp-text')
    const enemyHpMax = Math.max(1, Number(state.enemyHpMax) || 1)
    const enemyHpRate = Math.max(0, Math.min(1, (Number(state.enemyHp) || 0) / enemyHpMax))
    enemyHpFill.style.width = `${enemyHpRate * 100}%`
    enemyHpText.textContent = `${state.enemyHp}/${state.enemyHpMax}`

    // Enemy intent
    const intentEl = o.querySelector('#hud-enemy-intent')
    if (state.enemyIntent) {
      const { type, value } = state.enemyIntent
      const iconKey = type === 'FORTIFY' ? 'intent_defense' : 'intent_attack'
      const iconUrl = this._iconUrls[iconKey] || ''
      const label   = type === 'FORTIFY' ? `+${value} BLK` : `${value} DMG`
      intentEl.innerHTML = `<img src="${iconUrl}" style="height:22px;width:auto;vertical-align:middle;margin-right:4px;"><span>${label}</span>`
    }

    // Enemy status badges
    const statusEl = o.querySelector('#hud-enemy-status')
    const badges = []
    if (state.enemyBlock > 0) {
      badges.push(`<span class="hud-combat-badge hud-block"><img src="${this._iconUrls.status_block}" style="height:28px;vertical-align:middle;margin-right:4px;">${state.enemyBlock}</span>`)
    }
    if (state.enemyVulnerable > 0) {
      badges.push(`<span class="hud-combat-badge"><img src="${this._iconUrls.status_vulnerable}" style="height:28px;vertical-align:middle;margin-right:4px;">${state.enemyVulnerable}</span>`)
    }
    statusEl.innerHTML = badges.join('')

    // Position enemy DOM overlays using enemy head world position.
    const enemy = this.findByTag('enemy')[0]
    const player = this.findByTag('player')[0]
    const enemyHpEl = o.querySelector('#hud-enemy-hp')
    if (enemy?.getHeadPosition) {
      const head = this._worldToDom(enemy.getHeadPosition())
      const combatY = head.y + this._intentOffsetY
      const hpLeft = head.x + this._enemyHpOffsetX
      const hpTop = head.y + this._enemyHpOffsetY
      const hpVisualRight = hpLeft + (this._enemyHpWidth * (1 + this._enemyHpScale)) / 2
      enemyHpEl.style.left = `${hpLeft}px`
      enemyHpEl.style.top  = `${hpTop}px`
      intentEl.style.left = `${hpVisualRight + this._enemyIntentGap}px`
      intentEl.style.top  = `${hpTop + this._enemyIntentSideOffsetY}px`
      statusEl.style.left = `${head.x + this._enemyStatusOffsetX}px`
      statusEl.style.top  = `${combatY}px`

      if (player?.getHeadPosition) {
        const playerHead = this._worldToDom(player.getHeadPosition())
        playerCombatEl.style.left = `${playerHead.x + this._playerCombatOffsetX}px`
        playerCombatEl.style.top = `${combatY}px`
      }
    }
  }

  _worldToDom(pos) {
    return { x: pos.x, y: pos.y }
  }

  _syncScale(force) {
    if (!this._container || !this._root) return
    const r = this._container.getBoundingClientRect()
    if (!force && r.width === this._lastContainerW && r.height === this._lastContainerH) return
    this._lastContainerW = r.width
    this._lastContainerH = r.height

    const sx = r.width / this._logicalWidth
    const sy = r.height / this._logicalHeight
    let scaleX = sx
    let scaleY = sy
    let offsetX = 0
    let offsetY = 0
    if (this._scaleMode === 'fit') {
      const s = Math.min(sx, sy)
      scaleX = s
      scaleY = s
      offsetX = (r.width - this._logicalWidth * s) * 0.5
      offsetY = (r.height - this._logicalHeight * s) * 0.5
    }
    this._root.style.transform = `translate(${offsetX}px, ${offsetY}px) scale(${scaleX}, ${scaleY})`
  }

  destroy() {
    this._overlay?.remove()
  }
}
