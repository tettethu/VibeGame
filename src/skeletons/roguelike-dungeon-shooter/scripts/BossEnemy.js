import Enemy from './Enemy.js'
import Bullet from './Bullet.js'
import { generateId } from '/engine/Node.js'

// Boss state machine: CHASE -> ATTACK -> RETREAT -> repeat
// Phase 1: chase + bullet patterns + summon wraith shards
// Phase 2: faster erratics chase + denser patterns + tracking burst, no summon

const BOSS_SOUL_TRAIL = 0x8a78ff

const BULLET_MAP = {
  orb: { texKey: 'bullet_boss_soul_orb', style: 'boss_soul_orb', trailColor: BOSS_SOUL_TRAIL, trailInterval: 0.06 },
  shard: { texKey: 'bullet_boss_soul_shard', style: 'boss_soul_shard', trailColor: BOSS_SOUL_TRAIL, trailInterval: 0.06 },
  dart: { texKey: 'bullet_boss_soul_dart', style: 'boss_soul_dart', trailColor: BOSS_SOUL_TRAIL, trailInterval: 0.06 },
  wraith_slash: { texKey: 'bullet_boss_soul_wave', style: 'boss_soul_wave', trailColor: BOSS_SOUL_TRAIL, trailInterval: 0.08 },
}

const WK_ATLAS = 'wraith_knight_atlas'
const WK_FRAMES = {
  idle: ['idle_0', 'idle_1'],
  walk: ['walk_0', 'walk_1'],
  slash: ['slash_0', 'slash_1'],
  die: ['die_0', 'die_1'],
}

const States = { CHASE: 'CHASE', ATTACK: 'ATTACK', RETREAT: 'RETREAT' }

export default class BossEnemy extends Enemy {
  ready() {
    const c = this.config
    this.bulletDamage = c.bulletDamage || 15
    this.baseBulletSpeed = c.baseBulletSpeed || 150
    this.phaseThreshold = c.phaseThreshold || 0.4
    this.transitionDuration = c.transitionDuration || 2.5

    this.chaseSpeed = c.chaseSpeed || 120
    this.attackRange = c.attackRange || 200
    this.contactDamage = c.contactDamage || 25
    this.contactCooldownTime = c.contactCooldown || 0.8
    this.retreatDuration = c.retreatDuration || 0.8
    this.retreatSpeed = c.retreatSpeed || 80

    // Minion summon config
    this._minionSpawnInterval = c.minionSpawnInterval || 10
    this._minionMaxCount = c.minionMaxCount || 4
    this._minionPerSpawn = c.minionPerSpawn || 2
    this._minionSpawnTimer = this._minionSpawnInterval

    // Transition hand skill config
    this._transitionHandCount = c.transitionHandCount || 10
    this._transitionHandDamage = c.transitionHandDamage || 8
    this._transitionHandDuration = c.transitionHandDuration || 1.0
    this._transitionHandCooldown = c.transitionHandCooldown || 0.8

    this.gameObject.setDepth(7)
    this.gameObject.setScale(1, 1)

    // Wraith Knight animation state
    this._wkKey = 'idle'
    this._wkFrame = 0
    this._wkTimer = 0
    this._wkInterval = 0.25
    this._chaseStarted = false

    this._initEnemy(c)

    // Boss uses the bottom HUD boss bar only; remove the inherited overhead HP bar
    if (this._hpBg) { this._hpBg.destroy(); this._hpBg = null }
    if (this._hpBar) { this._hpBar.destroy(); this._hpBar = null }

    // Push initial boss HP to HUD
    const hudInit = this.findByTag('hud')[0]
    if (hudInit) hudInit.updateBossHP(this.hp, this.maxHP, 1)

    // State machine
    this._state = States.CHASE
    this._stateTimer = 0
    this._contactCooldown = 0
    this._attackToken = 0

    // Phase state
    this._phase = 1
    this._transitioning = false
    this._transitionTimer = 0
    this._phaseTransitioned = false

    // Phase 2 chase drift
    this._chaseDriftAngle = 0
    this._chaseDriftTimer = 0
    this._chaseDriftInterval = 2.5

    // Transition hand objects (managed directly, not as enemy instances)
    this._transitionHands = []

    // Entrance delay
    this._entranceTimer = 2.0

    this._spawnEffect()
  }

