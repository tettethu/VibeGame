# Errors — Roguelike Dungeon Shooter

Recurring failure modes encountered while building this sub-genre. Each entry has a `**Spec update**:` line pointing at where the fix lives so the loop closes.

Source: distilled from completed roguelike dungeon shooter projects. Repeated entries here are the patterns that proved sub-genre-defining; engine-bug and process-only notes stay out of the skeleton.

---

## 1. Enemy activation/follow threshold ≤ map diagonal → enemies stuck

### Symptom
"Lots of slimes don't move." Enemies spawn, stay frozen, never engage even when player is across the room.

### Cause
Enemy script gates pursuit on `dist <= followThreshold`. Threshold was hardcoded at 400 px. A multi-room playable area extends well beyond 400 px from many enemy spawns (rooms 672×480 px each, world ~2500 px across), so most spawned enemies are immediately out-of-range and never tick.

Second-order bug: when the gate fails, `setVelocity(0, 0)` was not called, so any spawn-time impulse drifts the enemy into a wall.

### Fix
For closed arenas, just remove the distance gate — there's no off-screen-deactivation concern when the room is bounded by walls. If a gate is genuinely needed (e.g. screen-streaming worlds), it must be `≥ map diagonal`, not a fixed pixel number. Always `setVelocity(0,0)` on the early-return branch.

```js
// BAD
if (Phaser.Math.Distance.Between(this.x, this.y, p.x, p.y) > 400) return

// GOOD (closed arena)
// no gate at all

// GOOD (streaming world)
const maxDist = Math.hypot(world.width, world.height)
if (dist > maxDist * 0.6) {
  this.gameObject.setVelocity(0, 0)
  return
}
```

**Spec update**: `Enemy.js` no longer gates by hardcoded distance; `config/enemies.json` should expose `followThreshold` if needed, defaulted to `Infinity` for arena games.

---

## 2. Top-down weapon: rotation-only, no `setFlipX` stacking

### Symptom
"Aiming back-left while moving right makes the gun render upside-down."

### Cause
WeaponVisual was both rotating (`setRotation(angleToCursor + π/2)`) AND flipping horizontally (`setFlipX(parentGO.flipX)`). The π/2 offset already handles all four quadrants of aim angle — flipping on top of rotation produces a mirrored render.

### Fix
Use rotation only. Drop `setFlipX` from the weapon. The weapon's sprite must be authored pointing up (towards 12 o'clock); rotation by `aim_angle + π/2` rotates it to point at the cursor in any direction.

**Spec update**: `scripts/WeaponVisual.js` — rotation-only orientation. Comment at top of file: "Weapon sprite is authored pointing UP. Orientation is rotation-only; do NOT add flipX or you will double-flip when the player flips."

---

## 3. Player facing: cursor decides, NOT movement direction

### Symptom
"Strafing left while shooting right makes the character's back face the gun."

### Cause
`Player._handleMovement()` flipped the body based on `vx` (movement direction). `Player._updateFacing()` separately tried to flip based on cursor — but only when idle. The two paths conflict: when moving, the movement flip wins, but the gun (which follows cursor) ends up facing away from the body.

### Fix
Single source of truth: player body faces cursor at all times, movement is independent. Remove movement-based flip; `_updateFacing()` always reads cursor angle.

```js
// In _updateFacing(), unconditional:
const dx = mouse.x - this.x
this.gameObject.setFlipX(dx < 0)
```

**Spec update**: `scripts/Player.js` — `_handleMovement()` no longer flips. `_updateFacing()` runs every frame.

**Genre convention**: In a top-down twin-stick shooter, character facing follows the *aim* vector, not the *movement* vector. This is a sub-genre rule, not an opinion — players cannot interpret a character whose torso disagrees with the gun barrel.

---

## 4. `invisibleWall` coordinate convention: tile-boundary vs centered zone

### Symptom
After v7 tileset replacement, physics-debug overlay shows the vertical corridor's side colliders pushed 16 px (one half-tile) into the corridor interior.

### Cause
Two coordinate conventions co-existed in `GameManager.js`:

- Tilemap layout uses **tile-boundary coords**: `corridor.x0 * TS` is the left edge of the corridor (32-aligned).
- `_addInvisibleWall(x, y, w, h)` passes `x, y` to a Phaser Zone, which interprets them as the body's **center**.

Old code derived the centerX from `leftW / 2`, then added an extra `TS / 2` — applying the boundary→center correction twice. Result: collider inner edge sits 16 px inside the visible corridor edge.

### Fix
Use a single coordinate convention per call site. Prefer **boundary-rect** helpers over centered helpers:

```js
// BAD (mixed conventions; corridor x0 is boundary, then add TS/2 to get center)
_addInvisibleWall(corridor.x0 * TS + leftW / 2 + TS / 2, ...)

// GOOD (single rect-by-boundary)
_addInvisibleWallRect(left, top, width, height) {
  const zone = this.scene.add.zone(left + width / 2, top + height / 2, width, height)
  // ...
}
this._addInvisibleWallRect(corridor.x0 * TS, top, leftW, h)
```

### Better: avoid `invisibleWall` entirely

For map-shape colliders, prefer **tilemap-built collision** (`tile.collision: true` + `getCollisionLayer()`) over hand-placed zones. The tilemap pipeline already handles the boundary↔center conversion correctly. Reserve `invisibleWall` for shape-irregular geometry that can't be expressed as a tile grid (e.g. an arbitrary polygon room).

**Spec update**: Folded into [`contracts/tilemap.md`](../../.vibegame/spec/contracts/tilemap.md) `#### Architect/Programmer` → Common Mistakes §3.
