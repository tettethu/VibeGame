# DOM Card Contract

## Pattern 1: dom-card-hand-frontend

### When to use

Use this pattern when a game needs a browser-DOM card hand that renders pure card data into playable cards, including card art, text layers, hover lift, drag-to-target interaction, tooltip, target highlighting, and logical-resolution scaling. It is practice-verified for a fixed-screen turn-based deckbuilder battle slice with a bottom hand, energy-gated cards, enemy/self targets, and card rewards.

The produced runtime object is a node using `script: "DomCardManagerModule"`. The module is a frontend. It does not own deck rules, damage rules, reward rules, or turn progression.

### Basic Knowledge

A card has two separate meanings:

- Display data: what the card looks like on screen.
- Rule data: what the game does after the card is played.

`DomCardManagerModule` reads display data and passes the whole card object back to the game. The battle script decides what `effect`, `value`, `draw`, `vuln`, or other rule fields mean.

A card is not a node. In this pattern, a card is plain data rendered by one hand frontend node. The hand frontend owns the DOM card elements, pointer hover, drag, target box, and drag arrow.

### Card data shape

Minimum display fields:

```js
{
  id: 'strike',
  uid: 'unique-card-instance-id',
  name: 'STRIKE',
  type: 'Attack',
  cost: 1,
  desc: 'Deal 6 damage.',
  category: 'offense'
}
```

Optional rule fields are allowed and passed through untouched:

```js
{
  effect: 'damage',
  value: 6,
  draw: 1,
  vuln: 2,
  playAnim: 'attack'
}
```

Field meanings for the module:

- `id`: atlas frame key fallback and stable card kind.
- `uid`: stable instance key when multiple copies of the same card exist.
- `name`: title text.
- `type`: visible card type label, for example `Attack`, `Skill`, `Power`.
- `cost`: energy gate and optional visible cost badge.
- `desc`: bottom rules text.
- `category`: visual style class fallback, for example `offense`, `defense`, `utility`.

### Responsibility

#### Artist

Artist owns the card-art pipeline behind `DomCardManagerModule`'s `cardAtlas`. Scope:

- One raw illustration sheet covering every card `id` in the deck — generated in a single pass for style consistency.
- Decomposed into N transparent-background final sprites under one atlas, frame names = card `id`.
- Burned-in cost badge (when requested by the design); name / type / description text stays as DOM overlay and is **never** painted into the art.

##### Workflow

1. **Generate**

   This pattern needs **one raw sheet** — see [skeletons/&lt;slug&gt;/art-pack.md `### cards_<N>`](../../../skeletons/) for the practice-verified example (the `roguelike-deckbuilder` art-pack records a 12-card 6×2 grid at 3840×2160).

   Use a pure marker background — `#FF00FF` magenta by default. Pass the project style reference as `-i` so all cards inherit one cohesive painterly look. Generate the entire deck in a single image: one-shot card-deck generation is the only reliable way to keep style, character identity, and border treatment consistent across the set.

   Templated prompt — derived from the art-pack pattern, placeholders in `<…>`:

   ```text
   A single image containing <N> <theme> card illustrations arranged in a <cols>-column x <rows>-row grid on a pure magenta (#FF00FF) background. Each card is a vertical (portrait) rectangle. CLEAR magenta strips between every pair of adjacent cards so cards do NOT touch. No grid lines, no separators, no borders drawn between cells — just plain magenta gap.

   Style: ALL <N> cards share IDENTICAL <style-descriptor> matching the project reference image. Each card has the same visual treatment, the same border/edge style, the same painterly finish — they must look like a single set.

   Per-card structure (applies to ALL <N> cards identically):
   - Card is a vertical rectangle with a thin dark inner border, painted edges
   - TOP-LEFT corner of the card: a SOLID YELLOW (warm gold) CIRCULAR BADGE about 18 percent of card width in diameter, with a dark navy/black numeric digit in the center. The badge is INSIDE the card art (NOT floating outside), painted into the illustration. The digit is the card's <cost-field>.
   - The REST of the card is the card's main illustration depicting the card's effect
   - NO text anywhere on the card except the cost digit inside the yellow circle. NO card name, NO type label, NO description text — those will be added separately later as DOM overlay

   Card grid (left-to-right, top-to-bottom). All artworks depict effects involving the SAME <player-character> from the reference image — same character identity throughout:

   ROW 1:
   1. <CARD-1-NAME> (cost <c1>): <visual-concept-1>
   2. <CARD-2-NAME> (cost <c2>): <visual-concept-2>
   ...

   Hard requirements:
   - Pure flat magenta (#FF00FF) background, completely uniform, no gradient
   - Exactly <N> cards in a <cols>-column x <rows>-row layout
   - Each card is a portrait rectangle, all <N> the SAME size and orientation, evenly spaced with clear magenta gaps
   - No card touches another; clear magenta strip between every pair
   - Cost badge: yellow circle TOP-LEFT corner INSIDE each card, with the cost digit clearly visible
   - No card text (no card name, no type, no description) — only the cost digit in the badge
   - The SAME <player-character> appears consistently across all illustrations
   - All <N> cards must read clearly as their described concept; viewer should distinguish them at a glance
   ```

   Aspect-ratio constraint: each card cell's `width:height` should match the module's `cardW:cardH` config (or stay close). For a `95×136` runtime card, painted-card cells should be roughly `2:3` portrait so neither side gets cropped at render. Sketch the cell aspect in the prompt's "vertical rectangle" wording, not as a numeric ratio (image-gen models ignore numeric ratios in prose).

