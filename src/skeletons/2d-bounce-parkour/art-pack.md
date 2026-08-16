# Art Pack — 2d-bounce-parkour

Reusable raw-asset list for the side-view rhythm-bounce platformer sub-genre (stay airborne, stomp-pop floating balloons, bounce all the way to the goal). One player character hops a row of floating balloons from a start platform to a goal platform. Prompts assume a single pixel-art style anchor image (`style_anchor.png`) passed as `-i` on every subsequent generation. Every `### <raw-asset>` heading is one `vibegame art gen image` call recovered verbatim from `.vibegame/logs/imagegen.jsonl`.

Model used throughout: `gpt-image-2` (no native transparent output — every marker-background sheet goes through chroma-key + cut + concat).

## Reference

### style_anchor

- prompt
  ```
  # Project style anchor v6 — Aniya Balloon Parkour (pixel art, Celeste school, name-only character)

  Generate ONE 16:9 image that looks exactly like a screenshot of the initial viewport of a chunky pixel-art 2D platformer game on Steam — Celeste / Owlboy / Hyper Light Drifter school of pixel art. NOT smooth illustration. NOT anime cel-shading. NOT vector flat-art. NOT painted concept art. **True crunchy pixel art** with discrete pixels, no anti-aliasing softening, limited palette per sprite.

  ## Pixel art rendering style (project canon)

  - **Retro pixel art, 32-bit pixel game look, Celeste school**. Each foreground sprite reads as hand-pixeled at small native resolution (sprites ~32-64 pixels tall in native pixel coordinates), displayed scaled up with nearest-neighbor crispness.
  - **Chunky pixel blocks** are clearly visible. Pixel edges are sharp and stair-stepped, NEVER smoothed with anti-aliasing or sub-pixel blends.
  - **Pixel outlines**: each foreground sprite has a 1-pixel dark outline along its silhouette (Celeste-style selective outlining — outline can lighten or disappear on shadowed edges, but always crisp pixels, never a smooth vector line).
  - **Limited palette per sprite** (~4-8 colors). Solid pixel blocks of base color + darker shadow color + brighter highlight color. No gradient fills inside pixels. No painterly brushwork.
  - **Background is pixel-painted**: pixel sky gradient with visible color bands or dithering, pixel-block clouds, distant hills as pure-color pixel silhouettes.
  - Composition: strict 2D orthogonal side view (no 3/4, no isometric, no perspective). 16:9 horizontal full game-screen layout.

  ## Character

  The character standing on the start platform is **Anya Forger from Spy x Family** — the well-known anime/manga character. Render her in pixel-art form. Keep her instantly recognizable as Anya Forger. She is the player character of this game. Pose: standing upright (or in a tiny ready-to-jump crouch) on the right edge of the start platform, facing right. She occupies roughly **12-15% of total image height** — small chunky-pixel character like Madeline in Celeste, NOT the visual focus of the composition.

  ## Composition (initial viewport — no goal in view)

  - **Left ~1/5 of frame**: start platform anchored to the lower-left, extending off the left screen edge. Two pixel layers:
    - top: a band of pixel grass — bright green base with darker green pixel "blade" specks along the top edge in a 2-3 pixel strip.
    - body: warm brown pixel earth block with a couple of slightly lighter brown rounded pixel "pebble" clusters embedded. Crisp dark pixel outline along the visible top, exposed right edge, and bottom edge.
  - **Anya Forger** stands on the right edge of this platform, small (~12-15% screen height), facing right.
  - **Right ~4/5 of frame**: 7 floating balloons in a roughly horizontal row with **subtle vertical stagger**. The leftmost balloon sits a short distance to the right of the start platform; the **rightmost balloon is partially clipped by the right screen edge**, clearly suggesting more balloons continue off-screen.
  - **Do NOT draw any end platform, goal flag, finish line, signpost, star, or destination marker anywhere in the image.**

  ## Balloons (7 total, pixel-art rendered)

  - Each balloon is a small chunky pixel sprite: classic round teardrop balloon silhouette with a small pixel knot at the bottom and a 1-2 pixel pixel string trailing straight down a short distance. Pixel outlined.
  - Each balloon fill = one flat saturated pixel color + one darker pixel shadow crescent on the lower-right + one pure-white pixel highlight rectangle/oval on the upper-left.
  - Left-to-right variant order: **red (standard), blue (~20% larger), red, gold (~20% smaller), red, blue (~20% larger), red (partially clipped at right edge)**.
  - Standard red balloon size in pixel coordinates roughly equal to Anya's body height (so balloons read as gameplay-significant objects).

  ## Background

  - **Sky**: pixel-art vertical gradient from lavender-blue at the top to soft peach-pink near the horizon. Visible pixel color bands stepping through 4-6 intermediate colors, OR pixel dithering (checkerboard pixel pattern) between adjacent bands. NOT a smooth photographic gradient.
  - **Pixel clouds**: 3 chunky cartoon pixel-art clouds in the upper sky. Each cloud is a rounded bumpy silhouette of pure white pixels with a 1-pixel light-gray bottom shadow row. Pixel-stepped silhouette.
  - **Distant pixel hills**: 1 or 2 layers of solid pixel-color rolling hill silhouettes near the bottom of the sky, behind the platform and behind the balloons. Each layer is a flat block of pixel color (back: dusty lavender; optional front: slightly darker lavender). No internal detail. No outlines. Smooth bumpy curves rendered in pixel stair-steps.

  ## Color guide

  - Red balloon: #E63A3A + shadow #B22A2A + white highlight
  - Blue balloon: #3A8FE6 + shadow #1F6BBA + white highlight
  - Gold balloon: #F5C04A + shadow #C99026 + white highlight
  - Grass top: #7BC36A + darker tufts #4F9A48
  - Earth body: #9C6A3C + lighter pebbles #C9925C
  - Sky top: #A8B4E8 lavender-blue
  - Sky horizon: #FFD8C2 peach-pink
  - Cloud fill: pure white; cloud shadow row: #D8DCE6 light gray
  - Back hill: #B7A8D6 dusty lavender; optional front hill: #9C8BC4
  - Foreground pixel outlines: #2A1F24 very dark warm brown / near-black

  (Anya's own palette: use her canonical Spy x Family appearance — do NOT improvise replacement colors for her hair / outfit.)

  ## Hard constraints

  - **MUST be pixel art** with crisp stair-stepped pixel edges. Do NOT smooth, antialias, or soften pixel edges. Do NOT render in smooth anime / vector / illustration / cel-shaded / painted style.
  - The character is **Anya Forger from Spy x Family** rendered as pixel art — keep her canonical recognizable look. Do NOT substitute a generic anime girl.
  - Do NOT include any end platform, goal flag, goal star, finish line, banner, signpost, arrow, or destination marker.
  - Do NOT include any text, captions, labels, watermark, signature, score numbers, HP bars, speech bubbles, UI overlays, instructional arrows, or game logo.
  - Do NOT include any character besides Anya. Do NOT include enemies, NPCs, coins, or any pickup props besides the 7 balloons.
  - Do NOT add motion blur, lens flare, bloom, depth-of-field blur, photographic noise, paper texture, or canvas texture.
  - Do NOT split into panels / cells / borders. One continuous game-screenshot frame.
  - The whole image must read as an actual screenshot from a chunky-pixel 2D platformer on Steam, NOT illustrated artwork.
  ```
