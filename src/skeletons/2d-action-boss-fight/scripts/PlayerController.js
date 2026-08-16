import { Node } from '/engine/Node.js'

export default class PlayerController extends Node {
  ready() {
    this.cfg = this.config || {}
    this.hp = this._num('hp')
    this.maxHp = this.hp
    this.state = 'IDLE'
    this.facing = this._num('defaultFacing')
    this.isGrounded = false
    this.lastAction = null
    this.activeAttackKind = null
    this.controlsEnabled = true

    this.chargeTimer = 0
    this.actionTimer = 0
    this.hitboxActiveTimer = 0
    this.invulnTimer = 0
    this.dashCooldownTimer = 0
    this.dashTimer = 0
    this.hurtTimer = 0
    this._canDash = true
    this._nailActive = false
    this._hitRegisteredThisSwing = false
    this._pendingAttackFx = null
    this.damageTakenCount = 0
    this.totalDamageTaken = 0
    this.lastDamage = null
    this._runtimeGroundedFrames = 0
    this._runtimeResetCount = 0
    this._runtimeLastReset = null

    for (const n of this.findByTag('ground')) this.scene.physics.add.collider(this.gameObject, n.gameObject)
    for (const n of this.findByTag('wall')) this.scene.physics.add.collider(this.gameObject, n.gameObject)

    this.nailHitboxes = Object.fromEntries(
      Object.entries(this.cfg.hitboxNodes || {}).map(([kind, name]) => [kind, this.getChild(name)])
    )
    this.chargeReadyIndicator = this.getChild(this.cfg.chargeReadyIndicatorNode)
    this._setChargeReadyIndicator(false)
    this._boss = this.findByTag('boss')[0] || null
    this._bindNailHitboxes()

    this._disableNailHitbox()
    this.on('hit', (data = {}) => this._takeDamage(data))
    this._syncVisualState()
  }

  _num(key) {
    return Number(this.cfg?.[key]) || 0
  }

  update(dt) {
    if (!this.gameObject?.body) return

    this._updatePendingAttackFx()
    this._updateGrounded()
    this._tickTimers(dt)
    this._syncInvulnFlicker()

    if (this.state === 'DIE') return
    if (this.state === 'HURT') {
      this.hurtTimer -= dt
      if (this.hurtTimer <= 0 && this._isCurrentAnimationComplete()) this._setState(this.isGrounded ? 'IDLE' : 'FALL')
      return
    }

    if (this.state === 'DASH') {
      if (this._isCurrentAnimationComplete()) this._finishDash()
      return
    }

    const input = this.sceneTree.inputMap
    if (!input || !this.controlsEnabled) return

    if (this.state === 'CHARGE_BUILD' || this.state === 'CHARGE_FULL') {
      this._updateCharge(dt, input)
      return
    }

    if (this.state === 'ATTACK' || this.state === 'CHARGE_RELEASE' || this.state === 'AIR_ATTACK') {
      this._updateAttackLock(dt)
      return
    }

    if (input.isPressed('jump') && this.isGrounded) {
      this._doJump()
      return
    }

    if (input.isPressed('dash') && this._canDash && this.isGrounded && this.dashCooldownTimer <= 0) {
      this._doDash()
      return
    }

    if (input.isPressed('attack')) {
      if (this.isGrounded) this._beginCharge()
      else this._startAttack('air')
      return
    }

    this._applyHorizontal(input, this.cfg.speed)
    this._syncLocomotionState()
  }

  _tickTimers(dt) {
    this.invulnTimer = Math.max(0, this.invulnTimer - dt)
    this.dashCooldownTimer = Math.max(0, this.dashCooldownTimer - dt)
    if (this.hitboxActiveTimer > 0) {
      this.hitboxActiveTimer = Math.max(0, this.hitboxActiveTimer - dt)
      if (this.hitboxActiveTimer <= 0) this._disableNailHitbox()
    }
    if (this.isGrounded && this.dashCooldownTimer <= 0 && this.state !== 'DASH') this._canDash = true
  }

