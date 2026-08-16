/**
 * Dashboard bridge: integrates the atlas editor into the Dashboard assets view.
 * Manages file tree, browse/edit mode switching, and editor lifecycle.
 */

import { S, pushUndo, popUndo, clearUndo, markSaveDirty, clearSaveDirty, setSaveDirtyListener } from './state.js'
import * as api from './api.js'
import * as canvas from './canvas.js'
import * as atlasCanvas from './atlas/canvas.js'
import { updateSpriteList, clearBboxes, bindPanel } from './atlas/panel.js'
import { detectSprites } from './atlas/auto-detect.js'

const COLLAPSED_DEFAULT = new Set(['artifacts', 'decomposed', 'cut', 'generated', 'concepts'])

let assetTree = null
let currentFolder = 'assets'
let editorActive = false
let currentAssetPath = null
let onStatusChange = null
let onSelect = null
let keyHandler = null
let initialized = false
let animationFrameId = 0
let animationPreviewStartedAt = 0
let atlasLoadToken = 0
const folderManifestCache = new Map()
const PREVIEW_FRAME_MS = 100

// DOM references set during init
let sidebarBody = null
let panelBody = null

// Cached DOM snapshots for fast restore
let cachedSidebarHTML = ''
let cachedPanelHTML = ''

/** Initialize or restore the editor bridge. */
export async function init(sidebarEl, panelEl, statusFn, options = {}) {
  sidebarBody = sidebarEl
  panelBody = panelEl
  onStatusChange = statusFn
  onSelect = options.onSelect || null
  setSaveDirtyListener(updateSaveButton)

  if (initialized) {
    // Restore cached DOM
    sidebarBody.innerHTML = cachedSidebarHTML
    panelBody.innerHTML = cachedPanelHTML
    reattachHandlers()
    if (editorActive) resumeEditor()
    if (currentAssetPath && onSelect) onSelect(currentAssetPath)
    return
  }

  try {
    assetTree = await api.fetchAssetTree()
  } catch {
    assetTree = { name: 'assets', type: 'folder', path: 'assets', children: [] }
  }

  renderFileTree()
  if (options.initialPath) {
    await openEditor(options.initialPath, false)
    const activeItem = [...sidebarBody.querySelectorAll('.at-file')]
      .find(item => item.dataset.path === options.initialPath)
    if (activeItem) setActiveTreeItem(activeItem)
  } else {
    await browseFolder('assets')
  }
  initialized = true
}

/** Pause when leaving Assets view. Caches DOM for fast restore. */
export function destroy() {
  // Cache current DOM before it gets replaced
  if (sidebarBody) cachedSidebarHTML = sidebarBody.innerHTML
  if (panelBody) cachedPanelHTML = panelBody.innerHTML
  canvas.stopLoop()
  stopAnimationPreview()
  if (keyHandler) {
    document.removeEventListener('keydown', keyHandler)
    keyHandler = null
  }
}

/** Re-attach click handlers to restored sidebar DOM. */
function reattachHandlers() {
  if (!sidebarBody) return
  sidebarBody.querySelectorAll('.at-folder').forEach(el => {
    const nameEl = el.querySelector('.at-folder-name')
    const arrowEl = el.querySelector('.at-arrow')
    const body = el.nextElementSibling
    if (!nameEl || !body) return
    const path = nameEl.dataset.path
    if (arrowEl) arrowEl.onclick = (e) => {
      e.stopPropagation()
      const isCollapsed = body.style.display === 'none'
      body.style.display = isCollapsed ? '' : 'none'
      arrowEl.textContent = isCollapsed ? '\u25be' : '\u25b8'
    }
    if (path) nameEl.onclick = (e) => {
      e.stopPropagation()
      if (body.style.display === 'none') {
        body.style.display = ''
        if (arrowEl) arrowEl.textContent = '\u25be'
      }
      browseFolder(path)
      setActiveTreeItem(el)
    }
  })
  sidebarBody.querySelectorAll('.at-file').forEach(el => {
    const path = el.dataset.path
    if (path) el.onclick = () => { openEditor(path); setActiveTreeItem(el) }
  })

  // Re-attach browse panel handlers
  if (panelBody && !editorActive) {
    panelBody.querySelectorAll('.at-folder-card').forEach(el => {
      el.onclick = () => browseFolder(el.dataset.path)
    })
    panelBody.querySelectorAll('.at-file-card').forEach(el => {
      el.onclick = () => openEditor(el.dataset.path)
    })
    panelBody.querySelectorAll('.at-bc-item').forEach(el => {
      el.onclick = () => browseFolder(el.dataset.path)
    })
    setupTilesetPreviewCards()
  }
}