  // -- Main update loop --

  update(dt) {
    if (this._dead) return
    this._tickHpBar()
    this._contactCooldown = Math.max(0, this._contactCooldown - dt)

    // Entrance animation: stand still
    if (this._entranceTimer > 0) {
      this._entranceTimer -= dt
      this._facePlayer()
      this._tickBossAnim(dt)
      return
    }

    if (!this._chaseStarted) {
      this._chaseStarted = true
      this._setBossVisual('walk')
    }

    if (this._transitioning) {
      this._updateTransition(dt)
      return
    }

    // Phase threshold check
    const hpRatio = this.hp / this.maxHP
    if (this._phase === 1 && hpRatio <= this.phaseThreshold && !this._phaseTransitioned) {
      this._startTransition()
      return
    }

    this._facePlayer()

    // Phase 1 minion spawning (not during transition, not in Phase 2)
    if (this._phase === 1) {
      this._updateMinionSpawn(dt)
    }

    switch (this._state) {
      case States.CHASE:   this._updateChase(dt); break
      case States.ATTACK:  this._updateAttack(dt); break
      case States.RETREAT: this._updateRetreat(dt); break
    }

    this._clampToArena()
    this._tickBossAnim(dt)

    // Phase 2 periodic pulse ring
    if (this._phase === 2 && !this._transitioning) {
      this._phase2PulseTimer = (this._phase2PulseTimer || 0) + dt
      if (this._phase2PulseTimer >= 2.0) {
        this._phase2PulseTimer = 0
        this._pulseEffect(0xff4444, 0.4)
      }
    }
  }

  // -- CHASE: move toward player --

  _updateChase(dt) {
    const player = this._getPlayer()
    if (!player) return

    const dist = Phaser.Math.Distance.Between(
      this.gameObject.x, this.gameObject.y, player.x, player.y
    )

    if (dist <= this.attackRange) {
      this._enterAttack()
      return
    }

    const angle = Phaser.Math.Angle.Between(
      this.gameObject.x, this.gameObject.y, player.x, player.y
    )

    if (this._phase === 2) {
      // Phase 2: faster + aggressive drift offset every 1-2s
      this._chaseDriftTimer += dt
      if (this._chaseDriftTimer >= this._chaseDriftInterval) {
        this._chaseDriftTimer = 0
        this._chaseDriftAngle = Phaser.Math.DegToRad(25 + Math.random() * 15) * (Math.random() < 0.5 ? 1 : -1)
        this._chaseDriftInterval = 1 + Math.random()
      }
      const speed = this.chaseSpeed * 1.6
      const driftAngle = angle + this._chaseDriftAngle
      this.gameObject.body.setVelocity(
        Math.cos(driftAngle) * speed,
        Math.sin(driftAngle) * speed
      )
    } else {
      this.gameObject.body.setVelocity(
        Math.cos(angle) * this.chaseSpeed,
        Math.sin(angle) * this.chaseSpeed
      )
    }
  }

  // -- ATTACK: fire a bullet pattern, stay still --

  _enterAttack() {
    this._attackToken++
    this._state = States.ATTACK
    this._stateTimer = 1.5
    this._firedPattern = false
    this.gameObject.body.setVelocity(0, 0)
    this._setBossVisual('slash')
    this._showSlashArc()
    this._showTelegraph()
  }

  _updateAttack(dt) {
    this._stateTimer -= dt
    // Fire pattern after 0.3s telegraph window
    if (!this._firedPattern && this._stateTimer <= 1.2) {
      this._firedPattern = true
      this._firePattern()
    }
    if (this._stateTimer <= 0) {
      this._hideTelegraph()
      this._enterRetreat()
    }
  }

