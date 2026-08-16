/**
 * Imagegen - AI image generation client for AI games.
 *
 * Thin fetch wrapper. Talks to the game's own backend at
 * `apiBaseUrl()/api/ai/imagegen`, which holds IMAGE_API_KEY in its process
 * env. The browser never sees the key.
 *
 * Returns { dataUrl } - a base64-encoded image the game can load directly:
 *   const img = new Image(); img.src = dataUrl
 *
 * Usage:
 *   import { Imagegen } from '../engine/ai/Imagegen.js'
 *   const { dataUrl } = await Imagegen.generate({
 *     prompt: 'pixel art forest, 64x64',
 *     size: '1024x1024',
 *   })
 */

import { apiUrl } from '../url.js'

export class Imagegen {
  static async generate({ prompt, refs = [], model, size, aspect, resolution, quality } = {}) {
    if (!prompt) throw new Error('Imagegen.generate: prompt is required')

    const res = await fetch(apiUrl('api/ai/imagegen'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ prompt, refs, model, size, aspect, resolution, quality }),
    })

    if (!res.ok) {
      const detail = await res.text().catch(() => '')
      throw new Error(`Imagegen.generate failed: ${res.status} ${detail}`)
    }
    return await res.json()
  }
}