/** Resume editor canvas after restore. */
function resumeEditor() {
  const canvasEl = document.getElementById('at-canvas')
  const careaEl = document.getElementById('at-carea')
  const zlabelEl = document.getElementById('at-zlabel')
  if (!canvasEl || !careaEl) { editorActive = false; return }

  canvas.bindCanvas(canvasEl, careaEl, zlabelEl)
  const slistEl = document.getElementById('at-slist')
  const headEl = document.getElementById('at-sprite-count')
  bindPanel(slistEl, headEl)

  atlasCanvas.init(setStatus, updateSpriteList)
  atlasCanvas.attachMouseHandlers()
  canvas.setRenderer(atlasCanvas.render)
  canvas.startLoop()
  S.dirty = true
  updateSaveButton()

  keyHandler = (e) => {
    if ((e.metaKey || e.ctrlKey) && e.key === 'z' && !e.shiftKey) {
      e.preventDefault()
      if (popUndo()) {
        markAtlasDirty()
        updateSpriteList()
      }
      return
    }
    atlasCanvas.handleKeyDown(e)
  }
  document.addEventListener('keydown', keyHandler)

  // Re-attach toolbar buttons
  const folderPath = currentAssetPath?.substring(0, currentAssetPath.lastIndexOf('/'))
  const backBtn = document.getElementById('at-btn-back')
  if (backBtn && folderPath) backBtn.onclick = () => browseFolder(folderPath)
  const saveBtn = document.getElementById('at-btn-save')
  if (saveBtn) saveBtn.onclick = save
  const revertBtn = document.getElementById('at-btn-revert')
  if (revertBtn) revertBtn.onclick = revert
  const detectBtn = document.getElementById('at-btn-detect')
  if (detectBtn) detectBtn.onclick = autoDetect
  const clearBtn = document.getElementById('at-clear-btn')
  if (clearBtn) clearBtn.onclick = clearSprites
  bindAnimationPanel()
  startAnimationPreview()
}

// ===================== FILE TREE =====================

function renderFileTree() {
  if (!sidebarBody || !assetTree) return
  sidebarBody.innerHTML = ''
  renderTreeNode(assetTree, sidebarBody, 0)
}

function renderTreeNode(node, container, depth) {
  const children = node.children || []
  const folders = children.filter(c => c.type === 'folder')
  const files = children.filter(c => c.type === 'file')

  if (depth === 0) {
    // Root level: render children directly
    for (const f of files) renderFileItem(f, container, 0)
    for (const sub of folders) renderFolderItem(sub, container, 0)
    return
  }

  for (const f of files) renderFileItem(f, container, depth)
  for (const sub of folders) renderFolderItem(sub, container, depth)
}

function renderFolderItem(node, container, depth) {
  const children = node.children || []
  const isLazy = node.lazy === true
  if (children.length === 0 && !isLazy) return
  const collapsed = COLLAPSED_DEFAULT.has(node.name)

  const hd = document.createElement('div')
  hd.className = 'at-folder'
  hd.style.paddingLeft = (depth * 14 + 12) + 'px'

  const arrow = document.createElement('span')
  arrow.className = 'at-arrow'
  arrow.textContent = collapsed ? '\u25b8' : '\u25be'

  const label = document.createElement('span')
  label.className = 'at-folder-name'
  label.textContent = node.name
  label.dataset.path = node.path

  hd.appendChild(arrow)
  hd.appendChild(label)
  container.appendChild(hd)

  const body = document.createElement('div')
  body.style.display = collapsed ? 'none' : ''
  container.appendChild(body)

  let loaded = !isLazy

  // Click arrow: toggle expand/collapse (lazy load on first expand)
  arrow.onclick = async (e) => {
    e.stopPropagation()
    const isCollapsed = body.style.display === 'none'
    if (isCollapsed && !loaded) {
      arrow.textContent = '...'
      try {
        const subtree = await api.fetchAssetSubtree(node.path)
        node.children = subtree.children || []
        loaded = true
        const folders = node.children.filter(c => c.type === 'folder')
        const files = node.children.filter(c => c.type === 'file')
        for (const f of files) renderFileItem(f, body, depth + 1)
        for (const sub of folders) renderFolderItem(sub, body, depth + 1)
      } catch {
        arrow.textContent = '\u25b8'
        return
      }
    }
    body.style.display = isCollapsed ? '' : 'none'
    arrow.textContent = isCollapsed ? '\u25be' : '\u25b8'
  }

  // Click folder name: browse this folder
  label.onclick = async (e) => {
    e.stopPropagation()
    // Also expand if collapsed (lazy load if needed)
    if (body.style.display === 'none') {
      if (!loaded) {
        arrow.textContent = '...'
        try {
          const subtree = await api.fetchAssetSubtree(node.path)
          node.children = subtree.children || []
          loaded = true
          const folders = node.children.filter(c => c.type === 'folder')
          const files = node.children.filter(c => c.type === 'file')
          for (const f of files) renderFileItem(f, body, depth + 1)
          for (const sub of folders) renderFolderItem(sub, body, depth + 1)
        } catch { /* fall through */ }
      }
      body.style.display = ''
      arrow.textContent = '\u25be'
    }
    browseFolder(node.path)
    setActiveTreeItem(hd)
  }

  if (loaded) {
    const folders = children.filter(c => c.type === 'folder')
    const files = children.filter(c => c.type === 'file')
    for (const f of files) renderFileItem(f, body, depth + 1)
    for (const sub of folders) renderFolderItem(sub, body, depth + 1)
  }
}

