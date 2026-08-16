/**
 * Vlm - Vision Language Model client for AI games.
 *
 * Thin fetch wrapper. Talks to the game's own backend at
 * `apiBaseUrl()/api/ai/vlm`, which holds VLM_API_KEY in its process env.
 * The browser never sees the key.
 *
 * Usage:
 *   import { Vlm } from '../engine/ai/Vlm.js'
 *   const { text } = await Vlm.describe({
 *     prompt: 'Describe the scene',
 *     images: ['/screenshots/frame.png'],  // url or data URL
 *   })
 */

import { apiUrl } from '../url.js'

export class Vlm {
  static async describe({ prompt, images = [], system, model } = {}) {
    if (!prompt) throw new Error('Vlm.describe: prompt is required')

    const res = await fetch(apiUrl('api/ai/vlm'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ prompt, images, system, model }),
    })

    if (!res.ok) {
      const detail = await res.text().catch(() => '')
      throw new Error(`Vlm.describe failed: ${res.status} ${detail}`)
    }
    return await res.json()
  }
}