2. **Package**

   Save raw under `assets/artifacts/raw/cards/<deck>_v1.png`. Then run chroma-key removal — gap pixels often drift away from pure `#FF00FF` (commonly `~232, 39, 225` for gpt-image-2), so sample the actual gap color and use a wider tolerance:

   ```bash
   vibegame python -c "from PIL import Image; import numpy as np; \
     arr = np.array(Image.open('assets/artifacts/raw/cards/<deck>_v1.png')); \
     print(arr[arr.shape[0]//2, arr.shape[1]//6])"   # sample one gap column
   vibegame art rmbg assets/artifacts/raw/cards/<deck>_v1.png \
     -c <r>,<g>,<b> -t 60 -o assets/artifacts/clean/cards_<deck>.png
   ```

   Auto-cut into N components, then **rename each cut frame to its semantic card `id`** so concat's `manifest.json` ships with frame names that match the `id` field in card data (the module looks up `cardAtlas` frames by `id`):

   ```bash
   vibegame art cut assets/artifacts/clean/cards_<deck>.png \
     -o assets/artifacts/cut/ --min-area 50000
   # rename: cards_<deck>_c0.png -> 01_strike.png, c1 -> 02_deflect.png, ...
   # the numeric prefix preserves order for concat; the suffix is the manifest frame key
   vibegame art concat assets/artifacts/cut/cards_<deck>/ \
     -o assets/cards/<deck>.png --layout <cols>x<rows> --spacing 4
   ```

   Final asset, manifest entry, and node template:

   ```text
   assets/cards/<deck>.png
   ```

   Add the atlas to `assets/manifest.json` (the master, not a sub-folder manifest — concat may write one alongside the PNG, **trash it** afterward):

   ```json
   "cards": {
     "type": "atlas",
     "path": "cards/<deck>.png",
     "pivot": [0.5, 0.5],
     "sprites": {
       "strike":  { "bbox": [7,    1, 567, 933] },
       "deflect": { "bbox": [587,  1, 576, 934] },
       "bash":    { "bbox": [3,  941, 574, 934] }
     }
   }
   ```

   The node consuming this atlas is the `DomCardManagerModule` node in this contract — the artist does not author it, but the atlas key registered here (`cards`) must match the module's `config.cardAtlas`.

3. **Verify**

   For each card frame, run a chroma-halo + safe-area check via overlay + VLM. The cost badge is the highest-risk feature because the DOM hand overlays text bands at the top-center for `name` / `type`; the badge must stay in the top-LEFT safe corner:

   ```bash
   vibegame art label assets/cards/<deck>.png \
     --bbox "<x>,<y>,<w>,<h>:strike" \
     --bbox "<bx>,<by>,<bw>,<bh>:cost-safe-area" \
     -o assets/artifacts/cards_qc/strike_safe.png

   vibegame vlm \
     -i assets/artifacts/cards_qc/strike_safe.png \
     -t "This is a single card from a card-game atlas. The card-safe-area bbox should contain the entire card with no marker halo at its edges. The cost-safe-area bbox marks the top-left corner where the cost badge should live. Answer PASS only if: (1) the card has no magenta halo, (2) the yellow cost badge sits inside the cost-safe-area bbox, (3) no card name / type / description text is painted into the art (the DOM overlay will add those). Otherwise FAIL with a short reason." \
     --add-background white
   ```

   On FAIL, fix in Package (re-run rmbg with higher tolerance for halo, or re-cut with adjusted boundaries for badge placement). On chronic badge-position FAIL across many cards, re-generate with stronger prompt emphasis on the "TOP-LEFT corner" clause.

   Second VLM pass — set identity / style consistency across the whole deck (renders the full atlas with thumbnails of every card side-by-side):

   ```text
   This is an atlas of <N> game cards. Do all <N> cards share an identical art style — same painterly finish, same border treatment, same character identity across every illustration that depicts the player? Answer PASS or FAIL with a short reason naming any card that breaks set consistency.
   ```

   On FAIL, regenerate in Generate. The recurring fix is to combine the project reference image AND a previously-good card frame as two `-i` inputs so style drift cannot reset between batches.

Common mistakes:

- Generating cards one at a time instead of one-shot grid — style drifts between runs, character identity wanders, and the set no longer reads as one deck.
- Painting card name / type / description text into the art. The DOM frontend renders those from card data; text-in-art collides with the DOM overlay at every breakpoint.
- Cost badge floating outside the card (CSS overlay style) when the design asked for burned-in. The badge must live INSIDE the card art so the cost cannot drift out of sync with card data.
- Using auto-generated frame names (`c0`, `c1`, …) in the manifest. Rename to the card `id` (`strike`, `deflect`, …) — the module looks frames up by `id`, not by index.
- Generating cards at an aspect ratio far from `cardW:cardH`. The DOM card stretches or letterboxes; both look wrong. Match the runtime card rectangle (commonly ~2:3 portrait).
- Skipping the chroma-key tolerance check. Card-deck gaps often drift from `#FF00FF` to a desaturated nearby color; `-t 30` leaves gaps un-removed and the cut tool finds 1 mega-component instead of N cards.
- Leaving sub-folder `manifest.json` files from `vibegame art concat`. The master `assets/manifest.json` is the single source of truth; trash the per-folder ones every time.

#### Architect/Programmer

Use `modules/DomCardManagerModule.js` rather than writing a new hand renderer. Add one scene node:

```json
{
  "name": "CardManager",
  "script": "DomCardManagerModule",
  "tags": ["handRenderer", "cardManager"],
  "config": {
    "cardAtlas": "cards",
    "logicalWidth": 960,
    "logicalHeight": 540,
    "scaleMode": "stretch",
    "layout": "arc",
    "cardW": 95,
    "cardH": 136,
    "targets": [
      { "id": "enemy", "tag": "enemy" },
      { "id": "self", "tag": "player" }
    ],
    "enemyTargetEffects": ["damage", "bash", "twin_strike", "vuln_enemy"]
  }
}
```

Wire it from the battle script:

```js
const hand = this.findByTag('handRenderer')[0]
hand.setCardPlayCallback((index, target, event) => {
  const card = event.card
  // Game rules resolve here.
})
hand.refresh(cards, energy, phase, locked)
```

Public runtime input:

```js
setState({ cards, energy, phase, locked })
refresh(cards, energy, phase, locked)
```

Public runtime output:

```js
card_play_requested event
setCardPlayCallback((index, target, event) => {})
```

Static/runtime checks:

- `DomCardManagerModule` runs a runtime self-check in `ready()` for invalid layout, scale, size, target, and card atlas config.
- `modules/DomCardManagerModule.check.py` can statically validate a `.node.json` or `.scene.json` containing `script: "DomCardManagerModule"`. It checks required config shapes, positive layout numbers, target entries, and whether `cardAtlas` exists in project manifests.

Layout rules:

- `layout: "flat"` uses `xSpread`, `handRootW`, `handRootH`, `hoverScale`, `hoverLift`, and `neighborShift`.
- `layout: "arc"` uses `arcCenterX`, `arcCenterY`, `arcRadius`, `arcCenterAngleDeg`, `arcAngleStepDeg`, `arcMaxAngleDeg`, and `hoverGapAngleDeg`.
- Arc cards use top-center pivot. The visual model is: the top center of each card sits on a circle; card position is represented by angle.
- For a deckbuilder-style bottom hand, place the circle center far below the screen and allow non-hover cards to extend partly off-screen. On hover, lift the hovered card enough that its bottom is fully visible.

Drag indicator rules:

- Use chevron bands for card targeting, not a line plus arrowhead.
- Tune `arrowColor`, `arrowChevronSpacing`, `arrowChevronLength`, `arrowChevronWidth`, `arrowChevronStroke`, and `arrowSpring` in node config.
- The drag arrow is decorative. Target validation still comes from the configured `targets` and hit boxes.

Scaling rules:

- The module owns a logical DOM root. Do not position card DOM directly in viewport pixels.
- Use `logicalWidth/logicalHeight` matching the game canvas design size.
- `scaleMode: "fit"` preserves aspect ratio with letterboxing. `scaleMode: "stretch"` fills the container, matching projects that stretch the canvas to the dashboard viewport.

Boundaries:

- Do not put battle rules into `DomCardManagerModule`.
- Do not instantiate one node per card for this pattern.
- Do not use CSS-only hover when neighboring cards must move. The module computes neighbor layout in JS.
- Do not rely on unscaled DOM coordinates when the canvas is scaled by the dashboard.

#### Player

Verify with runtime evidence:

- Initial hand renders the expected number of cards.
- Energy-locked cards are visibly disabled and cannot be dragged.
- Hover enlarges the card, lifts it, keeps its bottom visible, and moves neighboring cards without layout jumps.
- Dragging shows the chevron band arrow and target box.
- Releasing over the correct target emits one play request and changes game state once.
- Releasing over empty space snaps the card back without spending energy or changing hand state.
- Dashboard Play viewport and headless runtime viewport both preserve usable card positions.

#### Reviewer

Reject if the card frontend owns game rules, if battle logic depends on DOM class names, if card art and card config disagree on aspect ratio, or if a card can visually play without a matching state transition in the battle script.

### Manifest and asset boundary

The card atlas must be registered in `assets/manifest.json`. Frame keys should match card `id`. The card frontend may render visible text overlays from data, but card illustration pixels come from the atlas.
