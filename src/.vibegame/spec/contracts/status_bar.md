# Status Bar Contract

## Pattern 1: sprite-backed-status-bar

### When to use

This pattern covers sprite-backed status bars such as HP, mana, stamina, shield, and boss posture — each bar is an independent UI node assembled from generated raster sprites.

Core idea: a status bar is not a single static image. It is a set of runtime-clippable assets plus one fixed node template. The same `modules/StatusBarModule.js` can power any number of bars. Different `.node.json` files only need different `icon`, `slot`, `bar`, `bbox`, `x`, `y`, and `scale` values to create bars with different visuals, sizes, and positions.

Do **not** use this pattern when the bars are part of a tightly coordinated match HUD with timer, names, round indicators, or mirrored layout — use Pattern 2 instead. Do **not** use this pattern when the meter is a small integer count (1–10) where each unit is a distinct icon (mask / heart / pip) rather than a continuous fill — use Pattern 3 instead.

### Responsibility

#### Artist

Artist owns the art-dependent setup:

- Generate or receive the decomposed source image.
- Cut and clean `icon`, `slot`, and `bar`.
- Iteratively mark the exact inner fill region of `slot`, producing the final `bbox`.
- Package the result as a `.node.json` using the fixed `StatusBarModule` template.
- Register assets in `assets/manifest.json` and update `.vibegame/assets.md`.

##### Workflow

1. **Generate**

   A status bar consists of 3 assets, all from one decomposed source image:

   - `icon` (top of sheet): status icon (heart, magic crystal, stamina bolt). Optional.
   - `slot` (middle): the visible base shown when the value is empty. Must not be hollow — the interior has a visible base color or texture.
   - `bar` (bottom): the rectangular fill that represents remaining value. Flat color or with gradient / highlight. Usually a clean rectangle with no slot frame.

   Runtime fact for context: only the right side of `bar` is clipped; `slot` and `icon` do not change with the value.

   Put the raw under `assets/artifacts/raw/`. Use a pure marker background — `#FF00FF` magenta by default, fall back to `#00FF00`, `#00FFFF`, black, or white if the asset palette conflicts.

   Generation constraints:

   - No text, no labels, no UI mockup.
   - Leave enough pure marker background between icon, slot, and bar for clean cutting.
   - `slot` must not be hollow.
   - `bar` is a fill-only rectangle without its own frame, unless an inner frame is explicitly requested.
   - Pixel art is clean and crisp; no soft anti-aliased transitions.
   - `slot` and `icon` may have black outlines; `bar` usually does not.

   Prompt template — when a reference image exists:

   ```text
   Based on this image, create a decomposed <bar-kind> bar asset sheet in a 3 rows x 1 column vertical layout. From top to bottom: a <icon-shape>, the bar slot, and a standalone <fill-color> <bar-kind> fill bar without the slot.

   Use a pure marker background. Prefer #FF00FF magenta by default, but use another pure marker color if it conflicts with the asset. The slot must not be hollow. At 0 <bar-kind>, the slot should still show an interior base color. Add a black outline around the <icon-shape> and slot. The bar is a frameless <fill-color> rectangle with a subtle gradient and highlight, sized close to the slot's internal fill region.

   Preserve the <style> of the reference. Keep the sheet clean and crisp. No text, no labels, no UI mockup, no speech bubbles, no soft anti-aliased transitions. The three elements must be separated by pure marker background so they can be cut cleanly.
   ```

   Prompt template — when no reference exists:

   ```text
   Create a game asset sheet for a <bar-kind> bar in a 3 rows x 1 column vertical layout. From top to bottom:
   - A <icon-shape> with a black outline
   - A slot: the empty base shown at 0 <bar-kind>, not hollow, with a black outline and deep <slot-color> interior
   - A standalone <fill-color> <bar-kind> fill bar, a frameless rectangle with a gradient, matching the slot's internal fill length and height

   Use a pure marker background. Prefer #FF00FF magenta by default, but use another pure marker color if it conflicts with the asset. The icon height should be slightly smaller than the slot and bar. Leave enough marker background between all three elements for clean post-processing cuts. Keep the sheet clean and crisp. No text, no labels, no UI mockup, no speech bubbles, no soft anti-aliased transitions. <style>.
   ```

