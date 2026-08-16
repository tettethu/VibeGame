/**
 * Frame-level runtime controller for agent-driven testing.
 * Enables step-by-step execution, breakpoints, snapshots, and input injection.
 * Attached to SceneTree as `sceneTree.runtimeController`.
 */

export class RuntimeController {
  /**
   * @param {import('./SceneTree.js').SceneTree} sceneTree
   */
  constructor(sceneTree) {
    this.sceneTree = sceneTree
    this.enabled = false
    this.mode = 'paused'    // 'paused' | 'stepping' | 'play'
    this.frameCount = 0
    this.stepsRemaining = 0
    this._resolveStep = null
    this._breakpointHit = null
  }

  /** Activate runtime control mode (pauses immediately) */
  activate() {
    this.enabled = true
    this.mode = 'paused'
    this.frameCount = 0
    this._pausePhysics()
  }

  /** Deactivate runtime control mode */
  deactivate() {
    this.enabled = false
    this.mode = 'paused'
    this.frameCount = 0
    if (this._resolveStep) {
      this._resolveStep({ status: 'deactivated', frame: this.frameCount })
      this._resolveStep = null
    }
    this._breakpointHit = null
    this._resumePhysics()
  }

  /**
   * Run exactly N frames then pause. Blocks until done or breakpoint hit.
   * @param {number} frames
   * @returns {Promise<{status: string, frame: number, node?: string, reason?: string}>}
   */
  continue(frames) {
    return new Promise(resolve => {
      this._resumePhysics()
      this.mode = 'stepping'
      this.stepsRemaining = frames
      this._resolveStep = resolve
    })
  }

  /** Resume free-running play (non-blocking) */
  play() {
    this.mode = 'play'
    this._resumePhysics()
  }

  /** Pause immediately */
  pause() {
    this.mode = 'paused'
    this.stepsRemaining = 0
    this._pausePhysics()
    if (this._resolveStep) {
      this._resolveStep({ status: 'paused', frame: this.frameCount })
      this._resolveStep = null
    }
  }

  /**
   * Called by SceneTree.update() before propagateUpdate.
   * @returns {boolean} true if this frame should execute
   */
  shouldUpdate() {
    if (!this.enabled) return true

    if (this.mode === 'paused') return false

    if (this.mode === 'stepping') {
      if (this.stepsRemaining <= 0) {
        this.mode = 'paused'
        this._pausePhysics()
        if (this._resolveStep) {
          this._resolveStep({ status: 'completed', frame: this.frameCount })
          this._resolveStep = null
        }
        return false
      }
      this.stepsRemaining--
      return true
    }

    return true // 'play' mode
  }

  /** Called by SceneTree.update() after propagateUpdate */
  postUpdate() {
    this.frameCount++

    if (this._breakpointHit) {
      const bp = this._breakpointHit
      this._breakpointHit = null
      this.mode = 'paused'
      this.stepsRemaining = 0
      this._pausePhysics()
      if (this._resolveStep) {
        this._resolveStep({
          status: 'breakpoint',
          frame: this.frameCount,
          node: bp.nodeName,
          reason: bp.reason,
        })
        this._resolveStep = null
      }
    }
  }

  /**
   * Called by Node.breakpoint(). Records hit for postUpdate processing.
   * @param {import('./Node.js').Node} node
   * @param {string} reason
   */
  hit(node, reason) {
    if (!this.enabled) return
    // Only record the first breakpoint per frame
    if (!this._breakpointHit) {
      this._breakpointHit = { nodeName: node.name || node.id, reason }
    }
  }

  /** Capture current frame state as serializable JSON */
  snapshot() {
    const nodes = {}
    for (const [id, node] of this.sceneTree.nodes) {
      const entry = {
        name: node.name,
        tags: Array.isArray(node.tags) ? [...node.tags] : [],
        enabled: node.enabled,
        config: { ...node.config },
      }

      if (node.gameObject) {
        entry.transform = {
          x: node.gameObject.x ?? 0,
          y: node.gameObject.y ?? 0,
        }
        if (node.gameObject.rotation) entry.transform.rotation = node.gameObject.rotation
        if (node.gameObject.scaleX !== undefined) {
          entry.transform.scaleX = node.gameObject.scaleX
          entry.transform.scaleY = node.gameObject.scaleY
        }
        if (node.gameObject.flipX !== undefined) entry.transform.flipX = node.gameObject.flipX
        if (node.gameObject.flipY !== undefined) entry.transform.flipY = node.gameObject.flipY
      }

      if (node.gameObject?.body) {
        const b = node.gameObject.body
        entry.physics = {
          vx: b.velocity?.x ?? 0,
          vy: b.velocity?.y ?? 0,
          ax: b.acceleration?.x ?? 0,
          ay: b.acceleration?.y ?? 0,
        }
        if (b.blocked) {
          entry.physics.blocked = {
            up: b.blocked.up,
            down: b.blocked.down,
            left: b.blocked.left,
            right: b.blocked.right,
          }
        }
      }

      // Custom runtime state from script (opt-in)
      if (typeof node.runtimeState === 'function') {
        try { entry.runtime = node.runtimeState() } catch { /* skip */ }
      }

      nodes[id] = entry
    }

    return { frame: this.frameCount, mode: this.mode, nodes }
  }

  _pausePhysics() {
    this.sceneTree.phaserScene?.physics?.world?.pause()
  }

  _resumePhysics() {
    this.sceneTree.phaserScene?.physics?.world?.resume()
  }
}
