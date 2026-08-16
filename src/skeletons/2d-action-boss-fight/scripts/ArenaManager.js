import { Node } from '/engine/Node.js'

export default class ArenaManager extends Node {
  ready() {
    this.arenaWidth = this._num('arenaWidth')
    this.arenaHeight = this._num('arenaHeight')
    this.cameraWidth = this._num('cameraWidth')
    this.cameraHeight = this._num('cameraHeight')
    this.placeholderVisuals = this.config.placeholderVisuals === true

    this.scene.physics.world.setBounds(0, 0, this.arenaWidth, this.arenaHeight)
    this.scene.cameras.main.setBounds(0, 0, this.arenaWidth, this.arenaHeight)
    this.scene.cameras.main.setRoundPixels(true)

    this.player = this.findByTag('player')[0] || null
    this.boss = this.findByTag('boss')[0] || null
    this.playerHpHud = this.findByTag('playerHpHud')[0] || null
    this.bossHpBar = this.findByTag('bossHpBar')[0] || null
    this.overlay = this.findByTag('overlay')[0] || null

    this.encounterState = 'intro'
    this.fightOver = false
    this.outcome = null
    this.runtimeTestResetCount = 0
    this.lastRuntimeTestReset = null

    if (this.player?.gameObject) {
      this._startCameraFollow()
    }

    this.playerHpHud?.setValue?.(this.player?.hp ?? this.player?.maxHp)
    this.bossHpBar?.setLeftRate?.(1)

    if (this.boss) {
      this.boss.aiEnabled = false
      const introDelay = this._num('introDelay')
      this._introTimer = this.scene.time.delayedCall(introDelay * this._num('timeMsPerSecond'), () => {
        if (this.fightOver || !this.boss) return
        this.encounterState = 'fighting'
        this.boss.aiEnabled = true
      })
    }

    this.on('player_hurt', ({ hp }) => this._onPlayerHurt(hp))
    this.on('boss_hit', ({ hp, maxHp }) => this._onBossHit(hp, maxHp))
    this.on('player_die', () => this._onPlayerDefeated())
    this.on('boss_die', () => this._onBossDefeated())
    this.on('spawn_thorn', (data) => this._spawnThorn(data))
    this.on('spawn_fx', (data) => this._spawnFx(data))
  }

  _num(key) {
    return Number(this.config?.[key]) || 0
  }

  _startCameraFollow() {
    const lerp = this.config.cameraFollowLerp || {}
    this.scene.cameras.main.startFollow(this.player.gameObject, true, Number(lerp.x) || 0, Number(lerp.y) || 0)
  }

  _onPlayerHurt(hp) {
    const nextHp = Number.isFinite(hp) ? hp : this.player?.hp
    this.playerHpHud?.setValue?.(nextHp)
    this.overlay?.flashHurt?.()
  }

  _onBossHit(hp, maxHp) {
    const nextMax = Number(maxHp || this.boss?.maxHp || 1)
    const nextHp = Number.isFinite(hp) ? hp : this.boss?.hp
    this.bossHpBar?.setLeftRate?.(nextMax > 0 ? nextHp / nextMax : 0)
  }

  _outcomeDelayMs(kind) {
    const value = Number(this.config.outcomeOverlayDelayMs?.[kind])
    return Number.isFinite(value) && value >= 0 ? value : 0
  }

  _onPlayerDefeated() {
    if (this.fightOver) return
    this.fightOver = true
    this.encounterState = 'defeat'
    this.outcome = 'boss'
    if (this.boss) this.boss.aiEnabled = false
    const delay = this._outcomeDelayMs('death')
    this._fightOverTimer = this.scene.time.delayedCall(delay, () => this.overlay?.showMenu?.('death'))
  }

  _onBossDefeated() {
    if (this.fightOver) return
    this.fightOver = true
    this.encounterState = 'victory'
    this.outcome = 'player'
    if (this.boss) this.boss.aiEnabled = false
    const delay = this._outcomeDelayMs('victory')
    this._fightOverTimer = this.scene.time.delayedCall(delay, () => this.overlay?.showMenu?.('victory'))
  }

  _spawnThorn(data = {}) {
    const config = {}
    for (const key of ['x', 'y', 'vx', 'vy', 'damage', 'lifetime', 'attack']) {
      if (data[key] !== undefined) config[key] = data[key]
    }
    void this.instantiate('entities/thorn-bolt.node.json', config)
  }

  _spawnFx(data = {}) {
    const template = data.template ?? 'entities/one-shot-fx.node.json'
    const config = {}
    for (const key of [
      'x', 'y', 'kind', 'lifetime', 'maxLifetime', 'alpha',
      'facing', 'attackKind', 'sourceX', 'sourceY'
    ]) {
      if (data[key] !== undefined) config[key] = data[key]
    }
    void this.instantiate(template, config)
  }

