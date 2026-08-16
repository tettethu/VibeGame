# Errors — Swipe-Slice Arcade

Recurring failure modes encountered while building this sub-genre. Each entry has a `**Spec update**:` line pointing at where the fix lives so the loop closes.

This is the skeleton's own reusable failure catalog. Entries here are patterns proven to recur across swipe-slice-style builds; one-off project specifics stay in the project only.

---

## 1. Tuning silently changed scoring fairness (opening-miss forgiveness)

### Category
Constraints Ignore

### Symptom
During feel-tuning, the first few objects that fell past the bottom did **not** count as misses — the player expected "every drop counts" and saw the contract broken.

### Cause
An "opening grace" branch forgave misses while `elapsed < N` or `spawnIndex <= K`. It was added as a quiet feel-softener, but miss-counting is a **scoring-fairness rule** (it decides when the run ends), i.e. a product decision — not a free tuning knob.

### Fix
Removed the forgiveness; every missed object counts from the opening. Fairness lives where it belongs: in the object's `minReadableTimeForMiss` gate (an object only reports a miss after it actually entered the readable field), so an object that never really appeared is never charged.

```js
onObjectMiss(obj) {
  this.misses += 1
  this.combo = 0
  if (this.misses >= this.missLimit) this.endGame('misses')
}
// Fairness upstream in the object:
if (this.y > this.missY) {
  if (this.readableTime >= this.minReadableTimeForMiss) this.controller?.onObjectMiss?.(this)
  this.removeSelf()
}
```

**Spec update**: `scripts/GameController.js` `onFruitMiss` (no opening grace); `scripts/Fruit.js` `minReadableTimeForMiss`. Rule: any tuning that moves a lose/score boundary is a product decision — surface it to the orchestrator, do not bury it in a difficulty branch.

---

## 2. Spawn density runaway at the opening

### Category
Best Practices

### Symptom
Iterating on "more action" produced a continuous-refill + doubled-density opener that buried the player in objects from second one — overwhelming and unfair before the player has read the screen.

### Cause
Density was driven by hardcoded early-game fast paths (tiny spawn interval, high desired on-screen count, aggressive pressure-refill). Each tweak stacked, with no smooth global control of how fast intensity rises.

### Fix
Drive interval / wave-size / on-screen-target-count from a single logarithmic ramp keyed on elapsed time, so intensity starts gentle and rises fast-early-then-plateaus:

```js
spawnRamp() {                       // ln(1 + t/tau) / ln(1 + full/tau), clamped [0,1]
  return clamp(Math.log(1 + this.elapsed / this.spawnRampTau) /
               Math.log(1 + this.spawnRampFull / this.spawnRampTau), 0, 1)
}
nextSpawnDelay()        { const r = this.spawnRamp(); return (this.slow + (this.min - this.slow) * r) * rand(0.85,1.15) }
desiredActiveTargets()  { return Math.round(this.startN + (this.maxN - this.startN) * this.spawnRamp()) }
```

**Spec update**: `scripts/GameController.js` `spawnRamp` / `nextSpawnDelay` / `desiredActiveTargetCount` / `pickWaveSize`; tunables `spawnRampTau`, `spawnRampFull`, `targetCountStart/Max`, `waveSizeMax`, `spawnIntervalSlow/Min` in config. Prefer one continuous ramp over stacked stage thresholds for arcade pacing.

---

## 3. Empty-image-manifest failure

### Category
Technical Error

### Symptom
Every texture falls back to the magenta missing-texture placeholder immediately on boot, or the skeleton fails to load any texture at all.

### Cause
`assets/manifest.json` declared `type: "image"` entries pointing at real-project art paths that don't exist inside the skeleton (a skeleton ships no real art), instead of `placeholder_image` / `placeholder_atlas` entries the engine can synthesize at runtime.

### Fix
Convert every entry to `placeholder_image` / `placeholder_atlas` with the same semantic key plus a `shape`/`color` placeholder description. Keep semantic keys stable so a later real-art swap only edits manifest entries, never scripts.

**Spec update**: `assets/manifest.json`; `.vibegame/spec/contracts/prototype_polish.md` Pattern `prototype`.

---

## 4. DOM-asset-bypass failure

### Category
Technical Error

