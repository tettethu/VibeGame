# Tilemap Contract

## Pattern 1: tilemap

### When to use

This pattern comes from a top-down dungeon roguelike. It has been verified for random room layouts where rooms are connected by corridors, doors close when the player enters a room, and doors open or disappear after all enemies in the room are cleared.

This pattern achieves:

- A tilemap-based dungeon room built from a tileset with 6 floor tiles, 2 wall tiles, and 1 door tile.
- A room visual where floors fill the room area, rectangular wall blocks enclose the room, pieces align tightly, lower walls partially occlude upper doors/walls to suggest a tilted view, and door objects with wall-like shape and height, such as pillars or spikes, follow the same occlusion rule. When the player enters a room with enemies, doors appear and block the exits. After enemies are cleared, the doors disappear.

This pattern does not cover:

- A single hand-painted background with hand-authored colliders.
- A non-grid freeform map.
- The full implementation details of a complete random dungeon algorithm. Keep that in project-local design / implementation docs.

### Basic Knowledge

Game engines usually support fixed-size square tiles in a tilemap. To make non-square wall/door sprites usable in that tilemap, use this structure:

1. Resize the raw wall/door sprite to `w x h`, where `w = tileSize` and `h` is between `1x` and `2x tileSize`. It must be taller than the floor tile, but if it is taller than `2x`, the visual result usually looks wrong.
2. Split each wall/door horizontally into two uneven tiles: `face(tileSize x tileSize)` + `top(tileSize x (h - tileSize))`. The `top` tile does not fill its whole tile cell. Its visible content sits near the lower part of the tile. Then place `wall_face` / `door_face` at each wall/door face position, place the matching `top` tile in the grid cell above that face, and set depth to `wall_top = door_top > wall_face = door_face > floor`.
3. With this setup, every wall that has another wall below it will have the lower wall column's `top` tile covering the lower part of its face cell. It is not literally half, but visually it reads like tilted-view occlusion.

**Follow this principle. It is the strongest prior for implementing this pattern.**

Output:

- A tilemap that can be rendered in game.
- Stable visual depth between floor / wall / door.
- Usable collision boundaries for wall / door.
- Corridors that connect rooms.
- Doors that can close after room entry and open after enemies are cleared.

### Responsibility

#### Artist

The artist is responsible for creating the tileset image and labeling the meaning of each tile.

##### Workflow

