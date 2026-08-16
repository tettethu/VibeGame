import { Node } from '/engine/Node.js'

/**
 * Hero — player controller.
 * State machine: idle / run / jump / fall / dash / bounce.
 * Dash: single mid-air, refreshed only by stomping a target (not by landing).
 * Stomp judgement lives here (owns gameObject + facing + intent).
 * Animation: playAnim(state, {restart:false}) each frame; flipX tracks facing.
 * Sizing is fully engine-driven via visual.ratio — each pose renders at its
 * native frame size * ratio (aspect preserved per pose), re-applied every frame
 * by AnimationPlayer. No script-side displayWidth/Height, no postupdate re-assert.
 */

export default class Hero extends Node {
  ready() {
    const c = this.config || {}
    this.speed = c.speed
    this.jumpForce = c.jumpForce
    this.bounceForce = c.bounceForce
    this.dashSpeed = c.dashSpeed
    this.dashDuration = c.dashDuration
    this.deathY = c.deathY
    this.stompAllowance = c.stompAllowance
    this.stompShakeMs = c.stompShakeMs
    this.stompShakeAmount = c.stompShakeAmount
    this.stompZoomScale = c.stompZoomScale
    this.stompZoomMs = c.stompZoomMs

    this.state = 'idle'
    this.dashCharges = 0
    this.isGrounded = false
    this.facing = 1
    this._dashTimer = 0
    this._dead = false
    this._goalReached = false

    // Ground colliders: plain physics.add.collider blocks Hero from passing through.
    // Reserve trackCollider for goal — we want first-touch enter event there.
    for (const g of this.findByTag('ground')) {
      if (!g.gameObject) continue
      if (g.tags?.includes('goal')) {
        this.trackCollider(g.gameObject, g)
      } else {
        this.scene.physics.add.collider(this.gameObject, g.gameObject)
      }
    }
    // Register balloon overlaps (no blocking — Hero passes through unless stomp succeeds).
    // Per-frame overlap (not enter-only) so a fast vertical drop can't tunnel past a
    // one-frame stomp window; _tryStomp guards against double-pop via balloon._popped.
    for (const b of this.findByTag('balloon')) {
      if (b.gameObject) {
        this.scene.physics.add.overlap(this.gameObject, b.gameObject, () => this._tryStomp(b))
      }
    }

    this.on('collision_enter', ({ other }) => {
      if (!other?.tags) return
      if (other.tags.includes('goal') && !this._goalReached) {
        const t = this.gameObject?.body?.touching
        if (t?.down || this.gameObject?.body?.blocked?.down) {
          this._goalReached = true
          this.emit('reached_goal')
        }
      }
    })

    // Initial visual sync (state = idle).
    this._syncVisual()
  }

  _tryStomp(balloon) {
    if (!this.gameObject?.body || !balloon.gameObject) return
    if (balloon._popped) return
    const body = this.gameObject.body
    const balloonObj = balloon.gameObject
    // Forgiving top-stomp: descending (or level) AND feet at/above the balloon's
    // vertical center (+ allowance). Center-relative (not a tight top band) so a
    // clean vertical drop reliably pops; a side/underneath hit (feet well below
    // center, or rising) still does not. balloonObj.y is the sprite center (pivot 0.5,0.5).
    const stompLine = balloonObj.y + this.stompAllowance
    if (body.bottom <= stompLine && body.velocity.y >= 0) {
      const mult = (typeof balloon.bounceMultiplier === 'number') ? balloon.bounceMultiplier : 1.0
      balloon.pop()
      this._bounce(mult)
      // Bubble up so StageManager can spawn confetti at the balloon location.
      this.emit('balloon_stomped', { x: balloonObj.x, y: balloonObj.y })
      // Local camera juice (Hero owns the moment).
      // NOTE: tweening cam.zoom directly does NOT work in Phaser 3 CE — zoom is
      // a setter writing to _zoomX/_zoomY, and the tweens engine assigns to the
      // property without going through the setter. Use cam.zoomTo() instead,
      // which is Phaser's first-class zoom animation API.
      const cam = this.scene?.cameras?.main
      if (cam) {
        cam.shake(this.stompShakeMs, this.stompShakeAmount)
        cam.zoomTo(this.stompZoomScale, this.stompZoomMs, 'Quad.easeOut')
        this.scene.time.delayedCall(this.stompZoomMs, () => {
          if (cam) cam.zoomTo(1.0, this.stompZoomMs, 'Quad.easeOut')
        })
      }
    }
  }

