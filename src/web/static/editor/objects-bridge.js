/**
 * Objects bridge: read-only .node.json browser and preview for the Dashboard.
 */

import * as api from './api.js'

let nodeTree = null
let sidebarBody = null
let panelBody = null
let onStatusChange = null
let onSelect = null
let selectedPath = ''
let preview = null
let resizeObserver = null
let initialized = false
let renderToken = 0
let animationFrameId = 0
let editState = null
let keyHandlerBound = false
let editErrors = {}
let canvasDrag = null
let canvasPan = null
let canvasView = null
let spaceDown = false

let cachedSidebarHTML = ''
let cachedPanelHTML = ''

export async function init(sidebarEl, panelEl, statusFn, options = {}) {
  sidebarBody = sidebarEl
  panelBody = panelEl
  onStatusChange = statusFn
  onSelect = options.onSelect || null

  if (initialized && cachedSidebarHTML && cachedPanelHTML) {
    sidebarBody.innerHTML = cachedSidebarHTML
    panelBody.innerHTML = cachedPanelHTML
    reattachHandlers()
    bindAnimationControls()
    bindChildControls()
    bindEditorControls()
    drawPreview()
    startAnimationLoop()
    return
  }

  sidebarBody.innerHTML = `<div class="obj-empty-side">Loading objects...</div>`
  panelBody.innerHTML = emptyPanel('Select a .node.json template')

  try {
    nodeTree = await api.fetchNodeTree()
    if (nodeTree?.error) throw new Error(nodeTree.error)
  } catch (err) {
    nodeTree = null
    panelBody.innerHTML = emptyPanel(`Objects API unavailable: ${err.message || err}`)
    sidebarBody.innerHTML = `<div class="obj-empty-side">Objects API unavailable</div>`
    initialized = false
    return
  }
  renderTree()
  if (options.initialPath) {
    const activeItem = [...sidebarBody.querySelectorAll('.at-file')]
      .find(item => item.dataset.path === options.initialPath)
    if (activeItem) {
      setActive(activeItem)
      await openNode(options.initialPath, false)
    } else {
      panelBody.innerHTML = emptyPanel(`Object not found: ${options.initialPath}`)
    }
  } else {
    panelBody.innerHTML = emptyPanel(hasFiles(nodeTree) ? 'Select a .node.json template' : 'No object templates found')
  }
  bindKeyboardShortcuts()
  initialized = true
}

export function destroy() {
  stopAnimationLoop()
  stopCanvasDrag()
  stopCanvasPan()
  if (sidebarBody) cachedSidebarHTML = sidebarBody.innerHTML
  if (panelBody) cachedPanelHTML = panelBody.innerHTML
  if (resizeObserver) {
    resizeObserver.disconnect()
    resizeObserver = null
  }
}

function resetCanvasView() {
  canvasView = null
  stopCanvasDrag()
  stopCanvasPan()
}

function bindKeyboardShortcuts() {
  if (keyHandlerBound) return
  document.addEventListener('keydown', onEditorKeyDown)
  document.addEventListener('keyup', onEditorKeyUp)
  keyHandlerBound = true
}

