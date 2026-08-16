import { Node } from '/engine/Node.js'
import { fetchJson } from '../engine/url.js'

const STATE_START = 'start'
const STATE_PLAYING = 'playing'
const STATE_GAME_OVER = 'gameOver'
const BEST_SCORE_KEY = 'swipe-slice-arcade.bestScore'

function worldGravityY(scene) {
  return Number(scene?.physics?.world?.gravity?.y ?? 300)
}

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value))
}

function round(value) {
  return Math.round(value * 100) / 100
}

function numberOr(value, fallback = 0) {
  const n = Number(value)
  return Number.isFinite(n) ? n : fallback
}

const CONFIG_KEYS = [
  'missLimit', 'missY', 'cleanupMargin',
  'spawnIntervalSlow', 'spawnIntervalMin',
  'spawnRampTau', 'spawnRampFull',
  'targetCountStart', 'targetCountMax', 'waveSizeMax',
  'gameOverOverlayDelayMs',
  'difficultyBucketSeconds', 'initialSpawnCooldown',
  'halfSpawnOffsetFactor', 'comboCalloutDurationMs',
  'halfVelocityCarryX', 'halfVelocityCarryY',
  'apexHeightMinFraction', 'apexHeightMaxFraction',
  'apexHeavyBiasScale', 'apexHeavyBiasMin', 'apexHeavyBiasMax',
  'apexMinFractionClampLow', 'apexMinFractionClampHigh',
  'apexMaxFractionClampLow', 'apexMaxFractionClampHigh',
  'openingFruitTypeWindowSeconds', 'openingFruitTypeSpawnCount',
  'spawnDelayJitterMin', 'spawnDelayJitterMax',
  'halfPopJitterXMin', 'halfPopJitterXMax',
  'halfPopJitterYMin', 'halfPopJitterYMax',
  'halfPopJitterSpinMin', 'halfPopJitterSpinMax',
]

const LAUNCH_GEOMETRY_KEYS = [
  'laneMarginX', 'laneJitterX',
  'edgeYMarginMin', 'edgeYMarginMax',
  'dropInJitterX', 'dropInYMarginMin', 'dropInYMarginMax', 'dropInClampMargin',
  'edgeOvershootX', 'sideRollThreshold1', 'sideRollThreshold2',
  'fallbackClampMargin', 'fallbackXMargin', 'dropInOvershootY',
  'minGravityY', 'minRise',
]

const SPAWN_PRESSURE_KEYS = [
  'fullCooldownFloor', 'emptyCooldownBase', 'emptyCooldownRampFactor',
  'belowCooldownBase', 'belowCooldownRampFactor',
]

export default class GameController extends Node {
  async ready() {
    // Camera bounds are read from the live scene scale (a runtime fact, not a
    // tuning value); 960x540/FIT is fixed by project.json, this is only a
    // bootstrap-order safety net for before scale is attached.
    this.bounds = {
      width: Number(this.scene.scale?.width || this.scene.game?.config?.width || 960),
      height: Number(this.scene.scale?.height || this.scene.game?.config?.height || 540),
    }

    // Every key below is config-owned tuning (Part C1): single declared
    // source is GameRoot.config in main.scene.json, no script default. A
    // missing or non-finite value fails loudly instead of masking a gap.
    for (const key of CONFIG_KEYS) {
      const value = Number(this.config[key])
      if (!Number.isFinite(value)) throw new Error(`GameController: config.${key} missing or non-finite; declare it in GameRoot.config`)
      this[key] = value
    }
    if (!Array.isArray(this.config.openingWaveLaneFractions) || this.config.openingWaveLaneFractions.length !== 2) {
      throw new Error('GameController: config.openingWaveLaneFractions missing; declare it in GameRoot.config')
    }
    this.openingWaveLaneFractions = this.config.openingWaveLaneFractions.map(Number)
    if (this.openingWaveLaneFractions.some(v => !Number.isFinite(v))) {
      throw new Error('GameController: config.openingWaveLaneFractions must be two finite numbers')
    }

    this.launchGeometry = {}
    for (const key of LAUNCH_GEOMETRY_KEYS) {
      const value = Number(this.config.launchGeometry?.[key])
      if (!Number.isFinite(value)) throw new Error(`GameController: config.launchGeometry.${key} missing or non-finite; declare it in GameRoot.config`)
      this.launchGeometry[key] = value
    }

    this.spawnPressureTuning = {}
    for (const key of SPAWN_PRESSURE_KEYS) {
      const value = Number(this.config.spawnPressureTuning?.[key])
      if (!Number.isFinite(value)) throw new Error(`GameController: config.spawnPressureTuning.${key} missing or non-finite; declare it in GameRoot.config`)
      this.spawnPressureTuning[key] = value
    }

    this.spawnInterval = { slow: this.spawnIntervalSlow, min: this.spawnIntervalMin }

    this.rosterData = await fetchJson('config/fruit-roster.json')
    this.fruitTypes = [...(this.rosterData.types || [])]
    this.fruitProfiles = this.rosterData.profiles || {}
    this.comboBonus = this.rosterData.comboBonus || {}
    this.bombProfile = this.rosterData.bomb || {}

    // Shared roster-level tuning (Part C2): single authoritative source is
    // fruit-roster.json, read once here and forwarded per-spawn where a
    // second script (FruitHalf) also needs it.
    this.halfPopGravityBoost = Number(this.rosterData.halfPopGravityBoost)
    if (!Number.isFinite(this.halfPopGravityBoost)) throw new Error('GameController: fruit-roster.json halfPopGravityBoost missing or non-finite')
    if (!Array.isArray(this.rosterData.sliceVfxAngleJitterDeg) || this.rosterData.sliceVfxAngleJitterDeg.length !== 2) {
      throw new Error('GameController: fruit-roster.json sliceVfxAngleJitterDeg missing')
    }
    this.sliceVfxAngleJitterDeg = this.rosterData.sliceVfxAngleJitterDeg.map(Number)
    if (this.sliceVfxAngleJitterDeg.some(v => !Number.isFinite(v))) {
      throw new Error('GameController: fruit-roster.json sliceVfxAngleJitterDeg must be two finite numbers')
    }
    this.bombSpawnChanceElapsedRate = Number(this.bombProfile.spawnChanceElapsedRate)
    this.bombSpawnChanceDifficultyRate = Number(this.bombProfile.spawnChanceDifficultyRate)
    if (!Number.isFinite(this.bombSpawnChanceElapsedRate) || !Number.isFinite(this.bombSpawnChanceDifficultyRate)) {
      throw new Error('GameController: fruit-roster.json bomb.spawnChanceElapsedRate/spawnChanceDifficultyRate missing or non-finite')
    }

    this.profileSummary = this.buildProfileSummary()

    this.bestScore = this.readBestScore()
    this.gameState = STATE_START
    this.resetCounters(false)

    // Pointer slash trail + segment-circle hit detection are owned by the
    // SwipeSlashModule node (config.groups route hits to fruit.slice /
    // bomb.hitBySlash). This controller only supplies the host hooks below.
    this.buildHud()
    this.updateHud()
  }

