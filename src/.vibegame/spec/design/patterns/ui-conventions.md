# UI Conventions

Project-level UI / HUD / screen patterns. Pick the default unless your game's mechanic clearly calls for an override; capture the chosen variant in GDD as a one-line decision.

> **Reminder**: write **intent and semantics** (what is shown, where, when), never production specifics (px sizes, frame counts, shake amplitudes) and never implementation form (placeholder, CSS, or authored asset). Both are programmer / artist's call. Whether a screen needs authored art is decided during implementation against `engine/ui.md`, not here and not in the GDD.

---

## Player HP / status display

**Default**: continuous bar at top-left.
- Why: action games have varying damage; players need precise read of remaining HP. Bar is universal, low cognitive overhead.

**Override to badge row** when game has 1-3 hit limit (classic platformer, lives mechanic — Mario, Castlevania).

**Override to no HUD(only when user specifies)** when game is atmospheric / immersion-first and damage is signaled diegetically (Dead Space style vignette / heartbeat).

**Override to other design** when user gives creative and achievable ideas.

| Layer | Spec |
|---|---|
| Programmer params (code-only) | position, bar width, fill update from `hp / hpMax` each frame |
| Procedural shortcuts | badge row = artist delivers 1 icon, programmer arrays N copies |

**GDD line**: `Player HP: bar at top-left` or `Player HP: 3-heart badge row at top-left`

---

## Boss HP / status display

**Default**: full-width bar at bottom center, shown only during boss encounter.
- Why: boss HP is the visual statement that "this is a boss fight". Bottom-center feels cinematic (Hollow Knight, Cuphead).

**Override to top-center** when game has arcade-y / shmup feel (classic platformer bosses).

**Override to multi-segment** when boss has discrete phase changes (e.g. 3 phases = 3 bar segments that empty in sequence).

**Override to no HP UI** when boss is a puzzle / mechanic encounter, not an HP grind.

| Layer | Spec |
|---|---|
| Programmer params | position, show on boss-encounter event, hide on boss-defeated event, fill from `boss.hp / boss.hpMax` |
| Procedural shortcuts | multi-segment = N segments side-by-side, no extra asset |

**GDD line**: `Boss HP: full-width bar bottom-center, with name label above` or `Boss HP: 3-segment bar bottom-center`

---

## Mob / regular enemy HP

**Default**: don't show.
- Why: HP for every mob = visual noise; useful only when player needs unit-level info.

**Override to bar above unit** when game is tactical / RTS / MMO-grind where mob HP matters per encounter.

**GDD line**: `Mob HP: not shown` or `Mob HP: small bar over unit, fades when full`

---

## Hit feedback

**Default for action games**: screen shake + brief flash + spark particle + hit-stagger animation on hit.

| Element | When | Asset needed |
|---|---|---|
| Screen shake | default for any impact | none (camera oscillation) |
| Hit flash | default for player taking damage | none (overlay) |
| Damage numbers | RPG / action-RPG / rouguelike; **not** default for platformers | font |
| Hit spark particle | default for combat games | one particle sprite (object class: spark / slash mark / dust — pick a class) |
| Hit-stagger animation | when target is interruptible (genre / per-entity / per-attack choice) | one `hit` action sheet per entity that can be interrupted |

**Interruptibility** — does the entity flinch (play `hit` animation) when damaged, or play through? Driven by genre:

| Genre | Player | Enemies / Boss |
|---|---|---|
| Action / melee combat (Hollow Knight, Souls, Sekiro) | flinches on hit | flinches in idle; attacks commit |
| Shooter / shmup | usually **doesn't** flinch (keeps shooting through hits) | small mobs die in 1-shot; large enemies may stagger |
| Platformer (Mario, Celeste) | knockback on hit | mobs usually just die, no stagger |
| RPG / hack-and-slash (Diablo) | stagger on big hits only | tier-dependent |

**Super-armor**: an entity that **never** flinches, even when not attacking. Used for raging phases / final boss states. Drop the `hit` animation entirely for that entity.

Whenever an entity flinches, designer must include a `hit` animation in the asset list.

**GDD line**: `Hit feedback: screen shake + flash on player damage; spark particle on enemy hit (class: spark); player has knockback hit-stagger`
**GDD line (boss)**: `Boss flinches in idle; phase 2 enters super-armor (no flinching).`

---

## Death effects

**Default**: dedicated `death` animation that ends with sprite removal, optionally followed by a particle burst.
- Why: image-gen artist reliably delivers a `death` action sheet for any character — a deliberate animation reads stronger than a fade. Use this whenever the entity has a character identity worth respecting (player, boss, named enemies).

**Override to particle burst only** when entity is small / abstract (e.g. slime, projectile-thing) — disappears in a puff, no animation needed.

**Override to fade-out** only as a fallback when no `death` animation can be produced (rare).

| Element | Asset needed |
|---|---|
| Death animation | one `death` action sheet from artist for that entity |
| Particle burst (after / instead of animation) | one particle sprite (object class: ash / spark / smoke / petal — pick a class) |
| Fade-out fallback | none (overlay) |

After-effects on player death: freeze → respawn prompt (programmer params, no asset).
After-effects on boss death: defeat banner / fade-to-black (programmer params).

**GDD line**: `Death effect (player): dedicated death animation → respawn prompt` and `Death effect (boss): dedicated death animation → defeat banner` and `Death effect (slime mob): ash particle burst, no animation`

---

## Pause / game over screens

**Default**: full-screen semi-transparent overlay with title + button stack (Resume / Restart / Quit).

**Override to none** when game is single-session arcade with no pause / instant restart.

| Layer | Spec |
|---|---|
| Programmer params | trigger (ESC for pause, hp<=0 for game over), button layout, key bindings |

**GDD line**: `Pause menu: standard 3-button overlay (Resume / Restart / Quit), triggered by ESC`

---

## Reminders for design language

| Write this (intent / semantics) | Not this (production / motion) |
|---|---|
| Boss HP shown as bar at bottom | Boss HP bar: 240px wide, bottom margin 20px |
| Death effect: particle burst, class ash | 12 ash particles spreading in 360° at 2.5px/frame |
| Hit feedback: shake + spark | Shake amplitude 8px decay 0.2s, sparks at hit-position |
| Player death has dedicated animation | Player death animates head-tilt then collapse over 18 frames |

The "Not this" entries are programmer / artist's job — designer writing them either locks in a number that breaks on later tuning, or asks for a visual precision (specific motion, exact pose) that image-gen can't deliver.