  _firePattern() {
    // Screen shake on attack
    this.scene.cameras.main.shake(150, 0.004)

    // Phase 2 has its own aggressive combo patterns
    const patterns = this._phase === 2
      ? ['tracking_cross', 'tracking_spiral', 'tracking_fan', 'cross_spiral']
      : ['ring', 'aimed', 'ring', 'cross', 'aimed']
    const pick = patterns[Math.floor(Math.random() * patterns.length)]
    switch (pick) {
      case 'ring':      this._attackRingBurst(); break
      case 'aimed':     this._attackAimedFan(); break
      case 'cross':     this._attackCrossBurst(); break
      case 'spiral':    this._attackRotatingSpiral(); break
      case 'tracking':  this._attackTrackingBurst(); break
      // Phase 2 combo patterns
      case 'tracking_cross':  this._attackTrackingBurst(); this.scene.time.delayedCall(400, () => this._attackCrossBurst()); break
      case 'tracking_spiral': this._attackTrackingBurst(); this.scene.time.delayedCall(300, () => this._attackRotatingSpiral()); break
      case 'tracking_fan':    this._attackTrackingBurst(); this.scene.time.delayedCall(350, () => this._attackAimedFan()); break
      case 'cross_spiral':    this._attackCrossBurst(); this.scene.time.delayedCall(500, () => this._attackRotatingSpiral()); break
    }
  }

  // -- RETREAT: brief backwards movement --

  _enterRetreat() {
    this._setBossVisual('walk')
    this._state = States.RETREAT
    // Phase 2: near-zero retreat
    this._stateTimer = this._phase === 2
      ? Math.min(this.retreatDuration * 0.25, 0.2)
      : this.retreatDuration

    const player = this._getPlayer()
    if (player) {
      const awayAngle = Phaser.Math.Angle.Between(
        player.x, player.y, this.gameObject.x, this.gameObject.y
      )
      this.gameObject.body.setVelocity(
        Math.cos(awayAngle) * this.retreatSpeed,
        Math.sin(awayAngle) * this.retreatSpeed
      )
    }
  }

  _updateRetreat(dt) {
    this._stateTimer -= dt
    if (this._stateTimer <= 0) {
      this.gameObject.body.setVelocity(0, 0)
      this._state = States.CHASE
    }
  }

  // -- Contact damage --

  onContactPlayer(player) {
    if (this._dead || this._contactCooldown > 0) return
    if (player._invincible || player._rolling || (player._rollGraceTimer && player._rollGraceTimer > 0)) return
    this._contactCooldown = this.contactCooldownTime
    player.takeDamage(this.contactDamage)
  }

  // -- Minion spawning (Phase 1 only) --

  _updateMinionSpawn(dt) {
    this._minionSpawnTimer -= dt
    if (this._minionSpawnTimer > 0) return
    this._minionSpawnTimer = this._minionSpawnInterval

    // Count alive minions
    const minions = this.findByTag('boss_minion')
    const alive = minions.filter(m => !m._dead).length
    if (alive >= this._minionMaxCount) return

    const gm = this._getGM()
    if (!gm) return

    const count = Math.min(this._minionPerSpawn, this._minionMaxCount - alive)
    for (let i = 0; i < count; i++) {
      this._spawnMinion(gm)
    }
  }

  _spawnMinion(gm) {
    const bx = this.gameObject.x
    const by = this.gameObject.y
    const spread = 200
    const x = bx + (Math.random() - 0.5) * spread * 2
    const y = by + (Math.random() - 0.5) * spread * 2
    gm.instantiate('entities/wraith_shard.node.json', { x, y }).catch(() => {})
  }

  // -- Attack topologies --

  _attackRingBurst() {
    const gm = this._getGM()
    if (!gm) return
    const cx = this.gameObject.x, cy = this.gameObject.y
    const n = this._phase === 2 ? 16 : 10
    const spd = this.baseBulletSpeed
    for (let i = 0; i < n; i++) {
      const a = (Math.PI * 2 / n) * i
      this._spawnBullet(gm, cx, cy, Math.cos(a) * spd, Math.sin(a) * spd, 'orb')
    }
  }

