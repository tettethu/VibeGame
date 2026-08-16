# Contracts Index

Cross-role collaboration contracts. Each file describes one production type and one or more named **Patterns**. The orchestrator picks a Pattern at task creation time and writes a short sentence in `prd.md` `Reuse / Constraints`; downstream roles route based on that decision, they do not pick Patterns themselves.

| Contract | Production type | Patterns | Pick when |
|---|---|---|---|
| [`rastermap.md`](rastermap.md) | Level / arena layout | `rastermap` | Single bespoke background PNG with invisible explicit colliders — side-scroller backgrounds, boss arenas, fixed-screen platformer slices |
| [`tilemap.md`](tilemap.md) | Level / arena layout | `tilemap` | Grid of reusable tiles with tile-level collision — Celeste-style levels, top-down dungeons, procedural maps. References `spec/engine/tilemap-guide.md` for the runtime API. |
| [`status_bar.md`](status_bar.md) | UI status bar | `sprite-backed-status-bar`, `fighting-hud-dom`, `discrete-icon-meter` | Resource meters (HP, mana, stamina, shield, boss posture). Pick `sprite-backed-status-bar` for continuous-fill independent meters; `fighting-hud-dom` for a mirrored fighting-game match HUD; `discrete-icon-meter` when each unit is a distinct icon (mask / heart / pip) and partial fill is not meaningful |
| [`game_overlay.md`](game_overlay.md) | Pause / death / victory / custom menu overlay | `dom-overlay-with-phaser-pause` | Single-screen game with full-screen menus (pause, death, victory, prompts). Pattern correctly halts BOTH `sceneTree.running` AND `scene.scene.pause()` so physics / anims / timers truly freeze. |
| [`charge-family.md`](charge-family.md) | Hold-charge-release ability animation pack | `three-sheet-charge-release` | Any ability with three phases: build-up while held → looping peak swirl at max charge → committed release stroke. Examples: nail-charge (Hollow Knight), spin attack (Zelda), R2 heavy (Souls), charged buster (Megaman). |
| [`digit.md`](digit.md) | Numeric HUD UI | `dom-css-digit-hud` | Score, timer, combo, best score, or other frequently-changing numbers. Defaults to DOM/CSS unless a raster digit sheet passes strict completeness and clipping QA. |
| [`dom_card.md`](dom_card.md) | DOM card hand frontend | `dom-card-hand-frontend` | Fixed-screen turn-based card battlers that need a browser-DOM hand renderer for pure card data: atlas card art, text layers, energy gating, hover lift, drag-to-target play, target highlight, tooltip, logical-resolution scaling, and card reward frontends. |
| [`sideview_fighter.md`](sideview_fighter.md) | Player combat controller | `sideview-fighter-module` | Side-scrolling action game with directional movement, jump, dash, guard, attack combo, optional deathblow. Module handles input→animator→hitbox; project layer owns damage/overlap/HP. |
| [`prototype_polish.md`](prototype_polish.md) | Prototype-to-real-art workflow | `prototype`, `polish` | Early-project two-task flow where gameplay ships first on `placeholder_atlas` / `placeholder_image` manifest entries, then a follow-up task swaps in registered real art without redesigning behavior. |
| [`parallax_background.md`](parallax_background.md) | Scrolling multi-layer background | `scrolling-parallax-layers` | Side-view scene needs a depth-layered scrolling background from independently generated art layers (pinned sky + drifting clouds + parallax silhouettes). Uses `ParallaxModule`, one node per layer; playable terrain stays a separate collider / `rastermap` asset. |
| [`runtime-ai.md`](runtime-ai.md) | Runtime AI | `chatbot-as-game-character-or-player` | A game character or player uses a runtime LLM for speech and bounded gameplay actions, with legal-option validation and an explicit product-defined unavailable path. |

## How to use this index

1. At the start of every new task, scan this table.
2. For any contract whose production type matches the task's product description, open the contract and read its Patterns' `### When to use` sections.
3. Pick exactly one Pattern per applicable contract.
4. Write the decision into `prd.md` `Reuse / Constraints` as a sentence: `Use <contract> pattern <pattern-slug> because <task-specific reason>.`

If no contract here matches the task, the default `spec/engine/` guides cover the case. Do not invent a contract file inline in `prd.md`; if a new production type recurs, raise it for the `self-evolve` workflow to capture as a real contract.

## Schema reminder

See `self-evolve` skill for the contract file schema: `## Pattern N: slug-N` → `### When to use` + `### Responsibility` (with `#### Artist`, `#### Architect/Programmer`, `#### Player`, `#### Reviewer` subsections as needed) + optional `### Manifest and asset boundary`. The `#### Artist` chapter has a nested mandatory `##### Workflow` (H5) with exactly three steps Generate / Package / Verify — see `skills/artist-self-evolve/SKILL.md` Phase 3 for body shape rules. Patterns where artist has not yet participated in a real project replace the chapter body with a placeholder sentence (see `game_overlay.md` and `status_bar.md` Pattern 2 for examples).
