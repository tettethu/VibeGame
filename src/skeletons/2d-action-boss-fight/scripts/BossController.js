import { Node } from '/engine/Node.js'

const ATTACKS = ['ANTLER_SLAM', 'NEEDLE_LUNGE', 'THORN_VOLLEY']
const ATTACK_CLIPS = {
  ANTLER_SLAM: { all: 'antler_slam' },
  NEEDLE_LUNGE: {
    windup: 'needle_lunge_windup',
    active: 'needle_lunge_active',
    recovery: 'needle_lunge_recovery',
    all: 'needle_lunge'
  },
  THORN_VOLLEY: { all: 'thorn_volley_cast' }
}

export default class BossController extends Node {
  ready() {
    this.cfg = this.config || {}
    this.hp = this._num('hp')
    this.maxHp = this.hp
    this.state = 'IDLE'
    this.currentAttack = null
    this.attackPhase = null
    this.phaseTier = 'normal'
    this.facing = this._num('defaultFacing')
    this.aiEnabled = false
    this.stateTimer = 0
    this._lungeCommitted = false
    this._attackHitPlayer = false
    this._runtimeResetCount = 0
    this._runtimeLastReset = null
    this._frameEventKey = null
    this._frameEventLastProgress = -1
    this._frameEventsFired = new Set()

    this.cooldowns = Object.fromEntries(ATTACKS.map(k => [k, 0]))
    this.attackUseCounts = Object.fromEntries(ATTACKS.map(k => [k, 0]))

    this.attackHitboxes = Object.fromEntries(
      Object.entries(this.cfg.hitboxNodes || {}).map(([attack, name]) => [attack, this.getChild(name)])
    )
    this.hitboxFxNodes = Object.fromEntries(
      Object.entries(this.cfg.hitboxFxNodes || {}).map(([attack, path]) => [attack, this.getNode(path)])
    )
    this._disableHitboxes()
    this._hideHitboxFx()

    this._player = this.findByTag('player')[0] || null

    for (const n of this.findByTag('ground')) this.scene.physics.add.collider(this.gameObject, n.gameObject)
    for (const n of this.findByTag('wall')) this.scene.physics.add.collider(this.gameObject, n.gameObject)

    if (this._player?.gameObject) this._bindDamageHitboxes()

    this.on('hit', (data = {}) => this._takeDamage(data))
    this._syncVisualState()
  }

  _num(key) {
    return Number(this.cfg?.[key]) || 0
  }

  update(dt) {
    if (!this.gameObject?.body || this.state === 'DIE') return

    this._tickCooldowns(dt)
    this._facePlayer()
    this._updatePhaseTier()

    if (!this.aiEnabled) {
      this.gameObject.body.setVelocityX(0)
      return
    }

    switch (this.state) {
      case 'IDLE':
      case 'APPROACH':
        this._decideNeutral()
        break
      case 'WINDUP':
        this._tickWindup(dt)
        break
      case 'ACTIVE':
        this._tickActive(dt)
        break
      case 'RECOVERY':
        this._tickRecovery(dt)
        break
      case 'HURT':
        this._tickHurt(dt)
        break
    }
  }

  _tickCooldowns(dt) {
    for (const key of ATTACKS) this.cooldowns[key] = Math.max(0, this.cooldowns[key] - dt)
  }

  _updatePhaseTier() {
    this.phaseTier = this.hp / this.maxHp <= this.cfg.lowHpThreshold ? 'low_hp' : 'normal'
  }

  _decideNeutral() {
    if (!this._player?.gameObject) return
    const dx = this._player.gameObject.x - this.gameObject.x
    const dist = Math.abs(dx)
    const preferred = this._preferredAttack(dist)

    if (preferred && this.cooldowns[preferred] <= 0) {
      this._beginAttack(preferred)
      return
    }

    const body = this.gameObject.body
    if (dist < this.cfg.antlerSlamRange * this._num('neutralBackoffRangeMultiplier') && this.cooldowns.ANTLER_SLAM > 0) {
      body.setVelocityX(-Math.sign(dx || this.facing) * this.cfg.backoffSpeed)
    } else if (dist > this.cfg.antlerSlamRange * this._num('neutralApproachRangeMultiplier')) {
      body.setVelocityX(Math.sign(dx || this.facing) * this.cfg.approachSpeed)
    } else {
      body.setVelocityX(0)
    }
    this._setState(Math.abs(body.velocity.x) > this._num('approachVelocityThreshold') ? 'APPROACH' : 'IDLE')
  }

