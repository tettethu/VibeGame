# Errors — 2D Action Boss-Fight

Recurring failure modes encountered while building this sub-genre. Each entry has a `**Spec update**:` line pointing at where the fix lives so the loop closes.

Source: distilled from completed 2D action boss-fight projects. Repeated entries here are the patterns that proved reusable; one-off project specifics stay out of the skeleton.

---

## 1. State machine drives animation, animation stuck on frame 0

### Symptom
Player walks; walk animation shows frame 0 every render — never advances.

### Cause
`AnimationPlayer.play(name)` defaults to `restart=true`. A state-machine `_syncAnim()` called every frame by `_setState` calls `playAnim('walk')` every frame, resetting frame index.

### Fix
Idempotent state setter:
```js
_setState(s) {
  if (this.state === s) return
  this.state = s
  this._syncAnim()
}
```

**Spec update**: Skeleton `scripts/PlayerController.js` and `scripts/BossController.js` both ship with this guard. New action-2D scripts should copy the pattern.

---

## 2. `setFlipX` condition wrong for assets that default left

### Symptom
Player faces correctly when moving; boss faces backwards when chasing — even though both use the same facing logic.

### Cause
Different art has different default orientation. Player art defaults right (`setFlipX(facing < 0)`), boss art may default left (then needs `setFlipX(facing > 0)`).

### Fix
Document each character's default facing in its script, then write the flip condition to match.

**Spec update**: Skeleton `scripts/PlayerController.js:185` and `scripts/BossController.js:155` carry explicit comments stating default orientation and flip rule.

---

## 3. Ability-recharge flag never resets without a "land" edge

### Symptom
Player dashes once. Cooldown timer expires. Dash never fires again until player jumps and lands.

### Cause
```js
if (!this._prevGrounded && this.isGrounded) {
  this._canDash = true   // only fires on the airborne→grounded edge
}
```
A player who never leaves the ground never sees that edge.

### Fix
Use a state predicate, not an event:
```js
if (this.isGrounded && this.dashCooldownTimer <= 0) {
  this._canDash = true
}
```

**Spec update**: Skeleton `scripts/PlayerController.js:87-89` ships with the state-predicate version. Same rule applies to double-jump, charge availability, parry windows.

---

## 4. Thin visual + thick collider requires `collider.host: "separate"`

### Symptom
Ground / wall declared as `visual:{ blank 1x1 }` + `collider:{ width: 1440, height: 20 }`. Player falls through.

### Cause
Default `host` mode applies `body.setSize` on the visual's gameObject, which then divides by `gameObject.scaleX` (≈ 1 / visual width). A wide collider request collapses back to 1×1.

### Fix
```json
"collider": { "body": "static", "host": "separate", "width": 1440, "height": 20 }
```

**Spec update**: Skeleton `scenes/main.scene.json` Ground / WallLeft / WallRight all use `host: "separate"`. Engine guide: [`collision-guide.md`](../../.vibegame/spec/engine/collision-guide.md).

---

## 5. Phaser does not separate two immovable bodies

### Symptom
Boss has `immovable: true` "because it shouldn't get pushed by the player". Boss falls through the ground.

### Cause
Phaser arcade physics requires at least one of two colliding bodies to be movable in order to apply the separation impulse. Ground is static (effectively immovable); if boss is also immovable, the pair has no movable side and no separation happens.

### Fix
Boss `collider: { "body": "dynamic", "immovable": false, "gravity": true }`. If push-resistance is needed, set `immovable: true` AND use `physics.add.overlap` (sensor) instead of `physics.add.collider` (resolved) for the player↔boss pair — or apply manual `setVelocityX(0)` on hit.

**Spec update**: Skeleton `entities/boss.node.json` ships `immovable: false`.

---

## 6. `runtimeState()` must expose every PRD-asserted field

### Symptom
Player agent fails an acceptance criterion because runtimeState lacks the asserted field — e.g. PRD requires `currentAttack` but BossController only exposes `state`.

### Cause
runtimeState authored at coding time, PRD criteria expanded later — drift.

### Fix
Each controller's `runtimeState()` covers all PRD-visible state. Three layers:
- player controller: position, hp, state, facing, isGrounded, invuln
- boss controller: position, hp/maxHp, state, currentAttack, aiEnabled
- root manager: fightOver, victorySide

**Spec update**: Skeleton ships all three controllers with full runtimeState. When adding a new state machine in a derivative project, audit runtimeState against PRD as the last check before player handoff.

---

## 7. Runtime-spawned ground FX buried below the floor (offset measured from the wrong origin)

### Symptom
A boss ground-slam crack / impact FX plays underneath the floor instead of on the surface.

### Cause
A runtime-spawned FX is positioned relative to the spawner's `gameObject` origin. For a feet-pivot character (`collider.pivot [0.5,1]`), that origin `y` is the feet / floor line, not the body center. A large positive `offsetY` (e.g. +72) then pushes a center-pivot FX well below the ground.

### Fix
For ground-contact FX off a feet-pivot spawner, keep `offsetY` near 0 (small negative to sit the impact band on the surface). Remember: `boss.y` with bottom pivot already equals the floor line.

**Spec update**: skeleton `entities/boss.node.json` inline `config.fx` offsets; FX placement convention noted here.
