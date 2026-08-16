/** Atlas canvas: bbox drawing, handles, mouse interaction. Dashboard version. */

import { S, COLORS, pushUndo, markSaveDirty } from '../state.js'
import { imgCoords, getLastMouse, getCanvas, isSpacePanning } from '../canvas.js'
import { resolveItemPivot } from './panel.js'

let _setStatus = null
let _updateSpriteList = null
let pivotDragChanged = false

export function init(setStatus, updateList) {
  _setStatus = setStatus
  _updateSpriteList = updateList
}

function setStatus(msg) { if (_setStatus) _setStatus(msg) }
function updateList() { if (_updateSpriteList) _updateSpriteList() }

// --- Canvas rendering ---

export function render(ctx, w, h) {
  const a = S.atlas
  if (!a.img || !a.img.complete) return

  ctx.save()
  ctx.translate(S.panX, S.panY)
  ctx.scale(S.zoom, S.zoom)

  // Checkerboard bg (dark for contrast with sprites)
  const iw = a.img.naturalWidth, ih = a.img.naturalHeight
  const sz = 10
  for (let y = 0; y < ih; y += sz) {
    for (let x = 0; x < iw; x += sz) {
      ctx.fillStyle = ((x/sz|0) + (y/sz|0)) % 2 === 0 ? '#3a3a3a' : '#2a2a2a'
      ctx.fillRect(x, y, Math.min(sz, iw-x), Math.min(sz, ih-y))
    }
  }
  ctx.drawImage(a.img, 0, 0)

  // Fixed grid modes: spritesheet frames and tileset preview.
  const gridMode = (a.sheetMode && a.frameWidth > 0 && a.frameHeight > 0)
    || (a.tilesetMode && a.tileWidth > 0 && a.tileHeight > 0)
  if (gridMode) {
    const cellW = a.tilesetMode ? a.tileWidth : a.frameWidth
    const cellH = a.tilesetMode ? a.tileHeight : a.frameHeight
    const cols = Math.floor(iw / cellW)
    const rows = Math.floor(ih / cellH)
    const lw = 1 / S.zoom

    // Grid lines
    ctx.strokeStyle = 'rgba(255,255,255,0.25)'
    ctx.lineWidth = lw
    ctx.setLineDash([])
    for (let c = 0; c <= cols; c++) {
      ctx.beginPath()
      ctx.moveTo(c * cellW, 0)
      ctx.lineTo(c * cellW, rows * cellH)
      ctx.stroke()
    }
    for (let r = 0; r <= rows; r++) {
      ctx.beginPath()
      ctx.moveTo(0, r * cellH)
      ctx.lineTo(cols * cellW, r * cellH)
      ctx.stroke()
    }

    // Selected frame highlight
    if (a.sel >= 0 && a.sel < a.bboxes.length) {
      const [bx, by, bw, bh] = a.bboxes[a.sel].bbox
      ctx.fillStyle = 'rgba(56,152,236,0.25)'
      ctx.fillRect(bx, by, bw, bh)
      ctx.strokeStyle = '#3898ec'
      ctx.lineWidth = 2 / S.zoom
      ctx.strokeRect(bx, by, bw, bh)

      // Frame index label
      const fs = Math.max(10, 12 / S.zoom)
      ctx.font = `600 ${fs}px -apple-system,sans-serif`
      const label = a.tilesetMode ? (a.bboxes[a.sel].name || `#${a.sel}`) : `#${a.sel}`
      const tw = ctx.measureText(label).width
      ctx.fillStyle = '#3898eccc'
      ctx.fillRect(bx, by - fs - 4/S.zoom, tw + 6/S.zoom, fs + 4/S.zoom)
      ctx.fillStyle = '#fff'
      ctx.fillText(label, bx + 3/S.zoom, by - 4/S.zoom)
    }

    ctx.restore()
    return
  }

  // Atlas bbox mode (original)
  a.bboxes.forEach((item, i) => {
    const [bx, by, bw, bh] = item.bbox
    const color = COLORS[i % COLORS.length]
    const isSel = i === a.sel

    ctx.fillStyle = color + (isSel ? '30' : '18')
    ctx.fillRect(bx, by, bw, bh)
    ctx.strokeStyle = color
    ctx.lineWidth = (isSel ? 2 : 1) / S.zoom
    ctx.setLineDash(isSel ? [] : [4/S.zoom, 3/S.zoom])
    ctx.strokeRect(bx, by, bw, bh)
    ctx.setLineDash([])

    // Label
    const fs = Math.max(10, 13 / S.zoom)
    ctx.font = `600 ${fs}px -apple-system,sans-serif`
    const tw = ctx.measureText(item.name).width
    ctx.fillStyle = color + 'cc'
    ctx.fillRect(bx, by - fs - 4/S.zoom, tw + 6/S.zoom, fs + 4/S.zoom)
    ctx.fillStyle = '#fff'
    ctx.fillText(item.name, bx + 3/S.zoom, by - 4/S.zoom)

    // Pivot marker (small crosshair). Selected = white-filled; unselected = bbox color.
    const { value: pv, source } = resolveItemPivot(item)
    const px = bx + bw * pv[0]
    const py = by + bh * pv[1]
    const r = (isSel ? 5 : 4) / S.zoom
    const arm = (isSel ? 7 : 5) / S.zoom
    const lw = (isSel ? 1.5 : 1) / S.zoom
    ctx.strokeStyle = isSel ? '#fff' : color
    ctx.fillStyle = isSel ? '#fff' : color + (source === 'sprite' ? 'ff' : '99')
    ctx.lineWidth = lw
    ctx.beginPath()
    ctx.arc(px, py, r, 0, Math.PI * 2)
    ctx.fill()
    ctx.stroke()
    ctx.beginPath()
    ctx.moveTo(px - arm, py); ctx.lineTo(px + arm, py)
    ctx.moveTo(px, py - arm); ctx.lineTo(px, py + arm)
    ctx.stroke()

    // Handles
    if (isSel) {
      const hs = 7 / S.zoom
      ctx.fillStyle = '#fff'
      ctx.strokeStyle = color
      ctx.lineWidth = 1.5 / S.zoom
      for (const [hx, hy] of [[bx,by],[bx+bw,by],[bx,by+bh],[bx+bw,by+bh]]) {
        ctx.fillRect(hx-hs/2, hy-hs/2, hs, hs)
        ctx.strokeRect(hx-hs/2, hy-hs/2, hs, hs)
      }
    }
  })

  ctx.restore()
}

