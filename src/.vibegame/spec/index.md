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

| Doc | File | Default Inject | Description |
|-----|------|---------------|-------------|
| Project Setup | engine/project-setup.md | programmer | project.json, manifest, input-map, directory layout, runtime flow |
| Entity Guide | engine/entity-guide.md | programmer | NodeDef, VisualDef, Node lifecycle, tree ops, MountPoint, AI patterns |
| Animation Guide | engine/animation-guide.md | selective | visual.animations, animations.clips, animator state machine |
| Collision Guide | engine/collision-guide.md | selective | ColliderDef, trackCollider/trackOverlap, Collider child node, events |
| Script Rules | engine/script-rules.md | programmer + auditor | File structure, import rules, common mistakes, pitfalls |
| Modules | engine/modules.md | selective | `modules/` reusable Node scripts, `Module` suffix routing, subclassing |
| Tilemap Guide | engine/tilemap-guide.md | selective | Tileset/tilemap formats + TileMap Node API |
| Rastermap | contracts/rastermap.md | selective | One-PNG-with-explicit-colliders map pattern, landmark schema, artist/programmer/player workflow |
| Runtime | engine/runtime.md | programmer + player + reviewer | startup, parameters, control API, bot testing, evidence, shutdown |
| Engine Internals | engine/engine-internals.md | — | SceneTree internals + PhaserHost (engine integration only, not for game agents) |

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
