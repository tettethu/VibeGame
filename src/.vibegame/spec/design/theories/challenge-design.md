# Challenge Type Design

Game challenges fall into two categories: memory-based and skill-based. Understanding this classification helps design learning curves and assist systems.

---

## Memory Games

**Core requirements**: Trial and error, memory recognition, instinctive reaction, mastery of the game itself.

**Classic examples**:
- FPS: Memorize element and item positions, level layouts
- Side-scrolling platformers: Memorize object positions and movement patterns
- Racing: Memorize tracks, apply reaction ability

**Potential problem**: May become boring from repetition after extended play.

**Solution**: Add randomness while keeping mechanics, story, and outcomes unchanged — enemy position variation, platform movement variation, item drop variation.

---

## Skill Games

**Core requirements**: Physical or mental ability and conditions, mathematical calculation, information acquisition and planning, strategy evaluation.

**Classic examples**:
- Billiards: Calculate shot angles and collision results
- RPG: Acquire information, plan routes, evaluate item acquisition methods

**Potential problem**: Players who haven't developed required skills will feel frustrated.

**Solution**: Provide assist systems — guide characters, help videos, flashing hints, using enemy bounce to reach platforms.

---

## Hybrid Design

Many games incorporate both types. Excellent arcade games require both memory (the game doesn't change) and specific skills. Mnemonics in games can be used to improve real-world skills (soldier, doctor simulation training).

---

## Design Decision Matrix

| Challenge Type | Main Problem | Solution Direction | Target Audience |
|---------------|-------------|-------------------|----------------|
| Memory-dominant | Repetition boredom | Add randomness | Players who enjoy mastery |
| Skill-dominant | High skill barrier | Provide assist systems | Players who enjoy growth |
| Balanced hybrid | Difficulty balancing | Tiered design | Broad audience |

---

## Assist System Design Principles

1. **Optional**: Assists should be toggleable, not affecting challenge-seeking players
2. **Progressive**: Assist intensity should be adjustable
3. **Non-intrusive**: Should not break game experience integrity