function renderFileItem(f, container, depth) {
  const el = document.createElement('div')
  el.className = 'at-file'
  el.style.paddingLeft = (depth * 14 + 26) + 'px'

  const dot = document.createElement('span')
  dot.className = 'at-file-dot'
  const ext = f.name.split('.').pop().toLowerCase()
  dot.style.background = { png:'#4a8a4a', jpg:'#3898ec', jpeg:'#3898ec', gif:'#d97757', webp:'#6366f1', svg:'#c96442' }[ext] || '#87867f'

  const name = document.createElement('span')
  name.textContent = f.name

  el.appendChild(dot)
  el.appendChild(name)
  el.dataset.path = f.path
  container.appendChild(el)

  el.onclick = () => {
    openEditor(f.path)
    setActiveTreeItem(el)
  }
}

function setActiveTreeItem(el) {
  if (!sidebarBody) return
  sidebarBody.querySelectorAll('.at-file, .at-folder').forEach(e => e.classList.remove('active'))
  el.classList.add('active')
}

// ===================== BROWSE MODE =====================

async function browseFolder(folderPath, notifySelection = true) {
  if (editorActive) exitEditor()
  if (notifySelection && onSelect) onSelect('')
  currentFolder = folderPath

  let node = findNode(assetTree, folderPath)
  // Lazy-load subtree if needed
  if (node && node.lazy && (!node.children || node.children.length === 0)) {
    try {
      const subtree = await api.fetchAssetSubtree(folderPath)
      node.children = subtree.children || []
      node.lazy = false
    } catch { /* show whatever we have */ }
  }
  if (!node) {
    panelBody.innerHTML = `<div style="padding:2rem;color:var(--stone)">Folder not found</div>`
    return
  }

  const children = node.children || []
  const folders = children.filter(c => c.type === 'folder')
  const files = children.filter(c => c.type === 'file')

  // Breadcrumb
  const parts = folderPath.split('/')
  const breadcrumb = parts.map((p, i) => {
    const path = parts.slice(0, i + 1).join('/')
    return `<span class="at-bc-item" data-path="${esc(path)}">${esc(p)}</span>`
  }).join('<span class="at-bc-sep">/</span>')

  let html = `<div class="at-browse">
    <div class="at-bc">${breadcrumb}</div>
    <div class="card-grid" id="at-grid">`

  // Subfolder cards
  for (const f of folders) {
    const count = countFiles(f)
    html += `<div class="card-item at-folder-card" data-path="${esc(f.path)}">
      <div class="card-thumb">
        <span class="card-placeholder">
          <svg width="40" height="40" viewBox="0 0 40 40" fill="none" stroke="var(--stone)" stroke-width="1.2">
            <path d="M6 12h28v20H6z"/><path d="M6 12l4-6h10l4 6"/>
          </svg>
        </span>
      </div>
      <div class="card-body">
        <div class="card-name">${esc(f.name)}</div>
        <div class="card-meta">${count} file${count !== 1 ? 's' : ''}</div>
      </div>
    </div>`
  }

  // File cards
  for (const f of files) {
    const isImage = /\.(png|jpg|jpeg|gif|webp|svg)$/i.test(f.name)
    const tileset = isImage ? await findTilesetInfoForFile(f.path) : null
    const thumb = isImage
      ? tileset
        ? `<span class="tileset-preview" data-tile-width="${tileset.tileWidth}" data-tile-height="${tileset.tileHeight}">
            <img src="/${f.path}" loading="lazy" alt="${esc(f.name)}">
          </span>`
        : `<img src="/${f.path}" loading="lazy" alt="${esc(f.name)}">`
      : `<span class="card-placeholder">?</span>`
    const meta = tileset
      ? `tileset · ${tileset.tileWidth}x${tileset.tileHeight}`
      : formatSize(f.size)
    html += `<div class="card-item at-file-card${tileset ? ' at-tileset-card' : ''}" data-path="${esc(f.path)}">
      <div class="card-thumb">${thumb}</div>
      <div class="card-body">
        <div class="card-name">${esc(f.name)}</div>
        <div class="card-meta">${esc(meta)}</div>
      </div>
    </div>`
  }

  if (!folders.length && !files.length) {
    html += `<div style="color:var(--stone);font-size:0.875rem;grid-column:1/-1">Empty folder</div>`
  }

  html += '</div></div>'
  panelBody.innerHTML = html

  // Attach click handlers
  panelBody.querySelectorAll('.at-folder-card').forEach(el => {
    el.onclick = () => browseFolder(el.dataset.path)
  })
  panelBody.querySelectorAll('.at-file-card').forEach(el => {
    el.onclick = () => openEditor(el.dataset.path)
  })
  panelBody.querySelectorAll('.at-bc-item').forEach(el => {
    el.onclick = () => browseFolder(el.dataset.path)
  })
  setupTilesetPreviewCards()
}

// ===================== EDITOR MODE =====================

