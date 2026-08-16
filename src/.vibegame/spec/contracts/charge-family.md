# Charge Family Contract

## Pattern 1: three-sheet-charge-release

### When to use

A player ability with "hold to build, sustain at peak, release for a heavy strike" semantics — charged slash, charged shot, R2 heavy attack, fully-charged beam. The mechanic has three distinct visual phases that the runtime needs to play independently:

- A one-shot build-up that plays while the input is held below the peak threshold.
- A loopable at-peak state that plays continuously after the threshold is reached and the input is still held.
- A one-shot release strike that plays when the input is released (or when a max-hold timeout fires).

If the ability is a single-shot strike with no held-state distinction (a plain attack, a one-button special), use the regular `attack` action and skip this pattern. If the held-state has no visual distinction at peak (the only feedback is a HUD bar filling, the character animation does not change), this pattern is overkill — model the visual as a single `attack` with a runtime damage scalar and ship just the `attack` sheet.

### Responsibility

#### Artist

Artist owns three independent sprite sheets, generated separately, registered separately, and verified for cross-action character-scale consistency.

##### Workflow

1. **Generate**

   The three sheets are:

   - `<ability>_charge` — one-shot build-up.
   - `<ability>_charge_full` — loopable at-peak swirl.
   - `<ability>_charge_release` — one-shot release strike.

   Generation rules:

   - Generate each sheet as a **separate** `vibegame art gen image` call with its own prompt. Do not pack the three phases into one giant sheet — image-gen does not preserve character identity or scale across three widely different actions in a single image.
   - Each sheet uses the same reference image (`-i <ref>.png`) so the character looks identical across all three.
   - `<ability>_charge_full` must loop seamlessly: f3 must reverse direction so the loop closes. Apply the same "reverse closure" rule as `idle` (see `spec/art/sprite.md` "Practice Experience" under `idle`).
   - `<ability>_charge_release` typically shows the character shrunk in-cell because the release FX (a huge slash arc, a wide explosion) consumes most of the cell budget. After manifest registration, compare its frame bbox heights against the canonical action as part of `agents/artist.md` Phase 5 "Cross-action scale gate".

   For each sheet:

   1. Write the prompt using the action enum keys `charge`, `charge_full`, `charge_release`.
   2. Generate with `vibegame art gen image -i <ref>.png -t prompts/<ability>_<phase>.md -o assets/artifacts/<ability>_<phase>_raw.png`.

   Prompt template: write project-local prompts from the action enum keys and follow `spec/art/sprite.md`.