  _attackAimedFan() {
    const gm = this._getGM()
    if (!gm) return
    const player = this._getPlayer()
    if (!player) return
    const cx = this.gameObject.x, cy = this.gameObject.y
    const n = this._phase === 2 ? 7 : 5
    const spreadRad = Phaser.Math.DegToRad(this._phase === 2 ? 40 : 25)
    const spd = this.baseBulletSpeed * 1.5
    const baseAngle = Phaser.Math.Angle.Between(cx, cy, player.x, player.y)
    for (let i = 0; i < n; i++) {
      const offset = n === 1 ? 0 : -spreadRad + (2 * spreadRad / (n - 1)) * i
      const a = baseAngle + offset
      this._spawnBullet(gm, cx, cy, Math.cos(a) * spd, Math.sin(a) * spd, 'dart')
    }
  }

  _attackCrossBurst() {
    const gm = this._getGM()
    if (!gm) return
    const cx = this.gameObject.x, cy = this.gameObject.y
    const arms = 4
    const perArm = this._phase === 2 ? 3 : 2
    const spd = this.baseBulletSpeed * 1.2
    const baseOffset = Math.random() * Math.PI / 2
    const attackToken = this._attackToken
    for (let arm = 0; arm < arms; arm++) {
      const dir = (Math.PI * 2 / arms) * arm + baseOffset
      for (let j = 0; j < perArm; j++) {
        const delay = j * 100
        this.scene.time.delayedCall(delay, () => {
          if (this._dead || attackToken !== this._attackToken) return
          this._spawnBullet(gm, cx, cy, Math.cos(dir) * spd, Math.sin(dir) * spd, 'wraith_slash')
        })
      }
    }
  }

  _attackRotatingSpiral() {
    const gm = this._getGM()
    if (!gm) return
    const cx = this.gameObject.x, cy = this.gameObject.y
    const n = 8
    const spd = this.baseBulletSpeed * 0.9
    const shots = 4
    const attackToken = this._attackToken
    for (let s = 0; s < shots; s++) {
      const offset = (Math.PI * 2 / shots) * s
      this.scene.time.delayedCall(s * 150, () => {
        if (this._dead || attackToken !== this._attackToken) return
        for (let i = 0; i < n; i++) {
          const a = (Math.PI * 2 / n) * i + offset
          this._spawnBullet(gm, cx, cy, Math.cos(a) * spd, Math.sin(a) * spd, 'orb')
        }
      })
    }
  }

  // Phase 2 exclusive: tracking burst - bullets continuously steer toward player
  _attackTrackingBurst() {
    const gm = this._getGM()
    if (!gm) return
    const player = this._getPlayer()
    if (!player) return
    const cx = this.gameObject.x, cy = this.gameObject.y
    const n = 5
    const spd = this.baseBulletSpeed * 0.6
    const attackToken = this._attackToken
    const trackCfg = { tracking: true, trackTurnRate: 2.0, trackLife: 3.0 }
    for (let i = 0; i < n; i++) {
      this.scene.time.delayedCall(i * 200, () => {
        if (this._dead || attackToken !== this._attackToken) return
        const px = player.x, py = player.y
        const a = Phaser.Math.Angle.Between(cx, cy, px, py)
        const wobble = Phaser.Math.DegToRad(-15 + Math.random() * 30)
        const finalA = a + wobble
        this._spawnBullet(gm, cx, cy, Math.cos(finalA) * spd, Math.sin(finalA) * spd, 'shard', trackCfg)
      })
    }
  }

  // -- Bullet spawn helper --

  _spawnBullet(gm, x, y, vx, vy, bulletType, extraConfig) {
    if (this._dead) return
    const info = BULLET_MAP[bulletType] || BULLET_MAP.orb
    const bullet = new Bullet()
    bullet.id = generateId()
    bullet.config = {
      x, y, vx, vy,
      damage: this.bulletDamage,
      isEnemy: true,
      texKey: info.texKey,
      style: info.style,
      trailColor: info.trailColor,
      trailInterval: info.trailInterval,
      ...extraConfig,
    }
    gm.addChild(bullet)
  }

  // -- Phase transition with skeleton hand skill --

