# Art Pack — 2d-action-boss-fight

Reusable asset list for the 1v1 boss-slice sub-genre. Prompts assume the project has a single style reference image, but they must not depend on an unrecoverable uploaded file or a previous project's private assets. Entries without a prompt point at the relevant `spec/art/*.md` section.

## Map

### background

- prompt
  ```
  Use the project style reference as the style anchor: dark blue hand-drawn gothic dark gothic insect-fantasy boss arena, painterly cartoon shapes, deep arches, ruined stone columns, hanging roots, mist, pale motes, cold blue-black palette.

  Create a single empty side-view battle arena background for a 1v1 boss duel.
  Target composition: a wide 1440x540 game world, camera side-view, no perspective tilt. The floor is a continuous flat stone platform across the full width, readable as the collider surface. Put the visible top floor line around the lower quarter of the image, with chunky cracked stone blocks below it. Left and right arena bounds should be visible as dark ruined wall/column edges, suitable for explicit static colliders.

  Scene content:
  - dark blue ruined gothic hall interior
  - deep archways receding into darkness
  - broken columns and carved stone
  - hanging black roots and tattered vines from the ceiling
  - low mist near the floor and faint pale motes in the air
  - continuous flat stone floor from left edge to right edge
  - subtle foreground silhouettes only at extreme edges, never covering the floor line

  Hard exclusions:
  - no player character
  - no boss character
  - no slash effects
  - no projectiles
  - no UI
  - no text, labels, logos, watermarks, borders, frame lines, grid lines
  - no bright daylight, no colorful fantasy forest

  Keep the arena playable: clear horizontal space, readable floor line, left and right wall boundaries, enough contrast for small white characters and white slash FX.
  ```
- layout: single frame, opaque, ~1.5× camera width for horizontal scroll

**Hints**
- After generation, run the rastermap landmark workflow (see [spec/contracts/rastermap.md](../../.vibegame/spec/contracts/rastermap.md)) to converge `floor_top_y`, `left_wall_right_x`, `right_wall_left_x`, and any prop bboxes.

## Player

### idle

- prompt
  ```
  Use the project style reference as the absolute style anchor: same hand-drawn 2D cartoon style, same thick black outlines, same painterly fills, same color palette (black cloak, white mask, teal mist), dark gothic insect-fantasy aesthetic. Recreate the SAME small masked warrior character from the reference (NOT redesigned).

  Create exactly one 2x2 sheet (4 cells, 2 rows x 2 columns) showing the small cloaked knight character IDLE animation.

  Subject identity (IDENTICAL in every cell, matching the small masked warrior in the reference):
  - small black hooded cloak covering the body
  - white oval/egg-shaped mask with two black horns curving upward
  - two empty black eyeholes on the mask
  - tiny dark legs visible below the cloak
  - holding a long thin silver nail-sword pointed downward in one hand
  - side-view, canonical facing: RIGHT
  - same silhouette, same scale, same proportions in all 4 cells

  Animation (4 idle frames, breathing loop):
  - top-left: neutral standing pose
  - top-right: cloak shifts slightly, subtle weight shift
  - bottom-left: peak of breathing motion, body slightly raised
  - bottom-right: settling back down

  Strict layout:
  - exactly 2x2 grid, 4 equal cells
  - background is 100% solid flat #FF00FF magenta everywhere — NO gradients, NO texture, NO shadow on ground, NO floor plane
  - entire knight fits fully inside each cell with generous magenta margin on all 4 sides
  - nothing crosses cell edges
  - NO grid lines, NO borders between cells, NO text, NO labels, NO UI, NO numbers, NO watermark
  - knight occupies ~55-65% of cell height
  ```
- layout: 2x2 grid

**Hints**
- `idle` is the canonical scale anchor for the character — after manifest registration, compare every other action's frame bbox heights against it (see [agents/artist.md](../../agents/artist.md) Phase 5 "Cross-action scale gate").
- With bottom-center pivot `[0.5,1]`, the lowest visible pixel is the feet. Matching compact frame bbox height keeps in-scene size and the foot baseline stable across actions.

### walk

- prompt
  ```
  Use the project style reference as the absolute style anchor: same hand-drawn 2D cartoon style, thick black outlines, dark gothic insect-fantasy aesthetic. Recreate the SAME small masked warrior character from the reference (NOT redesigned).

  Create exactly one 2x2 sheet (4 cells, 2 rows x 2 columns) showing the small cloaked knight character WALK / RUN cycle.

  Subject identity (IDENTICAL in every cell, same as reference):
  - small black hooded cloak
  - white oval mask with two upward horns and two black eyeholes
  - tiny dark legs visible below cloak
  - holding a long thin silver nail-sword in one hand
  - side-view, canonical facing: RIGHT (moving rightward)
  - same silhouette and scale in all 4 cells

  Animation (4-frame walk loop, side view):
  - top-left: contact, right leg forward and down, left leg pushing back
  - top-right: passing, body slightly raised, legs crossing under center
  - bottom-left: contact, left leg forward and down, right leg pushing back
  - bottom-right: passing, body slightly raised, opposite stride

  Cloak flares slightly with motion. Sword bobs naturally with stride.
  ```
