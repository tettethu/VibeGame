# Bartle Player Type Analysis

Richard Bartle's classic player classification method based on MUD game research (1996).

---

## Four Player Types

### Achievers

**Core motivation**: Win or achieve specific goals.

**Behavioral traits**: Pursue leveling, leaderboard positions, collect coins/items/achievements, speedrun content, value quantifiable progress.

**Design points**: Clear progression systems, leaderboards and competitive opportunities, rich collectible content, clear rewards and recognition.

### Explorers

**Core motivation**: Discover and understand the game world.

**Behavioral traits**: Try to find everything in the virtual world, explore map breadth, research mechanic depth. Game designers and collection enthusiasts often fall into this category.

**Design points**: Rich hidden content and easter eggs, complex deep game mechanics, encourage experimentation and discovery, world lore and details.

### Socializers

**Core motivation**: Enjoy interacting with other players.

**Behavioral traits**: Leverage guild and team mechanics, strengthen social presence, build interpersonal relationships and community, gain fun through communication.

**Design points**: Guilds, friends and other social systems, chat and interaction tools, team collaboration and group activities, social topics and events.

### Killers

**Core motivation**: Impose their will on others.

**Behavioral traits**: Attack to show dominance or harass others, seek opponents in PvP environments, gain satisfaction through affecting others.

**Design points**: Fair PvP environments, clear confrontation mechanics, control "griefer" behavior (reporting systems), balance PvE and PvP content.

---

## Analysis Model

### 2D Coordinate System

- **X-axis**: Players ↔ World
- **Y-axis**: Interacting with ↔ Acting upon

| Quadrant | Type | Focus |
|----------|------|-------|
| Acting upon World | Achievers | Conquer game content |
| Interacting with World | Explorers | Understand the game world |
| Interacting with Players | Socializers | Build relationships |
| Acting upon Players | Killers | Affect others |

---

## Application Examples

### MMORPG (World of Warcraft)
- Achievers: Raid progression, levels, achievement system
- Explorers: Explore maps, discover hidden areas
- Socializers: Guild system, raid groups, social chat
- Killers: PvP arena, open-world PvP

### Social Games
- Socializer players dominate
- Use leaderboards to implicitly incentivize achievers
- Emphasize interaction and sharing, use social reward mechanisms

### Competitive Games
- Achievers pursue rankings, Killers pursue defeating opponents
- Clear ranking systems, rich competitive modes, balanced matchmaking

---

## Notes

- Actual player behavior may mix multiple types
- Classification is a simplified model, but provides a useful design framework
- Player type distribution varies by game genre
- Player types may change over time
