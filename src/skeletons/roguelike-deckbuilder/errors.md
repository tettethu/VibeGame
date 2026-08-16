# Roguelike Deckbuilder Errors

## DOM cards drifting from canvas scale

**Symptom:** Cards look correct in one runtime but wrong in the dashboard, or card size no longer matches the logical game composition.

**Cause:** DOM UI and canvas rendering do not share coordinates automatically. If cards are positioned in viewport pixels while the canvas is scaled, the card hand drifts.

**Fix:** Use `DomCardManagerModule` with `logicalWidth`, `logicalHeight`, and `scaleMode`. Treat card positions as logical game-space values, then scale the module's DOM root.

**Spec update:** `.vibegame/spec/contracts/dom_card.md`

## Card size changed but atlas crop still uses old assumptions

**Symptom:** One card appears to show parts of several cards, or card art bleeds from neighboring atlas frames.

**Cause:** Card DOM size and atlas-frame background/crop math were not updated together.

**Fix:** Keep card art lookup tied to `cardW/cardH` in the card frontend. Do not hardcode old card dimensions in CSS or background-size math.

**Spec update:** `.vibegame/spec/contracts/dom_card.md`

## Waiting for Phaser animationcomplete on engine-driven clips

**Symptom:** A turn appears to wait too long after attack or taunt, or a fallback timer fires even though the visible animation ended.

**Cause:** Vibegame `AnimationPlayer` advances clips with dt and directly applies frames using `setTexture` / `setFrame`. It does not call Phaser native `sprite.play()`, so Phaser `animationcomplete` is not the completion signal for these clips.

**Fix:** Use `animationPlayer.isFinished()` for non-loop clips, or use `Animator` transitions with `hasExitTime`. If gameplay sequencing must await an animation, poll the engine `AnimationPlayer` rather than listening for Phaser native animation events.

**Spec update:** `.vibegame/spec/engine/animation-guide.md`, `.vibegame/spec/contracts/dom_card.md`

## Fixed timeout cuts non-loop animations or adds dead time

**Symptom:** Attack or taunt either cuts off early or blocks the next game step after the visible clip has finished.

**Cause:** A fixed timeout is not the same thing as clip completion. Clip timing comes from `frameDurations` or `frameRate * frames.length`.

**Fix:** Let engine animation metadata decide clip length. For battle sequencing, wait for `animationPlayer.isFinished()` and then return to idle for non-die clips.

**Spec update:** `.vibegame/spec/engine/animation-guide.md`

## Large central fly-out card competes with hand refresh

**Symptom:** Consecutive card plays feel delayed, a second attack appears to have no animation, or hand DOM re-rendering fights with the flying card element.

**Cause:** The visual fly-out element and the state-driven hand refresh both try to own card DOM after a play.

**Fix:** Keep the dragged card separate from the hand while dragging, remove it on successful play, and let the battle state call `refresh()` for the remaining hand. Avoid long central fly-out animations unless they are isolated from hand re-rendering.

**Spec update:** `.vibegame/spec/contracts/dom_card.md`

## Arc hand implemented as rotate-only fan

**Symptom:** Cards overlap too much, do not spread like a deckbuilder hand, or hover cannot reveal the full card cleanly.

**Cause:** Rotating cards around their own centers does not place their top edges on a shared arc.

**Fix:** Use arc positioning: each card's top-center pivot sits on a circle. Position cards by angle, put the circle center far below the screen, and lift the hovered card enough that its bottom is visible.

**Spec update:** `.vibegame/spec/contracts/dom_card.md`

## Changing module interfaces instead of using placeholder_atlas

**Category:** Constraints Ignore

**Symptom:** A skeleton carries custom SVG/raster placeholder assets, or module code is edited so it can special-case the engine placeholder.

**Cause:** The conversion treated runnable placeholder as "make any visible asset" or "make the module understand a different placeholder shape" instead of preserving the future real asset interface.

**Fix:** Use `placeholder_atlas` entries in `assets/manifest.json`. Keep the same manifest keys and semantic frame names that real art will use later, so node JSON and modules keep their normal atlas-shaped interface. If a DOM renderer needs an image URL for atlas clipping, use a project-local normal `atlas` entry backed by a placeholder-safe PNG instead of changing the module. Do not add `path` to `placeholder_atlas`; `vibegame check` rejects it.

**Spec update:** `.vibegame/spec/contracts/prototype_polish.md`, `skeletons/roguelike-deckbuilder/index.md`
