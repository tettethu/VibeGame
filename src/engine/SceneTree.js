/**
 * Scene tree: loads scene JSON, builds node tree, drives lifecycle.
 * `running` flag controls edit/play mode (default false for editor).
 */

import { Node, generateId } from './Node.js'
import { AnimationPlayer } from './AnimationPlayer.js'
import { Animator } from './Animator.js'
import { VisualFactory } from './VisualFactory.js'
import { ColliderFactory } from './ColliderFactory.js'

export class SceneTree {
  nodes = new Map()       // id -> Node
  root = null
  phaserScene = null      // Phaser.Scene
  scriptClasses = {}      // script name -> class
  prefabs = {}            // prefab name -> JSON
  nodeDefinitions = {}    // srcPath -> loaded .node.json content
  inputMap = null          // InputMap instance
  running = false          // false = edit mode, true = play mode
  runtimeController = null // RuntimeController instance (when runtime mode is active)
  tilesets = {}            // tileset name -> tileset.json content
  tilemaps = {}            // src path -> tilemap.json content
  assetManifest = null     // { key: { type, path, sprites?, ... } }
  ui = null                // UiLayer instance
  _postUpdateSyncHandler = null
  _postUpdateSyncScene = null

  /**
   * Dynamically load a script module and register its default export.
   * @param {string} name - script name (e.g. "PlayerBox")
   * @param {string} url - URL to fetch the module from
   */
  async loadScript(name, url) {
    try {
      const mod = await import(url)
      const cls = mod.default || mod[name]
      if (cls) {
        this.scriptClasses[name] = cls
      }
    } catch (err) {
      console.warn(`Failed to load script "${name}" from ${url}:`, err)
    }
  }

  /** Load scene JSON: build tree and propagate ready */
  async load(sceneJson) {
    if (!sceneJson || !sceneJson.root) {
      console.error('SceneTree.load: scene JSON missing "root" field. Check your scene file.')
      return
    }
    if (typeof sceneJson.root !== 'object' || Array.isArray(sceneJson.root)) {
      console.error('SceneTree.load: "root" must be an object, got', typeof sceneJson.root)
      return
    }
    this.destroyAll()
    this.root = await this._buildNode(sceneJson.root, null)
    await this.propagateReady(this.root)
    this._bindPostUpdateSync()
  }

  _bindPostUpdateSync() {
    const scene = this.phaserScene
    const events = scene?.events
    if (!events) return
    if (this._postUpdateSyncHandler && this._postUpdateSyncScene === scene) return

    this._unbindPostUpdateSync()
    this._postUpdateSyncHandler = () => {
      if (!this.root) return
      this._syncSeparatedVisuals(this.root)
    }
    this._postUpdateSyncScene = scene
    events.on('postupdate', this._postUpdateSyncHandler)
  }

  _unbindPostUpdateSync() {
    if (!this._postUpdateSyncHandler) return

    const events = this._postUpdateSyncScene?.events
    if (typeof events?.off === 'function') {
      events.off('postupdate', this._postUpdateSyncHandler)
    } else if (typeof events?.removeListener === 'function') {
      events.removeListener('postupdate', this._postUpdateSyncHandler)
    }
    this._postUpdateSyncHandler = null
    this._postUpdateSyncScene = null
  }

  /**
   * Resolve a def with `src` field: load from nodeDefinitions, deep-clone, merge overrides.
   * @returns {object} resolved NodeDef (src field removed)
   */
  _resolveSrc(def) {
    if (!def.src) return def

    const srcDef = this.nodeDefinitions[def.src]
    if (!srcDef) {
      throw new Error(
        `SceneTree: node definition "${def.src}" not found in nodeDefinitions. ` +
        `Templates are preloaded from scene JSON src references; add a disabled placeholder ` +
        `node with this src to the scene, or register it manually before instantiate().`
      )
    }

    // Deep-clone the loaded definition
    const resolved = JSON.parse(JSON.stringify(srcDef))

    // Merge inline config on top of loaded config (shallow merge)
    if (def.config) {
      resolved.config = { ...(resolved.config || {}), ...def.config }
    }

    // Inline name/tags/enabled override loaded values if present
    if (def.name !== undefined) resolved.name = def.name
    if (def.tags !== undefined) resolved.tags = def.tags
    if (def.enabled !== undefined) resolved.enabled = def.enabled

    return resolved
  }

