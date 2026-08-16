# 2d-bounce-parkour — Reusable Errors

Failure modes worth preserving for this sub-genre. Each entry closes with a Spec update pointer.

## 1. Camera zoom juice via tween silently no-ops (Phaser 3 CE)

- **Category**: Implicit Framework Behavior (Phaser 3 CE quirk).
- **Symptom**: A stomp/hit "zoom punch" implemented by tweening `camera.zoom` produces no visible zoom.
- **Cause**: In Phaser 3 CE `camera.zoom` is a setter writing to `_zoomX/_zoomY`; the tween engine assigns the property directly, bypassing the setter, so the zoom never applies.
- **Fix**: Use the first-class zoom animation API `camera.zoomTo(scale, durationMs, ease)` for zoom punches; combine with `camera.shake()` for hit feel. Reset with `camera.zoomTo(1, durationMs)`.
- **Spec update**: recorded here; the seed controller (`scripts/*` player) uses `zoomTo` in its stomp juice as the reference.

## 2. Script-driven sin-motion nodes must disable body integration

- **Category**: Technical Error (sub-genre-specific: floating bounce-targets).
- **Symptom**: A floating target that a script positions every frame (sin float + breath scale) visibly jitters/shakes, especially after a respawn/reset that snaps it back to base position.
- **Cause**: The target has an Arcade body for stomp overlap. With `body.moves = true` (default), Phaser integrates the body from its own velocity and interpolates the delta introduced when the script snaps `gameObject.y`, fighting the per-frame position assignment.
- **Fix**: For any node whose transform is fully script-driven but still needs a body for overlap detection, set `gameObject.body.moves = false` in `ready()`. Overlap detection still works; the script owns position via `body.updateFromGameObject()` each frame.
- **Spec update**: recorded here; the seed bounce-target script sets `body.moves = false`.

## 3. Do not force per-state sprite sizes in script — use engine visual.ratio

- **Category**: Best Practices (replaces an older working-but-wrong approach).
- **Symptom**: Per-animation-state display sizes are hard-coded in the controller script and re-asserted every frame via a `postupdate` hook, because `setFrame`/`setTexture` reset width via `setSizeToFrame`. This also distorts each pose's aspect ratio (e.g. a wide-short dash pose forced to a tall box).
- **Cause**: Setting `visual.width`/`visual.height` independently forces both dimensions and overrides the engine per-frame sizing; the script then fights the engine.
- **Fix**: Author animation frames at a consistent character scale and give the node a single `visual.ratio`. The engine's `AnimationPlayer` re-applies `frame.realSize * ratio` every frame, preserving each pose's native aspect; the controller only calls `playAnim(state)` and sets `flipX`. No script-side displayWidth/Height, no postupdate re-assert.
- **Spec update**: recorded here; the seed player uses `visual.ratio` with no per-state size table.

## 4. Stomp detection must be continuous + center-relative, not enter-only + tight top band

- **Category**: Technical Error (sub-genre-specific: the core stomp-bounce mechanic).
- **Symptom**: The player clearly drops vertically onto a bounce-target but it does not pop — misses feel random, worse the faster the fall.
- **Cause**: Two compounding faults. (a) The stomp check ran only on the `overlap_enter` event (the single frame overlap begins); a fast fall enters the overlap already past the acceptance band and never re-checks. (b) The acceptance test was a tight band at the target's *visual top* (`body.bottom <= (center - height/2) + smallAllowance`), measured against a target that is floating (sin) and breathing (scale) every frame — so the window is both thin and moving.
- **Fix**: Register a per-frame overlap (`physics.add.overlap(hero, target, () => tryStomp(target))`) instead of an enter-only listener, guarding double-pop via a `_popped` flag. Loosen the acceptance to center-relative: pop when `body.velocity.y >= 0` (descending/level) AND `body.bottom <= target.y + stompAllowance` (feet at/above the target's vertical center + allowance). A clean vertical drop reliably pops; a side/underneath hit (feet well below center, or rising) still does not.
- **Spec update**: recorded here; the seed player (`scripts/Hero.js` `_tryStomp` + its overlap registration) uses the continuous, center-relative form.
