/**
 * Lightweight parameter-driven animator built on top of AnimationPlayer.
 * Inspired by classic state-machine controllers: scripts set parameters,
 * animator evaluates transitions and selects clips.
 */

export class Animator {
  player = null
  def = null
  currentState = null
  parameters = {}

  constructor(player, def) {
    this.player = player
    this.def = def || { states: {}, transitions: [] }

    for (const [name, type] of Object.entries(this.def.parameters || {})) {
      this.parameters[name] = type === 'bool' ? false : null
    }
  }

  init() {
    const initial = this.def.defaultState || null
    if (initial) {
      this._enterState(initial)
    }
  }

  setBool(name, value) {
    this.parameters[name] = Boolean(value)
  }

  getBool(name) {
    return Boolean(this.parameters[name])
  }

  setTrigger(name) {
    this.parameters[name] = true
  }

  resetTrigger(name) {
    this.parameters[name] = false
  }

  getState() {
    return this.currentState
  }

  update() {
    if (!this.currentState) return

    for (const transition of this.def.transitions || []) {
      if (!this._matchesFrom(transition.from)) continue
      if (transition.hasExitTime && !this.player?.isFinished()) continue
      if (!this._matchesConditions(transition.when || [])) continue

      this._consumeConditions(transition.when || [])
      this._enterState(transition.to)
      return
    }
  }

  _matchesFrom(from) {
    return from === this.currentState || from === 'Any'
  }

  _matchesConditions(conditions) {
    for (const cond of conditions) {
      if (cond.trigger) {
        if (!this.parameters[cond.trigger]) return false
        continue
      }

      if (cond.param) {
        if (cond.eq !== undefined && this.parameters[cond.param] !== cond.eq) return false
        continue
      }
    }
    return true
  }

  _consumeConditions(conditions) {
    for (const cond of conditions) {
      if (cond.trigger) {
        this.parameters[cond.trigger] = false
      }
    }
  }

  _enterState(name) {
    if (name === this.currentState) return
    const state = this.def.states?.[name]
    if (!state) {
      console.warn(`Animator: state "${name}" not found`)
      return
    }

    this.currentState = name
    if (state.clip) {
      this.player?.play(state.clip, { restart: true, force: true })
    }
  }
}