1. **Generate**

   Use the verified prompt below as a strong prior for tileset raw generation. Material, palette, theme, and per-cell content may be replaced, but do not remove the constraints on projection, footprint, cuboid silhouette, or per-cell description.

   ```text
   A pixel-art dungeon SPRITE SHEET arranged in a 3x3 grid on a solid magenta background. Nine independent dungeon-tile sprites on pure magenta (#FF00FF) marker background. Each sprite sits centered inside its own cell with a clear magenta margin.

   PERSPECTIVE RULE (most important, read carefully):
   This sheet uses a STYLIZED 45-DEGREE TOP-DOWN tile projection (like Pokemon dungeons, Stardew Valley dungeons, or classic 16-bit JRPG dungeons). Critically, this is ORTHOGRAPHIC, NOT true 3D oblique projection. Specifically:

   - ROW 1 sprites (walls and door) are CUBOID BLOCKS. Each cuboid is drawn as TWO STACKED RECTANGULAR REGIONS:
     - The UPPER ~25 PERCENT of the cuboid sprite is the TOP face, drawn as a clean horizontal rectangle representing the cuboid's top surface seen from a slight overhead angle.
     - The LOWER ~75 PERCENT of the cuboid sprite is the FRONT face, drawn as a clean rectangle representing the cuboid's front surface.
   - CRITICAL ALIGNMENT RULE: The TOP face and the FRONT face MUST be the EXACT SAME WIDTH. Their LEFT edges align on the same vertical line, and their RIGHT edges align on the same vertical line. The cuboid's overall silhouette is a CLEAN VERTICAL RECTANGLE, not a parallelogram, not a trapezoid, not a 3D box with oblique skew.
   - The top face is NOT drawn as a tilted parallelogram receding into the distance. It is a flat horizontal strip at the top of the sprite, with markings (texture, mortar lines) that simply hint that this surface is "up there" rather than using perspective foreshortening.
   - The transition between top face and front face is a single clean horizontal line.
   - You do NOT see the side faces of the cuboid.
   - The cuboid sprite outline is a perfect vertical rectangle (like a domino standing upright), with no diagonal edges anywhere on its silhouette.

   - ROW 2 and ROW 3 sprites (floors) are FLAT SQUARE SLABS in PURE STRAIGHT TOP-DOWN view.

   CUBOID FOOTPRINT RULE:
   - Horizontal width of each row-1 cuboid is IDENTICAL to the horizontal width of each row-2 / row-3 floor slab.
   - Each cuboid is a SINGLE solid block (not a stack of multiple stones).
   - No floor visible underneath the cuboid.

   Layout, row by row, left to right:

   Row 1 (orthographic cuboid blocks, top ~25% flat horizontal strip, front ~75% rectangle, no oblique skew):
   - (1,1) Wall block variant A. A single sandstone cuboid block in orthographic 45-degree projection. TOP face (upper 25%): a clean horizontal strip of mid-tan sandstone with subtle weathering speckle, slightly darker than the front face to suggest it is "the top". FRONT face (lower 75%): mid-tan sandstone, with 2-3 small natural cracks, one horizontal mortar line near the middle, slightly darker bottom edge for grounding. The top-front boundary is a single horizontal line. Cuboid silhouette is a clean vertical rectangle.
   - (1,2) Closed door pillar. A single CUBOID STONE PILLAR with the same orthographic projection as the wall blocks. TOP face (upper 25%): dark obsidian-black horizontal strip with a single glowing crimson rune sigil. FRONT face (lower 75%): same dark obsidian-black stone with 2-3 short glowing crimson rune lines etched horizontally. Cuboid silhouette is a clean vertical rectangle, the SAME outline shape as the wall blocks.
   - (1,3) Wall block variant B. Same wall family as A: same sandstone palette, same orthographic projection, same clean vertical rectangle silhouette. Visually distinct: chipped top-right corner (the chip is a small notch out of the top-right of the top face), one longer diagonal crack across the front face, one small embedded pebble.

   Row 2 (flat square floor slabs, pure straight top-down view):
   - (2,1) Floor tile 1. Plain warm-sandstone floor slab. Square outline. Dark mortar grid along the slab edges. Subtle surface speckle.
   - (2,2) Floor tile 2. Same flat floor base, with one prominent zig-zag crack running diagonally.
   - (2,3) Floor tile 3. Same flat floor base, with a small square drain grate set INTO the floor: four dark iron bars over a recessed black hole, flush with surface.

   Row 3 (more flat square floor slabs):
   - (3,1) Floor tile 4. Same flat floor base, with a small skeletal hand-bone fragment lying flat.
   - (3,2) Floor tile 5. Same flat floor base, with a thin moss patch growing along one mortar seam.
   - (3,3) Floor tile 6. Same flat floor base, with a dried crimson bloodstain.

   Visual contrast (mandatory):
   - All 9 sprites have the SAME horizontal width (same base footprint).
   - Row 1 cuboids each have a CLEAN VERTICAL RECTANGLE outline (no oblique edges, no parallelogram top, no perspective skew).
   - Row 1 cuboids show top + front as two stacked horizontal regions of the SAME WIDTH, separated by a single horizontal line.
   - Row 2 + Row 3 floors are flat squares.
   - The cuboid silhouettes should look like upright dominoes — rectangular, vertical, no diagonal edges anywhere on the outline.

   Style: pixel art, chunky readable pixels, integer pixel scale, crisp dark 1-pixel outlines, limited warm-stone palette (sandstone tans for walls; deep mortar browns; charcoal shadows; dark obsidian-black for door with crimson rune accents; bone-white, olive-green, dried-crimson floor accents). Soft top-down ambient light.

   Strict rules:
   - Exactly 9 sprites in a 3x3 grid. No extra sprites, no missing sprites.
   - Each sprite centered within its 1/9 share of the canvas with at least 10% magenta margin per side.
   - All 9 sprites share the SAME horizontal width within their cells.
   - Row 1 cuboid silhouettes are CLEAN VERTICAL RECTANGLES — every edge of the silhouette is either purely vertical or purely horizontal. NO diagonal edges on any cuboid's outer silhouette.
   - Row 1 cuboid total height is modestly greater than row 2/3 floor slab height (because of added top strip), but not dramatically taller.
   - No sprite crosses into a neighboring cell.
   - No magenta pixels INSIDE any sprite.
   - No text, no labels, no numbers, no UI, no HUD, no speech bubbles.
   - No frames, no decorative box, no grid lines drawn on the magenta.
   - Background between and around sprites is solid flat magenta only.
   ```

   The key part of this prompt is not the "sandstone dungeon" theme. The key constraints are:

   - A 3x3 sparse raw sheet, with one independent tile sprite per cell.
   - Row 1 contains wall / door cuboids.
   - Rows 2/3 contain floor square slabs.
   - Wall / door and floor share the same footprint.
   - The top face and front face of each wall / door have the same width.
   - Every cell has an explicit semantic description.

2. **Package**

   The artist delivers the tileset image and a tile inventory.

   The tile inventory must at least state:

   - The name of each tile.
   - The category of each tile: floor, floor variant, wall_top, wall_face, door_top, door_face.
   - Which `wall_top` matches which `wall_face`.
   - Which `door_top` matches which `door_face`.
   - Which floor tile is the main tile, and which floors are variants.
   - Which tiles should have collision, and which are visual-only layers.

   Wall / door must not be delivered as a single tall tile. They must be split into two tile categories:

   - `<name>_top`: the upper visual part, rendered at a higher depth.
   - `<name>_face`: the lower physical part, usually carrying collision.

   `top` and `face` must come from the same cuboid visual body. They should not look like unrelated assets.