  _startTransition() {
    this._transitioning = true
    this._transitionTimer = this.transitionDuration
    this._phaseTransitioned = true
    this._attackToken++
    this._hideTelegraph()
    this.gameObject.body.setVelocity(0, 0)

    this._setBossVisual('idle', 0xff2222)
    this._pulseEffect(0x44ccff, 0.5)

    const hud = this.findByTag('hud')[0]
    if (hud) hud.showNotify('PHASE 2 - EXECUTION', 2500)

    this._clearBossBullets()

    // Spawn transition skeleton hands after 1s delay (within the 2.5s transition)
    this.scene.time.delayedCall(1000, () => {
      if (this._dead) return
      this._spawnTransitionHands()
    })
  }

  _updateTransition(dt) {
    this._transitionTimer -= dt
    const t = 1 - (this._transitionTimer / this.transitionDuration)
    const pulse = Math.sin(t * Math.PI * 6) * 0.3 + 1.0
    this.gameObject.setScale(1 * pulse, 1 * pulse)

    // Update hand contact damage
    this._updateTransitionHands(dt)

    if (this._transitionTimer <= 0) {
      // Clean up remaining hands
      this._cleanupTransitionHands()
      this._transitioning = false
      this._phase = 2
      this.gameObject.setScale(1.3, 1.3)
      this._setBossVisual('walk', 0xff8888)

      // Phase 2 periodic pulse ring
      this._phase2PulseTimer = 0

      this._state = States.CHASE
      const hud = this.findByTag('hud')[0]
      if (hud) hud.showBossPhase2()
    }
  }

  _spawnTransitionHands() {
    const player = this._getPlayer()
    const px = player ? player.x : this.gameObject.x
    const py = player ? player.y : this.gameObject.y
    const wb = this.scene.physics.world.bounds
    const margin = 60
    const safeRadius = 120
    const minSpacing = 80
    const count = this._transitionHandCount

    const positions = []
    let attempts = 0
    while (positions.length < count && attempts < 200) {
      attempts++
      const spread = 300
      const x = px + (Math.random() - 0.5) * spread * 2
      const y = py + (Math.random() - 0.5) * spread * 2

      // Exclude player safe zone
      const distToPlayer = Phaser.Math.Distance.Between(x, y, px, py)
      if (distToPlayer < safeRadius) continue

      // Min spacing from other hands
      const tooClose = positions.some(p =>
        Phaser.Math.Distance.Between(x, y, p.x, p.y) < minSpacing
      )
      if (tooClose) continue

      positions.push({ x, y })
    }

    // Phase 1: warning markers (0.5s pulsing circles)
    const warnings = []
    for (const pos of positions) {
      const circle = this.scene.add.circle(pos.x, pos.y, 20, 0x44ff88, 0)
        .setStrokeStyle(2, 0x44ff88, 0.6)
        .setDepth(6)
      this.scene.tweens.add({
        targets: circle,
        alpha: 0.8,
        duration: 250,
        yoyo: true,
        repeat: 1,
      })
      warnings.push(circle)
    }

    // Phase 2: after 0.5s, show hands + enable damage
    this.scene.time.delayedCall(500, () => {
      for (const w of warnings) w.destroy()

      for (const pos of positions) {
        // Danger zone circle under each hand
        const dangerCircle = this.scene.add.circle(pos.x, pos.y, 32, 0xff2222, 0.25)
          .setDepth(5)

        const sprite = this.scene.add.image(pos.x, pos.y, 'sk_hand_emerge', 'emerge_0')
          .setDisplaySize(64, 64)
          .setTint(0x88ffaa)
          .setDepth(6)
          .setAlpha(0.9)
          .setScale(0.1)

        // Scale-in emerge animation
        this.scene.tweens.add({
          targets: sprite,
          scaleX: 1,
          scaleY: 1,
          duration: 300,
          ease: 'Back.easeOut',
        })
        this._playTransitionHandEmerge(sprite)

        const handData = {
          sprite,
          dangerCircle,
          x: pos.x,
          y: pos.y,
          cooldown: 0,
          damage: this._transitionHandDamage,
          halfW: 32,
          halfH: 32,
        }
        this._transitionHands.push(handData)
      }

      // Hands disappear after duration
      const duration = this._transitionHandDuration * 1000
      this.scene.time.delayedCall(duration, () => {
        this._cleanupTransitionHands()
      })
    })
  }

