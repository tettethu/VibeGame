/**
 * WebSocket bridge between backend runtime API and the engine RuntimeController.
 * Receives commands from backend, executes on engine, returns results.
 *
 * Protocol: backend sends { id, cmd, ...params }, bridge responds { id, result }.
 */

import { RuntimeController } from './RuntimeController.js'

export class RuntimeBridge {
  /** Reconnect interval in ms */
  static RECONNECT_INTERVAL = 3000
  /** Ping interval in ms */
  static PING_INTERVAL = 15000

  static installBuffers() {
    if (window.__vibegameRuntime) return
    const MAX_CONSOLE = 200
    const MAX_NETWORK = 500
    const runtime = window.__vibegameRuntime = { console: [], network: [], _seq: 0 }
    const recentErrors = new Set()

    const trimConsole = () => {
      if (runtime.console.length > MAX_CONSOLE) runtime.console.shift()
    }

    const stringifyConsoleValue = (value) => {
      if (value instanceof Error) return value.stack || `${value.name}: ${value.message}`
      if (value && typeof value === 'object') {
        try { return JSON.stringify(value) } catch { return String(value) }
      }
      return String(value)
    }

    const pushConsole = (level, source, message, extra = {}) => {
      const key = `${level}:${message}:${extra.stack || ''}`
      if (recentErrors.has(key)) return
      recentErrors.add(key)
      setTimeout(() => recentErrors.delete(key), 1000)
      runtime.console.push({
        seq: runtime._seq++,
        level,
        source,
        message,
        timestamp: Date.now(),
        ...extra,
      })
      trimConsole()
    }

    // Console capture
    for (const level of ['log', 'info', 'warn', 'error']) {
      const orig = console[level].bind(console)
      console[level] = (...args) => {
        orig(...args)
        pushConsole(level, 'console', args.map(stringifyConsoleValue).join(' '))
      }
    }

    // Uncaught error capture
    const origOnerror = window.onerror
    window.onerror = (msg, src, line, col, err) => {
      pushConsole('error', 'onerror', String(msg) + (src ? ` (${src}:${line}:${col})` : ''), {
        stack: err?.stack || null,
      })
      return origOnerror ? origOnerror(msg, src, line, col, err) : false
    }

    window.addEventListener('error', (event) => {
      const target = event.target
      if (target && target !== window && (target.src || target.href)) {
        pushConsole('error', 'resource', `Failed to load resource: ${target.src || target.href}`)
        return
      }

      const message = event.message || event.error?.message || 'Uncaught error'
      pushConsole('error', 'error', message + (event.filename ? ` (${event.filename}:${event.lineno}:${event.colno})` : ''), {
        stack: event.error?.stack || null,
      })
    }, true)

    // Unhandled promise rejection capture
    window.addEventListener('unhandledrejection', (e) => {
      const reason = e.reason
      pushConsole('error', 'unhandledrejection', reason ? (reason.message || String(reason)) : 'Unhandled promise rejection', {
        stack: reason?.stack || null,
      })
    })

    // fetch capture
    const origFetch = window.fetch.bind(window)
    window.fetch = async (input, init) => {
      const method = (init?.method || 'GET').toUpperCase()
      const url = typeof input === 'string' ? input : input instanceof Request ? input.url : String(input)
      const startTime = Date.now()
      const entry = { seq: runtime._seq++, method, url, initiator: 'fetch', timestamp: startTime }
      try {
        const res = await origFetch(input, init)
        entry.status = res.status; entry.ok = res.ok; entry.durationMs = Date.now() - startTime
        runtime.network.push(entry)
        if (runtime.network.length > MAX_NETWORK) runtime.network.shift()
        return res
      } catch (err) {
        entry.status = 0; entry.ok = false; entry.durationMs = Date.now() - startTime; entry.error = err.message || String(err)
        runtime.network.push(entry)
        if (runtime.network.length > MAX_NETWORK) runtime.network.shift()
        throw err
      }
    }

    // XHR capture
    const OrigXHR = window.XMLHttpRequest
    window.XMLHttpRequest = class extends OrigXHR {
      constructor() { super(); this._xhrMethod = 'GET'; this._xhrUrl = ''; this._xhrStart = 0 }
      open(method, url, ...rest) { this._xhrMethod = method; this._xhrUrl = url; return super.open(method, url, ...rest) }
      send(...args) {
        this._xhrStart = Date.now()
        this.addEventListener('loadend', () => {
          const entry = {
            seq: runtime._seq++, method: this._xhrMethod.toUpperCase(), url: this._xhrUrl,
            status: this.status, ok: this.status >= 200 && this.status < 300,
            durationMs: Date.now() - this._xhrStart, initiator: 'xhr', timestamp: this._xhrStart,
          }
          runtime.network.push(entry)
          if (runtime.network.length > MAX_NETWORK) runtime.network.shift()
        })
        return super.send(...args)
      }
    }
  }

