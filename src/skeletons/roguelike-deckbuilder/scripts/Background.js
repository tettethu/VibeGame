import { Node } from '/engine/Node.js'

export default class Background extends Node {
  ready() {
    const go = this.getVisualObject?.() ?? this.gameObject
    if (!go) return
    const c = this.config ?? {}
    go.setOrigin(0.5, 0.5)
    go.setPosition(c.x ?? 480, c.y ?? 270)
  }
}
