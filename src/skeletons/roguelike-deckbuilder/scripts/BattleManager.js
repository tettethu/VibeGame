import { Node } from '/engine/Node.js'
import { STARTER_DECK_TEMPLATE, REWARD_POOL, shuffle } from './CardData.js'
import { extractFrameDataUrl } from './AtlasUtils.js'

export default class BattleManager extends Node {
  ready() {
    this._destroyed = false

    // Defer wiring to next frame so all siblings' ready() complete first
    this.scene.time.delayedCall(0, () => {
      if (this._destroyed) return

      this._playerNode   = this.findByTag('player')[0]
      this._enemyNode    = this.findByTag('enemy')[0]
      this._handRenderer = this.findByTag('handRenderer')[0]
      this._hudRenderer  = this.findByTag('hudRenderer')[0]
      this._overlayNode  = this.findByTag('overlay')[0]

      this._hudRenderer?.setEndTurnCallback(() => this._endTurn())
      this._handRenderer?.setCardPlayCallback((idx, targetTag) => this._onCardPlay(idx, targetTag))

      // Pre-extract card art data URLs for the reward picker overlay
      this._cardArtUrls = {}
      const CARD_IDS = ['strike','deflect','bash','twin_strike','heavy_blow','overload',
                        'scramble','iron_curtain','phase_shift','neural_link','overclock','reflex_grid']
      for (const id of CARD_IDS) {
        this._cardArtUrls[id] = extractFrameDataUrl(this.scene, 'cards', id, 96)
      }

      this._initRun()
    })
  }

  destroy() { this._destroyed = true }

  _animDurationMs(node, animName) {
    const clip = node?.animationPlayer?.def?.clips?.[animName]
    if (!clip) return 300
    if (Array.isArray(clip.frameDurations) && clip.frameDurations.length > 0) {
      return clip.frameDurations.reduce((sum, ms) => sum + (Number(ms) || 0), 0)
    }
    const frameCount = Array.isArray(clip.frames) && clip.frames.length > 0 ? clip.frames.length : 1
    const frameRate = Number(clip.frameRate || 10)
    return frameRate > 0 ? Math.ceil(frameCount / frameRate * 1000) : 300
  }

  _awaitAnim(node, animName, maxMs = null) {
    if (!node?.triggerAnim) return Promise.resolve(false)

    return new Promise((resolve) => {
      let done = false
      const finish = (reason) => {
        if (done) return
        done = true
        if (animName !== 'die') {
          node.playAnim?.('idle', { restart: true, force: true })
          if (node.animator) node.animator.currentState = 'idle'
        }
        resolve(reason)
      }

      node.triggerAnim(animName)
      const duration = maxMs ?? this._animDurationMs(node, animName) + 40
      globalThis.setTimeout(() => finish('duration'), duration)
    })
  }

  // ─── Run / Fight init ─────────────────────────────────────────────────────

  _initRun() {
    this.hp = 80;    this.hpMax = 80
    this.block = 0;  this.vulnerable = 0
    this.energy = 3; this.energyMax = 3
    this.gold = 0;   this.turn = 1; this.fightNumber = 1

    this.drawPile     = this._buildStarterDeck()
    this.hand         = []
    this.discardPile  = []
    this.activePowers = new Set()

    this.enemyIntentIndex = 0
    this.gamePhase = 'playerTurn'
    this.isResolvingAction = false

    this._startFight(1)
  }

  _buildStarterDeck() {
    return shuffle(STARTER_DECK_TEMPLATE.map((c, i) => ({
      ...c, uid: `s_${i}_${Date.now()}`
    })))
  }

  _startFight(n) {
    this.enemyHp         = 200 + (n - 1) * 20
    this.enemyHpMax      = this.enemyHp
    this.enemyBlock      = 0
    this.enemyVulnerable = 0
    this.enemyIntentIndex = 0
    this._startPlayerTurn()
  }

