# Art Pack — roguelike-deckbuilder

Reusable raw-asset list for the 1v1 turn-based card-battler sub-genre. Prompts assume the project has a single style reference image. Entries without a prompt point at the relevant `spec/art/*.md` section. Project-specific names and signage are neutralized; replace placeholders (`<player-character>`, `<boss>`, in-world signage text, etc.) when reusing.

**Cross-cutting practice deltas (learned on this sub-genre, apply to every entry below):**

- **Reference-vs-description conflict.** When a dedicated *character* reference image is passed as `-i` (not just a style anchor), the prompt must NOT re-describe the character's appearance (hair length, outfit, palette) in free-form prose. Say only "match the character in the reference image exactly; do not change hair length / outfit / palette." Re-describing invites a prose-vs-image conflict, and the model follows the prose — e.g. prompting "long hair" over a short-haired reference produced long hair. Free-form character description is reserved for (a) no reference image, or (b) deliberate stylization (chibi, proportion remap). A plain style-anchor screenshot (no isolated character) is the exception — describing the character is still needed there.
- **Copyright boundary.** Do not anchor a playable/enemy character on a copyrighted IP character image. Use original in-house concepts. (A Cyberpunk: Edgerunners "Lucy" anchor was rejected mid-project for this reason; the shipped player is an in-house silver-bob design.)
- **Idle restraint.** Idle sheets carry breathing + one secondary natural motion only (hair sway, cloth drift). Do NOT bake in designer "flavor" gestures (hand-near-temple, interface-poking) — those make the loop read as a scripted action, not an idle. See `spec/art/sprite.md` idle Practice Experience.

## Map

### battle_bg

- prompt
  ```
  A single static cyberpunk ruins night-scene battle arena background. Side-view (horizontal landscape). Game art for a 2D card battler in the style of the project reference image.

  Composition (three depth layers, NO foreground characters):
  - FAR BACKGROUND (upper third of image): towering neon skyscrapers and broken signs glowing magenta, cyan, and dim orange against a dark teal-purple polluted night sky. One large vertical neon billboard partially visible in stylized retro-cyber lettering, slightly tilted and flickering — the billboard glyphs may be abstract or unreadable; do NOT embed a fixed project-specific phrase. Atmospheric haze, faint smog, distant pinpoint city lights, soft volumetric glow.
  - MID BACKGROUND (middle third): silhouettes of collapsed/ruined industrial buildings, twisted rebar and concrete chunks, heavy thick vines and overgrowth wrapping the wrecked structures, dark teal-cyan rim light on the vine leaves, a few dim windows still lit warm orange behind broken walls. Slightly out of focus for depth.
  - FOREGROUND PLATFORM (lower third): a clear wide flat ground platform stretching horizontally across the entire width of the image, made of cracked concrete and wet broken pavement reflecting magenta and cyan neon. Puddles of water with subtle reflections. The ground line is FLAT and HORIZONTAL across the full width, sitting roughly at 70 percent down the image (so characters stand on it with sky above). No foreground objects blocking the playable space in the middle; the center 60 percent of the width is open arena. A few subtle props at far left and far right edges (a broken pipe, a piece of rebar, a small chunk of rubble) anchor the foreground depth but stay out of the center.

  Color palette: dominant deep teal-cyan and magenta-violet neon, with deep blacks in shadows and tiny warm orange accents. Heavy atmospheric perspective. Subtle film grain.

  Style: painterly stylized digital illustration, dramatic cinematic lighting, soft glow on neon signs, light volumetric fog, matches the project reference image style exactly (high-contrast painterly, no pixel art).

  Hard requirements:
  - NO characters, NO player, NO enemy, NO creatures
  - NO floating UI, NO HUD elements, NO text overlays except the in-world flickering neon billboard (abstract/unreadable lettering)
  - The ground line in the lower third is FLAT and HORIZONTAL all the way across; do not slope or break it
  - Open center playable space (do NOT place big props at center bottom)
  - Cinematic horizontal composition suitable as a 960x540 or wider battle arena backdrop
  - High visual style consistency with the reference image
  ```
- layout: single frame, opaque, 16:9 horizontal (1024×768 native, target 960×540 canvas)

**Hints**
- Run the rastermap landmark workflow (see [spec/contracts/rastermap.md](../../.vibegame/spec/contracts/rastermap.md)) to record `ground_y`, `left_bound_x`, `right_bound_x` for explicit ground / wall colliders. The programmer places a horizontal ground collider at `ground_y` so character feet sit on the visible platform.

## Player

### player_idle