  destroy() {
    this.unbindHud()
    this.ui?.root?.remove()
    this.ui = null
    if (this.comboTimer) window.clearTimeout(this.comboTimer)
    this.comboTimer = null
    this.clearGameOverOverlayDelay()
  }

  update(dt) {
    this.handleActionShortcuts()
    this.tickGameOverOverlayDelay(dt)

    if (this.gameState !== STATE_PLAYING) return

    this.elapsed += dt
    this.difficultyLevel = Math.floor(this.elapsed / this.difficultyBucketSeconds)
    this.refreshSpawnPressure()
    this.spawnCooldown -= dt
    if (this.spawnCooldown <= 0 && !this.spawnPending) {
      this.spawnCooldown = this.nextSpawnDelay()
      if (this.activeTargetCount() < this.desiredActiveTargetCount()) void this.spawnWave()
    }
  }

  resetCounters(resetBest = false) {
    this.score = 0
    this.misses = 0
    this.combo = 0
    this.maxCombo = 0
    this.lastSlashCount = 0
    this.elapsed = 0
    this.difficultyLevel = 0
    this.spawnCooldown = this.initialSpawnCooldown
    this.spawnPending = false
    this.spawnedCount = 0
    this.slicedCount = 0
    this.missedCount = 0
    this.forgivenMissCount = 0
    this.bombHitCount = 0
    this.bombSpawnedCount = 0
    this.lastSliced = null
    this.lastMissed = null
    this.lastVfx = null
    this.lastBombExplosion = null
    this.lastBombHit = null
    this.spawnEvidenceByType = {}
    this.sliceEvidenceByType = {}
    this.missingTextureKeys = []
    this.gameOverPanelVisible = false
    this.gameOverPanelDelayActive = false
    this.gameOverOverlayDelayRemaining = 0
    this.lastGameOverReason = null
    if (resetBest) this.bestScore = this.readBestScore()
  }

  startRun() {
    this.runEpoch = (this.runEpoch || 0) + 1
    this.clearGameOverOverlayDelay()
    this.removeDynamicNodes()
    this.resetCounters(false)
    this.gameState = STATE_PLAYING
    this.hideComboCallout()
    this.updateHud()
    this.spawnCooldown = this.nextSpawnDelay()
    void this.spawnOpeningWave(this.runEpoch)
  }

  endGame(reason, options = {}) {
    if (this.gameState === STATE_GAME_OVER) return
    this.gameState = STATE_GAME_OVER
    this.lastGameOverReason = reason
    if (this.score > this.bestScore) {
      this.bestScore = this.score
      this.writeBestScore(this.bestScore)
    }
    this.setGameOverPanelDelay(Number(options.overlayDelayMs || 0))
    this.updateHud()
  }

  isPlaying() {
    return this.gameState === STATE_PLAYING
  }

  onFruitSliced(fruit, slashMeta = {}) {
    if (this.gameState !== STATE_PLAYING) return false

    const runEpoch = this.runEpoch
    const profile = this.fruitProfiles[fruit.fruitType] || {}
    const score = Number(fruit.score || profile.score || 0)
    const velocity = this.readVelocity(fruit)
    const halfVelocities = this.planHalfVelocities(fruit, profile, velocity)

    this.score += score
    this.slicedCount += 1

    // Running count of fruits cut by the current swipe, supplied by SwipeSlashModule.
    const comboCount = Number(slashMeta.count || 1)
    const sliceEvidence = {
      fruitType: fruit.fruitType,
      score,
      radius: Number(profile.radius || fruit.radius || 24),
      weight: Number(profile.weight || 1),
      gravity: this.gravitySummary(profile.weight),
      baseVelocity: { vx: round(velocity.vx), vy: round(velocity.vy) },
      halfVelocities: halfVelocities.map(v => ({ ...v })),
      halfPop: this.profileSummary[fruit.fruitType]?.halfPop || null,
      vfxTextures: this.profileSummary[fruit.fruitType]?.sliceVfxTextures || [],
      vfxIntensity: this.profileSummary[fruit.fruitType]?.vfxIntensity || null,
    }

    this.lastSliced = {
      ...sliceEvidence,
      x: round(fruit.x),
      y: round(fruit.y),
      comboCount,
      comboBonus: 0,
    }
    this.sliceEvidenceByType[fruit.fruitType] = { ...sliceEvidence }

    void this.spawnFruitHalves(fruit, profile, halfVelocities, runEpoch)
    void this.spawnSliceVfx(fruit, profile, runEpoch)
    this.updateHud()
    return true
  }