async function openEditor(path, notifySelection = true) {
  currentAssetPath = path
  if (notifySelection && onSelect) onSelect(path)
  editorActive = true

  // Build editor DOM
  const folderPath = path.substring(0, path.lastIndexOf('/'))
  const parts = path.split('/')
  const breadcrumb = parts.map((p, i) => {
    const bp = parts.slice(0, i + 1).join('/')
    return `<span class="at-bc-item" data-path="${esc(bp)}">${esc(p)}</span>`
  }).join('<span class="at-bc-sep">/</span>')

  panelBody.innerHTML = `
    <div class="at-editor">
      <div class="at-toolbar">
        <div class="at-bc">${breadcrumb}</div>
        <div class="at-toolbar-actions">
          <button class="at-btn" id="at-btn-back">Back</button>
          <button class="at-btn" id="at-btn-revert">Revert</button>
          <button class="at-btn" id="at-btn-detect">Auto-Detect</button>
          <button class="at-btn at-btn-primary" id="at-btn-save" disabled>Save</button>
        </div>
      </div>
      <div class="at-editor-body">
        <div class="at-stage">
          <div class="at-canvas-area" id="at-carea">
            <canvas id="at-canvas"></canvas>
            <div class="at-zoom" id="at-zlabel">100%</div>
          </div>
          <div class="at-anim-panel" id="at-anim-panel"></div>
        </div>
        <div class="at-rpanel">
          <div class="at-rpanel-head">
            <span id="at-sprite-count">Sprites (0)</span>
            <button class="at-btn" style="font-size:0.6875rem;padding:1px 6px" id="at-clear-btn">Clear</button>
          </div>
          <div class="at-rpanel-body" id="at-slist"></div>
        </div>
      </div>
    </div>`

  // Bind canvas
  const canvasEl = document.getElementById('at-canvas')
  const careaEl = document.getElementById('at-carea')
  const zlabelEl = document.getElementById('at-zlabel')
  canvas.bindCanvas(canvasEl, careaEl, zlabelEl)

  // Bind panel
  const slistEl = document.getElementById('at-slist')
  const headEl = document.getElementById('at-sprite-count')
  bindPanel(slistEl, headEl)

  // Init atlas canvas interactions
  atlasCanvas.init(setStatus, updateSpriteList)
  atlasCanvas.attachMouseHandlers()
  canvas.setRenderer(atlasCanvas.render)
  canvas.startLoop()

  // Keyboard handler
  keyHandler = (e) => {
    if ((e.metaKey || e.ctrlKey) && e.key === 'z' && !e.shiftKey) {
      e.preventDefault()
      if (popUndo()) {
        markAtlasDirty()
        updateSpriteList()
      }
      return
    }
    atlasCanvas.handleKeyDown(e)
  }
  document.addEventListener('keydown', keyHandler)

  // Buttons
  document.getElementById('at-btn-back').onclick = () => browseFolder(folderPath)
  document.getElementById('at-btn-save').onclick = save
  document.getElementById('at-btn-revert').onclick = revert
  document.getElementById('at-btn-detect').onclick = autoDetect
  document.getElementById('at-clear-btn').onclick = clearSprites
  bindAnimationPanel()

  // Breadcrumb navigation
  panelBody.querySelectorAll('.at-bc-item').forEach(el => {
    const p = el.dataset.path
    if (p !== path) el.onclick = () => browseFolder(p)
  })

  // Load file
  await loadAtlasFile(path)
}

function exitEditor() {
  atlasLoadToken += 1
  canvas.stopLoop()
  if (keyHandler) {
    document.removeEventListener('keydown', keyHandler)
    keyHandler = null
  }
  editorActive = false
  currentAssetPath = null
  // Reset atlas state
  S.atlas.img = null
  S.atlas.bboxes = []
  S.atlas.sel = -1
  S.atlas.mode = 'idle'
  S.atlas.sheetMode = false
  S.atlas.frameWidth = 0
  S.atlas.frameHeight = 0
  S.atlas.tilesetMode = false
  S.atlas.tileWidth = 0
  S.atlas.tileHeight = 0
  S.atlas.tilesetTiles = {}
  S.atlas.animation = { playing: true, pausedFrameIndex: 0 }
  stopAnimationPreview()
}

