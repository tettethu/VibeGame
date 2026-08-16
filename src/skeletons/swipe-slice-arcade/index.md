# Swipe-Slice Arcade — Skeleton

Fixed single-screen arcade where the player swipes a pointer/finger to slice objects that are launched up into the screen and arc back down under gravity. Cutting an object splits it into physics halves + spawns transient juice VFX; cutting 3+ in one swipe scores a combo; a hazard object (bomb) ends the run when sliced; letting N objects fall past the bottom ends the run on misses. Endless high-score loop with a logarithmic difficulty ramp.

This is a runnable placeholder baseline: from this directory, `vibegame run` boots directly with full placeholder art and the complete loop playable end-to-end. Below are the rules, systems, launch/runtime facts, and the practice-verified layout / proportion starting points.

## Launch

- `index.html` loads Phaser 3.80.1 from the same CDN bootstrap used by shipped runnable skeletons. `vibegame run` mounts the framework engine and required modules; JSON fetches and asset paths remain project-relative / base-aware.
- `assets/manifest.json` uses `placeholder_image` entries under the same semantic keys a real project would register — swapping in real art later only edits manifest entries, no script rewrite.

## Controls

- **PC**: press and hold mouse left button, drag to draw a slash, release to end it.
- **Mobile**: finger drag does the same.
- Click/touch `Start` on the start overlay to begin a run; click/touch `Restart` on the game-over overlay to start a new run (best score persists, run counters reset).

## runtimeState() facts

`GameController.runtimeState()` exposes: `gameState` (`start`/`playing`/`gameOver`), `score`, `bestScore`, `bestScoreStorageAvailable` (false when sessionStorage read/write fails — best score is never faked across sessions in that case), `misses`, `missLimit`, `combo`, `maxCombo`, `uiState.missRoute` (fixed `'css'`), and a per-type `fruitProfiles` summary. `Fruit` / `FruitHalf` / `Bomb` each expose their own `radius`, `fruitType`/`side`, and lifecycle flags (`sliced`, `ttl` for halves) via their own `runtimeState()`.

## Module + engine fallback

- `SwipeSlashModule` and `TimedImageVfxModule` are required modules; if either fails to resolve, boot must fail loudly and report the missing module — no silent no-slash / no-VFX degraded mode.
- A missing-local-engine warning during `vibegame check` is only acceptable once this skeleton has been proven to boot in place via `vibegame run` plus a runtime smoke check; otherwise treat it as a real error.

## Production shape

- **Single fixed screen**, no camera scroll, no tilemap. One decorative background image fills the screen.
- **Endless high-score**: score + best (sessionStorage) + combo + N-miss lose + hazard-instant-lose.
- **DOM/CSS HUD** (score / best / miss badges / combo callout / start + game-over overlays) — not `Phaser.Text`.
- **Runtime-spawned content** via `instantiate` of `.node.json` templates: targets, hazard, halves, VFX. Nothing pre-placed except background, the controller, and disabled template-registration nodes.

## Layout & proportions (verified starting points)

- **Logical resolution `960 × 540`**, `project.json.settings.scaleMode: "FIT"`. The Phaser world is pinned to this size at every viewport — the engine (`PhaserHost`) maps logical→display, so spawn-Y / missY / gravity stay valid in any browser. Do **not** size gameplay off the container.
- **World gravity `y = 560`** (px/s²). Per-object fall feel is scaled by a `weight` multiplier (`bodyGravityY = (weight-1) * worldGravity`).
- **Miss line `missY = height + 80 = 620`** — an object counts as missed only after falling below the bottom edge (not while still on screen).
- **Launch**: objects spawn near/below the bottom (`y ≈ height-100` for the visible opening wave, `y = height+44` for off-bottom lobs) with an upward velocity solved to reach an apex at `~0.32–0.56 × height` (heavier objects aim a touch lower). Horizontal speed `~110–240 px/s`, direction toward screen center.
- **Target radii**: standard object `≈24–25`, heavy object up to `~27`, hazard `27`. Slice hit-test adds `hitPadding 7` for forgiveness.
- **Halves**: each half body is a small circle (`~0.42 × radius`), pops apart at `±popX (~145)` with a slight up-kick (`popY ~ -85`) and spin, plus extra `+70` gravity so they fall convincingly; cleaned up at `ttl 2.5s` or off-screen.

