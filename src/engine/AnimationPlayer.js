/**
 * Runtime frame-based animation playback independent from Phaser's anim system.
 * Uses dt in seconds and applies frames directly to the node's visual object.
 */

import { applyPivot } from './PivotResolver.js'
import { VisualFactory } from './VisualFactory.js'
import { ColliderFactory } from './ColliderFactory.js'

export class AnimationPlayer {
  node = null
  def = null
  currentClipName = null
  currentClip = null
  currentFrameIndex = 0
  elapsed = 0
  finished = false
  _warnedFrameOffsetSameObject = false
  _sameObjectFrameOffset = { x: 0, y: 0 }
  _declaredExplicitSizeApplied = false

  constructor(node, def) {
    this.node = node
    this.def = def || { clips: {} }
  }

  init(autoPlayDefault = true) {
    if (!autoPlayDefault) return
    const defaultClip = this.def.default || null
    if (defaultClip) {
      this.play(defaultClip)
    }
  }

  play(name, options = {}) {
    const { restart = true, force = true } = options
    if (!force && this.currentClipName) return false
    if (!restart && this.currentClipName === name) return true

    const clip = this.def?.clips?.[name]
    if (!clip) {
      console.warn(`AnimationPlayer: clip "${name}" not found on node "${this.node?.name || this.node?.id || 'unknown'}"`)
      return false
    }

    this.currentClipName = name
    this.currentClip = clip
    this.currentFrameIndex = 0
    this.elapsed = 0
    this.finished = false
    this._clearFrameOffset()
    this._applyCurrentFrame()
    return true
  }

  stop() {
    this._clearFrameOffset()
    this.currentClipName = null
    this.currentClip = null
    this.currentFrameIndex = 0
    this.elapsed = 0
    this.finished = false
  }

  update(dt) {
    if (!this.currentClip) return

    const frames = this._getFrames(this.currentClip)
    if (frames.length <= 1 || this.finished) return

    this.elapsed += dt

    while (true) {
      const frameDuration = this._getFrameDuration(this.currentClip, this.currentFrameIndex)
      if (frameDuration <= 0 || this.elapsed < frameDuration) break
      this.elapsed -= frameDuration
      this.currentFrameIndex += 1

      if (this.currentFrameIndex >= frames.length) {
        if (this.currentClip.loop !== false) {
          this.currentFrameIndex = 0
        } else {
          this.finished = true
          this.currentFrameIndex = this.currentClip.onFinish === 'first' ? 0 : frames.length - 1
          this._applyCurrentFrame()
          return
        }
      }
    }

    this._applyCurrentFrame()
  }

  getCurrentClip() {
    return this.currentClipName
  }

  isPlaying(name) {
    return this.currentClipName === name
  }

  isFinished() {
    return this.finished
  }

  _getFrames(clip) {
    if (Array.isArray(clip.frames) && clip.frames.length > 0) return clip.frames
    if (clip.source?.type === 'image' && clip.source.texture) return [clip.source.texture]
    return []
  }

  _getFrameId(frameRef) {
    if (frameRef && typeof frameRef === 'object' && !Array.isArray(frameRef)) {
      return frameRef.frame
    }
    return frameRef
  }

  _getFrameOffset(frameRef) {
    if (!frameRef || typeof frameRef !== 'object' || Array.isArray(frameRef)) return [0, 0]
    const offset = frameRef.offset
    if (!Array.isArray(offset) || offset.length !== 2) return [0, 0]
    const x = Number(offset[0])
    const y = Number(offset[1])
    return [Number.isFinite(x) ? x : 0, Number.isFinite(y) ? y : 0]
  }

  _getFrameDuration(clip, frameIndex) {
    const durations = Array.isArray(clip?.frameDurations) ? clip.frameDurations : null
    const ms = Number(durations?.[frameIndex])
    if (Number.isFinite(ms) && ms > 0) return ms / 1000
    // clip.duration is total seconds, split evenly across frames.
    const totalSec = Number(clip?.duration)
    if (Number.isFinite(totalSec) && totalSec > 0) {
      const frames = this._getFrames(clip)
      if (frames.length > 0) return totalSec / frames.length
    }
    const frameRate = Number(clip?.frameRate || 10)
    return frameRate > 0 ? 1 / frameRate : 0
  }

  _applyCurrentFrame() {
    const go = this.node?.getVisualObject?.() || this.node?.gameObject
    if (!go || !this.currentClip) return

    const clip = this.currentClip
    const source = clip.source || {}
    const frames = this._getFrames(clip)
    const frameRef = frames[this.currentFrameIndex]
    const frame = this._getFrameId(frameRef)
    const manifest = this.node?.sceneTree?.assetManifest
    const clipPivot = clip.pivot

    if (source.type === 'image') {
      if (typeof frame === 'string') {
        go.setTexture?.(frame)
        applyPivot(go, manifest, frame, null, clipPivot)
        this._applyDeclaredDisplaySize(go)
        this._applyFrameOffset(frameRef)
      } else if (source.texture) {
        go.setTexture?.(source.texture)
        applyPivot(go, manifest, source.texture, null, clipPivot)
        this._applyDeclaredDisplaySize(go)
        this._applyFrameOffset(frameRef)
      }
      return
    }

    if (!source.texture) {
      this._clearFrameOffset()
      return
    }

    if (frame !== undefined) {
      go.setTexture?.(source.texture, frame)
      go.setFrame?.(frame)
      applyPivot(go, manifest, source.texture, frame, clipPivot)
      this._applyDeclaredDisplaySize(go)
      this._applyFrameOffset(frameRef)
      return
    }

    go.setTexture?.(source.texture)
    applyPivot(go, manifest, source.texture, null, clipPivot)
    this._applyDeclaredDisplaySize(go)
    this._applyFrameOffset(frameRef)
  }

