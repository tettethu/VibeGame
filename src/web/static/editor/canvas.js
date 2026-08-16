/** Shared canvas: DPR, pan/zoom, render loop. Adapted for Dashboard embedding. */

import { S } from './state.js'

let canvas = null
let carea = null
let zlabel = null
let currentRenderer = null
let loopRunning = false

/** Bind to DOM elements. Call once after the editor DOM is created. */
export function bindCanvas(canvasEl, careaEl, zlabelEl) {
  canvas = canvasEl
  carea = careaEl
  zlabel = zlabelEl
  attachEvents()
}

export function getCanvas() { return canvas }

/** Convert mouse event to image-local coordinates. */
export function imgCoords(e) {
  const r = canvas.getBoundingClientRect()
  return { x: (e.clientX - r.left - S.panX) / S.zoom, y: (e.clientY - r.top - S.panY) / S.zoom }
}

/** Fit image into view area. */
export function fitToView(img) {
  if (!carea) return
  const scale = Math.min(carea.clientWidth / img.naturalWidth, carea.clientHeight / img.naturalHeight, 2)
  S.zoom = Math.max(0.1, Math.min(scale, 4))
  S.panX = (carea.clientWidth - img.naturalWidth * S.zoom) / 2
  S.panY = (carea.clientHeight - img.naturalHeight * S.zoom) / 2
  S.dirty = true
  updateZoomLabel()
}

export function setRenderer(fn) { currentRenderer = fn }

export function updateZoomLabel() {
  if (zlabel) zlabel.textContent = Math.round(S.zoom * 100) + '%'
}

function render() {
  if (!canvas || !carea) return
  const dpr = window.devicePixelRatio || 1
  const w = carea.clientWidth
  const h = carea.clientHeight
  canvas.width = w * dpr
  canvas.height = h * dpr
  canvas.style.width = w + 'px'
  canvas.style.height = h + 'px'
  const ctx = canvas.getContext('2d')
  ctx.scale(dpr, dpr)
  ctx.clearRect(0, 0, w, h)
  if (currentRenderer) currentRenderer(ctx, w, h)
}

export function startLoop() {
  if (loopRunning) return
  loopRunning = true
  ;(function loop() {
    if (!loopRunning) return
    if (S.dirty) { S.dirty = false; render() }
    requestAnimationFrame(loop)
  })()
}

export function stopLoop() {
  loopRunning = false
}

let lastMouse = { x: 0, y: 0 }
let spaceHeld = false

export function isSpacePanning() { return spaceHeld }

function attachEvents() {
  if (!canvas) return

  document.addEventListener('keydown', e => {
    if (e.code === 'Space' && !e.repeat && e.target.tagName !== 'INPUT' && e.target.tagName !== 'TEXTAREA') {
      spaceHeld = true
      if (canvas) canvas.style.cursor = 'grab'
      e.preventDefault()
    }
  })

  document.addEventListener('keyup', e => {
    if (e.code === 'Space') {
      spaceHeld = false
      if (canvas && !S._panState) canvas.style.cursor = ''
    }
  })

  canvas.addEventListener('mousedown', e => {
    if (e.button === 1 || (e.button === 0 && e.altKey) || (e.button === 0 && spaceHeld)) {
      S._panState = { mode: 'pan', x: e.clientX, y: e.clientY, px: S.panX, py: S.panY }
      if (canvas) canvas.style.cursor = 'grabbing'
      e.preventDefault()
    }
  })

  canvas.addEventListener('mousemove', e => {
    lastMouse = imgCoords(e)
    if (S._panState?.mode === 'pan') {
      S.panX = S._panState.px + (e.clientX - S._panState.x)
      S.panY = S._panState.py + (e.clientY - S._panState.y)
      S.dirty = true
    }
  })

  canvas.addEventListener('mouseup', () => {
    if (S._panState?.mode === 'pan') {
      S._panState = null
      if (canvas) canvas.style.cursor = spaceHeld ? 'grab' : ''
    }
  })

  canvas.addEventListener('wheel', e => {
    e.preventDefault()
    const factor = e.deltaY < 0 ? 1.15 : 1 / 1.15
    const r = canvas.getBoundingClientRect()
    const mx = e.clientX - r.left, my = e.clientY - r.top
    const newZoom = Math.max(0.05, Math.min(S.zoom * factor, 20))
    S.panX = mx - (mx - S.panX) * (newZoom / S.zoom)
    S.panY = my - (my - S.panY) * (newZoom / S.zoom)
    S.zoom = newZoom
    S.dirty = true
    updateZoomLabel()
  }, { passive: false })
}

export function getLastMouse() { return lastMouse }