  _preferredAttack(dist) {
    if (dist <= this.cfg.antlerSlamRange) return 'ANTLER_SLAM'
    if (dist <= this.cfg.needleLungeRange) return 'NEEDLE_LUNGE'
    return 'THORN_VOLLEY'
  }

  _beginAttack(attack) {
    this.currentAttack = attack
    this.attackPhase = 'windup'
    this.stateTimer = this._duration('windup', attack)
    this._lungeCommitted = false
    this._attackHitPlayer = false
    this.gameObject.body.setVelocityX(0)
    this.attackUseCounts[attack] += 1
    const multiplier = this.phaseTier === 'low_hp' ? this.cfg.lowHpCooldownMultiplier : 1
    this.cooldowns[attack] = this._duration('cooldown', attack) * multiplier
    this._setState('WINDUP')
  }

  _tickWindup(dt) {
    this.gameObject.body.setVelocityX(0)
    this.stateTimer -= dt
    this._processFrameEvents()
    if (this.state !== 'WINDUP') return
    if (this.stateTimer <= 0 && this._isCurrentAnimationComplete()) this._enterActive(dt)
  }

  _enterActive(dt = 0, fromFrameEvent = false) {
    const attack = this.currentAttack
    if (!attack) return this._enterRecovery()
    this.attackPhase = 'active'
    this.stateTimer = this._duration('active', attack)
    this._attackHitPlayer = false
    this._setState('ACTIVE')
    if (fromFrameEvent) return
    if (this._hasFrameEvents(attack, 'active')) {
      this._processFrameEvents()
      return
    }

    if (attack === 'ANTLER_SLAM') {
      this._enableHitbox(attack)
      this._spawnConfiguredFx('groundCrack')
    }
    if (attack === 'NEEDLE_LUNGE') {
      this._enableHitbox(attack)
      this._startNeedleLungeMovement(dt)
    }
    if (attack === 'THORN_VOLLEY') this._spawnThornVolley()
  }

  _startNeedleLungeMovement(dt = 0) {
    const body = this.gameObject?.body
    if (!body) return
    const vx = this.facing * this.cfg.needleLungeSpeed
    body.setVelocityX(vx)
    this._lungeCommitted = true

    const step = Math.max(0, Number(dt) || 0)
    if (step > 0) {
      this.gameObject.x += vx * step
      body.updateFromGameObject?.()
    }
  }

  _tickActive(dt) {
    this.stateTimer -= dt
    this._processFrameEvents()
    if (this.state !== 'ACTIVE') return
    if (this.currentAttack === 'ANTLER_SLAM') this.gameObject.body.setVelocityX(0)
    // Active timer owns the damage window. Do not extend enabled hitboxes just
    // because a visual clip is still playing.
    if (this.stateTimer <= 0) this._enterRecovery()
  }

  _enterRecovery() {
    this._disableHitboxes()
    this.gameObject.body.setVelocityX(0)
    this.attackPhase = 'recovery'
    this.stateTimer = this._duration('recovery', this.currentAttack)
    this._setState('RECOVERY')
  }

  _tickRecovery(dt) {
    this.gameObject.body.setVelocityX(0)
    this.stateTimer -= dt
    this._syncRecoveryClip()
    if (this.stateTimer > 0 || !this._isCurrentAnimationComplete()) return
    this.currentAttack = null
    this.attackPhase = null
    this._resetFrameEventTracker()
    this._setState('IDLE')
  }

  _syncRecoveryClip() {
    if (!this.currentAttack) return
    this.playAnim(this._recoveryClipFor(this.currentAttack), { restart: false })
  }

  _recoveryClipFor(attack) {
    const recoveryClip = ATTACK_CLIPS[attack]?.recovery
    if (!recoveryClip) return 'idle'
    const elapsed = this._duration('recovery', attack) - this.stateTimer
    return elapsed < this._num('closingPoseHoldTime') ? recoveryClip : 'idle'
  }

  _tickHurt(dt) {
    this.gameObject.body.setVelocityX(0)
    this.stateTimer -= dt
    if (this.stateTimer <= 0 && this._isCurrentAnimationComplete()) this._setState('IDLE')
  }

  _duration(group, attack) {
    return Number(this.cfg?.[group]?.[attack]) || 0
  }

  _facePlayer() {
    if (!this._player?.gameObject || this.state === 'ACTIVE' && this.currentAttack === 'NEEDLE_LUNGE') return
    const dx = this._player.gameObject.x - this.gameObject.x
    if (Math.abs(dx) > this._num('facingDeadzone')) {
      this.facing = Math.sign(dx)
      this.visualObject?.setFlipX?.(this.facing > 0)
    }
  }

