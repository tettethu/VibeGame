"""Deliver control commands and queued input to the browser clock."""

import json
import logging
import time
from pathlib import Path
from queue import Empty, Queue

from playwright.sync_api import Page

from cli.run_bot import execute_pointer_action, _normalize_point, _normalize_drag

logger = logging.getLogger(__name__)


class RuntimeClock:
    def __init__(self, page: Page) -> None:
        logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
        self.page = page
        page.on('pageerror', lambda error: logger.error('Runtime page error: %s', error))
        self.inputs: list[tuple[str, dict]] = []
        self.pending: Queue | None = None
        self.session: int | None = None
        self.blocked: bool | None = None
        self.ready = False
        self.document_id: str | None = None
        self.revision = -1
        self.notifications = Queue()
        page.expose_binding('__vibegameClockNotify', lambda source, state: self.notifications.put(state))
        script = Path(__file__).resolve().parents[1] / 'engine' / 'RuntimeClock.js'
        logger.info('Installing runtime clock hooks: %s', script)
        self.interval = page.evaluate("""() => new Promise(resolve => {
          const samples = []
          let previous = null
          function frame(time) {
            if (previous !== null) samples.push(time - previous)
            previous = time
            if (samples.length === 8) resolve(samples.sort((a, b) => a - b)[4])
            else requestAnimationFrame(frame)
          }
          requestAnimationFrame(frame)
        })""")
        vendor = script.parent / 'vendor' / 'fake-timers.js'
        logger.info('Loading pinned runtime timer library: %s', vendor)
        source = vendor.read_text() + '\n' + script.read_text()
        source += f'\nwindow.__vibegameClock.configure({json.dumps(self.interval)});'
        page.add_init_script(script='if (window === window.top) {\n' + source + '\n}')
        self.cdp = page.context.new_cdp_session(page)
        self.cdp.send('Animation.enable')
        self.cdp.send('Animation.setPlaybackRate', {'playbackRate': 0})
        self.cdp.send('Page.enable')
        self.cdp.on('Page.frameNavigated', self._navigated)

    def _advance_time(self, milliseconds: int) -> None:
        if milliseconds <= 0:
            raise ValueError('Time advance must be positive')
        self.page.evaluate('ms => window.__vibegameClock.advance(ms)', milliseconds)

    def _navigated(self, event) -> None:
        # Same-document URL changes do not replace the runtime clock.
        if 'parentId' not in event['frame']:
            self.ready = False
            self.inputs.clear()
            self.session = None
            self.blocked = None
            self.document_id = None
            self.revision = -1
            if self.pending is not None:
                self.pending.put({'error': 'Page navigated during continue'})
                self.pending = None

    def load(self, url: str) -> None:
        logger.info('Loading runtime page: %s', url.split('?')[0])
        self.page.goto(url, wait_until='domcontentloaded')
        self.wait_ready()

    def wait_ready(self) -> None:
        deadline = time.monotonic() + 30
        while True:
            state = self.page.evaluate('({engine: Boolean(window.__vibegame_ready), clock: Boolean(window.__vibegameClock?.ready)})')
            if state['engine'] and state['clock']:
                break
            if state['engine']:
                raise RuntimeError('Project engine lacks runtime clock support. Update the project engine from the same VibeGame version as the runtime host.')
            if time.monotonic() >= deadline:
                raise TimeoutError(f'Runtime clock initialization did not complete: {state}')
            self._advance_time(16)
            self.page.wait_for_timeout(5)
        self.cdp.send('Animation.setPlaybackRate', {'playbackRate': 0})
        self.ready = True
        state = self.page.evaluate('window.__vibegameClock.release()')
        self.document_id = state['documentId']
        self._accept_state(state)
        logger.info('Runtime clock ready')

    def _sync(self) -> dict:
        state = self.page.evaluate('window.__vibegameClock.synchronize()')
        return self._accept_state(state)

    def _accept_state(self, state: dict) -> dict:
        if state['revision'] < self.revision:
            return state
        self.revision = state['revision']
        if state['error']:
            raise RuntimeError(state['error'])
        if self.session != state['session']:
            self.inputs.clear()
            self.session = state['session']
        blocked = state['active']
        if blocked != self.blocked:
            self.cdp.send('Input.setIgnoreInputEvents', {'ignore': blocked})
            self.blocked = blocked
        if self.pending is not None and state['result'] is not None:
            self.pending.put(state['result'])
            self.pending = None
        return state

    def command(self, cmd: str, params: dict, response: Queue) -> None:
        logger.info('Runtime command: %s %s', cmd, params)
        if not self.ready:
            self.wait_ready()
        state = self._accept_state(self.page.evaluate('window.__vibegameClock.acquire()'))
        try:
            try:
                result = self._command(cmd, params, response, state)
            finally:
                self._accept_state(self.page.evaluate('window.__vibegameClock.release()'))
        except Exception:
            if self.pending is response:
                self.pending = None
            raise
        if result is not None:
            response.put(result)

    def _command(self, cmd: str, params: dict, response: Queue, state: dict) -> dict | None:
        if cmd in {'input', 'key', 'click', 'mousemove', 'drag'}:
            self._validate_input(cmd, params)
            if state['active'] and state['mode'] == 'paused':
                self.inputs.append((cmd, params))
                return {'status': 'queued'}
            self._input(cmd, params)
            return {'status': 'ok'}
        if cmd == 'continue':
            frames = params.get('frames', 60)
            if not isinstance(frames, int) or isinstance(frames, bool) or frames <= 0:
                raise ValueError('frames must be a positive integer')
            if not state['active']:
                raise ValueError('No runtime session. Call activate first.')
            if self.pending is not None:
                raise ValueError('A continue command is already in progress')
            self.page.evaluate('(frames) => { window.__vibegameClock.start(frames) }', frames)
            try:
                self._sync()
                self._flush()
                self._sync()
            except Exception:
                self.page.evaluate('window.__vibegameClock.runtime.pause()')
                self._sync()
                raise
            self.pending = response
            return
        result = self.page.evaluate('(request) => window.__vibegameClock.command(request)', {'cmd': cmd, 'params': params})
        if 'error' in result:
            raise ValueError(result['error'])
        if cmd == 'play':
            try:
                self._sync()
                self._flush()
            except Exception:
                self.page.evaluate('window.__vibegameClock.runtime.pause()')
                self._sync()
                raise
        self._sync()
        return result

    def _validate_input(self, kind: str, params: dict) -> None:
        if kind in {'click', 'mousemove'}:
            _normalize_point(params)
        elif kind == 'drag':
            _normalize_drag(params)
        elif kind == 'input':
            if not params.get('action'):
                raise ValueError('Missing action field')
        elif kind == 'key':
            valid = self.page.evaluate('p => typeof p.key === "string" && p.key in window.__vibegameClock.bridge.constructor._CODE_TO_KEY && ["press", "down", "up"].includes(p.type ?? "press")', params)
            if not valid:
                raise ValueError('Invalid key or type. Use a DOM KeyboardEvent.code and press, down, or up.')

    def _input(self, kind: str, params: dict) -> None:
        self.cdp.send('Input.setIgnoreInputEvents', {'ignore': False})
        self.page.evaluate('window.__vibegameClock.dispatching = true')
        try:
            if kind in {'click', 'mousemove', 'drag'}:
                execute_pointer_action(self.page, kind, params)
            else:
                result = self.page.evaluate('request => window.__vibegameClock.command(request)', {'cmd': kind, 'params': params})
                if 'error' in result:
                    raise ValueError(result['error'])
        finally:
            self.page.evaluate('window.__vibegameClock.dispatching = false')
            self.cdp.send('Input.setIgnoreInputEvents', {'ignore': self.blocked})

    def _flush(self) -> None:
        queued, self.inputs = self.inputs, []
        for kind, params in queued:
            self._input(kind, params)

    def tick(self) -> float:
        if not self.ready:
            self.wait_ready()
        while True:
            try:
                state = self.notifications.get_nowait()
            except Empty:
                return 0.05
            if state['documentId'] == self.document_id:
                self._accept_state(state)

    def abort(self, error: Exception) -> None:
        logger.exception('Runtime clock operation failed: %s', error)
        self.inputs.clear()
        if self.pending is not None:
            self.pending.put({'error': str(error)})
            self.pending = None
        if self.ready:
            self.page.evaluate('window.__vibegameClock.runtime.pause()')
            self._sync()

    def close(self) -> None:
        self.inputs.clear()
        if self.pending is not None:
            self.pending.put({'error': 'Runtime closed during continue'})
            self.pending = None
