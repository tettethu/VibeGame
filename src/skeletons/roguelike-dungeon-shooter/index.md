# Roguelike Dungeon Shooter Skeleton

Top-down twin-stick dungeon shooter: linear multi-room dungeon, weapon-pickup combat, enemy waves trigger by room entry, boss room finale, magnet-orb pickups, DOM HUD + minimap, DOM upgrade choice between rooms. Cherry-pick the files in this directory into a new project — the skeleton is runnable as-is via `vibegame run` (placeholder art throughout: colored shapes for characters/bullets, procedurally generated flat-color PNGs for tileset/HUD/minimap/weapon-icon chrome), so you can already see room flow, combat, and HUD before swapping in real art.

## Production shape

- **Top-down camera.** Single fixed camera that follows the player; world is larger than viewport, scroll on follow.
- **Tilemap-built dungeon.** One tileset (32×32) + one `.tilemap.json` describing the entire multi-room world. Rooms are tile rectangles in the same tilemap, not separate maps. Walls and floors come from the tileset; doors are independent dynamic nodes overlaid on tile positions.
- **5 rooms in a linear/branching layout.** Default 5 rooms (1 start + 3 combat + 1 boss). Layouts (`cross`, `tee`, `ell`) live in `config/layouts.json` — each is a list of `{col, row}` grid positions; corridors connect adjacent rooms automatically.
- **Room-based combat trigger.** Entering a combat room locks both doors, spawns the room's wave from `config/waves.json`, opens both doors when the room is cleared. Upgrade choice (3-of-N buff pool) fires *after* the room clears, not during combat.
- **Two persistent characters per spawn.** Player and Chest are scene-declared (in start room). Enemies / bullets / pickup orbs / weapon drops are runtime-spawned via `instantiate()` from `entities/*.node.json` templates.
- **Magnet-orb pickups.** XP / coin / mana drops gravitate to the player within a magnet range, then disappear on contact (callback grants resource).
- **DOM overlay HUD.** Pixel-art HUD with HP/shield/mana bars + weapon slot + minimap. Use `var(--font-ui)` and `var(--font-display)` (Pixelify Sans + zpix for CJK). All overlays (pause, upgrade choice, end screen) are DOM, not Phaser.Text.

## Visual proportions (practice-verified starting point)

Use these as starting `.node.json` `width` / `height` values. Numbers are from the seed roguelike project (viewport 960×540, tile 32×32, room 21×15 tiles, world ~3 rooms wide). New projects of this sub-genre can keep these or scale uniformly — the relative ratios are what makes the genre "feel right".

| Element | Render w × h (px) | % of viewport (w × h) | Tile equivalents |
|---|---|---|---|
| Viewport | 960 × 540 | 100% × 100% | 30 × 16.9 tiles |
| Tile (logical) | 32 × 32 | 3.3% × 5.9% | 1 × 1 |
| Single room (interior) | 672 × 480 | 70% × 89% | 21 × 15 tiles |
| Corridor (between rooms) | 288 × 160 | 30% × 30% | 9 × 5 tiles |
| Player | 56 × 80 | 5.8% × 14.8% | 1.75 × 2.5 tiles |
| Slime (low-tier melee) | 32 × 32 | 3.3% × 5.9% | 1 × 1 tile |
| Bat (low-tier air) | 128 × 80 (atlas) / 18 dia (collider) | — | wide flap, tiny hitbox |
| Archer (ranged) | 44 × 58 | 4.6% × 10.7% | 1.4 × 1.8 |
| Boss | 96 × 192 | 10% × 35.6% | 3 × 6 tiles |

**Boss vs Player** — width 1.71×, height 2.4×. Boss is taller and narrower than a 3× uniform scale — read as "looming pillar", not "giant of same shape".

**Room vs Viewport** — a single room (21×15 tiles = 672×480 px) is slightly *smaller* than the 960×540 viewport in width but larger in height ratio than typical. Camera does NOT fit-one-room-per-screen — it follows the player so multiple adjacent rooms can be visible during transitions. If you need strict one-room-per-screen (Zelda 1 style), shrink rooms to ~30×16 tiles and disable camera follow within a room.

## Files