  onFruitMiss(fruit) {
    if (this.gameState !== STATE_PLAYING) return
    // Every missed fruit counts from the opening, including the first ones to
    // fall. Fairness is handled upstream in Fruit (minReadableTimeForMiss): a
    // fruit only reports a miss after it actually entered the readable field.
    this.misses += 1
    this.missedCount += 1
    this.combo = 0
    this.lastMissed = {
      fruitType: fruit.fruitType,
      x: round(fruit.x),
      y: round(fruit.y),
      readableTime: round(fruit.readableTime || 0),
      spawnIndex: Number(fruit.spawnIndex || 0),
      forgiven: false,
    }
    if (this.misses >= this.missLimit) {
      this.endGame('misses')
    } else {
      this.updateHud()
    }
  }

  onBombHit(bomb, slashMeta = {}) {
    if (this.gameState !== STATE_PLAYING) return
    this.bombHitCount += 1
    this.lastSlashCount = Number(slashMeta.counts?.slice ?? this.lastSlashCount)
    this.lastBombHit = {
      x: round(bomb.x),
      y: round(bomb.y),
    }
    void this.spawnBombExplosion({ x: bomb.x, y: bomb.y }, this.runEpoch)
    this.endGame('bomb', { overlayDelayMs: this.gameOverOverlayDelayMs })
  }

  async spawnWave() {
    if (this.gameState !== STATE_PLAYING) return
    const runEpoch = this.runEpoch
    this.spawnPending = true
    try {
      const fruitCount = this.pickWaveSize()
      const includeBomb = this.shouldSpawnBomb()
      const total = fruitCount + (includeBomb ? 1 : 0)
      const lanes = this.pickLaunchLanes(total)

      for (let i = 0; i < fruitCount; i += 1) {
        if (this.gameState !== STATE_PLAYING || runEpoch !== this.runEpoch) return
        await this.spawnFruit(lanes[i], runEpoch)
      }

      if (includeBomb && this.gameState === STATE_PLAYING && runEpoch === this.runEpoch) {
        await this.spawnBomb(lanes[total - 1], runEpoch)
      }
    } finally {
      if (runEpoch === this.runEpoch) this.spawnPending = false
    }
  }

  async spawnOpeningWave(runEpoch = this.runEpoch) {
    if (this.gameState !== STATE_PLAYING || this.spawnPending) return
    this.spawnPending = true
    try {
      const lanes = this.openingWaveLaneFractions.map(fraction => ({
        xHint: this.bounds.width * fraction,
        visibleStart: true,
      }))
      for (const lane of lanes) {
        if (this.gameState !== STATE_PLAYING || runEpoch !== this.runEpoch) return
        await this.spawnFruit(lane, runEpoch)
      }
    } finally {
      if (runEpoch === this.runEpoch) this.spawnPending = false
    }
  }

  async spawnFruit(lane = null, runEpoch = this.runEpoch) {
    const fruitType = this.pickFruitType()
    const profile = this.fruitProfiles[fruitType]
    if (!profile) return null

    const launch = this.computeLaunch(profile.speed || {}, lane, Number(profile.weight || 1))
    // radius is business/report data only (score/gravity summaries); the
    // node's own visual/collider size is declared by its per-type template
    // and is never forwarded here.
    const radius = Number(profile.radius || 24)
    const wholeTexture = profile.wholeTexture || `fruit_${fruitType}_whole`
    const leftTexture = profile.leftTexture || `fruit_${fruitType}_left`
    const rightTexture = profile.rightTexture || `fruit_${fruitType}_right`
    const spawnIndex = this.spawnedCount + 1
    this.noteMissingTextureIfNeeded(wholeTexture)
    this.noteMissingTextureIfNeeded(leftTexture)
    this.noteMissingTextureIfNeeded(rightTexture)
    const node = await this.instantiate(`entities/fruit-${fruitType}.node.json`, {
      x: launch.x,
      y: launch.y,
      fruitType,
      label: profile.label || fruitType,
      score: Number(profile.score || 0),
      spawnIndex,
      weight: Number(profile.weight || 1),
      velocityX: launch.vx,
      velocityY: launch.vy,
      missY: this.missY,
      cleanupMargin: this.cleanupMargin,
      wholeTexture,
      leftTexture,
      rightTexture,
      halfPop: profile.halfPop || {},
    })
    if (runEpoch !== this.runEpoch || this.gameState !== STATE_PLAYING) {
      node?.removeSelf?.()
      return null
    }
    this.spawnEvidenceByType[fruitType] = {
      fruitType,
      spawnIndex,
      radius,
      score: Number(profile.score || 0),
      weight: Number(profile.weight || 1),
      launchVelocity: { vx: launch.vx, vy: launch.vy },
      visibleAtLaunch: Boolean(launch.visibleAtLaunch),
      speedRange: this.profileSummary[fruitType]?.speedRange || null,
      gravity: this.gravitySummary(profile.weight),
    }
    this.spawnedCount += 1
    return node
  }

  async spawnBomb(lane = null, runEpoch = this.runEpoch) {
    const launch = this.computeLaunch(this.bombProfile.speed || {}, lane, Number(this.bombProfile.weight || 1.1))
    const texture = this.bombProfile.texture || 'bomb_idle'
    const warningTexture = this.bombProfile.warningTexture || 'bomb_warning'
    this.noteMissingTextureIfNeeded(texture)
    this.noteMissingTextureIfNeeded(warningTexture)
    const node = await this.instantiate('entities/bomb.node.json', {
      x: launch.x,
      y: launch.y,
      weight: Number(this.bombProfile.weight || 1.1),
      velocityX: launch.vx,
      velocityY: launch.vy,
      missY: this.missY,
      cleanupMargin: this.cleanupMargin,
      texture,
      warningTexture,
    })
    if (runEpoch !== this.runEpoch || this.gameState !== STATE_PLAYING) {
      node?.removeSelf?.()
      return null
    }
    this.bombSpawnedCount += 1
    return node
  }