function onEditorKeyDown(event) {
  if (!editState || !panelBody?.querySelector('.obj-editor')) return
  if (event.key === ' ' && !isTextInput(event.target)) {
    event.preventDefault()
    spaceDown = true
    updateCanvasCursor()
    return
  }
  const isUndoKey = (event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'z'
  if (!isUndoKey) return
  event.preventDefault()
  if (event.shiftKey) {
    redoEdit()
  } else {
    undoEdit()
  }
}

function onEditorKeyUp(event) {
  if (event.key !== ' ') return
  spaceDown = false
  if (!canvasPan) updateCanvasCursor()
}

function isTextInput(target) {
  const tag = target?.tagName
  return tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || target?.isContentEditable
}

function renderTree() {
  if (!sidebarBody) return
  sidebarBody.innerHTML = ''
  if (!nodeTree || !hasFiles(nodeTree)) {
    sidebarBody.innerHTML = `<div class="obj-empty-side">No .node.json files</div>`
    return
  }
  for (const child of nodeTree.children || []) {
    renderTreeNode(child, sidebarBody, 0)
  }
}

function renderTreeNode(node, container, depth) {
  if (node.type === 'file') {
    renderFileItem(node, container, depth)
    return
  }

  const children = node.children || []
  if (!children.length) return

  const head = document.createElement('div')
  head.className = 'at-folder'
  head.style.paddingLeft = (depth * 14 + 12) + 'px'

  const arrow = document.createElement('span')
  arrow.className = 'at-arrow'
  arrow.textContent = '\u25be'

  const label = document.createElement('span')
  label.className = 'at-folder-name'
  label.textContent = node.name
  label.dataset.path = node.path || ''

  head.appendChild(arrow)
  head.appendChild(label)
  container.appendChild(head)

  const body = document.createElement('div')
  container.appendChild(body)

  const toggle = (e) => {
    e.stopPropagation()
    const closed = body.style.display === 'none'
    body.style.display = closed ? '' : 'none'
    arrow.textContent = closed ? '\u25be' : '\u25b8'
  }
  arrow.onclick = toggle
  label.onclick = toggle

  for (const child of children) renderTreeNode(child, body, depth + 1)
}

function renderFileItem(file, container, depth) {
  const el = document.createElement('div')
  el.className = 'at-file'
  el.style.paddingLeft = (depth * 14 + 26) + 'px'
  el.dataset.path = file.path

  const dot = document.createElement('span')
  dot.className = 'at-file-dot'
  dot.style.background = '#d97757'

  const name = document.createElement('span')
  name.textContent = file.name

  el.appendChild(dot)
  el.appendChild(name)
  container.appendChild(el)

  el.onclick = () => {
    openNode(file.path)
    setActive(el)
  }
}

function reattachHandlers() {
  if (!sidebarBody) return
  sidebarBody.querySelectorAll('.at-folder').forEach(el => {
    const arrow = el.querySelector('.at-arrow')
    const label = el.querySelector('.at-folder-name')
    const body = el.nextElementSibling
    const toggle = (e) => {
      e.stopPropagation()
      if (!body) return
      const closed = body.style.display === 'none'
      body.style.display = closed ? '' : 'none'
      if (arrow) arrow.textContent = closed ? '\u25be' : '\u25b8'
    }
    if (arrow) arrow.onclick = toggle
    if (label) label.onclick = toggle
  })
  sidebarBody.querySelectorAll('.at-file').forEach(el => {
    const path = el.dataset.path
    if (path) el.onclick = () => { openNode(path); setActive(el) }
  })
}

async function openNode(path, notifySelection = true) {
  stopAnimationLoop()
  selectedPath = path
  if (notifySelection && onSelect) onSelect(path)
  panelBody.innerHTML = `<div class="obj-loading">Loading ${esc(path)}...</div>`
  try {
    const result = await api.fetchNode(path)
    if (result.error) throw new Error(result.error)
    await renderObject(path, result.data || {})
    setStatus(`Loaded ${path}`)
  } catch (err) {
    panelBody.innerHTML = emptyPanel(err.message || 'Could not load object')
    setStatus(`Object load failed: ${err.message || err}`)
  }
}

async function renderObject(path, node) {
  resetCanvasView()
  editState = {
    path,
    data: cloneJSON(node),
    savedData: cloneJSON(node),
    undoStack: [],
    redoStack: [],
    dirty: false,
    saving: false,
    selectedChildIndex: null,
    selectedBoxTarget: null,
  }
  editErrors = {}
  const data = editState.data
  const visual = objectOrNull(data.visual)
  const collider = objectOrNull(data.collider)
  const animations = objectOrNull(data.animations)
  const config = objectOrNull(data.config)
  const children = Array.isArray(data.children) ? data.children : []
  const textureKey = visual?.texture || ''
  const token = ++renderToken
  preview = null

  panelBody.innerHTML = `
    <div class="obj-editor">
      <div class="obj-toolbar">
        <div>
          <div class="obj-eyebrow">Object Editor</div>
          <div class="obj-title">${esc(data.name || basename(path))}</div>
        </div>
        <div class="obj-actions">
          <span class="obj-dirty" id="obj-dirty">Saved</span>
          <button type="button" class="obj-tool-btn" id="obj-undo" disabled>Undo</button>
          <button type="button" class="obj-tool-btn" id="obj-redo" disabled>Redo</button>
          <button type="button" class="obj-tool-btn" id="obj-revert" disabled>Revert</button>
          <button type="button" class="obj-save-btn" id="obj-save" disabled>Save</button>
        </div>
        <div class="obj-path">${esc(path)}</div>
      </div>
      <div class="obj-body">
        <div class="obj-stage">
          <div class="obj-canvas-wrap" id="obj-canvas-wrap">
            <canvas id="obj-canvas"></canvas>
            <div class="obj-legend">
              <span><i class="obj-swatch obj-swatch-visual"></i>visual</span>
              <span><i class="obj-swatch obj-swatch-collider"></i>collider</span>
              <span><i class="obj-swatch obj-swatch-child"></i>child</span>
              <span><i class="obj-swatch obj-swatch-anchor"></i>origin</span>
            </div>
          </div>
          <div class="obj-readout" id="obj-readout">${esc(previewLabel(node, null))}</div>
          <div class="obj-anim-rail" id="obj-anim-rail"></div>
        </div>
        <aside class="obj-inspector">
          ${section('Identity', [
            row('name', data.name),
            row('script', data.script || '(none)'),
            row('src', data.src || '(none)'),
            row('tags', Array.isArray(data.tags) ? data.tags.join(', ') : '(none)'),
            row('children', Array.isArray(data.children) ? String(data.children.length) : '0'),
          ])}
          ${section('Visual', [
            row('type', visual?.type || '(none)'),
            row('texture', textureKey || '(none)'),
            editableTextRow('frame', 'visual.frame', visual?.frame ?? ''),
            ...(visual?.type === 'rect' ? [] : [
              editableNumberRow('ratio', 'visual.ratio', visual?.ratio, { min: 0.01, placeholder: '(size)' }),
            ]),
            editableNumberRow('width', 'visual.width', visual?.width, { min: 1 }),
            editableNumberRow('height', 'visual.height', visual?.height, { min: 1 }),
          ], { target: 'visual' })}
          ${visualTransformRows(data)}
          ${section('Collider', colliderRows(collider), { swatch: 'obj-title-swatch-collider', target: 'collider' })}
          ${section('Animation', animationRows(animations, ''))}
          ${section('Script Config', configRows(config))}
          ${section('Children', childRows(children), { swatch: 'obj-title-swatch-child' })}
        </aside>
      </div>
    </div>`

  preview = {
    node: data,
    visual,
    collider,
    children,
    selectedChildIndex: null,
    animations,
    asset: null,
    clipName: '',
    clip: null,
    clipAsset: null,
    animationPlaying: true,
    pausedFrameIndex: 0,
    selectedBoxTarget: null,
    childVisuals: [],
    childVisualError: '',
    layout: null,
    animationStartedAt: performance.now(),
  }
  bindCanvas()
  bindAnimationControls()
  bindChildControls()
  bindEditorControls()
  updateEditorButtons()

  const asset = await loadVisualAsset(visual)
  if (token !== renderToken) return
  preview.asset = asset
  try {
    preview.childVisuals = await loadChildVisuals(children)
  } catch (err) {
    preview.childVisualError = err.message || String(err)
  }
  if (token !== renderToken) return
  preview.animationStartedAt = performance.now()
  updateReadout()
  drawPreview()
}

function bindCanvas() {
  const wrap = document.getElementById('obj-canvas-wrap')
  const canvas = document.getElementById('obj-canvas')
  if (!wrap || !canvas) return
  if (resizeObserver) resizeObserver.disconnect()
  resizeObserver = new ResizeObserver(() => drawPreview())
  resizeObserver.observe(wrap)
  canvas.onmousedown = onCanvasMouseDown
  canvas.onmousemove = onCanvasMouseMove
  canvas.onwheel = onCanvasWheel
  canvas.onmouseleave = () => {
    if (!canvasDrag && !canvasPan) updateCanvasCursor()
  }
  drawPreview()
}

async function loadVisualAsset(visual) {
  if (!visual || !['image', 'spritesheet', 'atlas'].includes(visual.type) || !visual.texture) return null
  try {
    const info = await api.resolveNodeTexture(visual.texture)
    if (info.error) return { error: info.error }
    if (!info.url) return { info, error: 'Texture has no image path' }
    const img = await loadImage(info.url)
    return { info, img, crop: resolveCrop(visual, info, img) }
  } catch (err) {
    return { error: err.message || String(err) }
  }
}

async function loadChildVisuals(children, srcStack = new Set()) {
  const result = []
  for (const rawChild of children || []) {
    const resolved = await resolveChildDefinition(rawChild, srcStack)
    const child = resolved.node
    const initial = initialNodeVisual(child)
    result.push({
      node: child,
      visual: initial.visual,
      clip: initial.clip,
      asset: await loadVisualAsset(initial.visual),
      children: await loadChildVisuals(child.children, resolved.srcStack),
    })
  }
  return result
}

async function resolveChildDefinition(rawChild, srcStack) {
  if (!objectOrNull(rawChild)) throw new Error('Child definition must be an object')
  if (!rawChild.src) return { node: cloneJSON(rawChild), srcStack }
  if (srcStack.has(rawChild.src)) throw new Error(`Circular child src: ${rawChild.src}`)
  const response = await api.fetchNode(rawChild.src)
  if (response.error) throw new Error(response.error)
  const resolved = cloneJSON(response.data || {})
  if (rawChild.config) resolved.config = { ...(resolved.config || {}), ...rawChild.config }
  for (const field of ['name', 'tags', 'enabled']) {
    if (rawChild[field] !== undefined) resolved[field] = cloneJSON(rawChild[field])
  }
  return { node: resolved, srcStack: new Set([...srcStack, rawChild.src]) }
}

function initialNodeVisual(node) {
  const visual = objectOrNull(node?.visual) ? cloneJSON(node.visual) : null
  const defaultName = node?.animations?.default
  const clip = defaultName ? objectOrNull(node?.animations?.clips?.[defaultName]) : null
  const firstFrame = Array.isArray(clip?.frames) ? clip.frames[0] : null
  if (!visual || firstFrame == null) return { visual, clip }
  const source = objectOrNull(clip.source)
  if (source?.type) visual.type = source.type
  if (source?.texture) visual.texture = source.texture
  visual.frame = frameRefId(firstFrame)
  return { visual, clip }
}

async function loadClipAsset(clip, visual) {
  const source = objectOrNull(clip?.source)
  const texture = source?.texture || visual?.texture
  const type = source?.type || visual?.type || 'atlas'
  const frames = Array.isArray(clip?.frames) ? clip.frames : []
  if (!texture) return { error: 'Clip has no texture' }
  if (!frames.length) return { error: 'Clip has no frames' }
  try {
    const info = await api.resolveNodeTexture(texture)
    if (info.error) return { error: info.error }
    if (!info.url) return { info, error: 'Texture has no image path' }
    const img = await loadImage(info.url)
    const resolvedFrames = frames.map(frameRef => ({
      label: String(frameRefId(frameRef)),
      crop: resolveFrameCrop(type, frameRefId(frameRef), info, img),
      offset: frameRefOffset(frameRef),
    })).filter(frame => Array.isArray(frame.crop))
    if (!resolvedFrames.length) return { info, img, error: 'Clip frames not found' }
    return { info, img, frames: resolvedFrames }
  } catch (err) {
    return { error: err.message || String(err) }
  }
}

function frameRefId(frameRef) {
  if (objectOrNull(frameRef)) return frameRef.frame
  return frameRef
}

function frameRefOffset(frameRef) {
  if (!objectOrNull(frameRef)) return [0, 0]
  const offset = frameRef.offset
  if (!Array.isArray(offset) || offset.length !== 2) return [0, 0]
  const x = Number(offset[0])
  const y = Number(offset[1])
  return [Number.isFinite(x) ? x : 0, Number.isFinite(y) ? y : 0]
}

function loadImage(url) {
  return new Promise((resolve, reject) => {
    const img = new Image()
    img.onload = () => resolve(img)
    img.onerror = () => reject(new Error(`Image failed: ${url}`))
    img.src = `${url}?t=${Date.now()}`
  })
}

function resolveCrop(visual, info, img) {
  const crop = resolveFrameCrop(visual.type, visual.frame, info, img)
  return crop || [0, 0, img.naturalWidth, img.naturalHeight]
}

function resolveFrameCrop(type, frame, info, img) {
  if (type === 'atlas' && frame != null && info.sprites && info.sprites[frame]) {
    const bbox = info.sprites[frame].bbox
    if (Array.isArray(bbox) && bbox.length === 4) return bbox.map(Number)
  }
  if (type === 'spritesheet' && info.frameWidth && info.frameHeight) {
    const fw = Number(info.frameWidth)
    const fh = Number(info.frameHeight)
    const frameIndex = Number.isFinite(Number(frame)) ? Number(frame) : 0
    const cols = Math.max(1, Math.floor(img.naturalWidth / fw))
    return [(frameIndex % cols) * fw, Math.floor(frameIndex / cols) * fh, fw, fh]
  }
  if (type === 'image') return [0, 0, img.naturalWidth, img.naturalHeight]
  return null
}

function resolvePreviewPivot(visual, info, animationFrame = null) {
  const clipPivot = preview?.clip?.pivot
  if (validPivot(clipPivot)) return clipPivot.map(Number)
  const frameName = animationFrame?.label ?? visual?.frame
  if (frameName != null && validPivot(info?.sprites?.[frameName]?.pivot)) return info.sprites[frameName].pivot.map(Number)
  if (validPivot(info?.pivot)) return info.pivot.map(Number)
  if (visual?.type === 'rect') return [0.5, 0.5]
  return [0.5, 1]
}

function resolveNodeVisualPivot(visual, info, clip = null) {
  if (validPivot(clip?.pivot)) return clip.pivot.map(Number)
  if (visual?.frame != null && validPivot(info?.sprites?.[visual.frame]?.pivot)) {
    return info.sprites[visual.frame].pivot.map(Number)
  }
  if (validPivot(info?.pivot)) return info.pivot.map(Number)
  if (visual?.type === 'rect') return [0.5, 0.5]
  return [0.5, 1]
}

function resolveColliderPivot(collider, isCircle) {
  if (validPivot(collider?.pivot)) return collider.pivot.map(Number)
  if (isCircle) return [0.5, 0.5]
  return preview?.layout?.pivot || [0.5, 1]
}

function resolveChildColliderPivot(collider, isCircle) {
  if (validPivot(collider?.pivot)) return collider.pivot.map(Number)
  return [0.5, 0.5]
}

function validPivot(value) {
  return Array.isArray(value) && value.length === 2 && Number.isFinite(Number(value[0])) && Number.isFinite(Number(value[1]))
}

function drawPreview() {
  const canvas = document.getElementById('obj-canvas')
  const wrap = document.getElementById('obj-canvas-wrap')
  if (!canvas || !wrap) return
  const dpr = window.devicePixelRatio || 1
  const w = wrap.clientWidth
  const h = wrap.clientHeight
  canvas.width = Math.max(1, w * dpr)
  canvas.height = Math.max(1, h * dpr)
  canvas.style.width = w + 'px'
  canvas.style.height = h + 'px'
  const ctx = canvas.getContext('2d')
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
  ctx.clearRect(0, 0, w, h)
  drawGrid(ctx, w, h)

  if (!preview) {
    drawCenteredText(ctx, w, h, 'Select an object')
    return
  }

  const { visual, collider } = preview
  const metrics = computePreviewMetrics(w, h)
  preview.layout = metrics
  const { activeAsset, activeError, crop, displayW, displayH, baseDisplayW, baseDisplayH, scale, originX, originY, visualRect, animationFrame } = metrics

  if (activeAsset?.img && crop) {
    ctx.imageSmoothingEnabled = false
    ctx.drawImage(activeAsset.img, crop[0], crop[1], crop[2], crop[3], visualRect.x, visualRect.y, visualRect.w, visualRect.h)
  } else if (visual?.type === 'rect') {
    ctx.fillStyle = cssColor(visual.color)
    ctx.fillRect(visualRect.x, visualRect.y, visualRect.w, visualRect.h)
  } else {
    drawPlaceholder(ctx, visualRect.x, visualRect.y, visualRect.w, visualRect.h, activeError || 'No visual')
  }

  const rootWorld = nodeWorldPosition(preview.node)
  drawChildSprites(ctx, preview.childVisuals, originX, originY, scale, rootWorld, rootWorld)
  drawVisualBox(ctx, visualRect.x, visualRect.y, visualRect.w, visualRect.h)
  drawCollider(ctx, collider, originX, originY, baseDisplayW, baseDisplayH, scale)
  drawChildBounds(ctx, preview.children, preview.selectedChildIndex, originX, originY, baseDisplayW, baseDisplayH, scale)
  drawSelectedBoxHandles(ctx)
  drawOrigin(ctx, originX, originY)
  updateReadout(animationFrame)
  updateObjectAnimationRail(currentAnimationTiming(preview))
}

function computePreviewMetrics(w, h) {
  const visual = preview?.visual || null
  const asset = preview?.asset || null
  const animationFrame = currentAnimationFrame(preview)
  const activeAsset = animationFrame ? { img: preview.clipAsset?.img, crop: animationFrame.crop } : asset
  const activeError = preview?.clip && preview.clipAsset?.error ? preview.clipAsset.error : asset?.error
  const crop = activeAsset?.crop || null
  const sourceW = crop ? crop[2] : Number(visual?.width || 64)
  const sourceH = crop ? crop[3] : Number(visual?.height || 64)
  const baseSourceSize = resolveBaseVisualSourceSize(asset, sourceW, sourceH)
  const displaySize = resolveVisualDisplaySize(visual, sourceW, sourceH, baseSourceSize.width, baseSourceSize.height)
  const baseDisplaySize = resolveVisualDisplaySize(visual, baseSourceSize.width, baseSourceSize.height, baseSourceSize.width, baseSourceSize.height)
  const displayW = displaySize.width
  const displayH = displaySize.height
  const baseDisplayW = baseDisplaySize.width
  const baseDisplayH = baseDisplaySize.height
  const pivot = resolvePreviewPivot(visual, activeAsset?.info, animationFrame)
  const fitBounds = unitFitBounds(displayW, displayH, baseDisplayW, baseDisplayH, pivot)
  const fitScale = Math.max(0.1, Math.min(
    Math.max(1, w - 96) / Math.max(fitBounds.w, 1),
    Math.max(1, h - 96) / Math.max(fitBounds.h, 1),
    6,
  ))
  if (!canvasView) {
    canvasView = {
      scale: fitScale,
      originX: w / 2 - fitBounds.cx * fitScale,
      originY: h / 2 - fitBounds.cy * fitScale,
    }
  }
  const scale = canvasDrag?.metrics?.scale || canvasView.scale
  const originX = canvasDrag?.metrics?.originX ?? canvasView.originX
  const originY = canvasDrag?.metrics?.originY ?? canvasView.originY
  const transform = objectOrNull(preview?.node?.visualTransform)
  const visualOffsetX = numberValue(transform?.offsetX, 0)
  const visualOffsetY = numberValue(transform?.offsetY, 0)
  const frameOffset = Array.isArray(animationFrame?.offset) ? animationFrame.offset : [0, 0]
  const frameOffsetX = numberValue(frameOffset[0], 0)
  const frameOffsetY = numberValue(frameOffset[1], 0)
  const visualCx = originX + (visualOffsetX + frameOffsetX) * scale
  const visualCy = originY + (visualOffsetY + frameOffsetY) * scale
  const visualRect = {
    x: visualCx - displayW * pivot[0] * scale,
    y: visualCy - displayH * pivot[1] * scale,
    w: displayW * scale,
    h: displayH * scale,
  }
  return {
    canvasW: w,
    canvasH: h,
    originX,
    originY,
    scale,
    activeAsset,
    activeError,
    crop,
    sourceW,
    sourceH,
    baseSourceW: baseSourceSize.width,
    baseSourceH: baseSourceSize.height,
    displayW,
    displayH,
    baseDisplayW,
    baseDisplayH,
    visualOffsetX,
    visualOffsetY,
    frameOffsetX,
    frameOffsetY,
    pivot,
    visualRect,
    animationFrame,
  }
}

function resolveBaseVisualSourceSize(asset, sourceW, sourceH) {
  const crop = asset?.crop
  if (Array.isArray(crop) && crop.length === 4) {
    return { width: Number(crop[2]) || sourceW, height: Number(crop[3]) || sourceH }
  }
  return { width: sourceW, height: sourceH }
}

function resolveVisualDisplaySize(visual, sourceW, sourceH, baseSourceW = sourceW, baseSourceH = sourceH) {
  const fallbackW = Number(sourceW || 64)
  const fallbackH = Number(sourceH || 64)
  if (!visual) return { width: fallbackW, height: fallbackH, mode: 'source' }
  const hasWidth = visual.width !== undefined
  const hasHeight = visual.height !== undefined
  if (hasWidth || hasHeight) {
    const baseW = Math.max(1, Number(baseSourceW || fallbackW))
    const baseH = Math.max(1, Number(baseSourceH || fallbackH))
    const scaleX = hasWidth ? numberValue(visual.width, baseW) / baseW : 1
    const scaleY = hasHeight ? numberValue(visual.height, baseH) / baseH : 1
    return {
      width: fallbackW * scaleX,
      height: fallbackH * scaleY,
      mode: 'size',
    }
  }
  const ratio = Number(visual.ratio)
  if (Number.isFinite(ratio) && ratio > 0 && visual.type !== 'rect') {
    return { width: fallbackW * ratio, height: fallbackH * ratio, mode: 'ratio' }
  }
  return { width: fallbackW, height: fallbackH, mode: 'source' }
}

function unitFitBounds(displayW, displayH, baseDisplayW = displayW, baseDisplayH = displayH, pivot = [0.5, 0.5]) {
  const transform = objectOrNull(editState?.data?.visualTransform)
  const visualOffsetX = numberValue(transform?.offsetX, 0)
  const visualOffsetY = numberValue(transform?.offsetY, 0)
  const animationFrame = currentAnimationFrame(preview)
  const frameOffset = Array.isArray(animationFrame?.offset) ? animationFrame.offset : [0, 0]
  const frameOffsetX = numberValue(frameOffset[0], 0)
  const frameOffsetY = numberValue(frameOffset[1], 0)
  let bounds = unitPivotRectBounds(visualOffsetX + frameOffsetX, visualOffsetY + frameOffsetY, displayW, displayH, pivot)
  const rootWorld = nodeWorldPosition(preview?.node)
  const childrenBounds = childVisualBounds(preview?.childVisuals, rootWorld, rootWorld)
  if (childrenBounds) bounds = unionUnitBounds(bounds, childrenBounds)
  const targetBounds = selectedTargetUnitBounds(baseDisplayW, baseDisplayH, pivot)
  if (targetBounds) bounds = unionUnitBounds(bounds, targetBounds)
  return bounds
}

function childVisualBounds(nodes, rootWorld, parentWorld) {
  let bounds = null
  for (const entry of nodes || []) {
    const world = childWorldPosition(entry.node, parentWorld)
    const x = world.x - rootWorld.x
    const y = world.y - rootWorld.y
    const visual = entry.visual
    const asset = entry.asset
    if (visual && entry.node.enabled !== false) {
      const crop = asset?.crop
      const sourceW = crop?.[2] || numberValue(visual.width, 64)
      const sourceH = crop?.[3] || numberValue(visual.height, 64)
      const size = resolveVisualDisplaySize(visual, sourceW, sourceH)
      const transform = objectOrNull(entry.node.visualTransform)
      const pivot = resolveNodeVisualPivot(visual, asset?.info, entry.clip)
      const own = unitPivotRectBounds(
        x + numberValue(transform?.offsetX, 0),
        y + numberValue(transform?.offsetY, 0),
        size.width,
        size.height,
        pivot,
      )
      bounds = bounds ? unionUnitBounds(bounds, own) : own
    }
    const nested = childVisualBounds(entry.children, rootWorld, world)
    if (nested) bounds = bounds ? unionUnitBounds(bounds, nested) : nested
  }
  return bounds
}

function selectedTargetUnitBounds(displayW, displayH, pivot = [0.5, 0.5]) {
  const target = editState?.selectedBoxTarget
  if (!target || !editState?.data) return null
  if (target === 'visual') {
    const visual = objectOrNull(editState.data.visual)
    if (!visual) return null
    const transform = objectOrNull(editState.data.visualTransform)
    return unitPivotRectBounds(
      numberValue(transform?.offsetX, 0),
      numberValue(transform?.offsetY, 0),
      numberValue(visual.width, displayW),
      numberValue(visual.height, displayH),
      pivot,
    )
  }
  if (target === 'collider') {
    const collider = objectOrNull(editState.data.collider)
    if (!collider) return null
    const shape = collider.shape === 'circle' ? 'circle' : 'box'
    const radius = numberValue(collider.radius, Math.min(displayW, displayH) / 2)
    const width = shape === 'circle' ? radius * 2 : numberValue(collider.width, displayW)
    const height = shape === 'circle' ? radius * 2 : numberValue(collider.height, displayH)
    return unitPivotRectBounds(
      numberValue(collider.offsetX, 0),
      numberValue(collider.offsetY, 0),
      width,
      height,
      resolveColliderPivot(collider, shape === 'circle'),
    )
  }
  const childMatch = target.match(/^child:(\d+):collider$/)
  if (!childMatch) return null
  const index = Number(childMatch[1])
  const child = editState.data.children?.[index]
  const collider = objectOrNull(child?.collider)
  if (!child || !collider) return null
  const visual = objectOrNull(child.visual)
  const offset = childOffset(child)
  const fallbackW = numberValue(visual?.width, displayW)
  const fallbackH = numberValue(visual?.height, displayH)
  const shape = collider.shape === 'circle' ? 'circle' : 'box'
  const radius = numberValue(collider.radius, Math.min(fallbackW, fallbackH) / 2)
  const width = shape === 'circle' ? radius * 2 : numberValue(collider.width, fallbackW)
  const height = shape === 'circle' ? radius * 2 : numberValue(collider.height, fallbackH)
  const childPivot = resolveChildColliderPivot(collider, shape === 'circle')
  return unitPivotRectBounds(
    offset.x + numberValue(collider.offsetX, 0),
    offset.y + numberValue(collider.offsetY, 0),
    width,
    height,
    childPivot,
  )
}

function unitRectBounds(cx, cy, width, height) {
  const x1 = cx - width / 2
  const y1 = cy - height / 2
  const x2 = cx + width / 2
  const y2 = cy + height / 2
  return { x1, y1, x2, y2, w: x2 - x1, h: y2 - y1, cx: (x1 + x2) / 2, cy: (y1 + y2) / 2 }
}

function unitPivotRectBounds(anchorX, anchorY, width, height, pivot = [0.5, 0.5]) {
  const px = Number(pivot?.[0])
  const py = Number(pivot?.[1])
  const x1 = anchorX - width * (Number.isFinite(px) ? px : 0.5)
  const y1 = anchorY - height * (Number.isFinite(py) ? py : 0.5)
  const x2 = x1 + width
  const y2 = y1 + height
  return { x1, y1, x2, y2, w: x2 - x1, h: y2 - y1, cx: (x1 + x2) / 2, cy: (y1 + y2) / 2 }
}

function unionUnitBounds(a, b) {
  const x1 = Math.min(a.x1, b.x1)
  const y1 = Math.min(a.y1, b.y1)
  const x2 = Math.max(a.x2, b.x2)
  const y2 = Math.max(a.y2, b.y2)
  return { x1, y1, x2, y2, w: x2 - x1, h: y2 - y1, cx: (x1 + x2) / 2, cy: (y1 + y2) / 2 }
}

function drawGrid(ctx, w, h) {
  ctx.fillStyle = '#25231f'
  ctx.fillRect(0, 0, w, h)
  ctx.strokeStyle = 'rgba(255,255,255,0.035)'
  ctx.lineWidth = 1
  for (let x = 0; x < w; x += 24) {
    ctx.beginPath()
    ctx.moveTo(x, 0)
    ctx.lineTo(x, h)
    ctx.stroke()
  }
  for (let y = 0; y < h; y += 24) {
    ctx.beginPath()
    ctx.moveTo(0, y)
    ctx.lineTo(w, y)
    ctx.stroke()
  }
}

function drawVisualBox(ctx, x, y, w, h) {
  drawOverlayRect(ctx, x, y, w, h, '#8fb6ff', {
    fill: 'rgba(143,182,255,0.045)',
    dash: [6, 5],
    width: 1.5,
  })
}

function drawCollider(ctx, collider, cx, cy, visualW, visualH, scale) {
  if (!collider) return
  const ox = Number(collider.offsetX || 0) * scale
  const oy = Number(collider.offsetY || 0) * scale
  ctx.strokeStyle = '#ff6b5f'
  ctx.fillStyle = 'rgba(255,107,95,0.08)'
  ctx.lineWidth = 2
  if (collider.shape === 'circle') {
    const r = Number(collider.radius || Math.min(visualW, visualH) / 2) * scale
    const pivot = resolveColliderPivot(collider, true)
    ctx.beginPath()
    ctx.arc(cx + ox + r * (1 - 2 * pivot[0]), cy + oy + r * (1 - 2 * pivot[1]), r, 0, Math.PI * 2)
    ctx.fill()
    ctx.stroke()
    return
  }
  const cw = Number(collider.width || visualW) * scale
  const ch = Number(collider.height || visualH) * scale
  const pivot = resolveColliderPivot(collider, false)
  drawOverlayRect(ctx, cx + ox - cw * pivot[0], cy + oy - ch * pivot[1], cw, ch, '#ff6b5f', {
    fill: 'rgba(255,107,95,0.08)',
    width: 2,
  })
}

function drawChildBounds(ctx, children, selectedIndex, cx, cy, parentW, parentH, scale) {
  if (!Array.isArray(children)) return
  children.forEach((child, index) => {
    if (!objectOrNull(child)) return
    const collider = objectOrNull(child.collider)
    const visual = objectOrNull(child.visual)
    if (!collider && !visual) return
    const selected = index === selectedIndex
    const offset = childOffset(child)
    const targetCx = cx + offset.x * scale
    const targetCy = cy + offset.y * scale
    const sourceW = Number(collider?.width || visual?.width || parentW)
    const sourceH = Number(collider?.height || visual?.height || parentH)
    const ox = Number(collider?.offsetX || 0) * scale
    const oy = Number(collider?.offsetY || 0) * scale
    const cw = sourceW * scale
    const ch = sourceH * scale

    ctx.save()
    ctx.strokeStyle = '#ffd166'
    ctx.fillStyle = selected ? 'rgba(255,209,102,0.16)' : 'rgba(255,209,102,0.05)'
    ctx.lineWidth = selected ? 2 : 1.25
    if (!selected) ctx.setLineDash([4, 4])
    if (collider?.shape === 'circle') {
      const r = Number(collider.radius || Math.min(sourceW, sourceH) / 2) * scale
      const pivot = resolveChildColliderPivot(collider, true)
      ctx.beginPath()
      ctx.arc(targetCx + ox + r * (1 - 2 * pivot[0]), targetCy + oy + r * (1 - 2 * pivot[1]), r, 0, Math.PI * 2)
      ctx.fill()
      ctx.stroke()
    } else {
      const pivot = resolveChildColliderPivot(collider, false)
      drawOverlayRect(ctx, targetCx + ox - cw * pivot[0], targetCy + oy - ch * pivot[1], cw, ch, '#ffd166', {
        fill: selected ? 'rgba(255,209,102,0.16)' : 'rgba(255,209,102,0.05)',
        dash: selected ? [] : [4, 4],
        width: selected ? 2 : 1.25,
      })
    }
    ctx.restore()
  })
}

function drawChildSprites(ctx, nodes, originX, originY, scale, rootWorld, parentWorld) {
  for (const entry of nodes || []) {
    const world = childWorldPosition(entry.node, parentWorld)
    const nodeX = originX + (world.x - rootWorld.x) * scale
    const nodeY = originY + (world.y - rootWorld.y) * scale
    const visual = entry.visual
    if (visual && entry.node.enabled !== false) {
      const asset = entry.asset
      const crop = asset?.crop
      const sourceW = crop?.[2] || numberValue(visual.width, 64)
      const sourceH = crop?.[3] || numberValue(visual.height, 64)
      const size = resolveVisualDisplaySize(visual, sourceW, sourceH)
      const transform = objectOrNull(entry.node.visualTransform)
      const pivot = resolveNodeVisualPivot(visual, asset?.info, entry.clip)
      const w = size.width * scale
      const h = size.height * scale
      const x = nodeX + numberValue(transform?.offsetX, 0) * scale - w * pivot[0]
      const y = nodeY + numberValue(transform?.offsetY, 0) * scale - h * pivot[1]
      if (asset?.img && crop) {
        ctx.imageSmoothingEnabled = false
        ctx.drawImage(asset.img, crop[0], crop[1], crop[2], crop[3], x, y, w, h)
      } else if (visual.type === 'rect') {
        ctx.fillStyle = cssColor(visual.color)
        ctx.fillRect(x, y, w, h)
      } else {
        drawPlaceholder(ctx, x, y, w, h, asset?.error || 'Child visual')
      }
    }
    drawChildSprites(ctx, entry.children, originX, originY, scale, rootWorld, world)
  }
}

function nodeWorldPosition(node) {
  const config = objectOrNull(node?.config)
  return {
    x: numberValue(config?.x, 0),
    y: numberValue(config?.y, 0),
  }
}

function childWorldPosition(child, parentWorld) {
  const config = objectOrNull(child?.config)
  return {
    x: config?.offsetX !== undefined
      ? parentWorld.x + numberValue(config.offsetX, 0)
      : config?.x !== undefined ? numberValue(config.x, 0) : parentWorld.x,
    y: config?.offsetY !== undefined
      ? parentWorld.y + numberValue(config.offsetY, 0)
      : config?.y !== undefined ? numberValue(config.y, 0) : parentWorld.y,
  }
}

function drawSelectedBoxHandles(ctx) {
  const desc = getSelectedBoxDescriptor()
  if (!desc) return
  const rect = descriptorRect(desc)
  if (!rect) return
  const hs = 8

  ctx.save()
  if (desc.shape === 'circle') {
    ctx.strokeStyle = desc.color
    ctx.fillStyle = `${desc.color}22`
    ctx.lineWidth = 2.5
    ctx.setLineDash([])
    ctx.beginPath()
    ctx.arc(rect.cx, rect.cy, rect.w / 2, 0, Math.PI * 2)
    ctx.fill()
    ctx.stroke()
  } else {
    drawOverlayRect(ctx, rect.x, rect.y, rect.w, rect.h, desc.color, {
      fill: `${desc.color}22`,
      radius: 5,
      width: 2.5,
    })
  }
  if (desc.canResize) {
    for (const [, hx, hy] of boxHandlePoints(rect)) {
      drawHandle(ctx, hx, hy, hs, desc.color)
    }
  }
  ctx.restore()
}

function drawOverlayRect(ctx, x, y, w, h, color, options = {}) {
  const radius = options.radius ?? 4
  const fill = options.fill || 'transparent'
  ctx.save()
  ctx.strokeStyle = color
  ctx.fillStyle = fill
  ctx.lineWidth = options.width ?? 1.5
  ctx.setLineDash(options.dash || [])
  roundedPath(ctx, x, y, w, h, radius)
  if (fill !== 'transparent') ctx.fill()
  ctx.stroke()
  ctx.restore()
}

function drawHandle(ctx, x, y, size, color) {
  const r = size / 2
  ctx.save()
  ctx.fillStyle = '#25231f'
  ctx.strokeStyle = color
  ctx.lineWidth = 1.75
  roundedPath(ctx, x - r, y - r, size, size, 2.5)
  ctx.fill()
  ctx.stroke()
  ctx.restore()
}

function roundedPath(ctx, x, y, w, h, radius) {
  const r = Math.max(0, Math.min(radius, Math.abs(w) / 2, Math.abs(h) / 2))
  if (ctx.roundRect) {
    ctx.beginPath()
    ctx.roundRect(x, y, w, h, r)
    return
  }
  ctx.beginPath()
  ctx.moveTo(x + r, y)
  ctx.lineTo(x + w - r, y)
  ctx.quadraticCurveTo(x + w, y, x + w, y + r)
  ctx.lineTo(x + w, y + h - r)
  ctx.quadraticCurveTo(x + w, y + h, x + w - r, y + h)
  ctx.lineTo(x + r, y + h)
  ctx.quadraticCurveTo(x, y + h, x, y + h - r)
  ctx.lineTo(x, y + r)
  ctx.quadraticCurveTo(x, y, x + r, y)
}

function getSelectedBoxDescriptor(target = editState?.selectedBoxTarget) {
  if (!target || !editState || !preview?.layout) return null
  if (target === 'frameVisual') return frameVisualBoxDescriptor()
  if (target === 'visual') return visualBoxDescriptor()
  if (target === 'collider') return colliderBoxDescriptor()
  const childMatch = target.match(/^child:(\d+):collider$/)
  if (childMatch) return childColliderBoxDescriptor(Number(childMatch[1]))
  return null
}

function frameVisualBoxDescriptor() {
  const visual = objectOrNull(editState?.data?.visual)
  const metrics = preview?.layout
  if (!visual || !metrics || !preview?.clipName || !preview?.clipAsset?.frames?.length) return null
  const timing = currentAnimationTiming(preview)
  const frame = preview.clipAsset.frames[timing.index]
  if (!frame) return null
  const transform = objectOrNull(editState.data.visualTransform)
  const visualOffsetX = numberValue(transform?.offsetX, 0)
  const visualOffsetY = numberValue(transform?.offsetY, 0)
  const frameOffset = Array.isArray(frame.offset) ? frame.offset : [0, 0]
  return {
    target: 'frameVisual',
    label: `Frame ${frame.label || timing.index} Offset`,
    color: '#d97757',
    shape: 'box',
    baseX: visualOffsetX,
    baseY: visualOffsetY,
    centerX: visualOffsetX + numberValue(frameOffset[0], 0),
    centerY: visualOffsetY + numberValue(frameOffset[1], 0),
    width: metrics.displayW,
    height: metrics.displayH,
    frameIndex: timing.index,
    pivot: metrics.pivot,
    canMove: true,
    canResize: false,
  }
}

function visualBoxDescriptor() {
  const visual = objectOrNull(editState?.data?.visual)
  const metrics = preview?.layout
  if (!visual || !metrics) return null
  const transform = objectOrNull(editState.data.visualTransform)
  const frameOffsetX = numberValue(metrics.frameOffsetX, 0)
  const frameOffsetY = numberValue(metrics.frameOffsetY, 0)
  const ratioMode = visual.ratio !== undefined && visual.width === undefined && visual.height === undefined && visual.type !== 'rect'
  return {
    target: 'visual',
    label: 'Visual',
    color: '#8fb6ff',
    shape: 'box',
    baseX: frameOffsetX,
    baseY: frameOffsetY,
    centerX: numberValue(transform?.offsetX, 0) + frameOffsetX,
    centerY: numberValue(transform?.offsetY, 0) + frameOffsetY,
    width: metrics.displayW,
    height: metrics.displayH,
    widthPath: ratioMode ? '' : 'visual.width',
    heightPath: ratioMode ? '' : 'visual.height',
    ratioPath: ratioMode ? 'visual.ratio' : '',
    sourceW: metrics.sourceW,
    sourceH: metrics.sourceH,
    baseSourceW: metrics.baseSourceW,
    baseSourceH: metrics.baseSourceH,
    pivot: metrics.pivot,
    offsetXPath: transform ? 'visualTransform.offsetX' : '',
    offsetYPath: transform ? 'visualTransform.offsetY' : '',
    canMove: Boolean(transform),
    canResize: true,
  }
}

function colliderBoxDescriptor() {
  const collider = objectOrNull(editState?.data?.collider)
  const metrics = preview?.layout
  if (!collider || !metrics) return null
  const shape = collider.shape === 'circle' ? 'circle' : 'box'
  const fallbackW = numberValue(metrics.baseDisplayW, metrics.displayW)
  const fallbackH = numberValue(metrics.baseDisplayH, metrics.displayH)
  const radius = numberValue(collider.radius, Math.min(fallbackW, fallbackH) / 2)
  return {
    target: 'collider',
    label: 'Collider',
    color: '#ff6b5f',
    shape,
    baseX: 0,
    baseY: 0,
    centerX: numberValue(collider.offsetX, 0),
    centerY: numberValue(collider.offsetY, 0),
    width: shape === 'circle' ? radius * 2 : numberValue(collider.width, fallbackW),
    height: shape === 'circle' ? radius * 2 : numberValue(collider.height, fallbackH),
    radius,
    pivot: resolveColliderPivot(collider, shape === 'circle'),
    widthPath: 'collider.width',
    heightPath: 'collider.height',
    radiusPath: 'collider.radius',
    offsetXPath: 'collider.offsetX',
    offsetYPath: 'collider.offsetY',
    canMove: true,
    canResize: true,
  }
}

function childColliderBoxDescriptor(index) {
  const child = editState?.data?.children?.[index]
  const collider = objectOrNull(child?.collider)
  const metrics = preview?.layout
  if (!child || !collider || !metrics) return null
  const visual = objectOrNull(child.visual)
  const offset = childOffset(child)
  const shape = collider.shape === 'circle' ? 'circle' : 'box'
  const fallbackW = numberValue(visual?.width, numberValue(metrics.baseDisplayW, metrics.displayW))
  const fallbackH = numberValue(visual?.height, numberValue(metrics.baseDisplayH, metrics.displayH))
  const radius = numberValue(collider.radius, Math.min(fallbackW, fallbackH) / 2)
  const base = `children.${index}.collider`
  return {
    target: `child:${index}:collider`,
    label: `${child.name || `Child ${index + 1}`} Collider`,
    color: '#ffd166',
    shape,
    baseX: offset.x,
    baseY: offset.y,
    centerX: offset.x + numberValue(collider.offsetX, 0),
    centerY: offset.y + numberValue(collider.offsetY, 0),
    width: shape === 'circle' ? radius * 2 : numberValue(collider.width, fallbackW),
    height: shape === 'circle' ? radius * 2 : numberValue(collider.height, fallbackH),
    radius,
    pivot: resolveChildColliderPivot(collider, shape === 'circle'),
    widthPath: `${base}.width`,
    heightPath: `${base}.height`,
    radiusPath: `${base}.radius`,
    offsetXPath: `${base}.offsetX`,
    offsetYPath: `${base}.offsetY`,
    canMove: true,
    canResize: true,
  }
}

function descriptorRect(desc, metrics = preview?.layout) {
  if (!desc || !metrics) return null
  const scale = metrics.scale
  const width = desc.shape === 'circle' ? desc.radius * 2 : desc.width
  const height = desc.shape === 'circle' ? desc.radius * 2 : desc.height
  const pivot = desc.pivot || [0.5, 0.5]
  const px = Number.isFinite(Number(pivot[0])) ? Number(pivot[0]) : 0.5
  const py = Number.isFinite(Number(pivot[1])) ? Number(pivot[1]) : 0.5
  const x = metrics.originX + (desc.centerX - width * px) * scale
  const y = metrics.originY + (desc.centerY - height * py) * scale
  const w = width * scale
  const h = height * scale
  return { x, y, w, h, cx: x + w * px, cy: y + h * py }
}

function boxHandlePoints(rect) {
  return [
    ['tl', rect.x, rect.y],
    ['tr', rect.x + rect.w, rect.y],
    ['bl', rect.x, rect.y + rect.h],
    ['br', rect.x + rect.w, rect.y + rect.h],
  ]
}

function drawOrigin(ctx, x, y) {
  ctx.save()
  ctx.fillStyle = 'rgba(123,224,165,0.16)'
  ctx.strokeStyle = '#7be0a5'
  ctx.lineWidth = 1.75
  ctx.beginPath()
  ctx.arc(x, y, 6, 0, Math.PI * 2)
  ctx.fill()
  ctx.stroke()
  ctx.beginPath()
  ctx.moveTo(x - 10, y)
  ctx.lineTo(x - 4, y)
  ctx.moveTo(x + 4, y)
  ctx.lineTo(x + 10, y)
  ctx.moveTo(x, y - 10)
  ctx.lineTo(x, y - 4)
  ctx.moveTo(x, y + 4)
  ctx.lineTo(x, y + 10)
  ctx.stroke()
  ctx.restore()
}

function drawPlaceholder(ctx, x, y, w, h, text) {
  ctx.fillStyle = 'rgba(217,119,87,0.08)'
  ctx.strokeStyle = 'rgba(217,119,87,0.45)'
  ctx.lineWidth = 1
  ctx.fillRect(x, y, w, h)
  ctx.strokeRect(x, y, w, h)
  ctx.fillStyle = '#8a867e'
  ctx.font = '12px system-ui'
  ctx.textAlign = 'center'
  ctx.fillText(text, x + w / 2, y + h / 2, Math.max(24, w - 12))
}

function drawCenteredText(ctx, w, h, text) {
  ctx.fillStyle = '#8a867e'
  ctx.font = '14px system-ui'
  ctx.textAlign = 'center'
  ctx.fillText(text, w / 2, h / 2)
}

function colliderRows(collider) {
  if (!collider) return [row('state', '(none)')]
  return [
    row('shape', collider.shape || 'box'),
    row('body', collider.body || 'dynamic'),
    row('host', collider.host || '(visual)'),
    editableNumberRow('width', 'collider.width', collider.width, { min: 1, placeholder: '(visual)' }),
    editableNumberRow('height', 'collider.height', collider.height, { min: 1, placeholder: '(visual)' }),
    editableNumberRow('radius', 'collider.radius', collider.radius, { min: 1, placeholder: '(none)' }),
    editableNumberRow('offsetX', 'collider.offsetX', collider.offsetX, { placeholder: '0' }),
    editableNumberRow('offsetY', 'collider.offsetY', collider.offsetY, { placeholder: '0' }),
  ]
}

function visualTransformRows(data) {
  const transform = objectOrNull(data.visualTransform)
  if (!transform) return ''
  return section('Visual Transform', [
    row('scope', 'all frames'),
    editableNumberRow('offsetX', 'visualTransform.offsetX', transform.offsetX, { placeholder: '0' }),
    editableNumberRow('offsetY', 'visualTransform.offsetY', transform.offsetY, { placeholder: '0' }),
  ])
}

function childRows(children) {
  if (!Array.isArray(children) || !children.length) return [row('state', 'No children')]
  return [`
    <div class="obj-child-list">
      ${children.map((child, index) => childButtonHTML(child, index)).join('')}
    </div>
    <div id="obj-child-detail" class="obj-child-detail">${childDetailHTML(null)}</div>
  `]
}

function childButtonHTML(child, index) {
  const name = child?.name || `Child ${index + 1}`
  return `
    <button type="button" class="obj-child-btn" data-child-index="${index}">
      <span>${esc(name)}</span>
      <em>${esc(childSummary(child))}</em>
    </button>`
}

function childSummary(child) {
  const collider = objectOrNull(child?.collider)
  const visual = objectOrNull(child?.visual)
  if (collider) {
    const shape = collider.shape || 'box'
    const size = collider.radius != null ? `r ${num(collider.radius)}` : `${num(collider.width)} x ${num(collider.height)}`
    return `collider ${shape} ${size}`
  }
  if (visual) return `visual ${visual.type || 'node'} ${visualSizeLabel(visual)}`
  return child?.script || 'node'
}

function childDetailHTML(child) {
  if (!child) return `<div class="obj-child-empty">Select a child to inspect its collider and config.</div>`
  const index = preview?.selectedChildIndex
  const base = Number.isInteger(index) ? `children.${index}` : ''
  const visual = objectOrNull(child.visual)
  const collider = objectOrNull(child.collider)
  const config = objectOrNull(child.config)
  const scriptConfig = config ? Object.fromEntries(Object.entries(config).filter(([key]) => key !== 'flipWithParent')) : null
  return `
    <div class="obj-child-heading">${esc(child.name || 'Child')}</div>
    ${row('script', child.script || '(none)')}
    ${row('visual', visual ? `${visual.type || '(unknown)'} ${visualSizeLabel(visual)}` : '(none)')}
    ${collider ? [
      targetHeading('Collider', `child:${index}:collider`, 'obj-title-swatch-child'),
      row('shape', collider.shape || 'box'),
      row('body', collider.body || '(none)'),
      editableNumberRow('width', `${base}.collider.width`, collider.width, { min: 1, placeholder: '(visual)' }),
      editableNumberRow('height', `${base}.collider.height`, collider.height, { min: 1, placeholder: '(visual)' }),
      editableNumberRow('radius', `${base}.collider.radius`, collider.radius, { min: 1, placeholder: '(none)' }),
      editableNumberRow('offsetX', `${base}.collider.offsetX`, collider.offsetX, { placeholder: '0' }),
      editableNumberRow('offsetY', `${base}.collider.offsetY`, collider.offsetY, { placeholder: '0' }),
    ].join('') : row('collider', '(none)')}
    ${row('offset', childOffsetLabel(child))}
    ${editablePrimitiveRow('flipWithParent', `${base}.config.flipWithParent`, config?.flipWithParent === true, 'boolean')}
    ${configRows(scriptConfig, `${base}.config`).join('')}`
}

function bindChildControls() {
  if (!panelBody) return
  panelBody.querySelectorAll('.obj-child-btn').forEach(btn => {
    btn.onclick = () => selectChild(Number(btn.dataset.childIndex))
  })
}

function bindEditorControls() {
  if (!panelBody) return
  panelBody.querySelectorAll('.obj-input').forEach(input => {
    input.onchange = () => applyInputChange(input)
  })
  panelBody.querySelectorAll('[data-bbox-target]').forEach(btn => {
    btn.onclick = () => selectBoxTarget(btn.dataset.bboxTarget || '')
  })
  const undoBtn = document.getElementById('obj-undo')
  const redoBtn = document.getElementById('obj-redo')
  const revertBtn = document.getElementById('obj-revert')
  const saveBtn = document.getElementById('obj-save')
  if (undoBtn) undoBtn.onclick = undoEdit
  if (redoBtn) redoBtn.onclick = redoEdit
  if (revertBtn) revertBtn.onclick = revertEdit
  if (saveBtn) saveBtn.onclick = saveEdit
  updateTargetButtons()
}

function selectBoxTarget(target) {
  if (!editState || !preview) return
  const current = editState.selectedBoxTarget
  editState.selectedBoxTarget = current === target ? null : target
  preview.selectedBoxTarget = editState.selectedBoxTarget
  if (editState.selectedBoxTarget && !getSelectedBoxDescriptor()) {
    editState.selectedBoxTarget = null
    preview.selectedBoxTarget = null
    setStatus('No editable bbox for this section')
  } else if (editState.selectedBoxTarget) {
    setStatus(`Selected ${getSelectedBoxDescriptor()?.label || 'bbox'}`)
  } else {
    setStatus('BBox selection cleared')
  }
  updateTargetButtons()
  drawPreview()
}

function updateTargetButtons() {
  if (!panelBody) return
  const target = editState?.selectedBoxTarget || ''
  panelBody.querySelectorAll('[data-bbox-target]').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.bboxTarget === target)
  })
}

