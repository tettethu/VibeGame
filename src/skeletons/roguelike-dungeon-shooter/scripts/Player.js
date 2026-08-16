import { Node, generateId } from '/engine/Node.js'
import Bullet from './Bullet.js'

// Player: move/aim/shoot/HP/Shield/Mana/Coins/i-frames
export default class Player extends Node {
  ready() {
    const c = this.config
    this._bodyObject = this.getPhysicsObject()
    this._visual = this.getVisualObject()
    this.maxHP = c.maxHP || 5
    this.hp = this.maxHP
    this.maxShield = c.maxShield || 5
    this.shield = this.maxShield
    this.maxMana = c.maxMana || 200
    this.mana = this.maxMana
    this.coins = 0

    // Shield regen: 3s delay after hit, then 1 per 2s
    this.shieldRegenDelay = c.shieldRegenDelay || 3
    this.shieldRegenInterval = c.shieldRegenInterval || 2
    this._shieldRegenTimer = 0
    this._shieldRegenAccum = 0

    this.speed = c.speed || 180
    this.invincibleDuration = c.invincibleDuration || 1.0
    this.pickupRadius = c.pickupRadius
    this._invincible = false
    this._invincibleTimer = 0
    this._blinkTimer = 0
    this._dead = false

    // Roll state
    this._rolling = false
    this._rollTimer = 0
    this._rollCooldownTimer = 0
    this._rollGraceTimer = 0
    this._rollDirX = 0
    this._rollDirY = 0
    this._lastMoveDirX = 1
    this._lastMoveDirY = 0
    this.rollDuration = c.rollDuration || 0.3
    this.rollCooldown = c.rollCooldown || 1.0
    this.rollSpeedMultiplier = c.rollSpeedMultiplier || 2.0
    if (this._visual) this._visual.setDepth(5)
    this.rollGraceDuration = c.rollGraceDuration || 0.1
    this._afterimageTimer = 0

    // Weapon state: slot1 = active, slot2 = backup
    this.weaponType = null
    this.weaponData = null
    this.weaponType2 = null
    this.weaponData2 = null
    this._fireCooldown = 0
    this._requirePointerRelease = true

    // Buff accumulation
    this.buffFireRateMultiplier = 1.0
    this.buffSpeedMultiplier = 1.0
    this.buffDamageMultiplier = 1.0
    this.buffPenetrate = 0
    this.buffDoubleShot = false
    this.critChance = c.critChance || 0.15

    // Animation state
    this._isMoving = false
    this.tags = ['player']

    // Demo control overlay (inactive by default)
    this._demoMode = false
    this._demoMoveX = 0
    this._demoMoveY = 0
    this._demoAimX = 0
    this._demoAimY = 0
    this._demoFire = false

    // Get weapon visual child node
    this.weaponNode = this.getChild('Weapon')
    this.weaponNode?.setWeaponType?.(this.weaponType)
  }

  update(dt) {
    if (this._dead) return

    this._updateRollCooldown(dt)
    this._handleRollInput()
    if (this._rolling) {
      this._updateRoll(dt)
    } else {
      this._handleMovement(dt)
      this._handleShooting(dt)
      this._handleWeaponSwitch()
    }
    this._updateInvincible(dt)
    this._updateFacing()

    this._regenShield(dt)
    this._checkOrbs()
  }

  // Shield regen: wait shieldRegenDelay after last hit, then 1 per shieldRegenInterval
  _regenShield(dt) {
    if (this.shield >= this.maxShield) {
      this._shieldRegenTimer = 0
      this._shieldRegenAccum = 0
      return
    }
    this._shieldRegenTimer += dt
    if (this._shieldRegenTimer < this.shieldRegenDelay) return
    this._shieldRegenAccum += dt
    if (this._shieldRegenAccum >= this.shieldRegenInterval) {
      this._shieldRegenAccum -= this.shieldRegenInterval
      this.shield = Math.min(this.maxShield, this.shield + 1)
      const hud = this.findByTag('hud')[0]
      if (hud) hud.updateShield(this.shield, this.maxShield)
    }
  }