- layout: 2x2 grid

### attack

- prompt
  ```
  Use the project style reference as the absolute style anchor: same hand-drawn 2D cartoon style, thick black outlines, dark gothic insect-fantasy aesthetic. Recreate the SAME small masked warrior character from the reference (NOT redesigned).

  Create exactly one 2x2 sheet (4 cells, 2 rows x 2 columns) showing the small cloaked knight character ATTACK animation (nail-sword sword swing).

  Animation (4-frame attack):
  - top-left (wind-up): knight crouches slightly, sword pulled back over shoulder, ready to strike
  - top-right (strike): sword swings forward in a horizontal slash, body leans into motion, faint white motion arc
  - bottom-left (follow-through): sword fully extended forward and slightly down, body committed forward
  - bottom-right (recovery): sword returns to neutral, body settles back to stance
  ```
- layout: 2x2 grid

### air_attack

- prompt
  ```
  Use the project style reference as the absolute style anchor. Recreate the same small horned white-mask warrior from the reference, not a redesign. Side-view, facing RIGHT. Hand-drawn dark gothic cartoon.

  Create exactly 4 animation frames for player_air_attack, arranged left-to-right as a 1x4 horizontal strip on pure #FF00FF marker background.
  Animation: clearly airborne slash, not grounded normal_attack.
  - frame 0: airborne wind-up, knees tucked, cloak hanging downward, nail pulled back
  - frame 1: midair strike, body floating, nail slashes forward, white arc below and in front
  - frame 2: follow-through in the air, cloak flares, feet not touching ground
  - frame 3: aerial recovery, body drifting, nail lowering

  Strict rules:
  - pure solid #FF00FF magenta background only
  - exactly 4 separated frames
  - no floor, no shadow, no ground contact
  - slash arc stays inside each frame with magenta margin
  - no grid lines, borders, text, labels, UI, watermark
  - same character identity and same body scale in every frame
  ```
- layout: 1x4 horizontal strip

**Hints**
- Airborne pose must read as off-ground (no floor / no shadow) so it is distinguishable from `attack`.

### dash

- prompt
  ```
  Use the project style reference as the absolute style anchor: same hand-drawn 2D cartoon style, thick black outlines, dark gothic insect-fantasy aesthetic. Recreate the SAME small masked warrior character from the reference (NOT redesigned).

  Create exactly one 1x4 sheet (1 row x 4 columns) showing the small cloaked knight character DASH animation — a horizontal dash with after-image trail.

  Animation (4-frame dash):
  - cell 1 (windup): knight slightly crouched, body coiled, sword close to body, wisps of teal energy gathering at feet
  - cell 2 (launch): knight body extended forward horizontally, motion blur streak behind, faint translucent after-image of the knight trailing behind in teal
  - cell 3 (mid-dash): full horizontal stretch, body leaned forward, multiple ghosted after-images trailing behind in fading teal-blue, motion lines streaking
  - cell 4 (recovery): knight landing back upright, last wisps of teal energy fading, returning to stance
  ```
- layout: 1x4 horizontal strip

**Hints**
- After-image trail must stay tightly grouped within each cell, no streak crosses cell edges.

### hurt

- prompt
  ```
  Use the project style reference as the absolute style anchor: same hand-drawn 2D cartoon style, thick black outlines, dark gothic insect-fantasy aesthetic. Recreate the SAME small masked warrior character from the reference (NOT redesigned).

  Create exactly one 2x2 sheet (4 cells, 2 rows x 2 columns) showing the small cloaked knight character HURT animation (taking damage).

  Animation (4-frame hurt reaction):
  - top-left (impact): knight body recoils backward (leftward), mask slightly tilted, white flash silhouette tint on body
  - top-right (knockback): body airborne briefly, knocked back, sword loose, cloak flying
  - bottom-left (stagger): landed, body bent at knees, leaning back, sword arm lowered
  - bottom-right (recovery): straightening up, returning to neutral stance
  ```
- layout: 2x2 grid

### jump / fall