  _startPlayerTurn() {
    this.block  = 0
    if (this.activePowers.has('reflex_grid')) this.block += 3
    this.energy = this.energyMax

    this.discardPile.push(...this.hand)
    this.hand = []
    this._drawCards(5)
    this.gamePhase = 'playerTurn'
    this._notifyRenderers()
  }

  // ─── Turn sequence ────────────────────────────────────────────────────────

  async _endTurn() {
    if (this.gamePhase !== 'playerTurn' || this.isResolvingAction) return
    this.isResolvingAction = true
    this.gamePhase = 'enemyTurn'
    this._notifyRenderers()

    this.enemyBlock = 0

    // Phase 1: Execute intent with matching enemy animation.
    const intent = this._getIntent(this.enemyIntentIndex, this.fightNumber)
    if (intent.type === 'FORTIFY') {
      await this._awaitAnim(this._enemyNode, 'taunt')
      if (this._destroyed) return
      this.enemyBlock += intent.value
    } else {
      await this._awaitAnim(this._enemyNode, 'attack')
      if (this._destroyed) return

      const result = this._dealDamage('player', intent.value, false)
      this._overlayNode?.flashHurt?.()
      // VFX on player: block_break if any block absorbed, hit_impact if HP was lost
      if (result.blockAbsorbed > 0) this._spawnVfx(this._playerNode, 'block_break')
      if (result.hpDamage > 0) {
        this._spawnVfx(this._playerNode, 'hit_impact')
        await this._awaitAnim(this._playerNode, 'hurt')
      }
    }
    if (this._destroyed) return

    // Phase 3: Settle vulnerable, advance intent cycle
    this.vulnerable       = Math.max(0, this.vulnerable - 1)
    this.enemyVulnerable  = Math.max(0, this.enemyVulnerable - 1)
    this.enemyIntentIndex = (this.enemyIntentIndex + 1) % 3

    if (this.hp <= 0) {
      this.gamePhase = 'runOver'
      this.isResolvingAction = false
      this._notifyRenderers()
      this._showRunOver()
      return
    }

    this.turn++
    this.isResolvingAction = false
    this._startPlayerTurn()
  }

  // ─── Card play ────────────────────────────────────────────────────────────

  // targetTag ('enemy' | 'self') is validated by HandRenderer; not used here
  // since card.effect already encodes the target type
  async _onCardPlay(handIdx, targetTag) {
    if (this.gamePhase !== 'playerTurn' || this.isResolvingAction) return
    const card = this.hand[handIdx]
    if (!card || card.cost > this.energy) return

    this.isResolvingAction = true
    this.energy -= card.cost
    this.hand.splice(handIdx, 1)
    this.discardPile.push(card)
    this._notifyRenderers()
    try {
      await this._applyCardEffect(card)
    } finally {
      if (!this._destroyed && this.gamePhase === 'playerTurn') {
        this.isResolvingAction = false
        this._notifyRenderers()
      }
    }
  }