  async spawnFruitHalves(fruit, profile, halfVelocities, runEpoch = this.runEpoch) {
    const radius = Number(profile.radius || fruit.radius || 24)
    const x = fruit.x
    const y = fruit.y
    for (const planned of halfVelocities) {
      this.noteMissingTextureIfNeeded(planned.texture)
      if (runEpoch !== this.runEpoch || this.gameState !== STATE_PLAYING) return
      const node = await this.instantiate(`entities/fruit-half-${fruit.fruitType}.node.json`, {
        x: x + planned.sign * radius * this.halfSpawnOffsetFactor,
        y,
        fruitType: fruit.fruitType,
        side: planned.side,
        radius,
        velocityX: planned.vx,
        velocityY: planned.vy,
        spin: planned.spin,
        weight: Number(profile.weight || 1),
        cleanupMargin: this.cleanupMargin,
        texture: planned.texture,
        popGravityBoost: this.halfPopGravityBoost,
      })
      if (runEpoch !== this.runEpoch || this.gameState !== STATE_PLAYING) {
        node?.removeSelf?.()
        return
      }
    }
  }

  async spawnSliceVfx(fruit, profile, runEpoch = this.runEpoch) {
    const entries = Array.isArray(profile.sliceVfx) ? profile.sliceVfx : []
    if (!entries.length) return

    const origin = { x: fruit.x, y: fruit.y }
    const planned = []
    for (const entry of entries) {
      const texture = String(entry.texture || '')
      if (!texture || !this.textureExists(texture)) {
        this.noteMissingTextureIfNeeded(texture)
        continue
      }
      planned.push({
        entry,
        texture,
      })
    }

    if (!planned.length) return

    this.lastVfx = {
      kind: 'slice',
      fruitType: fruit.fruitType,
      textures: planned.map(item => item.texture),
      entries: planned.map(item => this.summarizeVfxEntry(item.entry)),
      intensity: this.vfxIntensity(planned.map(item => item.entry)),
      x: round(origin.x),
      y: round(origin.y),
    }

    for (const item of planned) {
      if (runEpoch !== this.runEpoch) return

      const scatter = Number(item.entry.scatter || 0)
      const config = {
        ...item.entry,
        kind: 'slice',
        label: fruit.fruitType,
        texture: item.texture,
        x: origin.x + this.rand(-scatter, scatter),
        y: origin.y + this.rand(-scatter, scatter),
        angle: item.entry.angle !== undefined ? Number(item.entry.angle) : this.rand(this.sliceVfxAngleJitterDeg[0], this.sliceVfxAngleJitterDeg[1]),
      }
      const node = await this.instantiate('entities/slice-vfx.node.json', config)
      if (runEpoch !== this.runEpoch) {
        node?.removeSelf?.()
        return
      }
    }
  }

  async spawnBombExplosion(position, runEpoch = this.runEpoch) {
    const vfx = this.bombProfile.explosionVfx || {}
    const sequence = Array.isArray(vfx.textureSequence)
      ? vfx.textureSequence.filter(item => item?.texture && this.textureExists(item.texture))
      : []
    const texture = sequence[0]?.texture || vfx.texture || 'bomb_explosion_ignition'
    this.noteMissingTextureIfNeeded(texture)
    for (const item of vfx.textureSequence || []) this.noteMissingTextureIfNeeded(item?.texture)
    if (!this.textureExists(texture)) return

    const x = Number(position.x || 0)
    const y = Number(position.y || 0)
    this.lastBombExplosion = {
      kind: 'bombExplosion',
      textures: sequence.length ? sequence.map(item => item.texture) : [texture],
      x: round(x),
      y: round(y),
      ttl: Number(vfx.ttl || 0.72),
    }
    const config = {
      ...vfx,
      kind: 'bombExplosion',
      texture,
      textureSequence: sequence,
      x,
      y,
    }
    const node = await this.instantiate('entities/bomb-explosion.node.json', config)
    if (runEpoch !== this.runEpoch) {
      node?.removeSelf?.()
      return
    }
  }

  planHalfVelocities(fruit, profile, baseVelocity) {
    const pop = profile.halfPop || {}
    const popX = Number(pop.x || 150)
    const popY = Number(pop.y || -85)
    const spin = Number(pop.spin || 4)
    const spread = Number(pop.spread || 1)
    const plans = []
    for (const side of ['left', 'right']) {
      const sign = side === 'left' ? -1 : 1
      const jitter = this.rand(this.halfPopJitterXMin, this.halfPopJitterXMax)
      plans.push({
        side,
        sign,
        vx: round(baseVelocity.vx * this.halfVelocityCarryX + sign * popX * spread * jitter),
        vy: round(baseVelocity.vy * this.halfVelocityCarryY + popY * this.rand(this.halfPopJitterYMin, this.halfPopJitterYMax)),
        spin: round(sign * spin * this.rand(this.halfPopJitterSpinMin, this.halfPopJitterSpinMax)),
        texture: side === 'left'
          ? (profile.leftTexture || `fruit_${fruit.fruitType}_left`)
          : (profile.rightTexture || `fruit_${fruit.fruitType}_right`),
      })
    }
    return plans
  }

  spawnRamp() {
    const tau = this.spawnRampTau
    const full = this.spawnRampFull
    if (tau <= 0 || full <= 0) return 1
    return clamp(Math.log(1 + this.elapsed / tau) / Math.log(1 + full / tau), 0, 1)
  }