  _playTransitionHandEmerge(sprite) {
    const frames = ['emerge_0', 'emerge_1', 'emerge_2', 'emerge_3']
    const frameMs = 90
    for (let i = 0; i < frames.length; i++) {
      this.scene.time.delayedCall(i * frameMs, () => {
        if (!sprite || !sprite.active) return
        sprite.setTexture('sk_hand_emerge', frames[i])
      })
    }
  }

  _updateTransitionHands(dt) {
    const players = this.findByTag('player')
    if (players.length === 0 || !players[0].gameObject) return
    const player = players[0]
    const pgo = player.gameObject
    if (player._dead) return

    for (const hand of this._transitionHands) {
      hand.cooldown = Math.max(0, hand.cooldown - dt)
      if (hand.cooldown > 0) continue

      // Hurtbox overlap: prefer physics body
      const pHW = pgo.body ? pgo.body.halfWidth : (pgo.displayWidth || 32) / 2
      const pHH = pgo.body ? pgo.body.halfHeight : (pgo.displayHeight || 48) / 2
      if (Math.abs(hand.x - pgo.x) < hand.halfW + pHW &&
          Math.abs(hand.y - pgo.y) < hand.halfH + pHH) {
        if (player.isRollInvincible && player.isRollInvincible()) continue
        player.takeDamage(hand.damage)
        hand.cooldown = this._transitionHandCooldown
      }
    }
  }

  _cleanupTransitionHands() {
    for (const hand of this._transitionHands) {
      if (hand.dangerCircle && hand.dangerCircle.active) {
        this.scene.tweens.add({
          targets: hand.dangerCircle,
          alpha: 0,
          duration: 400,
          onComplete: () => hand.dangerCircle.destroy()
        })
      }
      if (hand.sprite && hand.sprite.active) {
        this.scene.tweens.add({
          targets: hand.sprite,
          alpha: 0,
          scaleX: 0.1,
          scaleY: 0.1,
          duration: 400,
          onComplete: () => hand.sprite.destroy()
        })
      }
    }
    this._transitionHands = []
  }

  // -- Wraith Knight visual helpers --

  _setBossVisual(action, tint) {
    this._wkKey = action
    this._wkFrame = 0
    this._wkTimer = 0
    const frames = WK_FRAMES[action]
    if (frames) this.gameObject.setTexture(WK_ATLAS, frames[0])
    if (action === 'slash') {
      this.gameObject.setDisplaySize(200, 130)
    } else {
      this.gameObject.setDisplaySize(96, 192)
    }
    if (tint !== undefined) this.gameObject.setTint(tint)
  }

  _showSlashArc() {
    const go = this.gameObject
    if (!go) return
    const flip = go.flipX ? -1 : 1
    const cx = go.x + flip * 40
    const cy = go.y - 10
    const g = this.scene.add.graphics().setDepth(8)
    const baseAngle = flip > 0 ? -Math.PI * 0.6 : Math.PI * 0.4
    g.lineStyle(6, 0x88ddff, 0.7)
    g.beginPath()
    g.arc(cx, cy, 60, baseAngle, baseAngle + Math.PI * 0.8, false)
    g.strokePath()
    this.scene.tweens.add({
      targets: g,
      alpha: 0,
      duration: 300,
      ease: 'Quad.easeOut',
      onComplete: () => g.destroy()
    })
  }

  _tickBossAnim(dt) {
    const frames = WK_FRAMES[this._wkKey]
    if (!frames || frames.length <= 1) return
    this._wkTimer += dt
    if (this._wkTimer >= this._wkInterval) {
      this._wkTimer = 0
      this._wkFrame = (this._wkFrame + 1) % frames.length
      this.gameObject.setTexture(WK_ATLAS, frames[this._wkFrame])
    }
  }

