import { Node } from '/engine/Node.js'

export default class ThornBolt extends Node {
  ready() {
    this.vx = Number(this.config.vx) || 0
    this.vy = Number(this.config.vy) || 0
    this.damage = Number(this.config.damage) || 0
    this.lifetime = Number(this.config.lifetime) || 0
    this.hasHit = false
    this.attack = this.config.attack || 'THORN_VOLLEY'
    this.impactFx = this.config.impactFx || {}
    this.removeBounds = this.config.removeBounds || {}

    this.gameObject?.body?.setVelocity(this.vx, this.vy)
    this.visualObject?.setRotation?.(Math.atan2(this.vy, this.vx || 1))
    this.playAnim('fly', { restart: false })

    const player = this.findByTag('player')[0]
    if (player?.gameObject && this.gameObject) {
      this.scene.physics.add.overlap(this.gameObject, player.gameObject, () => {
        if (this.hasHit) return
        player.emit('hit', { damage: this.damage, attack: this.attack, sourceX: this.gameObject?.x })
        this._impactAndRemove()
      })
    }

    for (const wall of this.findByTag('wall')) {
      if (!wall?.gameObject) continue
      this.scene.physics.add.overlap(this.gameObject, wall.gameObject, () => this._impactAndRemove())
    }
  }

  _impactAndRemove() {
    if (!this.gameObject || this.hasHit) return
    this.hasHit = true
    this.emit('spawn_fx', {
      kind: 'thorn_impact',
      ...this.impactFx,
      x: this.gameObject.x,
      y: this.gameObject.y,
      facing: Math.sign(this.vx || 1)
    })
    this.removeSelf()
  }

  update(dt) {
    this.lifetime -= dt
    const go = this.gameObject
    if (!go || this.lifetime <= 0 ||
      go.x < this.removeBounds.minX || go.x > this.removeBounds.maxX ||
      go.y < this.removeBounds.minY || go.y > this.removeBounds.maxY) {
      this.removeSelf()
    }
  }

  runtimeState() {
    return {
      x: this.gameObject?.x ?? null,
      y: this.gameObject?.y ?? null,
      velocity: {
        x: this.gameObject?.body?.velocity?.x ?? this.vx,
        y: this.gameObject?.body?.velocity?.y ?? this.vy
      },
      lifetime: this.lifetime,
      damage: this.damage,
      hasHit: this.hasHit,
      attack: this.attack,
      visual: 'projectile_thorn_bolt_fly'
    }
  }
}
