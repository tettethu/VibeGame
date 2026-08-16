# Boss Design

Project-level patterns for designing boss encounters: attack categories, phasing, telegraphing, movement, AI rhythm, multi-phase structure.

> **Reminder**: write **intent and semantics** (action category, object class, spatial origin), never production specifics (frame counts, motion direction, exact poses, sub-frame phase divisions). Production specifics are programmer / artist's call.

---

## Visual scale

A boss is the focal threat of its arena and should read that way at a glance. Default size: **roughly half the screen height** at the camera's working zoom — large enough to feel imposing next to the player (whose typical height is ~10-15% of the screen), small enough to leave room for movement and telegraph readability. Smaller than this and the boss reads as "another enemy"; much larger and it eats the play space.

This is a starting heuristic, not a rule. Adjust when the design specifically calls for a giant boss (screen-filling silhouette, scrolling reveal) or a small one (swarmy / fast-moving). Whatever the choice, name it explicitly in the design brief so artist and implementer both target the same scale.

---

## Attack categories

Three default categories. Most bosses pick a mix of 2-3.

### Melee
- Range: close, in front of the boss
- Hit shape: front arc (180°) or AOE radius around impact point
- Object class: usually none — boss's own body / weapon does the damage

### Ranged
- Origin: from boss body (chest / hands / mouth — pick one)
- Trajectory: straight / arc / homing
- Spawn count: single / spread (e.g. 3-fan / 5-fan) / continuous burst
- **Object class**: designer specifies one — `bullet` / `arrow` / `fire-orb` / `lightning-bolt` / `feather-blade` / etc. Image-gen reliably renders named noun-class objects.

### Summon
- Spatial origin (pick one):
  - **From-above**: spawns at top of play area, falls down (most common for meteors / debris)
  - **From-ground**: rises from floor (spikes, vines, pillars)
  - **At-fixed-point**: pre-determined screen coordinates
  - **At-player**: tracks player position, telegraphs landing zone
- **Object class**: designer specifies — `meteor` / `spike` / `fire-orb` / `spike-pillar` / `summoned-creature` / etc.
- Telegraph: warning circle / glow / sound at landing point before impact (presence yes/no, not duration)

| Layer | Spec |
|---|---|
| Programmer params (code-only) | spatial position math, trajectory, spawn count, telegraph timing, hit detection |
| Required visual assets (artist) | boss action animations per category, object sprite for summons / projectiles, telegraph sprite, impact VFX |
| Procedural shortcuts | spread shots = 1 projectile sprite × N spawn angles; rain-of-objects = 1 object sprite × N spawn points (programmer arrays them) |

---

## Telegraph and warning

Every attack with a damaging area should give the player a fair read.

| Telegraph type | When |
|---|---|
| Animation tell (boss starts the attack motion — arm raises, mouth opens, glow) | always — comes free with the attack animation |
| Ground warning circle / shape | summons that land away from boss; ranged attacks with delayed impact |
| Color flash on boss | optional, for signature attacks ("this one is committed") |
| Sound cue | common for ranged / cast attacks |

**GDD line**: `Slam: animation tell only. Meteor-summon: ground warning circles + sound cue.`

---

## Boss interruptibility

See **`patterns/ui-conventions.md` → Hit feedback** for full context.

One design-feel choice: when the player hits the boss in idle (between attacks), does the boss flinch?

| Default for genre | Idle stagger |
|---|---|
| Action / melee combat (Hollow Knight, Souls) | yes — boss flinches, plays `hit` animation |
| Boss in raging / final-phase state | optional override to no — super-armor, boss never flinches |

**GDD line**: `Boss interruptibility: idle stagger; phase 2 super-armor (no idle stagger)`

---

## Boss movement

A boss that never moves feels like a punching bag. Pick the simplest movement that fits the encounter.

Movement is composed from these patterns based on game type, encounter feel, and per-skill behavior. A boss usually mixes 2-3 of them, plus movement embedded in specific skills.

**Standalone movement patterns** (boss does this between / instead of attacks):
- **Stationary**: doesn't move; rotates / facing-flips toward player. Simplest, focuses player on attack reading.
- **Always-chase**: continuously closes distance to the player. Pressure-driven feel.
- **Range-keep / kite**: chases when far, retreats when close (or vice versa — closes for melee, then backs off). Forces player to manage distance.
- **Irregular pacing**: alternates approach and retreat without strict logic — feels alive, hard to predict.
- **Multi-position teleport / dash**: snaps between fixed positions (corners, center) between attacks. Cinematic / supernatural feel.

**Skill-embedded movement** — the attack itself moves the boss:
- **Dash / lunge attack**: skill carries forward motion as part of damage frame
- **Jump / slam from above**: skill repositions vertically
- **Knockback recoil**: boss pushes itself back after a heavy hit on player

Designer's job is to **list which patterns this boss uses** based on game type and what feel each phase should have. Selecting patterns is intent; speeds, distances, and pathing are programmer's params.

**GDD line**: `Boss movement: chases player when > 200px away, kites back when < 100px (range-keep); meteor-summon attack repositions boss to arena center first; phase 2 adds teleport between corners`

---

## AI decision rhythm

Boss alternates between attacks with cooldowns. Two anti-patterns:
- "Always attacks back-to-back" — feels overwhelming, no breathing room
- "Random with no rhythm" — feels chaotic, no pattern to learn

**Default for single-phase bosses**: 2-4 attacks in rotation, each with its own cooldown. Distance determines which subset is available (close-range when player is close, ranged when far).

**Override to scripted sequence** when encounter is highly choreographed (e.g. opening cinematic, phase entry).

**Override to phase-gated rotation** for multi-phase bosses (each phase unlocks new attacks).

**Default cooldown**: each attack has its own cooldown (e.g. melee shorter, summon longer). Small randomization (±20%) keeps it feeling alive without pure randomness.

| Layer | Spec |
|---|---|
| Programmer params | decision tree / state machine, cooldowns, distance thresholds, randomization range |
| Required visual assets | none (logic only) |

**GDD line**: `Boss AI: 3 attacks (melee slam, ranged shout, meteor summon); melee when player < 200px, ranged 200-500px, summon when > 300px; per-attack cooldown with ±20% randomization`

---

## Phase transitions

Multi-phase bosses signal phase change with a cinematic moment players remember.

**Default**: at HP threshold, boss enters phase-transition animation (super-armor — uninterruptible), then unlocks new attack pool.

| Layer | Spec |
|---|---|
| Programmer params | HP thresholds, transition duration, attack pool changes per phase |
| Required visual assets | `phase-transition` action sheet (roar / power-up / form change) |

**GDD line**: `Boss phases: phase 1 (100-50% HP, 3 base attacks); phase 2 (50-0% HP, adds 2 super-armor attacks). Phase transition: roar animation, super-armor.`

---

## Reminders for design language

| Write this (intent / semantics) | Not this (production / motion) |
|---|---|
| Boss has 3 attacks: melee slam, ranged shout, summon meteors from above | Boss does an upward-cleave then spinning-roundhouse then triple-vertical-slash |
| Summon meteors falling from above the play area | 5 meteors spinning at 90°/s falling at 8px/frame |
| Boss flinches in idle; phase 2 enters super-armor | Boss hitbox activates from frame 8-12 of slam animation |
| Slam attack: melee, AOE radius medium, with ground crack VFX | Slam attack: 30f windup → 6f hit → 60f recovery, hitbox 200px radius offset 10px y |

The "Not this" entries are programmer / artist's job — designer writing them either locks in a number that breaks on later tuning, or asks for a visual precision (specific motion, exact arc) that image-gen can't deliver.