function onCanvasMouseDown(event) {
  if (event.button !== 0 || !editState || editState.saving) return
  if (spaceDown) {
    startCanvasPan(event)
    return
  }
  const hit = hitActiveBox(canvasPoint(event))
  if (!hit.kind) return
  const desc = getSelectedBoxDescriptor()
  if (!desc) return
  event.preventDefault()
  const metrics = { ...preview.layout }
  canvasDrag = {
    mode: hit.kind,
    handle: hit.handle || '',
    target: desc.target,
    label: desc.label,
    before: cloneJSON(editState.data),
    startPoint: canvasPoint(event),
    startUnits: canvasToObjectUnits(canvasPoint(event), metrics),
    startDesc: cloneJSON({ ...desc, unitBox: descriptorUnitBox(desc) }),
    metrics,
    shiftKey: event.shiftKey,
    changed: false,
  }
  window.addEventListener('mousemove', onCanvasDragMove)
  window.addEventListener('mouseup', onCanvasDragEnd)
}

function onCanvasMouseMove(event) {
  const canvas = document.getElementById('obj-canvas')
  if (!canvas || canvasDrag || canvasPan) return
  if (spaceDown) {
    updateCanvasCursor()
    return
  }
  const hit = hitActiveBox(canvasPoint(event))
  const cursors = { tl: 'nw-resize', tr: 'ne-resize', bl: 'sw-resize', br: 'se-resize' }
  canvas.style.cursor = hit.kind === 'move' ? 'move' : hit.kind === 'resize' ? cursors[hit.handle] || 'default' : 'default'
}

