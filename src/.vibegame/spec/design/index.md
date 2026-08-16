# Game Design Knowledge Base

This directory contains design theories distilled from professional game design books, for use by the designer agent.

---

## Injection Mechanism

**Always Injected** (auto-injected by hook, present every time designer starts):
- This file (`index.md`)
- `theories/core-frameworks.md` — MDA + Core Loop + Magic Circle
- `theories/player-motivation.md` — Four Types of Fun + Koster's Learning Theory

**design.jsonl Injection** (curated by designer, then auto-injected):
- On first run, designer reads the directory below and selects theories relevant to the current game
- Writes selected theories to `.vibegame/design.jsonl`
- On subsequent calls, the hook auto-injects content from design.jsonl

**On-Demand Read** (designer actively reads):
- Theories not written to design.jsonl can be read by the designer as needed

---

## Designer First-Run Workflow

1. Read this file to understand available theories
2. Based on game type and design task, read relevant theories/*.md
3. Write theories relevant to the current game to `.vibegame/design.jsonl`:
   ```jsonl
   {"file": ".vibegame/spec/design/theories/mechanism-design.md", "reason": "Platformer core mechanic design"}
   {"file": ".vibegame/spec/design/theories/feedback-loops.md", "reason": "Difficulty curve and progression tuning"}
   ```
4. On every subsequent call, these theories are auto-injected into your context

---

## Theory Directory

### High Frequency — Most Games Will Use These

| File | Content | When to Read |
|------|---------|-------------|
| `theories/mechanism-design.md` | Puzzle design, cyclic counters (rock-paper-scissors), emotion systems, reward systems (Skinner box), dynamic value ranking | Designing specific gameplay mechanics |
| `theories/challenge-design.md` | Memory-based vs skill-based challenges, assist system design | Determining learning curves and challenge types |
| `theories/feedback-loops.md` | Positive feedback (rich get richer) + negative feedback (maintain suspense), analysis framework | Tuning, diagnosing "too easy/too hard/boring" |
| `theories/game-fairness.md` | Game contract, randomness fairness, difficulty curves, Rabin fairness model | Designing rules and feedback systems, handling fairness complaints |

### Player Analysis — When Building User Personas

| File | Content | When to Read |
|------|---------|-------------|
| `theories/player-types.md` | Bartle's four types (achiever/explorer/socializer/killer), 2D coordinate model, application examples | Analyzing player motivations, designing content for different types |
| `theories/player-personality.md` | Big Five → game preferences, Multiple Intelligences → game element mapping | Deep user research, creating player personas |

### Strategy/Multiplayer — When Involving Multiplayer or Strategy Gameplay

| File | Content | When to Read |
|------|---------|-------------|
| `theories/game-theory.md` | Nash equilibrium, Prisoner's Dilemma, Volunteer's Dilemma, simultaneous/sequential games, AI decision-making | Designing strategy games, analyzing optimal strategies |
| `theories/multiplayer-design.md` | Symmetric/asymmetric, synchronous/asynchronous, cooperative/competitive mechanics | Designing multiplayer game foundations |
| `theories/social-systems.md` | Dunbar's number, network effects, tragedy of the commons, social mechanism types | Designing social features, shared resource management |

### Information/Narrative — For Deduction or Narrative-Driven Games

| File | Content | When to Read |
|------|---------|-------------|
| `theories/information-design.md` | Three categories of information architecture, transparency types, voluntary/involuntary information disclosure | Designing information reveal mechanics, deduction games |
| `theories/hidden-narrative.md` | Hidden narrative formula, spatial/temporal/mechanical/easter egg design | Designing hidden content, narrative twists |

### Meta Methods — Project Planning and Ideation Phase

| File | Content | When to Read |
|------|---------|-------------|
| `theories/design-process.md` | Three brainstorming methods, 100 design principles index, 80/20 resource allocation | Early project ideation, resource planning |
| `theories/business-models.md` | Consumer surplus, freemium four-tier IAP, payment balance | Planning business models, designing IAP strategies |
