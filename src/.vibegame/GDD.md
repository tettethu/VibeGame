# Game Design Document

> **Version** v0.1 | **Type** <!-- TODO --> | **Platform** Browser (PC/Mobile) | **Session** <!-- TODO: e.g., 5-15 min per run -->
> **One-liner**: <!-- TODO: one sentence that captures the game's unique appeal -->

---

## Core Fantasy

> The moment the player wins / succeeds — what does it *feel* like?

<!-- Write 2-4 sentences describing the exact emotional payoff. This is the north star for all other design decisions.
Example (Sekiro): "You've died to this boss forty times. You finally read every attack. The parry clicks — sparks fly, posture breaks, deathblow lands. Pure mastery earned through suffering." -->

<!-- TODO: Define the core fantasy -->

---

## Game Overview

### Design Pillars

<!-- 3-5 short, punchy statements that define the experience. Every feature should support at least one pillar.
Example (Animal Crossing):
- [x] Craft and customize your world
- [x] Celebrate the seasons
- [x] Gather friends for island adventures -->

<!-- TODO: Define 3-5 design pillars -->

### Design Philosophy

<!-- 2-4 principles that guide every design decision. When there's a conflict between features, these resolve it.
Example: "Information first — the player always knows why they died." -->

1. <!-- TODO -->
2. <!-- TODO -->

### Core Settings

**Art Style**: <!-- Cartoon / Pixel Art / Anime / Realistic / Stylized / Hand-drawn / Other -->

**Game Type**: <!-- Action / RPG / Platformer / Puzzle / Strategy / Simulation / Narrative / Other -->

**Atmosphere**: <!-- Epic / Mysterious / Peaceful / Tense / Humorous / Dark / Whimsical / Scary -->

**Background Vibe**: <!-- e.g., "Post-apocalyptic city where music is banned" -->

**Player Character**: <!-- Who the player is: appearance, personality, motivation -->

**Game Objective**: <!-- What the player is trying to achieve -->

### Target Audience

| Attribute | Description |
|-----------|-------------|
| Age range | <!-- TODO --> |
| Play context | <!-- e.g., commute, desktop, couch session --> |
| Motivation | <!-- e.g., mastery challenge, story, social, relaxation --> |
| Session length | <!-- TODO --> |

### Comparable Games

| Game | Borrow what |
|------|-------------|
| <!-- TODO --> | <!-- visual style / core mechanic / pacing / etc. --> |

### MDA Framework

<!-- Fill top-down: Aesthetics (feelings) → Dynamics (behaviors) → Mechanics (rules). -->

**Target Aesthetics (feelings)**:

| Feeling | Weight | How to deliver |
|---------|--------|----------------|
| <!-- e.g., Mastery / Discovery / Narrative / Challenge --> | ★★★★★ | <!-- TODO --> |

**Derived Dynamics (player behaviors)**:
- <!-- e.g., Player experiments → discovers synergies → feels clever -->

**Supporting Mechanics**:
- <!-- e.g., Combo system with visible feedback → skill expression -->

### Signature Mechanics

<!-- The 1-2 mechanics that define this game. Everything else supports them.
Examples: Mario's jump / Sekiro's parry / Zelda's puzzle-combat -->

<!-- TODO: Describe the 1-2 signature mechanics and why they produce the core fantasy -->

### Core Game Loop

<!-- The repeating cycle the player lives in. ASCII diagram recommended. -->

```
<!-- TODO:
  Explore map
      │
      ▼
  Find challenge
      │
      ├── succeed → reward → upgrade
      └── fail → retry with knowledge
-->
```

**Loop duration**: <!-- e.g., "30s–2min per encounter" -->

---

## Detailed Design

<!-- Fill this section AFTER confirming Design Pillars with the user. -->

### System Mechanics

**Core Gameplay**: <!-- Combat / Exploration / Puzzle / Resource Management / Building / Stealth / Crafting -->

**Player Perspective**: <!-- Top Down / Side View / Isometric / First Person / Third Person / Combined -->

**Multiplayer**: <!-- Single Player / Local Co-op / Online / N/A -->