  /** @private Recursively build a node from its JSON definition */
  async _buildNode(def, parent) {
    // Step 1: src resolution
    const resolved = this._resolveSrc(def)

    let ScriptClass = Node
    if (resolved.script) {
      ScriptClass = this.scriptClasses[resolved.script]
      if (!ScriptClass) {
        console.error(
          `SceneTree: script "${resolved.script}" not found in scriptClasses. ` +
          `Available: [${Object.keys(this.scriptClasses).join(', ')}]. ` +
          `Node "${resolved.name || resolved.id || '(unnamed)'}" will not have script behavior.`
        )
        ScriptClass = Node
      }
    }

    const node = new ScriptClass()
    node.id = resolved.id || generateId()
    node.name = resolved.name || ''
    node.enabled = resolved.enabled !== undefined ? resolved.enabled : true
    node.tags = resolved.tags || []
    node.config = resolved.config || {}
    node.parent = parent
    node.scene = this.phaserScene
    node.sceneTree = this
    // Store original definition name for script lookup
    node._scriptName = resolved.script || null
    // Store visual/collider defs for cleanup tracking
    node._visualDef = resolved.visual || null
    node._colliderDef = resolved.collider || null
    node.visualTransform = this._normalizeVisualTransform(resolved.visualTransform)
    node._animationsDef = this._normalizeAnimations(resolved)
    node._animatorDef = resolved.animator || null
    // Each instance needs its own children array and listeners
    node.children = []
    node._listeners = {}
    node._collisionState = new Map()

    const separateColliderHost = !!(resolved.visual && resolved.collider && resolved.collider.host === 'separate')

    // Step 2: visual creation (skip disabled nodes to avoid ghost sprites)
    if (resolved.visual && node.enabled) {
      const visualObject = VisualFactory.create(this.phaserScene, resolved.visual, node.config, this.assetManifest)
      if (visualObject) {
        node.visualObject = visualObject
      }
    }

    // Step 3: collider configuration
    if (resolved.collider && node.enabled) {
      if (separateColliderHost) {
        const physicsObject = ColliderFactory.createHost(this.phaserScene, resolved.collider, node.config, node.visualObject)
        node.physicsObject = physicsObject
        node.gameObject = physicsObject
      } else if (node.visualObject) {
        ColliderFactory.configure(this.phaserScene, node.visualObject, resolved.collider)
        node.physicsObject = node.visualObject
        node.gameObject = node.visualObject
      }
    }

    if (!node.gameObject && node.visualObject) {
      node.gameObject = node.visualObject
    }
    if (!node.physicsObject && node.gameObject?.body) {
      node.physicsObject = node.gameObject
    }
    this._syncVisualToTransform(node, node.getTransformObject?.() || node.gameObject)
    this._recordTransformSnapshot(node)
    node._effectiveFlipX = this._readNodeFlipX(node)

    if (node._animationsDef) {
      node.animationPlayer = new AnimationPlayer(node, node._animationsDef)
    }

    if (node._animatorDef) {
      if (!node.animationPlayer) {
        console.warn(`SceneTree: node "${node.name}" defines animator but has no animations.clips`)
      } else {
        node.animator = new Animator(node.animationPlayer, node._animatorDef)
      }
    }

    // Build children. A disabled node is an inert declaration container:
    // its entire subtree is skipped, not built as live objects.
    if (resolved.children && node.enabled) {
      if (!Array.isArray(resolved.children)) {
        console.error(`SceneTree.buildNode: "${node.name}" children must be an array, got ${typeof resolved.children}. Skipping children.`)
      } else {
        for (const childDef of resolved.children) {
          const child = await this._buildNode(childDef, node)
          node.children.push(child)
        }
      }
    }

    this.nodes.set(node.id, node)
    if (node.animator) {
      node.animator.init()
    } else if (node.animationPlayer) {
      node.animationPlayer.init(true)
    }
    return node
  }

  // === Lifecycle propagation ===

  /** ready: children before parent (post-order) */
  async propagateReady(node) {
    for (const child of node.children) {
      await this.propagateReady(child)
    }
    if (node.enabled) await node.ready()
  }