2. **Package**

   For each of the three raw sheets, run the standard sprite pipeline (see `spec/art/sprite.md`):

   1. Remove background (`vibegame art rmbg <image> --agent -o <output>`).
   2. Cut frames (`vibegame art cut --min-area 900`).
   3. Concat into final atlas (`vibegame art concat`).

   After all three sheets are concatenated and registered in the manifest:

   4. After registering manifest bboxes, compare character frame bbox heights against the canonical action for this character (typically `idle` from the same character's base sheet set). Resize the whole animation clip proportionally when it is out of band. See `agents/artist.md` Phase 5 "Cross-action scale gate".

   Manifest entries: register all three as separate `atlas` keys, each with the per-frame bboxes pasted from the `vibegame art concat` output.

   5. Register the three keys in `assets/manifest.json` and update `.vibegame/assets.md`.

3. **Verify**

   VLM audit before delivery:

   - Adjacent frames are visibly separated within each sheet (no cross-frame bleed).
   - The character looks identical across all three sheets (same proportions, palette, costume).
   - The release strike's effect is visibly larger than the matching `attack` sheet, if one exists for the same character.
   - After scale alignment, character body height across the three sheets is visibly consistent (compositing all three on a dark background side-by-side and asking the VLM "do these three actions show the same character at the same size?" should return yes).

Common mistakes:

- Packing the three phases into one sheet. Frames will drift and identity will break.
- Letting `<ability>_charge_full` end on a return-to-neutral frame. It must reverse direction at f3 so it loops without a visible reset to f0.
- Skipping the cross-action scale check. `<ability>_charge_release` is the #1 hot zone for character-scale drift (−40% to −60% relative to `idle`).
- Baking the at-peak swirl into `<ability>_charge`. The build-up should end with the character braced and energy mostly gathered; the at-peak swirl is a separate continuous loop, not the last build-up frame.
- Baking impact FX (sparks, ground crack) into `<ability>_charge_release` frames. Impact FX is a separate runtime spawn — see `### Manifest and asset boundary`.

#### Architect/Programmer

Architect/Programmer owns the state machine that wires the three sheets together:

- Define states `CHARGE_BUILD`, `CHARGE_FULL`, `CHARGE_RELEASE` (or equivalents in the project's naming).
- Define one peak threshold: `chargeFullTime` (seconds from input press to peak). While the input is held below this, play `<ability>_charge`. Once exceeded, transition into the loop `<ability>_charge_full`.
- Define one commit window: `releaseLockTime` (seconds during which `<ability>_charge_release` plays and movement / cancel input are blocked).
- During `CHARGE_BUILD` and `CHARGE_FULL`, the actor is locked: movement input is suppressed. The actor can still receive damage; getting hit interrupts the charge and consumes the buffered animation without releasing the strike.
- During `CHARGE_RELEASE`, the actor is locked: no movement, no cancel, no new attack input until the animation completes.
- The hitbox for the release strike is **persistent across the whole release animation**, not a single-frame swing. This is the practical difference from `attack`: a charged release sweeps a wider arc over a longer duration and should remain hit-active for that whole window.
- Hold-time progress can be surfaced as a runtime read (`actor.chargeProgress: 0..1`) so HUD, AI reactions, and sound systems can react without re-deriving the timer.

Suggested config shape (place in the actor's config or per-ability config):

```json
{
  "chargeFullTime": 0.6,
  "releaseLockTime": 0.4,
  "releaseDamageMultiplier": 3.0,
  "hitboxActiveDuringRelease": true
}
```

Cancel rules — pick one explicitly and document it in the actor's config:

- **Tap-to-attack model**: releasing the button before `chargeFullTime` fires the normal `attack` instead of the release. The release only fires when the button is released after the peak threshold is crossed.
- **Always-commit model**: releasing the button at any time fires the release at a damage scaled by how much of `chargeFullTime` was charged.

Either is valid; the runtime contract is that the choice is config-driven, not hard-coded.

#### Player

Player owns runtime visual and timing verification:

- Hold the input below `chargeFullTime` and release — verify `<ability>_charge` plays once and either ends in the normal `attack` (tap-to-attack model) or a weakened release (always-commit model), per the configured cancel rule.
- Hold past `chargeFullTime` — verify the animation transitions smoothly into the `<ability>_charge_full` loop (no visible reset to f0, no animation seam).
- Release the input after peak — verify `<ability>_charge_release` plays once at the correct timing, the actor is locked for the full `releaseLockTime`, and the hitbox is active for the entire release window (test by sweeping a target through the arc mid-animation).
- Take a hit mid-charge — verify the charge is interrupted and the actor enters `hurt` without firing the release.

#### Reviewer

Reviewer enforces the three-sheet decomposition and the runtime contract:

- Reject a single packed sheet containing all three phases.
- Reject a setup where `<ability>_charge_full` does not loop seamlessly (visible frame-0 reset).
- Reject a setup where the release hitbox is single-frame — that contradicts the "wider arc, longer commit" intent of this pattern.
- Reject a delivery where the character's body height in `<ability>_charge_release` is visibly different from the character's other actions (the cross-action scale check was skipped).
- Reject a setup where the cancel rule is implicit (not declared in config) — the runtime contract requires the choice to be config-driven.

### Manifest and asset boundary

- Register all three sheets in `assets/manifest.json`, each with its own key (`<ability>_charge`, `<ability>_charge_full`, `<ability>_charge_release`).
- The three keys form one logical unit but stay manifest-independent — the runtime references them by name from the actor's state machine. Do not merge them into one atlas; the engine cannot stream a partial-atlas animation as a loop while leaving other phases ready to play.
- VFX produced by the release strike (impact sparks, ground crack, shockwave) belong to the project's FX manifest namespace, **not** the ability namespace. Do not bake impact FX into `<ability>_charge_release` frames; keep it as a separate atlas that the runtime spawns when the hitbox lands. This keeps the release animation reusable across stages and lets the FX be re-tinted, scaled, or swapped without re-generating character frames.
