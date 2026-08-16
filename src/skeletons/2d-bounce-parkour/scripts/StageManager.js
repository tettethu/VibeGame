import { Node } from '/engine/Node.js'
import { fetchJson } from '/engine/url.js'

/**
 * Top-level orchestrator for 3-stage flow + tries / best + clear flow + final overlay.
 * Lives as the root script. Listens for bubbled events from the player controller:
 *   'player_died'      → respawn current stage
 *   'reached_goal'     → save best, spawn goal confetti, schedule next or final
 *   'balloon_stomped'  → spawn confetti at balloon location
 *
 * Persists per-stage best in localStorage. Total Best = sum of per-stage best
 * (lifetime aggregate). Total Tries = sum of this-session tries across stages.
 */

const STAGES = [
  { name: 'stage1', path: 'stages/stage1.node.json', next: 'stage2', label: 'Stage 1' },
  { name: 'stage2', path: 'stages/stage2.node.json', next: 'stage3', label: 'Stage 2' },
  { name: 'stage3', path: 'stages/stage3.node.json', next: null,     label: 'Stage 3' },
]
const BEST_KEY = (s) => `bounce-parkour:${s}:best`

export default class StageManager extends Node {
  async ready() {
    this._host = this.getChild('StageHost')
    this.tries = 1
    this.stage = null
    this.cleared = false
    this.centerText = ''
    this.centerHtml = ''
    this.isFinal = false
    this.clearDelayMs = this.config?.clearDelayMs
    this._stompConfettiCount = this.config?.stompConfettiCount
    this._goalConfettiCount = this.config?.goalConfettiCount
    this._worldBoundsUp = this.config?.worldBoundsUp
    this._worldBoundsDown = this.config?.worldBoundsDown
    this._stageNode = null
    this._spawnX = 0
    this._spawnY = 0
    this._levelWidth = this.scene?.scale?.width
    this._triesByStage = {}  // session-only accumulator
    this.totalTries = 0
    this.totalBest = this._computeTotalBest()
    this.best = this._loadBest(STAGES[0].name)

    this.on('player_died', () => this._handleDeath())
    this.on('reached_goal', () => this._handleClear())
    this.on('balloon_stomped', ({ x, y }) => this._spawnConfetti(x, y, this._stompConfettiCount))

    await this._preloadStages(STAGES.map(s => s.path))
    await this._preloadStages(['entities/fx/confetti.node.json'])

    await this._loadStage(this.config.startStage)
  }

  async _preloadStages(paths) {
    const defs = this.sceneTree.nodeDefinitions || (this.sceneTree.nodeDefinitions = {})
    for (const p of paths) {
      if (defs[p]) continue
      try {
        defs[p] = await fetchJson(p)
      } catch (err) {
        console.error(`StageManager: failed to load ${p}`, err)
      }
    }
  }

  _loadBest(stage) {
    try {
      const v = localStorage.getItem(BEST_KEY(stage))
      if (!v) return null
      const n = parseInt(v, 10)
      return Number.isFinite(n) && n > 0 ? n : null
    } catch {
      return null
    }
  }

  _saveBest(stage, n) {
    try { localStorage.setItem(BEST_KEY(stage), String(n)) } catch {}
  }

  _computeTotalBest() {
    const bests = STAGES.map(s => this._loadBest(s.name))
    return bests.every(b => b !== null) ? bests.reduce((a, b) => a + b, 0) : null
  }

  _computeTotalTries() {
    let sum = this.tries  // current stage in-progress
    for (const s of STAGES) {
      if (s.name !== this.stage && this._triesByStage[s.name]) {
        sum += this._triesByStage[s.name]
      }
    }
    return sum
  }

  async _loadStage(name) {
    if (!this._host) return
    for (const child of [...this._host.children]) child.removeSelf()

    const meta = STAGES.find(s => s.name === name)
    if (!meta) {
      console.error(`StageManager: unknown stage "${name}"`)
      return
    }

    this.stage = name
    this.cleared = false
    this.tries = 1
    this.centerText = ''
    this.centerHtml = ''
    this.isFinal = meta.next === null
    this.best = this._loadBest(name)

    this._stageNode = await this._host.instantiate(meta.path)
    const cfg = this._stageNode.config || {}
    this._spawnX = cfg.spawnX
    this._spawnY = cfg.spawnY
    this._levelWidth = cfg.levelWidth
    this._configureCamera(this._levelWidth, true)
    this.totalTries = this._computeTotalTries()
  }