  /** update: parent before children (pre-order), only when running */
  propagateUpdate(node, dt) {
    if (!node.enabled) return
    this._ensureTransformSnapshot(node)
    node.update(dt)
    if (node.animator) node.animator.update(dt)
    if (node.animationPlayer) node.animationPlayer.update(dt)
    node._effectiveFlipX = this._readNodeFlipX(node)
    const currentTransform = this._readTransform(node.getTransformObject?.() || node.gameObject)
    for (const child of node.children) {
      this._inheritParentTransformDelta(node, child, currentTransform)
    }
    node._lastTransform = currentTransform
    for (const child of node.children) {
      this.propagateUpdate(child, dt)
    }
  }

  _ensureTransformSnapshot(node) {
    if (!node._lastTransform) {
      this._recordTransformSnapshot(node)
    }
  }

  _recordTransformSnapshot(node) {
    node._lastTransform = this._readTransform(node.getTransformObject?.() || node.gameObject)
  }

  _readTransform(gameObject) {
    if (!gameObject) return null
    return {
      x: gameObject.x || 0,
      y: gameObject.y || 0,
      width: this._readDisplayWidth(gameObject),
      height: this._readDisplayHeight(gameObject),
    }
  }

  _readDisplayWidth(gameObject) {
    if (typeof gameObject.displayWidth === 'number') return gameObject.displayWidth
    if (typeof gameObject.width === 'number') return gameObject.width
    return 0
  }

  _readDisplayHeight(gameObject) {
    if (typeof gameObject.displayHeight === 'number') return gameObject.displayHeight
    if (typeof gameObject.height === 'number') return gameObject.height
    return 0
  }

  _normalizeVisualTransform(visualTransform) {
    const vt = visualTransform || {}
    return {
      offsetX: Number.isFinite(vt.offsetX) ? vt.offsetX : 0,
      offsetY: Number.isFinite(vt.offsetY) ? vt.offsetY : 0,
    }
  }

  _inheritParentTransformDelta(parent, child, currentParentTransform) {
    const previousParentTransform = parent._lastTransform
    const childGameObject = child.getTransformObject?.() || child.gameObject
    if (!previousParentTransform || !currentParentTransform || !childGameObject) return

    const dx = currentParentTransform.x - previousParentTransform.x
    const dy = currentParentTransform.y - previousParentTransform.y
    const sx = previousParentTransform.width ? currentParentTransform.width / previousParentTransform.width : 1
    const sy = previousParentTransform.height ? currentParentTransform.height / previousParentTransform.height : 1
    const moved = dx !== 0 || dy !== 0
    const resized = sx !== 1 || sy !== 1
    const inheritedFlipX = child.config?.flipWithParent === true && parent._effectiveFlipX === true
    const flipChanged = inheritedFlipX !== child._inheritedFlipX
    if (!moved && !resized && !flipChanged) return

    const offsetX = childGameObject.x - previousParentTransform.x
    const offsetY = childGameObject.y - previousParentTransform.y
    childGameObject.x = currentParentTransform.x + offsetX * sx * (flipChanged ? -1 : 1)
    childGameObject.y = currentParentTransform.y + offsetY * sy

    if (resized) {
      if (typeof childGameObject.displayWidth === 'number') {
        childGameObject.displayWidth *= sx
      }
      if (typeof childGameObject.displayHeight === 'number') {
        childGameObject.displayHeight *= sy
      }
    }

    this._refreshPhysicsBody(childGameObject)
    this._applyVisualTransformDelta(child, childGameObject, sx, sy)
    if (flipChanged) this._applyInheritedFlipX(child, inheritedFlipX)
  }

  _readNodeFlipX(node) {
    const visualObject = node?.getVisualObject?.()
    if (typeof visualObject?.flipX === 'boolean') return visualObject.flipX
    const transformObject = node?.getTransformObject?.()
    if (typeof transformObject?.flipX === 'boolean') return transformObject.flipX
    return node?._inheritedFlipX === true
  }

  _applyInheritedFlipX(node, inheritedFlipX) {
    const objects = new Set([node.getVisualObject?.(), node.getTransformObject?.()])
    for (const object of objects) {
      if (!object || typeof object.flipX !== 'boolean') continue
      if (typeof object.setFlipX === 'function') object.setFlipX(!object.flipX)
      else object.flipX = !object.flipX
    }
    node._inheritedFlipX = inheritedFlipX
    node._effectiveFlipX = this._readNodeFlipX(node)
    this._applyColliderFlipX(node, inheritedFlipX)
  }

