import { Node } from '/engine/Node.js'

// Chest: start-room chest that grants a weapon on E press when nearby
// Flow: walk near -> chest opens + "E 拾取" prompt -> press E -> weapon granted, chest stays
export default class Chest extends Node {
  ready() {
    const c = this.config
    this._weaponType = c.weaponType || 'pistol'
    this._triggerRange = c.triggerRange || 48
    this._opened = false
    this._granted = false
    this._playerNear = false
    this._weaponIcon = null
    this._prompt = null
    if (this.gameObject) this.gameObject.setDepth(2)
  }

  update(dt) {
    if (this._granted) return
    const players = this.findByTag('player')
    if (players.length === 0 || !this.gameObject) return
    const player = players[0]
    if (!player.gameObject) return

    const dx = this.gameObject.x - player.gameObject.x
    const dy = this.gameObject.y - player.gameObject.y
    const dist = Math.sqrt(dx * dx + dy * dy)
    const near = dist <= this._triggerRange

    // Open chest when player first enters range
    if (near && !this._opened) {
      this._openChest()
    }

    // Show/hide prompt
    if (near !== this._playerNear) {
      this._playerNear = near
      this._setPrompt(near && this._opened)
    }

    // E key to grant weapon
    if (near && this._opened && this.sceneTree.inputMap?.isPressed('interact')) {
      this._grantWeapon()
    }
  }

  _openChest() {
    if (this._opened) return
    this._opened = true
    const go = this.gameObject
    go.setTexture('chest', 'chest_open_r')

    const gm = this.findByTag('game_manager')[0]
    const cfg = gm?.elementsConfig?.chest || {}

    this.scene.tweens.add({
      targets: go,
      y: go.y + (cfg.bounceY ?? -8),
      duration: 120,
      yoyo: true,
      ease: 'Quad.easeOut'
    })

    // Floating weapon icon above chest
    const texMap = {
      pistol: 'weapon_pistol',
      shotgun: 'weapon_shotgun',
      rifle: 'weapon_assault_rifle',
      rocket: 'weapon_rocket_launcher'
    }
    const iconTex = texMap[this._weaponType] || 'weapon_pistol'
    const icon = this.scene.add.image(go.x, go.y + (cfg.iconOffsetY ?? -28), iconTex)
      .setAlpha(0)
      .setDisplaySize(cfg.iconWidth ?? 20, cfg.iconHeight ?? 40)
      .setRotation((cfg.iconRotationDeg ?? 90) * Math.PI / 180)
      .setDepth(3)
    this._weaponIcon = icon

    this.scene.tweens.add({
      targets: icon,
      y: icon.y + (cfg.iconFloatY ?? -12),
      alpha: 1,
      duration: 350,
      ease: 'Back.easeOut'
    })
  }

  _setPrompt(visible) {
    if (visible && !this._prompt && this.gameObject) {
      const cfg = this.findByTag('game_manager')[0]?.elementsConfig?.chest || {}
      this._prompt = this.scene.add.text(
        this.gameObject.x, this.gameObject.y + (cfg.promptOffsetY ?? -52),
        'E 拾取', {
          fontFamily: 'Pixelify Sans',
          fontSize: '12px',
          fill: '#ffffff',
          stroke: '#000000',
          strokeThickness: 2
        }
      ).setOrigin(0.5, 1).setDepth(4)
    } else if (!visible && this._prompt) {
      this._prompt.destroy()
      this._prompt = null
    }
  }

  _grantWeapon() {
    if (this._granted) return
    this._granted = true

    const gm = this.findByTag('game_manager')[0]
    const players = this.findByTag('player')
    if (!gm || players.length === 0) return

    const player = players[0]
    const data = gm.weaponsConfig[this._weaponType]
    player.pickupWeapon(this._weaponType, data)

    // Fade out floating icon and prompt (chest stays open)
    if (this._weaponIcon) {
      const fadeY = gm?.elementsConfig?.chest?.pickupFadeY ?? -20
      this.scene.tweens.add({
        targets: this._weaponIcon,
        alpha: 0,
        y: this._weaponIcon.y + fadeY,
        duration: 300,
        onComplete: () => { this._weaponIcon?.destroy(); this._weaponIcon = null }
      })
    }
    if (this._prompt) {
      this._prompt.destroy()
      this._prompt = null
    }
  }

  destroy() {
    this._prompt?.destroy()
    this._weaponIcon?.destroy()
  }
}