2. **Package**

   Remove background and cut the 3 assets. Prefer edge-connected background removal — only remove marker / halo pixels connected to the outside of the canvas. Do not globally delete colors if doing so eats the slot frame.

   If `bar` includes its own frame, extract a fill-only layer to `assets/artifacts/<name>_qc/<name>_bar_fill.png` (post-processing intermediates do not belong in `raw/`).

   Pick the bbox of the slot's internal fill region. Coordinates are slot-image source pixels, top-left origin, format `{ "x": number, "y": number, "w": number, "h": number }`. Start from an eyeballed estimate; the Verify step iterates it to PASS.

   Write final assets:

   ```text
   assets/ui/<name>_icon.png
   assets/ui/<name>_slot.png
   assets/ui/<name>_bar.png
   assets/ui/<name>_slot_bar.png   # full-value preview from Verify
   nodes/<name>Bar.node.json
   ```

   If the original `bar` had a frame, also save `assets/ui/<name>_bar_fill.png`.

   Keep rejected variants and QC overlays under `assets/artifacts/<name>_qc/`. Raw generation outputs stay in `assets/artifacts/raw/` for traceability.

   Every status bar node must provide these 4 config fields:

   ```json
   {
     "icon": "<name>_icon",
     "slot": "<name>_slot",
     "bar":  "<name>_bar",
     "bbox": { "x": 17, "y": 18, "w": 731, "h": 197 }
   }
   ```

   Field meanings:

   - `icon`: manifest key, optional. Use `null` or `""` when there is no icon.
   - `slot`: manifest key for the empty slot image.
   - `bar`: manifest key for the fill-only bar image.
   - `bbox`: internal fill region of the slot, in source pixels.

   Allowed extra fields: `x`, `y` (scene position), `scale`, `leftRate` (initial fill `[0, 1]`), `depth` (Phaser depth), `iconGap` (source-pixel gap between icon and slot), `scrollFactor`, `slotSize` (`{ "width": number, "height": number }` display-size override), and `label` (DOM text aligned to the canvas).

   `label` accepts `text`, `offsetX`, `offsetY`, `originX`, `originY`, `fontSize`, `fontFamily`, `fontWeight`, `color`, `align`, `whiteSpace`, `pointerEvents`, `zIndex`, `letterSpacing`, `textTransform`, and `shadows`. Each shadow accepts `offsetX`, `offsetY`, `blur`, and `color`.

   NodeDef shape:

   ```json
   {
     "name": "<Name>Bar",
     "script": "StatusBarModule",
     "tags": ["<name>Bar", "statusBar"],
     "config": {
       "x": 480,
       "y": 260,
       "scale": 0.28,
       "icon": "<name>_icon",
       "slot": "<name>_slot",
       "bar":  "<name>_bar",
       "bbox": { "x": 17, "y": 18, "w": 731, "h": 197 },
       "leftRate": 1
     }
   }
   ```

   Manifest entries:

   ```json
   {
     "<name>_icon": { "type": "image", "path": "ui/<name>_icon.png" },
     "<name>_slot": {
       "type": "image",
       "path": "ui/<name>_slot.png",
       "landmark": {
         "bbox": {
           "fill-slot": { "x": 17, "y": 18, "w": 731, "h": 197 }
         }
       }
     },
     "<name>_bar":  { "type": "image", "path": "ui/<name>_bar.png" }
   }
   ```

   `landmark` is not consumed by the engine, but architect, programmer, and player use it to audit alignment.

   Finally, update `.vibegame/assets.md` with final paths, manifest keys, bbox, QC overlay path, missing assets, and blockers. Artist stops at final asset + node packaging; artist does not run runtime tests or tune scene position.

