const PLACEHOLDER_IMAGE_SIZE = 64
const PLACEHOLDER_IMAGE_COLOR = '#ff00ff'
const PLACEHOLDER_IMAGE_SHAPES = new Set(['rectangle', 'circle', 'hex'])

function placeholderImageColor(entry) {
  const color = typeof entry?.color === 'string' ? entry.color.trim() : ''
  if (/^0x[0-9a-f]{6}$/i.test(color)) return `#${color.slice(2)}`
  if (/^#[0-9a-f]{3,8}$/i.test(color)) return color
  return PLACEHOLDER_IMAGE_COLOR
}

function placeholderImageShape(entry) {
  const shape = typeof entry?.shape === 'string' ? entry.shape.trim() : ''
  return PLACEHOLDER_IMAGE_SHAPES.has(shape) ? shape : 'rectangle'
}

export function buildPlaceholderImageCanvas(entry) {
  const d = PLACEHOLDER_IMAGE_SIZE
  const pad = 3
  const canvas = document.createElement('canvas')
  canvas.width = d
  canvas.height = d

  const ctx = canvas.getContext('2d')
  ctx.fillStyle = placeholderImageColor(entry)
  ctx.beginPath()

  const shape = placeholderImageShape(entry)
  if (shape === 'circle') {
    ctx.arc(d / 2, d / 2, (d - pad * 2) / 2, 0, Math.PI * 2)
  } else if (shape === 'hex') {
    const cx = d / 2
    const cy = d / 2
    const r = (d - pad * 2) / 2
    for (let i = 0; i < 6; i++) {
      const angle = Math.PI / 6 + i * Math.PI / 3
      const x = cx + Math.cos(angle) * r
      const y = cy + Math.sin(angle) * r
      if (i === 0) ctx.moveTo(x, y)
      else ctx.lineTo(x, y)
    }
    ctx.closePath()
  } else {
    ctx.rect(0, 0, d, d)
  }

  ctx.fill()
  return canvas
}
