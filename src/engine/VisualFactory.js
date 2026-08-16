/**
 * Creates Phaser visual objects from NodeDef.visual field.
 * Supports: rect, image, atlas.
 * Deprecated: spritesheet kept for backwards compatibility; new assets use atlas.
 */

import { applyPivot } from './PivotResolver.js'

export const VisualFactory = {
  /**
   * Create a Phaser game object from a visual definition.
   * @param {Phaser.Scene} scene
   * @param {object} visualDef - { type, ... }
   * @param {object} config - node config (for x, y position)
   * @param {object} [assetManifest] - sceneTree.assetManifest for pivot resolution
   * @returns {Phaser.GameObjects.GameObject}
   */
  create(scene, visualDef, config, assetManifest) {
    const x = config.x || 0
    const y = config.y || 0
    const type = visualDef.type || 'rect'

    switch (type) {
      case 'rect':
        return this._createRect(scene, visualDef, x, y)
      case 'image':
        return this._createImage(scene, visualDef, x, y, assetManifest)
      // Deprecated: spritesheet kept for backwards compatibility; new assets use atlas.
      case 'spritesheet':
        return this._createSpritesheet(scene, visualDef, x, y, assetManifest)
      case 'atlas':
        return this._createAtlas(scene, visualDef, x, y, assetManifest)
      default:
        console.warn(`VisualFactory: unknown type "${type}"`)
        return null
    }
  },

  _createRect(scene, def, x, y) {
    const w = def.width || 32
    const h = def.height || 32
    const color = typeof def.color === 'string' ? parseInt(def.color) : (def.color || 0xffffff)
    return scene.add.rectangle(x, y, w, h, color)
  },

  _createImage(scene, def, x, y, assetManifest) {
    if (!def.texture || !scene.textures.exists(def.texture)) {
      console.error(`VisualFactory: texture "${def.texture}" not loaded. Add it to manifest.json. Falling back to rect.`)
      return scene.add.rectangle(x, y, def.width || 32, def.height || 32, 0xff00ff)
    }
    const sprite = scene.add.image(x, y, def.texture)
    applyPivot(sprite, assetManifest, def.texture, null, null)
    this.applyDisplaySize(sprite, def)
    return sprite
  },

  // Deprecated: spritesheet kept for backwards compatibility; new assets use atlas.
  _createSpritesheet(scene, def, x, y, assetManifest) {
    if (!def.texture || !scene.textures.exists(def.texture)) {
      console.error(`VisualFactory: texture "${def.texture}" not loaded. Add it to manifest.json. Falling back to rect.`)
      return scene.add.rectangle(x, y, def.width || 32, def.height || 32, 0xff00ff)
    }
    const frame = def.frame !== undefined ? def.frame : 0
    const sprite = scene.add.sprite(x, y, def.texture, frame)
    applyPivot(sprite, assetManifest, def.texture, null, null)
    this.applyDisplaySize(sprite, def)

    // Register animations
    if (def.animations) {
      for (const [name, anim] of Object.entries(def.animations)) {
        const animKey = `${def.texture}_${name}`
        if (!scene.anims.exists(animKey)) {
          scene.anims.create({
            key: animKey,
            frames: scene.anims.generateFrameNumbers(def.texture, { frames: anim.frames }),
            frameRate: anim.frameRate || 10,
            repeat: anim.loop !== false ? -1 : 0,
          })
        }
      }
      // Override play to auto-prefix
      const originalPlay = sprite.play.bind(sprite)
      sprite.play = (animName) => originalPlay(`${def.texture}_${animName}`)
    }

    return sprite
  },

  _createAtlas(scene, def, x, y, assetManifest) {
    if (!def.texture || !scene.textures.exists(def.texture)) {
      console.error(`VisualFactory: texture "${def.texture}" not loaded. Add it to manifest.json. Falling back to rect.`)
      return scene.add.rectangle(x, y, def.width || 32, def.height || 32, 0xff00ff)
    }
    const sprite = scene.add.sprite(x, y, def.texture, def.frame)
    applyPivot(sprite, assetManifest, def.texture, def.frame, null)
    this.applyDisplaySize(sprite, def)

    if (def.animations) {
      for (const [name, anim] of Object.entries(def.animations)) {
        const animKey = `${def.texture}_${name}`
        if (!scene.anims.exists(animKey)) {
          scene.anims.create({
            key: animKey,
            frames: anim.frames.map(f => ({ key: def.texture, frame: f })),
            frameRate: anim.frameRate || 10,
            repeat: anim.loop !== false ? -1 : 0,
          })
        }
      }
      const originalPlay = sprite.play.bind(sprite)
      sprite.play = (animName) => originalPlay(`${def.texture}_${animName}`)
    }

    return sprite
  },

  // width/height set displayed size for the currently bound frame, which also
  // establishes Phaser scale. AnimationPlayer uses this once for explicit size.
  applyDisplaySize(gameObject, def) {
    if (!def || !gameObject) return
    const hasWidth = def.width !== undefined
    const hasHeight = def.height !== undefined
    const hasRatio = def.ratio !== undefined

    if (hasRatio && (hasWidth || hasHeight)) {
      console.error('VisualFactory: visual.ratio cannot be combined with visual.width/height. Using width/height.')
    }

    if (hasWidth || hasHeight) {
      if (hasWidth) gameObject.displayWidth = def.width
      if (hasHeight) gameObject.displayHeight = def.height
      return
    }

    const ratio = Number(def.ratio)
    if (!Number.isFinite(ratio) || ratio <= 0) return
    const srcW = gameObject.frame?.realWidth || gameObject.width
    const srcH = gameObject.frame?.realHeight || gameObject.height
    if (srcW > 0) gameObject.displayWidth = srcW * ratio
    if (srcH > 0) gameObject.displayHeight = srcH * ratio
  },
}