  _updateGrounded() {
    if (this._runtimeGroundedFrames > 0) {
      this._runtimeGroundedFrames -= 1
      this.isGrounded = true
      return
    }
    const body = this.gameObject.body
    this.isGrounded = !!(body.blocked.down || body.touching.down)
  }

  _applyHorizontal(input, speed) {
    const left = input.isHeld('move_left')
    const right = input.isHeld('move_right')
    const vx = left === right ? 0 : (right ? speed : -speed)
    this.gameObject.body.setVelocityX(vx)
    if (vx !== 0) {
      this.facing = Math.sign(vx)
      this.visualObject?.setFlipX?.(this.facing < 0)
    }
  }

  _syncLocomotionState() {
    if (!this.isGrounded) {
      this._setState(this.gameObject.body.velocity.y < 0 ? 'JUMP' : 'FALL')
      return
    }
    this._setState(Math.abs(this.gameObject.body.velocity.x) > this._num('runVelocityThreshold') ? 'RUN' : 'IDLE')
  }

  _doJump() {
    this._cancelCharge('jump')
    this.gameObject.body.setVelocityY(-this.cfg.jumpForce)
    this.isGrounded = false
    this._canDash = false
    this.lastAction = 'jump'
    this._setState('JUMP')
  }

  _doDash() {
    this._cancelCharge('dash')
    this._disableNailHitbox()
    this._canDash = false
    this.dashCooldownTimer = this.cfg.dashCooldown
    this.invulnTimer = Math.max(this.invulnTimer, this.cfg.dashInvulnDuration)
    this.gameObject.body.setVelocity(this.facing * this.cfg.dashSpeed, 0)
    this.lastAction = 'dash'
    this._setState('DASH')
  }

  _finishDash() {
    this.dashTimer = 0
    this.gameObject.body.setVelocityX(0)
    this._setState(this.isGrounded ? 'IDLE' : 'FALL')
  }

  _beginCharge() {
    this.chargeTimer = 0
    this.activeAttackKind = null
    this.lastAction = 'charge_build'
    this._setState('CHARGE_BUILD')
  }

  _updateCharge(dt, input) {
    if (!this.isGrounded) {
      this._cancelCharge('fall')
      this._setState('FALL')
      return
    }

    if (input.isPressed('jump')) {
      this._doJump()
      return
    }

    if (input.isPressed('dash')) {
      if (this._canDash && this.dashCooldownTimer <= 0) this._doDash()
      else this._cancelCharge('dash')
      return
    }

    this.chargeTimer += dt
    if (this.chargeTimer >= this.cfg.chargeFullTime) this._setState('CHARGE_FULL')
    this._applyHorizontal(input, this.cfg.chargeMoveSpeed)

    if (input.isReleased('attack')) {
      const charged = this.chargeTimer >= this.cfg.chargeFullTime
      this._cancelCharge('release')
      this._startAttack(charged ? 'charged' : 'normal')
    }
  }

  _cancelCharge(reason) {
    if (this.state !== 'CHARGE_BUILD' && this.state !== 'CHARGE_FULL') return
    this.chargeTimer = 0
    if (reason !== 'release') {
      this.activeAttackKind = null
      this.lastAction = `charge_cancel_${reason}`
      this._setState(this.isGrounded ? 'IDLE' : 'FALL')
    }
  }

  _startAttack(kind) {
    const cfg = this.cfg
    const isAir = kind === 'air'
    const isCharged = kind === 'charged'
    const state = isAir ? 'AIR_ATTACK' : (isCharged ? 'CHARGE_RELEASE' : 'ATTACK')
    const damage = isCharged ? cfg.chargedDamage : (isAir ? cfg.airDamage : cfg.normalDamage)
    const lockTime = isCharged ? cfg.releaseLockTime : (isAir ? cfg.airLockTime : cfg.normalLockTime)
    const activeTime = isCharged ? cfg.chargedActiveTime : (isAir ? cfg.airActiveTime : cfg.normalActiveTime)

    this.activeAttackKind = isCharged ? 'charged' : (isAir ? 'air' : 'normal')
    this._currentAttackDamage = damage
    this.actionTimer = lockTime
    this.lastAction = this.activeAttackKind === 'charged' ? 'charge_release' : `${this.activeAttackKind}_attack`
    this._setState(state)

    if (!isAir) this.gameObject.body.setVelocityX(0)
    if (isCharged) {
      this._queueAttackFx(this.activeAttackKind, state, activeTime)
    } else {
      this._fireNailHitbox(this.activeAttackKind, activeTime)
      this._queueAttackFx(this.activeAttackKind, state, activeTime)
    }
  }