- prompt
  ```
  A horizontal sprite sheet of 4 idle-pose breathing-cycle frames of the SAME character on pure flat magenta (#FF00FF) background. The 4 frames are arranged in a SINGLE HORIZONTAL ROW (exactly 1 row x 4 columns).

  CRITICAL SIZING: Each character occupies 75-85 PERCENT of the cell HEIGHT (the character is TALL — head near the top of the cell, feet at the very bottom of the cell). Cells are equal-sized.

  GAP BETWEEN FRAMES: There must be a clear strip of pure magenta background (at least 60 px) between every pair of adjacent frames. NO body part, NO hair strand, NO sword blade, NO sword glow halo may cross the gap. Treat each cell like an isolated booth.

  Character: a slender young woman with short silver-white bob hair, fair skin, sleeveless black cropped tank top, black tactical shorts, tall black combat boots. She wields a glowing thick violet/magenta ENERGY longsword (saturated glowing energy blade, NOT a thin steel katana) in her right hand, sword held DOWN by her right side, blade pointing roughly down-right. Same character identity as the project reference image.

  4-frame idle breathing animation, character facing RIGHT. Camera stays the same (side view, ground line at very bottom of cell, both feet planted on the cell-bottom baseline). The CHARACTER'S BODY HEIGHT remains roughly constant across all 4 frames — character stands still with only subtle breathing:

  - Frame 1 of 4 (inhale peak): chest slightly raised, shoulders lifted a touch, head slightly up
  - Frame 2 of 4 (neutral, mid-cycle): base neutral pose
  - Frame 3 of 4 (exhale low): chest slightly lowered, shoulders dipped a touch, head slightly down
  - Frame 4 of 4 (neutral, returning): back to base, ready to repeat loop

  Style: painterly stylized digital illustration matching the project reference image, soft cinematic lighting, deep blacks in clothing, rim light on hair and shoulders, glowing violet energy blade highlights. Cohesive character identity across all 4 frames — same face, hairstyle, outfit, body proportions, scale. CRITICALLY: same FOOT BASELINE at the very bottom of each cell + same head-top y position (character body height constant; only chest/shoulder Y shifts by 3-5 px for breathing).

  Hard requirements:
  - EXACTLY 4 frames, EXACTLY 1 row x 4 columns horizontal layout
  - Pure flat magenta (#FF00FF) background, uniform
  - Each character is TALL (75-85% of cell height), full body from head to boots, feet planted at the very bottom of each cell
  - All 4 characters share roughly the same head-top y and the same feet-bottom y (uniform body height across frames)
  - 60+ px clear magenta gap between adjacent frames
  - Sword (held at right side pointing down-right) stays entirely within its cell — no blade tip or glow crosses the cell boundary
  - No text, labels, panel borders, UI, speech bubbles
  - Sword is a THICK glowing violet/magenta ENERGY BLADE (saturated, soft glow halo), NOT a thin steel katana
  - Energy glow uses violet + cyan, not pure #FF00FF
  - Character faces RIGHT in every frame
  ```
- layout: 1×4 horizontal strip, 4 frames

**Hints**
- `idle` is the canonical scale anchor for the player character. After concat, average frame bbox height defines the canonical body height; subsequent player actions (`attack`, `hurt`, `die`) re-scale to within `[0.92, 1.08]` of this canonical height — see [spec/art/sprite.md](../../.vibegame/spec/art/sprite.md) "Cross-action scale gate".
- The "75-85% cell height + same head-top y + same feet-bottom y" clauses are the answer to a recurring failure mode: when characters are painted at varying sizes per cell, scaling to canonical produces blurry upscales and inconsistent feet baselines across actions.

### player_attack

- prompt
  ```
  A horizontal sprite sheet of 4 sword-attack animation frames of the SAME character on pure flat magenta (#FF00FF) background. The 4 frames are arranged in a SINGLE HORIZONTAL ROW (exactly 1 row x 4 columns).

  CRITICAL SIZING: Each character occupies 75-85 PERCENT of the cell HEIGHT (the character is TALL — head near the top of the cell, feet at the very bottom of the cell). The cell is taller than wide; treat each cell as a portrait booth holding a full-bodied standing figure. Cells are equal-sized.

  GAP BETWEEN FRAMES: There must be a clear strip of pure magenta background (at least 60 px) between every pair of adjacent frames. NO body part, NO sword blade, NO slash arc may cross the gap. The slash arc in Frame 2 (strike_apex) must be SHORT and DIAGONAL (a brief slash, not a wide horizontal sweep) so it stays inside its own cell.

  Character: a slender young woman with short silver-white bob hair, fair skin, sleeveless black cropped tank top, black tactical shorts, tall black combat boots. She wields a glowing thick violet/magenta ENERGY longsword (saturated glowing energy blade, NOT a thin steel katana) in her right hand. Same character identity as the project reference image.

  4-frame right-hand sword attack, facing RIGHT. Camera stays the same (side view, ground line at very bottom of each cell, both feet planted on the cell-bottom baseline). The CHARACTER'S BODY HEIGHT remains roughly constant across all 4 frames — the character does NOT crouch or shrink. Pose changes are in the ARMS/SWORD only:

  - Frame 1 of 4 (windup_peak): standing upright, sword fully drawn back over right shoulder, body straight (NOT crouched), feet shoulder-width apart, free hand forward for balance
  - Frame 2 of 4 (strike_apex): standing upright, sword extending forward-right with a SHORT diagonal slash trail (the trail is a short crescent right in front of the character, NOT a long horizontal arc), body slightly twisted, feet still planted
  - Frame 3 of 4 (follow_through): standing upright, sword fully extended forward-right, body slightly leaned forward, no trail or only faint sparks at sword tip
  - Frame 4 of 4 (recovery): standing upright, sword lowered to right side, body neutral

  Style: painterly stylized digital illustration matching the project reference image, soft cinematic lighting, deep blacks in clothing, rim light on hair and shoulders, glowing violet energy blade highlights. Cohesive character identity across all 4 frames — same face, hairstyle, outfit, body proportions, scale. CRITICALLY: same FOOT BASELINE at the very bottom of each cell + same head-top y position (character body height constant; only sword arm position changes).

  Hard requirements:
  - EXACTLY 4 frames, EXACTLY 1 row x 4 columns horizontal layout
  - Pure flat magenta (#FF00FF) background, uniform
  - Each character is TALL (75-85% of cell height), full body from head to boots, feet planted at the very bottom of each cell
  - All 4 characters share the same head-top y and the same feet-bottom y (uniform body height across frames)
  - 60+ px clear magenta gap between adjacent frames
  - Slash arc in Frame 2 is a SHORT diagonal crescent contained in front of the character, NOT a long horizontal sweep
  - No body/sword/arc crosses into adjacent cells
  - Sword is a THICK glowing violet/magenta ENERGY BLADE (saturated, soft glow halo), NOT a thin steel katana
  - Energy glow uses violet + cyan, not pure #FF00FF
  - No text, labels, panel borders, UI, speech bubbles
  - Character faces RIGHT in every frame
  ```
