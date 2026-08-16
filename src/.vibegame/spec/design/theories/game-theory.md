# Game Theory and Strategy Design

Apply game theory principles to analyze and design strategy game decision mechanisms.

---

## 1. Core Concepts

### Payoff Types

- **Cardinal Payoffs**: Use specific values (currency, points) to quantify outcomes, like win/loss in rock-paper-scissors
- **Ordinal Payoffs**: Use ranking order (1, 2, 3...) to compare outcomes, like relative ranking in Prisoner's Dilemma

### Minimax Principle

Applicable to non-zero-sum games. Identifies conservative strategies for pessimistic decision-makers: choose the option that maximizes one's minimum payoff. Reflects players' tendency to avoid worst outcomes.

### Nash Equilibrium

A strategy profile where no player can improve their outcome by unilaterally changing their strategy.

**How to find**: In a payoff matrix, if in a cell the first payoff number is the highest in its column and the second payoff number is the highest in its row, that outcome is a Nash equilibrium.

### Pareto Optimality

A state with no room for Pareto improvement — no one's situation can be improved without harming others.

**Note**: Pareto optimality does not equal fairness or optimal distribution. Nash equilibrium outcomes are not necessarily Pareto optimal.

### Prisoner's Dilemma

**Payoff condition**: B>A>D>C (B best, C worst)

- **Single game**: Rational self-interest leads both to defect (Nash equilibrium), but mutual cooperation (Pareto optimal) is better for both
- **Repeated game**: Cooperation strategies like "tit for tat" become viable. But if the number of rounds is known, backward induction leads to defection every time

### Volunteer's Dilemma

In group games: Individuals can sacrifice a small portion of their interest to benefit everyone, but get no extra benefit themselves. If no one sacrifices, everyone faces severe damage.

**Dilemma essence**: Individual rationality (wait for others to act) → Collective irrationality (no one acts)

**Relationship to free-rider problem**: When costs are fixed, more people free-ride → fewer volunteers bear heavier burden → eventually no one may act.

---

## 2. Game Types

### Simultaneous Games

Players must consider what actions others will take, but cannot be certain what they will actually do. Key information is invisible at decision time.

**Classic examples**: Rock-paper-scissors, Prisoner's Dilemma.

**Design points**: Core strategy lies in predicting others' behavior, design multiple viable strategies to avoid a single optimal solution, Nash equilibrium can analyze strategy balance.

### Sequential Games

Players take turns making decisions, with at least partial knowledge of others' previous decisions.

**Classic examples**: Chess, Checkers, Turn-based strategy games.

**Design points**: Analyze whether first-mover advantage exists, design timing of information reveals, backward induction can analyze optimal strategies.

### Zero-Sum Games

One player's gain equals another's loss. Apply minimax principle: choose the strategy that minimizes the opponent's maximum gain.

---

## 3. Design Applications

### AI Decision Design

Use minimax algorithm to build AI opponents: assign evaluation values to each possible state, AI chooses the action that maximizes the opponent's minimum loss.

### Volunteer's Dilemma Design

**Encourage contribution**: Provide small extra rewards for actors (reputation, achievements), design visible contribution records.

**Enforce sharing**: Rotation mechanisms ensure fair burden-sharing, minimum contribution requirements, punish inaction.

**Accept**: Design as a core game challenge, let team dynamics form naturally.

Example: In Team Fortress 2, players may avoid dangerous but team-necessary tasks, assuming others will complete them.

### Strategy Balance Checklist

| Check Item | Simultaneous Games | Sequential Games |
|-----------|-------------------|-----------------|
| First-mover advantage | N/A | Must verify |
| Dominant strategy | Must verify | Must verify |
| Strategy diversity | Key design goal | Key design goal |
| Information symmetry | Symmetric at decision time | Can design asymmetry |

### Common Design Problems

| Problem | Solution |
|---------|----------|
| First-mover advantage too strong | Introduce randomness, increase rounds, design compensation for second mover |
| Strategy monoculture | Add strategy options, introduce uncertainty, design counter relationships |
| Decision complexity too high | Simplify decision trees, limit available actions, phased decisions |
