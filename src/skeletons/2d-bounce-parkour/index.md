# 2D Bounce Parkour Skeleton

Side-view precision bounce-parkour rhythm-platformer. Core loop: run off a start platform, stomp a line of floating bounce-targets (each pops and launches the player upward), use a single air-dash (refreshed on stomp) to cross gaps, reach the goal platform. Fall off the bottom = instant respawn. Multi-stage progression with per-stage tries/best persistence and a clear/final completion overlay.

## Directory Layout

```
project.json              canvas 960x540, pixelArt, gravity y=900
index.html                Press Start 2P font preload + engine boot
config/
  input-map.json          move_left/right, jump (Space), dash (Shift), confirm, cancel
scenes/
  main.scene.json         Background (5 ParallaxModule layers), StageHost, Hud, disabled entity templates
scripts/
  Hero.js                 player FSM + stomp judgment + dash logic + respawn
  Balloon.js              sin-float + breath scale + pop + reset (shared by all 3 variants)
  StageManager.js         multi-stage orchestrator, tries/best, clear/final overlay
  Hud.js                  DOM CSS overlay, reads StageManager.runtimeState()
  ConfettiParticle.js     short-lived fx particle, spawned at pop/goal events
entities/
  hero.node.json          player visual/collider/animations
  balloon-red.node.json   standard target (bounceMultiplier 1.0)
  balloon-blue.node.json  large soft target (bounceMultiplier 0.8)
  balloon-gold.node.json  small high target (bounceMultiplier 1.3)
  start-platform.node.json
  goal-platform.node.json
  mid-platform.node.json
  goal-flag.node.json
  fx/confetti.node.json
stages/
  stage1.node.json        tutorial — 10 red targets, uniform spacing
  stage2.node.json        introduces blue targets + variable gaps
  stage3.node.json        all 3 variants + mid platforms + dash-required gap
assets/
  manifest.json           placeholder_atlas / placeholder_image entries for all textures
art-pack.md               empirical asset recipe and prompt inventory (artist-owned)
errors.md                 recurring sub-genre mistakes and fixes
```

## Canvas and Visual Proportions

- Canvas: 960 x 540, `pixelArt: true`, background color `#9ed2ff`.
- Physics gravity: y = 900 px/s^2.
- Hero: `visual.ratio: 0.162` — engine re-applies `frame.realSize * ratio` every frame preserving each pose's native aspect. Collider: dynamic box 20 x 36 px, `host: "separate"` (physics host separate from visual sprite).
- `visualTransform.offsetY: -8` shifts the sprite 8 px up relative to the physics host so the visual feet align with the collider bottom.
- Bounce targets display sizes: red 38 x 68 px (r=22 circle collider), blue 57 x 102 px (r=33), gold 27 x 48 px (r=16). Colliders are dynamic circles, `immovable: true`, `gravity: false`.
- Platforms: start/goal 160 x 40 px, mid 120 x 32 px — all static box colliders with `host: "separate"`.
- GoalFlag: visual only, 48 x 96 px, no collider.
- Confetti particles: 12 x 12 px display, no collider.

## Camera Behavior

- Follows the hero horizontally with lerp factor 0.15: `cam.startFollow(hero.gameObject, true, 0.15, 0)`.
- Bounds clamped to `levelWidth` per stage (stage1: 2880, stage2: 2960, stage3: 3600).
- On every stomp: `cam.shake(stompShakeMs, stompShakeAmount)` + `cam.zoomTo(stompZoomScale, stompZoomMs, 'Quad.easeOut')` then reset to 1.0. See `errors.md` entry #1 for why tweening `camera.zoom` directly is wrong — use `zoomTo()` exclusively.
- On stage load: `cam.setZoom(1)` resets any in-flight tween.

## Stage Structure

Three stages in `stages/stage*.node.json`, loaded at runtime by `StageManager` via `this._host.instantiate(stagePath)`. Each stage node's `config` carries:

| Field | Meaning |
|---|---|
| `spawnX` / `spawnY` | Hero respawn position |
| `levelWidth` | World/camera bounds width |

Stages are children of `StageHost` and torn down completely on load (`child.removeSelf()` for all children before loading the next). Stage files reference entity node.json via `src` paths — these must be relative to the project root.

Difficulty ramp:
- Stage 1: all red targets, even 240 px spacing — teaches basic stomp timing.
- Stage 2: blue targets introduced (larger, lower bounce), gaps start varying — dash sometimes needed.
- Stage 3: gold targets (smaller, higher bounce) + two mid platforms + one gap wide enough to require dash.

## runtimeState Shapes

**Hero** (`scripts/Hero.js`):
```json
{ "state": "idle|run|jump|fall|dash|bounce", "dashCharges": 0, "isGrounded": true, "facing": 1 }
```

**Balloon** (`scripts/Balloon.js`):
```json
{ "alive": true, "variant": "red|blue|gold", "popping": false }
```

**StageManager** (`scripts/StageManager.js`):
```json
{
  "stage": "stage1",
  "tries": 1,
  "best": null,
  "cleared": false,
  "centerText": "",
  "centerHtml": "",
  "isFinal": false,
  "totalTries": 0,
  "totalBest": null
}
```

## Module Usage — ParallaxModule

Five sibling `ParallaxModule` nodes under `Background`, one per depth plane:

| Node | Texture | scrollFactorX | depth | driftX |
|---|---|---|---|---|
| Sky | `bg_sky` | 0 (viewport-pinned) | -100 | 0 |
| CloudA | `clouds` frame `a` | 0.3 | -45 | 12 px/s |
| CloudB | `clouds` frame `b` | 0.3 | -45 | 18 px/s |
| HillsBack | `hills` frame `back` | 0.2 | -50 | 0 |
| HillsFront | `hills` frame `front` | 0.4 | -40 | 0 |

All scrolling layers have `width: 4000` (spans max level width). `driftX` layers self-scroll while the camera is still. Adjacent layers use different `scrollFactorX` values — required for visible parallax depth separation.

Contract: `parallax_background` pattern `scrolling-parallax-layers`. Do not attach colliders to parallax layers. Playable terrain (platforms) is separate.

## HUD Approach

Route 1 — DOM + CSS (no Phaser.Text). `Hud.js` mounts a logical-size overlay through `sceneTree.ui`, with 3 position-absolute `<div>` elements:

- Top-left: stage label (e.g. "Stage 1"), 16 px font.
- Top-right: "Tries: N / Best: N", 11 px font, right-aligned.
- Center: clear popup / final overlay with semi-transparent backdrop, shown/hidden by `display: block/none`. Multi-line via `innerHTML` with `<br>` separators.

Font: "Press Start 2P" (Google Fonts, preloaded in `index.html`), monospace fallback. All text uses CSS `textShadow: '2px 2px 0 rgba(0,0,0,0.85)'` for legibility over the sky background.

`Hud.update()` reads `this.parent.runtimeState()` (parent = StageManager root node) each frame and diffs against last-rendered state to avoid unnecessary DOM writes.

## localStorage

Per-stage best scores persist at key `bounce-parkour:<stageName>:best` (e.g. `bounce-parkour:stage1:best`). When all 3 stages have a best, `totalBest` is their sum. Cleared on a new best within the stage, not cross-stage.