- prompt
  ```
  Use the project style reference as the absolute style anchor: same hand-drawn 2D cartoon style, thick black outlines, dark gothic insect-fantasy aesthetic. Recreate the SAME small masked warrior character from the reference (NOT redesigned).

  Create exactly one 2x1 sheet (1 row x 2 columns, 2 cells side by side) showing the small cloaked knight character in TWO airborne poses for jump and fall.

  Animation (2 frames):
  - LEFT cell (jump rising): knight in airborne ascending pose, body slightly tucked, legs gathered under, cloak trailing downward, sword angled up and back
  - RIGHT cell (falling descending): knight in airborne descending pose, body extended slightly, legs reaching down, cloak flaring upward from wind, sword angled down
  ```
- layout: 1x2 sheet, cut into two single-frame entries

**Hints**
- Output typically arrives +20–30% larger than `idle` body height. Scale down to match `idle` when manifest bbox heights show it is out of band (see [agents/artist.md](../../agents/artist.md) Phase 5 "Cross-action scale gate").

### die

- prompt
  ```
  Use the project style reference as the absolute style anchor: same hand-drawn 2D cartoon style, thick black outlines, dark gothic insect-fantasy aesthetic. Recreate the SAME small masked warrior character from the reference (NOT redesigned).

  Create exactly one 2x3 sheet (6 cells, 2 rows x 3 columns) showing the small cloaked knight character DEATH / DEFEAT animation.

  Animation (6-frame death sequence):
  - cell 1: hit, body recoils, sword dropping from hand
  - cell 2: knight on knees, slumped forward, sword lying beside on ground
  - cell 3: knight collapsed on one side, mask facing camera, body limp
  - cell 4: faint pale wisps of soul-energy starting to rise from body
  - cell 5: body partially dissolving into pale soul wisps, mask still visible
  - cell 6: only faint soul wisps and the abandoned mask remain, body dissipated
  ```
- layout: 2x3 grid

### charge

- prompt
  ```
  Use the project style reference as the absolute style anchor: same hand-drawn 2D cartoon style, thick black outlines, dark gothic insect-fantasy aesthetic. Recreate the SAME small masked warrior character from the reference (NOT redesigned).

  Create exactly one 2x2 sheet (4 cells, 2 rows x 2 columns) showing the small cloaked knight character CHARGE animation — building up power before a special attack.

  Animation (4-frame charge build-up):
  - top-left: knight braced low, sword held vertically in front pointing down, faint pale-white wisps of energy gathering around blade
  - top-right: brighter pale-cyan energy aura swirling around body and sword, mask glows faintly
  - bottom-left: stronger glow, white energy crackling around the knight, body crouched lower with anticipation
  - bottom-right: peak charge, brilliant white-cyan halo around entire knight, sword incandescent, ready to release
  ```
- layout: 2x2 grid

**Hints**
- One of the three sheets in the charge family. See [spec/contracts/charge-family.md](../../.vibegame/spec/contracts/charge-family.md) for the state-machine + hitbox-timing contract.
- The curving white-cyan / purple aura hugging the body IS intended design, not chroma-key residue. Before "cleaning" any purple near the body, run the residue test: if there are **zero non-transparent pixels below the character's foot baseline**, the colored shapes around the body are the aura — do not erase them.

### charge_full

- prompt
  ```
  Use the project style reference as the absolute style anchor. Recreate the same small horned white-mask warrior from the reference, not a redesign. Side-view, facing RIGHT. Hand-drawn dark gothic cartoon.

  Create exactly 4 animation frames for player_charge_full, arranged left-to-right as a 1x4 horizontal strip on pure #FF00FF marker background.
  Animation: loopable peak charge aura while input is held.
  - frame 0: peak stance, nail glowing, white-cyan aura curls clockwise around mask and blade
  - frame 1: aura reaches brightest side sweep, cloak fluttering slightly
  - frame 2: aura crosses behind body, still peak charge, no release
  - frame 3: aura reverses and returns toward frame 0 so the loop closes smoothly

  Strict rules:
  - pure solid #FF00FF magenta background only
  - exactly 4 separated frames
  - no big attack slash, no impact FX, no projectile
  - aura remains tight around body and nail, inside each frame
  - no grid lines, borders, text, labels, UI, watermark
  - same character identity, same body scale, same ground line in every frame
  ```
- layout: 1x4 horizontal strip

**Hints**
- Loopable peak swirl. f3 must reverse direction so it seams back to f0.
- See [spec/contracts/charge-family.md](../../.vibegame/spec/contracts/charge-family.md).
- Chroma-key trap observed on this sheet: the magenta marker survived as a near-pure `#FF00FF` (G≈0) band spanning the full sheet width at the very bottom, which rendered in-game as a purple horizontal line under the feet. Because the intended aura is bluish-purple (G clearly > 0), remove the residue by a **low-G magenta** color key only (G < ~14, high R and B), which spares the aura. Verify by compositing on a contrasting bg and scanning the bottom rows for any G≈0 magenta.

