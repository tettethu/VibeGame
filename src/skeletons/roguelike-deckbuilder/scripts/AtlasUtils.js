/**
 * Resolve the atlas-position (x,y) of a frame within its source image.
 * In Phaser 3.80 CE texture-packer atlases: cutX/cutY are the authoritative
 * top-left position of the frame inside the atlas image; x/y are always 0.
 */
function frameXY(frame) {
  const x = frame.cutX ?? frame.x ?? 0
  const y = frame.cutY ?? frame.y ?? 0
  return { x, y }
}

/**
 * Relative paths within /assets/ for atlas textures used in DOM <img> elements.
 * Phaser's frame.source.image.src is an internal blob URL that DOM <img> cannot load.
 */
// Projects may fill this map for DOM image clipping helpers.
// Skeletons prefer manifest placeholder_atlas keys, so modules and helpers keep the real atlas interface.
const ATLAS_ASSET_PATHS = {}

/**
 * Extract a single atlas sprite frame as a PNG data URL.
 * Uses canvas 2D drawImage — reliable for Canvas renderer, may produce blank
 * in WebGL mode if the browser has evicted the CPU-side pixel buffer.
 * Prefer getFrameBgStyle() for DOM background use cases.
 *
 * @param {Phaser.Scene} scene
 * @param {string} texKey
 * @param {string} frameName
 * @param {number} [displayHeight] - target height in px; omit for native
 * @returns {string} PNG data URL or ''
 */
export function extractFrameDataUrl(scene, texKey, frameName, displayHeight) {
  const tex = scene.textures.get(texKey)
  if (!tex) return ''
  const frame = tex.get(frameName)
  if (!frame || frame.realWidth <= 0 || frame.realHeight <= 0) return ''
  const { x: fx, y: fy } = frameXY(frame)
  const sw = frame.realWidth, sh = frame.realHeight
  const scale = displayHeight != null ? displayHeight / sh : 1
  const dw = Math.max(1, Math.round(sw * scale))
  const dh = Math.max(1, Math.round(sh * scale))
  const canvas = document.createElement('canvas')
  canvas.width = dw
  canvas.height = dh
  canvas.getContext('2d').drawImage(frame.source.image, fx, fy, sw, sh, 0, 0, dw, dh)
  return canvas.toDataURL('image/png')
}

/**
 * Return CSS background properties to display an atlas frame inside a container.
 * Uses the atlas image URL directly (no canvas drawImage) — safe in WebGL mode.
 * Scales the full atlas so that the target frame fills containerH pixels tall.
 *
 * @param {Phaser.Scene} scene
 * @param {string} texKey
 * @param {string} frameName
 * @param {number} containerH - display height in px (scale is height-driven)
 * @returns {{ url, bpX, bpY, bsW, bsH } | null}
 */
export function getFrameBgStyle(scene, texKey, frameName, containerH) {
  const tex = scene.textures.get(texKey)
  if (!tex) return null
  const frame = tex.get(frameName)
  if (!frame || frame.realHeight <= 0) return null
  const imgEl = frame.source?.image
  if (!imgEl?.src) return null
  const { x: fx, y: fy } = frameXY(frame)
  const aw = frame.source.width
  const ah = frame.source.height
  // Height-driven scale: frame fits containerH exactly
  const scale = containerH / frame.realHeight
  return {
    url: imgEl.src,
    bpX: -Math.round(fx * scale),
    bpY: -Math.round(fy * scale),
    bsW: Math.round(aw * scale),
    bsH: Math.round(ah * scale),
  }
}

/**
 * Return raw frame geometry for use with the <img> CSS-clip approach.
 * Logs a full diagnostic of all known frame offset fields on first call per frame.
 *
 * @param {Phaser.Scene} scene
 * @param {string} texKey
 * @param {string} frameName
 * @returns {{ url, atlasW, atlasH, frameX, frameY, frameW, frameH } | null}
 */
export function getFrameRawInfo(scene, texKey, frameName) {
  const tex = scene.textures.get(texKey)
  if (!tex) return null
  const frame = tex.get(frameName)
  if (!frame || frame.realWidth <= 0) return null
  // Use direct HTTP path — Phaser's blob URL is not usable by DOM <img>
  const url = getAtlasUrl(texKey)
  if (!url) { console.warn('[AtlasUtils] no ATLAS_URLS entry for', texKey); return null }

  return {
    url,
    atlasW: frame.source.width,
    atlasH: frame.source.height,
    frameX: frame.cutX ?? frame.x ?? 0,   // cutX = atlas top-left x in Phaser 3.80 CE
    frameY: frame.cutY ?? frame.y ?? 0,   // cutY = atlas top-left y
    frameW: frame.realWidth,
    frameH: frame.realHeight,
  }
}
