import { Node } from '/engine/Node.js'

export default class SideviewFighterModule extends Node {
  facing = 1
  _prevState = null
  _dashTimer = 0
  _dashDir = 1
  _guardStartTime = 0
  _activeHitbox = null
  _deathblowActive = false
  _deathblowTarget = null
  _deathblowWindowTimer = 0

  ready() {
    this._bindWorldColliders()
    this._selfCheck()
  }

  _selfCheck() {
    const tag = `SideviewFighterModule[${this.name}]`
    const errors = []
    const warns = []

    // Animator
    if (!this.animator) {
      errors.push('no animator — node.json must define "animator" with states and transitions')
    } else {
      const states = this.animator.def?.states || {}
      const params = this.animator.def?.parameters || {}
      for (const s of ['idle', 'walk']) {
        if (!states[s]) errors.push(`animator missing required state "${s}"`)
      }
      for (const p of ['moving', 'grounded']) {
        if (!(p in params)) errors.push(`animator missing required parameter "${p}"`)
      }
      for (const [name, state] of Object.entries(states)) {
        if (state.clip && !this.animationPlayer?.def?.clips?.[state.clip]) {
          errors.push(`state "${name}" references clip "${state.clip}" but clip not found in animations`)
        }
      }
    }

    // AnimationPlayer
    if (!this.animationPlayer) {
      errors.push('no animationPlayer — node.json must define "animations" with clips')
    }

    // Physics
    if (!this.getPhysicsObject?.()?.body) {
      errors.push('no physics body — node.json must define "collider" with body: "dynamic"')
    }

    // Hitbox children
    const attacks = this.config.attacks || {}
    for (const [state, def] of Object.entries(attacks)) {
      const child = this.getChild(def.hitbox)
      if (!child) errors.push(`config.attacks.${state}.hitbox "${def.hitbox}" — child node not found`)
      if (!Array.isArray(def.activeFrames) || !def.activeFrames.length) {
        warns.push(`config.attacks.${state}.activeFrames is empty — hitbox will never activate`)
      }
    }

    // Ground tag
    const grounds = this.findByTag('ground')
    if (!grounds?.length) warns.push('no nodes with tag "ground" — grounded detection will always be false')

    for (const e of errors) console.error(`${tag}: ${e}`)
    for (const w of warns) console.warn(`${tag}: ${w}`)
    if (!errors.length && !warns.length) console.log(`${tag}: self-check passed`)
  }

  update(dt) {
    if (this._deathblowActive) {
      this._updateDeathblow()
      return
    }
    if (this._deathblowWindowTimer > 0) {
      this._deathblowWindowTimer -= dt
      if (this._deathblowWindowTimer <= 0) this._deathblowTarget = null
    }

    const input = this.sceneTree?.inputMap
    if (!input) return

    const state = this.animator?.getState()
    if (state !== this._prevState) {
      this._onStateChange(this._prevState, state)
      this._prevState = state
    }

    if (state === 'die') return

    this._updateGrounded()
    this._updateFacing(input)
    this._updateDash(dt)
    this._updateBools(input)
    this._updateTriggers(input)
    this._updateHitboxes()
  }

  // --- Grounded ---

  _updateGrounded() {
    const body = this.getPhysicsObject?.()?.body
    this.animator?.setBool('grounded', !!body?.blocked?.down)
  }

  // --- Facing ---

  _updateFacing(input) {
    const left = input.isHeld('move_left')
    const right = input.isHeld('move_right')
    if (left && !right) this.facing = -1
    if (right && !left) this.facing = 1
    const vo = this.getVisualObject?.()
    if (vo) vo.flipX = this.facing < 0
  }

  // --- Movement & Dash ---

  _updateBools(input) {
    const left = input.isHeld('move_left')
    const right = input.isHeld('move_right')
    const moving = left || right

    this.animator?.setBool('moving', moving)
    this.animator?.setBool('running', moving && input.isHeld('run'))
    this.animator?.setBool('guarding', input.isHeld('guard'))

    const state = this.animator?.getState()
    if (this._dashTimer > 0) return
    if (state === 'attack1' || state === 'attack2' || state === 'airSlash' || state === 'hurt' || state === 'deflect') return

    const body = this.getPhysicsObject?.()?.body
    if (!body) return
    const guarding = state === 'guard' || state === 'defense_walk'
    const running = !guarding && input.isHeld('run')
    const speed = guarding ? (this.config.guardSpeed || 100) : running ? (this.config.runSpeed || 400) : (this.config.moveSpeed || 200)
    const vx = (right ? 1 : 0) - (left ? 1 : 0)
    body.setVelocityX(vx * speed)
  }

  _updateDash(dt) {
    if (this._dashTimer <= 0) return
    this._dashTimer -= dt
    const body = this.getPhysicsObject?.()?.body
    if (body) body.setVelocityX(this._dashDir * (this.config.dashSpeed || 500))
    if (this._dashTimer <= 0) this._dashTimer = 0
  }

  // --- Triggers ---

  _updateTriggers(input) {
    if (input.isPressed('jump')) this.animator?.setTrigger('jump')
    if (input.isPressed('attack')) {
      if (this._deathblowTarget) {
        this._doDeathblow(this._deathblowTarget)
        return
      }
      if (this._tryCombo()) return
      this.animator?.setTrigger('attack')
    }
    if (input.isPressed('dash')) {
      this.animator?.setTrigger('dash')
      this._dashDir = this.facing
      this._dashTimer = this.config.dashDuration || 0.2
    }
  }

  // --- Combo window ---

