# Skeleton Catalog

Runnable placeholder baselines for common game sub-genres. Each subfolder under `skeletons/` is an openable project whose scene flow, proportions, timing, colliders, HUD, and runtime state survive later asset replacement.

**This file is the selection catalog.** When picking a sub-genre, read the row(s) below to decide which `<slug>` matches the request. Once a slug is chosen, open `skeletons/<slug>/index.md` for the project's actual rules, features, and systems — it does not repeat the "when to use" question.

**Process**

1. Orchestrator scans this catalog only when establishing the first playable baseline or after an explicit genre pivot.
2. Pick one slug whose row matches the user's request.
3. Read `skeletons/<slug>/index.md` and use its coherent project surfaces as the baseline or source material.
4. Keep skeleton selection out of `prd.md` and teammate prompts; downstream roles receive only project facts and task contracts.

Orchestrator owns the baseline decision. `architect`, `programmer`, and the rest do not pick a slug themselves.

## Catalog

| Slug | Production-shape one-liner | When to use | When NOT to use |
|------|---------------------------|-------------|-----------------|
| [`2d-action-boss-fight`](2d-action-boss-fight/index.md) | Direct project-shaped 1v1 side-scroller boss-fight skeleton: arena scene, player FSM, boss FSM, projectiles, FX, HUD, overlay, stripped manifests | 1v1 boss-fight slice; Hollow Knight / Cuphead-boss / Sekiro-2D style. Use when a future project can start by replacing assets and lightly editing config / glue. | Multi-enemy wave / horde — use a roguelike skeleton; PvP flat-plane fighter — use `fighting-2d-arcade`; multi-arena exploration — use a metroidvania skeleton. |
| [`roguelike-deckbuilder`](roguelike-deckbuilder/index.md) | Fixed-screen turn-based card-battler skeleton: deck / hand / discard / energy loop, bottom arc DOM card hand, enemy intent, HUD, reward picker, placeholder runtime surface | Slay-the-Spire-style single battle slice with draggable cards, player/enemy turns, card rewards, and atlas-backed DOM card frontend. Start by replacing card data, enemy intent table, and placeholder atlas entries. | Real-time action roguelike — use `roguelike-dungeon-shooter`; side-scroller boss fight — use `2d-action-boss-fight`. |
| [`roguelike-dungeon-shooter`](roguelike-dungeon-shooter/index.md) | Top-down room-based dungeon shooter: procedural room graph, tilemap floors/walls, player movement + ranged weapons, enemy waves, pickups, boss room, minimap, upgrade choices | Vampire Survivors / Soul Knight / Enter the Gungeon style dungeon action with many enemies, runtime-spawned projectiles, pickups, rooms, and repeatable upgrade loops. | Single 1v1 boss arena — use `2d-action-boss-fight`; fixed-screen swipe slicing — use `swipe-slice-arcade`; pure platforming or exploration-first metroidvania — use a side-scroller / metroidvania skeleton. |
| [`swipe-slice-arcade`](swipe-slice-arcade/index.md) | Runnable placeholder baseline — fixed single-screen pointer-swipe slicer: objects lob up under gravity, swipe to slice into physics halves + juice VFX, combo on multi-cut, hazard-instant-lose + N-miss lose, logarithmic difficulty ramp, DOM HUD | Fruit-Ninja-style swipe-to-slice high-score arcade; any game whose core is "draw a path through flying targets" with combo and a do-not-cut hazard. Uses `SwipeSlashModule` + `TimedImageVfxModule`. | Targets tapped/clicked individually rather than swiped through — plain pointer input suffices; scrolling / exploration / platforming — use a level-based skeleton; grid match — not this. |
| [`2d-bounce-parkour`](2d-bounce-parkour/index.md) | Side-view precision bounce-platformer: player FSM (idle/run/jump/fall/dash/bounce), single air-dash refreshed on stomp, floating bounce-targets (sin-float + breath scale + pop-launch, circle collider), multi-stage flow with per-stage tries/best localStorage + clear/final overlay, DOM pixel-font HUD, `ParallaxModule` scrolling background, camera follow + stomp zoom/shake juice, fall-off-bottom instant respawn | Precision / rhythm platformer whose core is timing a chain of stomp-bounces across floating targets to reach a goal (Celeste-dash-flavored, "don't touch the ground" bounce runs) with a short linear multi-stage retry-count mastery loop. Uses `ParallaxModule` (`scrolling-parallax-layers`). | Free-roam / exploration platformer or metroidvania (this is short linear stages, no scrolling level authoring); combat-driven side-scroller — use `2d-action-boss-fight` / `sideview_fighter`; grid-tile level authoring — use a `tilemap` skeleton. |