function onCanvasWheel(event) {
  if (!preview?.layout) return
  event.preventDefault()
  const point = canvasPoint(event)
  const before = canvasToObjectUnits(point, preview.layout)
  const factor = Math.exp(-event.deltaY * 0.0012)
  const scale = Math.max(0.05, Math.min(64, preview.layout.scale * factor))
  canvasView = {
    scale,
    originX: point.x - before.x * scale,
    originY: point.y - before.y * scale,
  }
  drawPreview()
}

function startCanvasPan(event) {
  if (!preview?.layout) return
  event.preventDefault()
  canvasPan = {
    startPoint: canvasPoint(event),
    startView: {
      scale: preview.layout.scale,
      originX: preview.layout.originX,
      originY: preview.layout.originY,
    },
  }
  updateCanvasCursor()
  window.addEventListener('mousemove', onCanvasPanMove)
  window.addEventListener('mouseup', onCanvasPanEnd)
}

function onCanvasPanMove(event) {
  if (!canvasPan) return
  event.preventDefault()
  const point = canvasPoint(event)
  canvasView = {
    scale: canvasPan.startView.scale,
    originX: canvasPan.startView.originX + point.x - canvasPan.startPoint.x,
    originY: canvasPan.startView.originY + point.y - canvasPan.startPoint.y,
  }
  drawPreview()
}

