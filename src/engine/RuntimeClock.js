// Installed before game code by the runtime host, never by exported games.
(() => {
  const native = {
    now: performance.now.bind(performance),
    frame: window.requestAnimationFrame.bind(window),
    cancelFrame: window.cancelAnimationFrame.bind(window),
    timeout: window.setTimeout.bind(window),
    clearTimeout: window.clearTimeout.bind(window),
  }
  const contexts = new Set()
  const media = new Set()
  const collected = new FinalizationRegistry(({items, ref}) => items.delete(ref))
  const track = (items, value) => {
    const ref = new WeakRef(value)
    items.add(ref)
    collected.register(value, {items, ref})
  }
  const live = items => [...items].map(ref => ref.deref()).filter(value => value !== undefined)
  const AudioContext = window.AudioContext
  window.AudioContext = class extends AudioContext {
    constructor(...args) { super(...args); track(contexts, this) }
  }
  const Audio = window.Audio
  window.Audio = function (...args) { const item = new Audio(...args); track(media, item); return item }
  window.Audio.prototype = Audio.prototype

  const clock = window.__vibegameClock = {
    ready: false, frozen: false, dispatching: false, result: null,
    documentId: crypto.randomUUID(), revision: 0, operation: Promise.resolve(), held: true,
    running: false, advancing: false, failed: false, error: null, scheduled: null, pulse: null,
    due: 0, elapsed: 0, advanced: 0, published: null,
    contextsToResume: [], mediaToResume: [], displayInterval: null,
    configure(interval) { this.displayInterval = interval },
    advance(ms) { return gameTime.tickAsync(ms) },
    enqueue(work) {
      this.operation = this.operation.then(work)
      return this.operation
    },
    paused() { return this.runtime.enabled && this.runtime.mode === 'paused' },
    cancel() {
      if (this.scheduled !== null) native.cancelFrame(this.scheduled)
      this.scheduled = null
    },
    schedule() {
      if (!this.running || this.held || this.failed || this.paused() || this.scheduled !== null) return
      this.scheduled = native.frame(() => {
        this.scheduled = null
        this.schedule()
        if (this.advancing) return
        this.advancing = true
        this.enqueue(() => this.frame(native.now())).then(() => {
          this.advancing = false
        }, error => {
          this.advancing = false
          this.fail(error)
        })
      })
    },
    async frame(time) {
      if (this.held || this.paused()) return this.reconcile()
      const interval = this.state().interval
      if (!Number.isFinite(interval) || interval <= 0) throw new Error(`Invalid runtime frame interval: ${interval}`)
      if (time + 1 < this.due) return
      this.elapsed += interval
      const target = Math.round(this.elapsed)
      const ms = target - this.advanced
      this.advanced = target
      await this.advance(ms)
      this.step(ms)
      await this.reconcile()
      this.due = Math.max(this.due + interval, time)
    },
    poll() {
      this.pulse = native.timeout(() => {
        this.enqueue(() => this.reconcile()).then(() => {
          this.pulse = null
          this.schedule()
          if (this.running && !this.failed) this.poll()
        }, error => this.fail(error))
      }, 250)
    },
    acquire() {
      this.held = true
      this.cancel()
      return this.enqueue(() => this.reconcile())
    },
    release() {
      return this.enqueue(async () => {
        await this.reconcile()
        this.held = false
        this.running = true
        this.due = Math.max(this.due, native.now())
        this.schedule()
        if (this.pulse === null) this.poll()
        return this.state()
      })
    },
    publish() {
      const state = this.state()
      const key = JSON.stringify([state.session, state.mode, state.active, state.result, state.error])
      if (key === this.published) return
      this.published = key
      this.revision++
      window.__vibegameClockNotify(this.state()).catch(error => this.fail(error))
    },
    async fail(error) {
      if (this.failed) return
      this.failed = true
      this.error = String(error.stack || error)
      this.cancel()
      native.clearTimeout(this.pulse)
      this.pulse = null
      this.runtime.pause()
      console.error('Runtime clock failed:', error)
      try {
        await this.synchronizeMedia()
      } catch (mediaError) {
        this.error += `\nMedia freeze failed: ${mediaError}`
        console.error('Runtime media freeze failed:', mediaError)
      }
      this.publish()
    },
    attach(host, tree, bridge) {
      this.host = host
      this.tree = tree
      this.bridge = bridge
      this.runtime = tree.runtimeController
      host.game.loop.sleep()
      this.ready = true
    },
    state() {
      const r = this.runtime
      return { active: r.enabled, mode: r.mode, frame: r.frameCount, session: r.session,
        interval: this.host.fpsLimit > 0 ? Math.max(1000 / this.host.fpsLimit, this.displayInterval) : this.displayInterval,
        result: this.result, documentId: this.documentId, revision: this.revision, error: this.error }
    },
    synchronize() { return this.enqueue(() => this.reconcile()) },
    async reconcile() {
      this.bridge.poll(native.now())
      await this.synchronizeMedia()
      if (this.paused()) this.cancel()
      this.publish()
      return this.state()
    },
    async synchronizeMedia() {
      const paused = this.paused()
      if (paused !== this.frozen) {
        this.frozen = paused
        if (paused) {
          this.contextsToResume = live(contexts).filter(c => c.state === 'running')
          this.mediaToResume = [...new Set([...live(media), ...document.querySelectorAll('audio,video')])].filter(m => !m.paused)
          this.mediaToResume.forEach(m => m.pause())
          await Promise.all(this.contextsToResume.map(c => c.suspend()))
        } else {
          await Promise.all(this.contextsToResume.filter(c => c.state !== 'closed').map(c => c.resume()))
          await Promise.all(this.mediaToResume.map(m => m.play()))
          this.contextsToResume = []
          this.mediaToResume = []
        }
      }
    },
    step(ms) {
      for (const animation of document.getAnimations()) {
        if (animation.playState === 'running' && animation.currentTime !== null) {
          animation.currentTime += ms * animation.playbackRate
        }
      }
      this.host.game.loop.step(performance.now())
    },
    start(frames) {
      this.result = null
      this.runtime.continue(frames).then(result => { this.result = result })
    },
    command({cmd, params}) {
      const handlers = { activate: '_cmdActivate', deactivate: '_cmdDeactivate',
        pause: '_cmdPause', play: '_cmdPlay', input: '_cmdInput', key: '_cmdKey' }
      if (!(cmd in handlers)) throw new Error(`Unknown host command: ${cmd}`)
      return this.bridge[handlers[cmd]](params)
    },
  }

  for (const type of ['pointerdown', 'pointerup', 'pointermove', 'mousedown', 'mouseup', 'mousemove', 'click', 'dblclick', 'contextmenu', 'wheel', 'keydown', 'keyup', 'keypress', 'touchstart', 'touchmove', 'touchend', 'beforeinput', 'input']) {
    window.addEventListener(type, event => {
      if (!clock.runtime?.enabled || clock.dispatching) return
      event.preventDefault()
      event.stopImmediatePropagation()
    }, {capture: true, passive: false})
  }
  const gameTime = VibeGameTimers.withGlobal(window).install({
    now: Date.now(), shouldAdvanceTime: false,
    toFake: ['Date', 'performance', 'setTimeout', 'clearTimeout', 'setInterval', 'clearInterval', 'requestIdleCallback', 'cancelIdleCallback'],
  })
  window.requestAnimationFrame = callback => {
    if (typeof callback !== 'function') throw new TypeError('requestAnimationFrame requires a function')
    const interval = clock.displayInterval
    const delay = Math.max(1, Math.ceil(interval - performance.now() % interval))
    return gameTime.setTimeout(() => callback(performance.now()), delay)
  }
  window.cancelAnimationFrame = id => gameTime.clearTimeout(id)
})()