  _tryCombo() {
    if (this.animator?.getState() !== 'attack1') return false

    const player = this.animationPlayer
    if (!player?.currentClip) return false
    const frames = player.currentClip.frames || []
    if (frames.length <= 1) return false

    const progress = player.currentFrameIndex / (frames.length - 1)
    const [min, max] = this.config.comboWindowRatio || [0.6, 0.95]
    if (progress >= min && progress <= max) {
      this.animator?.setTrigger('comboAttack')
      return true
    }
    return false
  }

  // --- Hitboxes ---

  _updateHitboxes() {
    const state = this.animator?.getState()
    const attacks = this.config.attacks || {}
    const attackDef = attacks[state]

    if (!attackDef) {
      this._disableActiveHitbox()
      return
    }

    const frameIndex = this.animationPlayer?.currentFrameIndex ?? -1
    const active = (attackDef.activeFrames || []).includes(frameIndex)

    if (active) {
      const hitbox = this.getChild(attackDef.hitbox)
      if (hitbox && !hitbox.isEnabled?.()) {
        this._disableActiveHitbox()
        hitbox.enable?.()
        this._activeHitbox = hitbox
      }
    } else {
      this._disableActiveHitbox()
    }
  }

  _disableActiveHitbox() {
    if (this._activeHitbox?.isEnabled?.()) {
      this._activeHitbox.disable()
    }
    this._activeHitbox = null
  }

  // --- State change ---

  _onStateChange(from, to) {
    this._disableActiveHitbox()

    if (to === 'jump') {
      const body = this.getPhysicsObject?.()?.body
      if (body) body.setVelocityY(-(this.config.jumpForce || 520))
    }

    if (to === 'guard') {
      this._guardStartTime = performance.now()
    }
  }

  // --- Deflect ---

  tryDeflect() {
    const s = this.animator?.getState()
    if (s !== 'guard' && s !== 'defense_walk') return false
    const elapsed = performance.now() - this._guardStartTime
    if (elapsed <= (this.config.deflectWindowMs || 150)) {
      this.animator.setTrigger('deflect')
      return true
    }
    return false
  }

  // --- Deathblow ---

  enableDeathblow(target) {
    this._deathblowTarget = target
    this._deathblowWindowTimer = this.config.deathblowWindowDuration || 8
  }

  disableDeathblow() {
    this._deathblowTarget = null
    this._deathblowWindowTimer = 0
  }

  _doDeathblow(target) {
    this._deathblowActive = true
    this._deathblowTarget = null
    this._deathblowWindowTimer = 0
    this._disableActiveHitbox()
    this.animator?.setTrigger('deathblow')
    this._dbTarget = target
    this._dbPhase = 0
    this._dbAfterimageSpawned = 0

    const body = this.getPhysicsObject?.()?.body
    if (body) body.setVelocity(0, 0)

    this.animationPlayer?.play('deathblow', { restart: true, force: true })
  }

  _updateDeathblow() {
    if (!this._deathblowActive) return
    const frame = this.animationPlayer?.currentFrameIndex ?? -1
    const target = this._dbTarget
    const cfg = this.config

    // Phase: arrive starts at f08 — set velocity toward target's back
    if (frame >= 8 && this._dbPhase < 1) {
      this._dbPhase = 1
      const targetGO = target?.getPhysicsObject?.() || target?.gameObject
      const physObj = this.getPhysicsObject?.()
      if (targetGO && physObj) {
        const offset = cfg.deathblowTeleportOffset || 200
        this._dbTargetX = targetGO.x + this.facing * offset
        this._dbTargetY = physObj.y
        const dx = this._dbTargetX - physObj.x
        const throughDur = cfg.deathblowThroughDuration || 0.13
        const body = physObj.body
        if (body) body.setVelocity(dx / throughDur, 0)
      }
    }

    // Afterimages during arrive (f08)
    if (frame === 8 && this._dbPhase === 1) {
      const count = cfg.afterimageCount || 3
      const physObj = this.getPhysicsObject?.()
      if (physObj && this._dbAfterimageSpawned < count) {
        const i = this._dbAfterimageSpawned
        const alpha = (count - i) / (count + 1)
        this.instantiate?.('entities/wolf-afterimage.node.json', {
          x: physObj.x, y: physObj.y,
          initialAlpha: alpha,
          fadeDuration: cfg.afterimageFadeDuration || 0.3
        })
        this._dbAfterimageSpawned++
      }
    }

    // Phase: arrive finish at f09 — reset position, flip
    if (frame >= 9 && this._dbPhase < 2) {
      this._dbPhase = 2
      const body = this.getPhysicsObject?.()?.body
      const vo = this.getVisualObject?.()
      if (body && this._dbTargetX !== undefined) {
        body.reset(this._dbTargetX, this._dbTargetY)
        body.setVelocity(0, 0)
      }
      const targetGO = target?.getPhysicsObject?.() || target?.gameObject
      if (vo && targetGO && body) {
        this.facing = targetGO.x > body.position.x ? 1 : -1
        vo.flipX = this.facing < 0
      }
    }

    // Phase: done when clip finishes
    if (this.animationPlayer?.finished && this._dbPhase >= 2) {
      this._deathblowActive = false
      this._dbTarget = null
      this.parent?.emit?.('player_victory')
    }
  }

  // --- World colliders ---

  _bindWorldColliders() {
    const bodyObject = this.getPhysicsObject?.()
    if (!bodyObject || !this.scene?.physics) return
    for (const node of this.findByTag('ground') || []) {
      const target = node.getPhysicsObject?.() || node.gameObject
      if (target) this.scene.physics.add.collider(bodyObject, target)
    }
  }
}