### Symptom
A DOM/CSS HUD element (e.g. a miss badge) references a real-project asset path (`<img src="...">`) that does not exist in the skeleton, producing a 404 and a broken-image icon inside the HUD.

### Cause
DOM HUD elements were authored assuming a real-art project instead of using CSS-only shapes/colors for skeleton indicators.

### Fix
Render DOM-only status indicators (badges, icons) with pure CSS (background-color / border / clip-path), not `<img>` tags pointing at unregistered paths. Reserve `<img>` for manifest-registered keys only.

**Spec update**: `scripts/GameController.js` HUD builder; `.vibegame/spec/engine/ui.md`.

---

## 5. Imperative-runtime-facts failure

### Category
Constraints Ignore

### Symptom
A node's true rendered size / collider / depth / tilt at runtime silently differs from what its `.node.json` declares, because a script recomputes and overwrites it every `ready()`; reading the `.node.json` alone is misleading.

### Cause
Visual/collider/depth facts the engine already supports declaring (`visual.width/height`, `collider.radius`, and `config`-carried depth/tilt/blink-rate for facts with no native schema field) were instead computed and applied imperatively in script, often driven by a per-spawn config value that varies across a data-driven roster — one shared template plus a script formula, instead of one template per distinct value set.

### Fix
When the value is genuinely per-instance-type (a roster of distinct sizes/hitboxes), author one `.node.json` template per distinct value set rather than a shared template with a script-computed override. When the value is a single fixed constant, declare it directly in the template/config and delete the imperative override. Never let a script re-derive a value the engine could have declared, even when the numbers currently happen to agree.

**Spec update**: `.vibegame/spec/engine/collision-guide.md`; `.vibegame/spec/engine/animation-guide.md`; this skeleton's per-type `.node.json` templates.

---

## 6. Config-tuning failure

### Category
Constraints Ignore

### Symptom
Gameplay pacing/feel (spawn timing, jitter ranges, launch-physics minimums, pressure-refill curves) is scattered across bare numeric literals inside a controller script with no single place to find or adjust current tuning; some literals are duplicated as both a script fallback and a config default that "happen to" match.

### Cause
Feel-affecting numeric bounds (not pure math identities/clamps) were added directly in script during iteration instead of being promoted to the owning node's inline `config` (single-node tuning) or a shared named config (multi-node/shared tuning), and some were given `|| default` script fallbacks duplicating a config-declared value.

### Fix
Every gameplay/physics/visual-sizing/hitbox/spawn-timing/HUD-placement/animation-timing number that is not a pure math identity or clamp boundary belongs in exactly one config surface (the owning node's inline `config`, or a named shared config for values read by more than one node/script). Scripts read it directly and fail loudly if it is missing or invalid — no second literal default living in the script.

**Spec update**: `scenes/main.scene.json`; `config/fruit-roster.json`; `.vibegame/spec/engine/script-rules.md`.

---

## 7. Duplicate-template failure

### Category
Technical Error

### Symptom
Two directories (e.g. `entities/` and `nodes/`) contain byte-identical or near-identical `.node.json` templates, but only one is actually referenced by `instantiate()` calls — confusing which copy is authoritative and risking silent drift if only one gets edited.

### Cause
A directory was duplicated (rename/copy) during earlier iteration and the stale copy was never removed once the authoritative one was established.

### Fix
Keep exactly one authoritative `.node.json` template directory; `trash` (not `rm`) any duplicate and record it in the project's `.deleted` file.

**Spec update**: `.vibegame/spec/engine/entity-guide.md`.

---

## 8. Full-screen background stops at the screen midpoint

### Category
Constraints Ignore

### Symptom
A fixed-screen background shows one color or image in the upper half while the lower half exposes the canvas background, producing a perfectly horizontal seam at mid-screen.

### Cause
The background node is positioned at screen center, but its manifest entry omits `pivot`. The engine therefore applies the image default `[0.5, 1]` (bottom-center), so a full-screen-height image placed at `y = height / 2` ends at the midpoint instead of covering the viewport.

### Fix
For a full-screen image positioned at screen center, declare manifest `pivot: [0.5, 0.5]`. Keep scene position, display width, and display height aligned to the logical screen. Do not compensate with a second color layer or an unexplained position offset.

**Spec update**: `assets/manifest.json` `bg_dojo_backdrop`; `.vibegame/spec/engine/animation-guide.md` pivot cascade.