  _queueAttackFx(kind, expectedState, activeTime) {
    const triggerFrame = Number(this.cfg.attackFx?.[kind]?.triggerFrame)
    if (Number.isInteger(triggerFrame) && triggerFrame > 0) {
      this._pendingAttackFx = { kind, expectedState, triggerFrame, activeTime }
      return
    }
    this._pendingAttackFx = null
    if (kind === 'charged') this._fireNailHitbox(kind, activeTime)
    this._spawnAttackFx(kind)
  }

  _updatePendingAttackFx() {
    const pending = this._pendingAttackFx
    if (!pending) return
    if (this.state !== pending.expectedState || this.activeAttackKind !== pending.kind) {
      this._pendingAttackFx = null
      return
    }
    if ((this.animationPlayer?.currentFrameIndex ?? 0) < pending.triggerFrame) return
    this._pendingAttackFx = null
    this._fireNailHitbox(pending.kind, pending.activeTime)
    this._spawnAttackFx(pending.kind)
  }

  _spawnAttackFx(kind) {
    const fx = this.cfg.attackFx?.[kind]
    if (!fx || !this.gameObject) return
    const offsetX = Number(fx.offsetX) || 0
    const offsetY = Number(fx.offsetY) || 0
    this.emit('spawn_fx', {
      ...fx,
      x: this.gameObject.x + this.facing * offsetX,
      y: this.gameObject.y + offsetY,
      facing: this.facing,
      attackKind: kind,
      sourceX: this.gameObject.x,
      sourceY: this.gameObject.y
    })
  }

  _updateAttackLock(dt) {
    this.actionTimer = Math.max(0, this.actionTimer - dt)
    if (this.actionTimer > 0 || !this._isCurrentAnimationComplete()) return
    this.activeAttackKind = null
    this._disableNailHitbox()
    this._setState(this.isGrounded ? 'IDLE' : 'FALL')
  }

  _isCurrentAnimationComplete() {
    const player = this.animationPlayer
    if (!player?.currentClip) return true
    const clip = player.currentClip
    if (clip.loop !== false) return true
    const frames = Array.isArray(clip.frames) ? clip.frames : []
    if (frames.length <= 1) return true
    return player.isFinished?.() === true
  }

  _fireNailHitbox(kind, duration) {
    const hitbox = this._hitboxFor(kind)
    if (!hitbox) return
    this._disableNailHitbox()
    this._nailActive = true
    this._hitRegisteredThisSwing = false
    this.hitboxActiveTimer = duration
    hitbox.enable()
  }

  _disableNailHitbox() {
    this._nailActive = false
    this.hitboxActiveTimer = 0
    for (const hitbox of Object.values(this.nailHitboxes || {})) hitbox?.disable?.()
  }

  _hitboxFor(kind) {
    return this.nailHitboxes?.[kind] || null
  }

  _bindNailHitboxes() {
    if (!this._boss?.gameObject) return
    for (const hitbox of Object.values(this.nailHitboxes || {})) {
      if (!hitbox?.gameObject) continue
      this.scene.physics.add.overlap(hitbox.gameObject, this._boss.gameObject, () => {
        if (!this._nailActive || !hitbox.isEnabled?.() || this._hitRegisteredThisSwing) return
        this._hitRegisteredThisSwing = true
        this._boss.emit('hit', {
          damage: this._currentAttackDamage,
          attackKind: this.activeAttackKind,
          sourceX: this.gameObject?.x,
          sourceY: this.gameObject?.y
        })
      })
    }
  }

