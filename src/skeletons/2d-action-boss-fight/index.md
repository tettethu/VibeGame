# 2D Action Boss-Fight Skeleton

Single-arena side-view 1v1 boss-fight skeleton. This skeleton provides a proven project shape: rastermap arena, player FSM, boss FSM, projectile, one-shot FX, HUD, overlay, data-driven node config, node templates, and placeholder manifests.

Usage: start a new project from the normal Vibegame boot shell, copy or cherry-pick this skeleton, fill the manifests with real assets, then lightly edit config, scene data, and gameplay glue for the new theme.

## Directory

```text
project.json
config/
  input-map.json            # semantic input actions
scenes/
  main.scene.json           # arena, colliders, player, boss, HUD, overlay, templates
scripts/
  ArenaManager.js           # camera/world bounds, fight flow, HUD/overlay glue, runtime spawns
  PlayerController.js       # player action FSM
  BossController.js         # boss duel FSM
  OneShotFx.js              # slash / hit / ground / death FX, optional slash damage
  ThornBolt.js              # ranged projectile
modules/
  MaskHUDModule.js          # discrete-pip HUD (player HP)
  StatusBarModule.js        # sprite-backed HUD bar with DOM label (boss HP)
  GameOverlayModule.js      # pause/defeat/victory DOM overlay
entities/
  player.node.json          # player visual/collider/animations + per-attack hitbox children
  boss.node.json            # boss visual/collider/animations + attack hitboxes
  one-shot-fx.node.json     # reusable impact / ground / death FX template
  normal-slash-fx.node.json # normal attack FX sized to its hitbox
  air-slash-fx.node.json    # air attack FX sized to its hitbox
  thorn-bolt.node.json      # reusable projectile template
  charged-slash-fx.node.json # charged-release FX sized to its hitbox
assets/
  manifest.json             # arena + UI asset slots
  player/manifest.json      # player action asset slots
  boss/manifest.json        # boss action asset slots
  fx/manifest.json          # FX asset slots
  projectiles/manifest.json # projectile asset slots
art-pack.md                 # empirical asset recipe and prompt inventory
errors.md                   # recurring mistakes for this sub-genre
```

## Runtime shape

- Viewport: $960 * 540$.
- Arena: $1440 * 540$, with horizontal camera scroll clamped inside arena bounds.
- The scene contains one persistent player node and one persistent boss node.
- Projectiles and FX are spawned at runtime through `.node.json` templates.
- Player HP uses `MaskHUDModule` as discrete pips.
- Boss HP uses `StatusBarModule` as a bottom HUD bar.
- Pause, death, and victory menus use `GameOverlayModule`.
- Player, boss, and arena manager expose `runtimeState()` for Runtime API inspection.

## Asset hookup

Every manifest entry ships as a runnable `placeholder_atlas` or `placeholder_image` entry so the skeleton opens and plays with no real art. Swap manifest entries to real `atlas` / `image` entries with the same keys and frame names to add real art; node.json and scripts do not need to change.

Required groups:

- Arena and UI: arena background, mask pip, boss HP icon/slot/fill.
- Player: idle, run, jump, fall, dash, normal attack, charge, charge full, charge release, air attack, hurt, death.
- Boss: idle, walk, antler slam, needle lunge, thorn volley cast, focus, hit, death.
- FX: normal slash, charged slash, air slash, hit spark, ground crack, ash burst, boss lunge.
- Projectile: thorn bolt fly, thorn bolt impact.

## Player FSM

`PlayerController.js` is a concrete action-game controller.

States:

```text
IDLE, RUN, JUMP, FALL,
DASH,
ATTACK, AIR_ATTACK,
CHARGE_BUILD, CHARGE_FULL, CHARGE_RELEASE,
HURT, DIE
```

Core rules:

- `_setState(next)` is the only transition entry and is idempotent.
- `_syncVisualState()` maps gameplay state to animation clip.
- Locomotion states read movement, jump, dash, and attack input.
- Committed states lock input until the gameplay timer clears and the non-loop animation finishes.
- Hitbox active windows are separate from animation and action lock windows.
- Charge flow is build -> full -> release; early release falls back to normal attack.
- Dash is animation-driven, so dash distance depends on `dashSpeed * dashClipDuration`.

## Boss FSM

`BossController.js` is a readable duel boss controller.

States:

```text
IDLE, APPROACH, WINDUP, ACTIVE, RECOVERY, HURT, DIE
```

Attack flow:

```text
windup -> active -> recovery
```

Core rules:

- Distance gates attack choice.
- Cooldowns prevent repeat spam.
- Optional `frameEvents` in `boss.node.json`'s inline `config` can bind attack events to animation frames, such as entering active phase, opening hitboxes, spawning FX/projectiles, or starting lunge movement.
- Windup and recovery wait for non-loop animation completion.
- The active timer owns the damage window; hitboxes close when active ends.
- Needle lunge has phase-specific windup, active, and recovery clips.
- Boss flinches only in idle, approach, recovery, or hurt. Active attacks keep commitment.

## FX and projectile pattern

- `OneShotFx` handles temporary visual effects and removes itself after non-loop animation finish; it is visual-only and never owns collider sizing.
- Attack hitboxes are dedicated child `Collider` nodes with declared width, height, offset, and `flipWithParent`; scripts enable/disable them but never resize or reposition them at runtime.
- The needle-lunge active hitbox carries its sprite FX as a child node so collider and attack FX inspect together.
- `ThornBolt` handles projectile movement, overlap with player/walls, impact FX, and self-removal.

## Framework modules used

The scene expects these framework modules:

- `MaskHUDModule`
- `StatusBarModule`
- `GameOverlayModule`