async function loadAtlasFile(path) {
  const loadToken = ++atlasLoadToken
  stopAnimationPreview()
  clearUndo()
  let folder = '', manifest = {}, key = '', entry = null

  // Walk up directory tree to find manifest
  let p = path
  const candidates = []
  while (p.includes('/')) {
    p = p.substring(0, p.lastIndexOf('/'))
    candidates.push(p)
  }

  for (const f of candidates) {
    const m = await api.fetchManifestRaw(f)
    if (!m || typeof m !== 'object' || Object.keys(m).length === 0) continue
    const relPath = path.startsWith(f + '/') ? path.substring(f.length + 1) : path
    for (const [k, v] of Object.entries(m)) {
      if (v.path === relPath) { folder = f; manifest = m; key = k; entry = v; break }
    }
    if (entry) break
  }

  const a = S.atlas
  a.folder = folder
  a.manifest = manifest
  a.imageKey = key
  a.imageFile = entry?.path || path.split('/').pop()
  a.sheetMode = false
  a.frameWidth = 0
  a.frameHeight = 0
  a.tilesetMode = false
  a.tileWidth = 0
  a.tileHeight = 0
  a.tilesetTiles = {}
  a.bboxes = []
  a.sel = -1
  a.thumbs = {}
  a.img = null
  a.animation = { playing: true, pausedFrameIndex: 0 }

  // Detect asset type from manifest entry before loading image
  // Deprecated: spritesheet kept for backwards compatibility; new assets use atlas.
  if (entry && entry.type === 'spritesheet' && entry.frameWidth && entry.frameHeight) {
    a.sheetMode = true
    a.frameWidth = entry.frameWidth
    a.frameHeight = entry.frameHeight
  } else if (entry && entry.type === 'tileset') {
    const grid = tileGridFromEntry(entry)
    a.tilesetMode = true
    a.tileWidth = grid.tileWidth
    a.tileHeight = grid.tileHeight
    a.tilesetTiles = entry.tiles || {}
  } else if (entry && entry.type === 'atlas' && entry.sprites) {
    for (const [name, sp] of Object.entries(entry.sprites)) {
      const item = { name, bbox: [...sp.bbox] }
      if (Array.isArray(sp.pivot) && sp.pivot.length === 2) item.pivot = [...sp.pivot]
      a.bboxes.push(item)
    }
  } else if (!entry || entry.type !== 'atlas') {
    // Auto-convert to atlas for editing
    if (!key) a.imageKey = a.imageFile.replace(/\.[^.]+$/, '')
    if (!a.manifest[a.imageKey]) {
      a.manifest[a.imageKey] = { type: 'atlas', path: a.imageFile, sprites: {} }
    } else {
      a.manifest[a.imageKey].type = 'atlas'
      a.manifest[a.imageKey].sprites = a.manifest[a.imageKey].sprites || {}
    }
    if (!a.folder) a.folder = path.substring(0, path.lastIndexOf('/'))
  }

  // Load image
  const img = new Image()
  img.crossOrigin = 'anonymous'
  img.src = `/${path}?t=${Date.now()}`
  img.onload = () => {
    if (loadToken !== atlasLoadToken) return
    a.img = img
    canvas.fitToView(img)
    if (a.sheetMode && a.frameWidth > 0 && a.frameHeight > 0) {
      _rebuildSheetGrid()
    } else if (a.tilesetMode && a.tileWidth > 0 && a.tileHeight > 0) {
      _rebuildTilesetGrid()
    } else {
      updateAnimationPanel()
    }
    if (!a.tilesetMode) {
      startAnimationPreview()
    }
  }
  img.onerror = () => {
    if (loadToken !== atlasLoadToken) return
    setStatus(`Failed to load ${path}`)
  }

  a.originalBboxes = a.bboxes.map(cloneAtlasItem)
  updateSpriteList()
  if (a.tilesetMode) {
    stopAnimationPreview()
  } else {
    updateAnimationPanel()
  }

  // Adjust toolbar for spritesheet mode
  const detectBtn = document.getElementById('at-btn-detect')
  const clearBtn = document.getElementById('at-clear-btn')
  const saveBtn = document.getElementById('at-btn-save')
  const revertBtn = document.getElementById('at-btn-revert')
  const animPanel = document.getElementById('at-anim-panel')
  if (a.tilesetMode) {
    if (detectBtn) detectBtn.style.display = 'none'
    if (clearBtn) clearBtn.style.display = 'none'
    if (saveBtn) saveBtn.style.display = 'none'
    if (revertBtn) revertBtn.style.display = 'none'
    if (animPanel) animPanel.style.display = 'none'
    setStatus(a.tileWidth && a.tileHeight ? `Tileset ${a.tileWidth}x${a.tileHeight}` : 'Tileset missing tileSize')
  } else if (a.sheetMode) {
    if (detectBtn) detectBtn.style.display = 'none'
    if (clearBtn) clearBtn.style.display = 'none'
    setStatus(`Spritesheet ${a.frameWidth}x${a.frameHeight}`)
  } else {
    if (animPanel) animPanel.style.display = ''
    setStatus(`Loaded ${path}`)
  }
  clearSaveDirty()
}