  _applyFrameOffset(frameRef) {
    const [x, y] = this._getFrameOffset(frameRef)
    const hasOffset = x !== 0 || y !== 0
    const visualObject = this.node?.getVisualObject?.() || this.node?.visualObject || null
    const transformObject = this.node?.getTransformObject?.() || this.node?.gameObject || null

    if (hasOffset && visualObject && transformObject && visualObject === transformObject && this.node?._colliderDef) {
      if (!this._warnedFrameOffsetSameObject) {
        console.warn(
          `AnimationPlayer: node "${this.node?.name || this.node?.id || 'unknown'}" uses frame offset with same-object collider. ` +
          'Use collider.host: "separate"; offset was ignored.'
        )
        this._warnedFrameOffsetSameObject = true
      }
      this._clearFrameOffset()
      return
    }

    if (visualObject && transformObject && visualObject === transformObject) {
      this._applySameObjectFrameOffset(visualObject, x, y)
      if (this.node) this.node._frameOffset = { x: 0, y: 0 }
      return
    }

    this._clearSameObjectFrameOffset()
    if (this.node) this.node._frameOffset = { x, y }
    this._syncVisualToTransform()
  }

  _clearFrameOffset() {
    this._clearSameObjectFrameOffset()
    if (this.node) this.node._frameOffset = { x: 0, y: 0 }
    this._syncVisualToTransform()
  }

  _applySameObjectFrameOffset(visualObject, x, y) {
    const previous = this._sameObjectFrameOffset || { x: 0, y: 0 }
    visualObject.x += x - previous.x
    visualObject.y += y - previous.y
    this._sameObjectFrameOffset = { x, y }
  }

  _clearSameObjectFrameOffset() {
    const previous = this._sameObjectFrameOffset || { x: 0, y: 0 }
    if (previous.x === 0 && previous.y === 0) return
    const visualObject = this.node?.getVisualObject?.() || this.node?.visualObject || null
    const transformObject = this.node?.getTransformObject?.() || this.node?.gameObject || null
    if (visualObject && visualObject === transformObject) {
      visualObject.x -= previous.x
      visualObject.y -= previous.y
    }
    this._sameObjectFrameOffset = { x: 0, y: 0 }
  }

  _syncVisualToTransform() {
    const visualObject = this.node?.visualObject
    const transformObject = this.node?.getTransformObject?.() || this.node?.gameObject
    if (!visualObject || !transformObject || visualObject === transformObject) return
    this.node?.sceneTree?._syncVisualToTransform?.(this.node, transformObject)
  }

  // width/height establish scale once on the first real animation frame.
  // ratio remains a per-frame source multiplier.
  _applyDeclaredDisplaySize(gameObject) {
    const def = this.node?._visualDef
    if (!def) return
    const hasExplicitSize = def.width !== undefined || def.height !== undefined
    if (hasExplicitSize) {
      if (this._declaredExplicitSizeApplied) return
      VisualFactory.applyDisplaySize(gameObject, def)
      this._declaredExplicitSizeApplied = true
      this._syncColliderAfterDisplaySize(gameObject)
      return
    }
    VisualFactory.applyDisplaySize(gameObject, def)
  }

  _syncColliderAfterDisplaySize(visualObject) {
    const colliderDef = this.node?._colliderDef
    const physicsObject = this.node?.getPhysicsObject?.() || this.node?.physicsObject || this.node?.gameObject
    if (!colliderDef || !physicsObject?.body) return

    if (physicsObject !== visualObject) {
      this._syncSeparateColliderHostSize(physicsObject, visualObject, colliderDef)
    }
    ColliderFactory.applyBodyConfig(physicsObject, colliderDef)
  }

  _syncSeparateColliderHostSize(physicsObject, visualObject, colliderDef) {
    const shape = colliderDef.shape || 'box'
    const displayW = visualObject?.displayWidth || visualObject?.width || 0
    const displayH = visualObject?.displayHeight || visualObject?.height || 0
    if (shape === 'circle') {
      const diameter = colliderDef.radius !== undefined ? colliderDef.radius * 2 : Math.min(displayW, displayH)
      if (diameter > 0) {
        physicsObject.displayWidth = diameter
        physicsObject.displayHeight = diameter
      }
      return
    }
    if (colliderDef.width === undefined && displayW > 0) physicsObject.displayWidth = displayW
    if (colliderDef.height === undefined && displayH > 0) physicsObject.displayHeight = displayH
  }
}
