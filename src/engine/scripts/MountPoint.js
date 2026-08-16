/**
 * Engine script: child-follows-parent with mount/unmount support.
 * Config: offsetX, offsetY, aimRotation, flipWithParent.
 */

import { Node } from '../Node.js'

export default class MountPoint extends Node {
  _mounted = null   // currently mounted child Node
  _offsetX = 0
  _offsetY = 0
  _aimRotation = false
  _flipWithParent = true

  ready() {
    const c = this.config
    this._offsetX = c.offsetX || 0
    this._offsetY = c.offsetY || 0
    this._aimRotation = c.aimRotation || false
    this._flipWithParent = c.flipWithParent !== false
  }

  update(dt) {
    if (!this._mounted || !this.parent?.gameObject) return

    const parentGO = this.parent.gameObject
    const px = parentGO.x
    const py = parentGO.y

    // Determine effective offset (flip X if parent is flipped)
    let ox = this._offsetX
    const oy = this._offsetY

    if (this._flipWithParent && parentGO.flipX) {
      ox = -ox
    }

    // Position the mounted child's gameObject
    const mountedGO = this._mounted.gameObject
    if (mountedGO) {
      mountedGO.x = px + ox
      mountedGO.y = py + oy

      // Rotate toward aim direction (mouse pointer)
      if (this._aimRotation) {
        const pointer = this.scene.input.activePointer
        mountedGO.setRotation(Phaser.Math.Angle.Between(px, py, pointer.worldX, pointer.worldY))
      }

      // Mirror flip if configured
      if (this._flipWithParent && mountedGO.setFlipX) {
        mountedGO.setFlipX(parentGO.flipX || false)
      }
    }
  }

  /**
   * Load a .node.json and instantiate as mounted child.
   * Removes any previously mounted node.
   * @param {string} src - path to .node.json
   * @returns {Promise<Node>}
   */
  async mount(src) {
    this.unmount()
    this._mounted = await this.instantiate(src)
    return this._mounted
  }

  /** Remove the currently mounted child node. */
  unmount() {
    if (this._mounted) {
      this._mounted.removeSelf()
      this._mounted = null
    }
  }

  /** @returns {Node|null} the currently mounted child */
  getMounted() {
    return this._mounted
  }

  destroy() {
    this.unmount()
  }
}
