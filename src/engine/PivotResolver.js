/**
 * Pivot cascade resolver.
 * Cascade (high to low): clipPivot > manifest sprite.pivot > manifest group.pivot > [0.5, 1].
 * Values are [x, y] in 0..1, [0,0] = top-left, [0.5, 1] = bottom-center (default).
 */

export const DEFAULT_PIVOT = [0.5, 1]

function isValidPivot(p) {
  return Array.isArray(p) && p.length === 2 && Number.isFinite(p[0]) && Number.isFinite(p[1])
}

/**
 * @param {object|null} assetManifest - sceneTree.assetManifest
 * @param {string|null} textureKey - manifest entry key
 * @param {string|null} frameName - atlas sprite name, or null for image-type
 * @param {Array<number>|null} clipPivot - active clip's pivot override, or null
 * @returns {[number, number]}
 */
export function resolvePivot(assetManifest, textureKey, frameName, clipPivot) {
  if (isValidPivot(clipPivot)) return clipPivot
  const entry = textureKey ? assetManifest?.[textureKey] : null
  if (entry) {
    if (frameName && isValidPivot(entry.sprites?.[frameName]?.pivot)) {
      return entry.sprites[frameName].pivot
    }
    if (isValidPivot(entry.pivot)) return entry.pivot
  }
  return DEFAULT_PIVOT
}

/**
 * Apply resolved pivot to a Phaser GameObject via setOrigin.
 */
export function applyPivot(gameObject, assetManifest, textureKey, frameName, clipPivot) {
  if (!gameObject || typeof gameObject.setOrigin !== 'function') return
  const [px, py] = resolvePivot(assetManifest, textureKey, frameName, clipPivot)
  gameObject.setOrigin(px, py)
}