- layout: 1×4 horizontal strip, 4 frames

**Hints**
- The "slash arc must be SHORT and DIAGONAL, not a wide horizontal sweep" clause is the answer to a major bleed failure mode: a wide horizontal sweep extends into the next cell. After cut, the bleed appears as a disconnected component near the adjacent character. Mitigate with a small-distance fragment filter (e.g. scipy distance-transform 5 px) that drops floating particles unconnected to the character.

### player_hurt

- prompt
  ```
  A horizontal sprite sheet of 2 hurt-reaction frames of the SAME character, evenly spaced left-to-right with a CLEAR strip of pure magenta (#FF00FF) background between the two frames. Pure magenta background everywhere outside the character.

  Character: a slender young woman with short silver-white bob hair, pale skin, wearing a sleeveless black cropped tank top, black tactical shorts, tall black combat boots. She holds a glowing violet energy longsword in her right hand. Cyberpunk near-future aesthetic.

  2 frames of a damage-taken reaction, facing RIGHT (taking hit from the right):
  - Frame 1 (impact): body recoiling backward (leaning left, away from the impact direction), head jerked back, face winced in pain, sword arm flung outward to balance, soft red impact flash on the chest/torso area, dust kicked up at feet
  - Frame 2 (stagger back): one step back on left foot, hunched slightly, free hand clutching torso, sword lowered, pained expression

  Style: painterly stylized digital illustration matching project style, dramatic cinematic lighting, deep blacks in clothing, subtle red rim on the hit point, cohesive character identity across both frames: same face, same hair, same outfit, same body proportions, same character height.

  Hard requirements:
  - Pure flat magenta (#FF00FF) background, completely uniform
  - Exactly 2 frames in a single horizontal row (1 row x 2 columns)
  - Equal-sized cells with clear magenta gap between them
  - Character body must NOT touch the other frame; clear magenta strip between
  - Character faces RIGHT in both frames
  - Feet roughly on the same baseline across both frames
  - Character occupies roughly 70-80 percent of cell height
  - No text, no labels, no panel borders, no UI, no speech bubbles
  - Hit flash uses red-orange, not magenta, so it can be chroma-keyed cleanly
  ```
- layout: 1×2 horizontal strip, 2 frames

### player_die

- prompt
  ```
  A horizontal sprite sheet of 4 death animation frames of the SAME character, evenly spaced left-to-right with a CLEAR strip of pure magenta (#FF00FF) background between every two adjacent frames. Pure magenta background everywhere outside the character.

  Character: a slender young woman with short silver-white bob hair, pale skin, wearing a sleeveless black cropped tank top, black tactical shorts, tall black combat boots. She wields a glowing violet energy longsword in her right hand. Cyberpunk near-future aesthetic.

  4 frames of a defeated/dying sequence, character body oriented toward RIGHT (then collapsing). Camera angle stays the same across all frames (side view, ground line at bottom of cell):
  - Frame 1 (stagger): legs buckling, sword arm dropping, head bowed, body tilting forward, defeat starting
  - Frame 2 (falling): knees on the ground, torso pitching forward, sword tip touching ground, free hand reaching out to brace, expression weak
  - Frame 3 (collapse): body fully sagged onto one side, lying mostly horizontal on the ground facing right, sword fallen beside her, hair fanned out, eyes closed, sword glow dimming
  - Frame 4 (final rest): lying on ground, sword glow fully dimmed to faint embers, dust settled, motionless, slightly more transparent / desaturated to show fading life

  Style: painterly stylized digital illustration matching project style, low-key cinematic lighting, deep blacks in clothing, soft cool ambient light on her skin and hair, cohesive character identity across all 4 frames: same face, same hair, same outfit, same body proportions, same overall scale.

  Hard requirements:
  - Pure flat magenta (#FF00FF) background, completely uniform
  - Exactly 4 frames in a single horizontal row (1 row x 4 columns)
  - Equal-sized cells with clear magenta gap between adjacent frames
  - Character body + sword must NOT cross into adjacent cells; clear magenta strip between
  - Same ground-line baseline across all 4 frames (use the bottom of each cell as the ground)
  - Character occupies roughly 70-85 percent of cell width when lying down
  - No text, no labels, no panel borders, no UI, no speech bubbles
  - All glow uses violet + cyan, not pure magenta
  ```