### charge_release

- prompt missing — see [spec/art/sprite.md § charge_release action](../../.vibegame/spec/art/sprite.md)
- layout: 1x4 horizontal strip (per-frame bbox typically diverges after the rescale that the cross-action scale check forces)

**Hints**
- Always check manifest bbox heights after cut + concat — the model often shrinks the character to make room for the slash FX (character body can come out ~50% of `idle`). See [agents/artist.md](../../agents/artist.md) Phase 5 "Cross-action scale gate".
- See [spec/contracts/charge-family.md](../../.vibegame/spec/contracts/charge-family.md).
- The generation recipe (`spec/art/sprite.md § charge_release`) stays the canonical from-scratch path; the ~2.0x rescale still applies to a freshly generated sheet.

## Boss

Boss canonical facing is **LEFT** (toward the player). Grid actions (`idle`, `hurt`, `die`) use a 2x2 / 2x3 sheet; locomotion and attacks use 1x4 strips.

### idle

- prompt
  ```
  Use the project style reference as the absolute style anchor. Recreate the same boss boss from the reference, not a redesign: tall white mask, branch-like antlers, black thin limbs, ragged dark leaf cloak, branch-like spear or needle weapon, eerie gothic insect-forest silhouette. Hand-drawn dark blue gothic cartoon. Side-view, canonical facing LEFT toward the player.

  Create exactly 4 animation frames for boss_idle, arranged as a 2x2 sheet on pure #FF00FF marker background.
  Animation: tall breathing idle with subtle cloak and antler motion.
  - frame 0: neutral looming stance, weapon lowered diagonally
  - frame 1: mask dips, leaf cloak rustles
  - frame 2: antlers glow faintly, body rises slightly
  - frame 3: settles back, loop closes

  Strict rules:
  - pure solid #FF00FF magenta background only
  - exactly 4 separated frames
  - no player, no projectile, no floor, no UI
  - no grid lines, borders, text, labels, watermark
  - same boss identity, same body scale, same ground line, same proportions in every frame
  - full body and antlers visible with generous margin
  ```
- layout: 2x2 grid

**Hints**
- Canonical scale anchor for the boss — every other boss action is compared against `boss_idle` after manifest bbox registration (see [agents/artist.md](../../agents/artist.md) Phase 5 "Cross-action scale gate").

### walk

- prompt
  ```
  Use the project style reference as the absolute style anchor. Recreate the same boss boss from the reference, not a redesign: tall white mask, branch antlers, black thin limbs, ragged leaf cloak, branch-like weapon. Side-view, facing LEFT. Hand-drawn dark gothic cartoon.

  Create exactly 4 animation frames for boss_walk, arranged left-to-right as a 1x4 horizontal strip on pure #FF00FF marker background.
  Animation: grounded stalking walk, feet planted, not floating.
  - frame 0: left foot forward, weapon dragging low, cloak trails
  - frame 1: passing pose, tall body glides but feet visible on ground
  - frame 2: opposite foot forward, antlers tilting
  - frame 3: passing pose returning to frame 0

  Strict rules:
  - pure solid #FF00FF magenta background only
  - exactly 4 separated frames
  - no player, no projectile, no floor, no UI
  - no grid lines, borders, text, labels, watermark
  - same boss identity, same body scale, same ground line in every frame
  ```
- layout: 1x4 horizontal strip

**Hints**
- Legs visible, feet planted (NOT a floating glide). Glide is a separate aerial-reposition sheet.

### glide

- prompt missing — see [spec/art/sprite.md § hover action](../../.vibegame/spec/art/sprite.md)
- layout: 2x2 grid

**Hints**
- Generic sub-genre slot. Add this when the boss needs an aerial reposition or hovering movement read.

### attack_close (slam)

- prompt
  ```
  Use the project style reference as the absolute style anchor. Recreate the same boss boss from the reference, not a redesign. Side-view, facing LEFT toward the player. Hand-drawn dark gothic cartoon.

  Create exactly 4 animation frames for boss_antler_slam, arranged left-to-right as a 1x4 horizontal strip on pure #FF00FF marker background.
  Animation: heavy melee slam with readable telegraph.
  - frame 0: clear telegraph, antlers and branch weapon raised high, bright white glow building, body coiled
  - frame 1: downward slam begins, mask angled down, weapon/antlers descending
  - frame 2: impact pose, branch weapon or antlers slammed downward, bright white force at contact point
  - frame 3: follow-through, body low and extended, glow fading

  Strict rules:
  - pure solid #FF00FF magenta background only
  - exactly 4 separated frames
  - no player, no separate ground crack FX, no projectile
  - first frame must be a wind-up tell, not already hitting
  - no grid lines, borders, text, labels, watermark
  - same boss identity, same body scale, same ground line in every frame
  ```