### Characters

#### Player Character

- Initial position: <!-- where the player spawns, e.g., left side of screen -->
- Visual scale: <!-- relative to screen size, e.g., "about 1/8 of screen height" -->
- States: `IDLE`, `MOVE`, `JUMP`, `FALL`, `ATTACK`, `HURT`, `DIE`
- Stats (in `config/player.json`):
  - HP: 100 (baseline — all values calibrated against this)
  - Move speed: <!-- TODO -->
  - Jump height: <!-- TODO -->
  - Attack damage: <!-- TODO: 10–50% of normal enemy HP -->

#### Enemies

| Enemy | HP | Damage | Behavior |
|-------|-----|--------|----------|
| <!-- TODO --> | ×<!-- --> player HP | <!-- --> | <!-- patrol / chase / ranged --> |

### Game Flow

- **Start state**: <!-- what the player sees at launch -->
- **Win condition**: <!-- TODO -->
- **Lose condition**: <!-- TODO -->
- **After win/lose**: <!-- restart / keep progress / outro screen -->

### Player Visible

<!-- What the player must be able to see and read. Not how it is presented:
animation, layout and effects belong to the artist and the implementer.

Answer per interface — title, shop, combat, map, menus — rather than once for
the whole game. The same value is often readable on one screen and missing on
the next, and that gap is invisible to a single flat list.

UI form is yours where form follows mechanic: a segmented health bar and a
continuous one say different things about the game. A preliminary suggestion is
a design decision; the final arrangement is not. -->

**Values the player must be able to read**

| Interface | Value | Decision it serves |
|-----------|-------|--------------------|
| <!-- TODO --> | <!-- TODO --> | <!-- TODO --> |

**How much of a kind must be visible at once**

| Interface | Content | How many distinct ones together |
|-----------|---------|---------------------------------|
| <!-- TODO --> | <!-- TODO --> | <!-- TODO --> |

**Things the player must be told happened**

<!-- State changes the player did not cause: a round advancing, a rival being
eliminated, a threshold activating, a supply boat arriving. Write what the
player must know. How they are told is the artist's and implementer's call. -->

| Event | What the player must know |
|-------|---------------------------|
| <!-- TODO --> | <!-- TODO --> |

### Map / Level Design

- **Map type**: <!-- Random / Level-based / Open World -->
- **Map design rules**: <!-- TODO -->

---

## Art Requirements

<!-- Simple asset list for the Artist agent. Describe what is needed and what it should look like.
Do NOT specify frame counts or animation details — that is Artist's responsibility. -->

### Characters

| Character | Actions needed | Visual description |
|-----------|---------------|-------------------|
| Player | Idle, walk, jump, attack, hurt, die | <!-- TODO --> |
| <!-- Enemy --> | <!-- actions --> | <!-- TODO --> |

### Map Assets

<!-- 2D map has three layers:
- Background: behind everything, no collision
- Obstacle Props: platforms, walls, ground — player collides with these
- Decorative Props: clouds, grass, trees — visual only, no collision -->

**Background**: <!-- TODO: what it looks like per scene -->

**Obstacle Props** (with collision):
- <!-- TODO -->

**Decorative Props** (no collision):
- <!-- TODO -->

### UI & Effects

- Font style: <!-- TODO -->
- Visual effects: <!-- e.g., screen shake on hit, particles on death, damage numbers -->

---

## Design Decisions Log

<!-- Record key design choices: options considered, what was chosen, and why.
Not a version history — a decision record so future agents understand intent.

Example:
| Decision | Options | Chosen | Reason |
|----------|---------|--------|--------|
| Evidence collection | Random card vs active search | Active search | Random has no learning (Koster); active creates exploration feeling |
-->

| Decision | Options Considered | Chosen | Reason |
|----------|--------------------|--------|--------|
| <!-- TODO --> | <!-- A vs B --> | <!-- chosen --> | <!-- diagnosis + reasoning --> |

---

> Use the `language` value defined in `.vibegame/global.json` to write this file. Keep code identifiers, file paths, asset keys, and engine vocabulary in English.
