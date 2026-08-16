import { buildPlaceholderImageCanvas } from './placeholder.js'

const DOM_ASSET_TYPES = new Set(['image', 'placeholder_image'])

function cssBoxSize(element) {
  const style = getComputedStyle(element)
  let width = parseFloat(style.width)
  let height = parseFloat(style.height)
  if (style.boxSizing === 'content-box') {
    width += parseFloat(style.paddingLeft) + parseFloat(style.paddingRight)
    width += parseFloat(style.borderLeftWidth) + parseFloat(style.borderRightWidth)
    height += parseFloat(style.paddingTop) + parseFloat(style.paddingBottom)
    height += parseFloat(style.borderTopWidth) + parseFloat(style.borderBottomWidth)
  }
  if (!Number.isFinite(width) || !Number.isFinite(height)) {
    throw new Error('UiLayer could not resolve element display size')
  }
  return { width, height }
}

export class UiLayer {
  constructor({ container, canvas, logicalWidth, logicalHeight, manifest, assetBasePath }) {
    if (!container) throw new Error('UiLayer requires a container element')
    if (!canvas) throw new Error('UiLayer requires a Phaser canvas')
    if (!Number.isFinite(logicalWidth) || logicalWidth <= 0) {
      throw new Error('UiLayer logicalWidth must be a positive number')
    }
    if (!Number.isFinite(logicalHeight) || logicalHeight <= 0) {
      throw new Error('UiLayer logicalHeight must be a positive number')
    }

    this.container = container
    this.canvas = canvas
    this.logicalWidth = logicalWidth
    this.logicalHeight = logicalHeight
    this.manifest = manifest || {}
    this.assetBasePath = String(assetBasePath || '').replace(/\/+$/, '')
    this._assetUrlCache = new Map()

    const computedPosition = getComputedStyle(container).position
    this._restoreInlinePosition = container.style.position
    if (computedPosition === 'static') container.style.position = 'relative'

    this.root = document.createElement('div')
    this.root.id = 'vibegame-ui'
    this.root.style.position = 'absolute'
    this.root.style.width = `${logicalWidth}px`
    this.root.style.height = `${logicalHeight}px`
    this.root.style.transformOrigin = '0 0'
    this.root.style.pointerEvents = 'none'
    this.root.style.userSelect = 'none'
    this.root.style.zIndex = '10'
    container.appendChild(this.root)

    this._resizeObserver = new ResizeObserver(() => this.sync())
    this._resizeObserver.observe(container)
    this._resizeObserver.observe(canvas)
    this.sync()
  }

  sync() {
    if (!this.root || !this.canvas) return
    const containerRect = this.container.getBoundingClientRect()
    const canvasRect = this.canvas.getBoundingClientRect()
    const { width: containerWidth, height: containerHeight } = cssBoxSize(this.container)
    if (containerWidth <= 0 || containerHeight <= 0) {
      this.root.style.visibility = 'hidden'
      return
    }
    this.root.style.visibility = ''

    const containerScaleX = containerRect.width / containerWidth
    const containerScaleY = containerRect.height / containerHeight
    const { width, height } = cssBoxSize(this.canvas)
    if (width <= 0 || height <= 0) {
      this.root.style.visibility = 'hidden'
      return
    }
    const scaleX = width / this.logicalWidth
    const scaleY = height / this.logicalHeight
    const left = (canvasRect.left - containerRect.left) / containerScaleX
    const top = (canvasRect.top - containerRect.top) / containerScaleY

    this.root.style.left = `${left}px`
    this.root.style.top = `${top}px`
    this.root.style.transform = `scale(${scaleX}, ${scaleY})`
  }

  mount(element) {
    if (!(element instanceof Element)) throw new Error('UiLayer.mount requires a DOM element')
    this.root.appendChild(element)
    return element
  }

  assetUrl(key) {
    if (this._assetUrlCache.has(key)) return this._assetUrlCache.get(key)

    const entry = this.manifest[key]
    if (!entry) throw new Error(`UiLayer asset key not found in manifest: "${key}"`)
    if (!DOM_ASSET_TYPES.has(entry.type)) {
      throw new Error(`UiLayer asset "${key}" has unsupported type: "${entry.type}"`)
    }

    let url
    if (entry.type === 'placeholder_image') {
      url = buildPlaceholderImageCanvas(entry).toDataURL('image/png')
    } else {
      if (typeof entry.path !== 'string' || !entry.path.trim()) {
        throw new Error(`UiLayer image asset "${key}" is missing path`)
      }
      const path = entry.path.replace(/^\/+/, '')
      url = `${this.assetBasePath}/${path}`
    }

    this._assetUrlCache.set(key, url)
    return url
  }

  setImage(element, key) {
    if (!(element instanceof HTMLImageElement)) {
      throw new Error('UiLayer.setImage requires an HTMLImageElement')
    }
    element.src = this.assetUrl(key)
    return element
  }

  setBackground(element, key) {
    if (!(element instanceof HTMLElement)) {
      throw new Error('UiLayer.setBackground requires an HTMLElement')
    }
    element.style.backgroundImage = `url(${JSON.stringify(this.assetUrl(key))})`
    return element
  }

  clear() {
    this.root?.replaceChildren()
  }

  destroy() {
    this._resizeObserver?.disconnect()
    this._resizeObserver = null
    this.root?.remove()
    this.root = null
    if (this.container) this.container.style.position = this._restoreInlinePosition
    this.container = null
    this.canvas = null
    this._assetUrlCache.clear()
  }
}