  /**
   * @param {import('./PhaserHost.js').PhaserHost} host
   * @param {import('./SceneTree.js').SceneTree} sceneTree
   */
  constructor(host, sceneTree) {
    this.host = host
    this.sceneTree = sceneTree
    this.ws = null
    this.runtimeController = sceneTree.runtimeController || null
    this._wsUrl = null
    this._pingTimer = null
    this._reconnectTimer = null
    this._intentionalClose = false
  }

  /** Connect to backend runtime WebSocket with auto-reconnect */
  connect(wsUrl) {
    this._wsUrl = wsUrl
    this._intentionalClose = false
    this._connect()
  }

  _connect() {
    if (this.ws) {
      this.ws.close()
    }
    this.ws = new WebSocket(this._wsUrl)
    this.ws.onopen = () => {
      this._startPing()
      if (this._reconnectTimer) {
        clearTimeout(this._reconnectTimer)
        this._reconnectTimer = null
      }
    }
    this.ws.onmessage = (e) => {
      if (e.data === '__ping__') {
        this._send('__pong__')
        return
      }
      this._handleMessage(JSON.parse(e.data))
    }
    this.ws.onclose = () => {
      this.ws = null
      this._stopPing()
      if (!this._intentionalClose) this._scheduleReconnect()
    }
    this.ws.onerror = () => {
      // onclose will fire after onerror, reconnect handled there
    }
  }

  _startPing() {
    this._stopPing()
    this._pingTimer = setInterval(() => {
      if (this.ws?.readyState === WebSocket.OPEN) {
        this.ws.send('__ping__')
      }
    }, RuntimeBridge.PING_INTERVAL)
  }

  _stopPing() {
    if (this._pingTimer) {
      clearInterval(this._pingTimer)
      this._pingTimer = null
    }
  }

  _scheduleReconnect() {
    if (this._reconnectTimer) return
    this._reconnectTimer = setTimeout(() => {
      this._reconnectTimer = null
      this._connect()
    }, RuntimeBridge.RECONNECT_INTERVAL)
  }

  /** Disconnect and clean up */
  disconnect() {
    this._intentionalClose = true
    if (this._reconnectTimer) {
      clearTimeout(this._reconnectTimer)
      this._reconnectTimer = null
    }
    this._stopPing()
    if (this.runtimeController) {
      this.runtimeController.deactivate()
      this.sceneTree.runtimeController = null
      this.runtimeController = null
    }
    if (this.ws) {
      this.ws.close()
      this.ws = null
    }
  }

