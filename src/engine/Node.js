/**
 * Base class for all game nodes. Provides lifecycle, tree ops, and event system.
 * AI scripts extend this and override ready/update/destroy.
 */

let _nextId = 1
function generateId() {
  return `node_${_nextId++}`
}

export { generateId }

export class Node {
  // Engine-injected fields (set by SceneTree during build)
  id = ''
  name = ''
  enabled = true
  tags = []
  config = {}

  parent = null
  children = []

  scene = null       // Phaser.Scene ref
  sceneTree = null   // SceneTree ref
  gameObject = null  // Phaser GameObject (may be null)
  visualObject = null
  physicsObject = null
  visualTransform = null
  animationPlayer = null
  animator = null
  _lastTransform = null  // internal: last x/y/displayWidth/displayHeight for child inheritance
  _inheritedFlipX = false
  _effectiveFlipX = false

  // Collision tracking state: targetId -> { touching: boolean }
  _collisionState = new Map()

  // === Lifecycle (override in scripts) ===

  /** Called after node and all children are ready (children first) */
  ready() {}

  /** Called every frame. @param {number} dt - seconds */
  update(dt) {}

  /** Called when node is removed from tree */
  destroy() {}

  // === Tree operations ===

  /** Find direct child by name */
  getChild(name) {
    return this.children.find(c => c.name === name) || null
  }

  /** Find node by path ("Sprite", "../Sibling", "Group/Child") */
  getNode(path) {
    const parts = path.split('/')
    let current = this
    for (const part of parts) {
      if (part === '..') {
        current = current.parent
      } else {
        current = current.getChild(part)
      }
      if (!current) return null
    }
    return current
  }

  /** Find all nodes with a given tag in the entire scene tree */
  findByTag(tag) {
    return this.sceneTree.findByTag(tag)
  }

  /** Add a child node at runtime */
  async addChild(node) {
    node.parent = this
    node.scene = this.scene
    node.sceneTree = this.sceneTree
    this.children.push(node)
    this.sceneTree.register(node)
    await this.sceneTree.propagateReady(node)
  }

  /** Remove self from scene tree */
  removeSelf() {
    this.sceneTree.removeNode(this)
  }

  /** Instantiate a prefab as a child */
  async instantiatePrefab(prefabName, configOverride = {}) {
    return this.sceneTree.instantiatePrefab(prefabName, configOverride, this)
  }

  /**
   * Load a .node.json and instantiate as child of this node.
   * @param {string} nodeSrc - path to .node.json
   * @param {object} [configOverride] - config values to merge
   * @returns {Node}
   */
  async instantiate(nodeSrc, configOverride = {}) {
    return this.sceneTree.instantiateNode(nodeSrc, configOverride, this)
  }

  /** Switch to another scene */
  changeScene(sceneName) {
    this.sceneTree.changeScene(sceneName)
  }

  /** Play an animation clip immediately, interrupting the current clip by default. */
  playAnim(name, options = {}) {
    return this.animationPlayer?.play(name, options) || false
  }

  getVisualObject() {
    return this.visualObject || this.gameObject || null
  }

  getPhysicsObject() {
    return this.physicsObject || this.gameObject || null
  }

  getTransformObject() {
    return this.getPhysicsObject() || this.getVisualObject() || null
  }

  stopAnim() {
    this.animationPlayer?.stop()
  }

  getCurrentAnim() {
    return this.animationPlayer?.getCurrentClip() || null
  }

  // === Collision tracking ===

  /**
   * Register a physics collider with enter/exit state tracking.
   * Emits 'collision_enter' and 'collision_exit' on this node.
   * Uses per-frame flag to detect when collision callback stops firing.
   * @param {Phaser.GameObjects.GameObject} targetGameObject
   * @param {Node} targetNode
   */
  trackCollider(targetGameObject, targetNode) {
    if (!this.gameObject || !targetGameObject) return

    const stateKey = targetNode.id
    this._collisionState.set(stateKey, { touching: false, touchedThisFrame: false })

    this.scene.physics.add.collider(this.gameObject, targetGameObject, () => {
      const state = this._collisionState.get(stateKey)
      if (!state) return
      state.touchedThisFrame = true
      if (!state.touching) {
        state.touching = true
        this.emit('collision_enter', { other: targetNode })
      }
    })

    // Post-update: check if callback was NOT fired this frame -> exit
    this.scene.events.on('postupdate', () => {
      const state = this._collisionState.get(stateKey)
      if (!state) return
      if (state.touching && !state.touchedThisFrame) {
        state.touching = false
        this.emit('collision_exit', { other: targetNode })
      }
      state.touchedThisFrame = false
    })
  }

  /**
   * Register a physics overlap with enter/exit state tracking.
   * Emits 'overlap_enter' and 'overlap_exit' on this node.
   * Uses per-frame flag to detect when overlap callback stops firing.
   * @param {Phaser.GameObjects.GameObject} targetGameObject
   * @param {Node} targetNode
   */
  trackOverlap(targetGameObject, targetNode) {
    if (!this.gameObject || !targetGameObject) return

    const stateKey = targetNode.id
    this._collisionState.set(stateKey, { touching: false, touchedThisFrame: false })

    this.scene.physics.add.overlap(this.gameObject, targetGameObject, () => {
      const state = this._collisionState.get(stateKey)
      if (!state) return
      state.touchedThisFrame = true
      if (!state.touching) {
        state.touching = true
        this.emit('overlap_enter', { other: targetNode })
      }
    })

    // Post-update: check if callback was NOT fired this frame -> exit
    this.scene.events.on('postupdate', () => {
      const state = this._collisionState.get(stateKey)
      if (!state) return
      if (state.touching && !state.touchedThisFrame) {
        state.touching = false
        this.emit('overlap_exit', { other: targetNode })
      }
      state.touchedThisFrame = false
    })
  }

  // === Runtime Control ===

  /**
   * Pause execution in runtime control mode. No-op when controller is not active.
   * Agent scripts call this to set breakpoints in game logic.
   * @param {string} [reason] - description of why this breakpoint was placed
   */
  breakpoint(reason = '') {
    if (this.sceneTree?.runtimeController?.enabled) {
      this.sceneTree.runtimeController.hit(this, reason)
    }
  }

  // === Event system ===

  _listeners = {}

  /** Emit an event (bubbles up to parent) */
  emit(event, data = {}) {
    const callbacks = this._listeners[event]
    if (callbacks) {
      for (const cb of callbacks) cb(data)
    }
    if (this.parent) {
      this.parent.emit(event, { ...data, source: data.source || this })
    }
  }

  /** Listen for an event */
  on(event, callback) {
    if (!this._listeners[event]) this._listeners[event] = []
    this._listeners[event].push(callback)
  }

  /** Remove event listener */
  off(event, callback) {
    if (!this._listeners[event]) return
    this._listeners[event] = this._listeners[event].filter(cb => cb !== callback)
  }
}
