import { Node } from '/engine/Node.js'
import Minimap from './Minimap.js'

// HUD: DOM-based UI overlay with stats panel (left top) + coins (right top)
export default class HUD extends Node {
  ready() {
    this.tags = ['hud']
    this._weaponIconCache = new Map()
    this._introGuide = null
    this._introTimer = null
    this._introCleanupTimer = null
    this._pauseOverlay = null
    this._pauseResumeHandler = null

    const ui = this.sceneTree.ui
    if (!ui) throw new Error('HUD requires sceneTree.ui')
    const asset = (key) => ui.assetUrl(key)
    const overlay = document.createElement('div')
    overlay.id = 'hud-overlay'
    overlay.style.setProperty('--hud-panel-image', `url(${JSON.stringify(asset('hud_panel_nb_pixel'))})`)
    overlay.innerHTML = `
      <div id="hud-stats">
        <div class="hud-stat-row">
          <img class="hud-stat-icon" src="${asset('icon_heart_nb_pixel')}" alt="HP">
          <div class="hud-stat-bar">
            <img id="hud-hp-fill" class="hud-stat-fill" src="${asset('hud_bar_hp_nb_pixel')}" alt="">
            <span id="hud-hp-text" class="hud-stat-bar-text hp-color">5 / 5</span>
          </div>
        </div>
        <div class="hud-stat-row">
          <img class="hud-stat-icon" src="${asset('icon_shield_nb_pixel')}" alt="Shield">
          <div class="hud-stat-bar">
            <img id="hud-shield-fill" class="hud-stat-fill" src="${asset('hud_bar_shield_nb_pixel')}" alt="">
            <span id="hud-shield-text" class="hud-stat-bar-text shield-color">5 / 5</span>
          </div>
        </div>
        <div class="hud-stat-row">
          <img class="hud-stat-icon hud-stat-icon-mana" src="${asset('icon_energy_nb_pixel')}" alt="Mana">
          <div class="hud-stat-bar">
            <img id="hud-mana-fill" class="hud-stat-fill" src="${asset('hud_bar_energy_nb_pixel')}" alt="">
            <span id="hud-mana-text" class="hud-stat-bar-text mana-color">200 / 200</span>
          </div>
        </div>
      </div>
      <div id="hud-weapons" style="display:none">
        <div class="hud-weapon-row" id="hud-weapon-slot1" style="display:none">
          <canvas id="hud-weapon-icon" class="hud-weapon-icon" width="42" height="20"></canvas>
          <div class="hud-weapon-mana">
            <img id="hud-weapon-mana-icon" class="hud-weapon-mana-icon" src="${asset('icon_energy_nb_pixel')}" alt="Mana Cost">
            <span id="hud-weapon-mana-text" class="hud-weapon-mana-text">0</span>
          </div>
        </div>
        <div class="hud-weapon-row hud-weapon-row2" id="hud-weapon-slot2" style="display:none">
          <canvas id="hud-weapon-icon2" class="hud-weapon-icon" width="42" height="20"></canvas>
          <div class="hud-weapon-mana">
            <img id="hud-weapon-mana-icon2" class="hud-weapon-mana-icon" src="${asset('icon_energy_nb_pixel')}" alt="Mana Cost">
            <span id="hud-weapon-mana-text2" class="hud-weapon-mana-text">0</span>
          </div>
        </div>
      </div>
      <div id="hud-top-right">
        <div id="hud-coins">
          <img class="hud-coin-icon" src="${asset('icon_coin')}" alt="Coins">
          <span id="hud-coins-text">0</span>
        </div>
      </div>
      <div id="hud-bottom">
        <div id="hud-boss-label">BOSS</div>
        <div class="hud-bar-track">
          <div id="hud-boss-fill" class="hud-bar-fill boss" style="width:100%"></div>
          <div id="hud-boss-text" class="hud-bar-text">100%</div>
        </div>
      </div>
      <div id="hud-notify"></div>
    `
    ui.mount(overlay)

    // Cache DOM refs
    this._hpText = document.getElementById('hud-hp-text')
    this._hpFill = document.getElementById('hud-hp-fill')
    this._shieldText = document.getElementById('hud-shield-text')
    this._shieldFill = document.getElementById('hud-shield-fill')
    this._manaText = document.getElementById('hud-mana-text')
    this._manaFill = document.getElementById('hud-mana-fill')
    this._coinsText = document.getElementById('hud-coins-text')
    this._weaponContainer = document.getElementById('hud-weapons')
    this._weaponSlot1El = document.getElementById('hud-weapon-slot1')
    this._weaponIcon = document.getElementById('hud-weapon-icon')
    this._weaponIconCtx = this._weaponIcon?.getContext('2d')
    this._weaponManaText = document.getElementById('hud-weapon-mana-text')
    this._weaponIcon2 = document.getElementById('hud-weapon-icon2')
    this._weaponIconCtx2 = this._weaponIcon2?.getContext('2d')
    this._weaponManaText2 = document.getElementById('hud-weapon-mana-text2')
    this._weaponSlot2El = document.getElementById('hud-weapon-slot2')
    this._bossContainer = document.getElementById('hud-bottom')
    this._bossLabel = document.getElementById('hud-boss-label')
    this._bossFill = document.getElementById('hud-boss-fill')
    this._bossText = document.getElementById('hud-boss-text')
    this._notify = document.getElementById('hud-notify')
    this._notifyTimer = null

    this._minimap = new Minimap(
      document.getElementById('hud-top-right'),
      ui
    )
  }

