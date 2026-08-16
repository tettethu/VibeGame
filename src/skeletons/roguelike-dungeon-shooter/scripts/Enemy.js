import { Node, generateId } from '/engine/Node.js'
import CoinOrb from './CoinOrb.js'
import ManaOrb from './ManaOrb.js'
import WeaponDrop from './WeaponDrop.js'

// Enemy base: hp, damage, death, drops
export default class Enemy extends Node {
  _initEnemy(cfg) {
    const hpBarCfg = this.findByTag('game_manager')[0]?.elementsConfig?.enemyHpBar || {}
    const hpMultiplier = cfg.hpMultiplier || 1
    this.hp = Math.round((cfg.hp || 30) * hpMultiplier)
    this.maxHP = this.hp
    this._dead = false
    if (this.gameObject) this.gameObject.setDepth(5)

    const defaultWidth = hpBarCfg.defaultWidth
    const displayWidthInset = hpBarCfg.displayWidthInset
    const backgroundHeight = hpBarCfg.backgroundHeight
    const height = hpBarCfg.height
    this._hpBarOffsetY = hpBarCfg.offsetY

    this._hpBarFullW = cfg.hpBarWidth || Math.max(defaultWidth, (this.gameObject?.displayWidth || defaultWidth) - displayWidthInset)
    this._hpBg = this.scene.add.rectangle(0, 0, this._hpBarFullW, backgroundHeight, 0x2a1315, 0.95)
      .setOrigin(0, 0.5)
      .setStrokeStyle(1, 0x090405, 1)
      .setDepth(10)
    this._hpBar = this.scene.add.rectangle(0, 0, this._hpBarFullW, height, 0xf05a5a, 1)
      .setOrigin(0, 0.5)
      .setDepth(11)
  }

  takeDamage(dmg, isCrit = false) {
    if (this._dead || this._dormant) return
    this.hp = Math.max(0, this.hp - dmg)
    this._updateHpBar()
    this._showDamageNumber(dmg, isCrit)
    if (this.hp <= 0) this._die()
  }

  _updateHpBar() {
    if (!this.gameObject || !this._hpBar) return
    const ratio = Math.max(0, this.hp / this.maxHP)
    const x = this.gameObject.x - this._hpBarFullW / 2
    const y = this.gameObject.y - this.gameObject.displayHeight / 2 - this._hpBarOffsetY
    this._hpBg.setPosition(x, y)
    this._hpBar.setPosition(x, y)
    this._hpBar.width = this._hpBarFullW * ratio
  }

  _showDamageNumber(dmg, isCrit = false) {
    if (!this.gameObject) return
    const cam = this.scene.cameras.main
    const sx = (this.gameObject.x - cam.scrollX) * cam.zoom
    const sy = (this.gameObject.y - cam.scrollY) * cam.zoom - 20
    const el = document.createElement('div')
    el.className = 'dmg-number'
    if (isCrit) el.classList.add('crit')
    el.textContent = isCrit ? `-${dmg}!` : `-${dmg}`
    el.style.left = sx + 'px'
    el.style.top = sy + 'px'
    this.sceneTree.ui.mount(el)
    setTimeout(() => el.remove(), 820)
  }

  _die() {
    if (this._dead) return
    this._dead = true

    if (!this._isBossMinion) {
      const wm = this.findByTag('wave_manager')[0]
      if (wm) wm.onEnemyDied()
    }

    this._dropCoinOrb()
    this._dropManaOrb()

    // Stage 1 baseline: disable weapon drops in combat
    // const gm = this.findByTag('game_manager')[0]
    // const dropChance = gm?.wavesConfig?.weaponDropChance || 0.3
    // if (Math.random() < dropChance) this._dropWeapon()

    this.scene.time.delayedCall(0, () => this.removeSelf())
  }

  _dropCoinOrb() {
    const gm = this.findByTag('game_manager')[0]
    if (!gm) return
    const coin = new CoinOrb()
    coin.id = generateId()
    coin.config = {
      x: this.gameObject.x + (Math.random() - 0.5) * 16,
      y: this.gameObject.y + (Math.random() - 0.5) * 16,
      coinValue: 1
    }
    gm.addChild(coin)
  }

  _dropManaOrb() {
    const gm = this.findByTag('game_manager')[0]
    if (!gm) return
    const mana = new ManaOrb()
    mana.id = generateId()
    mana.config = {
      x: this.gameObject.x + (Math.random() - 0.5) * 16,
      y: this.gameObject.y + (Math.random() - 0.5) * 16,
      manaValue: Phaser.Math.Between(10, 20)
    }
    gm.addChild(mana)
  }

  _dropWeapon() {
    const gm = this.findByTag('game_manager')[0]
    if (!gm || !gm.weaponsConfig) return
    const types = Object.keys(gm.weaponsConfig)
    const type = types[Math.floor(Math.random() * types.length)]
    const wd = gm.weaponsConfig[type]
    const drop = new WeaponDrop()
    drop.id = generateId()
    drop.config = {
      x: this.gameObject.x,
      y: this.gameObject.y + 10,
      weaponType: type,
      weaponData: wd,
      name: wd.name
    }
    gm.addChild(drop)
  }

  _tickHpBar() {
    if (!this.gameObject || !this._hpBar || this._dead) return
    this._updateHpBar()
  }

  destroy() {
    if (this._hpBg) { this._hpBg.destroy(); this._hpBg = null }
    if (this._hpBar) { this._hpBar.destroy(); this._hpBar = null }
    // engine handles gameObject cleanup in declarative mode
  }
}
