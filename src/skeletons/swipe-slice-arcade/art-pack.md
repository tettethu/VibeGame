# Art Pack - swipe-slice-arcade

This file records the empirical raw-image patterns that produced the final runtime art for a fixed-screen swipe-to-slice arcade game. Prompts are distilled from the completed build; the original imagegen log was unavailable.

## Background

### background_raw
- reference: art-pack-assets/reference.webp
- prompt
  ```
Use image 1 as the visual style reference only. Create a final runtime background image for a 2D fixed-screen fruit slicing arcade game.

Canvas: 16:9 landscape, clean game background, no UI and no gameplay objects.
Style: dark low-detail dojo / wood / parchment / night backdrop, matching image 1's mood, warm dark browns and deep navy shadows, subtle wood grain, faint parchment panels, soft vignette, slight East Asian dojo wall motif.
Critical composition requirements:
- Full-screen back wall / abstract backdrop only.
- No ground, no tabletop, no counter, no floor, no platform, no horizon line, no fruit basket, no foreground support surface.
- Do not imply a place where fruit can rest; the fruits will float in front of this image at runtime.
- Keep the center and main play area low contrast and uncluttered so bright fruit sprites and bomb sprites remain readable.
- No fruit, no bomb, no slash trail, no juice, no characters, no hands, no knife, no HUD, no text, no labels, no borders, no watermark.
- Must look like a reusable runtime background layer, not a cinematic poster.
  ```
- layout: single 16:9 opaque background, later resized/cropped to runtime canvas

**Hints**
- Fixed-screen swipe-slice games worked best when the generated background was only a back-wall / abstract backdrop, not a scene with floor, table, counter, basket, or any foreground support surface.
- Keep gameplay readability explicit in the prompt: low contrast center, no fruit, no bomb, no slash, no juice, no HUD.

## Fruit body triplets

### fruit_apple_raw
- reference: art-pack-assets/reference.webp
- prompt
  ```
Use image 1 as the visual style reference only: high-saturation stylized cartoon runtime sprites, crisp readable silhouettes, juicy polished fruit rendering, clean arcade look.

Create a runtime fruit sprite triplet sheet on a perfectly flat solid #FF00FF magenta chroma-key background.
Canvas: 1536x1024 landscape.
Layout: exactly three separate sprite objects in one horizontal row with generous magenta space between them and around every object. No frame borders, no grid lines, no labels, no text.
From left to right: 1) whole Apple sprite, 2) left sliced half sprite, 3) right sliced half sprite.
Subject: round glossy red apple with a small connected stem, cream-colored cut flesh, tiny dark seeds, the baseline standard fruit.
Critical runtime constraints:
- The whole fruit, left half, and right half are separate transparent-PNG style runtime sprites; each must be fully visible and isolated.
- The sliced halves must visually match the whole fruit: same peel/shell colors, same material style, same cut flesh colors, matching cut angle and believable paired left/right halves.
- Do NOT include any juice, splashes, droplets, pulp particles, motion streaks, trails, labels, UI, shadows, contact shadows, floor, table, basket, hands, knife, or background art.
- The fruit body sprites must be clean and dry; juice VFX will be separate assets.
- Keep every sprite connected as a single readable silhouette where possible, with stems/leaves/crowns physically attached to the fruit body.
- No object may touch the image edge.
- Background must be one uniform flat #FF00FF, with no gradients, texture, shadows, or lighting variation.
  ```
- layout: 3-object horizontal triplet: whole fruit, left sliced half, right sliced half

**Hints**
- This raw class is the core sliceable-object pattern: generate dry fruit bodies only. Juice, droplets, pulp, and motion streaks must be separate VFX raws.
- The left and right sliced halves must visually match the whole fruit. Ask for same peel/shell colors, same material style, same cut flesh colors, and believable paired cut angles.

### fruit_watermelon_raw
- reference: art-pack-assets/reference.webp
- prompt
  ```
Use image 1 as the visual style reference only: high-saturation stylized cartoon runtime sprites, crisp readable silhouettes, juicy polished fruit rendering, clean arcade look.

Create a runtime fruit sprite triplet sheet on a perfectly flat solid #FF00FF magenta chroma-key background.
Canvas: 1536x1024 landscape.
Layout: exactly three separate sprite objects in one horizontal row with generous magenta space between them and around every object. No frame borders, no grid lines, no labels, no text.
From left to right: 1) whole Watermelon sprite, 2) left sliced half sprite, 3) right sliced half sprite.
Subject: large round striped green watermelon, vivid red flesh with black seeds, thick pale rind, heavy high-score fruit.
Critical runtime constraints:
- The whole fruit, left half, and right half are separate transparent-PNG style runtime sprites; each must be fully visible and isolated.
- The sliced halves must visually match the whole fruit: same peel/shell colors, same material style, same cut flesh colors, matching cut angle and believable paired left/right halves.
- Do NOT include any juice, splashes, droplets, pulp particles, motion streaks, trails, labels, UI, shadows, contact shadows, floor, table, basket, hands, knife, or background art.
- The fruit body sprites must be clean and dry; juice VFX will be separate assets.
- Keep every sprite connected as a single readable silhouette where possible, with stems/leaves/crowns physically attached to the fruit body.
- No object may touch the image edge.
- Background must be one uniform flat #FF00FF, with no gradients, texture, shadows, or lighting variation.
  ```