  pickWaveSize() {
    const active = this.activeTargetCount()
    const deficit = Math.max(1, this.desiredActiveTargetCount() - active)
    const maxSize = Math.max(1, Math.round(1 + (this.waveSizeMax - 1) * this.spawnRamp()))
    const targetCount = this.randInt(1, maxSize)
    return Math.max(1, Math.min(targetCount, deficit))
  }

  shouldSpawnBomb() {
    const introDelay = Number(this.bombProfile.introDelay || 10)
    const introSpawned = Number(this.bombProfile.introSpawnedCount || 8)
    if (this.elapsed < introDelay || this.spawnedCount < introSpawned) return false
    if (this.activeBombCount() >= 1) return false
    const base = Number(this.bombProfile.spawnChanceBase || 0.08)
    const max = Number(this.bombProfile.spawnChanceMax || 0.22)
    const chance = clamp(base + this.elapsed * this.bombSpawnChanceElapsedRate + this.difficultyLevel * this.bombSpawnChanceDifficultyRate, base, max)
    return Math.random() < chance
  }

  pickFruitType() {
    const opening = this.elapsed < this.openingFruitTypeWindowSeconds || this.spawnedCount < this.openingFruitTypeSpawnCount
    const types = opening
      ? this.fruitTypes.filter(t => ['apple', 'banana', 'orange'].includes(t))
      : this.fruitTypes
    const items = types.map(type => ({
      v: type,
      w: Number(this.fruitProfiles[type]?.spawnWeight || 1),
    }))
    return this.weightedPick(items) || this.fruitTypes[0]
  }

  pickLaunchLanes(total) {
    const lanes = []
    const g = this.launchGeometry
    const minX = g.laneMarginX
    const maxX = this.bounds.width - g.laneMarginX
    for (let i = 0; i < total; i += 1) {
      const t = total === 1 ? 0.5 : i / (total - 1)
      lanes.push({
        xHint: minX + (maxX - minX) * t + this.rand(-g.laneJitterX, g.laneJitterX),
        sideRoll: Math.random(),
      })
    }
    return lanes.sort(() => Math.random() - 0.5)
  }

  apexRangeForWeight(weight = 1) {
    const heavyBias = clamp((Number(weight || 1) - 1) * this.apexHeavyBiasScale, this.apexHeavyBiasMin, this.apexHeavyBiasMax)
    return {
      minY: round(this.bounds.height * clamp(this.apexHeightMinFraction + heavyBias, this.apexMinFractionClampLow, this.apexMinFractionClampHigh)),
      maxY: round(this.bounds.height * clamp(this.apexHeightMaxFraction + heavyBias, this.apexMaxFractionClampLow, this.apexMaxFractionClampHigh)),
    }
  }

  computeLaunch(speed, lane = null, weight = 1) {
    const g = this.launchGeometry
    const vxMin = Number(speed.vxMin || 110)
    const vxMax = Number(speed.vxMax || 240)
    const visibleStart = Boolean(lane?.visibleStart)
    const roll = visibleStart ? 0.5 : (lane?.sideRoll ?? Math.random())
    const edgeY = this.bounds.height - this.rand(g.edgeYMarginMin, g.edgeYMarginMax)
    let x
    let y
    let direction

    if (visibleStart) {
      x = clamp((lane?.xHint ?? this.bounds.width * 0.5) + this.rand(-g.dropInJitterX, g.dropInJitterX), g.dropInClampMargin, this.bounds.width - g.dropInClampMargin)
      y = this.bounds.height - this.rand(g.dropInYMarginMin, g.dropInYMarginMax)
      direction = x < this.bounds.width * 0.5 ? 1 : -1
    } else if (roll < g.sideRollThreshold1) {
      x = -g.edgeOvershootX
      y = edgeY
      direction = 1
    } else if (roll < g.sideRollThreshold2) {
      x = this.bounds.width + g.edgeOvershootX
      y = edgeY
      direction = -1
    } else {
      x = clamp(lane?.xHint ?? this.rand(g.fallbackXMargin, this.bounds.width - g.fallbackXMargin), g.fallbackClampMargin, this.bounds.width - g.fallbackClampMargin)
      y = this.bounds.height + g.dropInOvershootY
      direction = x < this.bounds.width * 0.5 ? 1 : -1
    }

    const vx = this.rand(vxMin, vxMax) * direction
    const apexRange = this.apexRangeForWeight(weight)
    const apexY = this.rand(apexRange.minY, apexRange.maxY)
    const gravityY = Math.max(g.minGravityY, worldGravityY(this.scene) * Number(weight || 1))
    const rise = Math.max(g.minRise, y - apexY)
    const vy = -Math.sqrt(2 * gravityY * rise)
    return { x: round(x), y: round(y), vx: round(vx), vy: round(vy), visibleAtLaunch: visibleStart }
  }

  nextSpawnDelay() {
    const ramp = this.spawnRamp()
    const interval = this.spawnInterval.slow + (this.spawnInterval.min - this.spawnInterval.slow) * ramp
    return interval * this.rand(this.spawnDelayJitterMin, this.spawnDelayJitterMax)
  }

  // --- SwipeSlashModule host hooks --------------------------------------
  // The SwipeSlashModule node owns pointer capture, the glow trail, and
  // segment-circle hit detection; it routes each hit to fruit.slice /
  // bomb.hitBySlash and calls these hooks for game-state decisions.

  canSlash() {
    return this.gameState === STATE_PLAYING
  }

  onSwipePointerDown() {
    if (this.gameState === STATE_START || this.gameState === STATE_GAME_OVER) {
      this.startRun()
    }
  }