3. **Verify**

   Check each cut asset for clean transparency. If VLM cannot judge transparency directly, place the asset on a white background and ask whether any marker halo remains.

   Validate the bbox with overlay + VLM. Iterate to PASS:

   ```bash
   vibegame art label assets/ui/<name>_slot.png \
     --bbox "17,18,731,197:fill-slot" \
     -o assets/artifacts/<name>_qc/slot_bbox_final.png

   vibegame vlm \
     -i assets/artifacts/<name>_qc/slot_bbox_final.png \
     -t "This is a game UI status bar slot. The red bbox labeled fill-slot should mark where the fill bar should be drawn inside the slot. The intended area is the colored interior, not the black outer frame. Does the bbox correctly mark the fill area and is the slot frame visually intact? Answer exactly PASS or FAIL, then a short reason." \
     --add-background white
   ```

   On FAIL, adjust the bbox numbers in Package and re-run label + VLM here until PASS.

   Assemble a full-value preview by compositing `bar` into `slot`'s bbox region (output `assets/ui/<name>_slot_bar.png`). Rules for the assembled preview:

   - Scale or crop `bar` into the `bbox` region of `slot`.
   - `bar` must not cover the slot frame.
   - `bar` must not leave short gaps on the left or right.
   - The slot frame remains intact.

   Then ask VLM:

   ```text
   This is an assembled game UI status bar. The fill bar should sit inside the empty slot, filling the interior area, while the outer frame remains visible, intact, and not covered. The red bbox marks the intended fill area. Answer exactly PASS if the assembled fill is aligned, fills the slot cleanly, has no marker halo, and the frame is intact. Otherwise answer FAIL with a short reason.
   ```

   On FAIL, fix the bbox or re-cut `bar` in Package and repeat. Stop on PASS.

Common mistakes:

- Do not generate a hollow slot. The slot must have a visible interior.
- Do not place a framed `bar` asset directly into the slot unless an inner frame is explicitly desired.
- Do not globally delete marker colors if doing so damages the slot frame. Prefer edge-connected background removal.
- Do not write `bbox` in screen coordinates. It is always slot image source pixels.
- Do not bake current HP or mana into the texture. The current value is controlled by runtime `leftRate`.
- Do not put demo control logic in `modules/StatusBarModule.js`. The template only displays and clips.

#### Architect/Programmer

Architect/Programmer owns gameplay state and formal scene integration:

- Bind gameplay HP, mana, stamina, or similar values to `leftRate`.
- Decide when and how the value changes.
- Place or instantiate the status bar node in the formal scene, with usable initial `x`, `y`, and `scale`.
- If a scene has multiple bars, find them by distinct tags/names. Do not assume there is only one `hpBar`.
- Do not re-measure the artist-delivered `bbox` unless player finds a visual alignment issue and sends it back.

Status bar node interface:

```js
bar.leftRate = 0.5
bar.setLeftRate(0.5)
```

`leftRate` means how much fill remains visible from the left:

- `1`: full bar.
- `0.5`: left half remains, right half is clipped away.
- `0`: no fill is visible.

The template clips from the right. Do not horizontally scale the fill to fake value loss.

Shared code lives in `modules/StatusBarModule.js`. The engine loads it directly via the Module-suffix routing in `boot.js` — no wrapper file in `scripts/` is needed. Reference the module from scene JSON as `"script": "StatusBarModule"`.

If a project needs to customize behavior (e.g. tween animation on value changes, particle burst on damage), subclass the module in `scripts/`:

```javascript
// scripts/PlayerHpBar.js
import StatusBarModule from '/modules/StatusBarModule.js'

export default class PlayerHpBar extends StatusBarModule {
  setLeftRate(value) {
    // tween, particle burst, sfx, etc.
    return super.setLeftRate(value)
  }
}
```

Then reference the subclass: `"script": "PlayerHpBar"`. Do not modify `modules/StatusBarModule.js` for project-specific behavior.

#### Player

Player owns visual tuning after the bar is integrated into a scene:

- Check size, position, depth, and overall readability in runtime.
- Adjust `x`, `y`, `scale`, `depth`, and `iconGap` in the scene or node override.
- Use screenshots or VLM to judge whether the bar blocks gameplay, is too large, too small, too close to the edge, or has awkward icon/bar spacing.
- Do not change the generic clipping logic in `modules/StatusBarModule.js`.
- Do not remake art assets. If `bbox` or the asset itself is wrong, send it back to artist.