- layout: 3-object horizontal triplet: whole fruit, left sliced half, right sliced half

**Hints**
- Use the same triplet structure as other fruit. Heavy or large fruits can still share the same raw layout as small fruits; runtime scale handles gameplay size.

### fruit_banana_raw
- reference: art-pack-assets/reference.webp
- prompt
  ```
Use image 1 as the visual style reference only: high-saturation stylized cartoon runtime sprites, crisp readable silhouettes, juicy polished fruit rendering, clean arcade look.

Create a runtime fruit sprite triplet sheet on a perfectly flat solid #FF00FF magenta chroma-key background.
Canvas: 1536x1024 landscape.
Layout: exactly three separate sprite objects in one horizontal row with generous magenta space between them and around every object. No frame borders, no grid lines, no labels, no text.
From left to right: 1) whole Banana sprite, 2) left sliced half sprite, 3) right sliced half sprite.
Subject: curved bright yellow banana, soft pale interior, light and playful fruit.
Critical runtime constraints:
- The whole fruit, left half, and right half are separate transparent-PNG style runtime sprites; each must be fully visible and isolated.
- The sliced halves must visually match the whole fruit: same peel/shell colors, same material style, same cut flesh colors, matching cut angle and believable paired left/right halves.
- Do NOT include any juice, splashes, droplets, pulp particles, motion streaks, trails, labels, UI, shadows, contact shadows, floor, table, basket, hands, knife, or background art.
- The fruit body sprites must be clean and dry; juice VFX will be separate assets.
- Keep every sprite connected as a single readable silhouette where possible, with stems/leaves/crowns physically attached to the fruit body.
- No object may touch the image edge.
- Background must be one uniform flat #FF00FF, with no gradients, texture, shadows, or lighting variation.
  ```
- layout: 3-object horizontal triplet: whole fruit, left sliced half, right sliced half

**Hints**
- For long curved fruit, make generous horizontal spacing mandatory so cut does not merge the triplet into one component.

### fruit_orange_raw
- reference: art-pack-assets/reference.webp
- prompt
  ```
Use image 1 as the visual style reference only: high-saturation stylized cartoon runtime sprites, crisp readable silhouettes, juicy polished fruit rendering, clean arcade look.

Create a runtime fruit sprite triplet sheet on a perfectly flat solid #FF00FF magenta chroma-key background.
Canvas: 1536x1024 landscape.
Layout: exactly three separate sprite objects in one horizontal row with generous magenta space between them and around every object. No frame borders, no grid lines, no labels, no text.
From left to right: 1) whole Orange sprite, 2) left sliced half sprite, 3) right sliced half sprite.
Subject: round bright orange with pebbled peel, juicy orange segment cut face, elastic bouncy fruit.
Critical runtime constraints:
- The whole fruit, left half, and right half are separate transparent-PNG style runtime sprites; each must be fully visible and isolated.
- The sliced halves must visually match the whole fruit: same peel/shell colors, same material style, same cut flesh colors, matching cut angle and believable paired left/right halves.
- Do NOT include any juice, splashes, droplets, pulp particles, motion streaks, trails, labels, UI, shadows, contact shadows, floor, table, basket, hands, knife, or background art.
- The fruit body sprites must be clean and dry; juice VFX will be separate assets.
- Keep every sprite connected as a single readable silhouette where possible, with stems/leaves/crowns physically attached to the fruit body.
- No object may touch the image edge.
- Background must be one uniform flat #FF00FF, with no gradients, texture, shadows, or lighting variation.
  ```
- layout: 3-object horizontal triplet: whole fruit, left sliced half, right sliced half