- layout: 1×4 horizontal strip, 4 frames

**Hints**
- `die` is the only player action where the body bbox height naturally shrinks across the sequence (standing → lying); the cross-action scale gate uses the FIRST frame (standing stagger) to compute the scale ratio, not the average. The trailing lying-down frames are pose-natural and stay shorter after scaling.
- `onFinish: hold` — the engine should hold the last frame after the OneShot plays, not transition back to idle (character is dead).

## Boss

### enemy_idle

- prompt
  ```
  A horizontal sprite sheet of 4 idle-pose frames of the SAME hulking heavy-armor villain on a pure magenta (#FF00FF) background. CRITICAL: between EVERY pair of adjacent frames there must be a WIDE EMPTY MAGENTA GAP at least 80 pixels wide where NO subject pixels exist — no shadow, no spilled hammer corner, no extended arm, NOTHING. Also leave a thick magenta margin (about 60 px) at the LEFT edge of frame 1 and the RIGHT edge of frame 4. Background everywhere outside the character is pure flat magenta, no gradient, no scene, no shadow on background.

  Character `<boss>`: a massive, intimidating heavy-armor brute, much larger and bulkier than a normal human, wearing plated cyberpunk steel armor with teal/blue-green and dark steel-gray panels and exposed mechanical joints, a brutal helmeted face mask with glowing cyan visor slits, broad armored shoulders. He grips a HUGE square-headed industrial sledgehammer with BOTH hands, hammer head is a massive cube of dark metal with worn edges, handle thick and long. The hammer rests with its head touching the ground beside him during idle.

  ALL 4 frames are a heavy menacing idle stance facing LEFT (hammer head rests on the ground on the LEFT side of the character, hammer handle gripped in both hands). Subtle breathing/swaying motion:
  - Frame 1: chest raised slightly (inhale), shoulders broad, hammer head still
  - Frame 2: settling, shoulders dropping
  - Frame 3: chest lowered (exhale), shoulders low, slight head tilt
  - Frame 4: rising back toward neutral, hammer hand adjusting grip

  Style: painterly stylized digital illustration matching the project reference image, dramatic cinematic rim light from above, teal-cyan glow on visor and armor seams, deep blacks in armor joints, heavy oppressive silhouette, cohesive character identity across all 4 frames: identical helmet, identical armor design and color palette, identical hammer, identical body proportions and overall size.

  Hard requirements:
  - Pure flat magenta (#FF00FF) background, completely uniform, no gradient
  - Exactly 4 frames in a single horizontal row (1 row x 4 columns)
  - WIDE clear magenta GAP (>=80 px) between every pair of adjacent frames; the gap is just pure magenta, no subject overflow
  - Comfortable magenta margin (>=60 px) at the LEFT of frame 1 and RIGHT of frame 4
  - Character body + hammer + any glow halo must be fully contained inside its own frame's center area with breathing room — NO touching the next frame's region, NO touching cell boundary
  - Character faces LEFT in EVERY frame
  - Same vertical baseline (feet aligned) and same character height in every frame
  - Character body occupies roughly 70 percent of its cell (smaller so gap is generous)
  - No text, no labels, no panel borders, no UI, no speech bubbles, no grid lines drawn
  - No pure magenta inside the character; cyan/teal glow, gray metal, black joints
  ```
- layout: 1×4 horizontal strip, 4 frames

**Hints**
- `enemy_idle` is the canonical scale anchor for the boss. Boss cross-character scale parity vs `player_idle`: aim for similar body height (~480 px) at source pixels so engine renders both at 1:1 without per-node scale tweaks. If the boss should read as visibly bulkier (per design reference), keep height parity and let silhouette mass do the work — DO NOT make the boss source pixels taller.
- The "Character body occupies roughly 70 percent of its cell" clause is intentional under-sizing so the 80-px-wide gap is achievable. After cut, a single scale upcast (≈1.85×) lands the body at the canonical ≈480 px.
- **Sprite-bleed cleanup (idle + taunt are the high-risk sheets).** A big two-handed weapon held low/wide (the hammer) and a wide raised-arm taunt pose both bleed small fragments into the adjacent cell even with an 80-px prompt gap. After cut, run a per-frame connected-component filter: keep only the largest component (the body + its own weapon are one connected blob, ~100-145k px), drop isolated edge fragments (<5k px, centroid near x=0 or x=w). Zero their alpha in place — manifest bboxes stay valid, no re-cut needed. This is post-processing; see the contract `#### Artist` chapter, not a prompt change.

### enemy_attack