```
project.json                — settings.width 960, settings.height 540, pixelArt true, top-down (no gravity)
config/
  input-map.json            — WASD/arrow move, mouse aim, LMB shoot, Space roll, E interact, F switch, P pause
  player.json               — hp, shield, mana, moveSpeed, rollSpeed, rollDuration, rollCooldown, invulnDuration
  weapons.json              — per-weapon stats: damage, fireRate, projectileSpeed, spread, recoil, magnet, etc.
  waves.json                — per-room enemy spawn list (slime/bat/archer/mage/ghost + counts)
  dungeon.json              — roomWidth 21, roomHeight 15, corridorWidth 9, corridorHeight 5, tileSize 32, rooms 5
  layouts.json              — named layouts: cross/tee/ell, each a list of {col, row} grid cells
  door.json                 — door states (open/locked), display size, lock-on-entry delay
  elements.json             — bullets, weaponDrop, weaponVisual, enemyHpBar, expOrb, chest visual constants
scenes/
  main.scene.json           — root tree: GameManager + persistent _templates (disabled) + Player + Chest + HUD + UpgradeUI + LevelUpManager + Minimap + RoomManager
scripts/
  GameManager.js            — root orchestrator: load configs, build map+rooms+corridors, manage start-run / end-run lifecycle, pause routing
  RoomManager.js            — room state machine: detect player entry, lock doors, spawn wave, watch clear, open doors, trigger upgrade
  DoorManager.js            — door open/close API + physics body toggle
  Minimap.js                — DOM minimap showing room grid + explored/current/boss markers
  HUD.js                    — DOM HUD (hp/shield/mana bars + weapon icon slots + crit pulse)
  UpgradeUI.js              — DOM 3-card buff choice overlay (category-banded cards, keyboard 1/2/3 or click)
  LevelUpManager.js         — XP queue + buff-choice trigger gate (only fires between rooms, not mid-combat)
  Player.js                 — movement (WASD), aiming (mouse), shooting, roll/dash, weapon swap (F), pickup (E)
  WeaponVisual.js           — visual weapon sprite attached to player, rotates toward cursor (NO flipX — see errors.md)
  Bullet.js                 — projectile node spawned by Player and Enemy weapons; speed/spread/damage from config
  Enemy.js                  — base class: HP bar, damage display, death VFX, drop logic (XP/coin/mana/weapon)
  SlimeEnemy.js / BatEnemy.js / ArcherEnemy.js / MageEnemy.js / GhostEnemy.js / SkeletonHandEnemy.js
                            — per-type AI (chase/shoot/teleport)
  BossEnemy.js              — 2-phase boss (chase + ranged + skeleton-hand transition + phase-2 dash)
  WraithShardEnemy.js       — boss summon (low HP, attention-splitter)
  Chest.js                  — proximity-open + E-pickup with floating weapon icon
  WeaponDrop.js             — pickup-on-floor weapon with floating tag + E prompt
  ExpOrb.js / CoinOrb.js / ManaOrb.js
                            — magnet-collectible resource orbs (3 near-identical scripts — promote to MagnetOrbModule)
entities/
  player.node.json          — atlas visual + dynamic collider + child WeaponVisual node
  boss.node.json            — atlas visual + dynamic collider + script BossEnemy
  slime / bat / archer / mage / ghost / skeleton_hand / wraith_shard.node.json
                            — per-enemy templates; scene declares disabled _XxxTemplate placeholders, RoomManager instantiates at runtime
  chest.node.json           — atlas visual + Chest script
assets/
  manifest.json             — RUNNABLE placeholder art. 9 placeholder_atlas, 15 placeholder_image, 21 real image (DOM/Image()-
                              consumed HUD/minimap/coin/weapon-icon chrome, each pointing at its own generated flat-color PNG
                              or, for icon_coin, SVG), 1 real tileset pointing at a procedurally generated sheet.
                              Swapping to real art: placeholder_atlas -> atlas + path + sprites bboxes, placeholder_image ->
                              image + path (see contracts/prototype_polish.md); the 21 DOM/Image()-consumed image entries and
                              the tileset entry need NO manifest edit at all — their path already matches the live
                              project's real asset path, so swapping is a straight file replace, identical to the tileset
                              PNG swap.
  tilesets/                 — dungeon_semantic_placeholder.png, a procedurally generated flat-color sheet
                              (16 cols x 12 rows, 32px cells) matching the manifest's tile indices.
  ui/, ui/minimap/          — 16 procedurally generated flat-color PNGs for DOM-consumed HUD panel/bars/icons and minimap
                              panel/room/connection cells, plus ui/icon_coin.svg (coin counter, DOM Image()-consumed).
  weapons/                  — 4 procedurally generated flat-color PNGs for weapon-slot icons (HUD.js Image()-consumed,
                              muzzle-up vertical rects at the live project's real weapon-sprite dimensions).
```

