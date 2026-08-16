import { Node } from '/engine/Node.js'

// WeaponVisual: follows parent player with offset, aims toward mouse
export default class WeaponVisual extends Node {
  ready() {
    const c = this.config
    const visualCfg = this.findByTag('game_manager')[0]?.elementsConfig?.weaponVisual || {}
    this.offsetX = c.offsetX ?? visualCfg.defaultOffsetX
    this.offsetY = c.offsetY ?? visualCfg.defaultOffsetY
    if (this.gameObject) this.gameObject.setDepth(6)
    this._textureMap = {
      pistol: 'weapon_pistol',
      shotgun: 'weapon_shotgun',
      rifle: 'weapon_assault_rifle',
      assault_rifle: 'weapon_assault_rifle',
      rocket: 'weapon_rocket_launcher',
      rocket_launcher: 'weapon_rocket_launcher'
    }
    if (!this.parent?.weaponType && this.gameObject) {
      this.gameObject.setVisible(false)
    }
  }

  update(dt) {
    if (!this.gameObject || !this.parent) return

    const parentBody = this.parent.getPhysicsObject?.() || this.parent.gameObject
    const parentVisual = this.parent.getVisualObject?.() || parentBody
    if (!parentBody) return
    const px = parentBody.x
    const py = parentBody.y

    // Calculate offset based on parent flip
    let ox = this.offsetX
    if (parentVisual?.flipX) ox = -ox

    // Position weapon
    this.gameObject.setPosition(px + ox, py + this.offsetY)

    // Rotate toward mouse (aim direction)
    const pointer = this.scene.input.activePointer
    const angle = Phaser.Math.Angle.Between(px, py, pointer.worldX, pointer.worldY)
    // Sprite is muzzle-up (needs +PI/2 to align muzzle-right at angle=0).
    // Use flipX when aiming left so the visible side stays consistent.
    // The visual transition happens at ±PI/2 (gun vertical) — less noticeable.
    this.gameObject.setFlipX(Math.abs(angle) > Math.PI / 2)
    this.gameObject.setFlipY(false)
    this.gameObject.setRotation(angle + Math.PI / 2)
  }

  setWeaponType(type) {
    if (!this.gameObject) return
    if (!type) {
      this.gameObject.setVisible(false)
      return
    }
    const texKey = this._textureMap[type] || 'weapon_pistol'
    this.gameObject.setTexture(texKey)
    this.gameObject.setVisible(true)
  }

  getWorldPosition() {
    if (!this.gameObject) return { x: 0, y: 0 }
    return { x: this.gameObject.x, y: this.gameObject.y }
  }
}