- layout: single 16:9 in-game-viewport screenshot (2560x1440), opaque. NOT registered in the runtime manifest — pure style anchor, passed as `-i` on every subsequent generation.

**Hints**
- **Style-lock took 6 iterations. The two decisive learnings:**
  - **Medium switch**: v1-v4 prompted "hand-drawn cartoon anime / cel-shaded flat color" per an early GDD read; the user rejected all of them and re-anchored the GDD to Celeste-school pixel art. v5-v6 rewrote the whole rendering-style block to "true crunchy pixel art, discrete pixels, no anti-aliasing, limited palette, selective 1-px outline". Lock the medium from the GDD before generating anything, or the anchor gets thrown away.
  - **Name-only character beats hand-described character**: v5 hand-detailed Anya ("two upward triangular pink hair tufts, huge purple eyes, red bow, black uniform") to force her likeness — the model still drifted. v6 replaced the entire description with **"Anya Forger from Spy x Family — keep her canonical recognizable look, do NOT substitute a generic anime girl"** plus "use her canonical palette, do NOT improvise replacement colors" — the model's built-in likeness is stronger than any manual description. For any known-IP character, name it and forbid substitution; do not spend prompt budget describing appearance.
- The anchor is a **gameplay-viewport screenshot**, not a character sheet or mood board: one player at gameplay scale (~12-15% screen height, explicitly "NOT the visual focus"), the balloon row as the actual composition subject, and the goal deliberately excluded because it is off-screen in the real first frame. Composition mirrors the actual initial viewport.

## Background

Background is a **parallax stack**: each depth plane is one independently generated image layer so the engine can scroll them at different rates — an opaque full-canvas sky, a transparent cloud pair, and a transparent hill-strip pair. All three inherit palette from the style anchor. **Doctrine (user-locked): each parallax depth layer = one generated transparent layer, horizontally tileable; never a generated base with hand-drawn or code-drawn pixels added on top.** Every scrolling plane must tile horizontally. Full prompt recipe + role/packaging workflow: [`spec/contracts/parallax_background.md`](../../.vibegame/spec/contracts/parallax_background.md) `#### Artist`.

### bg_sky

- prompt
  ```
  # bg_sky — pixel-art morning sky background

  Generate a **single static background image** showing ONLY a clear morning sky gradient. Pixel art. NO marker background (this image IS the background — it has no transparency).

  This image will be drawn as the back-most layer of every gameplay scene. Clouds and hills are SEPARATE sprites layered on top by the engine — do NOT include them in this image.

  ## Required content
  - A full-canvas vertical pixel sky gradient covering the entire image.
  - **Top of the image**: lavender-blue (#A8B4E8).
  - **Bottom of the image**: soft peach-pink (#FFD8C2).
  - The gradient transitions through 4-6 visible intermediate color bands (e.g. #A8B4E8 → #B6B7E0 → #C5BAD8 → #D8C2CF → #ECC8C5 → #FFD8C2), with **subtle pixel-dithering checkerboard patterns** between adjacent bands to smooth the steps. The band edges and the dither pixels are clearly visible — this is pixel-art retro gradient style, NOT smooth photographic gradient.
  - Optional: a single thin horizontal pixel stripe of slightly warmer color (e.g. #FFC6A0) at the very bottom edge to suggest a sun-glow horizon line.

  ## Pixel-art style (inherit from reference image)
  - Chunky retro pixel art, Celeste school. Crisp stair-stepped pixel edges. NO anti-aliasing softening. NO smooth photographic gradient. Visible pixel color bands plus checkerboard dithering between them.
  - Use the SAME sky palette as the reference image (lavender-blue → peach-pink) but with no clouds or hills painted in.

  ## Hard negatives
  - Do NOT include clouds (clouds are a separate sprite asset).
  - Do NOT include hills, mountains, ground, platform, or any landscape silhouette.
  - Do NOT include any character, balloon, prop, or foreground element.
  - Do NOT include any text, watermark, signature, UI overlay, or text/letter shapes.
  - Do NOT make the background transparent — this image is fully opaque, edge-to-edge sky.
  - Do NOT smooth the gradient into a continuous photographic blend. Visible pixel bands + dither only.
  ```
- layout: single frame, opaque, full canvas (2560x1440), NO marker background. Skips chroma-key — the image IS the background.

**Hints**
- Pixel-art gradient must be prompted as **visible color bands + checkerboard dithering between bands**, explicitly forbidding "smooth photographic gradient". A plain `--size 2560x1440` gradient request otherwise comes back as a soft blend that clashes with the crunchy-pixel foreground.
- Author back-most layer content-free (no clouds/hills). Those ship as separate transparent parallax sprites so the engine can scroll them at different speeds.

### clouds