  /** @param {{id: string, cmd: string, [key: string]: unknown}} msg */
  async _handleMessage(msg) {
    const { id, cmd, ...params } = msg
    let result

    try {
      switch (cmd) {
        case 'activate':
          result = this._cmdActivate()
          break
        case 'deactivate':
          result = this._cmdDeactivate()
          break
        case 'continue':
          result = await this._cmdContinue(params.frames ?? 60)
          break
        case 'pause':
          result = this._cmdPause()
          break
        case 'play':
          result = this._cmdPlay()
          break
        case 'snapshot':
          result = this._cmdSnapshot()
          break
        case 'input':
          result = this._cmdInput(params)
          break
        case 'set':
          result = this._cmdSet(params)
          break
        case 'click':
          result = this._cmdClick(params)
          break
        case 'mousemove':
          result = this._cmdMousemove(params)
          break
        case 'drag':
          result = await this._cmdDrag(params)
          break
        case 'key':
          result = this._cmdKey(params)
          break
        case 'eval':
          result = await this._cmdEval(params)
          break
        case 'status':
          result = this._cmdStatus()
          break
        case 'console_get':
          result = this._cmdConsoleGet(params)
          break
        case 'console_clear':
          result = this._cmdConsoleClear()
          break
        case 'network_get':
          result = this._cmdNetworkGet(params)
          break
        case 'network_clear':
          result = this._cmdNetworkClear()
          break
        default:
          result = { error: `Unknown command: ${cmd}` }
      }
    } catch (err) {
      result = { error: err.message || String(err) }
    }

    this._send({ id, result })
  }