  _findActive(tag) {
    return this.findByTag(tag).find(n => n.enabled && n.gameObject) || null
  }

  _findActiveAll(tag) {
    return this.findByTag(tag).filter(n => n.enabled && n.gameObject)
  }

  _configureCamera(levelWidth, followPlayer) {
    const cam = this.scene?.cameras?.main
    if (!cam) return
    const h = this.scene.scale.height
    cam.setBounds(0, 0, levelWidth, h)
    if (this.scene.physics?.world?.setBounds) {
      this.scene.physics.world.setBounds(0, -this._worldBoundsUp, levelWidth, h + this._worldBoundsDown)
    }
    // Reset zoom in case a previous stomp tween left it mid-flight.
    cam.setZoom(1)
    if (followPlayer) {
      const hero = this._findActive('player')
      if (hero?.gameObject) {
        cam.startFollow(hero.gameObject, true, 0.15, 0)
        cam.setFollowOffset(0, 0)
      }
    } else {
      cam.stopFollow()
      cam.setScroll(0, 0)
    }
  }

  _handleDeath() {
    if (this.cleared) return
    this.tries += 1
    for (const b of this.findByTag('balloon')) {
      if (typeof b.reset === 'function') b.reset()
    }
    const hero = this._findActive('player')
    if (hero && typeof hero.respawnTo === 'function') {
      hero.respawnTo(this._spawnX, this._spawnY)
    }
    this.totalTries = this._computeTotalTries()
  }

  _handleClear() {
    if (this.cleared) return
    this.cleared = true

    // Save best for current stage.
    const prev = this._loadBest(this.stage)
    if (prev === null || this.tries < prev) {
      this._saveBest(this.stage, this.tries)
    }
    this.best = this._loadBest(this.stage)
    this.totalBest = this._computeTotalBest()

    // Confetti at goal flag.
    const flag = this._findActive('goal-flag')
    if (flag?.gameObject) {
      this._spawnConfetti(flag.gameObject.x, flag.gameObject.y, this._goalConfettiCount)
    } else {
      const goal = this._findActive('goal')
      if (goal?.gameObject) {
        this._spawnConfetti(goal.gameObject.x, goal.gameObject.y - 60, this._goalConfettiCount)
      }
    }

    const meta = STAGES.find(s => s.name === this.stage)
    const bestStr = this.best != null ? this.best : '-'

    if (!meta.next) {
      // Final stage: build Game Complete overlay, DO NOT switch scene.
      // Record final-stage tries into the session accumulator so totalTries is stable.
      this._triesByStage[this.stage] = this.tries
      this.totalTries = STAGES.reduce((acc, s) => acc + (this._triesByStage[s.name] || 0), 0)
      const totalBestStr = this.totalBest != null ? this.totalBest : '-'
      this.centerHtml =
        `Game Complete!<br>` +
        `Tries: ${this.tries}<br>` +
        `Best: ${bestStr}<br>` +
        `Total Tries: ${this.totalTries}<br>` +
        `Best Total: ${totalBestStr}`
      return
    }

    // Non-final: clear popup, schedule next.
    this._triesByStage[this.stage] = this.tries
    this.totalTries = this._computeTotalTries()
    this.centerText = `${meta.label} Clear! Tries: ${this.tries} / Best: ${bestStr}`
    this.scene.time.delayedCall(this.clearDelayMs, () => {
      this._loadStage(meta.next)
    })
  }

  async _spawnConfetti(x, y, count) {
    if (!this._host) return
    for (let i = 0; i < count; i++) {
      try {
        await this._host.instantiate('entities/fx/confetti.node.json', { x, y })
      } catch (err) {
        console.error('StageManager: confetti spawn failed', err)
        return
      }
    }
  }

  runtimeState() {
    return {
      stage: this.stage,
      tries: this.tries,
      best: this.best,
      cleared: this.cleared,
      centerText: this.centerText,
      centerHtml: this.centerHtml,
      isFinal: this.isFinal,
      totalTries: this.totalTries,
      totalBest: this.totalBest,
    }
  }
}