- prompt
  ```
  A horizontal sprite sheet of 5 hammer-attack animation frames of the SAME hulking heavy-armor villain on a pure magenta (#FF00FF) background, evenly spaced left-to-right with CLEAR magenta strips between every pair of adjacent frames. Pure flat magenta everywhere outside the character; no gradient, no scene.

  Character `<boss>`: a massive heavy-armor brute, much larger than a normal human, wearing plated cyberpunk steel armor with teal/blue-green and dark steel-gray panels, helmet with cyan visor slits, broad armored shoulders. He grips a HUGE square-headed industrial sledgehammer with BOTH hands.

  5 frames of a 3-phase overhead hammer smash facing LEFT (windup -> strike -> recovery):
  - Frame 1 (windup A): body coiled, hammer drawn back over right shoulder, weight shifted onto back foot, leaning slightly back
  - Frame 2 (windup peak): hammer fully raised straight up overhead with both hands, body fully extended upward, ready to slam down to the LEFT, intimidating pose
  - Frame 3 (strike apex): hammer SLAMMING DOWN to the LEFT in front of him, peak speed, hammer head near ground level, body bent forward, shockwave / dust cloud puff at impact point on the ground to the LEFT, motion-blur arc on the hammer head, cyan energy crackle at impact
  - Frame 4 (follow-through): hammer head resting on the ground after impact to the LEFT, body bent forward over it, dust still drifting up
  - Frame 5 (recovery): straightening back up, lifting hammer slightly off the ground, returning toward neutral stance

  Style: painterly stylized digital illustration matching the project reference image, dramatic cinematic rim light from above, teal-cyan glow on visor and armor seams, deep blacks in armor joints, heavy oppressive silhouette, cohesive character identity across all 5 frames: identical helmet, identical armor design and color palette, identical hammer, identical body proportions and scale.

  Hard requirements:
  - Pure flat magenta (#FF00FF) background, completely uniform
  - Exactly 5 frames in a single horizontal row (1 row x 5 columns)
  - Equal-sized cells, evenly spaced with clear magenta gap between adjacent frames
  - Character body + hammer + impact dust must NOT cross into adjacent cells; clear magenta strip between every pair
  - Character faces LEFT in EVERY frame (hammer swings down-LEFT, dust kicks up to the LEFT)
  - Feet roughly on the same baseline across frames
  - Character occupies roughly 80-95 percent of cell height
  - No text, no labels, no panel borders, no UI, no speech bubbles
  - Glow uses cyan/teal, dust uses warm gray; no magenta inside the character or effects
  ```
- layout: 1×5 horizontal strip, 5 frames

**Hints**
- `strike_apex` (frame 3) is the canonical hit-event frame for the animator FSM: the programmer ties the `dealDamage` event to this frame index.
- 3-phase attack (`windup` / `strike` / `recovery`) → 5-frame breakdown is standard for a single heavy attack. Lighter attacks can use 4 frames (drop one windup phase).

### enemy_taunt

- prompt
  ```
  A horizontal sprite sheet of 3 taunt/roar animation frames of the SAME hulking heavy-armor villain on a pure magenta (#FF00FF) background. CRITICAL: between EVERY pair of adjacent frames there must be a WIDE EMPTY MAGENTA GAP at least 100 pixels wide where NO subject pixels exist — no shadow, no raised hand crossing over, no hammer extending into next cell, NOTHING. Also leave a thick magenta margin (about 60 px) at the LEFT edge of frame 1 and the RIGHT edge of frame 3. Background everywhere outside the character is pure flat magenta.

  Character `<boss>`: a massive heavy-armor brute, wearing plated cyberpunk steel armor with teal/blue-green and dark steel-gray panels, helmet with cyan visor slits, broad armored shoulders. He grips a HUGE square-headed industrial sledgehammer with BOTH hands (or one hand during the taunt).

  3 frames of an arrogant intimidation taunt (NOT an attack), facing LEFT. The hammer is held casually, NOT swung:
  - Frame 1 (chest puff): body straightening up, chest pushed forward, shoulders flexed back, hammer head dragged contemptuously up off the ground in one hand on his left side, intimidating challenge pose
  - Frame 2 (roar peak): full taunt: head thrown back slightly, free hand raised palm-up beckoning ("come on!"), hammer hoisted partly up to the side, visor glowing brighter cyan, body language pure arrogance and menace. The raised hand and hammer MUST stay inside this cell — no extending into adjacent cells
  - Frame 3 (settling): coming back down toward idle, hammer lowering back toward ground, shoulders dropping but visor still bright cyan, still puffed up

  Style: painterly stylized digital illustration matching the project reference image, dramatic cinematic rim light from above, intense teal-cyan glow on visor and armor seams (BRIGHTER on the taunt peak frame), deep blacks in armor joints, heavy oppressive silhouette, cohesive character identity across all 3 frames.

  Hard requirements:
  - Pure flat magenta (#FF00FF) background, completely uniform, no gradient
  - Exactly 3 frames in a single horizontal row (1 row x 3 columns)
  - WIDE clear magenta GAP (>=100 px) between every pair of adjacent frames; pure magenta, no subject overflow whatsoever
  - Comfortable magenta margin (>=60 px) at the LEFT of frame 1 and RIGHT of frame 3
  - Character body + hammer + raised hand + any glow halo must be fully contained inside its own frame's center area with generous breathing room — do NOT touch the next frame's region, do NOT touch the cell boundary
  - Character faces LEFT in EVERY frame
  - Feet roughly on the same baseline across frames
  - Character occupies roughly 65 percent of its cell height (smaller so gap is generous)
  - No text, no labels, no panel borders, no UI, no speech bubbles
  - Glow uses cyan/teal only; no magenta inside the character
  - This is a TAUNT (intimidation), NOT a hammer swing
  ```