  _handleMovement(dt) {
    let vx, vy
    if (this._demoMode) {
      vx = this._demoMoveX
      vy = this._demoMoveY
    } else {
      const im = this.sceneTree.inputMap
      vx = 0; vy = 0
      if (im.isHeld('move_left'))  vx -= 1
      if (im.isHeld('move_right')) vx += 1
      if (im.isHeld('move_up'))    vy -= 1
      if (im.isHeld('move_down'))  vy += 1
    }

    if (vx !== 0 && vy !== 0) {
      const inv = 1 / Math.SQRT2
      vx *= inv
      vy *= inv
    }

    // Track last move direction for roll fallback
    if (vx !== 0 || vy !== 0) {
      this._lastMoveDirX = vx
      this._lastMoveDirY = vy
    }

    const spd = this.speed * this.buffSpeedMultiplier
    this._bodyObject.body.setVelocity(vx * spd, vy * spd)

    // Update animation based on movement
    const moving = vx !== 0 || vy !== 0
    if (moving !== this._isMoving) {
      this._isMoving = moving
      this._applyMoveAnimState(moving)
    }
  }

  _handleShooting(dt) {
    this._fireCooldown = Math.max(0, this._fireCooldown - dt)
    if (!this.weaponData) return

    let shooting
    if (this._demoMode) {
      shooting = this._demoFire
    } else {
      const pointer = this.scene.input.activePointer
      if (this._requirePointerRelease) {
        if (!pointer.isDown) this._requirePointerRelease = false
        return
      }
      shooting = pointer.isDown
    }

    if (shooting && this._fireCooldown <= 0) {
      // Mana gate
      const manaCost = this.weaponData.manaCost || 0
      if (this.mana < manaCost) {
        const hud = this.findByTag('hud')[0]
        if (hud) hud.flashMana()
        return
      }

      const fireRate = this.weaponData.fireRate * this.buffFireRateMultiplier
      this._fireCooldown = 1 / fireRate
      this.mana -= manaCost
      this._fire()

      const hud = this.findByTag('hud')[0]
      if (hud) hud.updateMana(Math.floor(this.mana), this.maxMana)
    }
  }

  // Get weapon world position for bullet spawn
  getWeaponPosition() {
    if (this.weaponNode && this.weaponNode.getWorldPosition) {
      return this.weaponNode.getWorldPosition()
    }
    return { x: this._bodyObject.x, y: this._bodyObject.y }
  }

  _fire() {
    const wd = this.weaponData
    if (!wd) return
    let targetX, targetY
    if (this._demoMode) {
      targetX = this._demoAimX
      targetY = this._demoAimY
    } else {
      const pointer = this.scene.input.activePointer
      targetX = pointer.worldX
      targetY = pointer.worldY
    }
    const weaponPos = this.getWeaponPosition()

    const baseAngle = Phaser.Math.Angle.Between(
      weaponPos.x, weaponPos.y,
      targetX, targetY
    )

    // Face towards target
    if (targetX < this._bodyObject.x) this._visual?.setFlipX(true)
    else this._visual?.setFlipX(false)

    const pellets = wd.pellets || 1
    const spreadDeg = wd.spread || 0
    const spreadRad = Phaser.Math.DegToRad(spreadDeg)

    for (let i = 0; i < pellets; i++) {
      let angle = baseAngle
      if (pellets > 1) {
        const step = spreadRad * 2 / (pellets - 1)
        angle = baseAngle - spreadRad + step * i
      }
      this._spawnBullet(angle, wd, weaponPos)
    }

    if (this.buffDoubleShot) {
      const extraAngle = baseAngle + Phaser.Math.DegToRad(15)
      this._spawnBullet(extraAngle, wd, weaponPos)
    }
  }

  _spawnBullet(angle, wd, weaponPos) {
    const gm = this.findByTag('game_manager')[0]
    if (!gm) return
    const spd = wd.bulletSpeed || 400
    const vx = Math.cos(angle) * spd
    const vy = Math.sin(angle) * spd
    const dmg = (wd.damage || 20) * this.buffDamageMultiplier
    const isCrit = Math.random() < this.critChance

    const bullet = new Bullet()
    bullet.id = generateId()
    bullet.config = {
      x: weaponPos.x,
      y: weaponPos.y,
      vx, vy,
      damage: dmg,
      isCrit,
      isEnemy: false,
      isRocket: wd.isRocket || false,
      splashDamage: (wd.splashDamage || 0) * this.buffDamageMultiplier,
      splashRadius: wd.splashRadius || 0,
      penetrateCount: this.buffPenetrate,
      w: wd.bulletW || 8,
      h: wd.bulletH || 4
    }
    gm.addChild(bullet)
  }