## Running the skeleton

`vibegame run` needs `engine/` present at the skeleton root. This directory intentionally ships without it (normally `vibegame init` copies `engine/` into a real project) — symlink or copy the framework's `engine/` in before running:

```bash
ln -sfn /path/to/framework/engine skeletons/roguelike-dungeon-shooter/engine
vibegame check skeletons/roguelike-dungeon-shooter
vibegame run skeletons/roguelike-dungeon-shooter
```

Pixel fonts (`assets/fonts/*.ttf`) are not shipped in placeholder mode; `index.html`'s font stack already falls back to system sans-serif, so text still renders.

## Key engine decisions baked in

- **Top-down → no gravity.** `project.json.settings.physics.gravity = { x: 0, y: 0 }`. Every collider sets `gravity: false`.
- **Pivot `[0.5, 0.5]` for every atlas/image asset.** Engine default is `[0.5, 1]` (bottom-center, for platformers). Top-down centered sprites need `pivot: [0.5, 0.5]` at the manifest group level. Tilesets do NOT need pivot.
- **Tilemap as canonical map.** Walls and floors from one tilemap (`maps/dungeon.tilemap.json`), not Phaser Graphics primitives, not per-room separate maps. Doors are independent dynamic nodes overlaid; `invisibleWall` zones are last-resort for shape-irregular collision (see errors.md for coordinate convention).
- **Runtime spawning via `instantiate()`.** Disabled `_XxxTemplate` nodes in scene JSON register the entity type with the engine; `RoomManager` / `GameManager` call `instantiate('entities/<type>.node.json')` to spawn dynamic instances. Never assemble nodes from raw objects.
- **HUD + overlays = DOM, not Phaser.Text.** Inject `<div>` overlays into `#game-container` ; use `var(--font-ui)` (Pixelify Sans + zpix CJK) so Latin and Chinese both render pixel-art. `Phaser.Text` is banned by `spec/engine/ui.md`.
- **CSS scale, not engine scale-mode.** `index.html` boots Phaser at 960×540 (CSS-fixed `#game-frame`), THEN applies `transform: scale(...)` to letterbox into the viewport. Phaser's scale manager stays at NONE — game logic always sees 960×540 logical coords.
- **Boot order matters.** `await boot(gameContainer)` MUST come before `updateGameScale()`. Reversing produces a logical-resolution = visual-scale bug at start.

## When the skeleton needs a module

| Concern | Module | Why module |
|---|---|---|
| XP / coin / mana magnet pickup | `MagnetOrbModule` | Three near-identical scripts in `scripts/` (ExpOrb / CoinOrb / ManaOrb) consolidate to one configurable module — `orbType`, `texture`, `magnetRange`, `maxSpeed`, `onPickup` callback |
| Room-grid minimap | `MinimapModule` | DOM-based grid renderer with room states (explored / current / adjacent / boss / hidden); reusable across any room-based game (roguelike / metroidvania / dungeon crawler) |
| DOM 3-card upgrade choice | `UpgradeChoiceModule` | Used between rooms for buff selection; reusable in any run-based progression where the player picks 1-of-N at checkpoints |

The remaining scripts (Player / Enemy* / Boss / Bullet / GameManager / RoomManager / HUD / Chest / WeaponDrop / WeaponVisual / DoorManager / LevelUpManager) are sub-genre-bound and stay as cherry-pickable skeleton files.

## Art reference

See [`art-pack.md`](art-pack.md) for the empirical art recipe — per-asset prompts, layout, and reusable techniques (notably the rotation-as-frame trick used to expand `player_run` into `player_roll`). The included `art-pack-assets/player_run.png` is the canonical style reference; future projects of this sub-genre must i2i from it, not text-only.