### Common mistakes

- **HUD bar scrolls with the world.** This pattern renders as a Phaser container. A container defaults to `scrollFactor = 1`, so if you place it as a screen HUD it slides away as the camera scrolls. The module must `setScrollFactor(0)` on the container and on its children after `add`; a `scrollFactor` config key the module accepts must actually be consumed. Keep this consistent with the discrete-icon-meter pattern, which sets `setScrollFactor(0)` on each icon.

## Pattern 2: fighting-hud-dom

### When to use

Use this pattern for a fighting-game match HUD where status bars are part of a larger coordinated match overlay, not independent resource-bar nodes.

Good fits:

- 1v1, tag, or team fighting games.
- Mirrored HP bars for the two sides.
- A center timer between the two HP bars.
- Fighter names, portraits, super meters, round win dots, READY/FIGHT/KO banners, round results, or match results.
- UI text that should remain real text through CSS, web fonts, or runtime text objects instead of being baked into raster art.
- A fixed or responsive HUD layout that should be controlled by layout rules instead of per-node atlas clipping.

Do not use Pattern 1 for the main mirrored fighting HUD unless each bar is intentionally independent and the timer, names, round state, and mirrored layout are handled elsewhere. A fighting HUD should read as one match UI, not several unrelated status bars.

### Responsibility

#### Artist

Artist does not participate in this contract yet. Fill in this part after a successful project.

#### Architect/Programmer

Architect/Programmer owns HUD structure, state binding, and layout:

- Build a dedicated HUD layer, usually DOM/CSS in browser projects or a scene UI layer in non-DOM runtimes.
- Create separate fill elements or nodes for each side's HP.
- Bind each HP fill width, crop amount, or mask to that fighter's runtime HP ratio.
- Keep HP source of truth in gameplay state, not in the UI element.
- Bind timer text to match timer state.
- Bind round labels, win dots, banners, and result text to match state.
- Keep dynamic UI text as runtime text unless a raster-text art direction is explicitly required.
- Ensure the HUD can be hidden on title/menu screens and shown during match play.
- Ensure CSS, font, or layout files are included in the build/release pipeline.

Recommended DOM structure for a 1v1 HUD (use neutral `p1` / `p2` identifiers; the same structure serves PvP, PvE, replays, and spectator views):

```html
<div class="fight-hud" data-visible="false">
  <div class="hud-side hud-side-left">
    <div class="fighter-name" data-ui="p1-name"></div>
    <div class="hp-frame"><div class="hp-fill hp-p1" data-ui="p1-hp"></div></div>
    <div class="round-dots" data-ui="p1-rounds"></div>
  </div>
  <div class="hud-center">
    <div class="timer" data-ui="timer"></div>
    <div class="round-label" data-ui="round-label"></div>
  </div>
  <div class="hud-side hud-side-right">
    <div class="fighter-name" data-ui="p2-name"></div>
    <div class="hp-frame"><div class="hp-fill hp-p2" data-ui="p2-hp"></div></div>
    <div class="round-dots" data-ui="p2-rounds"></div>
  </div>
</div>
```

Recommended HP binding:

```js
ui['p1-hp'].style.width = `${hpPercent(p1)}%`
ui['p2-hp'].style.width = `${hpPercent(p2)}%`
```

Recommended percent helper:

```js
function hpPercent(fighter) {
  if (!fighter?.maxHp) return 0
  return Math.max(0, Math.min(100, (fighter.hp / fighter.maxHp) * 100))
}
```

Recommended mirrored behavior:

```css
.hp-frame {
  overflow: hidden;
}

.hp-fill {
  height: 100%;
  width: 100%;
}

.hp-p1 {
  margin-right: auto;
}

.hp-p2 {
  margin-left: auto;
}
```

This makes each bar stay anchored to its outer side while the inner edge near the center timer recedes as HP is lost. That is the standard fighting-game read.

#### Player

Player owns runtime visual verification:

- Verify the HUD appears during match play and hides on screens where it should be hidden.
- Verify both sides' HP bars shrink in the correct mirrored directions.
- Verify HP width, crop amount, or mask matches runtime HP after damage and runtime test helpers.
- Verify timer text updates from match timer state.
- Verify round labels, win dots, banners, and result screens update from match state.
- Verify the HUD layer sits above gameplay visuals but does not block gameplay input.
- Verify text remains readable against the stage background.

#### Reviewer

Reviewer owns contract-level acceptance:

- Confirm the selected pattern matches the feature shape.
- Reject CSS-only or DOM-only fighting HUD bars being registered as image assets.
- Reject baked dynamic values in raster UI art unless the task explicitly asks for rasterized text.
- Reject Pattern 1 usage when the requested UI clearly needs mirrored fighting-HUD behavior.

### Manifest and asset boundary

For Pattern 2, CSS-only, DOM-only, or runtime-text-only bars do not require manifest entries.

Rules:

- Do not create a generic status-bar node for the main mirrored fighting HUD unless the project explicitly chooses a node-based HUD layer.
- Do not route mirrored HP bars through `StatusBarModule` unless each bar is intentionally independent and the fighting-HUD behavior is handled elsewhere.
- Do not register CSS-only bars in `assets/manifest.json`.
- Register only actual runtime image assets, such as portraits, chrome, icons, frames, or decorative backplates.
- Do not bake current HP, timer number, fighter name, round label, score, or result text into art assets.

## Pattern 3: discrete-icon-meter

### When to use

Use this pattern when the meter represents a small integer count where each unit is a distinct visible icon — masks in Hollow Knight, hearts in Zelda, pips in arcade games. Each unit is either "full" or "empty"; partial values are not displayed.

Good fits:

- Player HP shown as 3–10 icons (mask / heart / shield pip).
- Charge / combo counter where every step matters.
- Lives counter pinned to a HUD corner.

Do **not** use this pattern when the value is continuous and a fill ratio is meaningful (e.g. health regen visible mid-tick, stamina draining smoothly) — use Pattern 1 (`sprite-backed-status-bar`) instead. Do **not** use this pattern when the meter is part of a mirrored fighting-game match HUD — use Pattern 2 (`fighting-hud-dom`) instead.

### Responsibility

#### Artist

Artist owns one icon asset:

- Generate a single icon PNG sized close to the display target.
- Chroma-key the marker background out to transparent.
- Register one `image` entry in `assets/manifest.json` and update `.vibegame/assets.md`.

##### Workflow

1. **Generate**

   This pattern needs exactly one image: a single pip / mask / heart icon at the desired display style. The runtime instantiates `slotCount` copies and dims trailing empty ones via alpha — there is no separate "empty" variant.

   If the design wants a visible difference between "filled" and "empty" pips beyond alpha dimming (outline-only variant, desaturated grayscale, cracked-broken variant for lost HP), Pattern 3 is the wrong choice — use Pattern 1 (`sprite-backed-status-bar`) with a tiny `slot` + `bar` per pip instead. Pattern 3's contract is "one icon, runtime tiles it, alpha controls fill".

   Shape and resolution constraints:

   - **Aspect ratio**: square or near-square (within ±20%). The runtime tiles copies at a uniform `size` per side; a tall or wide icon produces awkward gaps relative to `config.gap`.
   - **Resolution**: ~2x the eventual display `size` for high-DPI headroom. A 32px display target needs ~64–96px source, not 512px.
   - **Style consistency**: pass the project reference image via `-i <ref>.png` so the icon reads as part of the same UI family as panel / buttons / other HUD pieces.
   - **No baked padding**: tight-crop the silhouette. Extra transparent padding inside the PNG becomes visible gap in the HUD because `config.gap` is added **on top of** the icon's bounding box.

   Use a pure marker background (`#FF00FF` default; fall back to `#00FF00` / `#00FFFF` if magenta conflicts with the icon palette).

   Prompt template: prompt missing — recover via the fallback regen + compare flow (see `artist-self-evolve` SKILL Phase 1) before this contract can be considered prompt-complete.