  takeDamage(dmg) {
    if (this._dead || this._invincible || this._rolling || this._rollGraceTimer > 0) return

    // Always 1 damage, shield-first
    if (this.shield > 0) {
      this.shield = Math.max(0, this.shield - 1)
    } else {
      this.hp = Math.max(0, this.hp - 1)
    }

    // Reset shield regen timer on hit
    this._shieldRegenTimer = 0
    this._shieldRegenAccum = 0

    const hud = this.findByTag('hud')[0]
    if (hud) {
      hud.updateHP(this.hp, this.maxHP)
      hud.updateShield(this.shield, this.maxShield)
    }

    if (this.hp <= 0) {
      this._die()
      return
    }

    this._invincible = true
    this._invincibleTimer = this.invincibleDuration
    this._spawnHitParticles()
    this._visual?.setTint(0xffffff)
    this.scene.time.delayedCall(60, () => {
      if (this._visual && this._visual.active) this._visual.clearTint()
    })
  }

  _spawnHitParticles() {
    const px = this._bodyObject.x
    const py = this._bodyObject.y
    for (let i = 0; i < 8; i++) {
      const angle = (Math.PI * 2 / 8) * i + (Math.random() - 0.5) * 0.4
      const dist = 30 + Math.random() * 25
      const size = 2.5 + Math.random() * 1.5
      const p = this.scene.add.circle(px, py, size, 0xff4444, 0.9)
        .setBlendMode(Phaser.BlendModes.ADD)
        .setDepth(10)
      this.scene.tweens.add({
        targets: p,
        x: px + Math.cos(angle) * dist,
        y: py + Math.sin(angle) * dist,
        alpha: 0,
        duration: 350,
        ease: 'Quad.easeOut',
        onComplete: () => p.destroy()
      })
    }
  }

  _die() {
    if (this._dead) return
    this._dead = true
    this._bodyObject.body.setVelocity(0, 0)

    const gm = this.findByTag('game_manager')[0]
    if (gm) gm.onPlayerDied()
  }

  _updateFacing() {
    if (this._rolling) return
    if (this._demoMode) {
      if (typeof this._visual?.setFlipX === 'function') {
        if (this._demoAimX < this._bodyObject.x) this._visual.setFlipX(true)
        else this._visual.setFlipX(false)
      }
    } else {
      const pointer = this.scene.input.activePointer
      if (typeof this._visual?.setFlipX === 'function') {
        if (pointer.worldX < this._bodyObject.x) this._visual.setFlipX(true)
        else this._visual.setFlipX(false)
      }
    }
  }

  _updateInvincible(dt) {
    if (!this._invincible) return
    this._invincibleTimer -= dt
    this._blinkTimer += dt
    // Skip blink alpha during roll - roll visual takes priority
    if (!this._rolling) {
      const vis = Math.floor(this._blinkTimer / 0.08) % 2 === 0
      this._visual?.setAlpha(vis ? 1 : 0.2)
    }

    if (this._invincibleTimer <= 0) {
      this._invincible = false
      this._blinkTimer = 0
      if (!this._rolling) this._visual?.setAlpha(1)
    }
  }

  // Pickup coin and mana orbs
  _checkOrbs() {
    const hud = this.findByTag('hud')[0]

    const manaOrbs = this.findByTag('mana_orb')
    const manaToRemove = []
    for (const orb of manaOrbs) {
      if (!orb.gameObject) continue
      const dx = this._bodyObject.x - orb.gameObject.x
      const dy = this._bodyObject.y - orb.gameObject.y
      if (Math.sqrt(dx * dx + dy * dy) < this.pickupRadius) {
        this.mana = Math.min(this.maxMana, this.mana + (orb.manaValue || 10))
        manaToRemove.push(orb)
      }
    }
    if (manaToRemove.length > 0) {
      for (const orb of manaToRemove) {
        this.scene.time.delayedCall(0, () => orb.removeSelf())
      }
      if (hud) {
        hud.updateMana(Math.floor(this.mana), this.maxMana)
        hud.flashMana()
      }
    }

    // Coin orbs
    const coinOrbs = this.findByTag('coin_orb')
    const coinToRemove = []
    for (const orb of coinOrbs) {
      if (!orb.gameObject) continue
      const dx = this._bodyObject.x - orb.gameObject.x
      const dy = this._bodyObject.y - orb.gameObject.y
      if (Math.sqrt(dx * dx + dy * dy) < this.pickupRadius) {
        this.coins += orb.coinValue || 1
        coinToRemove.push(orb)
      }
    }
    if (coinToRemove.length > 0) {
      for (const orb of coinToRemove) {
        this.scene.time.delayedCall(0, () => orb.removeSelf())
      }
      if (hud) hud.updateCoins(this.coins)
    }
  }

