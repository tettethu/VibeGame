# Modules

`modules/` is a project-level directory of reusable Node scripts that ship with vibegame and can be used directly from any scene without copying their source.

This is distinct from `scripts/`:

| Dir | Owner | Lifetime | Typical content |
|---|---|---|---|
| `scripts/` | the game project (you / agents) | Written per-project | Game-specific Node scripts: `Hero.js`, `BossEnemy.js`, `Bullet.js` |
| `modules/` | vibegame (installed by `vibegame init`) | Shared across projects | Reusable Node scripts: `StatusBarModule.js`, `InventoryPanelModule.js` |

A module is just a Node subclass. There is no special API. The only thing that makes it a module is its location (`modules/`) and the **mandatory `Module` filename suffix**.

## Naming Convention

```
modules/StatusBarModule.js     class StatusBarModule extends Node { ... }
modules/InventoryPanelModule.js class InventoryPanelModule extends Node { ... }
```

- File name = class name = name used in scene JSON
- File name MUST end with `Module`
- Files in `scripts/` MUST NOT end with `Module`

`vibegame check` enforces both rules and rejects violators.

## How boot.js Resolves Script Names

When a scene JSON references `{ "script": "X" }`, boot.js routes by name:

| Name | Loaded from |
|---|---|
| `TileMap`, `Collider`, `MountPoint` | `engine/scripts/` (built-in engine scripts) |
| Anything ending with `Module` | `modules/` |
| Everything else | `scripts/` |

There is no manifest, no discovery API, no fallback probe. The suffix is the routing key.

## Using a Module as a Node Script

Direct use in scene JSON, with config passed via the standard `config` field:

```json
{
  "name": "HUD",
  "script": "StatusBarModule",
  "config": {
    "label": "HP",
    "max": 100,
    "color": "#ff0000",
    "x": 16,
    "y": 16
  }
}
```

The module reads `this.config` like any other Node script.

## Subclassing a Module

A game script may extend a module to customize behavior. Import via absolute path:

```javascript
// scripts/PlayerHpBar.js
import StatusBarModule from '/modules/StatusBarModule.js'

export default class PlayerHpBar extends StatusBarModule {
  ready() {
    super.ready()
    // custom logic, extra listeners, etc.
  }
}
```

The subclass lives in `scripts/`, follows the regular script naming rule (no `Module` suffix), and is referenced from scene JSON as `"script": "PlayerHpBar"`.

## Composing Modules

A module may import another module. Use a relative path within `modules/`:

```javascript
// modules/InventoryPanelModule.js
import ProgressBar from './ProgressBarModule.js'

export default class InventoryPanelModule extends Node {
  ready() {
    // use ProgressBar internally
  }
}
```

Browser-native ES module resolution. No bundler, no extra config.

## Authoring a Module

A module must be a self-contained, parameterizable Node script. Concrete rules:

- Extend `Node` (or another module that extends Node)
- Read all tuning parameters from `this.config` — never hardcode game-specific values like asset paths, level data, or specific labels
- Avoid hard dependencies on project structure (`findByTag('player')`-style coupling is acceptable for opt-in features but should not crash if missing)
- Clean up in `destroy()` for any manually-created Phaser objects (engine cleans up declarative `visual` / `collider` automatically)
- Document the expected `config` shape in a top-of-file comment

A module should drop into any project that needs its capability without code changes to the module file. Project-specific customization happens via `config` in scene JSON or via subclassing.

Modules may provide helpers and contracts, but they should not dynamically rewrite another node's `animator.states` or `transitions` at runtime. If a module requires a state/action, keep that FSM config explicit in the node JSON so runtime, dashboard, check, and export all read the same data.

## Event Contract

Modules that report facts to their parent should use fixed event names and distinguish concrete sources through payload fields. Do not encode skill names, fx names, or hitbox names into the event name.

Good:

```javascript
this.emit('fx_overlap', {
  sourceName: this.name,
  hitbox: 'blade',
  target: other,
  targetName: other.name,
})
```

Avoid:

```javascript
this.emit('slash_hit_enemy', { target: other })
```

Event name means "what type of fact happened"; payload means "who caused it and with what details". Parent scripts listen to the fixed event and decide behavior:

```javascript
this.on('fx_overlap', ({ source, sourceName, hitbox, target }) => {
  // Parent owns damage, dedup, knockback, and state changes.
})
```

Recommended fixed event names for action/fx modules:

- `animator_enter`
- `animator_exit`
- `animator_transition`
- `fx_started`
- `fx_finished`
- `fx_frame`
- `fx_collider_on`
- `fx_collider_off`
- `fx_overlap`

Recommended payload fields:

- `source`: original node that emitted the event; engine bubbling preserves the first source.
- `state`: animator state name, when relevant.
- `frame`: animation frame index, when relevant.
- `event`: event name, when relevant.
- `sourceName`: source node name, often the child node name.
- `hitbox`: collider/hitbox name inside the fx/action.
- `target`: target node, when overlap/hit related.
- `targetName`: target node name, when overlap/hit related.
- `data`: module-specific object for extra fields.

### SideviewFighterPracticeModule

`SideviewFighterPracticeModule` is a parent node script module for testing side-view fighter composition. It owns the character behavior. It reads input, sets animator parameters, listens to animator/fx facts, and emits hit facts. It does not generate FSM config at runtime.

Extension rule:

- Add new animation clip explicitly.
- Add new animator state explicitly.
- Add transitions explicitly.
- Add `config.actions.*` explicitly.

## Module vs Script: When to Use Which

| Use a module when | Use a script when |
|---|---|
| The behavior is generic (HUD bar, modal dialog, fade transition) | The behavior is unique to this game (a specific boss's attack pattern) |
| You want to share across projects | One-off project logic |
| You want the same code path used by many entities | Code that only ever lives in one entity |

Modules are written / promoted by the `evolve` workflow, not by hand during normal game development. During a regular task, prefer reusing existing modules over writing new ones; if you find yourself wanting a new module, flag it for evolve instead of inlining the abstraction.