async function save() {
  const a = S.atlas
  if (a.tilesetMode) return setStatus('Tileset preview is read-only')
  if (!a.folder || !a.imageKey) return setStatus('Nothing to save')
  if (!S.saveDirty) return setStatus('No changes to save')
  const manifest = { ...a.manifest }
  if (a.sheetMode) {
    // Deprecated: spritesheet kept for backwards compatibility; new assets use atlas.
    manifest[a.imageKey] = {
      type: 'spritesheet',
      path: a.imageFile,
      frameWidth: a.frameWidth,
      frameHeight: a.frameHeight,
    }
  } else {
    const sprites = {}
    for (const b of a.bboxes) {
      const sp = { bbox: b.bbox }
      if (Array.isArray(b.pivot) && b.pivot.length === 2) sp.pivot = b.pivot
      sprites[b.name] = sp
    }
    const prevEntry = a.manifest[a.imageKey] || {}
    manifest[a.imageKey] = { type: 'atlas', path: a.imageFile, sprites }
    if (Array.isArray(prevEntry.pivot) && prevEntry.pivot.length === 2) {
      manifest[a.imageKey].pivot = prevEntry.pivot
    }
  }

  const result = await api.putManifestRaw(a.folder, manifest)
  if (result.ok) {
    a.manifest = manifest
    folderManifestCache.set(a.folder, manifest)
    a.originalBboxes = a.bboxes.map(cloneAtlasItem)
    clearSaveDirty()
    setStatus(`Saved to ${a.folder}/manifest.json`)
  } else {
    setStatus(`Save failed: ${result.error}`)
  }
}

function markAtlasDirty() {
  markSaveDirty()
}

function updateSaveButton() {
  const saveBtn = document.getElementById('at-btn-save')
  if (saveBtn) saveBtn.disabled = !S.saveDirty
}

function cloneAtlasItem(item) {
  const clone = { ...item, bbox: [...item.bbox] }
  if (Array.isArray(item.pivot)) clone.pivot = [...item.pivot]
  return clone
}

function revert() {
  const a = S.atlas
  if (a.originalBboxes.length === 0 && a.bboxes.length === 0) return setStatus('Nothing to revert')
  a.bboxes = a.originalBboxes.map(cloneAtlasItem)
  a.sel = -1
  markAtlasDirty()
  updateSpriteList()
  updateAnimationPanel()
  setStatus('Reverted')
}

function autoDetect() {
  const a = S.atlas
  if (!a.img) return setStatus('Load an image first')

  const offscreen = document.createElement('canvas')
  offscreen.width = a.img.naturalWidth
  offscreen.height = a.img.naturalHeight
  const ctx = offscreen.getContext('2d')
  ctx.drawImage(a.img, 0, 0)
  const data = ctx.getImageData(0, 0, offscreen.width, offscreen.height)

  const detected = detectSprites(data, 64)
  if (detected.length === 0) return setStatus('No sprites detected')

  pushUndo()
  const stem = a.imageKey
  let counter = a.bboxes.length
  for (const bbox of detected) {
    a.bboxes.push({ name: `${stem}_c${counter}`, bbox })
    counter++
  }
  markAtlasDirty()
  updateSpriteList()
  updateAnimationPanel()
  setStatus(`Detected ${detected.length} sprites`)
}

function clearSprites() {
  clearBboxes()
  markAtlasDirty()
  updateAnimationPanel()
}

function bindAnimationPanel() {
  updateAnimationPanel()
}

function updateAnimationPanel() {
  const panel = document.getElementById('at-anim-panel')
  if (!panel) return
  const a = S.atlas
  const anim = a.animation || { playing: true, pausedFrameIndex: 0 }
  const frames = a.bboxes
  panel.innerHTML = `
    <div class="at-anim-head">
      <span>Animation Preview</span>
      <button class="at-btn at-anim-play" id="at-anim-play">${anim.playing === false ? 'Play' : 'Pause'}</button>
    </div>
    <canvas class="at-anim-canvas" id="at-anim-canvas" width="180" height="116"></canvas>
    <div class="at-anim-rail" id="at-anim-rail">
      <div class="at-anim-rail-track">
        ${frames.length ? frames.map((frame, i) => `
          <button class="at-anim-tick" data-seek-frame="${i}" title="${esc(frame.name || `frame_${i}`)}">
            <canvas width="34" height="34"></canvas>
          </button>`).join('') : '<div class="at-anim-empty">No frames</div>'}
        <i class="at-anim-pointer" id="at-anim-pointer"></i>
      </div>
    </div>`

  const play = document.getElementById('at-anim-play')
  if (play) play.onclick = () => {
    a.animation.playing = a.animation.playing === false
    animationPreviewStartedAt = performance.now()
    updateAnimationPanel()
    drawAnimationPreview()
    if (a.animation.playing) startAnimationPreview()
    else stopAnimationPreview()
  }
  panel.querySelectorAll('[data-seek-frame]').forEach(button => {
    button.onclick = () => {
      const idx = Number(button.dataset.seekFrame)
      if (!Number.isInteger(idx)) return
      const frame = frames[idx]
      const bboxIndex = frame ? a.bboxes.findIndex(item => item.name === frame.name) : -1
      a.sel = bboxIndex >= 0 ? bboxIndex : a.sel
      S.dirty = true
      a.animation.playing = false
      a.animation.pausedFrameIndex = idx
      stopAnimationPreview()
      updateSpriteList()
      updateAnimationPanel()
      drawAnimationPreview()
      setStatus(`Paused on frame ${idx + 1}`)
    }
  })
  drawAnimationRailThumbs()
  drawAnimationPreview()
}