  pickupWeapon(type, data) {
    const hud = this.findByTag('hud')[0]
    if (!this.weaponData) {
      this.weaponType = type
      this.weaponData = data
      if (this.weaponNode?.setWeaponType) this.weaponNode.setWeaponType(type)
      if (hud) hud.updateWeapon(type, data)
    } else if (!this.weaponData2) {
      this.weaponType2 = type
      this.weaponData2 = data
      if (hud) hud.updateWeapon2(type, data)
    } else {
      const oldType = this.weaponType
      const oldData = this.weaponData
      this.weaponType = type
      this.weaponData = data
      if (this.weaponNode?.setWeaponType) this.weaponNode.setWeaponType(type)
      if (hud) hud.updateWeapon(type, data)
      this._dropWeapon(oldType, oldData)
    }
  }

  _dropWeapon(type, data) {
    const gm = this.findByTag('game_manager')[0]
    if (!gm || !this._bodyObject) return
    const dropX = this._bodyObject.x + (Math.random() - 0.5) * 32
    const dropY = this._bodyObject.y + 24
    gm.spawnWeaponDrop(type, data, dropX, dropY)
  }

  _handleWeaponSwitch() {
    if (!this.weaponData2) return
    const im = this.sceneTree.inputMap
    if (!im?.isPressed('weapon_switch')) return
    const t1 = this.weaponType, d1 = this.weaponData
    this.weaponType = this.weaponType2
    this.weaponData = this.weaponData2
    this.weaponType2 = t1
    this.weaponData2 = d1
    const hud = this.findByTag('hud')[0]
    if (this.weaponNode?.setWeaponType) this.weaponNode.setWeaponType(this.weaponType)
    if (hud) {
      hud.updateWeapon(this.weaponType, this.weaponData)
      hud.updateWeapon2(this.weaponType2, this.weaponData2)
    }
    this._fireCooldown = 0
  }

  applyBuff(buffId) {
    const hud = this.findByTag('hud')[0]
    switch (buffId) {
      case 'fire_rate':    this.buffFireRateMultiplier *= 1.2; break
      case 'speed':        this.buffSpeedMultiplier *= 1.15; break
      case 'max_hp':
        this.maxHP += 1
        this.hp = Math.min(this.hp + 1, this.maxHP)
        if (hud) hud.updateHP(this.hp, this.maxHP)
        break
      case 'max_shield':
        this.maxShield += 1
        this.shield = Math.min(this.shield + 1, this.maxShield)
        if (hud) hud.updateShield(this.shield, this.maxShield)
        break
      case 'max_mana':
        this.maxMana += 20
        this.mana = Math.min(this.maxMana, this.mana + 20)
        if (hud) hud.updateMana(Math.floor(this.mana), this.maxMana)
        break
      case 'damage':       this.buffDamageMultiplier *= 1.25; break
      case 'penetrate':    this.buffPenetrate += 1; break
      case 'double_shot':  this.buffDoubleShot = true; break
    }
  }

  suspendFireUntilPointerUp() {
    this._requirePointerRelease = true
  }

  // -- Roll mechanics --

  _updateRollCooldown(dt) {
    if (this._rollCooldownTimer > 0) {
      this._rollCooldownTimer = Math.max(0, this._rollCooldownTimer - dt)
    }
    if (this._rollGraceTimer > 0) {
      this._rollGraceTimer = Math.max(0, this._rollGraceTimer - dt)
    }
  }

