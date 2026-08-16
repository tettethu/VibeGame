# Parallax Background

Cross-role contract for building a scrolling multi-layer parallax background from independently generated art layers, driven by `ParallaxModule`.

## Pattern 1: scrolling-parallax-layers

### When to use

Produces a depth-layered scrolling background for a side-view scene: several sibling `ParallaxModule` nodes, each a full-width `TileSprite` of one independently generated transparent layer, each with its own `scrollFactorX` and `depth` (and optional `driftX` self-scroll). Runtime behavior: as the camera scrolls horizontally the layers move at different rates — near layers track the camera, far layers lag, a pinned sky stays fixed — producing a parallax depth illusion; `driftX` layers (clouds, water) also self-scroll while the camera is still.

IO shape: input is N registered layer textures (plain image or atlas frames) + per-layer `scrollFactor`/`depth`/`driftX`; output is the on-screen layered background plus each node's `runtimeState()` for verification. No collision, no game state, no events.

Coordination boundary: artist produces the layers (independently generated, transparent, horizontally tileable), the code side wires one `ParallaxModule` node per layer, player verifies differential scroll. Practice-verified in a side-scrolling precision-platformer (bounce parkour) with a pinned gradient sky + drifting cloud layers + two hill silhouette layers.

Not for playable terrain: ground/platforms the player collides with are authored as their own collider sprites or a `rastermap` asset, never baked into a parallax layer.

### Responsibility

#### Artist

Artist owns one independently generated image layer per depth plane: a back-most opaque sky/gradient plus each transparent, horizontally-tileable decorative plane (far/near clouds, hill silhouettes, etc.). Hard rule (user-locked): every depth plane is its own generation — never a single generated base with hand-drawn or code-drawn pixels added on top; that mixed approach reads as crude and is exactly what this pattern corrects. This chapter is self-contained — the layer prompt recipe is inlined below.

##### Workflow

1. **Generate**

   One `vibegame art gen image` call per depth plane — never composite planes into one image. Pass the project style anchor as `-i` on every call for cohesion. Author back-to-front:

   - **sky** (back-most, opaque, full canvas): atmosphere only (gradient / glow band), NO clouds / hills / ground / props baked in. Opaque, edge-to-edge, no marker background — the image itself is the layer.
   - **far decorative plane** (transparent): the distant motif only (e.g. far clouds), low contrast + desaturated, on a flat pure `#FF00FF` marker background. May contain several instances of the motif laid out for tiling, but it is still one plane.
   - **near decorative plane** (transparent): the closer motif only (e.g. hill silhouettes), higher contrast than the far plane, on flat marker background. Ground-hugging silhouette strips need a flat horizontal bottom edge (the base that seats on the horizon) with variation only on the top edge, and a motif rhythm distinct from the far plane.
   - Playable terrain (ground / platforms the player collides with) is NOT a parallax plane — author it as its own collider sprite / `rastermap` asset. Parallax planes are non-colliding decoration only.

   Templated prompt — opaque back-most sky plane (theme / palette / gradient treatment may be replaced; keep the content-isolation and opacity constraints):

   ```text
   Use the input image as the visual style reference only: <style>.

   Generate a single opaque full-canvas <time-of-day> sky layer, back-most parallax plane.
   Content: <top-color> at the top transitioning to <horizon-color> near the bottom, <style-specific gradient treatment>.
   Do NOT include clouds, hills, mountains, ground, platforms, characters, props, text, watermark, or UI — those are separate layers.
   Fully opaque, edge-to-edge. No transparency, no marker background.
   ```

   Templated prompt — transparent, horizontally-tileable decorative plane (motif / contrast / depth cue may be replaced; keep the tiling, single-motif, and marker-background constraints):

   ```text
   Use the input image as the visual style reference only: <style>.

   Generate one <layer-name> parallax layer strip on a perfectly flat solid #FF00FF chroma-key background.
   Subject: <layer motif, e.g. distant rolling hill silhouette / soft cartoon clouds>, spanning the full width of the strip as a horizontally-repeating band.
   Depth cue: <low-contrast + desaturated for far planes; higher-contrast for near planes>.
   Horizontal tiling: the left edge and the right edge must match — motif density, base-line height, and edge shapes at the two ends must line up so copies placed side by side form one seamless continuous band with no visible seam.
   Do NOT bake in the sky gradient, other depth layers, ground, platforms, characters, props, text, labels, UI, or a frame border.
   Background is 100% flat #FF00FF only — no gradient, no texture, no shadow. Leave the marker color everywhere the layer is transparent.
   ```

