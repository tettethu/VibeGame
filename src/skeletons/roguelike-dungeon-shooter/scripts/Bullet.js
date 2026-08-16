import { Node } from '/engine/Node.js'

// Bullet: movement, bounds check, destruction. Uses an SVG image.
export default class Bullet extends Node {
  ready() {
    const c = this.config
    const gm = this.findByTag('game_manager')[0]
    const bulletsCfg = gm?.elementsConfig?.bullets || {}
    this.damage = c.damage || 10
    this.isCrit = c.isCrit || false
    this.isEnemy = c.isEnemy || false
    this.isRocket = c.isRocket || false
    this.splashDamage = c.splashDamage || 0
    this.splashRadius = c.splashRadius || 0
    this.penetrateCount = c.penetrateCount || 0
    this._destroyed = false

    // Tracking config
    this.tracking = c.tracking || false
    this.trackTurnRate = c.trackTurnRate || 2.0
    this._trackLife = c.trackLife || 3.0

    // Pick the bullet texture
    let texKey = c.texKey
    if (!texKey) {
      texKey = 'bullet_player'
      if (this.isEnemy) texKey = 'bullet_enemy'
    }

    const styleKey = c.style || (this.isRocket ? 'rocket' : (this.isEnemy ? 'enemy' : 'player'))
    const styleCfg = bulletsCfg[styleKey] || {}

    const vx = c.vx || 0
    const vy = c.vy || 0
    const angle = Math.atan2(vy, vx)
    const color = this.isRocket ? 0xff9b42 : (this.isEnemy ? 0xff5a54 : 0xffde59)
    const width = c.w ?? styleCfg.width ?? bulletsCfg.player?.width
    const height = c.h ?? styleCfg.height ?? bulletsCfg.player?.height
    const glowAlpha = c.glowAlpha ?? styleCfg.glowAlpha ?? bulletsCfg.player?.glowAlpha
    const boundsPadding = bulletsCfg.boundsPadding

    this._glow = null
    if (glowAlpha != null && glowAlpha > 0) {
      this._glow = this.scene.add.circle(c.x || 0, c.y || 0, Math.max(width, height), color, glowAlpha)
        .setBlendMode(Phaser.BlendModes.ADD)
        .setDepth(3)
    }

    this.gameObject = this.scene.add.image(c.x || 0, c.y || 0, texKey)
    this.gameObject.setDisplaySize(width, height)
    this.gameObject.setRotation(angle)
    this.scene.physics.add.existing(this.gameObject)
    this.gameObject.body.setAllowGravity(false)
    this.gameObject.body.setVelocity(vx, vy)
    this.gameObject.setDepth(4)
    gm?.addWallCollision?.(this.gameObject, () => this.onBlocked())

    this._bounds = {
      left: -boundsPadding,
      right: (this.scene.physics.world.bounds?.width || this.scene.scale.width) + boundsPadding,
      top: -boundsPadding,
      bottom: (this.scene.physics.world.bounds?.height || this.scene.scale.height) + boundsPadding
    }

    this._fxConfig = {
      explosionAlpha: bulletsCfg.explosionAlpha,
      explosionScale: bulletsCfg.explosionScale,
      explosionDurationMs: bulletsCfg.explosionDurationMs
    }

    this._visualTime = Math.random() * 10
    this._animFrameInterval = c.animFrameInterval ?? styleCfg.animFrameInterval ?? 0.07
    this._animPulseAmount = c.animPulseAmount ?? styleCfg.animPulseAmount ?? 0.08
    this._glowPulseAmount = c.glowPulseAmount ?? styleCfg.glowPulseAmount ?? 0.14
    this._baseGlowAlpha = glowAlpha || 0
    this._baseDisplayWidth = width
    this._baseDisplayHeight = height
    const altKey = `${texKey}_alt`
    this._altTexKey = this.scene.textures.exists(altKey) ? altKey : null
    this._activeTexKey = texKey

    // Trail config: player/boss bullets get trails
    this._trailTimer = 0
    this._trailInterval = c.trailInterval ?? (this.isRocket ? 0.03 : 0.025)
    if (c.trailColor != null) this._trailColor = c.trailColor
    else if (this.isRocket) this._trailColor = 0xff9b42
    else if (!this.isEnemy) this._trailColor = 0xffde59
    else this._trailColor = null

    // Rocket: bigger chunkier trail puffs
    this._trailRadius = this.isRocket ? 4.5 : 2.5
    this._trailDuration = this.isRocket ? 350 : 180
    this._trailAlpha = this.isRocket ? 0.55 : 0.45
  }