  _handleRollInput() {
    if (this._rolling || this._rollCooldownTimer > 0 || this._dead) return
    if (this.scene.physics.world.isPaused) return
    const im = this.sceneTree.inputMap
    if (!im || !im.isPressed('roll')) return

    let dx = 0, dy = 0
    if (im.isHeld('move_left'))  dx -= 1
    if (im.isHeld('move_right')) dx += 1
    if (im.isHeld('move_up'))    dy -= 1
    if (im.isHeld('move_down'))  dy += 1
    if (dx === 0 && dy === 0) {
      dx = this._lastMoveDirX
      dy = this._lastMoveDirY
    }
    if (dx === 0 && dy === 0) {
      dx = this._visual?.flipX ? -1 : 1
      dy = 0
    }

    const len = Math.sqrt(dx * dx + dy * dy)
    if (len > 0) { dx /= len; dy /= len }

    this._rolling = true
    this._rollTimer = this.rollDuration
    this._rollDirX = dx
    this._rollDirY = dy
    this._afterimageTimer = 0

    this._visual?.setFlipX(dx < 0)
    this._setRollVisualState(true)
    this._spawnRollAfterimage()
  }

  _updateRoll(dt) {
    this._rollTimer -= dt
    const spd = this.speed * this.buffSpeedMultiplier * this.rollSpeedMultiplier
    const b = this._bodyObject.body
    b.setVelocity(this._rollDirX * spd, this._rollDirY * spd)
    this._visual?.setAlpha(0.5)

    this._afterimageTimer += dt
    if (this._afterimageTimer >= 0.06) {
      this._afterimageTimer = 0
      this._spawnRollAfterimage()
    }

    if (this._rollTimer <= 0) {
      this._endRoll()
    }
  }

  _endRoll() {
    this._rolling = false
    this._rollTimer = 0
    this._rollCooldownTimer = this.rollCooldown
    this._rollGraceTimer = this.rollGraceDuration
    this._rollDirX = 0
    this._rollDirY = 0
    this._afterimageTimer = 0
    this._setRollVisualState(false)
    if (this._invincible) {
      this._visual?.setAlpha(0.2)
    } else {
      this._visual?.setAlpha(1)
    }
  }

  _spawnRollAfterimage() {
    const go = this._visual
    if (!go || !go.texture || !go.frame) return
    const img = this.scene.add.image(go.x, go.y, go.texture.key, go.frame.name)
      .setDisplaySize(go.displayWidth, go.displayHeight)
      .setFlipX(go.flipX)
      .setAlpha(0.3)
      .setDepth(go.depth - 1)
    this.scene.tweens.add({
      targets: img,
      alpha: 0,
      duration: 180,
      ease: 'Quad.easeOut',
      onComplete: () => img.destroy()
    })
  }

  isRollInvincible() {
    return this._rolling || this._rollGraceTimer > 0
  }

  _applyMoveAnimState(moving) {
    if (this.animator) {
      this.animator.setBool('isMoving', moving)
      return
    }
    if (this.playAnim) {
      this.playAnim(moving ? 'walk' : 'idle')
    }
  }

  _setRollVisualState(isRolling) {
    if (this.animator) {
      this.animator.setBool('isRolling', isRolling)
    }
    if (this._visual?.setVisible) this._visual.setVisible(true)
    const weaponGO = this.weaponNode?.gameObject
    if (weaponGO?.setVisible) {
      weaponGO.setVisible(!isRolling)
    }
  }

  // Demo control API
  enableDemoMode() {
    this._demoMode = true
    this._demoFire = false
    this._demoMoveX = 0
    this._demoMoveY = 0
  }

  disableDemoMode() {
    this._demoMode = false
    this._demoFire = false
    this._demoMoveX = 0
    this._demoMoveY = 0
  }

  setDemoControl(opts) {
    if (opts.aimX !== undefined) this._demoAimX = opts.aimX
    if (opts.aimY !== undefined) this._demoAimY = opts.aimY
    if (opts.fire !== undefined) this._demoFire = opts.fire
    if (opts.moveX !== undefined) this._demoMoveX = opts.moveX
    if (opts.moveY !== undefined) this._demoMoveY = opts.moveY
  }


  runtimeState() {
    return {
      hp: this.hp,
      maxHP: this.maxHP,
      shield: this.shield,
      maxShield: this.maxShield,
      mana: Math.floor(this.mana),
      maxMana: this.maxMana,
      coins: this.coins,
      isRolling: this._rolling,
      rollTimerRemaining: Math.max(0, this._rollTimer),
      rollCooldownRemaining: Math.max(0, this._rollCooldownTimer),
      rollDirX: this._rollDirX,
      rollDirY: this._rollDirY,
      invincible: this._invincible,
      rollInvincible: this._rolling
    }
  }

  destroy() {
    // Engine handles gameObject cleanup for declarative visuals
  }
}