  _applyColliderFlipX(node, inheritedFlipX) {
    const colliderDef = node?._colliderDef
    const physicsObject = node?.getPhysicsObject?.()
    if (!colliderDef || !physicsObject?.body) return
    if (!inheritedFlipX) {
      ColliderFactory.applyBodyConfig(physicsObject, colliderDef)
      return
    }
    const effectiveDef = { ...colliderDef }
    if (colliderDef.offsetX !== undefined) effectiveDef.offsetX = -colliderDef.offsetX
    if (Array.isArray(colliderDef.pivot) && colliderDef.pivot.length === 2) {
      effectiveDef.pivot = [1 - colliderDef.pivot[0], colliderDef.pivot[1]]
    }
    ColliderFactory.applyBodyConfig(physicsObject, effectiveDef)
  }

  _applyVisualTransformDelta(node, transformObject, sx, sy) {
    const visualObject = node.visualObject
    if (!visualObject || visualObject === transformObject) return

    if (sx !== 1 || sy !== 1) {
      node.visualTransform = node.visualTransform || { offsetX: 0, offsetY: 0 }
      node.visualTransform.offsetX = (node.visualTransform.offsetX || 0) * sx
      node.visualTransform.offsetY = (node.visualTransform.offsetY || 0) * sy
    }
    this._syncVisualToTransform(node, transformObject)
    if (sx !== 1 && typeof visualObject.displayWidth === 'number') {
      visualObject.displayWidth *= sx
    }
    if (sy !== 1 && typeof visualObject.displayHeight === 'number') {
      visualObject.displayHeight *= sy
    }
  }

  _visualOffset(node) {
    const visualTransform = node.visualTransform || {}
    const frameOffset = node._frameOffset || {}
    return {
      x: (visualTransform.offsetX || 0) + (frameOffset.x || 0),
      y: (visualTransform.offsetY || 0) + (frameOffset.y || 0),
    }
  }

  _syncVisualToTransform(node, transformObject) {
    const visualObject = node.visualObject
    if (!visualObject || !transformObject || visualObject === transformObject) return
    const offset = this._visualOffset(node)
    visualObject.x = transformObject.x + offset.x
    visualObject.y = transformObject.y + offset.y
  }

  _refreshPhysicsBody(gameObject) {
    const body = gameObject?.body
    if (!body) return
    if (typeof body.updateFromGameObject === 'function') {
      body.updateFromGameObject()
    } else if (typeof gameObject.refreshBody === 'function') {
      gameObject.refreshBody()
    }
  }

  /** Called by PhaserHost on each frame */
  update(time, delta) {
    if (!this.root) return
    // Runtime mode: controller owns frame stepping and completion
    if (this.runtimeController) {
      if (!this.runtimeController.shouldUpdate()) return
      this.propagateUpdate(this.root, delta / 1000)
      this.inputMap?._advanceFrame()
      this.runtimeController.postUpdate()
      return
    }
    // Normal mode: running flag controls
    if (!this.running) return
    this.propagateUpdate(this.root, delta / 1000)
    this.inputMap?._advanceFrame()
  }

  // === Node management ===

  register(node) {
    this.nodes.set(node.id, node)
  }

  removeNode(node) {
    const removingRoot = node === this.root
    for (const child of [...node.children]) {
      this.removeNode(child)
    }
    node.destroy()

    // Engine cleanup for declarative visual/collider. Manual objects remain script-owned.
    const visualObject = node.visualObject || null
    const physicsObject = node.physicsObject || null
    if (node._visualDef && visualObject) {
      visualObject.destroy()
      node.visualObject = null
      if (node.physicsObject === visualObject) node.physicsObject = null
      if (node.gameObject === visualObject) node.gameObject = null
    }
    if (node._colliderDef && physicsObject && physicsObject !== visualObject) {
      physicsObject.destroy()
      node.physicsObject = null
      if (node.gameObject === physicsObject) node.gameObject = null
    }

    if (node.parent) {
      node.parent.children = node.parent.children.filter(c => c !== node)
    }
    this.nodes.delete(node.id)
    if (removingRoot) {
      this.root = null
      this._unbindPostUpdateSync()
    }
  }

