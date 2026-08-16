# Core Design Frameworks

Three foundational frameworks form the conceptual bedrock of game design: MDA determines "how to analyze," the core loop determines "how to structure," and the magic circle determines "where the boundaries of the game lie."

---

## 1. MDA Framework: Mechanics-Dynamics-Aesthetics

**Originators**: Marc LeBlanc, Robin Hunicke, Robert Zubek

### Three Components

**Game Mechanics**: The rules of the entire system. Define how the system processes player input, what players can see and do.

**Game Dynamics**: The behavior of all system participants during gameplay. The hardest element to fully understand.
- Example: eBay auctions — mechanics are "see highest bid, fixed end time," dynamics are "bidder behavior concentrates at the end (sniping)"

**Game Aesthetics**: The emotional output of players under the influence of dynamics. Common types: challenge, fear, tension, fantasy, social, exploration.

### Two Practical Perspectives

**Designer Perspective (Top-Down)**: Desired experience → determine needed dynamics → set corresponding mechanics

**Player Perspective (Bottom-Up)**: Interact with mechanics → produce specific dynamics → bring specific experience

### Analysis Question Checklist

| Question | Corresponding Element |
|----------|----------------------|
| What player behavior will the mechanics create? | Mechanics → Dynamics |
| Does the behavior match expectations? | Dynamics validation |
| How do rule changes affect dynamics? | Mechanics adjustment |
| What is the game's purpose? | Experience goal |
| Which mechanics align or conflict with the purpose? | Consistency check |

### Limitations

Player emotional responses come not only from dynamics but also from personal background, cultural differences, and timing. People of different ages playing the same game will have different experiences.

### Design Application Process

Define desired experience → derive needed player behaviors → design mechanics that trigger those behaviors → prototype and test → iterate

---

## 2. Core Game Loop

### Definition

The core game loop is the foundational, central, repeated mechanic that provides the game experience.

- **Repeatability**: Players will perform these actions over and over
- **Centrality**: This is the foundation of the game experience, not a secondary activity
- **Satisfaction Source**: Immediate satisfaction mainly comes from the different outcomes of core mechanics

### Loop Structure

1. **Action**: Player input/choice
2. **Feedback**: Immediate result
3. **Reward**: Resource/progress gained
4. **Progression**: New abilities/content
5. **Repeat**: Continue from a stronger position

### Satisfaction Design

**Action**: Clear and responsive input, difficulty matched to skill, multiple viable strategies.

**Feedback**: Immediacy (results visible instantly), clarity (clear cause and effect), variety (same action produces different results).

**Reward**: Significance (meaningful to the player), uncertainty (moderate randomness increases anticipation), visibility (progress clearly visible).

### Goal Hierarchy Decomposition

- Main goal: Beat the game/win the match
- Mid goal: Complete current level/level up character
- Sub goal: Defeat current enemy/collect current resource
- Micro goal: Land one successful attack/execute one perfect move

The loop itself should be fun, not merely a means to an end.

### Examples by Type

| Type | Loop |
|------|------|
| Action | Move → find enemy → fight → collect loot → upgrade |
| Strategy | Resource management → unit building → deploy → battle → expand |
| Puzzle | Observe puzzle → try solution → success/failure feedback → next level |
| Simulation | Plan → act → observe → adjust → improve |

### Validation Checklist

- Is the core loop clearly identifiable?
- Would players want to repeat it?
- Is every step in the loop necessary?
- Are there redundant or broken links?

### Design Principles

1. **Simplicity**: The core loop should be simple, easy to understand and execute
2. **Repeatability**: The loop must be worth repeating, not tedious
3. **Scalability**: The loop should support the entire game's growth
4. **Balance**: Difficulty and rewards stay balanced

---

## 3. Magic Circle

### Core Concept

**Origin**: Proposed by Johan Huizinga in "Homo Ludens."

**Definition**: Games have separate activity spaces (arena, card table, stage) — temporary worlds within the "normal" world that exist for independent behavior with special rules.

When the game begins, it becomes different from reality. Symbols and rules within the game gain special meaning inside the magic circle — like red plastic shapes becoming "hotels."

### Design Freedom

The magic circle grants design freedom, allowing interactions in games that are impossible in reality due to taboos, physical laws, or resource scarcity:

| Reality Constraint | Game Breakthrough |
|-------------------|-------------------|
| Taboos | Violence themes, moral exploration |
| Physical laws | Superpowers, magic systems |
| Resource scarcity | Infinite resource simulation |

### Boundary Breaking

**Negative Breakthrough**: Gambling addiction (game influence extends beyond the magic circle), emotions carried into reality.

**Creative Breakthrough**: "Spoilsports" who embrace the idea that magic circle boundaries can be broken, creating new game forms through "meta-game thinking."

### Design Considerations

- **Leverage the magic circle**: Create experiences impossible in reality, design special rules and meaning systems
- **Watch for boundary issues**: Design anti-addiction mechanisms, handle malicious behavior, balance game experience with real-life responsibility

### Checklist

| Check Item | Description |
|-----------|-------------|
| Independence | Does the game have a clear start and end |
| Rule consistency | Are in-game rules complete and independent |
| Meaning system | Do in-game symbols have unique meaning |
| Boundary awareness | Is the impact of boundary breaking considered |