2. **Package**

   Chroma-key the marker background to transparent (standard `vibegame art rmbg` flow, see `spec/art/sprite.md`). Tight-crop the silhouette so no extra transparent padding sits inside the canvas.

   Write the final asset:

   ```text
   assets/ui/<name>_icon.png
   ```

   Manifest entry — a single `image`:

   ```json
   {
     "<name>_icon": { "type": "image", "path": "ui/<name>_icon.png" }
   }
   ```

   Artist's responsibility ends at the icon image + manifest entry. The `MaskHUDModule` node is placed by Architect / Programmer; no `.node.json` is required from artist.

   Update `.vibegame/assets.md` with the path, manifest key, display-size target, and any cropping notes.

3. **Verify**

   Place the icon on a white background and ask VLM:

   ```text
   This is a single HUD icon. Is the background fully transparent (no marker halo, no leftover marker pixels)? Is the icon tight-cropped to its silhouette with no extra transparent padding around it? Answer exactly PASS or FAIL, then a short reason.
   ```

   On FAIL, re-run chroma-key or re-crop in Package and repeat. Stop on PASS.

   Compose the icon side-by-side with the project's reference image and ask VLM:

   ```text
   These two images come from the same game UI family. Does the icon match the reference's style (line weight, palette, rendering style)? Answer exactly PASS or FAIL, then a short reason.
   ```

   On FAIL, re-generate in Generate with a stronger reference or adjusted prompt. Stop on PASS.

Common mistakes:

- Do not deliver a `slotCount`-frame sheet. The runtime needs exactly one image and arrays it itself.
- Do not bake the count or the player's current HP into the art.
- Do not use a marker color background. Ship transparent PNG (chroma-key the marker out before delivery — see `spec/art/sprite.md`).

#### Architect/Programmer

Architect/Programmer owns binding + placement:

- Place a `MaskHUDModule` node into the HUD subtree of the scene. Reference the module from scene JSON as `"script": "MaskHUDModule"`.
- Configure `iconKey`, `slotCount`, `size`, `gap`, `anchorX`, `anchorY` in the node's `config`.
- Bind gameplay HP to the module: on damage / heal events, call `setValue(currentHp)`.
- Keep HP source-of-truth in the player controller, not in the HUD module.
- If the project needs per-unit hit animations (a single mask flashing red when lost, a small particle burst per unit), subclass the module in `scripts/`:

```js
// scripts/PlayerMaskHUD.js
import MaskHUDModule from '/modules/MaskHUDModule.js'

export default class PlayerMaskHUD extends MaskHUDModule {
  setValue(n) {
    const prev = this.getValue()
    const result = super.setValue(n)
    if (n < prev) this._flashLastUnit()
    return result
  }
  _flashLastUnit() { /* ... */ }
}
```

Then reference the subclass: `"script": "PlayerMaskHUD"`. Do not modify `modules/MaskHUDModule.js` for project-specific behavior.

Reference scene placement (replace `p1` / `iconKey` with project values):

```json
{
  "name": "PlayerHUD",
  "script": "MaskHUDModule",
  "tags": ["hud", "p1Hp"],
  "config": {
    "iconKey": "ui_mask_icon",
    "slotCount": 5,
    "size": 32,
    "gap": 8,
    "anchorX": 16,
    "anchorY": 16
  }
}
```

#### Player

Player owns runtime tuning:

- Verify all `slotCount` pips render and pin to the screen edge (no camera scroll).
- Verify `setValue(n)` dims trailing pips correctly across the full range (0..slotCount).
- Tune `size`, `gap`, `anchorX`, `anchorY` against the actual viewport for legibility.
- Do not change the generic dimming logic in `modules/MaskHUDModule.js`.

#### Reviewer

Reviewer confirms the selected pattern matches the feature shape:

- Reject Pattern 3 when the design requires partial / continuous fill within a unit.
- Reject sheet-based icon delivery (Pattern 3 ships one image, not a sheet).
- Reject baked HP values in the icon art.

### Manifest and asset boundary

- One image per meter: a single `image` entry. No sheet, no atlas.
- Multiple discrete meters in the same HUD (e.g. HP pips and lives) each get their own icon and their own module instance.
