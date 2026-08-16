/**
 * Action-to-key mapping. Config-driven input abstraction over Phaser keyboard.
 * Scripts use inputMap.isHeld('jump') instead of raw key checks.
 */

// DOM KeyboardEvent.code -> Phaser KeyCodes name
const KEY_ALIASES = {
  Escape: 'ESC', ArrowUp: 'UP', ArrowDown: 'DOWN',
  ArrowLeft: 'LEFT', ArrowRight: 'RIGHT',
  Enter: 'ENTER', ' ': 'SPACE',
  ShiftLeft: 'SHIFT', ShiftRight: 'SHIFT',
  ControlLeft: 'CTRL', ControlRight: 'CTRL',
  AltLeft: 'ALT', AltRight: 'ALT',
  Tab: 'TAB', Backspace: 'BACKSPACE', Delete: 'DELETE',
}

export class InputMap {
  /**
   * @param {Phaser.Scene} phaserScene
   * @param {object} mappingJson - { action: [keyName, ...] }
   */
  constructor(phaserScene, mappingJson) {
    this.scene = phaserScene
    this.keys = {}
    this._injected = {} // runtime injection: { action: { pressed, held } }
    this._injectedHeldLastFrame = {} // snapshot of injected held state at previous frame end

    // Support both flat { action: [keys] } and nested { actions: { action: { keys: [...] } } }
    const actions = mappingJson.actions || mappingJson
    for (const [action, val] of Object.entries(actions)) {
      const keyNames = Array.isArray(val) ? val : (val.keys || [])
      this.keys[action] = []
      for (const k of keyNames) {
        const normalized = KEY_ALIASES[k] || k
        const code = Phaser.Input.Keyboard.KeyCodes[normalized]
        if (code === undefined) {
          console.error(`InputMap: invalid key "${k}"${normalized !== k ? ` (normalized: "${normalized}")` : ''} for action "${action}". Not a valid Phaser KeyCode, skipping.`)
          continue
        }
        this.keys[action].push(phaserScene.input.keyboard.addKey(code, false))
      }
    }
  }

  /** Ignore game input when a UI input element has focus */
  _uiHasFocus() {
    const tag = document.activeElement?.tagName
    return tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT'
  }

  /** True if any mapped key was just pressed this frame */
  isPressed(action) {
    const inj = this._injected[action]
    if (inj?.pressed) {
      inj.pressed = false // one-shot, consumed after read
      return true
    }
    if (this._uiHasFocus()) return false
    return this.keys[action]?.some(k => Phaser.Input.Keyboard.JustDown(k)) || false
  }

  /** True if any mapped key is currently held down */
  isHeld(action) {
    if (this._injected[action]?.held) return true
    if (this._uiHasFocus()) return false
    return this.keys[action]?.some(k => k.isDown) || false
  }

  /** True if any mapped key was just released this frame */
  isReleased(action) {
    // Injection edge: held last frame, not held this frame
    if (this._injectedHeldLastFrame[action] && !this._injected[action]?.held) {
      return true
    }
    if (this._uiHasFocus()) return false
    return this.keys[action]?.some(k => Phaser.Input.Keyboard.JustUp(k)) || false
  }

  // === Runtime injection (used by RuntimeController) ===

  /**
   * Inject a virtual input for runtime testing.
   * @param {string} action
   * @param {{pressed?: boolean, held?: boolean}} state
   */
  inject(action, { pressed = false, held = false } = {}) {
    this._injected[action] = { pressed, held }
  }

  /** Clear injection for a single action */
  clearInjection(action) {
    delete this._injected[action]
  }

  /** Clear all injections */
  clearAllInjections() {
    this._injected = {}
    this._injectedHeldLastFrame = {}
  }

  /**
   * Snapshot current injected `held` state for next-frame release-edge detection.
   * Called by SceneTree once per frame, after all node updates.
   */
  _advanceFrame() {
    const next = {}
    for (const [action, inj] of Object.entries(this._injected)) {
      next[action] = !!inj.held
    }
    this._injectedHeldLastFrame = next
  }
}