// --- Hit testing ---

function hitTest(ix, iy) {
  const a = S.atlas

  // Fixed grid modes: click selects cell.
  const gridMode = (a.sheetMode && a.frameWidth > 0 && a.frameHeight > 0)
    || (a.tilesetMode && a.tileWidth > 0 && a.tileHeight > 0)
  if (gridMode) {
    const cellW = a.tilesetMode ? a.tileWidth : a.frameWidth
    const cellH = a.tilesetMode ? a.tileHeight : a.frameHeight
    const col = Math.floor(ix / cellW)
    const row = Math.floor(iy / cellH)
    const iw = a.img.naturalWidth, ih = a.img.naturalHeight
    const cols = Math.floor(iw / cellW)
    const rows = Math.floor(ih / cellH)
    if (col >= 0 && col < cols && row >= 0 && row < rows) {
      const idx = row * cols + col
      if (idx < a.bboxes.length) return { kind: 'cell', idx }
    }
    return { kind: 'none' }
  }

  // Atlas mode: original hit test
  const hs = 8 / S.zoom
  if (a.sel >= 0 && a.bboxes[a.sel]) {
    const [bx, by, bw, bh] = a.bboxes[a.sel].bbox
    const { value: pivot } = resolveItemPivot(a.bboxes[a.sel])
    const px = bx + bw * pivot[0]
    const py = by + bh * pivot[1]
    if (Math.hypot(ix - px, iy - py) < 10 / S.zoom) return 'pivot'
    for (const [name, hx, hy] of [['tl',bx,by],['tr',bx+bw,by],['bl',bx,by+bh],['br',bx+bw,by+bh]]) {
      if (Math.abs(ix-hx) < hs && Math.abs(iy-hy) < hs) return name
    }
  }
  for (let i = a.bboxes.length - 1; i >= 0; i--) {
    const [bx, by, bw, bh] = a.bboxes[i].bbox
    if (ix >= bx && ix <= bx+bw && iy >= by && iy <= by+bh) return 'body'
  }
  return 'draw'
}