  _bounce(multiplier = 1) {
    if (!this.gameObject?.body) return
    this.gameObject.body.setVelocityY(-this.bounceForce * multiplier)
    this.dashCharges = 1
    this.state = 'bounce'
  }

  respawnTo(x, y) {
    if (!this.gameObject) return
    const body = this.gameObject.body
    if (body && typeof body.reset === 'function') {
      body.reset(x, y)
      body.setAllowGravity(true)
    } else {
      this.gameObject.x = x
      this.gameObject.y = y
      if (body) {
        body.setVelocity(0, 0)
        body.setAllowGravity(true)
        body.updateFromGameObject()
      }
    }
    this._dashTimer = 0
    this.dashCharges = 0
    this.facing = 1
    this.state = 'idle'
    this._dead = false
    this._goalReached = false
    this.isGrounded = false
    this._syncVisual()
  }

  update(dt) {
    if (this._dead) {
      return
    }
    const input = this.sceneTree.inputMap
    const body = this.gameObject?.body
    if (!input || !body) return

    // body.blocked.down only — see vertical-slice comment.
    this.isGrounded = !!body.blocked.down

    if (this.state === 'dash') {
      this._dashTimer -= dt
      if (this._dashTimer <= 0) {
        body.setAllowGravity(true)
        body.setVelocityX(this.facing * this.speed)
        this.state = 'fall'
      } else {
        body.setVelocityX(this.facing * this.dashSpeed)
        body.setVelocityY(0)
      }
      this._syncVisual()
      return
    }

    const left = input.isHeld('move_left')
    const right = input.isHeld('move_right')
    let vx = 0
    if (left && !right) { vx = -this.speed; this.facing = -1 }
    else if (right && !left) { vx = this.speed; this.facing = 1 }
    body.setVelocityX(vx)

    if (input.isPressed('jump') && this.isGrounded) {
      body.setVelocityY(-this.jumpForce)
      this.isGrounded = false
      this.state = 'jump'
    }

    if (input.isPressed('dash') && !this.isGrounded && this.dashCharges > 0 && this.state !== 'dash') {
      this.dashCharges = 0
      this._dashTimer = this.dashDuration
      this.state = 'dash'
      body.setAllowGravity(false)
      body.setVelocityX(this.facing * this.dashSpeed)
      body.setVelocityY(0)
      this._syncVisual()
      return
    }

    if (this.isGrounded) {
      this.state = vx !== 0 ? 'run' : 'idle'
    } else if (this.state === 'bounce') {
      if (body.velocity.y >= 0) this.state = 'fall'
    } else {
      this.state = body.velocity.y < 0 ? 'jump' : 'fall'
    }

    if (this.gameObject.y > this.deathY) {
      this._dead = true
      this.state = 'fall'
      this.emit('player_died')
    }

    this._syncVisual()
  }

  _syncVisual() {
    const v = this.getVisualObject?.() || this.visualObject
    if (!v) return
    v.flipX = this.facing < 0
    if (typeof this.playAnim === 'function') {
      this.playAnim(this.state, { restart: false })
    }
  }

  runtimeState() {
    return {
      state: this.state,
      dashCharges: this.dashCharges,
      isGrounded: this.isGrounded,
      facing: this.facing,
    }
  }
}