## Difficulty: logarithmic spawn ramp

Density starts gentle and rises fast-early-then-plateaus via `ramp(t) = ln(1 + t/τ) / ln(1 + full/τ)`, clamped `[0,1]` (GameController config):

- `spawnRampTau = 12`, `spawnRampFull = 55` (seconds to full intensity)
- spawn interval lerps `slow 1.5s → min 0.52s`
- on-screen target count lerps `targetCountStart 2 → targetCountMax 10`
- per-wave size lerps `1 → waveSizeMax 4`

Opening wave is a gentle 2 objects; the hazard is withheld for the first `introDelay 10s` / `introSpawnedCount 8` so players learn to slice first.

## Scoring

- Each object grants its `score`; heavier/rarer objects are worth more.
- **Combo** (single swipe cuts ≥3): `comboBonus { "3":5, "4":10, "5":20, "6":30 }` (6 = cap), with an escalating callout.
- Hazard grants nothing and ends the run; missed objects cost a miss (not score). `missLimit = 3`.

## Object roster (relative feel — exact values in `config/fruit-roster.json`)

Differentiate objects along **speed / weight / score / juice / half-pop**, not just art:

| Archetype | Feel | Role |
|---|---|---|
| Standard | medium speed/weight, baseline | the teaching object |
| Heavy (×2) | slow, heavy halves, high score | reward objects to fold into combos |
| Light/small | fast, small, low score, light pop | reaction + combo filler, easy to miss |
| Mid variants | distinguishable by speed / juice / elasticity / shell feel | keep the mid-game varied |
| Hazard | visually unmistakable; withheld at the opening | "do not cut" — controls greedy long swipes |

## Modules wired in

- **`SwipeSlashModule`** (top-level `modules/`) — owns pointer capture, the glow vector trail, and segment-circle continuous hit detection. Scene node config: `groups: [{tag:'sliceable', method:'slice', category:'slice'}, {tag:'bomb', method:'hitBySlash', category:'hazard', stopOnHit:true}]`. The controller implements the host hooks `canSlash()` / `onSwipePointerDown()` / `onSwipeEnd()`; targets implement their own `slice()` / `hitBySlash()`.
- **`TimedImageVfxModule`** (top-level `modules/`) — drives the juice / splash / explosion VFX node templates (`slice-vfx.node.json`, `bomb-explosion.node.json`); fire-and-forget, self-destroying.

## File map

- `scripts/GameController.js` — orchestrator: state machine (start/playing/gameOver), spawn ramp, scoring/combo, miss/hazard, DOM HUD, `runtimeState()`. Tagged `game`; hosts `SwipeSlashModule`.
- `scripts/Fruit.js` — launched sliceable object: physics launch, readable-field tracking, `minReadableTimeForMiss` fairness gate, `slice()`.
- `scripts/FruitHalf.js` — a split half: spin + extra gravity + ttl/offscreen cleanup.
- `scripts/Bomb.js` — hazard: warning-texture blink, `hitBySlash()`.
- `entities/fruit-<type>.node.json` / `entities/fruit-half-<type>.node.json` — one pair per roster object type, each declaring that type's own size/collider (no shared generic template, since size/hitbox genuinely varies by type); plus `entities/bomb.node.json`, `entities/slice-vfx.node.json`, `entities/bomb-explosion.node.json` for hazard / slice-VFX / explosion-VFX.
- `config/fruit-roster.json` — per-object speed / weight / score / spawnWeight / halfPop / sliceVfx, combo table, hazard profile, shared cross-script tuning (`halfPopGravityBoost`, VFX jitter, bomb spawn-chance rates).
- `config/input-map.json` — start / restart actions (pointer drives slicing directly).
- `index.html` — in-place boot shell with the standard Phaser CDN bootstrap, see Launch above.
- `art-pack.md` — empirical runtime art families (see file), artist-owned, untouched by the placeholder-baseline conversion. `assets/manifest.json` uses fully-populated `placeholder_image` entries, runnable as-is (not structure-only).