// --- Mouse interaction ---

export function attachMouseHandlers() {
  const canvas = getCanvas()
  if (!canvas) return

  canvas.addEventListener('mousedown', e => {
    if (e.button === 1 || (e.button === 0 && e.altKey) || isSpacePanning()) return
    if (e.button !== 0) return
    const a = S.atlas
    if (!a.img) return
    const p = imgCoords(e)
    const hit = hitTest(p.x, p.y)

    // Fixed grid modes: select cell on click.
    if (a.sheetMode || a.tilesetMode) {
      if (hit.kind === 'cell') {
        a.sel = hit.idx
        S.dirty = true
        updateList()
      }
      return
    }

    // Atlas mode: original interaction
    if (hit === 'draw') {
      a.mode = 'draw'
      a.dragStart = p
      a.dragBbox = [Math.round(p.x), Math.round(p.y), 0, 0]
      a.sel = -1
      updateList()
    } else if (hit === 'body') {
      const idx = a.bboxes.length - 1 - a.bboxes.slice().reverse().findIndex((_, ri) => {
        const [bx, by, bw, bh] = a.bboxes[a.bboxes.length-1-ri].bbox
        return p.x >= bx && p.x <= bx+bw && p.y >= by && p.y <= by+bh
      })
      pushUndo()
      a.sel = idx
      a.mode = 'move'
      a.dragStart = p
      a.dragBbox = [...a.bboxes[idx].bbox]
      updateList()
    } else if (hit === 'pivot') {
      a.mode = 'pivot'
      pivotDragChanged = false
    } else {
      pushUndo()
      const idx = a.sel
      a.mode = 'resize'
      a.handle = hit
      a.dragStart = p
      a.dragBbox = [...a.bboxes[idx].bbox]
    }
    S.dirty = true
  })

  canvas.addEventListener('mousemove', e => {
    const a = S.atlas
    if (!a.img) return
    const m = getLastMouse()

    if (a.mode === 'draw' && a.dragBbox) {
      a.dragBbox = [
        Math.round(Math.min(a.dragStart.x, m.x)),
        Math.round(Math.min(a.dragStart.y, m.y)),
        Math.abs(Math.round(m.x) - a.dragStart.x),
        Math.abs(Math.round(m.y) - a.dragStart.y)
      ]
      S.dirty = true
    }
    if (a.mode === 'move' && a.sel >= 0) {
      const dx = m.x - a.dragStart.x, dy = m.y - a.dragStart.y
      a.bboxes[a.sel].bbox = [
        Math.round(a.dragBbox[0] + dx), Math.round(a.dragBbox[1] + dy),
        a.dragBbox[2], a.dragBbox[3]
      ]
      markSaveDirty()
    }
    if (a.mode === 'resize' && a.sel >= 0) {
      const ob = a.dragBbox
      const mx = Math.round(m.x), my = Math.round(m.y)
      let x=ob[0], y=ob[1], w=ob[2], h=ob[3]
      const p = e.shiftKey ? proportionalResizePoint(ob, a.handle, mx, my) : { x: mx, y: my }
      if (a.handle==='tl') { x=p.x; y=p.y; w=ob[0]+ob[2]-p.x; h=ob[1]+ob[3]-p.y }
      else if (a.handle==='tr') { y=p.y; w=p.x-ob[0]; h=ob[1]+ob[3]-p.y }
      else if (a.handle==='bl') { x=p.x; w=ob[0]+ob[2]-p.x; h=p.y-ob[1] }
      else if (a.handle==='br') { w=p.x-ob[0]; h=p.y-ob[1] }
      if (w<0) { x+=w; w=-w }; if (h<0) { y+=h; h=-h }
      a.bboxes[a.sel].bbox = [x, y, w, h]
      markSaveDirty()
    }
    if (a.mode === 'pivot' && a.sel >= 0) {
      const item = a.bboxes[a.sel]
      const [bx, by, bw, bh] = item.bbox
      if (bw > 0 && bh > 0) {
        const pivot = [clampPivot((m.x - bx) / bw), clampPivot((m.y - by) / bh)]
        const current = resolveItemPivot(item).value
        if (pivot[0] !== current[0] || pivot[1] !== current[1]) {
          if (!pivotDragChanged) pushUndo()
          pivotDragChanged = true
          item.pivot = pivot
          markSaveDirty()
        }
      }
    }

    // Cursor (skip when space-panning)
    if (a.mode === 'idle' && a.img && !isSpacePanning()) {
      const hit = hitTest(m.x, m.y)
      if (a.sheetMode || a.tilesetMode) {
        canvas.style.cursor = (hit.kind === 'cell') ? 'pointer' : 'default'
      } else {
        const cursors = { tl:'nw-resize', tr:'ne-resize', bl:'sw-resize', br:'se-resize' }
        canvas.style.cursor = hit==='draw' ? 'crosshair' : (hit==='body' ? 'move' : hit==='pivot' ? 'grab' : cursors[hit] || 'default')
      }
    }
  })

  canvas.addEventListener('mouseup', () => {
    const a = S.atlas
    const adjustedPivot = a.mode === 'pivot' && pivotDragChanged
    if (a.mode === 'draw' && a.dragBbox && a.dragBbox[2] > 2 && a.dragBbox[3] > 2) {
      pushUndo()
      const stem = a.imageKey || 'sprite'
      const name = `${stem}_c${a.bboxes.length}`
      a.bboxes.push({ name, bbox: [...a.dragBbox] })
      a.sel = a.bboxes.length - 1
      markSaveDirty()
      updateList()
      setStatus(`Added "${name}"`)
    }
    a.mode = 'idle'
    a.dragBbox = null
    pivotDragChanged = false
    if (adjustedPivot) {
      updateList()
      setStatus('Adjusted frame pivot')
    }
    S.dirty = true
  })
}

