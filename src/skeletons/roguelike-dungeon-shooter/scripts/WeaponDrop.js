import { Node } from '/engine/Node.js'

// Weapon pickup: weapon icon; press E when close to pick it up (DOM labels, no Phaser text)
export default class WeaponDrop extends Node {
  ready() {
    const c = this.config
    const gm = this.findByTag('game_manager')[0]
    const dropCfg = gm?.elementsConfig?.weaponDrop || {}
    this.weaponType = c.weaponType || 'pistol'
    this.weaponData = c.weaponData || {}
    const x = c.x || 0
    const y = c.y || 0
    this._labelOffsetY = dropCfg.labelOffsetY
    this._hintOffsetY = dropCfg.hintOffsetY
    this._pickupRange = dropCfg.pickupRange
    const { width, height } = this._resolveDisplaySize(gm, dropCfg)

    const texMap = {
      pistol: 'weapon_pistol',
      shotgun: 'weapon_shotgun',
      rifle: 'weapon_assault_rifle',
      assault_rifle: 'weapon_assault_rifle',
      rocket: 'weapon_rocket_launcher',
      rocket_launcher: 'weapon_rocket_launcher'
    }
    const tex = texMap[this.weaponType] || 'weapon_pistol'

    this.gameObject = this.scene.add.image(x, y, tex)
    this.gameObject.setDisplaySize(width, height)
    // Source art points the muzzle up; rotate PI/2 (90 deg clockwise) so it points right
    this.gameObject.setRotation(Math.PI / 2)
    this.scene.physics.add.existing(this.gameObject, true)

    this._label = document.createElement('div')
    this._label.className = 'world-label'
    this._label.textContent = c.name || ''
    this.sceneTree.ui.mount(this._label)

    this._hint = document.createElement('div')
    this._hint.className = 'world-hint'
    this._hint.textContent = '[E] 拾取'
    this.sceneTree.ui.mount(this._hint)

    this._nearPlayer = false
    this._triangle = null
  }

  _resolveDisplaySize(gm, dropCfg) {
    const playerDef = gm?.sceneTree?.nodeDefinitions?.['entities/player.node.json']
    const weaponVisual = playerDef?.children?.find(child => child.name === 'Weapon')?.visual || {}
    return {
      width: weaponVisual.width ?? dropCfg.defaultWidth,
      height: weaponVisual.height ?? dropCfg.defaultHeight
    }
  }

  _toScreen(wx, wy) {
    const cam = this.scene.cameras.main
    return {
      x: (wx - cam.scrollX) * cam.zoom,
      y: (wy - cam.scrollY) * cam.zoom
    }
  }

  update(dt) {
    if (!this.gameObject) return

    const gx = this.gameObject.x
    const gy = this.gameObject.y
    const s = this._toScreen(gx, gy)
    if (this._label) {
      this._label.style.left = s.x + 'px'
      this._label.style.top = (s.y - this._labelOffsetY) + 'px'
    }
    if (this._hint) {
      this._hint.style.left = s.x + 'px'
      this._hint.style.top = (s.y + this._hintOffsetY) + 'px'
    }

    const players = this.findByTag('player')
    if (players.length === 0) return
    const p = players[0]
    if (!p.gameObject) return
    const dx = p.gameObject.x - gx
    const dy = p.gameObject.y - gy
    const near = Math.sqrt(dx * dx + dy * dy) < this._pickupRange

    if (near !== this._nearPlayer) {
      this._nearPlayer = near
      if (this._hint) this._hint.style.display = near ? 'block' : 'none'
      this._setTriangle(near)
    }

    if (near && this.sceneTree.inputMap.isPressed('interact')) {
      if (p.pickupWeapon) p.pickupWeapon(this.weaponType, this.weaponData)
      this.scene.time.delayedCall(0, () => this.removeSelf())
    }
  }

  _setTriangle(show) {
    if (show && !this._triangle && this.gameObject) {
      const x = this.gameObject.x
      const y = this.gameObject.y - 22
      const g = this.scene.add.graphics().setDepth(10)
      g.fillStyle(0xffffff, 1)
      // Inverted triangle: apex at the bottom, base on top
      g.fillTriangle(-5, -6, 5, -6, 0, 0)
      g.x = x
      g.y = y
      this._triangle = g
    } else if (!show && this._triangle) {
      this._triangle.destroy()
      this._triangle = null
    }
  }

  destroy() {
    if (this._triangle) { this._triangle.destroy(); this._triangle = null }
    if (this._label) { this._label.remove(); this._label = null }
    if (this._hint) { this._hint.remove(); this._hint = null }
    if (this.gameObject) { this.gameObject.destroy(); this.gameObject = null }
  }
}