  resetForRuntimeEvidence(options = {}) {
    const x = Number.isFinite(options.x) ? options.x : this._num('x')
    const y = Number.isFinite(options.y) ? options.y : this._num('y')
    const resetHp = options.resetHp !== false
    const resetDamageCounters = options.resetDamageCounters !== false

    this.sceneTree.inputMap?.clearAllInjections?.()
    this._disableNailHitbox()

    if (resetHp) this.hp = this.maxHp
    if (resetDamageCounters) {
      this.damageTakenCount = 0
      this.totalDamageTaken = 0
      this.lastDamage = null
    }

    this.state = 'IDLE'
    this.facing = Number.isFinite(options.facing) ? Math.sign(options.facing) || this._num('defaultFacing') : this._num('defaultFacing')
    this.isGrounded = true
    this.lastAction = 'runtime_reset'
    this.activeAttackKind = null
    this.chargeTimer = 0
    this.actionTimer = 0
    this.hitboxActiveTimer = 0
    this.invulnTimer = 0
    this.dashCooldownTimer = 0
    this.dashTimer = 0
    this.hurtTimer = 0
    this._canDash = true
    this._hitRegisteredThisSwing = false
    this._currentAttackDamage = 0
    this._pendingAttackFx = null
    this.controlsEnabled = true
    this._runtimeGroundedFrames = Number.isFinite(options.groundedFrames) ? options.groundedFrames : this._num('runtimeResetGroundedFrames')
    this._runtimeResetCount += 1
    this._runtimeLastReset = { x, y, resetHp, resetDamageCounters }

    this._resetBodyPosition(x, y)
    this.visualObject?.setFlipX?.(this.facing < 0)
    this._syncVisualState()

    return {
      cleanBaseline: this._isRuntimeBaselineClean(),
      runtime: this.runtimeState()
    }
  }

  _resetBodyPosition(x, y) {
    if (!this.gameObject) return
    this.gameObject.setPosition?.(x, y)
    const body = this.gameObject.body
    if (body) {
      body.enable = true
      body.reset?.(x, y)
      body.setVelocity?.(0, 0)
      body.setAcceleration?.(0, 0)
      body.setAllowGravity?.(true)
      body.setAngularVelocity?.(0)
      body.updateFromGameObject?.()
      if (body.blocked) {
        body.blocked.up = false
        body.blocked.left = false
        body.blocked.right = false
        body.blocked.down = true
      }
      if (body.touching) {
        body.touching.up = false
        body.touching.left = false
        body.touching.right = false
        body.touching.down = true
      }
    }
  }

  _isRuntimeBaselineClean() {
    const body = this.gameObject?.body
    const vx = body?.velocity?.x ?? 0
    const vy = body?.velocity?.y ?? 0
    const epsilon = this._num('velocityEpsilon')
    return this.state === 'IDLE' &&
      this.isGrounded === true &&
      Math.abs(vx) < epsilon &&
      Math.abs(vy) < epsilon &&
      this.activeAttackKind === null &&
      !this._nailActive &&
      this.chargeTimer === 0 &&
      this.actionTimer === 0 &&
      this.hitboxActiveTimer === 0 &&
      this.dashTimer === 0 &&
      this.dashCooldownTimer === 0 &&
      this.hurtTimer === 0 &&
      this.invulnTimer === 0 &&
      this._canDash === true
  }

  _takeDamage(data = {}) {
    const { damage = 0, sourceX = null, attack = null } = data
    if (this.state === 'DIE' || this.invulnTimer > 0) return
    const amount = Math.max(0, Number(damage) || 0)
    if (amount <= 0) return

    const stateBefore = this.state
    this.hp = Math.max(0, this.hp - amount)
    this.damageTakenCount += 1
    this.totalDamageTaken += amount
    this.lastDamage = {
      amount,
      attack,
      sourceX,
      hpAfter: this.hp,
      stateBefore
    }
    this.invulnTimer = this.cfg.invulnDuration
    this._cancelCharge('hurt')
    this._disableNailHitbox()
    this.activeAttackKind = null

    const dir = Number.isFinite(sourceX) ? Math.sign(this.gameObject.x - sourceX) || -this.facing : -this.facing
    this.gameObject.body.setVelocity(dir * this.cfg.knockbackX, this.cfg.knockbackY)
    this.scene.cameras.main.shake(this._num('hurtShakeMs'), this._num('hurtShakeIntensity'))
    this.emit('player_hurt', { hp: this.hp, maxHp: this.maxHp })

    if (this.hp <= 0) {
      this._setState('DIE')
      this.emit('player_die', {})
      return
    }

    this.hurtTimer = this.cfg.hurtDuration
    this.lastAction = 'hurt'
    this._setState('HURT')
  }