function onCanvasPanEnd() {
  stopCanvasPan()
}

function onCanvasDragMove(event) {
  if (!canvasDrag || !editState) return
  event.preventDefault()
  canvasDrag.shiftKey = event.shiftKey
  applyCanvasDrag(canvasPoint(event))
}

function onCanvasDragEnd() {
  if (!canvasDrag || !editState) return
  if (canvasDrag.changed) {
    editState.undoStack.push(canvasDrag.before)
    editState.redoStack = []
    setStatus(`Adjusted ${canvasDrag.label}`)
  }
  const changed = canvasDrag.changed
  const target = canvasDrag.target
  stopCanvasDrag()
  if (changed) {
    if (target.startsWith('child:')) refreshChildUI()
    updateEditorButtons()
    updateTargetButtons()
    drawPreview()
  }
}

function stopCanvasDrag() {
  if (!canvasDrag) return
  window.removeEventListener('mousemove', onCanvasDragMove)
  window.removeEventListener('mouseup', onCanvasDragEnd)
  canvasDrag = null
  updateCanvasCursor()
}

function stopCanvasPan() {
  if (!canvasPan) return
  window.removeEventListener('mousemove', onCanvasPanMove)
  window.removeEventListener('mouseup', onCanvasPanEnd)
  canvasPan = null
  updateCanvasCursor()
}

function updateCanvasCursor() {
  const canvas = document.getElementById('obj-canvas')
  if (!canvas) return
  if (canvasPan) {
    canvas.style.cursor = 'grabbing'
    return
  }
  if (spaceDown) {
    canvas.style.cursor = 'grab'
    return
  }
  canvas.style.cursor = 'default'
}

function applyCanvasDrag(point) {
  const drag = canvasDrag
  const desc = drag?.startDesc
  if (!drag || !desc || !editState) return
  const current = canvasToObjectUnits(point, drag.metrics)
  let dx = current.x - drag.startUnits.x
  let dy = current.y - drag.startUnits.y
  if (drag.mode === 'move' && drag.shiftKey) {
    if (Math.abs(dx) >= Math.abs(dy)) dy = 0
    else dx = 0
  }
  const paths = new Set()

  if (drag.mode === 'move' && desc.canMove) {
    setDescriptorCenter(desc, desc.centerX + dx, desc.centerY + dy, paths)
  } else if (drag.mode === 'resize' && desc.canResize) {
    resizeDescriptor(desc, drag.handle, current, paths, { keepAspect: drag.shiftKey })
  }

  drag.changed = !jsonEqual(editState.data, drag.before)
  syncPreviewRefs()
  updateInputsForPaths(paths)
  updateChildButtons()
  updateEditorButtons()
  drawPreview()
}

function resizeDescriptor(desc, handle, current, paths, options = {}) {
  if (desc.shape === 'circle') {
    const radius = Math.max(1, Math.hypot(current.x - desc.centerX, current.y - desc.centerY))
    setNumberField(desc.radiusPath, radius, paths)
    return
  }
  const ob = desc.unitBox
  let { x, y, w, h } = options.keepAspect
    ? proportionalResizeBox(handle, current, ob)
    : { x: ob.x, y: ob.y, w: ob.w, h: ob.h }
  if (!options.keepAspect) {
    if (handle === 'tl') {
      x = current.x
      y = current.y
      w = ob.x + ob.w - current.x
      h = ob.y + ob.h - current.y
    } else if (handle === 'tr') {
      y = current.y
      w = current.x - ob.x
      h = ob.y + ob.h - current.y
    } else if (handle === 'bl') {
      x = current.x
      w = ob.x + ob.w - current.x
      h = current.y - ob.y
    } else if (handle === 'br') {
      w = current.x - ob.x
      h = current.y - ob.y
    }
  }
  if (w < 0) {
    x += w
    w = -w
  }
  if (h < 0) {
    y += h
    h = -h
  }
  w = Math.max(1, w)
  h = Math.max(1, h)
  if (desc.ratioPath) {
    const ratio = Math.max(
      w / Math.max(1, desc.sourceW || desc.width),
      h / Math.max(1, desc.sourceH || desc.height),
    )
    setNumberField(desc.ratioPath, ratio, paths, { round: false })
  } else {
    const widthValue = desc.widthPath === 'visual.width' && desc.baseSourceW && desc.sourceW
      ? w * Number(desc.baseSourceW) / Math.max(1, Number(desc.sourceW))
      : w
    const heightValue = desc.heightPath === 'visual.height' && desc.baseSourceH && desc.sourceH
      ? h * Number(desc.baseSourceH) / Math.max(1, Number(desc.sourceH))
      : h
    if (desc.widthPath) setNumberField(desc.widthPath, widthValue, paths)
    if (desc.heightPath) setNumberField(desc.heightPath, heightValue, paths)
  }
  const pivot = desc.pivot || [0.5, 0.5]
  const px = Number.isFinite(Number(pivot[0])) ? Number(pivot[0]) : 0.5
  const py = Number.isFinite(Number(pivot[1])) ? Number(pivot[1]) : 0.5
  if (desc.canMove) setDescriptorCenter(desc, x + w * px, y + h * py, paths)
}

function proportionalResizeBox(handle, current, ob) {
  const aspect = Math.max(0.0001, ob.w / Math.max(0.0001, ob.h))
  let fixedX = ob.x
  let fixedY = ob.y
  let rawW = ob.w
  let rawH = ob.h
  if (handle === 'tl') {
    fixedX = ob.x + ob.w
    fixedY = ob.y + ob.h
    rawW = fixedX - current.x
    rawH = fixedY - current.y
  } else if (handle === 'tr') {
    fixedX = ob.x
    fixedY = ob.y + ob.h
    rawW = current.x - fixedX
    rawH = fixedY - current.y
  } else if (handle === 'bl') {
    fixedX = ob.x + ob.w
    fixedY = ob.y
    rawW = fixedX - current.x
    rawH = current.y - fixedY
  } else if (handle === 'br') {
    fixedX = ob.x
    fixedY = ob.y
    rawW = current.x - fixedX
    rawH = current.y - fixedY
  }

  const signW = rawW < 0 ? -1 : 1
  const signH = rawH < 0 ? -1 : 1
  let absW = Math.max(1, Math.abs(rawW))
  let absH = Math.max(1, Math.abs(rawH))
  if (absW / Math.max(1, ob.w) >= absH / Math.max(1, ob.h)) {
    absH = absW / aspect
  } else {
    absW = absH * aspect
  }
  const w = absW * signW
  const h = absH * signH
  if (handle === 'tl') return { x: fixedX - w, y: fixedY - h, w, h }
  if (handle === 'tr') return { x: fixedX, y: fixedY - h, w, h }
  if (handle === 'bl') return { x: fixedX - w, y: fixedY, w, h }
  return { x: fixedX, y: fixedY, w, h }
}