  findByTag(tag) {
    // Disabled nodes are intentionally excluded: they have no gameObject
    // (visual/collider creation is skipped at build time), so returning them
    // would force every caller to null-check before physics/render operations.
    // Disabled placeholder/template nodes (script registry, src cache) inherit
    // tags from their src — without this filter they show up as ghost targets.
    return [...this.nodes.values()].filter(n => n.enabled && n.tags.includes(tag))
  }

  _syncSeparatedVisuals(node) {
    if (node.visualObject && node.physicsObject && node.visualObject !== node.physicsObject) {
      this._syncVisualToTransform(node, node.physicsObject)
    }
    for (const child of node.children) {
      this._syncSeparatedVisuals(child)
    }
  }

  // === Prefab instantiation ===

  async instantiatePrefab(prefabName, configOverride, parent) {
    const prefabJson = this.prefabs[prefabName]
    if (!prefabJson) throw new Error(`Prefab not found: ${prefabName}`)

    const def = JSON.parse(JSON.stringify(prefabJson.node))
    Object.assign(def.config, configOverride)

    const node = await this._buildNode(def, parent)
    parent.children.push(node)
    this.register(node)
    await this.propagateReady(node)
    return node
  }

  // === Node definition instantiation ===

  /**
   * Instantiate a .node.json as a child node.
   * @param {string} nodeSrc - path to .node.json (key in nodeDefinitions)
   * @param {object} configOverride - config to merge on top
   * @param {Node} parent - parent node to attach to
   * @returns {Node}
   */
  async instantiateNode(nodeSrc, configOverride, parent) {
    const def = {
      src: nodeSrc,
      config: configOverride || {},
    }

    const node = await this._buildNode(def, parent)
    parent.children.push(node)
    await this.propagateReady(node)
    return node
  }

  // === Scene switching ===

  changeScene(sceneName) {
    this.destroyAll()
    // Caller should load new scene JSON and call load()
  }

  /** Destroy all nodes and reset */
  destroyAll() {
    this._unbindPostUpdateSync()
    if (this.root) {
      this.removeNode(this.root)
      this.root = null
    }
    this.nodes.clear()
    this.ui?.clear()
  }

  /**
   * Collect all scripts referenced in a scene definition (for dynamic loading).
   * Follows `src` references via nodeDefinitions registry.
   * @param {object} nodeDef
   * @param {Set} [scripts]
   * @param {object} [nodeDefinitions] - loaded .node.json registry for src traversal
   * @returns {Set<string>}
   */
  static collectScripts(nodeDef, scripts = new Set(), nodeDefinitions = {}) {
    // Resolve src to get the full definition
    let resolved = nodeDef
    if (nodeDef.src && nodeDefinitions[nodeDef.src]) {
      resolved = nodeDefinitions[nodeDef.src]
    }

    if (resolved.script) scripts.add(resolved.script)
    if (resolved.children) {
      for (const child of resolved.children) {
        SceneTree.collectScripts(child, scripts, nodeDefinitions)
      }
    }
    return scripts
  }

  _normalizeAnimations(def) {
    if (def.animations?.clips) {
      return this._resolveAnimationSources(def, def.animations)
    }

    if (!def.visual?.animations) return null

    const clips = {}
    for (const [name, clip] of Object.entries(def.visual.animations)) {
      clips[name] = {
        ...clip,
        source: this._inferClipSource(def, clip),
      }
    }

    return { clips }
  }

  _resolveAnimationSources(def, animationsDef) {
    const clips = {}
    for (const [name, clip] of Object.entries(animationsDef.clips || {})) {
      clips[name] = {
        ...clip,
        source: clip.source || this._inferClipSource(def, clip),
      }
    }
    return {
      ...animationsDef,
      clips,
    }
  }

  _inferClipSource(def, clip) {
    if (clip?.source) return clip.source

    const visual = def.visual || {}
    if (visual.type === 'image') {
      return { type: 'image', texture: visual.texture }
    }

    // Deprecated: spritesheet kept for backwards compatibility; new assets use atlas.
    if (visual.type === 'spritesheet' || visual.type === 'atlas') {
      return { type: visual.type, texture: visual.texture }
    }

    return {}
  }
}
