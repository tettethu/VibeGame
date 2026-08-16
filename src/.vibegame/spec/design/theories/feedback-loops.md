# Feedback Loop Design

Positive and negative feedback are the two fundamental tools of game balance. Understanding their mechanisms and risks is the foundation of tuning.

---

## Positive Feedback Loops: Rich Get Richer

### Definition

Achieving a goal earns a reward that makes the next goal easier to achieve, forming a "rich get richer" cycle.

### Classic Examples

| Game | Loop | Result |
|------|------|--------|
| Monopoly | Buy hotels → collect more money → buy more hotels | Leader's advantage keeps expanding, laggards struggle to catch up |
| RPG | Kill monsters → level up → easier to kill more monsters | Player power keeps increasing, may become too easy late game |
| Chess | Capture pieces → opponent weakens → easier to capture more | Reasonable positive feedback, reflects advantage accumulation |
| Dodgeball | Team with more players faces fewer threats | Numerical advantage keeps expanding |

### Design Risks

1. **Game loses balance too early**: The first player to gain an upper hand may keep winning
2. **Conflicts with player expectations**: Players want to get stronger (needs positive feedback) but also want challenge (needs balance)
3. **Economic system runaway**: Inflation, resource concentration

### Solution Approaches

1. **Use cautiously**: More in early game, reduce reliance in late game
2. **Pair with negative feedback**: Combine to balance difficulty. E.g. in RPG, leveling up (positive) but enemies also get stronger (negative)
3. **Cosmetic rewards**: Skins, animations, titles — provide satisfaction without breaking balance
4. **Limit magnitude**: Diminishing returns, set caps, periodic resets (seasons)

---

## Negative Feedback Loops: Maintaining Suspense

### Definition

Achieving a goal makes the next goal harder, aimed at suppressing leading advantages and maintaining game balance.

### Classic Examples

| Game | Negative Feedback Mechanism | Effect |
|------|---------------------------|--------|
| Mario Kart | First place can be hit by blue shell | Maintains race suspense |
| American Football | Closer to end zone, smaller defensive space | Balances offense and defense |
| 8-ball Pool | Opponent's balls get pocketed → fewer options for them | Increases strategic depth |

### Design Risks

1. **Unfair feeling**: Appears to punish good performance
2. **Rubber-banding**: Overly obvious catch-up mechanics make players feel effort doesn't matter

### Core Principle: Reward, Not Punish

- Provide help to laggards rather than punishing leaders
- Maintain causal connection, don't let players feel results are disconnected from effort

### Common Implementation Methods

1. **Item systems**: Laggards receive stronger items
2. **Resource compensation**: Laggards receive extra resources
3. **Difficulty adjustment**: Leaders face stronger challenges
4. **Information advantage**: Laggards receive more information

---

## Feedback Loop Analysis Framework

### Loop Elements

1. **Trigger condition**: What starts the loop?
2. **Reinforcement mechanism**: How does advantage/disadvantage accumulate?
3. **Loop speed**: How long is one cycle?
4. **Termination condition**: What stops the loop?

### Impact Assessment

1. **Irreversibility**: Once leading/lagging, can it be reversed?
2. **Speed**: How fast does advantage accumulate?
3. **Scope**: How much of the game does it affect?
4. **Necessity**: Is this loop necessary for the game?

### Design Checklist

- [ ] Have all positive and negative feedback loops been identified?
- [ ] Could positive feedback cause the game to lose balance too early?
- [ ] Does negative feedback make players feel treated unfairly?
- [ ] Are there corresponding balance mechanisms?
- [ ] Can laggards still make a comeback?
- [ ] Do leaders still feel their performance is meaningful?