  showIntroGuide(duration = 2400) {
    this.hideIntroGuide()
    const card = document.createElement('div')
    card.id = 'intro-guide'
    card.innerHTML = `
      <div class="guide-card">
        <div class="guide-title">操作指南</div>
        <div class="guide-subtitle">先拿武器, 再清空房间. 注意翻滚和暂停键.</div>
        <div class="guide-grid">
          ${this._controlsMarkup()}
        </div>
      </div>
    `
    this.sceneTree.ui.mount(card)
    this._introGuide = card

    requestAnimationFrame(() => card.classList.add('is-visible'))
    this._introTimer = setTimeout(() => {
      if (!this._introGuide) return
      this._introGuide.classList.remove('is-visible')
      this._introCleanupTimer = setTimeout(() => this.hideIntroGuide(), 260)
    }, duration)
  }

  hideIntroGuide() {
    if (this._introTimer) {
      clearTimeout(this._introTimer)
      this._introTimer = null
    }
    if (this._introCleanupTimer) {
      clearTimeout(this._introCleanupTimer)
      this._introCleanupTimer = null
    }
    if (this._introGuide) {
      this._introGuide.remove()
      this._introGuide = null
    }
  }

  showPauseOverlay(onResume) {
    this.hideIntroGuide()
    this.hidePauseOverlay()
    this._pauseResumeHandler = onResume || null

    const overlay = document.createElement('div')
    overlay.id = 'pause-overlay'
    overlay.innerHTML = `
      <div class="pause-panel">
        <div class="pause-kicker">Pause</div>
        <div class="pause-title">已暂停</div>
        <div class="pause-subtitle">按 Esc 继续, 或先看一眼当前操作.</div>
        <div class="pause-grid">
          ${this._controlsMarkup(true)}
        </div>
        <div class="pause-actions">
          <button class="pause-btn">继续游戏</button>
        </div>
      </div>
    `
    overlay.querySelector('.pause-btn')?.addEventListener('click', () => {
      this._pauseResumeHandler?.()
    })
    this.sceneTree.ui.mount(overlay)
    this._pauseOverlay = overlay
  }

  hidePauseOverlay() {
    if (this._pauseOverlay) {
      this._pauseOverlay.remove()
      this._pauseOverlay = null
    }
    this._pauseResumeHandler = null
  }

  _controlsMarkup(usePauseTone = false) {
    const items = [
      ['WASD', '移动'],
      ['Mouse', '瞄准和射击'],
      ['Space', '翻滚'],
      ['E', '拾取或交换'],
      ['F', '切换武器'],
      ['Esc', usePauseTone ? '继续或暂停' : '暂停']
    ]
    return items.map(([key, label]) => `
      <div class="guide-item">
        <div class="guide-key">${key}</div>
        <div class="guide-label">${label}</div>
      </div>
    `).join('')
  }

  initMinimap(layout, roomData) {
    this._minimap.init(layout, roomData)
  }

  updateMinimap(currentRoom, exploredRooms) {
    this._minimap.update(currentRoom, exploredRooms)
  }

  updateHP(hp, maxHP) {
    if (this._hpText) this._hpText.textContent = `${hp} / ${maxHP}`
    this._setBarRatio(this._hpFill, maxHP > 0 ? hp / maxHP : 0)
  }

  updateShield(shield, maxShield) {
    if (this._shieldText) this._shieldText.textContent = `${shield} / ${maxShield}`
    this._setBarRatio(this._shieldFill, maxShield > 0 ? shield / maxShield : 0)
  }

  updateMana(mana, maxMana) {
    if (this._manaText) this._manaText.textContent = `${mana} / ${maxMana}`
    this._setBarRatio(this._manaFill, maxMana > 0 ? mana / maxMana : 0)
  }

  flashMana() {
    if (!this._manaFill) return
    this._manaFill.classList.add('mana-flash')
    setTimeout(() => {
      if (this._manaFill) this._manaFill.classList.remove('mana-flash')
    }, 300)
  }

  updateCoins(coins) {
    if (this._coinsText) this._coinsText.textContent = coins
  }

  _setBarRatio(el, ratio) {
    if (!el) return
    const clamped = Math.max(0, Math.min(1, ratio || 0))
    el.style.clipPath = `inset(0 ${100 - clamped * 100}% 0 0)`
  }

  showBossPhase() {
    if (this._bossLabel) this._bossLabel.textContent = 'BOSS - PHASE 1'
  }