- layout: 1x4 horizontal strip

**Hints**
- Frame 0 MUST telegraph (weapon/antlers raised, not already swinging). If the model returns a mid-swing as f0, regenerate.
- Large pose-height variation between the raised-weapon f0 and the crouched slam frames is expected — cut per-frame tight bboxes (no same-size padding) so the slam frames do not inherit the tall telegraph frame's height and float.

### attack_mid (lunge)

- prompt
  ```
  Use the project style reference as the absolute style anchor. Recreate the same boss boss from the reference, not a redesign. Side-view, facing LEFT. Hand-drawn dark gothic cartoon.

  Create exactly 4 animation frames for boss_needle_lunge, arranged left-to-right as a 1x4 horizontal strip on pure #FF00FF marker background.
  Animation: committed forward melee lunge threat.
  - frame 0: telegraph, boss crouches back, long branch-needle weapon aimed left, mask focused
  - frame 1: launch, body thrusts forward left, cloak streaming back
  - frame 2: peak lunge, weapon fully extended left, mask and antlers aligned behind strike
  - frame 3: recovery, boss overextended, weapon lowering

  Strict rules:
  - pure solid #FF00FF magenta background only
  - exactly 4 separated frames
  - no player, no projectile, no floor, no UI
  - first frame must be readable wind-up
  - no grid lines, borders, text, labels, watermark
  - same boss identity, same body scale, same ground line in every frame
  ```
- layout: 1x4 horizontal strip

**Hints**
- Frame 0 MUST telegraph with a crouched-back windup. The active frame should read as a forward thrust, not a lateral sweep. Wide horizontal extension in the peak frame; cut tight per-frame bboxes.

### attack_ranged (cast)

- prompt
  ```
  Use the project style reference as the absolute style anchor. Recreate the same boss boss from the reference, not a redesign. Side-view, facing LEFT. Hand-drawn dark gothic cartoon.

  Create exactly 4 animation frames for boss_thorn_volley_cast, arranged left-to-right as a 1x4 horizontal strip on pure #FF00FF marker background.
  Animation: ranged cast from antlers/body, projectile itself is separate.
  - frame 0: readiness, boss still, antlers dim, weapon lowered
  - frame 1: gather, white thorn energy appears around antlers and chest
  - frame 2: release, multiple small bright thorn shapes form near antlers, body leans into cast
  - frame 3: recovery, energy fades, boss returns to stance

  Strict rules:
  - pure solid #FF00FF magenta background only
  - exactly 4 separated frames
  - show casting glow only, not traveling projectiles leaving the frame
  - no player, no floor, no UI
  - no grid lines, borders, text, labels, watermark
  - same boss identity, same body scale, same ground line in every frame
  ```
- layout: 1x4 horizontal strip

**Hints**
- The projectile itself is a separate asset (`projectile_thorn_bolt_fly`) — the cast sheet shows the gather/release glow only, no bolts leaving the frame.

### focus (mid-fight intensity)

- prompt
  ```
  Use the project style reference as the absolute style anchor. Recreate the same boss boss from the reference, not a redesign. Side-view, facing LEFT. Hand-drawn dark gothic cartoon.

  Create exactly 4 animation frames for boss_focus, arranged left-to-right as a 1x4 horizontal strip on pure #FF00FF marker background.
  Animation: short mid-fight intensity roar/focus moment, no new form.
  - frame 0: boss gathers inward, mask lowered, cloak drawn tight
  - frame 1: antlers flare bright white, leaf cloak lifts, black limbs tense
  - frame 2: peak roar/focus, pale motes burst around antlers and mask
  - frame 3: aura collapses back into normal stance

  Strict rules:
  - pure solid #FF00FF magenta background only
  - exactly 4 separated frames
  - no form change, no extra limbs, no player
  - no projectile, no floor, no UI
  - no grid lines, borders, text, labels, watermark
  - same boss identity, same body scale, same ground line in every frame
  ```
- layout: 1x4 horizontal strip

**Hints**
- Phase-transition / sub-50%-HP focus beat (replaces the unused `glide` for this sub-genre). Explicitly forbid "form change / extra limbs" or the model invents a second boss form.

### hurt