2. **Package**

   Keep post-processing gentle — the goal is to lift the generated layer onto transparency, not to re-render it. Preserve the generated palette and its shaded (soft, but not blurry) look; do not quantize / posterize / hard-flatten a good multi-color layer down to a few flat colors during cleanup.

   - Chroma-key each transparent plane; the opaque sky skips this:
     ```sh
     vibegame art rmbg <plane>_raw.png --agent -o <plane>.png
     ```
   - If a plane's raw sheet holds multiple motif instances / variants, cut then concat into a compact atlas; single-motif planes are used as-is:
     ```sh
     vibegame art cut <plane>_clean.png --agent -o bboxes.json --preview
     vibegame art concat ./frames/ -o <plane>.png --layout row --spacing 2
     ```
   - Move finals into `assets/...`; register one manifest entry per depth plane (plain `image` for a single-motif plane, `atlas` for a multi-frame plane). Layers are decorative and carry NO collider. The sky/gradient base is a distinct entry from clouds and hills — one entry per plane, never a composited image.
   - Node shape consumed by the module: one `ParallaxModule` node per layer, sibling under a `Background` node (see the Architect / Programmer chapter for `scrollFactorX` / `depth` / `driftX` / `width` wiring — artist does not set those).

3. **Verify**

   - **Tileability**: place two copies of each scrolling plane edge-to-edge and confirm the seam is invisible (matching edge motif + baseline). Regenerate the plane if the ends do not match — never hand-fix the seam.
     ```sh
     vibegame art label <plane>.png --xline <width> -o /tmp/seam.png
     vibegame vlm /tmp/seam.png -t "Two copies of this layer are placed side by side at the marked line. Is the join seamless, with no visible break in the motif or baseline? Answer yes or no."
     ```
   - **Transparency / halo**: composite each transparent plane over a contrasting solid and confirm no marker-color halo remains around the motif.
   - **Smoothness preserved**: compare the packaged layer against the raw generation — it must keep the same palette richness and shading smoothness. Ragged hard-stepped edges or lost shading mean cleanup over-quantized the layer; redo the packaging gently.
   - **Depth-distinct motifs**: confirm far planes are lower-contrast than near planes and each plane uses a different motif rhythm (two identical rhythms read as one flat plane).
   - **Content isolation**: confirm the sky plane has no clouds / hills baked in, and no playable terrain / collider surface is baked into any plane.

Common mistakes:

- Building the backdrop as one generated base image with clouds / hills / details hand-painted or code-drawn on top (the crude mixed approach the user explicitly rejected) — regenerate as separate planes.
- Over-quantizing / hard-flattening a good generated layer during Package (e.g. crushing a richly-shaded silhouette down to 2 flat colors) — it produces ragged hard-stepped edges and lost shading. Keep chroma-key / cut / concat gentle and preserve the raw generation's palette and smoothness.
- Baking clouds or hills into the sky plane, so they cannot scroll at their own rate.
- A scrolling plane whose left and right ends do not match, producing a visible seam every loop.
- A ground-hugging silhouette plane with an organic (non-flat) bottom edge that fails to seat on the horizon and jitters when scrolled.
- Two depth planes with identical motif rhythm, so the parallax reads as one flat plane.
- Baking playable terrain into a parallax layer instead of authoring it as its own collider sprite / `rastermap` asset.
- Attaching a collider to a parallax layer (they are decoration only).
- Marker-color halo left around a transparent plane after background removal.

#### Architect / Programmer

- Use `ParallaxModule` (`script: "ParallaxModule"`); do not re-implement TileSprite wiring per project.
- One node per depth layer, placed as siblings under a `Background` node. Order by `depth` (further layers more negative; a pinned sky is the most negative).
- Set `scrollFactorX` per layer: `0` for a viewport-pinned sky, small values (`0.1`–`0.3`) for far layers, up to `~0.5` for near layers. Adjacent layers must differ in `scrollFactor` or the parallax reads as one flat plane.
- Set `width` to span the full camera-scroll range (several screen-widths), not one screen — a `TileSprite` repeats its texture, so a wide extent keeps the layer covering the whole level. `height` may be omitted to derive from the frame.
- Use `driftX` (px/s) only for layers meant to self-scroll (clouds, water); leave it `0` for terrain-anchored silhouettes.
- Keep the sky/gradient layer as a plain image layer; do not bake clouds or hills into it, or they cannot scroll at their own rate.
- Never place a collider on a parallax layer and never route playable terrain through it.

#### Player

- Snapshot the parallax nodes' `runtimeState()` and assert adjacent layers report **different** `scrollFactorX` (proves depth separation is configured, not a flat plane).
- For `driftX` layers, advance frames and assert `tilePositionX` increases over time (self-scroll works).
- Drive the camera (move the player / scroll) some frames, then assert far layers have shifted less than near layers on screen (differential parallax). A before/after screenshot pair is the visual evidence.

#### Reviewer

- Background reads as layered depth in motion, not a flat backdrop.
- No visible seam when a layer loops, and no marker-color halo around transparent layers.
- Playable terrain is visually and structurally separate from the parallax layers.

### Manifest and asset boundary

- Each parallax layer is registered as its own manifest entry (plain image or an atlas frame); layers are decorative and carry no collider.
- The sky/gradient base is a distinct layer from clouds and hills — one generated layer per depth plane, never a single composited image.
- Playable terrain (platforms, ground the player stands on) is a separate collider sprite or `rastermap` asset and must not be part of any parallax layer.