  _bindDamageHitboxes() {
    for (const [attack, hitbox] of Object.entries(this.attackHitboxes || {})) this._bindDamageHitbox(hitbox, attack)
  }

  _bindDamageHitbox(hitbox, attack) {
    if (!hitbox?.gameObject || !this._player?.gameObject) return
    this.scene.physics.add.overlap(hitbox.gameObject, this._player.gameObject, () => {
      if (this.state !== 'ACTIVE' || this.currentAttack !== attack || !hitbox.isEnabled?.()) return
      if (this._attackHitPlayer) return
      this._attackHitPlayer = true
      this._player.emit('hit', {
        damage: this.cfg.meleeDamage,
        attack,
        sourceX: this.gameObject?.x
      })
    })
  }

  _enableHitbox(attack) {
    const hitbox = this._hitboxFor(attack)
    if (!hitbox) return
    hitbox.enable()
    this._showHitboxFx(attack)
  }

  _disableHitbox(attack) {
    this._hitboxFor(attack)?.disable?.()
    this._hideHitboxFx(attack)
  }

  _disableHitboxes() {
    for (const hitbox of Object.values(this.attackHitboxes || {})) hitbox?.disable?.()
    this._hideHitboxFx()
  }

  _showHitboxFx(attack) {
    const fx = this.hitboxFxNodes?.[attack]
    const visual = fx?.getVisualObject?.()
    if (!visual) return
    visual.setVisible?.(true)
    if (visual.setAlpha) visual.setAlpha(1)
    const clip = fx.config?.clip || fx.animationPlayer?.def?.default
    if (clip) fx.playAnim(clip, { restart: true })
  }

  _hideHitboxFx(attack = null) {
    const entries = Object.entries(this.hitboxFxNodes || {})
    for (const [key, fx] of entries) {
      if (attack && key !== attack) continue
      const visual = fx?.getVisualObject?.()
      if (visual?.setVisible) visual.setVisible(false)
    }
  }

  resetForRuntimeEvidence(options = {}) {
    const x = Number.isFinite(options.x) ? options.x : this._num('x')
    const y = Number.isFinite(options.y) ? options.y : this._num('y')
    const resetHp = options.resetHp !== false
    const resetCooldowns = options.resetCooldowns !== false
    const resetAttackUseCounts = options.resetAttackUseCounts === true

    if (resetHp) this.hp = this.maxHp
    if (resetCooldowns) this.cooldowns = Object.fromEntries(ATTACKS.map(k => [k, 0]))
    if (resetAttackUseCounts) this.attackUseCounts = Object.fromEntries(ATTACKS.map(k => [k, 0]))

    this.aiEnabled = options.aiEnabled === true
    this.state = 'IDLE'
    this.currentAttack = null
    this.attackPhase = null
    this.phaseTier = 'normal'
    this.stateTimer = 0
    this._lungeCommitted = false
    this._attackHitPlayer = false
    this._resetFrameEventTracker()
    this._disableHitboxes()

    this._resetBodyPosition(x, y)
    this._facePlayer()
    this._syncVisualState()

    this._runtimeResetCount += 1
    this._runtimeLastReset = {
      x,
      y,
      aiEnabled: this.aiEnabled,
      resetHp,
      resetCooldowns,
      resetAttackUseCounts
    }

    return {
      cleanBaseline: this._isRuntimeBaselineClean(),
      runtime: this.runtimeState()
    }
  }