### fruit_pineapple_raw
- reference: art-pack-assets/reference.webp
- prompt
  ```
Use image 1 as the visual style reference only: high-saturation stylized cartoon runtime sprites, crisp readable silhouettes, juicy polished fruit rendering, clean arcade look.

Create a runtime fruit sprite triplet sheet on a perfectly flat solid #FF00FF magenta chroma-key background.
Canvas: 1536x1024 landscape.
Layout: exactly three separate sprite objects in one horizontal row with generous magenta space between them and around every object. No frame borders, no grid lines, no labels, no text.
From left to right: 1) whole Pineapple sprite, 2) left sliced half sprite, 3) right sliced half sprite.
Subject: golden pineapple with connected spiky green crown, rough diamond shell, fibrous yellow cut face, sturdy hard-shell fruit.
Critical runtime constraints:
- The whole fruit, left half, and right half are separate transparent-PNG style runtime sprites; each must be fully visible and isolated.
- The sliced halves must visually match the whole fruit: same peel/shell colors, same material style, same cut flesh colors, matching cut angle and believable paired left/right halves.
- Do NOT include any juice, splashes, droplets, pulp particles, motion streaks, trails, labels, UI, shadows, contact shadows, floor, table, basket, hands, knife, or background art.
- The fruit body sprites must be clean and dry; juice VFX will be separate assets.
- Keep every sprite connected as a single readable silhouette where possible, with stems/leaves/crowns physically attached to the fruit body.
- No object may touch the image edge.
- Background must be one uniform flat #FF00FF, with no gradients, texture, shadows, or lighting variation.
  ```
- layout: 3-object horizontal triplet: whole fruit, left sliced half, right sliced half

**Hints**
- For crowned fruit, require leaves/crowns to remain physically attached to the fruit body. Detached crowns cut as separate components and become packaging cleanup.

### fruit_coconut_raw
- reference: art-pack-assets/reference.webp
- prompt
  ```
Use image 1 as the visual style reference only: high-saturation stylized cartoon runtime sprites, crisp readable silhouettes, juicy polished fruit rendering, clean arcade look.

Create a runtime fruit sprite triplet sheet on a perfectly flat solid #FF00FF magenta chroma-key background.
Canvas: 1536x1024 landscape.
Layout: exactly three separate sprite objects in one horizontal row with generous magenta space between them and around every object. No frame borders, no grid lines, no labels, no text.
From left to right: 1) whole Coconut sprite, 2) left sliced half sprite, 3) right sliced half sprite.
Subject: dark brown hairy coconut shell, thick white coconut meat cut face, hard heavy cracked fruit.
Critical runtime constraints:
- The whole fruit, left half, and right half are separate transparent-PNG style runtime sprites; each must be fully visible and isolated.
- The sliced halves must visually match the whole fruit: same peel/shell colors, same material style, same cut flesh colors, matching cut angle and believable paired left/right halves.
- Do NOT include any juice, splashes, droplets, pulp particles, motion streaks, trails, labels, UI, shadows, contact shadows, floor, table, basket, hands, knife, or background art.
- The fruit body sprites must be clean and dry; juice VFX will be separate assets.
- Keep every sprite connected as a single readable silhouette where possible, with stems/leaves/crowns physically attached to the fruit body.
- No object may touch the image edge.
- Background must be one uniform flat #FF00FF, with no gradients, texture, shadows, or lighting variation.
  ```
- layout: 3-object horizontal triplet: whole fruit, left sliced half, right sliced half

### fruit_strawberry_raw
- reference: art-pack-assets/reference.webp
- prompt
  ```
Use image 1 as the visual style reference only: high-saturation stylized cartoon runtime sprites, crisp readable silhouettes, juicy polished fruit rendering, clean arcade look.

Create a runtime fruit sprite triplet sheet on a perfectly flat solid #FF00FF magenta chroma-key background.
Canvas: 1536x1024 landscape.
Layout: exactly three separate sprite objects in one horizontal row with generous magenta space between them and around every object. No frame borders, no grid lines, no labels, no text.
From left to right: 1) whole Strawberry sprite, 2) left sliced half sprite, 3) right sliced half sprite.
Subject: small bright red strawberry with connected green leaves, pale red cut flesh, tiny yellow seeds, fast light fruit.
Critical runtime constraints:
- The whole fruit, left half, and right half are separate transparent-PNG style runtime sprites; each must be fully visible and isolated.
- The sliced halves must visually match the whole fruit: same peel/shell colors, same material style, same cut flesh colors, matching cut angle and believable paired left/right halves.
- Do NOT include any juice, splashes, droplets, pulp particles, motion streaks, trails, labels, UI, shadows, contact shadows, floor, table, basket, hands, knife, or background art.
- The fruit body sprites must be clean and dry; juice VFX will be separate assets.
- Keep every sprite connected as a single readable silhouette where possible, with stems/leaves/crowns physically attached to the fruit body.
- No object may touch the image edge.
- Background must be one uniform flat #FF00FF, with no gradients, texture, shadows, or lighting variation.
  ```
- layout: 3-object horizontal triplet: whole fruit, left sliced half, right sliced half

**Hints**
- For small fruit, still generate at the same raw canvas scale as other fruits. Runtime can downscale; source should retain readable seeds and cut face.