  update(dt) {
    if (!this.gameObject || this._destroyed) return
    this._visualTime += dt
    const x = this.gameObject.x, y = this.gameObject.y
    if (this._glow) this._glow.setPosition(x, y)
    this._updateVisualPulse()
    // Player bullet trail
    if (this._trailColor) {
      this._trailTimer += dt
      while (this._trailTimer >= this._trailInterval) {
        this._trailTimer -= this._trailInterval
        this._spawnTrail()
      }
    }

    // Tracking: steer toward player each frame
    if (this.tracking && !this._destroyed) {
      const players = this.findByTag('player')
      if (players.length > 0 && players[0].gameObject) {
        const pgo = players[0].gameObject
        const targetAngle = Phaser.Math.Angle.Between(x, y, pgo.x, pgo.y)
        const currentAngle = Math.atan2(this.gameObject.body.velocity.y, this.gameObject.body.velocity.x)
        const delta = Phaser.Math.Angle.Wrap(targetAngle - currentAngle)
        const step = Math.sign(delta) * Math.min(Math.abs(delta), this.trackTurnRate * dt)
        const newAngle = currentAngle + step
        const spd = this.gameObject.body.speed
        this.gameObject.body.setVelocity(Math.cos(newAngle) * spd, Math.sin(newAngle) * spd)
        this.gameObject.setRotation(newAngle)
      }
      this._trackLife -= dt
      if (this._trackLife <= 0) {
        this._destroyed = true
        this.scene.time.delayedCall(0, () => this.removeSelf())
        return
      }
    }
    const b = this._bounds
    if (x < b.left || x > b.right || y < b.top || y > b.bottom) {
      this._destroyed = true
      // Defer removal to avoid modifying children array during iteration
      this.scene.time.delayedCall(0, () => this.removeSelf())
    }
  }

  _spawnTrail() {
    const x = this.gameObject.x
    const y = this.gameObject.y
    const t = this.scene.add.circle(x, y, this._trailRadius, this._trailColor, this._trailAlpha)
      .setBlendMode(Phaser.BlendModes.ADD)
      .setDepth(3)
    this.scene.tweens.add({
      targets: t,
      alpha: 0,
      duration: this._trailDuration,
      ease: 'Quad.easeOut',
      onComplete: () => t.destroy()
    })
  }

  _updateVisualPulse() {
    const pulse = Math.sin(this._visualTime * 18)
    const scale = 1 + pulse * this._animPulseAmount
    this.gameObject.setDisplaySize(this._baseDisplayWidth * scale, this._baseDisplayHeight * scale)

    if (this._glow) {
      this._glow.alpha = Math.max(0, this._baseGlowAlpha * (1 + pulse * this._glowPulseAmount))
      this._glow.scale = 1 + pulse * 0.06
    }

    if (!this._altTexKey) return
    const nextKey = Math.floor(this._visualTime / this._animFrameInterval) % 2 === 0
      ? this._activeTexKey
      : this._altTexKey
    if (this.gameObject.texture?.key !== nextKey) this.gameObject.setTexture(nextKey)
  }

  onBlocked() {
    if (this._destroyed) return false
    if (this.isRocket) this._explode()
    this._destroyed = true
    this.scene.time.delayedCall(0, () => this.removeSelf())
    return false
  }

  // Called on hit. Returns true if the bullet keeps flying (pierce), false if destroyed.
  onHit() {
    if (this._destroyed) return false
    if (this.penetrateCount > 0) {
      this.penetrateCount--
      return true // pierced, keep going
    }
    if (this.isRocket) {
      this._explode()
    }
    this._destroyed = true
    this.scene.time.delayedCall(0, () => this.removeSelf())
    return false
  }

  _explode() {
    const cx = this.gameObject.x
    const cy = this.gameObject.y
    const fx = this._fxConfig || {}
    const flash = this.scene.add.circle(cx, cy, this.splashRadius, 0xff6600, fx.explosionAlpha).setDepth(4)
    this.scene.tweens.add({
      targets: flash,
      alpha: 0,
      scaleX: fx.explosionScale,
      scaleY: fx.explosionScale,
      duration: fx.explosionDurationMs,
      onComplete: () => flash.destroy()
    })
    const enemies = this.findByTag('enemy')
    for (const en of enemies) {
      if (!en.gameObject) continue
      const dx = en.gameObject.x - cx
      const dy = en.gameObject.y - cy
      if (Math.sqrt(dx * dx + dy * dy) <= this.splashRadius) {
        const splashDmg = this.isCrit ? this.splashDamage * 2 : this.splashDamage
        en.takeDamage(splashDmg, this.isCrit)
      }
    }
  }

  destroy() {
    if (this._glow) {
      this._glow.destroy()
      this._glow = null
    }
    if (this.gameObject) {
      this.gameObject.destroy()
      this.gameObject = null
    }
  }
}
