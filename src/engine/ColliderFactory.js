/**
 * Configures Phaser physics body from NodeDef.collider field.
 * Operates on an existing gameObject (created by VisualFactory or script).
 *
 * Collider pivot model (Sprint 2):
 *   colliderDef.pivot is a [x, y] in 0..1 indicating where on the collider box
 *   the anchor sits. The body offset is auto-computed so the collider's pivot
 *   point in world space coincides with the gameObject's origin point.
 *   Cascade default: sprite.originX/Y (= visual.pivot resolved) for box;
 *   [0.5, 0.5] for circles and when no source object is present.
 *   colliderDef.offsetX/Y still respected, applied additively on top.
 */

const DEFAULT_PIVOT = [0.5, 0.5]

function isValidPivot(p) {
  return Array.isArray(p) && p.length === 2 && Number.isFinite(p[0]) && Number.isFinite(p[1])
}

/**
 * @param {object} colliderDef
 * @param {object|null} sourceGameObject - the gameObject whose origin acts as the default source
 * @param {boolean} isCircle - circles default to [0.5, 0.5] regardless of source
 * @returns {[number, number]}
 */
function resolveColliderPivot(colliderDef, sourceGameObject, isCircle) {
  if (isValidPivot(colliderDef?.pivot)) return colliderDef.pivot
  if (isCircle) return DEFAULT_PIVOT
  if (sourceGameObject && Number.isFinite(sourceGameObject.originX) && Number.isFinite(sourceGameObject.originY)) {
    return [sourceGameObject.originX, sourceGameObject.originY]
  }
  return DEFAULT_PIVOT
}

export const ColliderFactory = {
  createHost(scene, colliderDef, config = {}, sourceGameObject = null) {
    const x = config.x || 0
    const y = config.y || 0
    const sourceW = sourceGameObject?.displayWidth || sourceGameObject?.width || 32
    const sourceH = sourceGameObject?.displayHeight || sourceGameObject?.height || 32
    const w = colliderDef?.width || sourceW
    const h = colliderDef?.height || sourceH
    const host = scene.add.rectangle(x, y, w, h, 0xffffff, 0)
    host.setVisible(false)
    const isCircle = (colliderDef?.shape || 'box') === 'circle'
    const pivot = resolveColliderPivot(colliderDef, sourceGameObject, isCircle)
    if (host.setOrigin) host.setOrigin(pivot[0], pivot[1])
    this.configure(scene, host, colliderDef)
    return host
  },

  /**
   * Add and configure a physics body on a game object.
   * @param {Phaser.Scene} scene
   * @param {Phaser.GameObjects.GameObject} gameObject
   * @param {object} colliderDef - ColliderDef from scene JSON
   */
  configure(scene, gameObject, colliderDef = {}) {
    if (!gameObject) return  // skip silently (caller guards before this)

    const isStatic = colliderDef.body === 'static'
    if (!gameObject.body) {
      scene.physics.add.existing(gameObject, isStatic)
    }

    this.applyBodyConfig(gameObject, colliderDef)
  },

  /**
   * Recompute body shape/offset from an existing game object's current display size.
   * @param {Phaser.GameObjects.GameObject} gameObject
   * @param {object} colliderDef
   */
  applyBodyConfig(gameObject, colliderDef = {}) {
    const body = gameObject.body
    if (!body) return
    const isStatic = colliderDef.body === 'static'

    // Collider dimensions are world-space (what the user sees).
    // Phaser body.setSize uses pre-scale local coords, so divide by scale.
    const sx = gameObject.scaleX || 1
    const sy = gameObject.scaleY || 1

    const shape = colliderDef.shape || 'box'
    const isCircle = shape === 'circle'
    const pivot = resolveColliderPivot(colliderDef, gameObject, isCircle)
    const explicitOffsetX = colliderDef.offsetX || 0
    const explicitOffsetY = colliderDef.offsetY || 0
    const displayW = gameObject.displayWidth || gameObject.width || 0
    const displayH = gameObject.displayHeight || gameObject.height || 0
    const originX = Number.isFinite(gameObject.originX) ? gameObject.originX : 0.5
    const originY = Number.isFinite(gameObject.originY) ? gameObject.originY : 0.5

    if (isCircle) {
      const sourceW = displayW || 0
      const sourceH = displayH || 0
      const r = (colliderDef.radius || Math.min(sourceW, sourceH) / 2) / Math.max(sx, sy)
      const bodyWWorld = 2 * r * Math.max(sx, sy)
      const bodyHWorld = 2 * r * Math.max(sx, sy)
      // Auto offset: place the circle's bounding-box pivot at the gameObject's origin point.
      const autoOx = (displayW * originX - bodyWWorld * pivot[0]) / sx
      const autoOy = (displayH * originY - bodyHWorld * pivot[1]) / sy
      const ox = autoOx + explicitOffsetX / sx
      const oy = autoOy + explicitOffsetY / sy
      body.setCircle(r, ox, oy)
    } else {
      // box
      const bodyWWorld = colliderDef.width || displayW || 32
      const bodyHWorld = colliderDef.height || displayH || 32
      const w = bodyWWorld / sx
      const h = bodyHWorld / sy
      body.setSize(w, h)
      // Auto offset: place the collider box's pivot at the gameObject's origin point.
      const autoOx = (displayW * originX - bodyWWorld * pivot[0]) / sx
      const autoOy = (displayH * originY - bodyHWorld * pivot[1]) / sy
      const ox = autoOx + explicitOffsetX / sx
      const oy = autoOy + explicitOffsetY / sy
      body.setOffset(ox, oy)
    }

    // Physics flags (only for dynamic bodies)
    if (!isStatic) {
      if (colliderDef.gravity === false) body.setAllowGravity(false)
      if (colliderDef.immovable) body.setImmovable(true)
    }

    if (colliderDef.worldBounds) body.setCollideWorldBounds(true)

    if (colliderDef.bounce) {
      const bx = typeof colliderDef.bounce === 'object' ? colliderDef.bounce.x : colliderDef.bounce
      const by = typeof colliderDef.bounce === 'object' ? colliderDef.bounce.y : colliderDef.bounce
      body.setBounce(bx || 0, by || 0)
    }

    // One-way platform: only blocks from above
    if (colliderDef.oneWay && body.checkCollision) {
      body.checkCollision.down = false
      body.checkCollision.left = false
      body.checkCollision.right = false
    }
  },
}