function setDescriptorCenter(desc, centerX, centerY, paths) {
  if (desc.target === 'frameVisual') {
    setFrameOffsetAt(desc.frameIndex, [centerX - desc.baseX, centerY - desc.baseY], paths)
    return
  }
  if (desc.offsetXPath) setNumberField(desc.offsetXPath, centerX - desc.baseX, paths)
  if (desc.offsetYPath) setNumberField(desc.offsetYPath, centerY - desc.baseY, paths)
}

function setNumberField(path, value, paths, options = {}) {
  if (!path) return
  const rounded = options.round === false ? Number(value.toFixed(4)) : Math.round(value)
  setPath(editState.data, path, rounded)
  delete editErrors[path]
  paths.add(path)
}

function hitActiveBox(point) {
  const desc = getSelectedBoxDescriptor()
  if (!desc) return { kind: '' }
  const rect = descriptorRect(desc)
  if (!rect) return { kind: '' }
  const hs = 8
  if (desc.canResize) {
    for (const [handle, hx, hy] of boxHandlePoints(rect)) {
      if (Math.abs(point.x - hx) <= hs && Math.abs(point.y - hy) <= hs) {
        return { kind: 'resize', handle }
      }
    }
  }
  if (!desc.canMove) return { kind: '' }
  if (desc.shape === 'circle') {
    const dist = Math.hypot(point.x - rect.cx, point.y - rect.cy)
    return dist <= rect.w / 2 ? { kind: 'move' } : { kind: '' }
  }
  if (point.x >= rect.x && point.x <= rect.x + rect.w && point.y >= rect.y && point.y <= rect.y + rect.h) {
    return { kind: 'move' }
  }
  if (desc.target === 'frameVisual') {
    const pad = 8
    if (point.x >= rect.x - pad && point.x <= rect.x + rect.w + pad && point.y >= rect.y - pad && point.y <= rect.y + rect.h + pad) {
      return { kind: 'move' }
    }
  }
  return { kind: '' }
}

function descriptorUnitBox(desc) {
  const width = desc.shape === 'circle' ? desc.radius * 2 : desc.width
  const height = desc.shape === 'circle' ? desc.radius * 2 : desc.height
  const pivot = desc.pivot || [0.5, 0.5]
  const px = Number.isFinite(Number(pivot[0])) ? Number(pivot[0]) : 0.5
  const py = Number.isFinite(Number(pivot[1])) ? Number(pivot[1]) : 0.5
  return {
    x: desc.centerX - width * px,
    y: desc.centerY - height * py,
    w: width,
    h: height,
  }
}

function canvasPoint(event) {
  const canvas = document.getElementById('obj-canvas')
  const rect = canvas.getBoundingClientRect()
  return { x: event.clientX - rect.left, y: event.clientY - rect.top }
}

function canvasToObjectUnits(point, metrics = preview?.layout) {
  return {
    x: (point.x - metrics.originX) / metrics.scale,
    y: (point.y - metrics.originY) / metrics.scale,
  }
}

function updateInputsForPaths(paths) {
  if (!paths.size || !panelBody) return
  panelBody.querySelectorAll('.obj-input').forEach(input => {
    const path = input.dataset.path
    if (!paths.has(path)) return
    const value = getPath(editState.data, path)
    if (input.type === 'checkbox') {
      input.checked = Boolean(value)
    } else {
      input.value = value == null ? '' : String(value)
    }
    clearInputError(input)
  })
  refreshBooleanLabels()
}

function updateChildButtons() {
  if (!preview || !panelBody) return
  panelBody.querySelectorAll('.obj-child-btn').forEach(btn => {
    const index = Number(btn.dataset.childIndex)
    const child = preview.children[index]
    if (!child) return
    const em = btn.querySelector('em')
    if (em) em.textContent = childSummary(child)
  })
}

function applyInputChange(input) {
  if (!editState) return
  const path = input.dataset.path
  if (!path) return
  const parsed = parseInputValue(input)
  if (parsed.error) {
    setInputError(input, parsed.error)
    updateEditorButtons()
    return
  }
  const before = cloneJSON(editState.data)
  const paths = new Set([path])
  if (parsed.deleteValue) {
    deletePath(editState.data, path)
  } else {
    setPath(editState.data, path, parsed.value)
    normalizeVisualSizeFields(path, paths)
  }
  if (JSON.stringify(before) === JSON.stringify(editState.data)) {
    clearInputError(input)
    updateEditorButtons()
    return
  }
  editState.undoStack.push(before)
  editState.redoStack = []
  editState.dirty = !jsonEqual(editState.data, editState.savedData)
  clearInputError(input)
  syncPreviewRefs()
  refreshDerivedUI(path)
  updateInputsForPaths(paths)
  updateEditorButtons()
  drawPreview()
}

function normalizeVisualSizeFields(path, paths) {
  if (path === 'visual.ratio') {
    deletePath(editState.data, 'visual.width')
    deletePath(editState.data, 'visual.height')
    paths.add('visual.width')
    paths.add('visual.height')
    return
  }
  if (path === 'visual.width' || path === 'visual.height') {
    deletePath(editState.data, 'visual.ratio')
    paths.add('visual.ratio')
    if (path === 'visual.width' && getPath(editState.data, 'visual.height') === undefined) {
      setPath(editState.data, 'visual.height', Math.round(preview?.layout?.displayH || 1))
      paths.add('visual.height')
    }
    if (path === 'visual.height' && getPath(editState.data, 'visual.width') === undefined) {
      setPath(editState.data, 'visual.width', Math.round(preview?.layout?.displayW || 1))
      paths.add('visual.width')
    }
  }
}

function parseInputValue(input) {
  const type = input.dataset.type
  if (type === 'boolean') return { value: Boolean(input.checked) }
  if (type === 'number') {
    const raw = String(input.value || '').trim()
    if (!raw) {
      if (input.dataset.optional === 'true') return { deleteValue: true }
      return { error: 'Required number' }
    }
    const value = Number(raw)
    if (!Number.isFinite(value)) return { error: 'Invalid number' }
    const min = input.dataset.min === '' || input.dataset.min == null ? null : Number(input.dataset.min)
    const max = input.dataset.max === '' || input.dataset.max == null ? null : Number(input.dataset.max)
    if (Number.isFinite(min) && value < min) return { error: `Must be >= ${min}` }
    if (Number.isFinite(max) && value > max) return { error: `Must be <= ${max}` }
    return { value }
  }
  const value = input.value
  if (input.dataset.optional === 'true' && value === '') return { deleteValue: true }
  return { value }
}

function setInputError(input, message) {
  editErrors[input.dataset.path] = message
  input.classList.add('invalid')
  input.title = message
  setStatus(message)
}

function clearInputError(input) {
  delete editErrors[input.dataset.path]
  input.classList.remove('invalid')
  input.title = ''
}

function syncPreviewRefs() {
  if (!preview || !editState) return
  preview.node = editState.data
  preview.visual = objectOrNull(editState.data.visual)
  preview.collider = objectOrNull(editState.data.collider)
  preview.children = Array.isArray(editState.data.children) ? editState.data.children : []
  preview.animations = objectOrNull(editState.data.animations)
  preview.selectedBoxTarget = editState.selectedBoxTarget
  if (preview.clipName) preview.clip = preview.animations?.clips?.[preview.clipName] || null
}

function refreshDerivedUI(path) {
  if (path.startsWith('visual.frame') && preview?.asset?.info && preview.asset?.img && preview.visual) {
    preview.asset.crop = resolveCrop(preview.visual, preview.asset.info, preview.asset.img)
  }
  if (path.startsWith('children.')) refreshChildUI()
  if (path.startsWith('animations.')) {
    if (preview?.clipName && !preview.animations?.clips?.[preview.clipName]) clearAnimationPreview()
  }
  refreshBooleanLabels()
}

function refreshChildUI() {
  if (!preview) return
  panelBody.querySelectorAll('.obj-child-btn').forEach(btn => {
    const index = Number(btn.dataset.childIndex)
    const child = preview.children[index]
    if (!child) return
    const span = btn.querySelector('span')
    const em = btn.querySelector('em')
    if (span) span.textContent = child.name || `Child ${index + 1}`
    if (em) em.textContent = childSummary(child)
  })
  const detail = document.getElementById('obj-child-detail')
  if (detail && preview.selectedChildIndex != null) {
    detail.innerHTML = childDetailHTML(preview.children[preview.selectedChildIndex])
    bindEditorControls()
  }
}

function refreshBooleanLabels() {
  panelBody.querySelectorAll('.obj-config-check .obj-input[type="checkbox"]').forEach(input => {
    const label = input.parentElement?.querySelector('span')
    if (label) label.textContent = input.checked ? 'true' : 'false'
  })
}

function updateEditorButtons() {
  if (!editState) return
  const hasErrors = Object.keys(editErrors).length > 0
  editState.dirty = !jsonEqual(editState.data, editState.savedData)
  const undoBtn = document.getElementById('obj-undo')
  const redoBtn = document.getElementById('obj-redo')
  const revertBtn = document.getElementById('obj-revert')
  const saveBtn = document.getElementById('obj-save')
  const dirty = document.getElementById('obj-dirty')
  if (undoBtn) undoBtn.disabled = !editState.undoStack.length || editState.saving
  if (redoBtn) redoBtn.disabled = !editState.redoStack.length || editState.saving
  if (revertBtn) revertBtn.disabled = (!editState.dirty && !editState.undoStack.length) || editState.saving
  if (saveBtn) saveBtn.disabled = !editState.dirty || hasErrors || editState.saving
  if (dirty) {
    dirty.textContent = hasErrors ? 'Invalid' : editState.dirty ? 'Unsaved' : 'Saved'
    dirty.classList.toggle('invalid', hasErrors)
    dirty.classList.toggle('dirty', editState.dirty && !hasErrors)
  }
}

function undoEdit() {
  if (!editState?.undoStack.length) return
  stopAnimationLoop()
  editState.redoStack.push(cloneJSON(editState.data))
  editState.data = editState.undoStack.pop()
  editErrors = {}
  rerenderCurrentObject('Undo')
}

function redoEdit() {
  if (!editState?.redoStack.length) return
  stopAnimationLoop()
  editState.undoStack.push(cloneJSON(editState.data))
  editState.data = editState.redoStack.pop()
  editErrors = {}
  rerenderCurrentObject('Redo')
}

async function saveEdit() {
  if (!editState || editState.saving || Object.keys(editErrors).length) return
  const changes = diffJSON(editState.savedData, editState.data)
  if (!changes.length) {
    updateEditorButtons()
    return
  }
  editState.saving = true
  updateEditorButtons()
  const result = await api.putNode(editState.path, editState.data, changes, 'save')
  editState.saving = false
  if (result.error) {
    setStatus(`Save failed: ${result.error}`)
    updateEditorButtons()
    return
  }
  editState.savedData = cloneJSON(editState.data)
  editState.undoStack = []
  editState.redoStack = []
  editState.dirty = false
  updateEditorButtons()
  setStatus(`Saved ${editState.path}`)
}

async function revertEdit() {
  if (!editState || editState.saving) return
  const reverted = cloneJSON(editState.savedData)
  const changes = diffJSON(editState.data, reverted)
  editState.data = reverted
  editState.undoStack = []
  editState.redoStack = []
  editErrors = {}
  if (changes.length) {
    editState.saving = true
    updateEditorButtons()
    const result = await api.putNode(editState.path, editState.data, changes, 'revert')
    editState.saving = false
    if (result.error) {
      setStatus(`Revert failed: ${result.error}`)
      updateEditorButtons()
      return
    }
  }
  rerenderCurrentObject('Reverted')
}

function rerenderCurrentObject(statusMessage) {
  if (!editState) return
  const path = editState.path
  const data = cloneJSON(editState.data)
  const savedData = cloneJSON(editState.savedData)
  const undoStack = editState.undoStack.map(cloneJSON)
  const redoStack = editState.redoStack.map(cloneJSON)
  const selectedChildIndex = editState.selectedChildIndex
  const selectedBoxTarget = editState.selectedBoxTarget
  const animationState = preview ? {
    clipName: preview.clipName,
    pausedFrameIndex: preview.pausedFrameIndex,
    animationPlaying: preview.animationPlaying,
    selectedBoxTarget,
  } : null
  const previousCanvasView = canvasView ? { ...canvasView } : null
  renderObject(path, data).then(() => {
    if (!editState) return
    editState.savedData = savedData
    editState.undoStack = undoStack
    editState.redoStack = redoStack
    editState.selectedBoxTarget = selectedBoxTarget
    if (preview) preview.selectedBoxTarget = selectedBoxTarget
    editState.dirty = !jsonEqual(editState.data, editState.savedData)
    if (previousCanvasView) canvasView = previousCanvasView
    if (selectedChildIndex != null && preview?.children?.[selectedChildIndex]) {
      selectChild(selectedChildIndex)
    }
    restoreAnimationState(animationState).then(() => {
      updateTargetButtons()
      updateEditorButtons()
      setStatus(statusMessage)
    })
  })
}

