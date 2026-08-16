import { Node } from '/engine/Node.js'

/**
 * ParallaxModule — a single scrolling parallax background layer.
 *
 * Creates a Phaser TileSprite from a texture (plain image or atlas frame),
 * pins it to a scroll factor so it drifts slower/faster than the camera, sets a
 * render depth, and optionally self-scrolls at a constant rate (for clouds /
 * water). One node = one depth layer; stack several (sky / far / near) as
 * sibling nodes with different scrollFactor + depth to build a parallax scene.
 *
 * It is a pure background primitive: no collision, no game state, no events.
 * Playable terrain must NOT live in a parallax layer — author that as its own
 * collider sprite or rastermap asset.
 *
 * Inputs (config on the node; the layer texture must be preloaded in manifest):
 *   texture: string (required)        texture key (plain image or atlas)
 *   frame?: string                    atlas frame name (omit for plain image)
 *   x?, y?: number = 0                top-left position (origin is top-left)
 *   width?, height?: number           TileSprite extent; height auto-derives
 *                                     from the frame size if omitted, width
 *                                     defaults to 64 — set width wide (e.g. a
 *                                     few screen-widths) so the layer covers the
 *                                     whole camera-scroll range
 *   originX?, originY?: number = 0     TileSprite origin (top-left anchored)
 *   scrollFactorX?, scrollFactorY?: number = 1   0 = fixed to viewport (sky),
 *                                     <1 = drifts slower than camera (far),
 *                                     1 = moves with world
 *   depth?: number = -50              render depth (further layers more negative)
 *   driftX?: number = 0               constant self-scroll in px/s (clouds/water)
 *
 * Output: the on-screen TileSprite (this.gameObject) and runtimeState() =
 * { texture, frame, scrollFactorX, scrollFactorY, depth, driftX, tilePositionX }
 * for parallax verification (assert layers report different scrollFactor and
 * that tilePositionX advances for drifting layers).
 */
export default class ParallaxModule extends Node {
  ready() {
    const c = this.config || {}
    const scene = this.scene
    if (!scene) return
    if (!c.texture) {
      console.error(`ParallaxModule[${this.name}]: config.texture is required`)
      return
    }
    if (!scene.textures.exists(c.texture)) {
      console.error(`ParallaxModule[${this.name}]: texture "${c.texture}" not loaded — register it in a manifest listed in project.json.manifests`)
      return
    }

    let fw, fh
    const tex = scene.textures.get(c.texture)
    if (c.frame && tex?.frames?.[c.frame]) {
      const f = tex.frames[c.frame]
      fw = f.width ?? f.cutWidth
      fh = f.height ?? f.cutHeight
    } else if (tex?.frames?.['__BASE']) {
      const f = tex.frames['__BASE']
      fw = f.width ?? f.cutWidth
      fh = f.height ?? f.cutHeight
    }
    const targetW = c.width || fw || 64
    const targetH = c.height || fh || 64
    const x = c.x ?? 0
    const y = c.y ?? 0

    const ts = c.frame
      ? scene.add.tileSprite(x, y, targetW, targetH, c.texture, c.frame)
      : scene.add.tileSprite(x, y, targetW, targetH, c.texture)
    ts.setOrigin(c.originX ?? 0, c.originY ?? 0)
    ts.setScrollFactor(c.scrollFactorX ?? 1, c.scrollFactorY ?? 1)
    ts.setDepth(c.depth ?? -50)

    this.gameObject = ts
    this._driftX = c.driftX || 0
  }

  update(dt) {
    if (this._driftX && this.gameObject) {
      this.gameObject.tilePositionX += this._driftX * dt
    }
  }

  destroy() {
    if (this.gameObject) {
      this.gameObject.destroy()
      this.gameObject = null
    }
  }

  runtimeState() {
    const c = this.config || {}
    return {
      texture: c.texture ?? null,
      frame: c.frame ?? null,
      scrollFactorX: c.scrollFactorX ?? 1,
      scrollFactorY: c.scrollFactorY ?? 1,
      depth: c.depth ?? -50,
      driftX: this._driftX ?? 0,
      tilePositionX: this.gameObject ? this.gameObject.tilePositionX : null,
    }
  }
}