  // -- Visual effects --

  _showTelegraph() {
    this.gameObject.setTint(0xffffff)
  }

  _hideTelegraph() {
    if (!this._dead) {
      if (this._phase === 2) {
        this.gameObject.setTint(0xff8888)
      } else {
        this.gameObject.clearTint()
      }
    }
  }

  _pulseEffect(color, duration) {
    if (!this.gameObject) return
    const ring = this.scene.add.circle(this.gameObject.x, this.gameObject.y, 10, color, 0.6)
      .setBlendMode(Phaser.BlendModes.ADD)
      .setDepth(8)
    this.scene.tweens.add({
      targets: ring,
      scaleX: 8, scaleY: 8,
      alpha: 0,
      duration: duration * 1000,
      onComplete: () => ring.destroy()
    })
  }

  _spawnEffect() {
    this.gameObject.setAlpha(0)
    this.scene.tweens.add({
      targets: this.gameObject,
      alpha: 1,
      duration: 600,
      ease: 'Quad.easeInOut'
    })
    this._pulseEffect(0x44ccff, 0.8)
  }

  _clearBossBullets() {
    const allNodes = [...this.sceneTree.nodes.values()]
    const bossBullets = allNodes.filter(n =>
      n.constructor?.name === 'Bullet' && n.isEnemy && n.gameObject && !n._destroyed
    )
    for (const b of bossBullets) {
      b._destroyed = true
      this.scene.time.delayedCall(0, () => b.removeSelf())
    }
  }

  // -- Helpers --

  _getGM() {
    if (this._dead) return null
    return this.findByTag('game_manager')[0]
  }

  _getPlayer() {
    const players = this.findByTag('player')
    if (players.length === 0 || !players[0].gameObject) return null
    return players[0].gameObject
  }

  _facePlayer() {
    const player = this._getPlayer()
    if (player) {
      this.gameObject.setFlipX(player.x < this.gameObject.x)
    }
  }

  // Keep boss inside arena walls (48px margin)
  _clampToArena() {
    const go = this.gameObject
    if (!go || !go.body) return
    const wb = this.scene.physics.world.bounds
    const margin = 48
    const hw = go.body.halfWidth
    const hh = go.body.halfHeight
    const minX = wb.x + margin + hw
    const maxX = wb.x + wb.width - margin - hw
    const minY = wb.y + margin + hh
    const maxY = wb.y + wb.height - margin - hh

    let vx = go.body.velocity.x
    let vy = go.body.velocity.y
    if (go.x < minX) { go.x = minX; vx = Math.max(0, vx) }
    if (go.x > maxX) { go.x = maxX; vx = Math.min(0, vx) }
    if (go.y < minY) { go.y = minY; vy = Math.max(0, vy) }
    if (go.y > maxY) { go.y = maxY; vy = Math.min(0, vy) }
    go.body.setVelocity(vx, vy)
  }

  _tickHpBar() {
    super._tickHpBar()
    if (this._dead) return
    const hud = this.findByTag('hud')[0]
    if (hud) hud.updateBossHP(this.hp, this.maxHP, this._phase)
  }

  runtimeState() {
    return {
      state: this._state,
      phase: this._phase,
      hp: this.hp,
      maxHP: this.maxHP,
      x: this.gameObject?.x,
      y: this.gameObject?.y,
      transitioning: this._transitioning,
      minionCount: this.findByTag('boss_minion').filter(m => !m._dead).length,
    }
  }

  _die() {
    if (this._dead) return
    // Step 6: clean up all boss minions
    const minions = this.findByTag('boss_minion')
    for (const m of minions) {
      if (!m._dead) m._die()
    }
    // Clean up transition hands
    this._cleanupTransitionHands()

    // Hide boss HUD bar
    const hud = this.findByTag('hud')[0]
    if (hud) hud.hideBossHP()

    this._hideTelegraph()
    this._attackToken++
    this._clearBossBullets()
    this._setBossVisual('die')
    this._pulseEffect(0x44ccff, 1.0)
    this._pulseEffect(0x88ddff, 0.8)
    super._die()
  }
}