- prompt
  ```
  Use the project style reference as the absolute style anchor. Recreate the same boss boss from the reference, not a redesign. Side-view, facing LEFT. Hand-drawn dark gothic cartoon.

  Create exactly 4 animation frames for boss_hit, arranged as a 2x2 sheet on pure #FF00FF marker background.
  Animation: boss taking a hit and recovering.
  - frame 0: impact recoil, mask jerks back, small bright hit flash on body
  - frame 1: stagger, antlers tilt, cloak thrown open
  - frame 2: knees/limbs bend, weapon lowered, recovering
  - frame 3: returns to looming stance

  Strict rules:
  - pure solid #FF00FF magenta background only
  - exactly 4 separated frames
  - no player, no big slash, no projectile, no floor
  - no grid lines, borders, text, labels, watermark
  - same boss identity, same body scale, same ground line in every frame
  ```
- layout: 2x2 grid

### die

- prompt
  ```
  Use the project style reference as the absolute style anchor. Recreate the same boss boss from the reference, not a redesign. Side-view, facing LEFT. Hand-drawn dark gothic cartoon.

  Create exactly 6 animation frames for boss_death, arranged as a 2 columns x 3 rows sheet on pure #FF00FF marker background.
  Animation: branch-mask boss defeat, pale ash and leaves.
  - frame 0: fatal hit, boss recoils, antlers cracked with pale light
  - frame 1: drops to one knee, weapon falling, cloak collapsing
  - frame 2: body slumps, branch antlers breaking apart
  - frame 3: white mask tilts down, pale ash and dry leaves rising
  - frame 4: body dissolves into ash, antler fragments and leaf cloak tearing away
  - frame 5: final pale ash burst, broken mask and branch fragments remain
  ```
- layout: 2x3 grid

**Hints**
- Disconnected ash / leaf fragments get over-cut at default `--min-area`. Tight-crop each original death cell instead of auto-dropping the detached particles.

## FX

All FX are i2i with the style anchor, no character, on `#FF00FF`, authored as 1x4 horizontal strips. Prompt the layout as "horizontal strip of 4 frames", NOT "2x2 grid" — the grid wording can make the model draw literal cell border lines (see [spec/art/sprite.md § Troubleshooting](../../.vibegame/spec/art/sprite.md)).

### normal_slash (slash arc)

- prompt
  ```
  Use the project style reference as style anchor for hand-drawn gothic combat effects. Create exactly 4 animation frames for fx_normal_slash, arranged left-to-right as a 1x4 strip on pure #FF00FF marker background.

  Subject: a small fast white nail slash arc, high-contrast white on dark-blue game backgrounds, no character.
  - frame 0: thin white arc appears
  - frame 1: arc expands brighter with sharp crescent shape
  - frame 2: peak slash, clean white crescent with pale blue edge
  - frame 3: fading trailing shards

  Rules: pure #FF00FF background only, no gradients or shadows in background, exactly 4 separated frames, no characters, no floor, no UI, no text, no border, no grid lines, same center and scale across frames, full FX inside each frame.
  ```
- layout: 1x4 horizontal strip

### charged_slash

- prompt
  ```
  Use the project style reference as style anchor for hand-drawn gothic combat effects. Create exactly 4 animation frames for fx_charged_slash, arranged left-to-right as a 1x4 strip on pure #FF00FF marker background.

  Subject: a large heavy charged white crescent slash, bigger and stronger than normal_slash, pale cyan edge, no character.
  - frame 0: thick white arc starts to ignite
  - frame 1: heavy crescent opens wide, bright core
  - frame 2: peak charged slash, broad white blade-like wave with cyan rim
  - frame 3: fading large crescent fragments and motes

  Rules: pure #FF00FF background only, exactly 4 separated frames, no character, no floor, no UI, no text, no border, no grid lines, same center and scale across frames, leave magenta margin around the entire effect.
  ```
- layout: 1x4 horizontal strip

### air_slash

- prompt
  ```
  Use the project style reference as style anchor for hand-drawn gothic combat effects. Create exactly 4 animation frames for fx_air_slash, arranged left-to-right as a 1x4 strip on pure #FF00FF marker background.

  Subject: a midair white slash arc, slightly diagonal and lighter than charged slash, no character.
  - frame 0: diagonal arc appears in air
  - frame 1: arc sweeps upward-forward, bright white
  - frame 2: peak airy crescent with a few pale motes
  - frame 3: fading thin streaks

  Rules: pure #FF00FF background only, exactly 4 separated frames, no characters, no floor, no UI, no text, no border, no grid lines, same center and scale across frames.
  ```
- layout: 1x4 horizontal strip

### hit_spark

