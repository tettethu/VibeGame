/** Flood-fill sprite auto-detection. Unchanged from original. */

export function detectSprites(imageData, minArea) {
  const { width, height, data } = imageData
  const visited = new Uint8Array(width * height)
  const results = []

  function opaque(x, y) {
    return data[(y * width + x) * 4 + 3] > 10
  }

  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      const idx = y * width + x
      if (visited[idx] || !opaque(x, y)) continue

      const stack = [x, y]
      let minX = x, maxX = x, minY = y, maxY = y, area = 0

      while (stack.length > 0) {
        const cy = stack.pop(), cx = stack.pop()
        if (cx < 0 || cx >= width || cy < 0 || cy >= height) continue
        const ci = cy * width + cx
        if (visited[ci] || !opaque(cx, cy)) continue
        visited[ci] = 1
        area++
        if (cx < minX) minX = cx; if (cx > maxX) maxX = cx
        if (cy < minY) minY = cy; if (cy > maxY) maxY = cy
        stack.push(cx-1, cy, cx+1, cy, cx, cy-1, cx, cy+1)
      }

      if (area >= minArea) {
        results.push([minX, minY, maxX - minX + 1, maxY - minY + 1])
      }
    }
  }

  results.sort((a, b) => (a[1] - b[1]) || (a[0] - b[0]))
  return results
}
