# Mechanism Design Toolkit

Theories and methods for designing specific game mechanics: puzzles, cyclic counters, emotion systems, reward systems, dynamic values.

---

## 1. Puzzle Design

### Four Design Principles

**Moderate Difficulty**: Make players feel challenged without being so frustrated they give up. Use breadcrumb guidance — hints inside and outside the puzzle guide the user step by step toward the answer. Example: In Sudoku, filled-in letters provide hints for remaining spaces.

**Requires Cleverness**: Needs intelligent, clever solutions rather than brute force. Counter-example: Guessing a number from 1-10 (pure guessing); a maze with very few wrong paths.

**Determinism**: Puzzles may be generated randomly, but the solving process must be deterministic. Same operations yield same results. Example: Sudoku, Minesweeper (same click sequence yields same experience).

**Clear Goals and Mechanics**: Players must know what the goal is and what operations to perform. Counter-example: Old adventure games where puzzle elements are obvious but goals and operation rules are vague.

---

## 2. Cyclic Counter Systems (Rock-Paper-Scissors)

### Design Principle

Based on the rock-paper-scissors model: simultaneous, semi-random, zero-sum game. 3 or more elements counter each other in a perfectly balanced cycle, preventing any single strategy or unit from always being optimal.

### Strategic Depth

- Unit advantages come with attack power weaknesses against another unit
- Attributes, weather, terrain, tactics can weaken or alter direct counter relationships

### Application Examples

| Game | Cyclic Counter | Source of Strategic Depth |
|------|---------------|--------------------------|
| Pokemon | Water → Fire → Grass → Water | Type combinations, move selection |
| StarCraft | Air → Ground → Anti-Air → Air | Economy management, build timing |
| Fighting Games | Attack → Throw → Block → Attack | Mind games, frame advantage |

### Warning

Should not be the only method for balancing a game. If cyclic counters are the only strategy, the game devolves into random guessing.

---

## 3. Emotion Systems

### 7 Universal Emotions

Surprise, contempt, anger, joy, fear, sadness, disgust — cross-culturally recognized.

### Emotion vs Mood

- **Emotion**: Unconscious, fleeting, easily visible through facial changes
- **Mood**: Lasts longer, can be hidden and concealed

### Design Levels

- Basic application: Graphical processing is more direct than observing facial expressions
- Deep application: Highly realistic facial expression technology, letting players recognize fleeting expressions

---

## 4. Reward Systems

### Variable Ratio Rewards (Skinner Box)

Rewards given at random intervals, so users can't predict how many attempts they need. Creates a "more presses, more rewards" impression. Example: Killing monsters in RPGs has a chance to drop treasure.

**Reinforcement Schedule Types**:

| Type | Mechanism | Effect | Example |
|------|-----------|--------|---------|
| Fixed ratio | Reward every N actions | Stable but predictable | Collect 10 stamps for coffee |
| Variable ratio | Reward on average every N actions | Strongest addictive quality | Slot machines, loot drops |
| Fixed interval | Reward at fixed time intervals | Decreased behavior before time | Daily login rewards |
| Variable interval | Random time rewards | Sustained engagement | Random event triggers |

### Goal Gradient Effect

The closer people get to a goal, the more motivated they are to complete it. Showing upcoming rewards can reignite motivation. Progress bar design: showing filled progress (e.g. 100/150) is more motivating than an empty progress bar.

### Constraints

Overusing Skinner box principles may make players feel manipulated, reducing intrinsic enjoyment. Balance extrinsic incentives with intrinsic fun.

---

## 5. Dynamic Value Ranking

### "A is Greatest" Mechanism

Without changing the game's basic rules, redefine the value ranking of game elements:
- **Decided before game starts**: Players agree or randomly choose which card is highest
- **Decided during gameplay**: Dynamically change the highest card through specific mechanisms (like "calling trump")

Effect: Change the distribution of cards on the table without reshuffling, increasing strategic choice space.

### "Wild Card" Mechanism

Designated cards can substitute for any other card in the game:
- Acts as an empty variable, players can assign any value
- Increases complexity, provides more strategic choices
- Changes the frequency of rare events

### Combined Effect

Setting multiple elements as wild cards further complicates the original distribution, statistically providing players with more options, increasing strategic depth and replayability.
