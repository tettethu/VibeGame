# State Machines

> **Owner**: Designer (initial states from GDD), Architect (adds states when planning new mechanics)
> One section per character type. Add enemy sections as they are designed.

---

## Player

<!-- TODO: Update states based on GDD.md character design.
Default states are a starting point — add/remove based on your game's mechanics. -->

**States**: `IDLE`, `MOVE`, `JUMP`, `FALL`, `ATTACK`, `HURT`, `DIE`

```mermaid
stateDiagram-v2
    [*] --> IDLE
    IDLE --> MOVE: directional input
    IDLE --> JUMP: jump key
    IDLE --> ATTACK: attack key
    MOVE --> IDLE: no input
    MOVE --> JUMP: jump key
    MOVE --> ATTACK: attack key
    JUMP --> FALL: peak reached
    FALL --> IDLE: landed
    IDLE --> HURT: damage received
    MOVE --> HURT: damage received
    HURT --> IDLE: recover
    IDLE --> DIE: HP = 0
    MOVE --> DIE: HP = 0
    HURT --> DIE: HP = 0
```

---

## Enemies

<!-- Add one section per enemy type as they are designed in GDD.md -->

<!-- Example:
### Grunt

**States**: `PATROL`, `CHASE`, `ATTACK`, `HURT`, `DIE`

```mermaid
stateDiagram-v2
    [*] --> PATROL
    PATROL --> CHASE: player detected
    CHASE --> ATTACK: in range
    ATTACK --> CHASE: out of range
    CHASE --> PATROL: player lost
    ATTACK --> HURT: hit received
    HURT --> CHASE: recover
    HURT --> DIE: HP = 0
```
-->