- layout: 1×3 horizontal strip, 3 frames

**Hints**
- The taunt is a NON-attack action: enemy plays it after `END TURN` to signal intent, then transitions to the queued attack/defense action on `onFinish`. Required for boss-class enemies in deckbuilder pacing — without taunt the boss feels like a vending machine of damage.

### enemy_die

- prompt
  ```
  A horizontal sprite sheet of 4 death animation frames of the SAME hulking heavy-armor villain on a pure magenta (#FF00FF) background, evenly spaced left-to-right with CLEAR magenta strips between every pair of adjacent frames. Pure flat magenta everywhere outside the character; no gradient, no scene.

  Character `<boss>`: a massive heavy-armor brute, much larger than a normal human, wearing plated cyberpunk steel armor with teal/blue-green and dark steel-gray panels, helmet with cyan visor slits, broad armored shoulders. He grips a HUGE square-headed industrial sledgehammer with BOTH hands.

  4 frames of a defeated/dying sequence, character body oriented toward LEFT (then collapsing). Camera angle stays the same across all frames (side view, ground line at bottom of cell):
  - Frame 1 (stagger): heavy stagger backward (to the right of frame, since he faces left), hammer arm dropping, head tilted, visor still glowing but flickering, armor sparking at the joints, defeat starting
  - Frame 2 (knee-drop): one knee hitting the ground, hammer falling out of one hand toward the LEFT-front, body pitching forward, free arm reaching out to brace
  - Frame 3 (collapse): body fully sagged onto the ground on his side facing LEFT, hammer fallen on the ground in front of him, helmet visor barely glowing, smoke and sparks rising from armor seams
  - Frame 4 (final rest): lying motionless on ground, visor fully dark, faint smoke wisp, dust settled, slight desaturation to show death

  Style: painterly stylized digital illustration matching the project reference image, low-key cinematic lighting, deep blacks in armor joints, cool ambient light, fading cyan glow on visor across the sequence (bright -> flicker -> dim -> off), cohesive character identity across all 4 frames: identical helmet, identical armor design and color palette, identical hammer, identical body proportions and scale.

  Hard requirements:
  - Pure flat magenta (#FF00FF) background, completely uniform
  - Exactly 4 frames in a single horizontal row (1 row x 4 columns)
  - Equal-sized cells with clear magenta gap between adjacent frames
  - Character body + hammer + smoke must NOT cross into adjacent cells; clear magenta strip between every pair
  - Same ground-line baseline across all 4 frames (bottom of each cell is the ground)
  - Character occupies roughly 80-95 percent of cell width when lying down
  - No text, no labels, no panel borders, no UI, no speech bubbles
  - Glow uses cyan only, never pure magenta
  ```
- layout: 1×4 horizontal strip, 4 frames

## Cards

### cards_12

- prompt
  ```
  A single image containing 12 cyberpunk card illustrations arranged in a 6-column x 2-row grid on a pure magenta (#FF00FF) background. Each card is a vertical (portrait) rectangle. CLEAR magenta strips between every pair of adjacent cards so cards do NOT touch. No grid lines, no separators, no borders drawn between cells — just plain magenta gap.

  Style: ALL 12 cards share IDENTICAL painterly stylized digital illustration style, matching the project reference image. High-contrast cinematic painterly, magenta + cyan neon palette, dramatic rim light. NOT pixel art. Each card has the same visual treatment, the same border/edge style, the same painterly finish — they must look like a single set.

  Per-card structure (applies to ALL 12 cards identically):
  - Card is a vertical rectangle with a thin dark inner border, painted edges
  - TOP-LEFT corner of the card: a SOLID YELLOW (warm gold) CIRCULAR BADGE about 18 percent of card width in diameter, with a dark navy/black numeric digit in the center. The badge has a slight darker outer ring. The digit is the card's energy cost. The badge is INSIDE the card art (NOT floating outside), painted into the illustration.
  - The REST of the card below/around the badge is the card's main illustration depicting the card's effect (described per card below)
  - NO text anywhere on the card except the cost digit inside the yellow circle. NO card name, NO type label, NO description text — those will be added separately later

  Card grid (left-to-right, top-to-bottom). All artworks depict effects involving the SAME silver-white short-bob hair young woman with magenta/violet energy sword from the reference image — same character identity throughout. Each card shows its visual concept clearly:

  ROW 1 (top row, left to right):
  1. STRIKE (cost 1): wide horizontal sweep of magenta/violet energy sword, glowing slash arc dominating the frame, sparks flying right
  2. DEFLECT (cost 1): player's sword raised vertically as a guard, large translucent cyan hexagonal energy shield projected forward, magenta sparks bouncing off
  3. BASH (cost 2): sword slammed down into the ground, ground-impact crater radiating magenta cracks and violet shockwave rings
  4. TWIN STRIKE (cost 1): two crossed slash arcs of violet energy forming an X across the frame, doubled afterimage of the sword swing
  5. HEAVY BLOW (cost 2): player charging up a massive overhead strike, sword glowing with concentrated violet plasma, intense light burst on the blade
  6. OVERLOAD (cost 3): sword OVER-charged with chaotic violet-magenta energy, electric arcs bursting in every direction off the blade, plasma explosion around the sword

  ROW 2 (bottom row, left to right):
  7. SCRAMBLE (cost 1): glowing orange targeting reticle/cross-hair lock overlaid on a fractured enemy silhouette, orange weakness markers superimposed
  8. IRON CURTAIN (cost 2): tall translucent cyan energy wall rising out of the ground around the player, full-body protective barrier, light beams shooting up
  9. PHASE SHIFT (cost 1): two semi-transparent ghost images of the player offset to either side, ethereal cyan-violet glow, motion-trail effect, one image deflecting, one drawing a card
  10. NEURAL LINK (cost 1): glowing cyan data-flow lines streaming from player's forehead/temple out toward a stack of cards floating beside her, digital particles
  11. OVERCLOCK (cost 2): player's body lit from within, cyan/violet glowing circuit-line patterns spreading across her skin and clothing, energy aura
  12. REFLEX GRID (cost 1): a cyan-green hexagonal grid mesh wrapping around player's body like a force-field net, geometric scan pattern lit on her silhouette

  Hard requirements:
  - Pure flat magenta (#FF00FF) background, completely uniform, no gradient
  - Exactly 12 cards in a 6-column x 2-row layout (6 across, 2 down)
  - Each card is a portrait rectangle, all 12 the SAME size and orientation, evenly spaced with clear magenta gaps
  - No card touches another; clear magenta strip between every pair
  - No grid lines or separator lines drawn anywhere — just magenta background between cards
  - Cost badge: yellow circle TOP-LEFT corner INSIDE each card, with the cost digit clearly visible
  - No card text (no card name, no type, no description) — only the cost digit in the badge
  - The SAME silver-white short-hair young woman with violet energy sword appears consistently across all illustrations
  - All 12 cards must read clearly as their described concept; viewer should be able to tell STRIKE from DEFLECT etc. at a glance
  ```