async function restoreAnimationState(state) {
  if (!state?.clipName || !preview?.animations?.clips?.[state.clipName]) {
    updateTargetButtons()
    updateEditorButtons()
    drawPreview()
    return
  }
  preview.clipName = state.clipName
  preview.clip = preview.animations.clips[state.clipName]
  preview.clipAsset = { error: 'Loading clip...' }
  preview.animationPlaying = false
  preview.pausedFrameIndex = Math.max(0, Number(state.pausedFrameIndex) || 0)
  renderObjectAnimationRail()
  drawPreview()

  const token = ++renderToken
  const clipAsset = await loadClipAsset(preview.clip, preview.visual)
  if (token !== renderToken || preview.clipName !== state.clipName) return
  preview.clipAsset = clipAsset
  const max = Math.max(0, (clipAsset.frames?.length || 1) - 1)
  preview.pausedFrameIndex = Math.min(preview.pausedFrameIndex, max)
  preview.animationPlaying = state.animationPlaying === true
  if (state.selectedBoxTarget === 'frameVisual') {
    preview.animationPlaying = false
    editState.selectedBoxTarget = 'frameVisual'
    preview.selectedBoxTarget = 'frameVisual'
  }
  renderObjectAnimationRail()
  updateReadout(currentAnimationFrame(preview))
  drawPreview()
  if (preview.animationPlaying) startAnimationLoop()
}

function selectChild(index) {
  if (!preview?.children?.[index]) return
  const nextIndex = preview.selectedChildIndex === index ? null : index
  preview.selectedChildIndex = nextIndex
  if (editState) editState.selectedChildIndex = nextIndex
  if (editState?.selectedBoxTarget?.startsWith('child:')) {
    const expected = Number.isInteger(nextIndex) ? `child:${nextIndex}:collider` : ''
    if (editState.selectedBoxTarget !== expected) {
      editState.selectedBoxTarget = null
      preview.selectedBoxTarget = null
    }
  }
  panelBody.querySelectorAll('.obj-child-btn').forEach(btn => {
    btn.classList.toggle('active', Number(btn.dataset.childIndex) === nextIndex)
  })
  const detail = document.getElementById('obj-child-detail')
  if (detail) detail.innerHTML = childDetailHTML(nextIndex == null ? null : preview.children[nextIndex])
  bindEditorControls()
  updateTargetButtons()
  drawPreview()
  setStatus(nextIndex == null ? 'Parent object preview' : `Selected child ${preview.children[nextIndex].name || nextIndex + 1}`)
}

function childOffset(child) {
  const config = objectOrNull(child?.config)
  return {
    x: numberValue(config?.offsetX ?? config?.x ?? child?.offsetX ?? child?.x, 0),
    y: numberValue(config?.offsetY ?? config?.y ?? child?.offsetY ?? child?.y, 0),
  }
}

function childOffsetLabel(child) {
  const offset = childOffset(child)
  return `${offset.x} , ${offset.y}`
}

function animationRows(animations, activeClip) {
  if (!animations?.clips || typeof animations.clips !== 'object') return [row('state', 'No clips')]
  const clipEntries = Object.entries(animations.clips)
  if (!clipEntries.length) return [row('state', 'No clips')]
  const rows = [editableSelectRow('default', 'animations.default', animations.default || '', clipEntries.map(([name]) => name))]
  rows.push(`
    <div class="obj-clip-list">
      ${clipEntries.map(([name, clip]) => `
        <button type="button" class="obj-clip-btn ${name === activeClip ? 'active' : ''}" data-clip="${esc(name)}">
          <span>${esc(name)}</span>
          <em>${esc(clipFrameRate(clip))} fps</em>
        </button>
      `).join('')}
    </div>
  `)
  for (const [name, clip] of Object.entries(animations.clips)) {
    rows.push(editableNumberRow(`${name} fps`, `animations.clips.${name}.frameRate`, clip?.frameRate ?? 10, { min: 0.01 }))
  }
  return rows
}

function bindAnimationControls() {
  if (!panelBody) return
  panelBody.querySelectorAll('.obj-clip-btn').forEach(btn => {
    btn.onclick = () => selectClip(btn.dataset.clip || '')
  })
  bindObjectAnimationRail()
}

async function selectClip(name) {
  if (!preview?.animations?.clips?.[name]) return
  stopAnimationLoop()
  if (preview.clipName === name) {
    clearAnimationPreview()
    return
  }
  panelBody.querySelectorAll('.obj-clip-btn').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.clip === name)
  })
  preview.clipName = name
  preview.clip = preview.animations.clips[name]
  preview.clipAsset = { error: 'Loading clip...' }
  preview.animationPlaying = true
  preview.pausedFrameIndex = 0
  preview.animationStartedAt = performance.now()
  renderObjectAnimationRail()
  updateReadout()
  drawPreview()

  const token = ++renderToken
  const clipAsset = await loadClipAsset(preview.clip, preview.visual)
  if (token !== renderToken || preview.clipName !== name) return
  preview.clipAsset = clipAsset
  preview.pausedFrameIndex = 0
  preview.animationPlaying = false
  selectFrameVisualTarget()
  renderObjectAnimationRail()
  updateReadout()
  drawPreview()
  setStatus(`Editing frame offset for ${name}`)
}

function clearAnimationPreview() {
  stopAnimationLoop()
  renderToken += 1
  if (editState?.selectedBoxTarget === 'frameVisual') {
    editState.selectedBoxTarget = null
    if (preview) preview.selectedBoxTarget = null
  }
  panelBody.querySelectorAll('.obj-clip-btn').forEach(btn => btn.classList.remove('active'))
  preview.clipName = ''
  preview.clip = null
  preview.clipAsset = null
  preview.animationPlaying = true
  preview.pausedFrameIndex = 0
  preview.animationStartedAt = performance.now()
  renderObjectAnimationRail()
  updateReadout()
  drawPreview()
  setStatus('Static texture preview')
}

function clipFrameRate(clip) {
  const fps = Number(clip?.frameRate)
  return Number.isFinite(fps) && fps > 0 ? fps : 10
}

function clipFrameDurations(clip, count) {
  const fpsDuration = 1000 / clipFrameRate(clip)
  const durations = Array.isArray(clip?.frameDurations) ? clip.frameDurations : []
  return Array.from({ length: count }, (_, i) => {
    const ms = Number(durations[i])
    return Number.isFinite(ms) && ms > 0 ? ms : fpsDuration
  })
}

function currentAnimationFrame(state) {
  if (!state?.clip || !state?.clipAsset?.frames?.length) return null
  const timing = currentAnimationTiming(state)
  const frame = state.clipAsset.frames[timing.index]
  return frame ? { ...frame, index: timing.index, count: state.clipAsset.frames.length } : null
}

function currentAnimationTiming(state) {
  if (!state?.clip || !state?.clipAsset?.frames?.length) return { index: 0, progress: 0 }
  const frames = state.clipAsset.frames
  const durations = clipFrameDurations(state.clip, frames.length)
  const total = durations.reduce((sum, ms) => sum + ms, 0)
  if (total <= 0) return { index: 0, progress: 0 }
  if (state.animationPlaying === false) {
    const index = Math.max(0, Math.min(state.pausedFrameIndex ?? 0, frames.length - 1))
    const before = durations.slice(0, index).reduce((sum, ms) => sum + ms, 0)
    return { index, progress: (before + durations[index] / 2) / total }
  }
  let elapsed = Math.max(0, performance.now() - state.animationStartedAt)
  if (state.clip.loop === false) {
    elapsed = Math.min(elapsed, total - 1)
  } else {
    elapsed = elapsed % total
  }
  let index = 0
  let cursor = 0
  for (let i = 0; i < durations.length; i++) {
    cursor += durations[i]
    if (elapsed < cursor) { index = i; break }
  }
  return { index, progress: elapsed / total }
}

function startAnimationLoop() {
  stopAnimationLoop()
  if (!preview?.clip || preview.animationPlaying === false) return
  const tick = () => {
    drawPreview()
    animationFrameId = requestAnimationFrame(tick)
  }
  animationFrameId = requestAnimationFrame(tick)
}

function stopAnimationLoop() {
  if (animationFrameId) {
    cancelAnimationFrame(animationFrameId)
    animationFrameId = 0
  }
}

function renderObjectAnimationRail() {
  const rail = document.getElementById('obj-anim-rail')
  if (!rail) return
  const frames = preview?.clipAsset?.frames || []
  if (!preview?.clipName || !frames.length) {
    rail.innerHTML = ''
    return
  }
  const current = currentAnimationTiming(preview).index
  const currentFrame = frames[current] || frames[0]
  const offset = currentFrame?.offset || [0, 0]
  const offsetPath = `animations.clips.${preview.clipName}.frames[${current}].offset`
  rail.innerHTML = `
    <div class="obj-anim-rail-head">
      <span>${esc(preview.clipName)}</span>
      <button type="button" class="obj-anim-play" id="obj-anim-play">${preview.animationPlaying === false ? 'Play' : 'Pause'}</button>
    </div>
    <div class="obj-anim-rail-track">
      ${frames.map((frame, i) => `
        <button type="button" class="obj-anim-tick" data-obj-seek-frame="${i}" title="${esc(frame.label || `frame_${i}`)}">
          <canvas width="34" height="34"></canvas>
        </button>`).join('')}
    </div>
    <div class="obj-anim-offset">
      <div class="obj-anim-offset-head">
        <span>Frame Offset <strong>${esc(currentFrame?.label || `frame_${current}`)}</strong></span>
        <code>${esc(offsetPath)}</code>
      </div>
      <label>
        <span>x</span>
        <input type="number" step="1" data-obj-frame-offset="x" value="${formatNumber(offset[0] || 0)}">
      </label>
      <label>
        <span>y</span>
        <input type="number" step="1" data-obj-frame-offset="y" value="${formatNumber(offset[1] || 0)}">
      </label>
    </div>`
  bindObjectAnimationRail()
  drawObjectAnimationRailThumbs()
  updateObjectAnimationRail(currentAnimationTiming(preview))
}

function bindObjectAnimationRail() {
  const rail = document.getElementById('obj-anim-rail')
  if (!rail || !preview) return
  const play = document.getElementById('obj-anim-play')
  if (play) play.onclick = () => {
    const nextPlaying = preview.animationPlaying === false
    preview.animationPlaying = nextPlaying
    preview.animationStartedAt = performance.now()
    if (nextPlaying && editState?.selectedBoxTarget === 'frameVisual') {
      editState.selectedBoxTarget = null
      preview.selectedBoxTarget = null
    } else if (!nextPlaying) {
      selectFrameVisualTarget()
    }
    renderObjectAnimationRail()
    drawPreview()
    if (preview.animationPlaying) startAnimationLoop()
    else stopAnimationLoop()
  }
  rail.querySelectorAll('[data-obj-seek-frame]').forEach(button => {
    button.onclick = () => {
      const idx = Number(button.dataset.objSeekFrame)
      if (!Number.isInteger(idx)) return
      stopAnimationLoop()
      preview.animationPlaying = false
      preview.pausedFrameIndex = idx
      selectFrameVisualTarget()
      renderObjectAnimationRail()
      updateReadout(currentAnimationFrame(preview))
      drawPreview()
      setStatus(`Paused ${preview.clipName} on frame ${idx + 1}`)
    }
  })
  rail.querySelectorAll('[data-obj-frame-offset]').forEach(input => {
    input.onchange = () => {
      const axis = input.dataset.objFrameOffset
      const value = Number(input.value)
      if (!Number.isFinite(value)) return
      setCurrentFrameOffset(axis, value)
    }
  })
}

function selectFrameVisualTarget() {
  if (!editState || !preview?.clipName) return
  const timing = currentAnimationTiming(preview)
  preview.animationPlaying = false
  preview.pausedFrameIndex = timing.index
  stopAnimationLoop()
  editState.selectedBoxTarget = 'frameVisual'
  preview.selectedBoxTarget = 'frameVisual'
  updateTargetButtons()
}

function setCurrentFrameOffset(axis, value) {
  if (!editState || !preview?.clipName || !preview?.clipAsset?.frames?.length) return
  const index = currentAnimationTiming(preview).index
  const before = cloneJSON(editState.data)
  const offset = frameRefOffset(preview.clip?.frames?.[index])
  if (axis === 'x') offset[0] = value
  if (axis === 'y') offset[1] = value
  const paths = new Set()
  setFrameOffsetAt(index, offset, paths)

  if (jsonEqual(before, editState.data)) return
  editState.undoStack.push(before)
  editState.redoStack = []
  editState.dirty = !jsonEqual(editState.data, editState.savedData)
  syncPreviewRefs()
  updateFrameOffsetInputs(index, offset)
  updateEditorButtons()
  renderObjectAnimationRail()
  drawPreview()
  setStatus(`Adjusted ${preview.clipName} frame ${index + 1} offset`)
}