  resetCombatTestState(options = {}) {
    this.sceneTree.inputMap?.clearAllInjections?.()
    this._introTimer?.remove?.(false)
    this._fightOverTimer?.remove?.(false)
    this._introTimer = null
    this._fightOverTimer = null

    const removed = this._removeRuntimeSpawnedNodes()
    this.overlay?.hideMenu?.()
    this.overlay?.resetTransientState?.()
    const inputCleared = this._isInputResidueClear()

    const playerResult = this.player?.resetForRuntimeEvidence?.(options.player || {}) || null
    const bossOptions = {
      aiEnabled: false,
      ...(options.boss || {})
    }
    const bossResult = this.boss?.resetForRuntimeEvidence?.(bossOptions) || null

    this.fightOver = false
    this.outcome = null
    this.encounterState = options.encounterState || 'runtime_test'
    this.runtimeTestResetCount += 1
    this.lastRuntimeTestReset = {
      count: this.runtimeTestResetCount,
      removed,
      inputCleared,
      player: playerResult?.runtime || null,
      boss: bossResult?.runtime || null,
      cleanBaseline: false
    }
    this.lastRuntimeTestReset.cleanBaseline = this._isRuntimeTestBaselineClean()

    this.playerHpHud?.setValue?.(this.player?.hp ?? this.player?.maxHp)
    this.bossHpBar?.setLeftRate?.(this.boss?.maxHp ? this.boss.hp / this.boss.maxHp : 1)

    const camera = this.scene.cameras.main
    camera?.setScroll?.(0, 0)
    if (this.player?.gameObject) this._startCameraFollow()

    return {
      cleanBaseline: this._isRuntimeTestBaselineClean(),
      inputCleared,
      removed,
      player: playerResult,
      boss: bossResult,
      runtime: this.runtimeState()
    }
  }

  forceBossRuntimeAttackActive(attack = 'ANTLER_SLAM') {
    return this.boss?.forceRuntimeAttackActive?.(attack) || { error: 'Boss not available' }
  }

  _removeRuntimeSpawnedNodes() {
    let projectiles = 0
    let fx = 0
    const nodes = [...this.sceneTree.nodes.values()]
    for (const node of nodes) {
      if (!node.enabled || node.name?.startsWith?.('_')) continue
      if (node.tags?.includes?.('projectile')) {
        projectiles += 1
        node.removeSelf()
        continue
      }
      if (node._scriptName === 'OneShotFx' || node.name === 'OneShotFx') {
        fx += 1
        node.removeSelf()
      }
    }
    return { projectiles, fx }
  }

  _isRuntimeTestBaselineClean() {
    const projectiles = this.findByTag('projectile').filter(n => n.enabled && !n.name?.startsWith?.('_')).length
    const inputCleared = this._isInputResidueClear()
    const overlayState = this.overlay?.runtimeState?.() || { visible: {}, hurtFlashVisible: false }
    const overlayHidden = Object.values(overlayState.visible || {}).every(v => v === false)
    return this.fightOver === false &&
      this.outcome === null &&
      inputCleared === true &&
      overlayHidden === true &&
      overlayState.hurtFlashVisible !== true &&
      projectiles === 0 &&
      this.player?.runtimeState?.().runtimeBaselineClean === true &&
      this.boss?.runtimeState?.().runtimeBaselineClean === true
  }

  _isInputResidueClear() {
    const inputMap = this.sceneTree.inputMap
    if (!inputMap) return true
    return Object.keys(inputMap._injected || {}).length === 0 &&
      Object.keys(inputMap._injectedHeldLastFrame || {}).length === 0 &&
      Object.keys(inputMap._injectedAutoRelease || {}).length === 0
  }

  runtimeState() {
    const camera = this.scene.cameras.main
    const bossRate = this.boss?.maxHp ? this.boss.hp / this.boss.maxHp : null
    return {
      arena: {
        width: this.arenaWidth,
        height: this.arenaHeight,
        cameraWidth: this.cameraWidth,
        cameraHeight: this.cameraHeight,
        bounds: { x: 0, y: 0, width: this.arenaWidth, height: this.arenaHeight }
      },
      camera: {
        scrollX: camera?.scrollX ?? 0,
        scrollY: camera?.scrollY ?? 0,
        bounds: { minX: 0, maxX: Math.max(0, this.arenaWidth - this.cameraWidth) }
      },
      encounter: {
        state: this.encounterState,
        fightOver: this.fightOver,
        outcome: this.outcome
      },
      hud: {
        playerHp: this.player?.hp ?? null,
        bossHpRate: bossRate,
        bossNameLabel: this.bossHpBar?.runtimeState?.().label || null
      },
      overlay: this.overlay?.runtimeState?.() || null,
      runtimeTest: {
        resetCount: this.runtimeTestResetCount,
        lastReset: this.lastRuntimeTestReset,
        cleanBaseline: this._isRuntimeTestBaselineClean(),
        inputCleared: this._isInputResidueClear()
      },
      placeholderVisuals: this.placeholderVisuals
    }
  }

}
