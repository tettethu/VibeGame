# Roguelike Deckbuilder Skeleton

This skeleton is a fixed-screen turn-based card battler with a reusable DOM card hand frontend. It is meant to be cherry-picked when a new project wants a Slay-the-Spire-style battle slice without rebuilding the deck / hand / discard / energy loop from scratch.

## Shape

- Logical viewport: `960 x 540`.
- Canvas style: painterly or illustrated assets, `pixelArt: false`.
- Scene shape: one battle scene, no camera scrolling.
- Engine source: intentionally not copied into this skeleton. `vibegame run` uses source-engine fallback for runnable skeletons; generated game projects should run `vibegame init` to copy `./engine`.
- Player position: left side, feet near bottom combat floor.
- Enemy position: right side, feet on the same combat floor.
- Hand: bottom arc layout, cards partly below screen when idle, hovered card fully visible.
- DOM HUD: player resources in top-left, turn / discard / end-turn in bottom-right, enemy intent and combat stats near enemy.

## Systems included

- `BattleManager.js`: deck, draw pile, hand, discard pile, energy, turn loop, fight loop, card reward, death overlay, state export.
- `CardData.js`: starter deck plus reward pool as pure data.
- `DomCardManagerModule`: referenced by scene JSON for the hand frontend. The module itself lives in top-level `modules/`.
- `HudRenderer.js`: DOM HUD and end-turn button glue.
- `PlayerCharacter.js` / `EnemyCharacter.js`: thin animation wrappers using engine `AnimationPlayer.isFinished()` polling.
- VFX node templates using `TimedImageVfxModule`.
- `UpgradeChoiceModule` card reward picker template.
- `GameOverlayModule` run-over overlay usage.

## Recommended reuse

Use the skeleton for the battle loop and frontend wiring, then replace:

- card roster and card effects,
- enemy intent table,
- reward pool,
- HUD copy and icon style,
- art atlas keys and manifest paths,
- balance numbers.

Do not turn `BattleManager.js` into a generic module by default. Card rules are project-specific and cheap to rewrite. The reusable part is the hand frontend: use `DomCardManagerModule` and the `dom_card.md` contract.

## Card frontend defaults

The scene starts with a bottom arc hand. In the skeleton, `cardAtlas` is already the future real atlas key, `cards`. `assets/manifest.json` provides that key as a normal `type: "atlas"` backed by `assets/placeholder/card_placeholder_atlas.png` because `DomCardManagerModule` renders card art through DOM `<img>` elements and needs a real image URL:

```json
{
  "layout": "arc",
  "cardW": 95,
  "cardH": 136,
  "arcCenterX": 480,
  "arcCenterY": 1150,
  "arcRadius": 720,
  "arcAngleStepDeg": 6,
  "arcMaxAngleDeg": 32,
  "hoverLift": 108
}
```

These values intentionally put the circle center far below the screen. Non-hover cards can extend below the viewport; hovered cards should lift enough to show the full card.

## Animation completion rule

The engine animation path here is transparent: `AnimationPlayer` is dt-driven and applies frames by `setTexture` / `setFrame`. It does not use Phaser native `sprite.play()`, so scripts must not wait for Phaser `animationcomplete`. Use `animationPlayer.isFinished()` or animator transitions with `hasExitTime`.

## Placeholder assets

The runnable skeleton uses `placeholder_atlas` entries in `assets/manifest.json` for player, enemy, VFX, and HUD icons. Each entry keeps the future real asset key and semantic frame names, so node JSON and modules stay atlas-shaped from day one. The `cards` entry is a normal `atlas` backed by `assets/placeholder/card_placeholder_atlas.png` because the DOM card renderer clips card art through an `<img>` URL and needs a real path. Future projects polish by replacing those manifest entries with real `type: "atlas"` entries using the same keys and frame names.
