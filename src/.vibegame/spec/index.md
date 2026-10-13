# Spec Index

This index lists all system specs and contracts for the current game project.
Updated by Architect and Programmer agents as the project grows.

---

## Systems

| System | File | Status |
|--------|------|--------|
| Engine & Tech Setup | systems/basic.md | Template (update in bootstrap task) |
| State Machines | systems/state-machine.md | Template (update in bootstrap task) |

## Engine

| Guide | File | Scope |
|---|---|---|
| Game development | [engine/index.md](engine/index.md) | Project, Node, world size, collision, animation, children, modules, UI, assets and runtime verification |
| Tilemaps and tilesets | [engine/tilemap-guide.md](engine/tilemap-guide.md) | Semantic grid data, tileset registration and TileMap API |
| Game deployment | [engine/deployment.md](engine/deployment.md) | Release payload, URLs and hosting |

The main guide is the default engine reference. It is not an index of additional
required engine manuals. Production-specific role handoffs live in
[contracts/index.md](contracts/index.md), including raster maps and prototype/polish.

---

## Contracts

| Contract | File | Systems | Status |
|----------|------|---------|--------|
| (none yet) | - | - | - |

---

## Data

| Config File | Schema Doc | Status |
|-------------|------------|--------|
| project.json | schema/project.schema.json | Active |
| *.scene.json | schema/scene.schema.json | Active |
| input-map.json | schema/input-map.schema.json | Active |
| manifest.json | schema/manifest.schema.json | Active |

## Validation

| Tool | Command | Description |
|------|---------|-------------|
| Project validator | `vibegame check .` | Validates project config, scenes, scripts, and cross-file consistency |

## Design Theory

| Doc | File | Description |
|-----|------|-------------|
| Design Index | design/index.md | Index of design theory documents |
| Core Frameworks | design/theories/core-frameworks.md | MDA, Core Loop, Magic Circle |
| Player Motivation | design/theories/player-motivation.md | Player motivation and fun theory |
| Mechanism Design | design/theories/mechanism-design.md | Game mechanics design principles |
| Challenge Design | design/theories/challenge-design.md | Challenge and difficulty design |
| (more theories) | design/theories/*.md | Additional design theory documents |

> Design theory files are injected into the designer team member context to support game design decisions.