  async _applyCardEffect(card) {
    switch (card.effect) {
      case 'damage': {
        this._spawnCardTrail()
        await this._awaitAnim(this._playerNode, 'attack')
        if (this._destroyed) return
        this._dealDamage('enemy', card.value, true)
        this._spawnVfx(this._enemyNode, 'hit_impact')
        if (this.enemyHp <= 0) { await this._onEnemyDefeated(); return }
        break
      }
      case 'bash': {
        this._spawnCardTrail()
        await this._awaitAnim(this._playerNode, 'attack')
        if (this._destroyed) return
        this._dealDamage('enemy', card.value, true)
        this.enemyVulnerable += (card.vuln ?? 2)
        this._spawnVfx(this._enemyNode, 'hit_impact')
        this._spawnVfx(this._enemyNode, 'vulnerable_apply')
        if (this.enemyHp <= 0) { await this._onEnemyDefeated(); return }
        break
      }
      case 'twin_strike': {
        this._spawnCardTrail()
        await this._awaitAnim(this._playerNode, 'attack')
        if (this._destroyed) return
        this._dealDamage('enemy', card.value, true)
        this._dealDamage('enemy', card.value, true)
        this._spawnVfx(this._enemyNode, 'hit_impact')
        this._spawnVfx(this._enemyNode, 'hit_impact')
        if (this.enemyHp <= 0) { await this._onEnemyDefeated(); return }
        break
      }
      case 'block':
        this._spawnCardTrail()
        this.block += card.value
        break
      case 'vuln_enemy':
        this._spawnCardTrail()
        this.enemyVulnerable += card.value
        this._spawnVfx(this._enemyNode, 'vulnerable_apply')
        break
      case 'block_draw':
        this._spawnCardTrail()
        this.block += card.value
        this._drawCards(card.draw ?? 1)
        break
      case 'draw':
        this._spawnCardTrail()
        this._drawCards(card.value)
        break
      case 'power_overclock':
        this._spawnCardTrail()
        this.activePowers.add('overclock')
        break
      case 'power_reflex_grid':
        this._spawnCardTrail()
        this.activePowers.add('reflex_grid')
        break
    }
    this._notifyRenderers()
  }

  // ─── Deck operations ──────────────────────────────────────────────────────

  _drawCards(n) {
    for (let i = 0; i < n; i++) {
      if (this.drawPile.length === 0) {
        if (this.discardPile.length === 0) break
        this.drawPile    = shuffle([...this.discardPile])
        this.discardPile = []
      }
      this.hand.push(this.drawPile.shift())
    }
  }

  // ─── Damage ───────────────────────────────────────────────────────────────

  _dealDamage(target, rawDmg, isAttack) {
    let dmg = rawDmg
    if (target === 'enemy' && isAttack && this.activePowers.has('overclock')) dmg += 3
    const vuln = target === 'enemy' ? this.enemyVulnerable : this.vulnerable
    if (vuln > 0) dmg = Math.floor(dmg * 1.5)

    if (target === 'enemy') {
      const absorbed = Math.min(this.enemyBlock, dmg)
      this.enemyBlock -= absorbed
      const hpDmg = dmg - absorbed
      this.enemyHp = Math.max(0, this.enemyHp - hpDmg)
      return { damage: dmg, blockAbsorbed: absorbed, hpDamage: hpDmg }
    } else {
      const absorbed = Math.min(this.block, dmg)
      this.block -= absorbed
      const hpDmg = dmg - absorbed
      this.hp = Math.max(0, this.hp - hpDmg)
      return { damage: dmg, blockAbsorbed: absorbed, hpDamage: hpDmg }
    }
  }

  // ─── Enemy intent ─────────────────────────────────────────────────────────

  _getIntent(index, n) {
    return [
      { type: 'SMASH',       value: 12 + (n - 1) * 2 },
      { type: 'HEAVY_SWING', value: 20 + (n - 1) * 2 },
      { type: 'FORTIFY',     value: 12 + (n - 1)     },
    ][index % 3]
  }

  // ─── Victory / defeat ─────────────────────────────────────────────────────

  async _onEnemyDefeated() {
    this.gamePhase = 'cardPick'
    this._notifyRenderers()

    if (this._enemyNode?.triggerAnim) {
      await new Promise(r => this._enemyNode.triggerAnim('die', r))
    }

    this.gold += 10 + (this.fightNumber - 1) * 5
    this._notifyRenderers()
    await this._showCardReward()
  }

  async _showCardReward() {
    const pool = REWARD_POOL
      .filter(c => !(c.effect.startsWith('power_') && this.activePowers.has(c.id)))
      .map(c => ({
        ...c,
        label: c.name,
        icon: this._cardArtUrls[c.id]
          ? `<img src="${this._cardArtUrls[c.id]}" style="width:100%;border-radius:4px;display:block;">`
          : (c.icon || '')
      }))

    if (pool.length === 0) {
      this._startNextFight()
      return
    }

    const picker = await this.instantiate('entities/card_picker.node.json', {
      buffPool: pool,
      onSelect: (opt) => this._onRewardPicked(opt),
      onClose:  () => {
        picker?.removeSelf?.()
        this._startNextFight()
      },
    })
    picker?.show?.()
  }