- prompt
  ```
  Use the project style reference as style anchor for hand-drawn gothic combat effects. Create exactly 4 animation frames for fx_hit_spark, arranged left-to-right as a 1x4 strip on pure #FF00FF marker background.

  Subject: small sharp white impact burst, high contrast, no character.
  - frame 0: tiny white contact flash
  - frame 1: sharp starburst spikes
  - frame 2: peak bright shards radiating outward
  - frame 3: small fading pale fragments

  Rules: pure #FF00FF background only, exactly 4 separated frames, no characters, no floor, no UI, no text, no border, no grid lines, same center and scale across frames.
  ```
- layout: 1x4 horizontal strip

**Hints**
- Radiating shards get over-cut. Raise `--min-area` or hand-pick the complete-burst cells.

### ground_crack (slam impact)

- prompt
  ```
  Use the project style reference as style anchor for hand-drawn gothic combat effects. Create exactly 4 animation frames for fx_ground_crack, arranged left-to-right as a 1x4 strip on pure #FF00FF marker background.

  Subject: readable slam impact on stone floor, white shock crack shape and dark stone fragments, no character.
  - frame 0: small contact flash and first thin crack
  - frame 1: cracks spread horizontally with pale light
  - frame 2: peak ground crack burst, sharp white fissures and small dark stone chips
  - frame 3: light fades, cracks remain as thin dark shapes

  Rules: pure #FF00FF background only, exactly 4 separated frames, no characters, no full background scene, no UI, no text, no border, no grid lines, same ground contact center across frames.
  ```
- layout: 1x4 horizontal strip

**Hints**
- Planar ground effect — pivot at the contact center `[0.5, 0.5]`, not bottom-center.

### ash_burst (death)

- prompt
  ```
  Use the project style reference as style anchor for hand-drawn gothic combat effects. Create exactly 4 animation frames for fx_ash_burst, arranged left-to-right as a 1x4 strip on pure #FF00FF marker background.

  Subject: pale ash death burst, quiet gothic soul motes and dust, no character.
  - frame 0: small pale soul puff appears
  - frame 1: ash cloud expands upward with white motes
  - frame 2: widest soft burst of pale particles and leaf-like fragments
  - frame 3: sparse motes fading away

  Rules: pure #FF00FF background only, exactly 4 separated frames, no characters, no floor, no UI, no text, no border, no grid lines, same center across frames, detached particles stay grouped inside each frame.
  ```
- layout: 1x4 horizontal strip

**Hints**
- Disconnected sparkle / mote pieces over-cut at default `--min-area`. Raise `--min-area` or hand-pick cells.

## Projectile

### thorn_bolt_fly

- prompt
  ```
  Use the project style reference as style anchor. Create exactly 4 animation frames for projectile_thorn_bolt_fly, arranged left-to-right as a 1x4 strip on pure #FF00FF marker background.

  Subject: white thorn-bolt projectile, sharp organic thorn energy matching the boss, traveling LEFT from boss toward player. It must read as a thorn or branch needle, not a fireball.
  - frame 0: compact white thorn bolt, pointed left, faint cyan glow
  - frame 1: thorn bolt pulses brighter, small trailing motes
  - frame 2: thorn bolt elongated with jagged organic barbs
  - frame 3: returns to compact shape for seamless loop

  Rules: pure #FF00FF background only, exactly 4 separated frames, no character, no floor, no UI, no text, no border, no grid lines, same projectile size and vertical position across frames.
  ```
- layout: 1x4 horizontal strip

**Hints**
- Loopable; same size and vertical position in every frame, only the internal pulse / barb shape varies. Authored traveling LEFT (boss→player); engine flips if reused for the other direction.

### thorn_bolt_impact

- prompt
  ```
  Use the project style reference as style anchor. Create exactly 4 animation frames for projectile_thorn_bolt_impact, arranged left-to-right as a 1x4 strip on pure #FF00FF marker background.

  Subject: small pale burst when a white thorn-bolt hits, sharp organic thorn fragments, no character.
  - frame 0: tiny contact flash with thorn tip
  - frame 1: burst of white thorn shards
  - frame 2: peak pale organic spike burst
  - frame 3: fading small shards and motes

  Rules: pure #FF00FF background only, exactly 4 separated frames, no character, no floor, no UI, no text, no border, no grid lines, same center position across frames.
  ```
- layout: 1x4 horizontal strip

## UI

### hp_unit

- prompt
  ```
  Use the project style reference as the style anchor. Create one game HUD icon: a single white horned mask pip for player HP, matching the player's mask language. Hand-drawn dark gothic UI, thick black outline, white mask, two small black horns, black eyeholes, readable at small size.

  The icon should be centered, front-facing, clean silhouette, no text. It will be repeated by runtime as 5 discrete HP icons.

  Rules:
  - pure solid #FF00FF magenta background only
  - no gradient or texture in the background
  - no frame rectangle, no full HUD mockup, no text, no number, no label, no watermark
  - generous magenta margin around icon
  ```