  _send(data) {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(data))
    }
  }

  // --- Command handlers ---

  _cmdActivate() {
    if (!this.sceneTree.runtimeController) {
      this.sceneTree.runtimeController = new RuntimeController(this.sceneTree)
    }
    this.runtimeController = this.sceneTree.runtimeController
    this.sceneTree.running = true
    if (!this.runtimeController.enabled) {
      this.runtimeController.activate()
    } else {
      this.runtimeController.pause()
    }
    return { status: 'ok', frame: this.runtimeController.frameCount }
  }

  _cmdDeactivate() {
    if (this.runtimeController) {
      this.runtimeController.deactivate()
      this.sceneTree.runtimeController = null
      this.sceneTree.running = true
      this.runtimeController = null
    }
    return { status: 'ok' }
  }

  async _cmdContinue(frames) {
    if (!this.runtimeController?.enabled) return { error: 'No runtime session. Call activate first.' }
    return await this.runtimeController.continue(frames)
  }

  _cmdPause() {
    if (!this.runtimeController?.enabled) return { error: 'No runtime session' }
    this.runtimeController.pause()
    return { status: 'paused', frame: this.runtimeController.frameCount }
  }

  _cmdPlay() {
    if (!this.runtimeController?.enabled) return { error: 'No runtime session' }
    this.runtimeController.play()
    return { status: 'playing', frame: this.runtimeController.frameCount }
  }

  _cmdSnapshot() {
    if (!this.runtimeController?.enabled) return { error: 'No runtime session' }
    return this.runtimeController.snapshot()
  }

  _cmdInput(params) {
    const inputMap = this.sceneTree.inputMap
    if (!inputMap) return { error: 'No input map loaded' }

    const { action, held } = params
    if (!action) return { error: 'Missing action field' }

    if (held !== undefined) {
      // held=true starts holding, held=false releases
      if (held) {
        inputMap.inject(action, { held: true })
      } else {
        inputMap.clearInjection(action)
      }
    } else {
      // One-shot press (consumed on next frame)
      inputMap.inject(action, { pressed: true })
    }
    return { status: 'ok' }
  }

  _cmdSet(params) {
    const { nodeId, path, value } = params
    if (!nodeId || !path) return { error: 'Missing nodeId or path' }

    const node = this.sceneTree.nodes.get(nodeId)
    if (!node) return { error: `Node "${nodeId}" not found` }

    const parts = path.split('.')
    let target = node
    for (let i = 0; i < parts.length - 1; i++) {
      target = target[parts[i]]
      if (target == null) return { error: `Invalid path: "${path}" (null at "${parts[i]}")` }
    }
    target[parts[parts.length - 1]] = value
    return { status: 'ok' }
  }

  async _cmdEval({ code }) {
    if (!code) return { error: 'Missing code' }
    try {
      const fn = new Function('sceneTree', 'host', 'runtime',
        `"use strict"; return (async () => { ${code} })()`)
      const ret = await fn(this.sceneTree, this.host, this.runtimeController)
      return { result: ret === undefined ? null : ret }
    } catch (err) {
      return { error: err.message || String(err) }
    }
  }

  _cmdStatus() {
    const active = !!this.runtimeController?.enabled
    return {
      active,
      mode: active ? this.runtimeController.mode : 'inactive',
      frame: active ? this.runtimeController.frameCount : 0,
    }
  }

  _cmdConsoleGet({ since, level } = {}) {
    const runtime = window.__vibegameRuntime
    if (!runtime) return { entries: [], lastSeq: -1 }
    const levels = ['log', 'info', 'warn', 'error']
    let entries = runtime.console
    if (since != null) entries = entries.filter(e => e.seq > since)
    if (level) {
      const minIdx = levels.indexOf(level)
      if (minIdx >= 0) entries = entries.filter(e => levels.indexOf(e.level) >= minIdx)
    }
    const lastSeq = runtime.console.length ? runtime.console[runtime.console.length - 1].seq : -1
    return { entries, lastSeq }
  }

  _cmdConsoleClear() {
    if (window.__vibegameRuntime) window.__vibegameRuntime.console = []
    return { status: 'ok' }
  }

  _cmdNetworkGet({ since, failedOnly } = {}) {
    const runtime = window.__vibegameRuntime
    if (!runtime) return { entries: [], lastSeq: -1 }
    let entries = runtime.network
    if (since != null) entries = entries.filter(e => e.seq > since)
    if (failedOnly) entries = entries.filter(e => !e.ok)
    const lastSeq = runtime.network.length ? runtime.network[runtime.network.length - 1].seq : -1
    return { entries, lastSeq }
  }

  _cmdNetworkClear() {
    if (window.__vibegameRuntime) window.__vibegameRuntime.network = []
    return { status: 'ok' }
  }

  // --- Coordinate conversion ---

  /** Convert game-world coordinates to canvas DOM clientX/clientY */
  _gameToClient(x, y) {
    const cam = this.host.phaserScene.cameras.main
    // World -> camera-relative (accounts for scroll + zoom)
    const cx = (x - cam.scrollX) * cam.zoom
    const cy = (y - cam.scrollY) * cam.zoom
    // Camera-relative -> DOM client coordinates
    const canvas = this.host.game.canvas
    const rect = canvas.getBoundingClientRect()
    const scale = this.host.game.scale.displayScale
    return {
      clientX: cx * scale.x + rect.left,
      clientY: cy * scale.y + rect.top,
    }
  }

  // --- Raw input simulation ---

  /** Convert button index (0=left,1=mid,2=right) to buttons bitmask */
  _buttonBitmask(button) { return [1, 4, 2][button] ?? 1 }

  _cmdClick(params) {
    const { x, y, button = 0 } = params
    if (x == null || y == null) return { error: 'Missing x or y' }

    const canvas = this.host.game.canvas
    const { clientX, clientY } = this._gameToClient(x, y)
    const buttons = this._buttonBitmask(button)

    canvas.dispatchEvent(new PointerEvent('pointerdown', { clientX, clientY, button, buttons, bubbles: true }))
    canvas.dispatchEvent(new PointerEvent('pointerup', { clientX, clientY, button, buttons: 0, bubbles: true }))
    return { status: 'ok' }
  }

  _cmdMousemove(params) {
    const { x, y } = params
    if (x == null || y == null) return { error: 'Missing x or y' }

    const canvas = this.host.game.canvas
    const { clientX, clientY } = this._gameToClient(x, y)

    canvas.dispatchEvent(new PointerEvent('pointermove', { clientX, clientY, bubbles: true }))
    return { status: 'ok' }
  }

  async _cmdDrag(params) {
    const from = params.from || (
      params.fromX != null && params.fromY != null
        ? { x: params.fromX, y: params.fromY }
        : null
    )
    const to = params.to || (
      params.toX != null && params.toY != null
        ? { x: params.toX, y: params.toY }
        : null
    )
    const { steps = 10, button = 0 } = params
    if (!from || !to) return { error: 'Missing from or to' }
    if (from.x == null || from.y == null) return { error: 'Missing from.x or from.y' }
    if (to.x == null || to.y == null) return { error: 'Missing to.x or to.y' }

    const canvas = this.host.game.canvas
    const start = this._gameToClient(from.x, from.y)
    const end = this._gameToClient(to.x, to.y)
    const buttons = this._buttonBitmask(button)

    // Press at start position
    canvas.dispatchEvent(new PointerEvent('pointerdown', {
      clientX: start.clientX, clientY: start.clientY, button, buttons, bubbles: true,
    }))

    // Interpolate movement (button held)
    for (let i = 1; i <= steps; i++) {
      const t = i / steps
      const cx = start.clientX + (end.clientX - start.clientX) * t
      const cy = start.clientY + (end.clientY - start.clientY) * t
      canvas.dispatchEvent(new PointerEvent('pointermove', {
        clientX: cx, clientY: cy, button: -1, buttons, bubbles: true,
      }))
      await new Promise((r) => setTimeout(r, 16))
    }

    // Release at end position
    canvas.dispatchEvent(new PointerEvent('pointerup', {
      clientX: end.clientX, clientY: end.clientY, button, buttons: 0, bubbles: true,
    }))
    return { status: 'ok' }
  }

  /** Map DOM code -> key value. Returns null for unknown codes. */
  static _CODE_TO_KEY = (() => {
    const m = {}
    // Letters: KeyA-KeyZ -> a-z
    for (let i = 0; i < 26; i++) {
      const ch = String.fromCharCode(65 + i)
      m['Key' + ch] = ch.toLowerCase()
    }
    // Digits: Digit0-Digit9 -> 0-9
    for (let i = 0; i <= 9; i++) { m['Digit' + i] = String(i) }
    // Numpad
    for (let i = 0; i <= 9; i++) { m['Numpad' + i] = String(i) }
    Object.assign(m, {
      NumpadAdd: '+', NumpadSubtract: '-', NumpadMultiply: '*',
      NumpadDivide: '/', NumpadDecimal: '.', NumpadEnter: 'Enter',
      // Punctuation
      Minus: '-', Equal: '=', BracketLeft: '[', BracketRight: ']',
      Backslash: '\\', Semicolon: ';', Quote: "'", Backquote: '`',
      Comma: ',', Period: '.', Slash: '/',
      // Whitespace / control
      Space: ' ', Enter: 'Enter', Escape: 'Escape', Tab: 'Tab',
      Backspace: 'Backspace', Delete: 'Delete',
      Insert: 'Insert', Home: 'Home', End: 'End',
      PageUp: 'PageUp', PageDown: 'PageDown',
      CapsLock: 'CapsLock',
      // Arrows
      ArrowUp: 'ArrowUp', ArrowDown: 'ArrowDown',
      ArrowLeft: 'ArrowLeft', ArrowRight: 'ArrowRight',
      // Modifiers
      ShiftLeft: 'Shift', ShiftRight: 'Shift',
      ControlLeft: 'Control', ControlRight: 'Control',
      AltLeft: 'Alt', AltRight: 'Alt',
      MetaLeft: 'Meta', MetaRight: 'Meta',
    })
    // F-keys: F1-F12
    for (let i = 1; i <= 12; i++) { m['F' + i] = 'F' + i }
    return m
  })()

  _cmdKey(params) {
    const { key, type = 'press' } = params
    if (!key) return { error: 'Missing key' }
    if (type !== 'press' && type !== 'down' && type !== 'up') {
      return { error: `Invalid type: "${type}". Must be press, down, or up` }
    }

    const keyValue = RuntimeBridge._CODE_TO_KEY[key]
    if (keyValue === undefined) {
      return { error: `Unknown key code: "${key}". Use DOM KeyboardEvent.code values (e.g. "KeyA", "Space", "ArrowUp")` }
    }

    const opts = { code: key, key: keyValue, bubbles: true, cancelable: true }
    const targets = [window, document, this.host.game.canvas].filter(Boolean)
    const dispatch = (eventType) => {
      for (const target of targets) {
        target.dispatchEvent(new KeyboardEvent(eventType, opts))
      }
    }

    if (type === 'down' || type === 'press') {
      dispatch('keydown')
    }
    if (type === 'up' || type === 'press') {
      dispatch('keyup')
    }
    return { status: 'ok' }
  }
}
