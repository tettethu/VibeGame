# Information Design

Information as game mechanics: what players know, when they know it, how to create gameplay through information.

---

## 1. Information Architecture Framework

### Three Types of Game Information

**Structural Information**: Game rule text, valid move definitions, win/loss criteria, game space layout, initial configuration.

**State Information**: Unit positions, scores and resources, item holdings, current phase, valid action ranges, turn order.

**Randomness Parameters**: Random element types (dice, card draws, etc.), randomness range definitions.

---

## 2. Information Transparency Types

### Perfect Information Games

All information is public to all players. Examples: Chess, Go, Checkers. Core appeal lies in strategic depth.

### Imperfect Information — Complete Information Subtype

Players have access to all information about the game environment and rules, but cannot see other players' action states. Know the game element composition (card types, ship sizes) but not the specific state (who holds which card, ship positions).

**Strategic core**: Infer hidden opponent states based on known rules and probabilities. Players can "count cards."

Examples: Battleship, most card games (Gin Rummy, Hearts, Bridge, Poker).

### Imperfect Information — Incomplete Information Subtype

Players have no basis to make assumptions about the unknown. Cannot know what types and varieties of game elements exist.

**Strategic core**: Deal with fundamental unknowns. Players cannot "count cards."

Examples: Magic: The Gathering, StarCraft (fog of war).

### Involuntary Information Transparency

Game rules force players to reveal information to other players that should be kept secret. Players can choose which part to reveal, but cannot choose whether to reveal.

**Strategic core**: Deal with forced information flow.

Example: In Clue, players sometimes must show another player a card from their hand.

---

## 3. Voluntary Information Transparency

### Design Mechanisms

Allow players to decide for themselves whether to reveal their identity or private information. No forced disclosure; the choice is entirely based on player willingness.

### Psychological Pressure

If a player admits a secret without being forced, their motives are questionable. Other players must judge: genuine confession or strategic deception? Creates the possibility of "double agents."

### Game Environment

- Design situations where information disclosure is profitable
- Simultaneously design situations where keeping information secret is beneficial
- Ensure both choices have sound strategic justification

### Key Principles

- **Non-coercive**: Players must have genuine choice
- **Ambiguous motivation**: Motives for voluntary disclosure should be questionable
- **Strategic value**: Both disclosure and secrecy should have strategic significance
- **Social dynamics**: Encourage speculation, suspicion, and alliance formation

Example: In Werewolf, the "Seer" can choose whether to reveal their identity.

---

## Design Decision Process

```
Determine game type objectives
    ↓
Identify core gameplay (strategy vs deduction)
    ↓
Design information visibility rules
    ↓
Define information reveal timing and methods
    ↓
Validate that information effectively supports decision-making
```

## Common Problem Diagnosis

| Problem | Possible Cause | Solution Direction |
|---------|---------------|-------------------|
| Player decision difficulty | Insufficient or unclearly presented information | Optimize information visualization |
| Insufficient strategic depth | Information too transparent | Introduce moderate hidden information |
| Meaningless deduction | Hidden information without clues | Design information reveal mechanisms |
| Too much luck factor | Key information unknowable | Adjust information transparency |