function setFrameOffsetAt(index, offset, paths = new Set()) {
  if (!editState || !preview?.clipName) return
  const framesPath = `animations.clips.${preview.clipName}.frames`
  const frames = getPath(editState.data, framesPath)
  if (!Array.isArray(frames) || frames[index] === undefined) return
  const frameRef = frames[index]
  const nextRef = objectOrNull(frameRef) ? cloneJSON(frameRef) : { frame: frameRef }
  const x = Math.round(numberValue(offset[0], 0))
  const y = Math.round(numberValue(offset[1], 0))
  nextRef.offset = [x, y]
  frames[index] = nextRef
  paths.add(`${framesPath}[${index}].offset`)
  if (preview.clipAsset?.frames?.[index]) preview.clipAsset.frames[index].offset = [x, y]
  updateFrameOffsetInputs(index, [x, y])
}

function updateFrameOffsetInputs(index, offset) {
  const rail = document.getElementById('obj-anim-rail')
  if (!rail) return
  const current = currentAnimationTiming(preview).index
  if (current !== index) return
  const x = rail.querySelector('[data-obj-frame-offset="x"]')
  const y = rail.querySelector('[data-obj-frame-offset="y"]')
  if (x) x.value = formatNumber(offset[0] || 0)
  if (y) y.value = formatNumber(offset[1] || 0)
}

function drawObjectAnimationRailThumbs() {
  const rail = document.getElementById('obj-anim-rail')
  const img = preview?.clipAsset?.img
  if (!rail || !img) return
  const frames = preview?.clipAsset?.frames || []
  rail.querySelectorAll('[data-obj-seek-frame]').forEach(button => {
    const idx = Number(button.dataset.objSeekFrame)
    const frame = frames[idx]
    const thumb = button.querySelector('canvas')
    if (!frame?.crop || !thumb) return
    const ctx = thumb.getContext('2d')
    ctx.clearRect(0, 0, thumb.width, thumb.height)
    const [sx, sy, sw, sh] = frame.crop
    const scale = Math.min(30 / sw, 30 / sh, 4)
    const dw = sw * scale
    const dh = sh * scale
    ctx.imageSmoothingEnabled = false
    ctx.drawImage(img, sx, sy, sw, sh, (thumb.width - dw) / 2, (thumb.height - dh) / 2, dw, dh)
  })
}

function updateObjectAnimationRail(timing) {
  const rail = document.getElementById('obj-anim-rail')
  if (!rail) return
  rail.querySelectorAll('[data-obj-seek-frame]').forEach((el, i) => {
    el.classList.toggle('active', i === timing.index)
  })
}

function updateReadout(animationFrame = null) {
  const readout = document.getElementById('obj-readout')
  if (!readout || !preview) return
  readout.textContent = previewLabel(preview.node, preview.asset, animationFrame)
}

function configRows(config, basePath = 'config') {
  if (!config || !Object.keys(config).length) return [row('state', '(empty)')]
  return flattenConfig(config).map(item => configRow(item.path, `${basePath}.${item.path}`, item.value))
}

function flattenConfig(value, prefix = '') {
  if (!objectOrNull(value)) return [{ path: prefix || 'value', value }]
  const rows = []
  for (const [key, child] of Object.entries(value)) {
    const path = prefix ? `${prefix}.${key}` : key
    if (objectOrNull(child) && Object.keys(child).length) {
      rows.push(...flattenConfig(child, path))
    } else {
      rows.push({ path, value: child })
    }
  }
  return rows
}

function configRow(label, path, value) {
  const type = configType(value)
  if (isEditablePrimitive(value)) {
    return editablePrimitiveRow(label, path, value, type)
  }
  return `
    <div class="obj-config-row">
      <span class="obj-config-key" title="${esc(label)}">${esc(label)}</span>
      <strong class="obj-config-field" title="${esc(formatConfigValue(value))}">${configValueHTML(value)}</strong>
      <em class="obj-config-type">${esc(type)}</em>
    </div>`
}

function configValueHTML(value) {
  if (typeof value === 'boolean') {
    return `<span class="obj-config-check"><input type="checkbox" ${value ? 'checked' : ''} disabled><span>${value ? 'true' : 'false'}</span></span>`
  }
  return esc(formatConfigValue(value))
}

function formatConfigValue(value) {
  if (value == null) return '(null)'
  if (Array.isArray(value)) return `[${value.map(formatConfigValue).join(', ')}]`
  if (objectOrNull(value)) return Object.keys(value).length ? '(object)' : '(empty object)'
  return String(value)
}

function configType(value) {
  if (Array.isArray(value)) return 'array'
  if (value == null) return 'null'
  return typeof value
}

function section(title, rows, options = {}) {
  const swatch = options.swatch ? `<span class="obj-title-swatch ${esc(options.swatch)}"></span>` : ''
  const heading = options.target
    ? targetHeading(title, options.target, options.swatch)
    : `<h3>${esc(title)}${swatch}</h3>`
  return `<section class="obj-section">${heading}${rows.join('')}</section>`
}

function targetHeading(title, target, swatchClass = '') {
  const swatch = swatchClass ? `<span class="obj-title-swatch ${esc(swatchClass)}"></span>` : ''
  return `
    <h3>
      <button type="button" class="obj-section-target" data-bbox-target="${esc(target)}">
        <span>${esc(title)}</span>${swatch}
      </button>
    </h3>`
}

function row(label, value) {
  return `<div class="obj-row"><span>${esc(label)}</span><strong>${esc(value)}</strong></div>`
}

function editableNumberRow(label, path, value, options = {}) {
  const placeholder = options.placeholder || ''
  const attrs = [
    `data-path="${esc(path)}"`,
    'data-type="number"',
    placeholder ? 'data-optional="true"' : '',
    options.min != null ? `data-min="${esc(options.min)}"` : '',
    options.max != null ? `data-max="${esc(options.max)}"` : '',
  ].filter(Boolean).join(' ')
  return `
    <div class="obj-row obj-edit-row">
      <span>${esc(label)}</span>
      <input class="obj-input" type="number" step="any" value="${value == null ? '' : esc(value)}" placeholder="${esc(placeholder)}" ${attrs}>
    </div>`
}

function editableTextRow(label, path, value) {
  return `
    <div class="obj-row obj-edit-row">
      <span>${esc(label)}</span>
      <input class="obj-input" type="text" value="${esc(value)}" placeholder="(default)" data-path="${esc(path)}" data-type="string" data-optional="true">
    </div>`
}

function editableSelectRow(label, path, value, options) {
  return `
    <div class="obj-row obj-edit-row">
      <span>${esc(label)}</span>
      <select class="obj-input" data-path="${esc(path)}" data-type="string">
        ${options.map(option => `<option value="${esc(option)}" ${option === value ? 'selected' : ''}>${esc(option)}</option>`).join('')}
      </select>
    </div>`
}

function editablePrimitiveRow(label, path, value, type) {
  if (typeof value === 'boolean') {
    return `
      <div class="obj-config-row">
        <span class="obj-config-key" title="${esc(label)}">${esc(label)}</span>
        <label class="obj-config-check">
          <input class="obj-input" type="checkbox" ${value ? 'checked' : ''} data-path="${esc(path)}" data-type="boolean">
          <span>${value ? 'true' : 'false'}</span>
        </label>
        <em class="obj-config-type">${esc(type)}</em>
      </div>`
  }
  const inputType = typeof value === 'number' ? 'number' : 'text'
  const step = typeof value === 'number' ? ' step="any"' : ''
  return `
    <div class="obj-config-row">
      <span class="obj-config-key" title="${esc(label)}">${esc(label)}</span>
      <input class="obj-config-field obj-input" type="${inputType}"${step} value="${esc(value)}" data-path="${esc(path)}" data-type="${esc(typeof value)}">
      <em class="obj-config-type">${esc(type)}</em>
    </div>`
}

function emptyPanel(text) {
  return `<div class="obj-empty"><div class="obj-empty-title">${esc(text)}</div><div class="obj-empty-sub">Objects are reusable .node.json templates.</div></div>`
}

function previewLabel(node, asset, animationFrame = null) {
  if (preview?.childVisualError) return `Child preview failed: ${preview.childVisualError}`
  if (preview?.clipName) {
    if (animationFrame) {
      return `${preview.clipName} frame ${animationFrame.label} (${animationFrame.index + 1}/${animationFrame.count}) @ ${clipFrameRate(preview.clip)} fps`
    }
    if (preview.clipAsset?.error) return `${preview.clipName}: ${preview.clipAsset.error}`
  }
  const visual = objectOrNull(node.visual)
  if (!visual) return 'No visual declared'
  if (visual.type === 'rect') return `rect ${visualSizeLabel(visual)}`
  if (asset?.error) return asset.error
  if (asset?.info) {
    const size = preview?.layout ? `${Math.round(preview.layout.displayW)} x ${Math.round(preview.layout.displayH)}` : visualSizeLabel(visual)
    return `${asset.info.key} ${size} from ${asset.info.manifest}`
  }
  return visual.texture ? `Resolving ${visual.texture}` : 'No texture'
}

function visualSizeLabel(visual) {
  if (!visual) return '-'
  if (visual.width !== undefined || visual.height !== undefined) return `${num(visual.width)} x ${num(visual.height)}`
  if (visual.ratio !== undefined) return `ratio ${num(visual.ratio)}`
  return '(source)'
}

function setActive(el) {
  if (!sidebarBody) return
  sidebarBody.querySelectorAll('.at-file, .at-folder').forEach(item => item.classList.remove('active'))
  el.classList.add('active')
}

function hasFiles(node) {
  if (!node) return false
  if (node.type === 'file') return true
  return (node.children || []).some(hasFiles)
}

function objectOrNull(value) {
  return value && typeof value === 'object' && !Array.isArray(value) ? value : null
}

function basename(path) {
  return String(path || '').split('/').pop() || 'Object'
}

function num(value) {
  return value == null ? '-' : String(value)
}

function formatNumber(value) {
  const n = Number(value)
  if (!Number.isFinite(n)) return ''
  return Number.isInteger(n) ? String(n) : n.toFixed(2).replace(/\.?0+$/, '')
}

function numberValue(value, fallback = 0) {
  const n = Number(value)
  return Number.isFinite(n) ? n : fallback
}

function cloneJSON(value) {
  return JSON.parse(JSON.stringify(value ?? null))
}

function jsonEqual(a, b) {
  return JSON.stringify(a) === JSON.stringify(b)
}

function getPathParts(path) {
  return String(path || '').split('.').filter(Boolean).map(part => {
    return /^\d+$/.test(part) ? Number(part) : part
  })
}

function setPath(obj, path, value) {
  const parts = getPathParts(path)
  let cursor = obj
  for (let i = 0; i < parts.length - 1; i += 1) {
    const part = parts[i]
    if (cursor[part] == null || typeof cursor[part] !== 'object') {
      cursor[part] = typeof parts[i + 1] === 'number' ? [] : {}
    }
    cursor = cursor[part]
  }
  cursor[parts[parts.length - 1]] = value
}

function getPath(obj, path) {
  let cursor = obj
  for (const part of getPathParts(path)) {
    cursor = cursor?.[part]
  }
  return cursor
}

function deletePath(obj, path) {
  const parts = getPathParts(path)
  let cursor = obj
  for (let i = 0; i < parts.length - 1; i += 1) {
    cursor = cursor?.[parts[i]]
    if (!cursor || typeof cursor !== 'object') return
  }
  delete cursor[parts[parts.length - 1]]
}

function diffJSON(before, after, prefix = '') {
  if (jsonEqual(before, after)) return []
  if (Array.isArray(before) && Array.isArray(after)) {
    const maxLength = Math.max(before.length, after.length)
    const changes = []
    for (let i = 0; i < maxLength; i += 1) {
      changes.push(...diffJSON(before[i], after[i], prefix ? `${prefix}.${i}` : String(i)))
    }
    return changes
  }
  if (objectOrNull(before) && objectOrNull(after)) {
    const keys = Array.from(new Set([...Object.keys(before), ...Object.keys(after)])).sort()
    return keys.flatMap(key => diffJSON(before[key], after[key], prefix ? `${prefix}.${key}` : key))
  }
  return [{ field: prefix || '$', before, after }]
}

function isEditablePrimitive(value) {
  return ['number', 'string', 'boolean'].includes(typeof value)
}

function cssColor(value) {
  if (value == null || value === '') return '#d97757'
  if (typeof value === 'number' && Number.isFinite(value)) {
    return '#' + Math.max(0, value).toString(16).padStart(6, '0').slice(-6)
  }
  const raw = String(value).trim()
  if (/^0x[0-9a-f]{1,8}$/i.test(raw)) return '#' + raw.slice(2).padStart(6, '0').slice(-6)
  return raw
}

function setStatus(msg) {
  if (onStatusChange) onStatusChange(msg)
}

function esc(value) {
  if (value == null) return ''
  return String(value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}
