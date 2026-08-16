/**
 * Engine script: extra invisible collision object that tracks parent.
 * Used for attack hitboxes, trigger zones, pickup ranges, etc.
 * Config: startEnabled.
 * Collider shape/size comes from the `collider` field on the NodeDef.
 */

import { Node } from '../Node.js'
import { ColliderFactory } from '../ColliderFactory.js'

export default class Collider extends Node {
  _enabled = true
  _ownGameObject = false  // true when this script created the gameObject (not the engine)

  ready() {
    const c = this.config
    this._enabled = c.startEnabled !== false

    // Create invisible rectangle if engine didn't create a gameObject (no visual field)
    if (!this.gameObject) {
      const parentGO = this.parent?.gameObject
      const x = parentGO ? parentGO.x : (c.x || 0)
      const y = parentGO ? parentGO.y : (c.y || 0)

      const colliderDef = this._colliderDef || {}
      const w = colliderDef.width || c.width || 32
      const h = colliderDef.height || c.height || 32

      const rect = this.scene.add.rectangle(x, y, w, h)
      rect.setVisible(false)
      this.gameObject = rect
      this._ownGameObject = true

      // Apply collider config to the newly created gameObject
      if (this._colliderDef) {
        ColliderFactory.configure(this.scene, this.gameObject, this._colliderDef)
      }
    }

    // Apply initial enabled state
    if (!this._enabled) {
      this._setBodyActive(false)
    }
  }

  update(dt) {
    if (!this._enabled) return
    this._syncToParent()
  }

  /** Enable this collider (body becomes active). */
  enable() {
    this._enabled = true
    this._setBodyActive(true)
    this._syncToParent()
  }

  /** Disable this collider (body becomes inactive). */
  disable() {
    this._enabled = false
    this._setBodyActive(false)
  }

  /** @returns {boolean} current enabled state */
  isEnabled() {
    return this._enabled
  }

  /** @private */
  _setBodyActive(active) {
    const body = this.gameObject?.body
    if (body) {
      body.enable = active
    }
  }

  _syncToParent() {
    const parentGO = this.parent?.gameObject
    if (!this.gameObject || !parentGO) return

    this.gameObject.x = parentGO.x
    this.gameObject.y = parentGO.y
  }

  destroy() {
    // Only destroy gameObject if this script created it (engine-created ones are handled by SceneTree)
    if (this._ownGameObject && this.gameObject) {
      this.gameObject.destroy()
      this.gameObject = null
    }
  }
}