function startAnimationPreview() {
  stopAnimationPreview()
  if (S.atlas.animation?.playing === false) return
  animationPreviewStartedAt = performance.now()
  const tick = () => {
    drawAnimationPreview()
    animationFrameId = requestAnimationFrame(tick)
  }
  animationFrameId = requestAnimationFrame(tick)
}

function stopAnimationPreview() {
  if (!animationFrameId) return
  cancelAnimationFrame(animationFrameId)
  animationFrameId = 0
}

function drawAnimationPreview() {
  const canvasEl = document.getElementById('at-anim-canvas')
  const a = S.atlas
  const frames = animationFrameItems()
  if (!canvasEl) return
  const ctx = canvasEl.getContext('2d')
  const w = canvasEl.width
  const h = canvasEl.height
  ctx.clearRect(0, 0, w, h)
  ctx.fillStyle = getComputedStyle(document.documentElement).getPropertyValue('--warm-sand') || '#2a2825'
  ctx.fillRect(0, 0, w, h)
  if (!a.img || !frames.length) return drawAnimText(ctx, w, h, 'No frames')

  const timing = getAnimationTiming()
  const idx = timing.index
  const frame = frames[idx] || frames[0]
  if (!frame) return
  const [sx, sy, sw, sh] = frame.bbox
  const scale = Math.min((w - 18) / sw, (h - 22) / sh, 6)
  const dw = sw * scale
  const dh = sh * scale
  ctx.imageSmoothingEnabled = false
  ctx.drawImage(a.img, sx, sy, sw, sh, (w - dw) / 2, (h - dh) / 2 - 4, dw, dh)
  ctx.fillStyle = getComputedStyle(document.documentElement).getPropertyValue('--stone') || '#8a867e'
  ctx.font = '11px SFMono-Regular,Consolas,monospace'
  ctx.textAlign = 'center'
  ctx.fillText(`${idx + 1}/${frames.length} ${frame.name || ''}`, w / 2, h - 7)
  updateAnimationRail(timing)
}

function getAnimationTiming() {
  const a = S.atlas
  const frames = animationFrameItems()
  const total = frames.length * PREVIEW_FRAME_MS
  if (!frames.length || total <= 0) return { index: 0, progress: 0 }
  if (a.animation?.playing === false) {
    const index = Math.max(0, Math.min(a.animation?.pausedFrameIndex ?? 0, frames.length - 1))
    return { index, progress: (index + 0.5) / frames.length }
  }
  const elapsed = Math.max(0, performance.now() - animationPreviewStartedAt) % total
  return {
    index: Math.min(frames.length - 1, Math.floor(elapsed / PREVIEW_FRAME_MS)),
    progress: elapsed / total,
  }
}

function updateAnimationRail(timing) {
  const rail = document.getElementById('at-anim-rail')
  const pointer = document.getElementById('at-anim-pointer')
  if (!rail || !pointer) return
  const progress = Math.max(0, Math.min(1, timing.progress || 0))
  pointer.style.left = `${progress * 100}%`
  rail.querySelectorAll('[data-seek-frame]').forEach((el, i) => {
    el.classList.toggle('active', i === timing.index)
  })
}

function drawAnimationRailThumbs() {
  const a = S.atlas
  const rail = document.getElementById('at-anim-rail')
  if (!rail || !a.img) return
  const frames = animationFrameItems()
  rail.querySelectorAll('[data-seek-frame]').forEach(button => {
    const idx = Number(button.dataset.seekFrame)
    const frame = frames[idx]
    const thumb = button.querySelector('canvas')
    if (!frame || !thumb) return
    const ctx = thumb.getContext('2d')
    ctx.clearRect(0, 0, thumb.width, thumb.height)
    const [sx, sy, sw, sh] = frame.bbox
    const scale = Math.min(30 / sw, 30 / sh, 4)
    const dw = sw * scale
    const dh = sh * scale
    ctx.imageSmoothingEnabled = false
    ctx.drawImage(a.img, sx, sy, sw, sh, (thumb.width - dw) / 2, (thumb.height - dh) / 2, dw, dh)
  })
}

function animationFrameItems() {
  return S.atlas.bboxes
}

function drawAnimText(ctx, w, h, text) {
  ctx.fillStyle = getComputedStyle(document.documentElement).getPropertyValue('--stone') || '#8a867e'
  ctx.font = '12px system-ui,sans-serif'
  ctx.textAlign = 'center'
  ctx.fillText(text, w / 2, h / 2)
}

// ===================== HELPERS =====================

function _rebuildSheetGrid() {
  const a = S.atlas
  if (!a.img || !a.frameWidth || !a.frameHeight) return
  const cols = Math.floor(a.img.naturalWidth / a.frameWidth)
  const rows = Math.floor(a.img.naturalHeight / a.frameHeight)
  const stem = a.imageKey || 'frame'
  a.bboxes = []
  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols; c++) {
      a.bboxes.push({
        name: `${stem}_${r * cols + c}`,
        bbox: [c * a.frameWidth, r * a.frameHeight, a.frameWidth, a.frameHeight],
      })
    }
  }
  a.sel = -1
  a.originalBboxes = a.bboxes.map(b => ({ name: b.name, bbox: [...b.bbox] }))
  updateSpriteList()
  updateAnimationPanel()
}