- layout: 6-column × 2-row card sheet, 12 portrait cards, generated at 3840×2160 for per-card detail

**Hints**
- One raw → 12 final manifest sprites under one `cards` atlas. The cut pipeline names each component by its semantic card id (`strike`, `deflect`, ...) rather than the auto-generated `c0..c11`. The card name / type / description text is CSS overlay at runtime — never bake it into the art.
- The cost badge is BURNED IN to the art (not a separate overlay sprite). This is the deckbuilder pattern — the cost digit is part of the card identity so it can't drift out of sync with effect data. The runtime trusts the burnt-in digit; the CSS overlay only renders name/type/description.
- The magenta gap between cards has an unusual color shift away from pure (#FF00FF) — closer to (~232, 39, 225) — so chroma-key tolerance must go higher (`-t 60` instead of the usual 30) for clean separation.

## UI

### hud_icons

- prompt
  ```
  A single image containing 9 cyberpunk HUD icons arranged in a 3-column x 3-row grid on a pure magenta (#FF00FF) background. CLEAR magenta strips between every pair of adjacent icons so icons do NOT touch. No grid lines, no separator lines, no borders drawn between cells — just plain magenta gaps.

  Style: ALL 9 icons share IDENTICAL flat-painterly stylized illustration style with sharp clean edges, slight inner glow, subtle dark outer outline, matching the project reference image. Each icon is centered in its cell, fills about 70-80 percent of the cell, has a clear silhouette readable as a small HUD element. Subtle painterly shading, NOT pixel art.

  Icon list (left-to-right, top-to-bottom):

  ROW 1:
  1. HEART_HP: a glossy red valentine heart icon with a soft inner pink highlight, slight cyan rim light, dark red outline. Clean iconic heart shape (the kind used for HP bars).
  2. COIN_EDS: a gold/yellow circular coin viewed straight-on, with a stylized "EDS" three-letter mark embossed in the center, polished metallic gold highlight on the upper-left edge, dark gold outer ring. Slight glow.
  3. INTENT_ATTACK: a clean stylized straight sword icon (vertical, point up) in steel-gray with a magenta glowing blade edge, simple dark grip at bottom, slight outer glow. Used to indicate an enemy intends to attack.

  ROW 2:
  4. INTENT_DEFENSE: a stylized cyan-blue kite shield icon (vertical), simple geometric shield shape with a darker central boss, cyan rim glow, slight outer dark outline. Used to indicate an enemy intends to defend.
  5. ENERGY_CRYSTAL: a faceted vertical cyan-blue energy crystal pointing up, glowing core, multiple flat facets reflecting light, slight magenta secondary glow, used as the energy/stamina icon.
  6. STATUS_VULNERABLE: a square debuff icon: an orange-yellow rounded square plaque with cracking lines radiating across it, a darker orange border, slight inner glow. Looks like cracked / fractured armor — signifies Vulnerable.

  ROW 3:
  7. STATUS_BLOCK: a square buff icon: a blue rounded square plaque with a small white shield emblem in the center, cyan rim glow, darker blue border. Signifies Block.
  8. PORTRAIT_PLAYER: a circular portrait icon of the silver-white short-hair young woman from the reference image — head-and-shoulders, looking forward, neutral expression, magenta rim light on hair, fits inside a clean circle with a subtle dark circular border. Painted style, recognizable as the same player character.
  9. SETTINGS_GEAR: a clean stylized gear/cog icon, dark steel-gray with cyan inner glow, simple geometric teeth, slight outer dark outline. Centered.

  Hard requirements:
  - Pure flat magenta (#FF00FF) background, completely uniform, no gradient
  - Exactly 9 icons in a 3x3 grid
  - Each icon centered in its cell, evenly spaced with clear magenta gaps
  - No icon touches another; clear magenta strip between every pair
  - No grid lines, no separator lines, no borders drawn between cells
  - No text on icons except the "EDS" letters on the coin
  - All icons same style, similar visual weight, look like one cohesive HUD icon set
  - No magenta pure-tone color used inside any icon (use red/orange/yellow/cyan/blue/gray)
  - Each icon should be instantly recognizable at small HUD size
  ```
- layout: 3×3 grid, 9 portrait icons

**Hints**
- One raw → 9 final manifest sprites under one `hud_icons` atlas. Each cell gets a semantic name (`heart_hp`, `coin_eds`, `intent_attack`, `intent_defense`, `energy_crystal`, `status_vulnerable`, `status_block`, `portrait_player`, `settings_gear`) instead of auto `c0..c8`.
- HUD icons render via DOM `<img>` background — the runtime extracts each frame as a PNG data URL using the engine's `extractFrameDataUrl(scene, 'hud_icons', frameKey, displayHeight)` helper.
- Like `cards`, the gap color shifts from pure (#FF00FF) to (~232, 39, 225). Use `-t 60` chroma-key tolerance for clean separation.

## FX

### vfx_4

- prompt
  ```
  A single image containing 4 cyberpunk VFX sprite sheets arranged in a 1-column x 4-row layout on a pure magenta (#FF00FF) background. Each row contains a horizontal sequence of 4 frames of one VFX. CLEAR wide magenta strips between every pair of adjacent frames in the same row, and between the rows.

  Style: painterly stylized digital illustration, glowing energy particles, dramatic neon glow, matches the project reference image style. NOT pixel art. Each VFX reads as a short transient burst that an engine can play frame-by-frame on top of game characters.

  VFX list (top to bottom):

  ROW 1 — HIT_IMPACT (4 frames): a quick bright impact flash burst at a point in mid-air. Magenta-violet color with white-hot core.
  - Frame 1: small bright white-hot core with thin radial spike streaks just forming
  - Frame 2: BIG burst peak — bright white-hot center with magenta-violet radial rays bursting outward in a star pattern, sharp glow
  - Frame 3: rays fading, core dimming, debris sparks scattering outward
  - Frame 4: faint residual magenta glow halo with a few dim sparks

  ROW 2 — BLOCK_BREAK (4 frames): cyan energy shield fragmenting into pieces. Cyan-teal color.
  - Frame 1: small cyan hexagonal shield piece glowing, intact
  - Frame 2: shield fragments mid-air, hexagonal cyan pieces spreading outward, cracks visible
  - Frame 3: fragments further spread, cyan glow dimming, fragments tumbling
  - Frame 4: faint cyan residual glow with a few dissipating dust particles

  ROW 3 — VULNERABLE_APPLY (4 frames): orange-yellow cracking pattern applied to a target. Orange-red color.
  - Frame 1: small orange crack mark forming at a center point
  - Frame 2: cracks spreading outward into a radial fracture pattern, brighter orange glow
  - Frame 3: cracks fully expanded into a wide jagged orange-red rune-like fracture, intense glow
  - Frame 4: cracks settling into a static orange debuff mark with steady dim glow

  ROW 4 — CARD_TRAIL (4 frames): a card swooshing forward leaving a glowing energy trail. Cyan-to-violet gradient color.
  - Frame 1: short cyan streak with a small card-shape head on the right end
  - Frame 2: longer cyan-violet glowing trail with the card head moved further right, energy particles
  - Frame 3: long curving cyan-violet trail across most of the frame, card head at far right, particle sparkle
  - Frame 4: card has hit target (right edge), bright flash, trail dispersing into glowing motes

  Hard requirements:
  - Pure flat magenta (#FF00FF) background, completely uniform, no gradient
  - Exactly 4 rows x 4 columns = 16 frames total
  - Each row contains 4 frames of one VFX, evenly spaced
  - CLEAR magenta strips between every pair of adjacent frames in same row, AND between rows
  - No VFX particle reaches into adjacent cells
  - No text, no labels, no panel borders, no UI
  - All frames within one row at the SAME scale and position so they can be cleanly extracted as a frame sequence
  - No pure magenta color used inside any VFX (use white-hot, violet, cyan, orange-red)
  ```
- layout: 4-row × 4-column matrix (one VFX per row), generated at 1536×1024

**Hints**
- One raw → 4 separate final atlases (`vfx_hit_impact`, `vfx_block_break`, `vfx_vulnerable_apply`, `vfx_card_trail`), each a single-row 4-frame sequence with `pivot: [0.5, 0.5]` for centered spawn on a target's body. Auto-cut from this raw is unreliable (sparkle particles fragment into many connected components); use grid-slice at uniform 4×4 cell boundaries with per-cell auto-bbox-crop instead.
- VFX play OneShot with `frameRate ≈ 12-18 fps` (full burst plays in ~0.25-0.33 s), destroyed on `onFinish`. Centered pivot avoids the silent-bug pattern where a feet-anchored VFX floats upward by half its height.