  _setState(next) {
    if (this.state === next) return
    this.state = next
    this._syncVisualState()
    this._setChargeReadyIndicator(next === 'CHARGE_FULL')
  }

  _setChargeReadyIndicator(visible) {
    const visual = this.chargeReadyIndicator?.getVisualObject?.()
    if (!visual) return
    visual.setVisible?.(visible)
    visual.setAlpha?.(Number(this.chargeReadyIndicator.config?.alpha))
  }

  _syncVisualState() {
    const clips = {
      IDLE: 'idle',
      RUN: 'run',
      JUMP: 'jump',
      FALL: 'fall',
      DASH: 'dash',
      ATTACK: 'attack',
      CHARGE_BUILD: 'charge_build',
      CHARGE_FULL: 'charge_full',
      CHARGE_RELEASE: 'charge_release',
      AIR_ATTACK: 'air_attack',
      HURT: 'hurt',
      DIE: 'die'
    }
    const clip = clips[this.state]
    if (clip) this.playAnim(clip, { restart: false })
  }

  _syncInvulnFlicker() {
    if (!this.visualObject || this.state === 'DIE') return
    if (this.invulnTimer > 0 && this.state !== 'DASH') {
      const dim = Math.floor(this.invulnTimer * this._num('invulnFlickerRate')) % this._num('invulnFlickerModulo') === 0
      this.visualObject.setAlpha?.(dim ? this._num('invulnFlickerAlpha') : 1)
    } else {
      this.visualObject.setAlpha?.(1)
    }
  }

  runtimeState() {
    const chargeProgress = Math.max(0, Math.min(1, this.chargeTimer / (this.cfg?.chargeFullTime || 1)))
    const activeAttack = this.state === 'ATTACK' || this.state === 'CHARGE_RELEASE' || this.state === 'AIR_ATTACK'
    return {
      x: this.gameObject?.x ?? null,
      y: this.gameObject?.y ?? null,
      velocity: {
        x: this.gameObject?.body?.velocity?.x ?? 0,
        y: this.gameObject?.body?.velocity?.y ?? 0
      },
      hp: this.hp,
      maxHp: this.maxHp,
      state: this.state,
      facing: this.facing,
      isGrounded: this.isGrounded,
      dashCooldownTimer: this.dashCooldownTimer,
      dashTimer: this.dashTimer,
      canDash: this._canDash,
      isInvulnerable: this.invulnTimer > 0,
      invulnTimer: this.invulnTimer,
      chargeProgress,
      isChargeReady: this.state === 'CHARGE_FULL' || chargeProgress >= 1,
      chargeReadyIndicatorVisible: this.chargeReadyIndicator?.getVisualObject?.().visible === true,
      lastAction: this.lastAction,
      activeAttackKind: this.activeAttackKind,
      activeAttackDamage: activeAttack ? (this._currentAttackDamage || 0) : 0,
      attackHitRegistered: activeAttack ? this._hitRegisteredThisSwing : false,
      hitboxActive: this._nailActive,
      hitboxTimeLeft: this.hitboxActiveTimer,
      damageTakenCount: this.damageTakenCount,
      totalDamageTaken: this.totalDamageTaken,
      lastDamage: this.lastDamage,
      runtimeResetCount: this._runtimeResetCount,
      runtimeLastReset: this._runtimeLastReset,
      runtimeBaselineClean: this._isRuntimeBaselineClean()
    }
  }
}