- layout: single frame, transparent PNG

**Hints**
- Square / near-square; runtime tiles N copies and dims empty pips. NOT a sheet. See [spec/contracts/status_bar.md Pattern 3 discrete-icon-meter](../../.vibegame/spec/contracts/status_bar.md).

### boss_hp_sheet

- prompt
  ```
  Use the project style reference as the style anchor. Create a decomposed gothic boss HP status bar asset sheet in a vertical 3 rows x 1 column layout on pure #FF00FF marker background. From top to bottom:
  1. boss icon: small boss white mask with branch antlers, black outline, no text
  2. slot: long bottom-center boss HP bar slot, dark blue-black gothic metal/stone frame, subtle branch-thorn ends, empty interior base color, readable continuous fill area
  3. bar: standalone fill-only pale white-cyan HP fill rectangle, no frame, sized to fit inside the slot interior

  Style: hand-drawn dark gothic UI, subdued, matching the concept reference. Keep all three elements separated by wide magenta gaps for cutting.

  Rules:
  - pure solid #FF00FF magenta background only
  - no full gameplay mockup, no text, no labels, no numbers, no watermark
  - slot must not be hollow; show dark interior at 0 HP
  - bar row is fill only, without its own outer frame
  - black outline around icon and slot only
  ```
- layout: vertical 3-section decomposed sheet → cut into `boss_hp_icon` + `boss_hp_slot` + `boss_hp_bar`

**Hints**
- One raw, three final manifest keys. See [spec/contracts/status_bar.md](../../.vibegame/spec/contracts/status_bar.md) for the cut + slot-fill bbox verification workflow. The pale-cyan bar fill from this sheet was later replaced by `boss_hp_bar_fill_v2`.

### boss_hp_bar_fill_v2

- prompt
  ```
  Use project UI references:
  - concept.png is the project mood: dark blue gothic ruins, pale soul energy, black thorn silhouettes, hand-drawn cartoon style.
  - boss_hp_slot.png is the existing ornate frame. The new fill must visually belong inside that frame.
  - boss_hp_bar.png is the old fill to replace because it is too flat and placeholder-like.

  Create ONE horizontal boss HP fill asset only, no outer frame.

  Subject:
  A long horizontal health fill that feels like eerie pale soul energy mixed with thorn sap and moonlit blood, for the boss boss duel. It should be mostly pale cyan, ghostly white, and faint blue, with hand-painted inner texture: soft soul glow, subtle wavering liquid edge, thin dark thorn-vein streaks inside, tiny pale motes, and a few organic branch-like ripples. It must remain readable when cropped from right to left by a status bar module.

  Composition:
  - one long horizontal fill strip, roughly 7:1 aspect ratio
  - centered on a pure #FF00FF magenta marker background
  - transparent-looking empty space outside the fill strip should be marker background only
  - no slot frame, no border, no icon, no text, no labels, no numbers, no UI mockup
  - no plain solid rectangle; the fill must have painterly texture and gothic energy detail
  - keep the silhouette mostly rectangular so it fits inside the existing slot, but use slight organic waviness on the top and bottom edges
  - left-to-right texture should be continuous so cropping still looks good at 25%, 50%, and 75% HP

  Strict background rules:
  - background is 100% solid flat #FF00FF magenta everywhere outside the fill
  - no gradients, shadows, or texture in the magenta background
  - do not use #FF00FF inside the fill art
  - leave generous margin around the fill
  ```
- layout: single horizontal fill strip (~7:1), replaces the flat placeholder fill from `boss_hp_sheet`

**Hints**
- i2i against multiple references (concept mood + existing slot + old fill). Texture must stay continuous left-to-right so right-to-left crop reads correctly at any HP %. Forbid `#FF00FF` inside the fill art so chroma-key does not punch holes in the bar.

### panel

- Use the artist guidance in [spec/contracts/game_overlay.md § Artist](../../.vibegame/spec/contracts/game_overlay.md).
- layout: single frame, transparent PNG

**Hints**
- Frame only; no baked title text. Reused for pause / death / victory.

### button_idle / button_hover

- Use the artist guidance in [spec/contracts/game_overlay.md § Artist](../../.vibegame/spec/contracts/game_overlay.md).
- layout: two single-frame PNGs (or one 1x2 sheet cut into two)

**Hints**
- Hover and idle must share the same canvas size and be centerline-aligned, otherwise the DOM `background-image` swap visibly shifts the button. Ported alongside the `panel` death/pause/victory HUD.
