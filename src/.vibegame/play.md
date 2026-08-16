# Game Guide

Quick reference for testing the agent. Read before testing.

---

## How to Run

```bash
vibegame run .
```

---

## Core Gameplay

<!-- Describe the core gameplay loop in 1-2 sentences. Example: Grid-based turn-based tactical RPG. Command 4-6 medieval units against AI enemies. -->

**Player Actions:**
- <!-- Describe primary player actions. Example: Click unit to select, view movement range (blue tiles) -->
- <!-- Example: Click highlighted tile to move -->
- <!-- Example: Click enemy in attack range (red tiles) to attack; hover shows damage preview -->
- <!-- Example: Click **ET** button to end turn -->
- Repeat until win or lose

**Game Over Conditions:**
- **Win**: <!-- Define win condition -->
- **Lose**: <!-- Define lose condition -->

**Controls:**
- <!-- Describe control scheme -->

---

## Units / Characters

<!-- Define unit types, their stats, strengths, weaknesses. Use a table if applicable. -->

| Unit | Strong Against | Weak Against | Range | Notes |
|------|---------------|-------------|-------|-------|
| <!-- Unit 1 --> | <!-- --> | <!-- --> | <!-- --> | <!-- --> |
| <!-- Unit 2 --> | <!-- --> | <!-- --> | <!-- --> | <!-- --> |

## Terrain / Environment Effects

<!-- Define terrain types and their effects, if applicable. -->

| Terrain | Move Cost | Defense | Special |
|---------|-----------|---------|---------|
| <!-- Default --> | 1 | None | Default |

---

## Test Scenarios

### Scenario 1: Basic Movement
1. <!-- Step 1 -->
2. <!-- Step 2 -->
3. <!-- Step 3 -->

### Scenario 2: Combat System
1. <!-- Step 1 -->
2. <!-- Step 2 -->
3. <!-- Step 3 -->

### Scenario 3: Win/Lose Conditions
1. <!-- Step 1 -->
2. <!-- Step 2 -->

---

## Known Issues / Limitations

- None yet

---

## Checkpoints

<!-- URL parameters for jumping to specific game states -->
<!-- Example: http://localhost:8765?checkpoint=combat-test -->

<!-- TODO: Define checkpoints as implementation progresses -->

---

> Use the `language` value defined in `.vibegame/global.json` to write this file. Keep code identifiers, file paths, asset keys, and engine vocabulary in English.