  onSwipeEnd(slash = {}) {
    const fruitCount = Number(slash.counts?.slice || 0)
    this.lastSlashCount = fruitCount
    if (fruitCount >= 3) {
      const bonus = this.comboBonusFor(fruitCount)
      this.score += bonus
      this.combo = fruitCount
      this.maxCombo = Math.max(this.maxCombo, fruitCount)
      if (this.lastSliced) {
        this.lastSliced.comboCount = fruitCount
        this.lastSliced.comboBonus = bonus
      }
      this.showComboCallout(`${fruitCount} Fruit Combo +${bonus}`)
    } else {
      this.combo = 0
    }
    this.updateHud()
  }

  comboBonusFor(count) {
    if (count >= 6) return Number(this.comboBonus['6'] || 30)
    return Number(this.comboBonus[String(count)] || 0)
  }

  activeFruitCount() {
    return this.findByTag('fruit').filter(n => n.enabled !== false && !n.sliced && !n.missed).length
  }

  activeBombCount() {
    return this.findByTag('bomb').filter(n => n.enabled !== false && n.armed !== false && !n.hit).length
  }

  activeTargetCount() {
    return this.activeFruitCount() + this.activeBombCount()
  }

  desiredActiveTargetCount() {
    return Math.round(this.targetCountStart + (this.targetCountMax - this.targetCountStart) * this.spawnRamp())
  }

  refreshSpawnPressure() {
    if (this.spawnPending) return
    const p = this.spawnPressureTuning
    const ramp = this.spawnRamp()
    const activeTargets = this.activeTargetCount()
    const desiredTargets = this.desiredActiveTargetCount()
    if (activeTargets >= desiredTargets) {
      this.spawnCooldown = Math.max(this.spawnCooldown, p.fullCooldownFloor)
    } else if (activeTargets <= 0) {
      // Empty arena: refill soon but never instantly; faster as ramp rises.
      this.spawnCooldown = Math.min(this.spawnCooldown, p.emptyCooldownBase - p.emptyCooldownRampFactor * ramp)
    } else {
      // Below target: nudge the next spawn earlier without bursting the field.
      this.spawnCooldown = Math.min(this.spawnCooldown, p.belowCooldownBase - p.belowCooldownRampFactor * ramp)
    }
  }

  activeHalfCount() {
    return this.findByTag('fruitHalf').filter(n => n.enabled !== false).length
  }

  activeVfxCount() {
    return this.findByTag('vfx').filter(n => n.enabled !== false).length
  }

  activeSliceVfxCount() {
    return this.findByTag('sliceVfx').filter(n => n.enabled !== false).length
  }

  activeBombExplosionCount() {
    return this.findByTag('bombExplosion').filter(n => n.enabled !== false).length
  }

  removeDynamicNodes() {
    const nodes = new Set([
      ...this.findByTag('fruit'),
      ...this.findByTag('bomb'),
      ...this.findByTag('fruitHalf'),
      ...this.findByTag('vfx'),
    ])
    for (const node of nodes) {
      if (node.enabled === false) continue
      if (node === this) continue
      node.removeSelf()
    }
  }

  readVelocity(node) {
    const body = node.gameObject?.body
    return {
      vx: body?.velocity?.x ?? Number(node.config?.velocityX || 0),
      vy: body?.velocity?.y ?? Number(node.config?.velocityY || 0),
    }
  }

  textureExists(texture) {
    return Boolean(texture && this.scene?.textures?.exists(texture))
  }

  noteMissingTextureIfNeeded(texture) {
    if (!texture || this.textureExists(texture)) return
    if (!this.missingTextureKeys.includes(texture)) this.missingTextureKeys.push(texture)
  }

  clearGameOverOverlayDelay() {
    this.gameOverPanelDelayActive = false
    this.gameOverOverlayDelayRemaining = 0
    this.gameOverPanelVisible = false
  }

  tickGameOverOverlayDelay(dt) {
    if (this.gameState !== STATE_GAME_OVER || !this.gameOverPanelDelayActive) return
    this.gameOverOverlayDelayRemaining -= Math.max(0, Number(dt || 0)) * 1000
    if (this.gameOverOverlayDelayRemaining > 0) return

    this.gameOverOverlayDelayRemaining = 0
    this.gameOverPanelDelayActive = false
    this.gameOverPanelVisible = true
    this.updateHud()
  }

  setGameOverPanelDelay(delayMs) {
    this.clearGameOverOverlayDelay()
    if (delayMs > 0) {
      this.gameOverPanelVisible = false
      this.gameOverPanelDelayActive = true
      this.gameOverOverlayDelayRemaining = Math.max(0, Number(delayMs || 0))
      return
    }

    this.gameOverPanelDelayActive = false
    this.gameOverOverlayDelayRemaining = 0
    this.gameOverPanelVisible = true
  }

  handleActionShortcuts() {
    const input = this.sceneTree.inputMap
    if (!input) return
    const pressedStart = input.isPressed('start') || input.isPressed('confirm')
    const pressedRestart = input.isPressed('restart')
    if (this.gameState === STATE_START && pressedStart) this.startRun()
    if (this.gameState === STATE_GAME_OVER && (pressedStart || pressedRestart)) this.startRun()
  }

