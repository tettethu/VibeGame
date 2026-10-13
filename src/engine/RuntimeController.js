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
    this.session = 0
    this.mode = 'paused'    // 'paused' | 'stepping' | 'play'
    this.frameCount = 0
    this.stepsRemaining = 0
    this._resolveStep = null
    this._breakpointHit = null
  }

  /** Activate runtime control mode (pauses immediately) */
  activate() {
    if (this.enabled) { this.pause(); return }
    this.session++
    this.enabled = true
    this.mode = 'paused'
    this.frameCount = 0
  }

  /** Deactivate runtime control mode */
  deactivate() {
    if (!this.enabled) return
    this.session++
    this.sceneTree.inputMap?.clearAllInjections()
    this.sceneTree.phaserScene?.input?.keyboard?.resetKeys()
    this.enabled = false
    this.mode = 'paused'
    this.frameCount = 0
    if (this._resolveStep) {
      this._resolveStep({ status: 'deactivated', frame: this.frameCount })
      this._resolveStep = null
    }
    this._breakpointHit = null
  }

  /**
   * Run exactly N frames then pause. Blocks until done or breakpoint hit.
   * @param {number} frames
   * @returns {Promise<{status: string, frame: number, node?: string, reason?: string}>}
   */
  continue(frames) {
    if (!this.enabled) throw new Error('No runtime session. Call activate first.')
    if (!Number.isInteger(frames) || frames <= 0) throw new Error('frames must be a positive integer')
    if (this._resolveStep) throw new Error('A continue command is already in progress')
    return new Promise(resolve => {
      this.mode = 'stepping'
      this.stepsRemaining = frames
      this._resolveStep = resolve
    })
  }

  /** Resume free-running play (non-blocking) */
  play() {
    if (this._resolveStep) this._finishStep({status: 'playing', frame: this.frameCount})
    this.mode = 'play'
  }

  /** Pause immediately */
  pause() {
    this.mode = 'paused'
    this.stepsRemaining = 0
    if (this._resolveStep) {
      this._resolveStep({ status: 'paused', frame: this.frameCount })
      this._resolveStep = null
    }
  }

  /** Gate node updates; the game loop owns frame completion. */
  shouldUpdate() {
    return !this.enabled || this.mode !== 'paused'
  }

  _finishStep(result) {
    const resolve = this._resolveStep
    this._resolveStep = null
    this.stepsRemaining = 0
    if (resolve) resolve(result)
  }

  /** Called after the full game frame, including paused scenes. */
  postFrame() {
    if (this.enabled && this.mode === 'paused') return
    this.frameCount++
    if (this._breakpointHit) {
      const bp = this._breakpointHit
      this._breakpointHit = null
      this.mode = 'paused'
      this._finishStep({status: 'breakpoint', frame: this.frameCount, node: bp.nodeName, reason: bp.reason})
    } else if (this.mode === 'stepping' && --this.stepsRemaining === 0) {
      this.mode = 'paused'
      this._finishStep({status: 'completed', frame: this.frameCount})
    }
  }

  /**
   * Called by Node.breakpoint(). Records hit for frame completion.
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

}
