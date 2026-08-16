import { Node } from '/engine/Node.js'

const ICON = {
  fire_rate: `<svg viewBox="0 0 16 16" shape-rendering="crispEdges" fill="currentColor"><path d="M10 1 H11 V2 H10 V4 H9 V6 H13 V7 H12 V9 H11 V10 H10 V12 H9 V14 H8 V15 H7 V14 H8 V12 H7 V10 H8 V9 H4 V8 H5 V6 H6 V5 H7 V3 H8 V1 H9 V2 H10 Z"/></svg>`,
  speed: `<svg viewBox="0 0 16 16" shape-rendering="crispEdges" fill="currentColor"><rect x="1" y="6" width="8" height="1"/><rect x="1" y="9" width="8" height="1"/><path d="M9 4 H10 V5 H11 V6 H12 V7 H13 V9 H12 V10 H11 V11 H10 V12 H9 V11 H8 V10 H9 V6 H8 V5 H9 Z"/><rect x="2" y="3" width="2" height="1"/><rect x="3" y="12" width="2" height="1"/></svg>`,
  max_hp: `<svg viewBox="0 0 16 16" shape-rendering="crispEdges" fill="currentColor"><path d="M3 3 H6 V4 H7 V5 H9 V4 H10 V3 H13 V4 H14 V8 H13 V9 H12 V10 H11 V11 H10 V12 H9 V13 H7 V12 H6 V11 H5 V10 H4 V9 H3 V8 H2 V4 H3 Z"/><path d="M6 5 H7 V6 H6 Z M9 5 H10 V6 H9 Z" fill="rgba(255,255,255,0.4)"/></svg>`,
  max_shield: `<svg viewBox="0 0 16 16" shape-rendering="crispEdges" fill="currentColor"><path d="M8 1 H9 V2 H10 V3 H11 V4 H13 V8 H12 V11 H11 V12 H10 V13 H9 V14 H7 V13 H6 V12 H5 V11 H4 V8 H3 V4 H5 V3 H6 V2 H7 V1 Z"/><path d="M7 5 H9 V8 H10 V9 H6 V8 H7 Z" fill="rgba(0,0,0,0.32)"/></svg>`,
  max_mana: `<svg viewBox="0 0 16 16" shape-rendering="crispEdges" fill="currentColor"><path d="M8 1 H9 V3 H10 V4 H11 V5 H12 V7 H13 V11 H12 V12 H11 V13 H10 V14 H6 V13 H5 V12 H4 V11 H3 V7 H4 V5 H5 V4 H6 V3 H7 V1 Z"/><path d="M6 6 H7 V8 H6 Z M7 5 H8 V6 H7 Z" fill="rgba(255,255,255,0.5)"/></svg>`,
  damage: `<svg viewBox="0 0 16 16" shape-rendering="crispEdges" fill="currentColor"><path d="M8 0 H9 V1 H10 V9 H6 V1 H7 V0 Z"/><rect x="4" y="9" width="8" height="1"/><rect x="6" y="10" width="4" height="3"/><rect x="5" y="13" width="6" height="1"/><path d="M7 2 H9 V8 H7 Z" fill="rgba(255,255,255,0.4)"/></svg>`,
  penetrate: `<svg viewBox="0 0 16 16" shape-rendering="crispEdges" fill="currentColor"><rect x="0" y="7" width="11" height="2"/><path d="M11 5 H12 V6 H13 V7 H14 V9 H13 V10 H12 V11 H11 Z"/><path d="M4 5 H7 V6 H8 V10 H7 V11 H4 V10 H3 V6 H4 Z" fill="none" stroke="currentColor" stroke-width="1"/><rect x="0" y="6" width="2" height="1" fill="rgba(255,255,255,0.5)"/><rect x="0" y="9" width="2" height="1" fill="rgba(255,255,255,0.5)"/></svg>`,
  double_shot: `<svg viewBox="0 0 16 16" shape-rendering="crispEdges" fill="currentColor"><rect x="1" y="3" width="9" height="2"/><path d="M10 1 H11 V2 H12 V3 H13 V5 H12 V6 H11 V7 H10 Z"/><rect x="1" y="11" width="9" height="2"/><path d="M10 9 H11 V10 H12 V11 H13 V13 H12 V14 H11 V15 H10 Z"/></svg>`
}