  buildHud() {
    const uiLayer = this.sceneTree.ui
    if (!uiLayer) throw new Error('GameController requires sceneTree.ui')
    let root = document.getElementById('fruit-ui')
    if (!root) {
      root = document.createElement('div')
      root.id = 'fruit-ui'
      root.innerHTML = `
        <div class="vg-hud">
          <div class="vg-score"><span>Score</span><strong id="score-value">0</strong></div>
          <div class="vg-best"><span>Best</span><strong id="best-value">0</strong></div>
          <div class="vg-misses" id="miss-badges"></div>
        </div>
        <div class="vg-combo" id="combo-callout"></div>
        <div class="vg-overlay" id="start-panel">
          <div class="vg-card"><h1>Swipe Slice Arcade</h1><p>Slice fruit. Avoid bombs. Do not miss 3.</p><button id="start-button">Start</button></div>
        </div>
        <div class="vg-overlay" id="game-over-panel" hidden>
          <div class="vg-card"><h1>Game Over</h1><p id="game-over-reason"></p><p>Score <strong id="final-score">0</strong> / Best <strong id="final-best">0</strong></p><p>Max combo <strong id="final-combo">0</strong></p><button id="restart-button">Restart</button></div>
        </div>`
      uiLayer.mount(root)
    }

    this.ui = {
      root,
      score: document.getElementById('score-value'),
      best: document.getElementById('best-value'),
      misses: document.getElementById('miss-badges'),
      combo: document.getElementById('combo-callout'),
      startPanel: document.getElementById('start-panel'),
      gameOverPanel: document.getElementById('game-over-panel'),
      reason: document.getElementById('game-over-reason'),
      finalScore: document.getElementById('final-score'),
      finalBest: document.getElementById('final-best'),
      finalCombo: document.getElementById('final-combo'),
    }
    this.domListeners = []
    this.bindButton('start-button', () => this.startRun())
    this.bindButton('restart-button', () => this.startRun())
  }

  bindButton(id, handler) {
    const el = document.getElementById(id)
    if (!el) return
    el.addEventListener('click', handler)
    this.domListeners.push({ el, handler })
  }

  unbindHud() {
    for (const item of this.domListeners || []) {
      item.el.removeEventListener('click', item.handler)
    }
    this.domListeners = []
  }

  updateHud() {
    if (!this.ui) return
    if (this.ui.score) this.ui.score.textContent = String(this.score)
    if (this.ui.best) this.ui.best.textContent = String(this.bestScore)
    if (this.ui.misses) {
      this.ui.misses.innerHTML = ''
      // Pure CSS badge (see .vg-miss / .vg-miss.is-used in index.html): no
      // <img>, so there is no broken-image or 404 risk.
      for (let i = 0; i < this.missLimit; i += 1) {
        const badge = document.createElement('span')
        const used = i < this.misses
        badge.className = used ? 'vg-miss is-used' : 'vg-miss'
        badge.dataset.state = used ? 'active' : 'dim'
        badge.setAttribute('aria-label', used ? 'Miss used' : 'Miss available')
        this.ui.misses.appendChild(badge)
      }
    }

    if (this.ui.startPanel) this.ui.startPanel.hidden = this.gameState !== STATE_START
    if (this.ui.gameOverPanel) {
      this.ui.gameOverPanel.hidden = !(this.gameState === STATE_GAME_OVER && this.gameOverPanelVisible)
    }
    if (this.ui.reason) this.ui.reason.textContent = this.lastGameOverReason === 'bomb' ? 'Bomb hit.' : 'Too many misses.'
    if (this.ui.finalScore) this.ui.finalScore.textContent = String(this.score)
    if (this.ui.finalBest) this.ui.finalBest.textContent = String(this.bestScore)
    if (this.ui.finalCombo) this.ui.finalCombo.textContent = String(this.maxCombo)
  }

  showComboCallout(text) {
    if (!this.ui?.combo) return
    if (this.comboTimer) window.clearTimeout(this.comboTimer)
    this.ui.combo.textContent = text
    this.ui.combo.classList.add('is-visible')
    this.comboTimer = window.setTimeout(() => this.hideComboCallout(), this.comboCalloutDurationMs)
  }

  hideComboCallout() {
    if (this.comboTimer) window.clearTimeout(this.comboTimer)
    this.comboTimer = null
    if (this.ui?.combo) {
      this.ui.combo.classList.remove('is-visible')
      this.ui.combo.textContent = ''
    }
  }

  buildProfileSummary() {
    const summary = {}
    for (const type of this.fruitTypes) {
      const p = this.fruitProfiles[type] || {}
      const speed = p.speed || {}
      const halfPop = p.halfPop || {}
      const sliceVfx = Array.isArray(p.sliceVfx) ? p.sliceVfx : []
      summary[type] = {
        score: Number(p.score || 0),
        radius: Number(p.radius || 0),
        spawnWeight: Number(p.spawnWeight || 1),
        weight: Number(p.weight || 1),
        speedRange: {
          vx: [Number(speed.vxMin || 0), Number(speed.vxMax || 0)],
          vy: [Number(speed.vyMin || 0), Number(speed.vyMax || 0)],
        },
        verticalLaunch: {
          mode: 'apex-targeted',
          apexYRange: this.apexRangeForWeight(Number(p.weight || 1)),
        },
        gravity: this.gravitySummary(p.weight),
        halfPop: {
          x: Number(halfPop.x || 0),
          y: Number(halfPop.y || 0),
          spin: Number(halfPop.spin || 0),
          spread: Number(halfPop.spread || 1),
        },
        sliceVfxTextures: sliceVfx.map(item => item.texture).filter(Boolean),
        sliceVfx: this.summarizeVfxEntries(sliceVfx),
        vfxIntensity: this.vfxIntensity(sliceVfx),
      }
    }
    return summary
  }

  gravitySummary(weight) {
    const safeWeight = numberOr(weight, 1)
    const worldY = worldGravityY(this.scene)
    const fruitBodyY = (safeWeight - 1) * worldY
    const halfBodyY = fruitBodyY + this.halfPopGravityBoost
    return {
      worldY: round(worldY),
      fruitBodyY: round(fruitBodyY),
      fruitTotalY: round(worldY + fruitBodyY),
      halfBodyY: round(halfBodyY),
      halfTotalY: round(worldY + halfBodyY),
    }
  }

