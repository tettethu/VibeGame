# Art Pack — roguelike-dungeon-shooter

Empirical asset list for the top-down dungeon bullet-hell roguelike sub-genre. Generation prompts are verbatim from `.vibegame/logs/imagegen.jsonl` / `.vibegame/logs/artist.log` of the reference build; entries without a recorded prompt point at the relevant `spec/art/*.md` section or call out included-reference / asset-pack / procedurally-authored origin.

This pack records the **verified generation method + useful candidate outputs** for the sub-genre, which is a superset of the runtime manifest — the runtime manifest records only the runtime-selected asset, whereas art-pack also keeps (a) methods verified via later fallback regeneration even when the shipped raw was off-pipeline, and (b) generated candidates that were NOT runtime-selected but carry a reusable method or failure lesson (marked "alternate candidate — not runtime-selected").

Camera: top-down 3/4, character canonical facing RIGHT (sprites are flipped for left-facing at runtime). Pixel art across the board, dark dungeon palette. The skeleton ships the playable character style anchor in `art-pack-assets/player_run.png` — see [Player § run](#run) — which must be passed as `-i` reference for any new player-class generation.

## Player

Both Player actions are **reference-driven**. The pack ships two anchor images that every reuse of this sub-genre must pass as `-i` input:

- [`art-pack-assets/player_run.png`](art-pack-assets/player_run.png) — 5-frame run/idle atlas, 1870x524. Identity anchor for the playable character.
- [`art-pack-assets/player_roll.png`](art-pack-assets/player_roll.png) — single-frame tucked-ball pose, 369x444. Pose anchor for the roll cycle.

### run

- prompt missing — **included reference pixel-art sprite, no generation**. The runtime atlas is `art-pack-assets/player_run.png` itself.
- layout: 1x5 horizontal strip, magenta-separated; frames = `run_0` (idle hold) + `run_1..run_4` (walk loop)

**Hints**
- Style + proportion (chunky pixel art, 1:1.5 head:body, handless cloaked figure) cannot be reproduced from text alone in this sub-genre — i2i with this reference is the only reliable path. Documented failures: text-only drifts to smooth illustration / soft monk hood / Q-version chibi.
- To derive a new player identity (same style, different character) pass `player_run.png` as `-i` and prompt for the new identity while preserving "粗块像素 / 头身比 1:1.5 / 无手无腿披风".

### roll

- prompt
  ```
  图2的角色, 改成图1的姿势: 身体变成球形, 在身体上叠加头,  身体的圆只比头大一点, 夸张化的表达准备翻滚的姿势, 角色面朝右边, 竖直姿态, 单帧, 保持像素风和角色形象不变
  ```
- layout: single-frame i2i output (~369x444 tucked ball), expanded to 8 frames by rotating the same PNG at 45° steps (see Hints)
- i2i inputs (order matters): image 1 = `art-pack-assets/player_roll.png` (pose anchor — tucked-ball composition); image 2 = `art-pack-assets/player_run.png` (identity anchor). The prompt's "图2的角色, 改成图1的姿势" clause grafts player identity onto the tuck composition.

**Hints**
- **Rotation-as-frame** (the reusable trick for raw frame expansion): produce one i2i tucked-ball frame, then rotate it 8 times at 0° / 45° / 90° / 135° / 180° / 225° / 270° / 315° with `vibegame art edit <base>.png -m rotate --angle <N> --pixel -o roll_<N>.png` to get an 8-frame raw sequence. `--pixel` is mandatory — it runs simplified RotSprite (NEAREST throughout, no mixed colors); without it bilinear softens pixel edges. Only valid for **rotationally symmetric** actions (roll / spin / tumble); directional actions (sword swing) must redraw each frame.
- **Pose-anchor identity does not matter, its composition does.** The original call used a retired character's roll frame (`saber_roll_frame0.png`) as image 1 — what mattered was the clean shoulder-tucked rolling-ball composition, not who the character was. `art-pack-assets/player_roll.png` plays the same role for sub-genre reuse: it is a pose template, not a character identity.
- **Body-size ratio note for non-handless characters**: this project's player has no legs/arms, so the tuck pose comes out close to the idle silhouette (the project lands roll/run display height ≈ 0.84). Normal humanoid players (visible legs/arms) tuck much smaller — target roll ≈ 0.5 × idle. When porting this prompt to a humanoid project, replace "球只比头大一点" with "球比头大约一倍" or similar so the model produces an appropriately compact ball.

### run — handless cloaked chibi (alternate candidate, NOT runtime-selected)
- prompt
  ```
  # Handless cloaked chibi — run cycle (pixel art)

  Pixel art sprite sheet, 4 frames of the SAME cute chibi character laid out in a single horizontal row, evenly spaced, with clearly visible solid magenta gaps between frames.

  ## Character (identical across all 4 frames)
  - Tiny chibi proportions: oversized round head, small body, total height roughly 1.7x the head height.
  - Wears a deep heavy hooded poncho/cloak that completely covers the body. The cloak hem reaches the ground; there is no visible split for legs, no visible feet.
  - NO visible arms. NO visible hands. The cloak silhouette is a closed bell shape with NO sleeve openings, NO hand-shapes sticking out.
  - Inside the deep hood, only the upper face peeks through: two big anime-style eyes, small mouth optional. The rest of the head is in deep shadow inside the hood.
  - Color scheme: dusty teal/blue-grey cloak with a single darker navy trim near the hem, beige/pale-cream face, dark eyes. Palette distinct from the warm-tan turban player.
  - One small accent: a single round wooden bead / coin pendant on the chest, same place every frame.

  ## Run animation language — no legs, conveyed by body shake
  Legs are hidden by the cloak, so running is communicated entirely by full-body vertical bob + slight lateral tilt:
  - Frame 1: body up 2px, tilted LEFT, cloak hem swept RIGHT.
  - Frame 2: body down 2px (squashed), upright, hem flared OUT both sides.
  - Frame 3: body up 2px, tilted RIGHT (mirror of f1), hem swept LEFT.
  - Frame 4: body down 2px (squashed), upright, hem settles toward CENTER.
  Same identity/colors/silhouette in all 4 frames; only vertical offset, tilt, hem direction change. Eyes forward, unchanged.

  ## Strict: 4 frames one row, same canvas height, same bbox+baseline, wide magenta gap between frames, magenta (255,0,255) background, no magenta inside subject, no text/UI/border/grid/gradient/shadow, no arms/hands/weapons/sleeves/legs/feet, no scenery.
  ```
- layout: 1x4 horizontal strip, magenta-separated
- verified generation method: **text-only t2i, no `-i` reference** (gpt-image-2, 1536x1024) → `rmbg -c <sampled magenta> -t 30` two passes → `cut --min-area 5000` → `perfectify -m sprite --edge inward` → `concat --layout row --spacing 2`. Runtime candidate = `assets/handless_run.png` (registered as manifest key `handless_run` but NOT the selected player — `player_run` is). Raw + prompt: `assets/artifacts/raw/handless_run/` (v1 is the shipped candidate; v4-v7 were replacement experiments, all rolled back).

**Hints**
- **This candidate's main value is a failure lesson, not the asset.** A 4-frame occluded-limb (legless/handless bell-cloak) run reads as *idle*, not running — the 2px bob + hem swish is too subtle at 4 frames / low speed to convey a run cycle. Verdict on the v4 attempt to make it the runtime player: "效果极差", rolled back. To make an occluded-limb run read, use ≥6-8 frames with much larger hem flutter, or give the character visible legs/arms. (This lesson is the basis of a `spec/art/sprite.md` Phase-2 candidate.)
- Unlike the runtime `player_run` (included reference, i2i-only), this style was reachable **text-only** because it is an original design with no pre-existing identity to preserve — text-only is viable when inventing a new character, but drifts when reproducing an established one.

## Enemy

- The shipped runtime enemy sprites are **off-pipeline** (predate jsonl logging), BUT the full generation method was later **reproduced and verified via fallback single-pass regen** in a self-evolve run. Verbatim per-enemy prompts are in `.vibegame/logs/imagegen.jsonl` at outputs `assets/artifacts/raw/regen_test/{monster_pack_v1, slime_v1, skeleton_archer_v1, shadow_mage_v1, skeleton_hand_v1, ghost_v3}.png`. Treat those as the recovered prompts for this class.
- layout: each enemy ships its own per-action sprite sheet under `assets/characters/<enemy>/<action>.png` or `assets/<enemy>/<action>.png`

**Hints**

Two-stage workflow keeps the enemy roster visually coherent:

1. **Roster pack first.** Generate one 3x2 (or 2x3) grid sheet containing **one frame per enemy** of the whole roster, using an in-game gameplay screenshot as the `-i` style anchor. This locks all enemies to the same camera angle (top-down 3/4), the same chunky pixel scale, the same outline treatment, and the same dark-dungeon palette family by leveraging single-image internal style consistency. Cut the 6 cells into per-enemy reference frames stored under `assets/artifacts/raw/monster_pack/`.
2. **Per-enemy action sheet.** For each enemy, generate the action sheet separately, passing that enemy's roster-pack frame as the `-i` reference. One action sheet per `### <enemy>—<action>` entry below.

Standard action list (matches runtime usage):

- **slime** — `jump`: 5-frame jump cycle (rest → crouch squash → peak stretch → descend → land squash). 1x5 horizontal strip.
- **skeleton_archer** — `attack`: 4-frame bow draw + release (raise bow → draw → loose → recover). 1x4 horizontal strip. **Do not draw the arrow itself in the sheet** — arrows are a separate projectile asset (see [FX § bullet families](#fx-svg-procedural)). If the model insists on including a fired arrow, cut the arrow pixels out via `vibegame art cut` and keep only the archer component.
- **shadow_mage** — `attack` (cast) + `teleport`: cast is 4-frame raise-arms / glow / fire spell; teleport is 4-frame fade-out / void / fade-in. Each 1x4 horizontal strip. Spell projectile is a separate asset.
- **bat** — `flap`: 4-frame wing-flap cycle (wings up → wings mid-down → wings full-down → wings mid-up). 1x4 horizontal strip.
- **ghost** — `idle`: 4-frame hover loop (vertical bob + slight silhouette stretch/squash). 1x4 horizontal strip. The ghost is a free-floating spirit silhouette, no container.
- **skeleton_hand** — `emerge`: 4-frame burst-from-ground (fingertips → half hand → full hand → fully clawed). 1x4 horizontal strip. Dirt mound at the base stays constant across all frames.

Generation rules common to every action sheet:

- Pass the matching roster-pack reference as `-i` for identity continuity across actions.
- Same canvas height per frame; subject sits on the same baseline so the cut atlas plays without vertical jumping.
- Magenta (#FF00FF) marker background; clear magenta strip between adjacent frames.
- No projectiles, no spell FX, no damage numbers — those are separate FX assets.
- Same enemy identity (palette, silhouette, proportion) across all frames of the action.

Verified-regen candidate lessons (from the fallback validation, useful even though outputs weren't runtime-selected):
- **ghost text-only drifts to a container.** Regen v1 → "spirit inside a green lantern/jar", v2 → "spirit inside an apothecary bottle", v3 → correct "free-floating green spirit, NO bottle / NO jar / NO container / NO cork, one continuous soft silhouette". A free-floating spirit must **explicitly forbid every container word** or the model encloses it. v3's prompt is the one that matched the runtime ghost.
- **each enemy prompt carries a "strict don'ts" block** listing the model's default wrong additions for that subject (skeleton → no flesh/armor/clothing/nocked-arrow; shadow_mage → no visible face/hands/legs; ghost → no container). Text-only enemy regen is reliable only with these per-subject negatives.
- **chunky/low-res reminder in every prompt** ("~96px per frame, visible blocky pixels, NOT a smooth illustration / high-res painting") — text-only gpt-image-2 defaults to smooth illustration without it.

## Boss

### wraith_knight — idle / walk / slash / die
- prompt missing — **off-pipeline source PNGs in the reference build**, no jsonl row, no fallback prompt available. Per-action raw files arrived as separate 2-frame strips at non-uniform sizes (220x222 idle, 260x234 walk, 506x168 attack_slash, 244x242 die). The runtime atlas `wraith_knight_atlas.png` (2024x242, 8 frames) was assembled by normalizing all four 2-frame strips to a shared 253x242 cell height and re-concatenating in order `idle_0, idle_1, walk_0, walk_1, slash_0, slash_1, die_0, die_1`.
- layout: 1x8 horizontal strip atlas (normalized cell height 242, variable cell widths recorded in manifest bboxes)

**Hints**
- **Cell-height normalization trick** when combining multiple separately-generated action strips into one boss atlas: pick the **largest** content-height across actions (here `slash` at 168 was shortest, but the visible boss body in `idle`/`walk`/`die` was ~234 — so the atlas was normalized to that body height) and pad shorter actions with transparent rows so the engine can play any action without the body visibly jumping in vertical position. Pivot `[0.5, 0.5]` then resolves to the same on-screen anchor across all actions.
- The boss attack uses a **separate projectile asset** (`bullet_boss_soul_wave.svg`, see [FX § boss_soul family](#boss_soul-family)) — do NOT bake projectile travel frames into the slash action sheet. The slash sheet is windup + strike only.

### wraith_shard — idle / die
- prompt missing — **off-pipeline source PNG in the reference build**, no jsonl row. Single 4-frame combined atlas `spritesheet.png` (864x240, 4 frames at 216x240 each).
- layout: 1x4 horizontal strip atlas covering both idle (frames 0-1, loop) and die (frames 2-3, one-shot)

**Hints**
- One atlas, two clips. The animation engine's clip definition simply slices `idle_0/1` vs `die_0/1` out of the same texture — see [`entities/wraith_shard.node.json`](../../entities/wraith_shard.node.json) for the `animations.clips` shape.

## Prop

### chest
- prompt
  ```
  按照这个游戏风格绘制一个游戏宝箱的spritesheet, 1x2, 左边是关着的宝箱, 右边是开着的宝箱, 像素风格, 品红色背景, 素材带黑色描边
  ```
- layout: 1x2 horizontal strip, magenta background, left=closed / right=open

**Hints**
- The "按照这个游戏风格" clause means the i2i call passes a project style reference (typically the player_run sprite or a curated style anchor frame) as the `-i` input — text alone won't lock the dungeon-art look. "素材带黑色描边" explicitly asks for pixel-art black outlines so the prop sits readably on the floor tiles.
- The two final manifest frames `chest_closed` and `chest_open_r` are cut from the same raw — auto-detect cut works here because the two states are clearly separated by the magenta column.

## FX (SVG procedural)

### bullet_player / bullet_enemy (and `_alt` variants)
- hand-written 1x1-rect-per-pixel pixel-style SVG. See [spec/art/svg-best-practices.md § Chapter: Pixel Energy Projectiles](../../.vibegame/spec/art/svg-best-practices.md).
- layout: 16x16 single-frame SVG with `shape-rendering="crispEdges"`; multi-tier core→halo color ramp (white-hot core, saturated body, near-white outer band, semi-transparent halo, irregular edge wave)

**Hints**
- The `_alt` variants share the same canvas size and center, only the outer ripple and inner hot-spot distribution differ — runtime alternates `bullet → bullet_alt` per shot for a cheap muzzle pulse without a per-shot animation clip.

### bullet_rocket
- hand-written SVG (path-based warhead nose + body + tail flame). 18x10 single frame.
- layout: single-frame SVG, right-facing canonical orientation (warhead nose points to +X)

### bullet_laser
- hand-written SVG with a `<linearGradient>` for the glow envelope. 16x4 single frame.
- layout: single-frame SVG, right-facing horizontal beam

**Hints**
- The laser is the one SVG that **uses gradients** intentionally (laser glow is a smooth envelope, not pixel art). Everything else in this pack is `crispEdges` 1x1-rect pixel art — do not mix.

### boss_soul family
- script-generated SVGs via [`tools/make_boss_soul_bullets.py`](../../tools/make_boss_soul_bullets.py) (character-grid → SVG rects). Shared boss-soul palette: D `#2a1ca0` / M `#5d44d8` / H `#9b85ff` / C `#aeefff` / W `#f0eaff` / halo-near `#c4b8ff @ 0.92` / halo-far `#8a78ff @ 0.36`. See [spec/art/svg-best-practices.md § 4. 家族级批量生产](../../.vibegame/spec/art/svg-best-practices.md).
- layout: 10 single-frame SVGs at varied canvas sizes covering the boss bullet vocabulary —
  - `dot` 8x8 (tiny mass-fire pellet)
  - `square` 8x8 (small geometric variant)
  - `orb` 16x16 (round mid-size)
  - `core` 16x16 (high-density hot-core variant)
  - `block` 16x16 (square mid-size)
  - `shard` 12x16 (angular projectile)
  - `dart` 16x8 (horizontal directional dart, right-facing)
  - `lance` 24x6 (extra-long piercing lance, right-facing)
  - `wave` 32x16 (wide wave slab — used for boss melee wave attack)
  - `wall` 48x20 (screen-clearing barrier slab)

**Hints**
- The boss-soul palette stays consistent across all 10 shapes so the player reads "boss attacks share an identity" even as shape vocabulary shifts. Family consistency matters more than per-shape identity for clutter readability.
- A sister script [`tools/preview_boss_soul_bullets.py`](../../tools/preview_boss_soul_bullets.py) renders the entire family onto one 6x-scaled contact sheet — used as VLM audit input before delivery.

## Tileset (Map)

### dungeon_3x3 — warm-sandstone wall + floor tile pack
- prompt
  ```
  A pixel-art dungeon SPRITE SHEET arranged in a 3x3 grid on a solid magenta background. Nine independent dungeon-tile sprites on pure magenta (#FF00FF) marker background. Each sprite sits centered inside its own cell with a clear magenta margin.

  PERSPECTIVE RULE (most important, read carefully):
  This sheet uses a STYLIZED 45-DEGREE TOP-DOWN tile projection (like Pokemon dungeons, Stardew Valley dungeons, or classic 16-bit JRPG dungeons). Critically, this is ORTHOGRAPHIC, NOT true 3D oblique projection. Specifically:

  - ROW 1 sprites (walls and door) are CUBOID BLOCKS. Each cuboid is drawn as TWO STACKED RECTANGULAR REGIONS:
    - The UPPER ~25 PERCENT of the cuboid sprite is the TOP face, drawn as a clean horizontal rectangle representing the cuboid's top surface seen from a slight overhead angle.
    - The LOWER ~75 PERCENT of the cuboid sprite is the FRONT face, drawn as a clean rectangle representing the cuboid's front surface.
  - CRITICAL ALIGNMENT RULE: The TOP face and the FRONT face MUST be the EXACT SAME WIDTH. Their LEFT edges align on the same vertical line, and their RIGHT edges align on the same vertical line. The cuboid's overall silhouette is a CLEAN VERTICAL RECTANGLE, not a parallelogram, not a trapezoid, not a 3D box with oblique skew.
  - The top face is NOT drawn as a tilted parallelogram receding into the distance. It is a flat horizontal strip at the top of the sprite, with markings (texture, mortar lines) that simply hint that this surface is "up there" rather than using perspective foreshortening.
  - The transition between top face and front face is a single clean horizontal line.
  - You do NOT see the side faces of the cuboid.
  - The cuboid sprite outline is a perfect vertical rectangle (like a domino standing upright), with no diagonal edges anywhere on its silhouette.

  - ROW 2 and ROW 3 sprites (floors) are FLAT SQUARE SLABS in PURE STRAIGHT TOP-DOWN view.

  CUBOID FOOTPRINT RULE:
  - Horizontal width of each row-1 cuboid is IDENTICAL to the horizontal width of each row-2 / row-3 floor slab.
  - Each cuboid is a SINGLE solid block (not a stack of multiple stones).
  - No floor visible underneath the cuboid.

  Layout, row by row, left to right:

  Row 1 (orthographic cuboid blocks, top ~25% flat horizontal strip, front ~75% rectangle, no oblique skew):
  - (1,1) Wall block variant A. A single sandstone cuboid block in orthographic 45-degree projection. TOP face (upper 25%): a clean horizontal strip of mid-tan sandstone with subtle weathering speckle, slightly darker than the front face to suggest it is "the top". FRONT face (lower 75%): mid-tan sandstone, with 2-3 small natural cracks, one horizontal mortar line near the middle, slightly darker bottom edge for grounding. The top-front boundary is a single horizontal line. Cuboid silhouette is a clean vertical rectangle.
  - (1,2) Closed door pillar. A single CUBOID STONE PILLAR with the same orthographic projection as the wall blocks. TOP face (upper 25%): dark obsidian-black horizontal strip with a single glowing crimson rune sigil. FRONT face (lower 75%): same dark obsidian-black stone with 2-3 short glowing crimson rune lines etched horizontally. Cuboid silhouette is a clean vertical rectangle, the SAME outline shape as the wall blocks.
  - (1,3) Wall block variant B. Same wall family as A: same sandstone palette, same orthographic projection, same clean vertical rectangle silhouette. Visually distinct: chipped top-right corner (the chip is a small notch out of the top-right of the top face), one longer diagonal crack across the front face, one small embedded pebble.

  Row 2 (flat square floor slabs, pure straight top-down view):
  - (2,1) Floor tile 1. Plain warm-sandstone floor slab. Square outline. Dark mortar grid along the slab edges. Subtle surface speckle.
  - (2,2) Floor tile 2. Same flat floor base, with one prominent zig-zag crack running diagonally.
  - (2,3) Floor tile 3. Same flat floor base, with a small square drain grate set INTO the floor: four dark iron bars over a recessed black hole, flush with surface.

  Row 3 (more flat square floor slabs):
  - (3,1) Floor tile 4. Same flat floor base, with a small skeletal hand-bone fragment lying flat.
  - (3,2) Floor tile 5. Same flat floor base, with a thin moss patch growing along one mortar seam.
  - (3,3) Floor tile 6. Same flat floor base, with a dried crimson bloodstain.

  Visual contrast (mandatory):
  - All 9 sprites have the SAME horizontal width (same base footprint).
  - Row 1 cuboids each have a CLEAN VERTICAL RECTANGLE outline (no oblique edges, no parallelogram top, no perspective skew).
  - Row 1 cuboids show top + front as two stacked horizontal regions of the SAME WIDTH, separated by a single horizontal line.
  - Row 2 + Row 3 floors are flat squares.
  - The cuboid silhouettes should look like upright dominoes — rectangular, vertical, no diagonal edges anywhere on the outline.

  Style: pixel art, chunky readable pixels, integer pixel scale, crisp dark 1-pixel outlines, limited warm-stone palette (sandstone tans for walls; deep mortar browns; charcoal shadows; dark obsidian-black for door with crimson rune accents; bone-white, olive-green, dried-crimson floor accents). Soft top-down ambient light.

  Strict rules:
  - Exactly 9 sprites in a 3x3 grid. No extra sprites, no missing sprites.
  - Each sprite centered within its 1/9 share of the canvas with at least 10% magenta margin per side.
  - All 9 sprites share the SAME horizontal width within their cells.
  - Row 1 cuboid silhouettes are CLEAN VERTICAL RECTANGLES — every edge of the silhouette is either purely vertical or purely horizontal. NO diagonal edges on any cuboid's outer silhouette.
  - Row 1 cuboid total height is modestly greater than row 2/3 floor slab height (because of added top strip), but not dramatically taller.
  - No sprite crosses into a neighboring cell.
  - No magenta pixels INSIDE any sprite.
  - No text, no labels, no numbers, no UI, no HUD, no speech bubbles.
  - No frames, no decorative box, no grid lines drawn on the magenta.
  - Background between and around sprites is solid flat magenta only.
  ```
- layout: 3x3 grid, 9 independent sprites on solid magenta marker background — row 1 = 3 wall/door cuboids, row 2 + row 3 = 6 floor variants

**Hints**
- **Sparse 3x3 raw + split-in-post pipeline.** Image-gen cannot produce a packed semantic tileset (a single sheet pre-laid out with `wall_top` / `wall_face` / `wall_full_alt` / ... slots in fixed engine-ready positions) in one call. The working pipeline is: (1) image-gen produces a 3x3 raw of 1 door + 6 floor + 2 wall cuboids; (2) floors become `tileSize × tileSize`; (3) wall/door cuboids become `tileSize × y` (`tileSize < y < 2*tileSize`, keep the cut cuboid's aspect ratio, do not force-stretch to a round 2× height); (4) each tall cuboid splits into a `_face` (bottom 32×32, fully opaque) plus a `_top` (upper `32×(y-32)` portion alpha-padded at the top of a 32×32 transparent canvas), so all final tiles are uniform 32×32; (5) concat into one row atlas.
- **The split is the tilemap pattern's load-bearing prior.** At runtime the `_top` tile sits in the row above the `_face` tile, and depth ordering `wallTop > wallFace > floor` makes `_top`'s opaque lower portion overhang the floor cell behind it — that overhang is what produces the slanted/3D pop-out look. Ship walls as single tall 32×y sprites and the engine renders them as misaligned squares with no perspective.
- **Walls and doors must be cuboids with the SAME footprint as floors.** Without this constraint the model defaults to tall pillars / stelae / wood spikes for walls and doors, which break tiling continuity with the flat floor squares below them. The prompt body has to say (a) "each row-1 cuboid horizontal width is IDENTICAL to row-2/row-3 floor slab", (b) "each cuboid is a SINGLE solid block, not a stack of stones", (c) "no floor visible underneath the cuboid". Floor-and-wall footprint match is what lets the level look continuous in-game.
- **Perspective is 45° orthographic top-down, NOT 3D oblique.** Walls drawn in true 3D oblique come out with parallelogram tops that don't tile cleanly against the flat-square floors. The prompt's "ORTHOGRAPHIC, NOT 3D oblique" + "top face and front face MUST be EXACT SAME WIDTH" + "CLEAN VERTICAL RECTANGLE silhouette" + "no diagonal edges on any cuboid's outer silhouette" together enforce the right projection. This phrasing converged over multiple iterations (45° front-dominant → 70° top-dominant → orthographic same-width) — keep all four clauses or the model regresses.
- **Cell-by-cell content list is mandatory.** Each of the 9 cells gets its own numbered description (`(1,1) Wall variant A`, `(1,2) Closed door pillar`, `(2,3) Floor with drain grate`, ...). Without this the model invents arbitrary tile contents and the wall/floor/door distribution drifts.

## UI

### hud_panel + bars + icons
- prompt missing — see [`spec/contracts/status_bar.md`](../../.vibegame/spec/contracts/status_bar.md). HUD is a 3-layer status-bar composite (icon + slot + bar) per stat, wrapped in a pixel-art panel that hosts all three stats and the weapon slot.
- layout: one panel PNG + per-stat (icon, slot, bar) triplet PNGs + one weapon-slot frame PNG

### button_pause, icon_coin, upgrade buff icons
- hand-written 1x1-rect-per-pixel pixel-style SVGs. See [spec/art/svg-best-practices.md](../../.vibegame/spec/art/svg-best-practices.md).
- layout: single-frame SVG each, `shape-rendering="crispEdges"`, transparent background. `button_pause` is 40x40, the rest are 16x16. **Upgrade buff icons (8 buffs: fire_rate / speed / max_hp / max_shield / max_mana / damage / penetrate / double_shot) are inlined as string constants in [scripts/UpgradeUI.js](../../scripts/UpgradeUI.js) `ICON` dict, NOT shipped as separate `.svg` files** — they get injected into the DOM level-up overlay directly.

**Hints**
- For small DOM-overlay icons that follow a CSS theme color, inlining the SVG as a string constant in the consuming script (instead of shipping a separate `.svg` file) is preferred: no fetch + no manifest entry, and the inlined `fill="currentColor"` follows CSS color inheritance automatically.

### minimap (procedural exception)
- procedural script: [`tools/make_minimap_assets.py`](../../tools/make_minimap_assets.py) (PIL putpixel / rect fills).
- layout: nine independent single-image PNGs — 1 panel + 6 room-state markers + 2 connector strips

**Hints**

Procedural PIL generation **violates the artist default of image-gen for art assets**. It is permitted here only because all three of the following conditions hold:

1. **User explicitly approves** the procedural path for this UI subset (programmatic authoring is opt-in, not the artist's default decision).
2. **The asset is a dynamic HUD overlay**, not a static piece of art — minimap room states cycle through current/explored/adjacent/hidden/start/boss at runtime, and connector lengths bind to JS layout constants (`Minimap.js` `GAP_X = 24` / `GAP_Y = 20`). Image-gen → cut → align cannot guarantee pixel-exact match to runtime constants.
3. **Retro pixel style** with a tiny per-asset canvas (<30x30 px each). At this scale image-gen output is indistinguishable from hand-painted PIL pixels but PIL gives exact pixel control.

If any of these three conditions fails, fall back to image-gen.