- prompt
  ```
  # clouds — 1x2 pixel-art sprite sheet (2 cloud variants for parallax)

  Generate a **1-row × 2-column grid sprite sheet (2 cells total)** of two cartoon pixel-cloud variants. Pixel art. Strict marker-color background.

  These are decorative parallax-layer clouds drawn on top of the sky background. They will have transparent backgrounds after chroma-key removal.

  ## The 2 cloud variants (left to right)
  1. **bg_cloud_a — small puffy cloud**. A round bumpy pixel cloud silhouette, 3-4 stacked bumps on top, flatter base. Filled with pure white pixels. A single row of light-gray (#D8DCE6) pixel shadow along the very bottom edge. 1-pixel medium-gray (#9AA3C0) outline along the upper bumps for clear silhouette readability (Celeste-style selective outline).
  2. **bg_cloud_b — larger stretched cloud**. A wider, more stretched-out pixel cloud silhouette, 5-6 bumps top and bottom irregularly distributed, more horizontal aspect. Same white fill + light-gray bottom shadow + medium-gray top outline as cloud_a — they form a matching pair.

  ## Sheet layout
  - Exactly **2 equal cells in one horizontal row (1x2)**.
  - No cell borders, no separator lines, no gutters — just marker background.
  - Same cell dimensions; each cloud is roughly centered in its cell.
  - Cloud_a fills ~40-50% of its cell, cloud_b fills ~60-70% of its cell (cloud_b is the bigger one). Both have plenty of marker margin around them.

  ## Pixel-art style (inherit from reference image)
  - Chunky retro pixel art, Celeste school. Native cloud size roughly 32-64 pixels tall in native coords; crisp stair-stepped silhouette edges. NO anti-aliasing softening. NO smooth gradients.
  - Pure-white pixel fill + 1-row light-gray bottom shadow + 1-pixel medium-gray outline along upper bumps.
  - Same pixel-art language as the reference image's clouds.

  ## Background (critical)
  - The entire image background MUST be a **solid pure flat magenta `#FF00FF` color marker fill** between, behind, and around the cloud cells. For chroma-key removal.
  - DO NOT include any element from the reference image (no character, no platform, no balloons, no hills, no sky gradient — clouds should sit on flat marker color, NOT on the sky).
  - No gradient anywhere. Pure flat `#FF00FF` only.

  ## Hard negatives
  - Do NOT draw a sky gradient behind the clouds — flat magenta only.
  - Do NOT include any character / platform / balloon / hill / extra prop.
  - Do NOT add text, numbers, frame labels, captions, watermarks, signatures, UI elements, or arrows.
  - Do NOT add cell borders, grid lines, separator strips, or panel frames between cells.
  - Do NOT add more than 2 clouds; exactly one cloud per cell.
  - Do NOT cross cell edges with cloud silhouettes.
  - Do NOT smooth, antialias, soften, or blur pixel edges. Crisp pixel art only.
  ```
- layout: 1x2 horizontal sheet → cut into `a` (small) + `b` (larger)

**Hints**
- The magenta marker must be forced explicitly ("clouds should sit on flat marker color, NOT on the sky"). Because the style anchor's clouds already sit on a sky gradient, i2i tends to re-paint the sky behind them; a pure-white cloud on a lavender sky then loses its chroma-key key color.

### hills

- prompt
  ```
  # hills — 2 stacked pixel-art hill silhouette strips for parallax layers

  Generate a **single image with 2 vertically-stacked rows**, each row containing one long horizontal hill silhouette strip. Pixel art. Strict marker-color background.

  These are decorative parallax-layer hill silhouettes drawn behind the gameplay, between the sky background and the playable platforms. They will have transparent backgrounds after chroma-key removal.

  ## The 2 hill strips (top to bottom)
  1. **bg_hill_back — distant back hills (top row)**. A long horizontal strip extending nearly the full width of the image. Several smooth rolling pixel-stepped hill bumps of varied heights along the top edge of the strip, with the bottom edge being a flat horizontal line that anchors to the bottom of its row's cell. Filled with a single flat **dusty lavender** color (#B7A8D6). NO internal detail. NO outline. Just a solid pixel silhouette.
  2. **bg_hill_front — closer front hills (bottom row)**. Similar long horizontal strip with rolling pixel-stepped hill bumps of varied heights. Filled with a single flat **slightly darker lavender** color (#9C8BC4) to suggest closer depth. NO internal detail. NO outline.

  The two hill silhouettes have **different bump rhythms** so they don't look identical (the back hills can be smoother / lower, the front hills can be more jagged / taller).

  ## Sheet layout
  - Two rows, each containing exactly one hill strip (one strip per row).
  - The hill strip extends nearly the full width of the row, leaving small marker-color margin only on the very left and very right edges.
  - Each hill strip has a flat horizontal bottom edge (this is the "base" that aligns to ground) and a bumpy varied top edge (the hill peaks).
  - No cell borders, no separator lines — just marker background filling the area above the strips and the row between them.
  - The two strips do NOT touch — there is clear marker-color space between them (so chroma-key cleanup separates them as two distinct sprites).

  ## Pixel-art style (inherit from reference image)
  - Chunky retro pixel art, Celeste school. Hills are pure solid color silhouettes with crisp stair-stepped tops. NO outlines, NO internal details, NO gradient inside the hills. Just flat solid pixel blocks.
  - Same hill silhouette language as the reference image's distant hills.

  ## Background (critical)
  - The entire image background MUST be a **solid pure flat magenta `#FF00FF` color marker fill** above, below, and between the two hill strips. For chroma-key removal.
  - DO NOT include any element from the reference image (no character, no platform, no balloons, no clouds, no sky gradient — hills should sit on flat marker color, NOT on the sky).
  - No gradient anywhere. Pure flat `#FF00FF` only.

  ## Hard negatives
  - Do NOT draw a sky gradient behind the hills — flat magenta only.
  - Do NOT include any character / platform / balloon / cloud / tree / extra prop.
  - Do NOT add internal hill details (texture, trees on hills, snow caps, contour lines).
  - Do NOT add outlines on the hills.
  - Do NOT add text, numbers, labels, captions, watermarks, signatures, UI elements, or arrows.
  - Do NOT add cell borders, grid lines, separator strips, or panel frames.
  - Do NOT make the two hill strips touch or overlap — keep a clear marker-color band between them.
  - Do NOT smooth, antialias, soften, or blur pixel edges. Crisp pixel art only.
  ```
- layout: 2 vertically-stacked long horizontal strips → cut into `back` (dusty lavender) + `front` (darker lavender)

**Hints**
- Long horizontal parallax strips: prompt a **flat horizontal bottom edge** ("base that aligns to ground") + bumpy varied top edge. The flat base is what the engine tiles/anchors against; a fully-organic blob would not seat cleanly on the horizon.
- Force a clear marker-color band between the two strips so chroma-key + cut separates them into two sprites; touching strips merge into one component.
- Give the two layers **different bump rhythms** (back smoother/lower, front jaggeder/taller) or parallax reads as one duplicated layer.

## Player

The player character is a single named IP character (Anya Forger). Locomotion loops (`idle`, `run`) are authored as 2x2 animation sheets; discrete state poses (`jump`, `fall`, `dash`, `bounce`, `die`) are packed into one horizontal single-pose sheet because their in-game motion is transform-driven, not frame-animated. Canonical facing: RIGHT.

### aniya_idle

- prompt
  ```
  # aniya_idle — 2x2 pixel-art sprite sheet (4 frames, looping idle)

  Generate a **2x2 grid sprite sheet (4 cells total)** of an **idle animation** for the player character. Pixel art. Strict marker-color background.

  ## Character
  The character is **Anya Forger from Spy x Family**, rendered as a chunky retro pixel-art sprite (Celeste / Owlboy school). Keep her canonical recognizable look — do not substitute a generic anime girl. The same Anya Forger appears in every cell, with identical scale, identical palette, identical outfit, identical pose offset, identical bounding box position within each cell.

  ## Sheet layout
  - Exactly **4 equal cells in a 2x2 grid**.
  - Reading order is top-left, top-right, bottom-left, bottom-right.
  - No borders, no separator lines, no gutters between cells — just the solid marker background filling the gap and the four character sprites positioned inside the four cell zones.
  - Same square bounding box in every cell. Sprite subject fills roughly 50-60% of each cell. Leave clean marker-color margin on all four sides of every sprite.
  - The character faces RIGHT in every frame.

  ## Animation (4-frame idle loop, looping seamlessly)
  A single continuous breathing micro-cycle with one subtle secondary motion (hair / cape edge). Same character identity in every frame, only the breath / blink phase changes.

  - frame 1 (top-left): neutral standing pose, arms at sides relaxed, chest at rest, hair tufts settled, eyes open normally.
  - frame 2 (top-right): subtle breath inhale, chest rises slightly, hair tufts drift gently to one side (e.g. left), eyes still open.
  - frame 3 (bottom-left): peak of inhale, body slightly taller, shoulders barely lifted, hair tufts fully drifted, eyes closed (blink frame).
  - frame 4 (bottom-right): exhale starts, chest sinks toward neutral, hair tufts recoil gently to the OTHER side (right), eyes reopening (half-lidded).

  Use restraint words (`subtle`, `slight`, `gently`, `softly`). Use relative deltas (`chest rises`, not `stands tall`).

  ## Pixel-art style (inherit from reference image)
  - Chunky retro pixel art, Celeste school. Sprite around 32-48 pixels tall in native pixel coordinates, displayed at scale with crisp stair-stepped edges. NO anti-aliasing. NO smooth gradients. Limited palette (~6-8 colors total for Anya).
  - 1-pixel dark outline (selective Celeste-style) around the silhouette.
  - Solid pixel blocks of color + simple darker shadow blocks + simple lighter highlight blocks. No painterly shading.
  - Same render style and palette as the reference image. Inherit Anya's pixel-art look from the reference; do NOT redesign her.

  ## Background (critical)
  - The entire image background MUST be a **solid pure flat magenta `#FF00FF` color marker fill** between, behind, and around the character cells. This is for chroma-key removal later. It is NOT the sky from the reference image.
  - DO NOT copy the sky / clouds / hills / platform background from the reference. The reference is for **character pixel-art style only**.
  - No gradient anywhere in the background. Pure flat `#FF00FF` only.

  ## Hard negatives
  - Do NOT draw the platform / sky / clouds / hills / balloons from the reference.
  - Do NOT add any text, numbers, labels, frame counters, captions, watermarks, signatures, UI elements, or arrows.
  - Do NOT add cell borders, grid lines, separator strips, or panel frames between the 4 cells.
  - Do NOT add any character other than Anya Forger.
  - Do NOT vary Anya's scale, palette, outfit, hair shape, or facing direction between frames.
  - Do NOT cross cell edges — every sprite stays fully contained in its cell with margin.
  - Do NOT smooth, antialias, soften, or blur pixel edges. Crisp pixel art only.
  ```
- layout: 2x2 grid

**Hints**
- `idle` is the canonical scale anchor for the character — after manifest registration, compare `run` and the action poses' frame bbox heights against it (see [agents/artist.md](../../.claude/agents/artist.md) Phase 5 "Cross-action scale gate").
- Idle uses the `sprite.md` idle micro-cycle recipe (one driving breath wave + one secondary hair motion, reverse-closure on frame 4). Explicitly restate "background is NOT the sky from the reference" — with an i2i style anchor that is itself a full gameplay scene, the model will otherwise paste the sky back in and kill the magenta key.

### aniya_run

- prompt
  ```
  # aniya_run — 2x2 pixel-art sprite sheet (4-frame running animation)

  Generate a **2x2 grid sprite sheet (4 cells total)** of a **side-view running animation** for the player character. Pixel art. Strict marker-color background.

  ## Character
  The character is **Anya Forger from Spy x Family**, rendered as a chunky retro pixel-art sprite (Celeste / Owlboy school). Keep her canonical recognizable look. Same Anya in every cell, identical scale, identical palette, identical outfit, identical bounding box position within each cell. Facing RIGHT (running rightward).

  ## Sheet layout
  - Exactly **4 equal cells in a 2x2 grid**.
  - Reading order top-left, top-right, bottom-left, bottom-right.
  - No cell borders, no separator lines, no gutters — just marker background filling the space.
  - Same square bounding box in every cell. Sprite fills ~50-60% of each cell. Clean marker margin on all four sides.
  - All four frames show the SAME character running RIGHT.

  ## Animation (4-frame running cycle, side-view profile)
  A classic 4-frame side-view running cycle. Read like a side-scroller platformer (Celeste, Mario). The character moves through one stride loop seamlessly.

  - frame 1 (top-left): **contact pose, right foot forward**. Right leg extended forward planted, left leg bent back behind. Torso leaning slightly forward into the run. Right arm swings back, left arm swings forward (opposite-arm-to-leg). Hair tufts trailing back from forward motion. Skirt hem flicks back.
  - frame 2 (top-right): **passing pose, body at low point**. Both legs near vertical and close together under the body, body briefly lowered, weight shifting. Arms near neutral mid-swing. Hair tufts still trailing back.
  - frame 3 (bottom-left): **contact pose, left foot forward**. Mirror of frame 1: left leg extended forward planted, right leg bent back behind. Left arm back, right arm forward. Hair still trailing back. Skirt flicks back.
  - frame 4 (bottom-right): **passing pose, body at high point**. Both legs near vertical and close together, but body slightly raised (airborne mini-hop between strides). Arms mid-swing. Hair trailing.

  Body lean is consistent across all frames (slight forward lean for running). Anya's expression stays focused / determined. Same outfit palette and silhouette in every frame.

  ## Pixel-art style (inherit from reference image)
  - Chunky retro pixel art, Celeste school. Sprite ~32-48 pixels tall in native pixel coords, displayed at scale with crisp stair-stepped edges. NO anti-aliasing. NO smooth gradients. Limited palette (~6-8 colors total for Anya).
  - 1-pixel dark outline (selective Celeste-style) along the silhouette.
  - Solid pixel blocks of color + simple darker shadow blocks + simple lighter highlight blocks. No painterly shading.
  - Same render style and palette as the reference image. Inherit Anya's pixel-art look from the reference.

  ## Background (critical)
  - The entire image background MUST be a **solid pure flat magenta `#FF00FF` color marker fill** between, behind, and around the character cells. For chroma-key removal.
  - DO NOT copy the sky / clouds / hills / platform background from the reference image. Reference is for **character pixel-art style only**.
  - No gradient anywhere in the background. Pure flat `#FF00FF` only.

  ## Hard negatives
  - Do NOT draw the platform / sky / clouds / hills / balloons from the reference.
  - Do NOT add any text, numbers, labels, frame counters, captions, watermarks, signatures, UI elements, motion blur trails, speed lines, or arrows.
  - Do NOT add cell borders, grid lines, separator strips, or panel frames between the 4 cells.
  - Do NOT add any character other than Anya Forger.
  - Do NOT vary Anya's scale, palette, outfit, hair shape, or overall silhouette mass between frames.
  - Do NOT change facing direction — every frame faces right.
  - Do NOT cross cell edges — every sprite fully contained in its cell with margin.
  - Do NOT smooth, antialias, soften, or blur pixel edges. Crisp pixel art only.
  ```
- layout: 2x2 grid

**Hints**
- Classic 4-frame side-view stride: contact-R / passing-low / contact-L / passing-high. Explicitly name the low-point and high-point passing poses so the run has vertical bob and reads as motion rather than a leg-shuffle.

### aniya_actions

- prompt
  ```
  # aniya_actions — 1x5 pixel-art sprite sheet (5 single-pose action poses)

  Generate a **1x5 grid sprite sheet (5 cells in a horizontal row)** of distinct single-pose actions for the player character. Pixel art. Strict marker-color background.

  ## Character
  The character is **Anya Forger from Spy x Family**, rendered as a chunky retro pixel-art sprite (Celeste / Owlboy school). Keep her canonical recognizable look. **Same Anya in every cell**, identical scale, identical palette, identical outfit. Only her pose, body angle, and expression change between cells. Facing RIGHT in every cell.

  ## Sheet layout
  - Exactly **5 equal cells in one horizontal row (1x5)**.
  - Reading order: left to right.
  - No cell borders, no separator lines, no gutters — just marker background filling the space.
  - Same vertical bounding box height in every cell. Sprite fills ~50-60% of each cell. Clean marker margin on all sides.
  - All five poses use the same character at the same scale and color palette.

  ## The 5 cells (left to right)
  1. **JUMP** — rising pose. Body upright but slightly tilted forward, both legs pulled up into a tight tuck (knees bent up), arms swinging up alongside body or one arm raised. Hair tufts blown back / up by upward motion. Expression: determined / focused.
  2. **FALL** — descending pose. Body upright but with legs dangling slightly extended down, arms slightly out for balance (gentle T-pose or one arm forward one arm back). Hair tufts blowing UP because of downward motion. Expression: neutral focused, mouth slightly open.
  3. **DASH** — horizontal speed-burst pose. Body extended FULLY HORIZONTAL toward the right side of the cell (parallel to ground), like Madeline's dash in Celeste. Arms streamlined back along body. Legs trailing back nearly horizontal. Hair tufts streaming back hard. Add 2-3 small pixel speed lines / pixel afterimage shapes behind her (very small, contained inside the cell, in a faint cyan or pink afterimage color). Expression: intense, eyes wide.
  4. **BOUNCE** — being launched upward by something below. Body kicked up vertically, arms thrown UP in surprised excitement, legs swung up under body in joyful kick. Hair tufts SHOOTING UP from the bounce. Expression: **wide excited surprise** — big round eyes wider than usual, mouth in an open round "wow / yay" shape (small "o").
  5. **DIE** — defeated falling pose. Body tilted backward in a small comedic flop, eyes closed in a cute "x_x" pixel-art X shape (or simple closed-eye lines), mouth a small unhappy zigzag or simple "ah" shape (small open mouth). Limbs limp / dangling. Hair tufts flopping. NOT gory, NOT scary — cute defeated look. A tiny dust-puff pixel cloud at her feet is OK if it fits in the cell.

  ## Pixel-art style (inherit from reference image)
  - Chunky retro pixel art, Celeste school. Sprite ~32-48 pixels tall in native pixel coords, displayed at scale with crisp stair-stepped edges. NO anti-aliasing. NO smooth gradients. Limited palette.
  - 1-pixel dark outline (selective Celeste-style) along the silhouette.
  - Solid pixel blocks of color + simple darker shadow blocks + simple lighter highlight blocks. No painterly shading.
  - Same render style and palette as the reference image. Inherit Anya's pixel-art look from the reference.

  ## Background (critical)
  - The entire image background MUST be a **solid pure flat magenta `#FF00FF` color marker fill** between, behind, and around the character cells. For chroma-key removal.
  - DO NOT copy the sky / clouds / hills / platform background from the reference image. Reference is for **character pixel-art style only**.
  - No gradient anywhere. Pure flat `#FF00FF` only.

  ## Hard negatives
  - Do NOT draw the platform / sky / clouds / hills / balloons from the reference.
  - Do NOT add any text, numbers, frame labels, captions, watermarks, signatures, UI elements, action-name banners, or arrows.
  - Do NOT add cell borders, grid lines, separator strips, or panel frames.
  - Do NOT add any character other than Anya Forger. (Tiny pixel afterimage / dust puff inside DASH or DIE cells are OK as small effect details, not extra characters.)
  - Do NOT vary Anya's scale, palette, outfit, or hair shape between cells.
  - Do NOT change facing direction — every cell faces right.
  - Do NOT cross cell edges — every pose fully contained in its cell with margin.
  - Do NOT smooth, antialias, soften, or blur pixel edges. Crisp pixel art only.
  ```
- layout: 1x5 horizontal single-pose sheet → cut into `jump` + `fall` + `dash` + `bounce` + `die` (5 independent state sprites, NOT an animation loop)

**Hints**
- These 5 are **single-pose held-pose states**, not animation loops. The discriminator is NOT "engine drives position" (position is engine/transform-driven for every state, including idle and run) — it is intrinsic body motion: `idle` and `run` have cyclic in-place body motion (breathing, leg-cycle) that animates regardless of world position, so they need multiple frames; `jump` / `fall` / `dash` / `bounce` each hold one characteristic pose while the engine translates the body through space, so one representative frame each is enough. Packing them in one sheet keeps scale + palette + outline weight identical across all states in a single generation.
- `bounce` (spring/balloon launch upward) and `dash` (Celeste horizontal burst) are this sub-genre's signature poses — bounce reads as "thrown up, arms up, wide surprised eyes"; dash reads as "fully horizontal body + faint cyan/pink pixel afterimage". Keep the afterimage tiny and inside the cell or the cut merges the trail into a separate component.
- After cut, run the cross-action scale gate against `aniya_idle`; single-pose sheets tend to come back close but the DASH horizontal pose can widen the bbox — check, don't assume.

## Balloon

Three balloon variants at intentionally different scales (red standard / blue ~1.5x / gold ~0.7x — this scale difference is gameplay design, so the cross-action scale gate does NOT apply between variants). Static idle sprites plus a shared 4-frame pop animation recolored per variant.

### balloons_idle

- prompt
  ```
  # balloons_idle — 1x3 pixel-art sprite sheet (3 static balloon variants)

  Generate a **1x3 grid sprite sheet (3 cells in a horizontal row)** of three balloon variants for the game. Each cell shows ONE static balloon (no animation). Pixel art. Strict marker-color background.

  ## The 3 balloons (left to right)
  1. **Standard red balloon** — medium size (this is the size reference). Bright cherry red color (#E63A3A).
  2. **Larger blue balloon** — roughly 1.5x the red balloon's height. Bright sky/royal blue color (#3A8FE6).
  3. **Smaller gold balloon** — roughly 0.7x the red balloon's height. Warm gold color (#F5C04A).

  Each balloon is a classic round teardrop balloon silhouette:
  - Round body, slightly taller than wide (egg-like).
  - Small triangular knot at the bottom.
  - Thin pixel string trailing straight down a short distance from the knot.
  - 1-pixel dark outline along the silhouette (selective Celeste-style — outline can lighten on shaded side).
  - One darker pixel shadow crescent shape on the lower-right of the body (~25-30% of body area).
  - One pure-white pixel highlight (small rounded rectangle or oval) on the upper-left of the body.
  - The gold balloon may have a slightly stronger/brighter highlight to suggest a metallic gleam.

  ## Sheet layout
  - Exactly **3 equal cells in one horizontal row (1x3)**.
  - Reading order: red, blue, gold.
  - No cell borders, no separator lines, no gutters — just marker background filling the space.
  - Same cell width and height across all three cells.
  - Each balloon is vertically centered within its cell, leaving clean marker margin on all four sides.
  - Balloons sit at the SAME baseline within their respective cells (knot bottom roughly at the same vertical position) so they can be aligned by the engine if needed.
  - The size differences between balloons (red standard / blue larger / gold smaller) are clearly visible.

  ## Pixel-art style (inherit from reference image)
  - Chunky retro pixel art, Celeste school. Native pixel-coordinate sizes roughly: red ~32 px tall, blue ~48 px tall, gold ~24 px tall — displayed at scale with crisp stair-stepped edges. NO anti-aliasing. NO smooth gradients.
  - 1-pixel dark outlines.
  - Solid color fill + simple darker shadow block + pure-white highlight block. No painterly shading.
  - Same render style and palette family as the reference image. Inherit the balloon look from the reference (the reference has red, blue, and gold balloons of the same shape — match that style).

  ## Background (critical)
  - The entire image background MUST be a **solid pure flat magenta `#FF00FF` color marker fill** between, behind, and around the balloon cells. For chroma-key removal.
  - DO NOT copy the sky / clouds / hills / platform / character from the reference image. Reference is for **balloon pixel-art style only**.
  - No gradient anywhere. Pure flat `#FF00FF` only.

  ## Hard negatives
  - Do NOT draw any character / platform / sky / clouds / hills / scenery from the reference.
  - Do NOT add any text, numbers, labels, size annotations, captions, watermarks, signatures, UI elements, price tags, or arrows.
  - Do NOT add cell borders, grid lines, separator strips, or panel frames.
  - Do NOT add extra props (gifts, ribbons, stars, sparkles) — just the three balloons each with their string.
  - Do NOT add more than three balloons. Exactly 3 balloons, one per cell.
  - Do NOT vary balloon shape between the three — only color and size differ.
  - Do NOT cross cell edges — every balloon (including string) fully contained in its cell with margin.
  - Do NOT smooth, antialias, soften, or blur pixel edges. Crisp pixel art only.
  ```
- layout: 1x3 horizontal sheet → cut into `red` + `blue` + `gold`

**Hints**
- **Intentional cross-variant scale difference** (blue ~1.5x, gold ~0.7x of red): drives gameplay (blue = soft big buffer, gold = small hard reward). Do NOT normalize these to one scale — the cross-action scale gate is for the same actor's animation clips, not for deliberately-sized sibling objects. Keep the per-variant compact bboxes as cut; the engine reads size from bbox.
- Only shape stays constant across variants; color + size differ. State "do NOT vary balloon shape" so the model does not restyle each variant.

### balloons_pop

- prompt
  ```
  # balloons_pop — 3x4 pixel-art sprite sheet (3 colors × 4-frame pop animation)

  Generate a **3-row × 4-column grid sprite sheet (12 cells total)** of balloon-pop animations. Each row is one color, animated across 4 frames left-to-right. Pixel art. Strict marker-color background.

  ## Sheet layout
  - Exactly **12 equal cells in a 3-row × 4-column grid**.
  - Reading order: rows top-to-bottom, frames left-to-right within each row.
  - **Row 1 (top): RED balloon pop** — red color #E63A3A
  - **Row 2 (middle): BLUE balloon pop** — blue color #3A8FE6
  - **Row 3 (bottom): GOLD balloon pop** — gold color #F5C04A
  - No cell borders, no separator lines, no gutters — just marker background filling the gaps.
  - Same cell dimensions across all 12 cells. Each balloon-pop fills ~50-60% of its cell. Leave clean marker margin on all four sides.
  - All three rows use the SAME 4-frame animation structure — only the dominant color differs between rows. Frame N looks structurally the same in red row, blue row, gold row (same silhouette / fragments / dust layout), just recolored.

  ## The 4-frame pop animation (each row)
  - **frame 1 (column 1): pre-pop squash**. The intact balloon, slightly squashed/compressed vertically (anticipation pose). Outline visible, string still attached at bottom. Subtle indication of about-to-burst.
  - **frame 2 (column 2): burst moment**. The balloon body breaks into 4-6 angular shard fragments flying outward from a central burst point. A bright pixel flash (small white star or cross shape) sits at the center where the balloon used to be. Fragments are clearly the color of the row's balloon. String remnant falling.
  - **frame 3 (column 3): scatter**. Fragments have flown further outward and started shrinking. Add ~3-4 tiny round confetti pixel pieces (white/light highlights) scattered between fragments. Burst flash gone or much smaller. Empty space where the balloon was.
  - **frame 4 (column 4): dissipate**. Most fragments are gone or tiny. Maybe 2-3 small pixel dots remain in the air, drifting outward and fading. A small "puff" of light-gray pixel smoke near the center. About to fully disappear.

  Effect motion is contained inside each cell — no fragment crosses cell edges.

  ## Pixel-art style (inherit from reference image)
  - Chunky retro pixel art, Celeste school. Native pixel coords match the corresponding balloon idle sizes (red ~32 px, blue ~48 px, gold ~24 px) plus a small effect area around it. Crisp stair-stepped edges. NO anti-aliasing. NO smooth gradients. Limited palette per row.
  - 1-pixel dark outlines on shapes that have body (fragments, smoke puff).
  - Solid color fill + simple darker shadow + simple lighter highlight per shape. No painterly shading.
  - Same render style and palette family as the reference image.

  ## Background (critical)
  - The entire image background MUST be a **solid pure flat magenta `#FF00FF` color marker fill** between, behind, and around every cell. For chroma-key removal.
  - DO NOT copy the sky / clouds / hills / platform / character from the reference image. Reference is for **balloon and pop-effect pixel-art style only**.
  - No gradient anywhere. Pure flat `#FF00FF` only.

  ## Hard negatives
  - Do NOT draw any character / platform / sky / clouds / hills / scenery from the reference.
  - Do NOT add any text, numbers, frame labels, captions, watermarks, signatures, UI elements, sound-effect words ("POP", "BANG"), or arrows.
  - Do NOT add cell borders, grid lines, separator strips, or panel frames between cells.
  - Do NOT vary balloon-shape language between rows — only the dominant color changes row-to-row.
  - Do NOT cross cell edges with fragments / debris / flash rays.
  - Do NOT smooth, antialias, soften, or blur pixel edges. Crisp pixel art only.
  ```
- layout: 3x4 grid (rows = red/blue/gold variant, columns = 4 pop frames) → cut into `{color}_0..3` (12 frames), engine plays `{color}_0 → {color}_3` on hit

**Hints**
- **Variant-rows × animation-columns grid**: one generation produces the same 4-frame animation recolored across 3 variant rows. Explicitly require "frame N structurally identical across rows, only recolored" so the three variants pop in visual lockstep and share timing.
- Frames 3-4 contain **detached fragments / confetti dots** — tune `vibegame art cut --min-area` down or hand-pick, or the auto-cut drops the scattered debris. Keep debris inside its cell.
- Pop FX is centered (not ground-anchored): register with `pivot [0.5, 0.5]` so the burst plays where the balloon was, not floating up by half-height.

## FX

### confetti

- prompt
  ```
  # confetti_particle — 2x4 pixel-art sprite sheet (8 confetti shape/color variants)

  Generate a **2-row × 4-column grid sprite sheet (8 cells total)** of confetti particle sprites. Each cell shows ONE tiny chunky pixel confetti piece. Pixel art. Strict marker-color background.

  These are tiny FX particles used to celebrate balloon pops and level completion. Each cell yields one independent confetti sprite that the engine spawns in bursts.

  ## The 8 confetti variants (left to right, top to bottom)
  1. **Red square** — small chunky pixel square, bright red #E63A3A, with a 1-pixel darker shadow row at the bottom.
  2. **Blue diamond / rotated square** — small pixel diamond shape, bright blue #3A8FE6, with a 1-pixel darker shadow on the lower-right side.
  3. **Gold star** — tiny 4-point or 5-point pixel star, warm gold #F5C04A, with a pure-white pixel highlight pixel near the center.
  4. **Pink rectangle strip** — narrow vertical pixel strip (e.g. 3 wide × 7 tall pixels), bright pink #FF7AB6, with 1-pixel darker shadow on the right edge.
  5. **Green triangle** — small pixel triangle pointing upward, fresh green #7BC36A, with 1-pixel darker shadow on the lower-right.
  6. **White round dot** — small round pixel circle, pure white, with 1-pixel light-gray shadow at the bottom (acts as a bright sparkle particle).
  7. **Orange short strip** — narrow horizontal pixel strip (e.g. 7 wide × 3 tall), bright warm orange #F58F3A, with 1-pixel darker shadow at the bottom.
  8. **Purple lozenge** — small rounded lozenge / pill shape (capsule), bright purple #B26AD9, with pure-white pixel highlight pixel on the upper-left.

  ## Sheet layout
  - Exactly **8 equal cells in a 2-row × 4-column grid**.
  - Reading order: top-left, top-row right; then bottom-left, bottom-row right.
  - No cell borders, no separator lines, no gutters — just marker background filling the gaps.
  - Same cell dimensions across all 8 cells. Each confetti piece is small, centered in its cell, occupying ~25-40% of the cell area. Lots of marker margin around each piece (since these are tiny particles, plenty of breathing room).
  - Each piece is one tightly-pixel-grouped shape, not floating scattered fragments.

  ## Pixel-art style (inherit from reference image)
  - Chunky retro pixel art, Celeste school. Particles are small (~6-12 pixels in their longest dimension in native coords). Crisp stair-stepped edges. NO anti-aliasing. NO smooth gradients.
  - 1-pixel dark or darker-tone outline along the silhouette where it improves silhouette readability (Celeste-style selective outline; pure shapes may have no outline if the color contrasts enough).
  - Solid color fill + 1 darker shadow pixel block + optional 1 lighter highlight pixel. No painterly shading.
  - Same pixel-art language as the reference image's balloon highlights / sky dithering.

  ## Background (critical)
  - The entire image background MUST be a **solid pure flat magenta `#FF00FF` color marker fill** between, behind, and around the confetti cells. For chroma-key removal.
  - DO NOT include any element from the reference image (no character, no platform, no sky, no clouds, no large balloons). Reference is for **pixel-art style only**.
  - No gradient anywhere. Pure flat `#FF00FF` only.

  ## Hard negatives
  - Do NOT include large balloons, large props, scenery, or characters.
  - Do NOT add any text, numbers, frame labels, captions, watermarks, signatures, UI elements, or arrows.
  - Do NOT add cell borders, grid lines, separator strips, or panel frames.
  - Do NOT cluster multiple confetti pieces in one cell — exactly ONE confetti piece per cell.
  - Do NOT cross cell edges with confetti pieces.
  - Do NOT smooth, antialias, soften, or blur pixel edges. Crisp chunky pixel art only.
  ```
- layout: 2x4 grid → cut into 8 named particles (`red_square`, `blue_diamond`, `gold_star`, `pink_strip`, `green_triangle`, `white_dot`, `orange_strip`, `purple_lozenge`)

**Hints**
- Particle sheet = 8 independent single-shape sprites the engine spawns randomly in bursts (balloon pop + goal celebration). Prompt each as "one tightly-pixel-grouped shape per cell, ~25-40% cell area, lots of margin" — tiny well-separated pieces cut cleanly; scattered fragments merge or over-cut.
- Register with `pivot [0.5, 0.5]` (particles spin/scatter around their center).

## Map

### platforms

- prompt
  ```
  # platforms — 1x3 pixel-art sprite sheet (3 platform variants)

  Generate a **1-row × 3-column grid sprite sheet (3 cells total)** of three pixel-art platform sprite variants. Pixel art. Strict marker-color background.

  These are static platform sprites the player can stand on. Each is one self-contained chunky pixel block (grass top + brown earth body). Lined up in one sheet for style consistency.

  ## The 3 platforms (left to right)
  1. **platform_start — wide tile-able start platform**. A wider rectangular platform sprite (e.g. ~96 pixels wide × 32 pixels tall in native pixel coords). Designed to be horizontally tileable: its left and right edges have matching pixel patterns at the same y-positions so adjacent copies form a seamless extended ground.
  2. **platform_mid — small midair platform**. A smaller rectangular platform sprite (e.g. ~48 pixels wide × 24 pixels tall in native coords), self-contained (not tileable). Used for jump targets between balloon arcs.
  3. **platform_goal — wide goal platform**. Same proportions as platform_start but slightly shorter (e.g. ~80 pixels wide × 32 pixels tall in native coords). Self-contained, not required to tile.

  All three share the same visual design:
  - **Top layer (grass)**: bright leaf green (#7BC36A) base color, with a row of slightly darker green (#4F9A48) pixel grass-blade tufts along the very top edge (3-4 pixel-tall protrusions of varied shapes giving an organic feel). This grass strip is roughly 1/3 of the platform's total height.
  - **Body (earth)**: warm cocoa brown (#9C6A3C) base color, with 2-3 small lighter brown (#C9925C) rounded pixel "pebble" clusters embedded in the body (just a few pixel dots arranged as a small pebble shape).
  - **Outline**: 1-pixel dark warm-brown (#3A2A24) outline along the visible top (above the grass strip), exposed left edge, exposed right edge, and bottom edge of every platform.
  - **Internal earth shadow**: 1-pixel darker brown (#7A5430) row immediately below the grass-earth boundary line, suggesting the cool shade under the grass overhang.

  The three platforms differ ONLY in size (and not-tileable vs tileable design for the side edges). Style / palette / language is identical.

  ## Sheet layout
  - Exactly **3 cells in one horizontal row (1x3)**.
  - No cell borders, no separator lines, no gutters between platforms — just marker background filling the space.
  - Same row height across all 3 cells. Each platform is vertically centered in its cell, with the wider/larger platforms allowed to be relatively wider but with consistent height.
  - Clear marker margin all around each platform; platforms do NOT touch each other.

  ## Pixel-art style (inherit from reference image)
  - Chunky retro pixel art, Celeste school. Native pixel sizes as noted (~32 px tall) — displayed at scale with crisp stair-stepped edges. NO anti-aliasing. NO smooth gradients. Limited palette.
  - 1-pixel dark outline along visible borders.
  - Solid color fills + simple darker shadow blocks + simple highlight pebbles. No painterly shading.
  - Same render style and palette family as the reference image's start platform. Inherit the platform's look from the reference.

  ## Background (critical)
  - The entire image background MUST be a **solid pure flat magenta `#FF00FF` color marker fill** between, behind, and around the platform cells. For chroma-key removal.
  - DO NOT copy the sky / clouds / hills / character / balloons from the reference. Reference is for **platform pixel-art style only**.
  - No gradient anywhere. Pure flat `#FF00FF` only.

  ## Hard negatives
  - Do NOT draw character / sky / clouds / hills / balloons from the reference.
  - Do NOT add text, numbers, labels (no "START", "GOAL", etc.), captions, watermarks, signatures, UI elements, or arrows.
  - Do NOT add cell borders, grid lines, separator strips, or panel frames.
  - Do NOT add decorative props on the platforms (flowers, flags, signs, mushrooms, stones beyond the few small pebble shapes).
  - Do NOT cross cell edges with platform pixels.
  - Do NOT smooth, antialias, soften, or blur pixel edges. Crisp pixel art only.
  ```
- layout: 1x3 horizontal sheet → cut into `start` (wide, tileable) + `mid` (small) + `goal` (wide)

**Hints**
- All three share one palette + construction (grass strip ~1/3 height over brown earth body, dark outline on visible edges, 1-px shade row under the grass line); only size and tileable-vs-self-contained edge design differ. State "differ ONLY in size" so the model keeps them a matching family.
- The `start` variant is prompted for **horizontal tiling** (matching left/right edge patterns at equal y) so the engine can extend the ground seamlessly. If the level needs longer ground, this is the tileable one.
- These are visible platform art; the physics collider is placed separately by the programmer (raster-map-style invisible static colliders aligned to the visible grass-top surface) — see the rastermap contract. Note the grass-top y in `.vibegame/assets.md` for the architect.

### goal_flag

- prompt
  ```
  # goal_flag — single pixel-art sprite (checker goal flag on pole)

  Generate a **single static sprite** of a pixel-art goal flag on a wooden pole. Pixel art. Strict marker-color background.

  This is the level-end marker. Player reaches it to complete the level.

  ## Subject
  A tall wooden flagpole with a bright triangular checker flag at the top:
  - **Pole**: a vertical rectangular column of warm brown pixels (#7A5430 base, with 1-pixel highlight column of lighter #9C6A3C on the left side and 1-pixel darker #4A2F22 shadow column on the right side). The pole is roughly 4 pixels wide and ~48-64 pixels tall in native pixel coords. The pole has a small rounded pixel "knob" at the very top (a 4×4 pixel rounded cap in lighter brown #C9925C with darker shadow underneath).
  - **Flag**: A triangular pennant attached to the upper-right side of the pole, pointing right. The flag is filled with a **pink-and-white checker pattern** (alternating 4×4 pixel squares of pink #FF7AB6 and pure white). The pink uses the same warm pink found in the reference image's flag. The flag's left edge is attached to the pole; its right edge tapers to a single pixel point. Roughly 24 pixels wide × 16 pixels tall at the base.
  - **Outline**: 1-pixel dark warm-brown (#3A2A24) outline around the flag silhouette and along the pole's vertical edges for clear silhouette readability.
  - **Wind suggestion**: the flag's right-side outline has a tiny gentle pixel curve / wave (1-2 pixel vertical offsets at the tip and midpoint) suggesting the flag flutters slightly in a breeze.

  ## Layout
  - Just ONE sprite, centered in the image. Plenty of marker margin on all four sides.
  - The whole flag + pole assembly sits roughly upright, pole vertical.

  ## Pixel-art style (inherit from reference image)
  - Chunky retro pixel art, Celeste school. Crisp stair-stepped pixel edges. NO anti-aliasing. NO smooth gradients.
  - 1-pixel dark outlines as specified.
  - Solid color fills + simple shadow/highlight columns. No painterly shading.
  - Same pixel-art language and flag look as the reference image's goal flag.

  ## Background (critical)
  - The entire image background MUST be a **solid pure flat magenta `#FF00FF` color marker fill** behind and around the flag sprite. For chroma-key removal.
  - DO NOT copy any element from the reference image (no character, no platform, no balloons, no clouds, no sky). Reference is for **flag pixel-art style only**.
  - No gradient anywhere. Pure flat `#FF00FF` only.

  ## Hard negatives
  - Do NOT include a platform under the flag — the flag is a standalone sprite the engine places on top of a platform.
  - Do NOT include character, balloons, clouds, hills, sky, scenery.
  - Do NOT add text on the flag ("GOAL", "FINISH", "FIN", numbers, etc.).
  - Do NOT add additional decorations (stars, ribbons, hearts, particles around the flag).
  - Do NOT add cell borders, grid lines, panel frames.
  - Do NOT smooth, antialias, soften, or blur pixel edges. Crisp pixel art only.
  ```
- layout: single frame, transparent PNG (chroma-key from magenta marker)

**Hints**
- Standalone marker sprite the engine places on top of the `goal` platform — explicitly forbid drawing a platform underneath, or the flag arrives fused to its own ground and cannot sit on the goal platform.
- Bottom-anchored (pole base = feet), so default `[0.5, 1]` pivot is correct; do not write a center pivot for it.