  summarizeVfxEntry(entry = {}) {
    const width = numberOr(entry.width, 0)
    const height = numberOr(entry.height, 0)
    return {
      texture: String(entry.texture || ''),
      width,
      height,
      area: round(width * height),
      ttl: numberOr(entry.ttl, 0),
      depth: numberOr(entry.depth, 0),
      scatter: numberOr(entry.scatter, 0),
      velocityX: numberOr(entry.velocityX, 0),
      velocityY: numberOr(entry.velocityY, 0),
      scaleStart: numberOr(entry.scaleStart, 1),
      scaleEnd: numberOr(entry.scaleEnd, 1),
    }
  }

  summarizeVfxEntries(entries = []) {
    return Array.isArray(entries) ? entries.map(entry => this.summarizeVfxEntry(entry)) : []
  }

  vfxIntensity(entries = []) {
    const summarized = this.summarizeVfxEntries(entries)
    const count = summarized.length
    if (!count) {
      return {
        count: 0,
        totalArea: 0,
        avgArea: 0,
        maxArea: 0,
        avgTtl: 0,
        maxTtl: 0,
        maxScatter: 0,
        maxScaleEnd: 0,
        textures: [],
      }
    }

    const totalArea = summarized.reduce((sum, entry) => sum + entry.area, 0)
    const totalTtl = summarized.reduce((sum, entry) => sum + entry.ttl, 0)
    return {
      count,
      totalArea: round(totalArea),
      avgArea: round(totalArea / count),
      maxArea: round(Math.max(...summarized.map(entry => entry.area))),
      avgTtl: round(totalTtl / count),
      maxTtl: round(Math.max(...summarized.map(entry => entry.ttl))),
      maxScatter: round(Math.max(...summarized.map(entry => entry.scatter))),
      maxScaleEnd: round(Math.max(...summarized.map(entry => entry.scaleEnd))),
      textures: summarized.map(entry => entry.texture).filter(Boolean),
    }
  }

  readUiState() {
    return {
      scoreRoute: 'dom-css',
      bestRoute: 'dom-css',
      missRoute: 'css',
      comboVisible: Boolean(this.ui?.combo?.classList?.contains('is-visible')),
      startPanelVisible: Boolean(this.ui?.startPanel && !this.ui.startPanel.hidden),
      gameOverPanelVisible: Boolean(this.ui?.gameOverPanel && !this.ui.gameOverPanel.hidden),
      overlayDelayActive: Boolean(this.gameOverPanelDelayActive),
      overlayDelayRemaining: Math.max(0, Math.round(this.gameOverOverlayDelayRemaining || 0)),
    }
  }

  readBestScore() {
    try {
      const value = Number(window.sessionStorage.getItem(BEST_SCORE_KEY) || 0)
      this.bestScoreStorageAvailable = true
      return value
    } catch {
      // Storage unavailable: expose the gap via runtimeState() rather than
      // silently faking a cross-session best score.
      this.bestScoreStorageAvailable = false
      return 0
    }
  }

  writeBestScore(value) {
    try {
      window.sessionStorage.setItem(BEST_SCORE_KEY, String(value))
      this.bestScoreStorageAvailable = true
    } catch {
      this.bestScoreStorageAvailable = false
    }
  }

  weightedPick(items) {
    const total = items.reduce((sum, item) => sum + Math.max(0, item.w), 0)
    if (total <= 0) return items[0]?.v
    let roll = Math.random() * total
    for (const item of items) {
      roll -= Math.max(0, item.w)
      if (roll <= 0) return item.v
    }
    return items[items.length - 1]?.v
  }

  rand(min, max) {
    return min + Math.random() * (max - min)
  }

  randInt(min, max) {
    return Math.floor(this.rand(min, max + 1))
  }

  runtimeState() {
    return {
      gameState: this.gameState,
      score: this.score,
      bestScore: this.bestScore,
      bestScoreStorageAvailable: Boolean(this.bestScoreStorageAvailable),
      misses: this.misses,
      missLimit: this.missLimit,
      combo: this.combo,
      maxCombo: this.maxCombo,
      lastSlashCount: this.lastSlashCount,
      activeFruitCount: this.activeFruitCount(),
      activeBombCount: this.activeBombCount(),
      activeTargetCount: this.activeTargetCount(),
      desiredActiveTargetCount: this.desiredActiveTargetCount(),
      activeHalfCount: this.activeHalfCount(),
      activeVfxCount: this.activeVfxCount(),
      activeSliceVfxCount: this.activeSliceVfxCount(),
      activeBombExplosionCount: this.activeBombExplosionCount(),
      spawnedCount: this.spawnedCount,
      slicedCount: this.slicedCount,
      missedCount: this.missedCount,
      forgivenMissCount: this.forgivenMissCount,
      bombHitCount: this.bombHitCount,
      bombSpawnedCount: this.bombSpawnedCount,
      elapsed: round(this.elapsed),
      difficultyLevel: this.difficultyLevel,
      spawnCooldown: round(this.spawnCooldown),
      spawnPending: Boolean(this.spawnPending),
      lastSliced: this.lastSliced,
      lastMissed: this.lastMissed,
      lastVfx: this.lastVfx,
      lastBombExplosion: this.lastBombExplosion,
      lastGameOverReason: this.lastGameOverReason,
      spawnEvidenceByType: this.spawnEvidenceByType,
      sliceEvidenceByType: this.sliceEvidenceByType,
      uiState: this.readUiState(),
      missingTextureKeys: [...this.missingTextureKeys],
      activeSlash: (() => {
        const s = this.swipe?.activeSlashSummary?.()
        return s ? { pointCount: s.pointCount, fruitCount: Number(s.counts?.slice || 0) } : null
      })(),
      fruitTypes: [...this.fruitTypes],
      fruitProfiles: this.profileSummary,
      physicsGravityY: worldGravityY(this.scene),
    }
  }
}