3. **Verify**

   Check before delivery:

   - `wall_top` and `wall_face` combine into one wall body.
   - `door_top` and `door_face` combine into one door body.
   - The horizontal footprint of wall / door matches the floor tile.
   - Wall / door did not turn into thin pillars, spikes, steles, or skewed perspective boxes.
   - Floor variants still read as the same floor family and do not turn the room into a noisy carpet.
   - Each tile has clear semantics, so the programmer does not have to guess.

Common mistakes:

- Making wall / door as one tall sprite and expecting one tile to render as two tiles high.
- `wall_top` and `wall_face` do not belong to the same visual body.
- `door_top` and `door_face` do not share a visual language with the wall family.
- Floor variants are too many or too strong, stealing focus from walls and doors.
- Delivering only an image without a tile inventory.
- Asking the model for a packed semantic tileset that is already engine-ready. This path is unstable.

#### Architect / Programmer

The architect / programmer is responsible for implementing the tileset as an in-game tilemap and room flow.

Core invariants:

- The map uses a square-grid tilemap.
- Floor, face, and top must at least visually satisfy `top > face > floor`, meaning that when they overlap, top covers face and face covers floor.
- The `top` tile of a wall / door renders above its `face` tile.
- Collision is usually attached to `face`, not `top`.
- Floors are laid with one main floor tile and a low ratio of floor variants.
- Rooms are connected by corridors.
- Walls are generated around rooms.
- Walls are also generated along both sides of corridors.
- Door uses the same top / face structure as wall.
- After the player enters a room, doors appear or close.
- After all enemies in the room die, doors disappear or open.

Layout model:

The diagram below shows tile semantics for one room connected to a vertical corridor at its bottom side. It does not require the engine to implement this with a single TileMap node or a single layer.

Symbols:

- `.` = floor only.
- `F` = floor + wall_face, with no wall_top covering this cell.
- `W` = floor + wall_face + wall_top, meaning this cell has its own face and is also covered by the top of a neighboring wall column.
- `D` = floor + door_face + door_top.
- `d` = floor + door_face + wall_top, used only when a door explicitly reuses `wall_top`. Default to `D`.
- `+` = corridor floor only.

One room connected to a vertical corridor looks roughly like this:

```text
WWWWWWW
W.....W
W.....W
W.....W
FFW.WFF
..W+W..
..W+W..
..W+W..
```

This diagram means:

- The room interior is mostly `.`.
- The room boundary is wall.
- The room entrance keeps a passable gap. It must not be blocked by `wall_face` or `wall_top`.
- When the room is locked, the entrance gap can be replaced by `D` or `d`.
- The corridor connects outside the entrance.
- The middle of the corridor is `+`, and both sides are wall.
- Horizontal and vertical corridors must share one visual language. If corridor tiles are directional, horizontal and vertical forms should be 90-degree rotations of each other. For example, if a horizontal corridor is `wNum x hNum`, the vertical corridor should be `hNum x wNum`.

Implementation hints:

- The verified roguelike skeleton uses one shared world-grid to represent rooms and corridors in a connected dungeon. This does not mean there can only be one TileMap node. It means the main traversable structure should share one tile coordinate system.
- A room can be represented as a tile rectangle.
- A corridor can be represented as a tile strip connecting two room rectangles.
- A helper can place a wall column in one operation: write `wall_face` at the face cell and the matching `wall_top` in the cell above it.
- Door can use the same top / face placement.
- Floor variants should be mixed in at a low ratio. Do not lay them fully at random into a high-noise floor.
- If a project represents each room with an independent tilemap coordinate system, it needs extra handling for corridor connection, wall continuity, collision continuity, and door state synchronization. That is outside the verified scope of this pattern.

#### Player / Reviewer

The player / reviewer is responsible for validating the map in game:

- The player cannot walk through walls or closed doors.
- The player can pass through open doors and corridors.
- Door closing after room entry is clearly visible.
- Doors open or disappear after enemies are cleared.
- Walls read as higher than the floor, not as floor tiles painted flat on the ground.
- `wall_top` / `wall_face` are not misaligned.
- `door_top` / `door_face` are not misaligned.
- There are no half-tile offsets, missing walls, double walls, or visual breaks at room-corridor connections.
- Floor variants do not interfere with the player's ability to read path and collision boundaries.

### Manifest and asset boundary

The tileset manifest must at least express:

- Tileset image.
- Tile size.
- Mapping from tile names to tileset indices.
- Which tiles have collision.
- Optional floor variant category.

Wall / door top and face must be registered as separate tile names. Do not try to encode "this tile is two tiles tall" as one tile entry.

The manifest only describes tile types and asset locations. It does not describe random room layout, enemies, or door runtime state.