## Independent slice VFX

### vfx_juice_raw
- reference: art-pack-assets/reference.webp
- prompt
  ```
Use image 1 as visual style reference only: high-saturation stylized cartoon arcade VFX, crisp readable shapes, glossy liquid highlights, runtime-composable transparent PNG sprite language.

Create a 5x4 atlas-style sheet of independent juice / pulp / droplet / streak VFX sprites on a perfectly flat solid #00FF00 chroma-key background.
Canvas: 1536x1024 landscape.
Layout: 5 columns x 4 rows, one independent VFX cluster per cell, generous green space between cells, no borders, no grid, no text.
Rows / color families:
Row 1: red apple/strawberry juice VFX - small burst, droplets, short streak, pulp dots.
Row 2: watermelon red pulp VFX - larger watery splash, red droplets, black seed/pulp bits, short burst trail.
Row 3: orange juice VFX - orange droplets, citrus splash, small bead clusters, short arc trail.
Row 4: yellow banana/pineapple and white coconut fragments - yellow smear/streak, yellow fibrous bits, pale coconut chips, white droplets/fragments, mixed small sparkle-free debris.
Critical runtime constraints:
- Every VFX cell must be a separate sprite-like cluster that could be cut out and spawned independently.
- Keep detached droplets tightly grouped within each cell, with clear separation between cells.
- Do not draw fruit bodies, fruit halves, bomb, slash trail, UI, labels, text, hands, knife, floor, table, or background art.
- Keep all liquid pieces on the green background only; no shadows, no contact shadows, no integrated painting across cells.
- Background must be uniform #00FF00 with no gradients, no texture, no lighting variation.
  ```
- layout: 5x4 atlas-style sheet of independent juice / pulp / droplet / streak clusters

**Hints**
- Use a marker color that does not conflict with liquid color. This project used #00FF00 for red/yellow/orange/white VFX because magenta was not needed and green was easy to remove.
- Group detached droplets tightly within each cell. If droplets spread across cell boundaries, auto-cut creates merged or fragmented sprites.

## Hazards and UI icons

### hazards_slash_ui_raw
- reference: art-pack-assets/reference.webp
- prompt
  ```
Use image 1 as visual style reference only: high-saturation stylized cartoon runtime sprites, crisp arcade readability, polished but implementation-ready.

Create a runtime sprite atlas sheet on a perfectly flat solid #FF00FF magenta chroma-key background.
Canvas: 1536x1024 landscape.
Layout: 3 rows x 4 columns, one independent sprite or VFX per cell, generous magenta space between cells, no borders, no grid lines.

Row 1 - bomb and explosion:
1. idle bomb sprite: dark metal round bomb, red warning triangle symbol, fuse unlit or tiny ember, clearly not a fruit.
2. warning/fuse bomb sprite: same bomb identity, fuse glowing brighter, small warning rim glow, still a separate intact bomb.
3. explosion ignition VFX: compact orange/yellow blast start, no bomb body required.
4. explosion peak VFX: larger stylized orange/red blast cloud and sparks, transparent-sprite style.

Row 2 - slash trail VFX:
1. short cyan-white slash trail, tapered curved blade streak, transparent-looking glow.
2. medium cyan-white slash trail, longer curved blade streak, tapered ends.
3. long cyan-white slash trail arc, bright core, soft blue glow, runtime VFX style.
4. secondary pale slash glint / small blade sparkle cluster.

Row 3 - UI sprite experiment:
1. top-right miss X / cross mark sprite, red-orange thick arcade cross with subtle dark outline.
2. miss X used/dim variant, darker red or purple muted cross.
3. small pause icon sprite, rounded dark translucent square with two light bars, simple UI chrome.
4. small combo burst badge background, no text, orange/yellow decorative burst for score pop.

Critical constraints:
- Each cell must contain a separate isolated runtime sprite or VFX cluster, fully inside the cell with generous magenta margin.
- No fruit, no juice, no score numbers, no BEST text here, no labels, no captions.
- No shadows, no floor, no table, no background art.
- Background must be uniform flat #FF00FF with no gradients, no texture, no lighting variation.
  ```
- layout: 3x4 mixed atlas: bomb states, explosion VFX, slash glints, miss X icons, pause/combo experiments

**Hints**
- The load-bearing outputs were bomb idle, bomb warning, bomb explosion ignition/peak, and miss X active/dim. Slash pieces were demoted to optional hit flash because the core slash trail was better as runtime vector graphics.
- Mixed utility sheets are acceptable only when every cell is a separate isolated runtime sprite and there is enough marker spacing for cuts. Do not use this pattern for final score digits; the digit experiment failed due clipping, adjacent bleed, missing 0, and split BEST.