function clampPivot(value) {
  return Math.round(Math.max(0, Math.min(1, value)) * 10000) / 10000
}

function proportionalResizePoint(bbox, handle, mx, my) {
  const [x, y, w, h] = bbox
  if (w <= 0 || h <= 0) return { x: mx, y: my }
  const anchors = {
    tl: [x + w, y + h],
    tr: [x, y + h],
    bl: [x + w, y],
    br: [x, y],
  }
  const [ax, ay] = anchors[handle] || [x, y]
  const aspect = w / h
  let dx = mx - ax
  let dy = my - ay
  const sx = dx < 0 ? -1 : 1
  const sy = dy < 0 ? -1 : 1
  if (Math.abs(dx) / aspect >= Math.abs(dy)) {
    dy = sy * Math.abs(dx) / aspect
  } else {
    dx = sx * Math.abs(dy) * aspect
  }
  return { x: Math.round(ax + dx), y: Math.round(ay + dy) }
}

/** Keyboard handler - call from document-level keydown. */
export function handleKeyDown(e) {
  if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return
  const a = S.atlas
  if (a.tilesetMode) return
  if ((e.key === 'Delete' || e.key === 'Backspace') && a.sel >= 0) {
    pushUndo()
    const removed = a.bboxes.splice(a.sel, 1)[0]
    setStatus(`Deleted "${removed.name}"`)
    a.sel = -1
    markSaveDirty()
    updateList()
  }
}