  forceRuntimeAttackActive(attack = 'ANTLER_SLAM') {
    if (!ATTACKS.includes(attack)) {
      return { error: `Unknown boss attack: ${attack}`, allowed: [...ATTACKS] }
    }

    this.aiEnabled = false
    this._disableHitboxes()
    this.currentAttack = attack
    this.attackPhase = 'active'
    this.stateTimer = this._duration('active', attack)
    this._attackHitPlayer = false
    this._lungeCommitted = false
    this._resetFrameEventTracker()
    this.gameObject?.body?.setVelocity?.(0, 0)
    this._setState('ACTIVE')

    if (attack === 'ANTLER_SLAM') {
      this._enableHitbox(attack)
      this._spawnConfiguredFx('groundCrack')
    }
    if (attack === 'NEEDLE_LUNGE') {
      this._enableHitbox(attack)
      this._startNeedleLungeMovement(this._num('runtimeStepDt'))
    }
    if (attack === 'THORN_VOLLEY') this._spawnThornVolley()

    return {
      forcedAttack: attack,
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
        body.blocked.down = false
      }
      if (body.touching) {
        body.touching.up = false
        body.touching.left = false
        body.touching.right = false
        body.touching.down = false
      }
    }
  }

  _resetFrameEventTracker() {
    this._frameEventKey = null
    this._frameEventLastProgress = -1
    this._frameEventsFired = new Set()
  }

  _isRuntimeBaselineClean() {
    const body = this.gameObject?.body
    const vx = body?.velocity?.x ?? 0
    const vy = body?.velocity?.y ?? 0
    return this.state === 'IDLE' &&
      this.currentAttack === null &&
      this.attackPhase === null &&
      this.aiEnabled === false &&
      Math.abs(vx) < this._num('velocityEpsilon') &&
      Math.abs(vy) < this._num('velocityEpsilon') &&
      Object.values(this.attackHitboxes || {}).every(hitbox => !hitbox?.isEnabled?.())
  }

  _spawnThornVolley() {
    const count = Math.max(1, Number(this.cfg.thornVolleyCount) || 1)
    const speed = this._num('thornProjectileSpeed')
    const spreadY = this._num('thornSpreadY')
    const center = (count - 1) / this._num('spreadCenterDivisor')
    const x = this.gameObject.x + this.facing * this._num('thornSpawnOffsetX')
    const y = this.gameObject.y + this._num('thornSpawnOffsetY')
    for (let i = 0; i < count; i++) {
      const vy = (i - center) * spreadY
      this.emit('spawn_thorn', {
        x,
        y: y + (i - center) * this._num('thornSpawnSpacingY'),
        vx: this.facing * speed,
        vy,
        damage: this.cfg.projectileDamage,
        attack: 'THORN_VOLLEY'
      })
    }
  }

  _takeDamage({ damage = 0 } = {}) {
    if (this.state === 'DIE') return
    const amount = Math.max(0, Number(damage) || 0)
    if (amount <= 0) return

    this.hp = Math.max(0, this.hp - amount)
    this.emit('boss_hit', { hp: this.hp, maxHp: this.maxHp })
    this.scene.cameras.main.shake(this._num('hitShakeMs'), this._num('hitShakeIntensity'))
    this._spawnConfiguredFx('hitSpark')

    if (this.hp <= 0) {
      this._die()
      return
    }

    if (this.state === 'IDLE' || this.state === 'APPROACH' || this.state === 'RECOVERY' || this.state === 'HURT') {
      this._disableHitboxes()
      this.currentAttack = null
      this.attackPhase = null
      this._resetFrameEventTracker()
      this.stateTimer = this.cfg.hurtDuration
      this._setState('HURT')
    }
  }

  _die() {
    this.hp = 0
    this.aiEnabled = false
    this.currentAttack = null
    this.attackPhase = null
    this._resetFrameEventTracker()
    this._disableHitboxes()
    this.gameObject.body.setVelocity(0, 0)
    this._setState('DIE')
    this._spawnConfiguredFx('deathBurst')
    this.emit('boss_die', {})
  }

  _setState(next) {
    if (this.state === next) return
    this.state = next
    this._syncVisualState()
  }

  _syncVisualState() {
    let clip = 'idle'
    if (this.state === 'APPROACH') clip = 'walk'
    else if (this.state === 'HURT') clip = 'hit'
    else if (this.state === 'DIE') clip = 'death'
    else if (this.currentAttack && (this.state === 'WINDUP' || this.state === 'ACTIVE')) {
      clip = this._attackClipFor(this.currentAttack, this.attackPhase) || 'idle'
    } else if (this.currentAttack && this.state === 'RECOVERY') {
      clip = this._recoveryClipFor(this.currentAttack)
    }
    this.playAnim(clip, { restart: false })
    this._syncFrameEventKey()
  }

  _attackClipFor(attack, phase) {
    const clips = ATTACK_CLIPS[attack]
    if (!clips) return null
    return clips[phase] || clips.all || null
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

  _syncFrameEventKey() {
    const key = `${this.currentAttack || 'none'}:${this.attackPhase || 'none'}:${this.animationPlayer?.currentClipName || 'none'}`
    if (this._frameEventKey === key) return
    this._frameEventKey = key
    this._frameEventLastProgress = -1
    this._frameEventsFired = new Set()
  }

  _frameProgress() {
    const player = this.animationPlayer
    const clip = player?.currentClip
    if (!clip) return 0
    const frames = Array.isArray(clip.frames) ? clip.frames : []
    if (clip.loop === false && player.isFinished?.()) return frames.length
    return player.currentFrameIndex ?? 0
  }

  _processFrameEvents() {
    const attack = this.currentAttack
    const phase = this.attackPhase
    if (!attack || !phase) return
    this._syncFrameEventKey()
    const events = this.cfg.frameEvents?.[attack]?.[phase] || []
    const current = this._frameProgress()
    const eventKey = this._frameEventKey
    if (!events.length) {
      this._frameEventLastProgress = current
      return
    }

    const previous = this._frameEventLastProgress
    events.forEach((event, index) => {
      const frame = Number(event.frame)
      if (!Number.isFinite(frame)) return
      const id = `${eventKey}:${index}`
      if (this._frameEventsFired.has(id)) return
      if (frame > previous && frame <= current) {
        this._frameEventsFired.add(id)
        this._triggerFrameEvent(event)
      }
    })
    if (this._frameEventKey === eventKey) this._frameEventLastProgress = current
  }

  _hasFrameEvents(attack, phase) {
    return Array.isArray(this.cfg.frameEvents?.[attack]?.[phase]) && this.cfg.frameEvents[attack][phase].length > 0
  }

  _triggerFrameEvent(event = {}) {
    switch (event.event) {
      case 'enter_active':
        this._enterActive(0, true)
        break
      case 'enter_recovery':
        this._enterRecovery()
        break
      case 'hitbox_on':
        this._enableHitbox(event.hitbox || this.currentAttack)
        break
      case 'hitbox_off':
        if (event.hitbox) this._disableHitbox(event.hitbox)
        else this._disableHitboxes()
        break
      case 'spawn_fx':
        this._spawnConfiguredFx(event.key)
        break
      case 'spawn_projectile':
        if (this.currentAttack === 'THORN_VOLLEY') this._spawnThornVolley()
        break
      case 'start_lunge':
        this._startNeedleLungeMovement(0)
        break
    }
  }

  _hitboxFor(attack) {
    return this.attackHitboxes?.[attack] || null
  }

  _isAttackHitboxEnabled(attack) {
    return !!this.attackHitboxes?.[attack]?.isEnabled?.()
  }

  _spawnConfiguredFx(key) {
    const fx = this.cfg.fx?.[key]
    if (!fx || !this.gameObject) return
    const offsetX = Number(fx.offsetX) || 0
    const offsetY = Number(fx.offsetY) || 0
    this.emit('spawn_fx', {
      ...fx,
      x: this.gameObject.x + this.facing * offsetX,
      y: this.gameObject.y + offsetY,
      facing: this.facing
    })
  }

  runtimeState() {
    const activeAttack = this.state === 'ACTIVE'
    return {
      x: this.gameObject?.x ?? null,
      y: this.gameObject?.y ?? null,
      velocity: {
        x: this.gameObject?.body?.velocity?.x ?? 0,
        y: this.gameObject?.body?.velocity?.y ?? 0
      },
      name: this.cfg?.name || null,
      hp: this.hp,
      maxHp: this.maxHp,
      state: this.state,
      currentAttack: this.currentAttack,
      attackPhase: this.attackPhase,
      phaseTier: this.phaseTier,
      facing: this.facing,
      aiEnabled: this.aiEnabled,
      cooldowns: { ...this.cooldowns },
      enabledHitboxes: {
        ANTLER_SLAM: this._isAttackHitboxEnabled('ANTLER_SLAM'),
        NEEDLE_LUNGE: this._isAttackHitboxEnabled('NEEDLE_LUNGE')
      },
      hitboxFx: this._hitboxFxState(),
      activeAttackHitPlayer: activeAttack ? this._attackHitPlayer : false,
      lungeCommitted: activeAttack && this.currentAttack === 'NEEDLE_LUNGE' ? this._lungeCommitted : false,
      animation: {
        clip: this.animationPlayer?.currentClipName || null,
        frameIndex: this.animationPlayer?.currentFrameIndex ?? null,
        frame: this.animationPlayer?.currentClip?.frames?.[this.animationPlayer?.currentFrameIndex] || null,
        finished: this._isCurrentAnimationComplete()
      },
      attackUseCounts: { ...this.attackUseCounts },
      runtimeResetCount: this._runtimeResetCount,
      runtimeLastReset: this._runtimeLastReset,
      runtimeBaselineClean: this._isRuntimeBaselineClean()
    }
  }

  _hitboxFxState() {
    const out = {}
    for (const [attack, fx] of Object.entries(this.hitboxFxNodes || {})) {
      const visual = fx?.getVisualObject?.()
      out[attack] = {
        exists: !!fx,
        visible: visual?.visible === true,
        clip: fx?.animationPlayer?.currentClipName || null,
        frame: fx?.animationPlayer?.currentClip?.frames?.[fx?.animationPlayer?.currentFrameIndex] || null
      }
    }
    return out
  }
}
