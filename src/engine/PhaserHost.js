/**
 * Creates and manages a Phaser.Game instance.
 * Delegates update to SceneTree.
 */

import { resourceUrl } from './url.js'
import { buildPlaceholderImageCanvas } from './placeholder.js'

// Framework-shipped placeholder assets for prototype-stage visuals.
// Atlas placeholder: 8x8 grid of 32x32 cells = 64 named frames.
// Image placeholder: static fallback image for image-type prototype entries.
const PLACEHOLDER_ATLAS_KEY = '__placeholder_atlas__'
const PLACEHOLDER_ATLAS_PATH = 'engine/assets/__placeholder_atlas__.png'
const PLACEHOLDER_IMAGE_KEY = '__placeholder_image__'
const PLACEHOLDER_IMAGE_PATH = 'engine/assets/__placeholder_image__.png'
const PLACEHOLDER_ATLAS_FRAME_SIZE = 32
const PLACEHOLDER_ATLAS_COLS = 8
const PLACEHOLDER_ATLAS_ROWS = 8

function placeholderFrameNames(entry) {
  if (Array.isArray(entry?.frames)) return entry.frames.map(String)
  if (entry?.sprites && typeof entry.sprites === 'object') return Object.keys(entry.sprites)
  return []
}

function buildPlaceholderAtlasData(key, entry) {
  const names = placeholderFrameNames(entry)
  const maxFrames = PLACEHOLDER_ATLAS_COLS * PLACEHOLDER_ATLAS_ROWS
  if (names.length > maxFrames) {
    console.warn(`placeholder_atlas "${key}" declares ${names.length} frames, but only ${maxFrames} unique placeholder cells exist.`)
  }
  const frames = {}
  for (let i = 0; i < Math.min(names.length, maxFrames); i++) {
    const col = i % PLACEHOLDER_ATLAS_COLS
    const row = Math.floor(i / PLACEHOLDER_ATLAS_COLS)
    const x = col * PLACEHOLDER_ATLAS_FRAME_SIZE
    const y = row * PLACEHOLDER_ATLAS_FRAME_SIZE
    const w = PLACEHOLDER_ATLAS_FRAME_SIZE
    const h = PLACEHOLDER_ATLAS_FRAME_SIZE
    frames[names[i]] = {
      frame: { x, y, w, h },
      rotated: false,
      trimmed: false,
      spriteSourceSize: { x: 0, y: 0, w, h },
      sourceSize: { w, h },
    }
  }
  return { frames }
}

function buildBuiltinPlaceholderAtlasData() {
  const maxFrames = PLACEHOLDER_ATLAS_COLS * PLACEHOLDER_ATLAS_ROWS
  return buildPlaceholderAtlasData(PLACEHOLDER_ATLAS_KEY, {
    frames: Array.from({ length: maxFrames }, (_, i) => `f${String(i).padStart(2, '0')}`),
  })
}

export class PhaserHost {
  game = null
  sceneTree = null
  phaserScene = null
  assetManifest = null  // { key: { type, path, ... } }
  assetBasePath = '/assets'
  rendererType = null   // null = Phaser.AUTO, or explicit Phaser.CANVAS/WEBGL
  fpsLimit = 0          // >0 caps update+render rate via Phaser fps.limit; 0 = follow rAF/display rate
  _pendingAtlases = {}  // key -> { frames } atlas data to register in create

  /**
   * @param {HTMLElement} container - DOM element to render into
   * @param {object} projectConfig - project.json content
   */
  init(container, projectConfig) {
    const self = this
    const settings = projectConfig.settings || {}

    // Logical resolution comes from settings, NOT container size. The Scale
    // Manager (mode below) is responsible for mapping logical -> physical
    // (display) pixels. Previously w/h were read from container.getBoundingClientRect(),
    // which silently overrode settings.width/height with whatever DOM size
    // the container happened to have, producing scenes whose coordinates
    // drifted across devices.
    const logicalW = settings.width || 800
    const logicalH = settings.height || 600

    const transparent = settings.transparent === true
    const bgColor = transparent ? undefined : (settings.backgroundColor || '#000000')

    this.game = new Phaser.Game({
      type: this.rendererType || Phaser.AUTO,
      parent: container,
      width: logicalW,
      height: logicalH,
      // fps.limit caps update+render inside Phaser's TimeStep; extra rAF wakeups
      // early-return. Without it Phaser renders at display refresh rate (see boot.js
      // resolveFpsLimit for the cascade). fps: undefined behaves as absent.
      fps: this.fpsLimit > 0 ? { limit: this.fpsLimit } : undefined,
      pixelArt: settings.pixelArt || false,
      backgroundColor: bgColor,
      transparent: transparent,
      scale: {
        mode: Phaser.Scale[settings.scaleMode] || Phaser.Scale.FIT,
        width: logicalW,
        height: logicalH,
        parent: container,
        autoCenter: Phaser.Scale.CENTER_BOTH,
      },
      physics: {
        default: 'arcade',
        arcade: {
          gravity: settings.physics?.gravity || { x: 0, y: 0 },
          debug: settings.physics?.debug || false,
        },
      },
      scene: {
        preload() { self.onPreload(this) },
        create() { self.onCreate(this) },
        update(time, delta) { self.onUpdate(time, delta) },
      },
    })
  }