const BUFF_POOL = [
  { id: 'fire_rate',   label: '攻速 +20%',     desc: '射击速度提升 20%',         category: 'offense' },
  { id: 'speed',       label: '移速 +15%',     desc: '移动速度提升 15%',         category: 'utility' },
  { id: 'max_hp',      label: '最大 HP +1',    desc: '最大生命值增加并恢复 1',    category: 'defense' },
  { id: 'max_shield',  label: '最大盾牌 +1',   desc: '最大盾牌值增加并恢复 1',    category: 'defense' },
  { id: 'max_mana',    label: '最大法力 +20',  desc: '最大法力值增加并恢复 20',   category: 'utility' },
  { id: 'damage',      label: '伤害 +25%',     desc: '所有伤害提升 25%',         category: 'offense' },
  { id: 'penetrate',   label: '子弹穿透',      desc: '子弹可穿过 1 个敌人',       category: 'offense' },
  { id: 'double_shot', label: '双弹齐射',      desc: '每次射击额外发射 1 颗',     category: 'offense' }
]

export default class UpgradeUI extends Node {
  ready() {
    this.tags = ['upgrade_ui']
    this._visible = false
    this._overlay = null
    this._keyHandler = null
    this._options = []
  }

  show() {
    this._visible = true
    this._options = [...BUFF_POOL].sort(() => Math.random() - 0.5).slice(0, 3)

    const overlay = document.createElement('div')
    overlay.id = 'upgrade-overlay'
    overlay.innerHTML = `
      <div class="up-stage">
        <div class="up-header">
          <div class="up-eyebrow">CHAMBER CLEARED</div>
          <div class="up-title">强化选择</div>
          <div class="up-subtitle">选择一道祝福, 继续深入地牢</div>
        </div>
        <div class="up-cards">
          ${this._options.map((opt, i) => `
            <button class="up-card" data-idx="${i}" data-cat="${opt.category}" type="button">
              <div class="up-card-band"></div>
              <div class="up-card-icon">${ICON[opt.id] || ''}</div>
              <div class="up-card-label">${opt.label}</div>
              <div class="up-card-desc">${opt.desc}</div>
              <div class="up-card-key"><span>${i + 1}</span></div>
            </button>
          `).join('')}
        </div>
        <div class="up-footer">按 <kbd>1</kbd> <kbd>2</kbd> <kbd>3</kbd> 或点击卡片确认</div>
      </div>
    `
    overlay.querySelectorAll('.up-card').forEach(card => {
      card.addEventListener('click', () => this._select(parseInt(card.dataset.idx)))
    })

    this.sceneTree.ui.mount(overlay)
    this._overlay = overlay

    this._keyHandler = (e) => {
      if (!this._visible) return
      if (e.key === '1') this._flashAndSelect(0)
      else if (e.key === '2') this._flashAndSelect(1)
      else if (e.key === '3') this._flashAndSelect(2)
    }
    window.addEventListener('keydown', this._keyHandler)
  }

  _flashAndSelect(idx) {
    const card = this._overlay && this._overlay.querySelector(`.up-card[data-idx="${idx}"]`)
    if (card) card.classList.add('is-active')
    this._select(idx)
  }

  _select(idx) {
    if (!this._visible) return
    this._visible = false
    const opt = this._options[idx]
    if (!opt) return

    const players = this.findByTag('player')
    if (players.length > 0) players[0].applyBuff(opt.id)

    this._cleanup()

    const lm = this.findByTag('level_manager')[0]
    if (lm) lm.onUpgradeClosed()
  }

  _cleanup() {
    if (this._overlay) { this._overlay.remove(); this._overlay = null }
    if (this._keyHandler) { window.removeEventListener('keydown', this._keyHandler); this._keyHandler = null }
  }

  destroy() {
    this._cleanup()
  }
}