  showBossPhase2() {
    if (this._bossLabel) {
      this._bossLabel.textContent = 'BOSS - PHASE 2'
      this._bossLabel.style.color = '#ff2222'
    }
  }

  updateBossHP(hp, maxHP, phase) {
    if (!this._bossFill) return
    this._bossContainer.style.display = 'block'
    const ratio = Math.max(0, hp / maxHP) * 100
    this._bossFill.style.width = ratio + '%'
    if (this._bossText) this._bossText.textContent = `${Math.ceil(hp)} / ${maxHP}`
    if (phase >= 2) {
      this._bossFill.classList.add('phase2')
    } else {
      this._bossFill.classList.remove('phase2')
    }
  }

  hideBossHP() {
    if (this._bossContainer) this._bossContainer.style.display = 'none'
  }

  updateWeapon(type, data) {
    if (!type) {
      if (this._weaponSlot1El) this._weaponSlot1El.style.display = 'none'
      if (this._weaponManaText) this._weaponManaText.textContent = '0'
      this._syncWeaponVisibility()
      return
    }
    if (this._weaponSlot1El) this._weaponSlot1El.style.display = ''
    const iconKey = this._iconKey(type)
    this._drawWeaponIconTo(this._weaponIconCtx, this._weaponIcon, this.sceneTree.ui.assetUrl(iconKey))
    if (this._weaponManaText) this._weaponManaText.textContent = String(data?.manaCost ?? 0)
    this._syncWeaponVisibility()
  }

  updateWeapon2(type, data) {
    if (!type) {
      if (this._weaponSlot2El) this._weaponSlot2El.style.display = 'none'
      if (this._weaponManaText2) this._weaponManaText2.textContent = '0'
      this._syncWeaponVisibility()
      return
    }
    if (this._weaponSlot2El) this._weaponSlot2El.style.display = ''
    const iconKey = this._iconKey(type)
    this._drawWeaponIconTo(this._weaponIconCtx2, this._weaponIcon2, this.sceneTree.ui.assetUrl(iconKey))
    if (this._weaponManaText2) this._weaponManaText2.textContent = String(data?.manaCost ?? 0)
    this._syncWeaponVisibility()
  }

  _syncWeaponVisibility() {
    if (!this._weaponContainer) return
    const slot1Visible = !!this._weaponSlot1El && this._weaponSlot1El.style.display !== 'none'
    const slot2Visible = !!this._weaponSlot2El && this._weaponSlot2El.style.display !== 'none'
    this._weaponContainer.style.display = (slot1Visible || slot2Visible) ? '' : 'none'
  }

  _iconKey(type) {
    const iconMap = {
      pistol: 'weapon_pistol',
      shotgun: 'weapon_shotgun',
      rifle: 'weapon_assault_rifle',
      assault_rifle: 'weapon_assault_rifle',
      rocket: 'weapon_rocket_launcher',
      rocket_launcher: 'weapon_rocket_launcher',
    }
    return iconMap[type] || iconMap['pistol']
  }

  async _drawWeaponIcon(src) {
    this._drawWeaponIconTo(this._weaponIconCtx, this._weaponIcon, src)
  }

  async _drawWeaponIconTo(ctx, canvas, src) {
    if (!ctx || !canvas) return
    ctx.clearRect(0, 0, canvas.width, canvas.height)

    try {
      const img = await this._loadWeaponIcon(src)
      const maxLong = canvas.width * 0.86
      const maxShort = canvas.height * 0.72
      const scale = Math.min(maxLong / img.height, maxShort / img.width)
      const drawW = img.width * scale
      const drawH = img.height * scale

      ctx.save()
      ctx.imageSmoothingEnabled = false
      ctx.translate(canvas.width / 2, canvas.height / 2)
      ctx.rotate(Math.PI / 2)
      ctx.drawImage(img, -drawW / 2, -drawH / 2, drawW, drawH)
      ctx.restore()
    } catch {
      // Ignore icon draw failure and keep slot empty.
    }
  }

  _loadWeaponIcon(src) {
    if (this._weaponIconCache.has(src)) return this._weaponIconCache.get(src)

    const promise = new Promise((resolve, reject) => {
      const img = new Image()
      img.onload = () => resolve(img)
      img.onerror = reject
      img.src = src
    })
    this._weaponIconCache.set(src, promise)
    return promise
  }

  showNotify(msg, duration = 2000) {
    this._notify.textContent = msg
    this._notify.style.display = 'block'
    if (this._notifyTimer) clearTimeout(this._notifyTimer)
    this._notifyTimer = setTimeout(() => {
      this._notify.style.display = 'none'
    }, duration)
  }

  destroy() {
    this.hideIntroGuide()
    this.hidePauseOverlay()
    if (this._notifyTimer) clearTimeout(this._notifyTimer)
    if (this._minimap) { this._minimap.destroy(); this._minimap = null }
    document.getElementById('hud-overlay')?.remove()
  }
}
