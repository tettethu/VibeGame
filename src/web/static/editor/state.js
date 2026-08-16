/** Shared reactive state for the atlas editor (Dashboard-embedded version). */

export const S = {
  dirty: true,
  saveDirty: false,
  zoom: 1, panX: 0, panY: 0,

  atlas: {
    folder: '', manifest: {}, imageKey: '', imageFile: '',
    img: null, bboxes: [], sel: -1,
    mode: 'idle', dragStart: null, dragBbox: null, handle: '',
    thumbs: {}, originalBboxes: [],
    sheetMode: false, frameWidth: 0, frameHeight: 0,
    tilesetMode: false, tileWidth: 0, tileHeight: 0, tilesetTiles: {},
    animation: { playing: true, pausedFrameIndex: 0 },
  },

  _undoStack: [],
}

let saveDirtyListener = null

export function setSaveDirtyListener(listener) {
  saveDirtyListener = typeof listener === 'function' ? listener : null
}

export function markSaveDirty() {
  S.dirty = true
  S.saveDirty = true
  if (saveDirtyListener) saveDirtyListener(S.saveDirty)
}

export function clearSaveDirty() {
  S.saveDirty = false
  if (saveDirtyListener) saveDirtyListener(S.saveDirty)
}

const MAX_UNDO = 50

/** Snapshot current bboxes onto the undo stack. Call before any mutation. */
export function pushUndo() {
  const snap = S.atlas.bboxes.map(cloneBBoxItem)
  S._undoStack.push({ bboxes: snap, sel: S.atlas.sel })
  if (S._undoStack.length > MAX_UNDO) S._undoStack.shift()
}

/** Restore last snapshot. Returns true if something was restored. */
export function popUndo() {
  const entry = S._undoStack.pop()
  if (!entry) return false
  S.atlas.bboxes = entry.bboxes
  S.atlas.sel = entry.sel
  S.dirty = true
  return true
}

export function clearUndo() {
  S._undoStack = []
}

function cloneBBoxItem(item) {
  const clone = { ...item, bbox: [...item.bbox] }
  if (Array.isArray(item.pivot)) clone.pivot = [...item.pivot]
  return clone
}

export const COLORS = ['#c96442','#4a8a4a','#3898ec','#d97757','#6366f1','#ec4899','#f59e0b','#06b6d4']