function _rebuildTilesetGrid() {
  const a = S.atlas
  if (!a.img || !a.tileWidth || !a.tileHeight) return
  const cols = Math.floor(a.img.naturalWidth / a.tileWidth)
  const rows = Math.floor(a.img.naturalHeight / a.tileHeight)
  const byIndex = new Map()
  for (const [name, def] of Object.entries(a.tilesetTiles || {})) {
    const index = Number(def?.index)
    if (Number.isInteger(index) && !byIndex.has(index)) byIndex.set(index, name)
  }
  a.bboxes = []
  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols; c++) {
      const index = r * cols + c
      const tileName = byIndex.get(index) || ''
      a.bboxes.push({
        name: tileName || `#${index}`,
        tileName,
        index,
        bbox: [c * a.tileWidth, r * a.tileHeight, a.tileWidth, a.tileHeight],
      })
    }
  }
  a.sel = -1
  a.originalBboxes = a.bboxes.map(b => ({ name: b.name, bbox: [...b.bbox] }))
  updateSpriteList()
  S.dirty = true
}

async function fetchFolderManifest(folderPath) {
  if (folderManifestCache.has(folderPath)) return folderManifestCache.get(folderPath)
  let manifest = {}
  try {
    const data = await api.fetchManifestRaw(folderPath)
    if (data && typeof data === 'object' && !Array.isArray(data)) manifest = data
  } catch {}
  folderManifestCache.set(folderPath, manifest)
  return manifest
}

function tilesetInfoForFile(manifest, folderPath, filePath) {
  if (!manifest || typeof manifest !== 'object') return null
  const relPath = filePath.startsWith(folderPath + '/') ? filePath.substring(folderPath.length + 1) : filePath
  for (const [key, entry] of Object.entries(manifest)) {
    if (!entry || entry.type !== 'tileset' || entry.path !== relPath) continue
    const grid = tileGridFromEntry(entry)
    if (!grid.tileWidth || !grid.tileHeight) return null
    return { key, entry, ...grid }
  }
  return null
}

async function findTilesetInfoForFile(filePath) {
  let p = filePath
  const candidates = []
  while (p.includes('/')) {
    p = p.substring(0, p.lastIndexOf('/'))
    candidates.push(p)
  }
  for (const folderPath of candidates) {
    const manifest = await fetchFolderManifest(folderPath)
    const found = tilesetInfoForFile(manifest, folderPath, filePath)
    if (found) return found
  }
  return null
}

function tileGridFromEntry(entry) {
  const size = Number(entry?.tileSize)
  const tileWidth = Number(entry?.tileWidth) || size || 0
  const tileHeight = Number(entry?.tileHeight) || size || 0
  return {
    tileWidth: Number.isFinite(tileWidth) && tileWidth > 0 ? tileWidth : 0,
    tileHeight: Number.isFinite(tileHeight) && tileHeight > 0 ? tileHeight : 0,
  }
}

function setupTilesetPreviewCards() {
  if (!panelBody) return
  panelBody.querySelectorAll('.tileset-preview').forEach(preview => {
    const img = preview.querySelector('img')
    const tileWidth = Number(preview.dataset.tileWidth)
    const tileHeight = Number(preview.dataset.tileHeight)
    if (!img || !tileWidth || !tileHeight) return
    const apply = () => {
      if (!img.naturalWidth || !img.naturalHeight) return
      const maxW = preview.clientWidth || img.naturalWidth
      const maxH = preview.clientHeight || img.naturalHeight
      const scale = Math.min(maxW / img.naturalWidth, maxH / img.naturalHeight, 1)
      preview.style.setProperty('--tile-grid-x', `${tileWidth / img.naturalWidth * 100}%`)
      preview.style.setProperty('--tile-grid-y', `${tileHeight / img.naturalHeight * 100}%`)
      preview.style.setProperty('--tileset-img-w', `${img.naturalWidth * scale}px`)
      preview.style.setProperty('--tileset-img-h', `${img.naturalHeight * scale}px`)
      preview.classList.add('ready')
    }
    if (img.complete) apply()
    else img.addEventListener('load', apply, { once: true })
  })
}

function findNode(tree, path) {
  if (!tree) return null
  if (tree.path === path) return tree
  if (tree.children) {
    for (const child of tree.children) {
      const found = findNode(child, path)
      if (found) return found
    }
  }
  return null
}

function countFiles(node) {
  if (!node) return 0
  if (node.type === 'file') return 1
  let count = 0
  for (const child of (node.children || [])) count += countFiles(child)
  return count
}

function formatSize(bytes) {
  if (!bytes) return ''
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / 1024 / 1024).toFixed(1) + ' MB'
}

function setStatus(msg) {
  if (onStatusChange) onStatusChange(msg)
}

function esc(s) {
  if (!s) return ''
  return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;')
}