  _onRewardPicked(opt) {
    this.drawPile.push({ ...opt, uid: `rwd_${Date.now()}` })
    if (opt.effect === 'power_overclock')   this.activePowers.add('overclock')
    if (opt.effect === 'power_reflex_grid') this.activePowers.add('reflex_grid')
  }

  _startNextFight() {
    this.hp = Math.min(this.hpMax, this.hp + 6)
    this.fightNumber++
    const all = [...this.drawPile, ...this.hand, ...this.discardPile]
    this.drawPile    = shuffle(all)
    this.hand        = []
    this.discardPile = []
    this._startFight(this.fightNumber)
  }

  async _showRunOver() {
    // Play player die animation before showing the overlay
    if (this._playerNode?.triggerAnim) {
      await new Promise(r => this._playerNode.triggerAnim('die', r))
    }
    if (this._destroyed) return
    const panel = document.querySelector('#vg-menu-runover-panel')
    if (panel) {
      const p = panel.querySelector('p')
      if (p) p.textContent = `Fights survived: ${this.fightNumber}.  EDS earned: ${this.gold}.`
    }
    this._overlayNode?.showMenu?.('runover')
  }

  // ─── VFX ─────────────────────────────────────────────────────────────────

  _spawnVfx(targetNode, vfxType = 'hit_impact') {
    const go = targetNode?.getVisualObject()
    if (!go) return
    const cx = go.x
    // Bottom-anchored sprite: center y = feet - half of displayed height
    const cy = go.y - (go.displayHeight ?? 100) * 0.5
    this.instantiate(`entities/vfx_${vfxType}.node.json`, { x: cx, y: cy })
  }

  _spawnCardTrail() {
    const go = this._playerNode?.getVisualObject()
    if (!go) return
    // Spawn slightly in front of and above the player
    this.instantiate('entities/vfx_card_trail.node.json', {
      x: go.x + 50,
      y: go.y - (go.displayHeight ?? 200) * 0.6
    })
  }

  // ─── Renderer notify ─────────────────────────────────────────────────────

  _notifyRenderers() {
    const state = this.runtimeState()
    this._handRenderer?.refresh?.(this.hand, this.energy, this.gamePhase, this.isResolvingAction)
    this._hudRenderer?.refresh?.(state)
  }

  // ─── Runtime state ────────────────────────────────────────────────────────

  runtimeState() {
    const intent = this._getIntent?.(this.enemyIntentIndex ?? 0, this.fightNumber ?? 1)
    return {
      hp:              this.hp              ?? 0,
      hpMax:           this.hpMax           ?? 80,
      block:           this.block           ?? 0,
      vulnerable:      this.vulnerable      ?? 0,
      energy:          this.energy          ?? 0,
      energyMax:       this.energyMax       ?? 3,
      gold:            this.gold            ?? 0,
      turn:            this.turn            ?? 1,
      fightNumber:     this.fightNumber     ?? 1,
      deckCount:       (this.drawPile       ?? []).length,
      handCount:       (this.hand           ?? []).length,
      discardCount:    (this.discardPile    ?? []).length,
      enemyHp:         this.enemyHp         ?? 200,
      enemyHpMax:      this.enemyHpMax      ?? 200,
      enemyBlock:      this.enemyBlock      ?? 0,
      enemyVulnerable: this.enemyVulnerable ?? 0,
      enemyIntent:     { type: intent?.type ?? 'SMASH', value: intent?.value ?? 12 },
      gamePhase:       this.gamePhase       ?? 'init',
      isResolvingAction: !!this.isResolvingAction,
    }
  }
}