  onPreload(phaserScene) {
    this.phaserScene = phaserScene
    this._pendingAtlases = {}

    phaserScene.load.image(PLACEHOLDER_ATLAS_KEY, resourceUrl(PLACEHOLDER_ATLAS_PATH))
    phaserScene.load.image(PLACEHOLDER_IMAGE_KEY, resourceUrl(PLACEHOLDER_IMAGE_PATH))
    this._pendingAtlases[PLACEHOLDER_ATLAS_KEY] = buildBuiltinPlaceholderAtlasData()

    if (!this.assetManifest) return
    const base = this.assetBasePath
    for (const [key, entry] of Object.entries(this.assetManifest)) {
      // Deprecated: spritesheet kept for backwards compatibility; new assets use atlas.
      if (entry.type === 'spritesheet') {
        const url = `${base}/${entry.path}?t=${Date.now()}`
        phaserScene.load.spritesheet(key, url, {
          frameWidth: entry.frameWidth,
          frameHeight: entry.frameHeight,
        })
      } else if (entry.type === 'placeholder_atlas') {
        phaserScene.load.image(key, resourceUrl(PLACEHOLDER_ATLAS_PATH))
        this._pendingAtlases[key] = buildPlaceholderAtlasData(key, entry)
      } else if (entry.type === 'placeholder_image') {
        if (phaserScene.textures.exists(key)) phaserScene.textures.remove(key)
        phaserScene.textures.addCanvas(key, buildPlaceholderImageCanvas(entry))
      } else if (entry.type === 'atlas' && entry.sprites) {
        // Load as image; named frames are registered in onCreate
        const url = `${base}/${entry.path}?t=${Date.now()}`
        phaserScene.load.image(key, url)
        const frames = {}
        for (const [name, sprite] of Object.entries(entry.sprites)) {
          const [x, y, w, h] = sprite.bbox
          frames[name] = {
            frame: { x, y, w, h },
            rotated: false,
            trimmed: false,
            spriteSourceSize: { x: 0, y: 0, w, h },
            sourceSize: { w, h },
          }
        }
        this._pendingAtlases[key] = { frames }
      } else if (entry.type === 'tileset') {
        if (entry.path) {
          const url = `${base}/${entry.path}?t=${Date.now()}`
          phaserScene.load.image(key, url)
        }
      } else {
        const url = `${base}/${entry.path}?t=${Date.now()}`
        phaserScene.load.image(key, url)
      }
    }
  }

  onCreate(phaserScene) {
    this.phaserScene = phaserScene

    // Register atlas frames on image textures loaded in preload
    for (const [key, atlasData] of Object.entries(this._pendingAtlases)) {
      const tex = phaserScene.textures.get(key)
      if (tex && tex.key !== '__MISSING') {
        Phaser.Textures.Parsers.JSONHash(tex, 0, atlasData)
      }
    }
    this._pendingAtlases = {}

    if (phaserScene.input?.keyboard) {
      phaserScene.input.keyboard.disableGlobalCapture()
    }
    if (this.onReady) this.onReady(phaserScene)
  }

  onUpdate(time, delta) {
    if (this.sceneTree) {
      this.sceneTree.update(time, delta)
    }
  }

  destroy() {
    if (this.sceneTree?.ui) {
      this.sceneTree.ui.destroy()
      this.sceneTree.ui = null
    }
    if (this.game) {
      this.game.destroy(true)
      this.game = null
    }
  }
}
