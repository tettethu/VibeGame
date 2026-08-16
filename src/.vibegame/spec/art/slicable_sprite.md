# Slicable Sprite

Use this for any 2D runtime asset that can be sliced, split, broken, chopped, or divided into independently moving pieces. Typical subjects: fruit, vegetable, crate, rock, coconut, vase, ice block.

## Core Rule

Do not make a slicable object as one illustration with baked-in effects. It must be generated as clean runtime-composable body parts:

- `whole`: the intact object before slicing.
- `left`: the left half or first main body shard after slicing.
- `right`: the right half or second main body shard after slicing.
- independent VFX: juice, dust, sparks, pulp, shell chips, droplets, slash hit flash. Generate these as separate VFX assets. Do not bake them into the body sprites.

## Raw Generation Pattern

Default raw generation shape: a horizontal triplet sheet.

- canvas: landscape.
- layout: exactly three separate sprite objects in one horizontal row.
- order: `whole`, `left`, `right`.
- background: flat pure marker color, usually `#FF00FF`.
- spacing: enough marker-color gap between all three objects so auto-cut does not merge them.

Prompt template:

```text
Use the input image as the visual style reference only: <style>.

Create a runtime slicable object sprite triplet sheet on a perfectly flat solid #FF00FF chroma-key background.
Layout: exactly three separate sprite objects in one horizontal row with generous marker-color space between them and around every object. No frame borders, no grid lines, no labels, no text.
From left to right: 1) whole <object> sprite, 2) left sliced half sprite, 3) right sliced half sprite.
Subject: <object visual identity>.
Critical runtime constraints:
- The whole object, left half, and right half are separate transparent-PNG style runtime sprites.
- The sliced halves must visually match the whole object: same outer colors, same material style, same outline language, same interior material colors, matching cut angle, and believable paired left/right halves.
- Do NOT include any hit VFX, liquid, splashes, droplets, dust, sparks, pulp, fragments, motion streaks, trails, labels, UI, shadows, floor, table, hands, weapon, or background art.
- The body sprites must be clean and dry; feedback VFX will be separate assets.
- Keep attached parts physically attached to the main body where possible.
- No object may touch the image edge.
- Background must be one uniform flat marker color, with no gradients, texture, shadows, or lighting variation.
```

## Matching Rules

The halves are useful only if players believe they came from the whole sprite. Check these before delivery:

- outer silhouette family matches the whole.
- palette and material language match the whole.
- cut face colors and texture match the object interior.
- left and right halves look like a pair, not two unrelated variants.
- stems, leaves, crowns, caps, labels, handles, or shell details stay attached unless the design explicitly needs detached fragments.
- no juice, dust, spark, or impact burst is baked into body sprites.

## Boundary

This file only defines the raw-generation prompt template and prompt-side rules for slicable body sprites.

Do not put background removal, cutout, crop, bbox, manifest registration, or final packaging steps here. Those belong in the relevant contract's Artist workflow, the project's asset workflow, or the CLI docs.

The expected raw output is still a triplet sheet that can later produce three runtime body assets:

- `<object>_whole`.
- `<object>_left`.
- `<object>_right`.

Independent feedback VFX must be generated as separate raw assets, not baked into the body triplet.

Common fail cases:

- juice or impact burst baked into the fruit or object body.
- left and right halves use different cut angles or different material style.
- half sprites look like separate whole objects rather than broken pieces.
- detached leaves or small parts become separate cut components.
- marker-color halo remains after background removal.
