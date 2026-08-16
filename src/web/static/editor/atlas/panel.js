/** Atlas right panel: sprite list with thumbnails. Dashboard version. */

import { S, COLORS, pushUndo, markSaveDirty } from '../state.js'

let slistEl = null
let headEl = null

export function bindPanel(slist, head) {
  slistEl = slist
  headEl = head
}

function formatCoord(n) {
  return Number.isInteger(n) ? String(n) : n.toFixed(2).replace(/\.?0+$/, '')
}

/**
 * Resolve effective pivot for a sprite item:
 *   sprite.pivot > manifest group.pivot > [0.5, 1]
 * Returns { value: [x, y], source: 'sprite' | 'group' | 'default' }.
 */
export function resolveItemPivot(item) {
  if (Array.isArray(item?.pivot) && item.pivot.length === 2) {
    return { value: item.pivot, source: 'sprite' }
  }
  const groupPivot = S.atlas.manifest?.[S.atlas.imageKey]?.pivot
  if (Array.isArray(groupPivot) && groupPivot.length === 2) {
    return { value: groupPivot, source: 'group' }
  }
  return { value: [0.5, 1], source: 'default' }
}

export function updateSpriteList() {
  if (!slistEl) return
  slistEl.innerHTML = ''
  const a = S.atlas
  const label = a.tilesetMode ? `Tiles (${a.bboxes.length})` : a.sheetMode ? `Frames (${a.bboxes.length})` : `Sprites (${a.bboxes.length})`
  if (headEl) headEl.textContent = label

  a.bboxes.forEach((item, i) => {
    const div = document.createElement('div')
    div.className = 'ae-sitem' + (i === a.sel ? ' sel' : '')
    div.onclick = () => { a.sel = i; S.dirty = true; updateSpriteList() }

    const thumb = document.createElement('canvas')
    thumb.className = 'ae-sthumb'
    thumb.width = 36; thumb.height = 36
    const tctx = thumb.getContext('2d')
    if (a.img) {
      const [bx, by, bw, bh] = item.bbox
      const s = Math.min(34/bw, 34/bh, 4)
      const dw = bw*s, dh = bh*s
      tctx.imageSmoothingEnabled = false
      tctx.drawImage(a.img, bx, by, bw, bh, (36-dw)/2, (36-dh)/2, dw, dh)
    }

    const info = document.createElement('div')
    info.className = 'ae-sinfo'
    const nameEl = document.createElement('div')
    nameEl.className = 'ae-sname'
    if (a.tilesetMode) {
      nameEl.textContent = item.name || `#${i}`
    } else if (a.sheetMode) {
      nameEl.textContent = `#${i}`
    } else {
      nameEl.textContent = item.name
      nameEl.ondblclick = (e) => { e.stopPropagation(); startRename(i, nameEl) }
    }
    const boxEl = document.createElement('div')
    boxEl.className = 'ae-sbox'
    if (a.tilesetMode) {
      const tileName = item.tileName ? ` · ${item.tileName}` : ''
      boxEl.textContent = `index ${item.index}${tileName}`
      boxEl.title = `tileset index ${item.index}`
    } else {
      const sizeText = `${item.bbox[2]}x${item.bbox[3]}`
      const { value: pv, source } = resolveItemPivot(item)
      const inheritMark = source === 'sprite' ? '' : '*'
      boxEl.textContent = `${sizeText} · pivot ${formatCoord(pv[0])},${formatCoord(pv[1])}${inheritMark}`
      boxEl.title = source === 'sprite'
        ? 'pivot: sprite-level (explicit)'
        : source === 'group'
          ? 'pivot: inherited from manifest group'
          : 'pivot: engine default [0.5, 1]'
    }

    info.appendChild(nameEl)
    info.appendChild(boxEl)
    if (i === a.sel && !a.tilesetMode && !a.sheetMode) {
      info.appendChild(pivotInputs(item, i))
    }
    div.appendChild(thumb)
    div.appendChild(info)
    slistEl.appendChild(div)
  })
}

function pivotInputs(item, index) {
  const { value } = resolveItemPivot(item)
  const controls = document.createElement('div')
  controls.className = 'ae-pivot-edit'
  controls.onclick = event => event.stopPropagation()

  for (const [axis, label] of [[0, 'X'], [1, 'Y']]) {
    const field = document.createElement('label')
    field.textContent = label
    const input = document.createElement('input')
    input.type = 'number'
    input.min = '0'
    input.max = '1'
    input.step = '0.01'
    input.value = formatCoord(value[axis])
    input.onchange = () => commitPivotAxis(index, axis, input)
    field.appendChild(input)
    controls.appendChild(field)
  }
  return controls
}

function commitPivotAxis(index, axis, input) {
  const item = S.atlas.bboxes[index]
  if (input.value.trim() === '') {
    updateSpriteList()
    return
  }
  const value = Number(input.value)
  if (!item || !Number.isFinite(value) || value < 0 || value > 1) {
    updateSpriteList()
    return
  }
  const current = [...resolveItemPivot(item).value]
  if (current[axis] === value) return
  pushUndo()
  current[axis] = value
  item.pivot = current
  markSaveDirty()
  updateSpriteList()
}

function startRename(idx, el) {
  const a = S.atlas
  const input = document.createElement('input')
  input.value = a.bboxes[idx].name
  input.onblur = () => {
    const v = input.value.trim()
    if (v && v !== a.bboxes[idx].name) { pushUndo(); a.bboxes[idx].name = v; markSaveDirty() }
    updateSpriteList()
    S.dirty = true
  }
  input.onkeydown = e => {
    if (e.key==='Enter') input.blur()
    if (e.key==='Escape') { input.value=a.bboxes[idx].name; input.blur() }
  }
  el.textContent = ''
  el.appendChild(input)
  input.focus()
  input.select()
}

export function clearBboxes() {
  pushUndo()
  S.atlas.bboxes = []
  S.atlas.sel = -1
  markSaveDirty()
  updateSpriteList()
}
