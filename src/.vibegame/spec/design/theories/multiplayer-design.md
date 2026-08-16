# Multiplayer Game Design

Two foundational dimensions of multiplayer games: symmetry (whether player experiences are identical) and interaction mode (cooperative or competitive).

---

## 1. Symmetry and Synchrony

### Symmetry

**Symmetric games**: All players see the same scene, have the same rules, abilities, and objectives. Examples: Chess, Pong.

**Asymmetric games**: Players have different roles, abilities, information, or objectives. Examples: In D&D, the Dungeon Master knows all information; specific players can see things others cannot.

**Hybrid**: Mario Kart — all players see the same minimap (symmetric), but each player's first-person view centers on their own kart (asymmetric).

### Synchrony

**Synchronous games**: Participating players act simultaneously. Local multiplayer has perfect synchrony. The most common form of online multiplayer games.

**Asynchronous games**: Players take turns, don't need to be online simultaneously, one turn may take minutes or even days. Examples: Turn-based strategy, social games.

### Design Decisions

| Requirement | Choice |
|-------------|--------|
| Fair competition between players | Prioritize symmetry |
| Differentiated experiences | Design asymmetry |
| Real-time tension | Synchronous design |
| Lower time barrier | Asynchronous design |

**Technical limitation**: Network latency may cause technical asymmetry (players see different screens).

---

## 2. Cooperative Gameplay

### Design Essentials

**Shared objective design**: Set goals requiring team collaboration, design shared rewards, ensure individual goals align with team goals.

**Role complementarity**: Design unique abilities for different roles, make players interdependent, encourage leveraging individual strengths.

**Team rewards**: Individual contributions translate to team benefits, provide team-level achievements and recognition.

### Common Forms

| Form | Example | Characteristics |
|------|---------|----------------|
| Tabletop RPG | D&D | Player team adventures together, role division |
| Video co-op | Trading items, healing each other, tank + ranged | Players vs AI opponents |
| Cross-device co-op | Animal Crossing | Leverage different device capabilities |
| Asynchronous co-op | Messages, ghosts | Interact with past versions of yourself or others |

---

## 3. Competitive Gameplay

### Design Essentials

**Win/loss conditions**: Clear victory criteria, fair competitive environment, avoid ambiguous rules that cause disputes.

**Ranking systems**: Quantify player skill levels, reasonable ladder or division systems, avoid excessive complexity.

**Competitive mechanics**: Direct confrontation methods, balance effectiveness of different strategies, avoid unbeatable suppression.

### Individual vs Team Competition

- **Individual**: Usually only one winner. Single-player games can compete against "past self" (high scores). Examples: Golf, racing.
- **Team**: Internal team cooperation, external team competition. Need to balance internal collaboration and external competition.

### Design Pitfalls

Game mechanics may inadvertently encourage competition. Example: Facebook games show friend leaderboards, intended to encourage social interaction but actually promoted competition.

---

## 4. Hybrid Design: Intra-team Cooperation, Inter-team Competition

1. **Clear boundary delineation**: Define cooperation scope and competition scope clearly
2. **Balance internal/external relations**: Ensure sufficient cooperation space within teams, fair competition between teams
3. **Incentive mechanisms**: Team rewards promote cooperation, individual rewards encourage competitive performance

---

## Checklist

### Cooperative
- [ ] Clear shared objectives?
- [ ] Complementary abilities between players?
- [ ] Team-level rewards?
- [ ] Can players feel the necessity of cooperation?

### Competitive
- [ ] Clear win/loss conditions?
- [ ] Fair competitive environment?
- [ ] Reasonable ranking system?
- [ ] No unbeatable suppression strategies?

### Hybrid
- [ ] Clear internal and external boundaries?
- [ ] Reasonable ratio of cooperation to competition?
- [ ] Balanced incentive mechanisms?
