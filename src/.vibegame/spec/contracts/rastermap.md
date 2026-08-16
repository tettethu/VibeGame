# Raster Map Contract

Single painted / generated background image with invisible physics colliders aligned to visible terrain.

## Pattern 1: rastermap

### When to use

Use when a level / arena is one bespoke image, not reusable tiles:
- side-view arena
- boss room
- fixed-screen platform slice
- hand-painted top-down room with explicit collision

Do not use for reusable tile grids or procedural room layouts; use [`tilemap.md`](tilemap.md).

### Responsibility

#### Orchestrator

- In `prd.md` `Reuse / Constraints`, write: `Use rastermap pattern rastermap because <task-specific reason>.`
- Commission artist with `map_pattern: rastermap`.
- Name required landmarks: ground line, platform bboxes, wall bounds, arena bounds, and kill zones if needed.
- If this is the first map-touching task, treat `rastermap` as the project map architecture until a project-wide refactor changes it.

#### Artist

- Produce one background PNG that includes the visible terrain.
- Estimate required landmarks with `vibegame art label` and VLM confirmation.
- Write final landmark estimates into `assets/manifest.json` under the image asset's `landmark` block.
- Do not write scene JSON.

##### Workflow

1. Generate
   - Create the background image with visible terrain, platforms, walls, and bounds.
2. Package
   - Register the image in `assets/manifest.json`.
   - Add `landmark.markY`, `landmark.markX`, and `landmark.bbox` entries for requested terrain features.
3. Verify
   - Use `vibegame art label` overlays plus VLM yes/no checks until each landmark is visually aligned.

#### Architect

- Read the manifest `landmark` block.
- Convert source-image pixel landmarks to world-space collider positions.
- Plan invisible static colliders only; terrain art stays in the background image.
- If required landmarks are missing, report `[MISSING LEAD DECISION] rastermap landmarks: <list>` or `[ASSETS GAP] <asset/key>` as appropriate.

#### Programmer

- Add the background image node.
- Add map colliders as `script: "Collider"` nodes with `collider.body: "static"` and no `visual` field.
- Do not add visible rect / circle / image placeholders for map collision.
- Keep collider names stable so player can tune them at runtime.

Example invisible raster-map colliders:

```json
{
  "name": "Ground",
  "script": "Collider",
  "tags": ["ground"],
  "collider": { "body": "static", "width": 1440, "height": 40 },
  "config": { "x": 720, "y": 446 }
},
{
  "name": "WallLeft",
  "script": "Collider",
  "tags": ["wall"],
  "collider": { "body": "static", "width": 20, "height": 540 },
  "config": { "x": 35, "y": 270 }
}
```

#### Player

- Run the game and tune collider positions live via Runtime API.
- Use screenshots plus VLM yes/no checks:
  - feet on visible ground: on / above / below
  - platform contact: on / above / below
  - wall stop: at edge / before / past
- Persist final collider values to scene JSON after convergence.
- Save before/after screenshots and VLM verdicts as evidence.

#### Reviewer

- Reject if terrain colliders are visible in normal runtime.
- Reject if player feet float or sink relative to visible ground / platforms.
- Reject if wall collision stops before or past the visible wall edge.
- Use external VLM verdicts for raster alignment checks.

### Manifest and asset boundary

`landmark` metadata is written on the image asset:

```json
{
  "forest-arena": {
    "type": "image",
    "path": "levels/forest-arena.png",
    "landmark": {
      "bbox": {
        "left-ledge": { "x": 430, "y": 630, "w": 260, "h": 30 }
      },
      "markY": {
        "ground": 840
      },
      "markX": {
        "left-bound": 60,
        "right-bound": 1860
      }
    }
  }
}
```

Rules:
- `landmark` is metadata for agents; the engine does not consume it.
- Coordinates are source-image pixels, top-left origin.
- Colliders are physics-only and invisible in normal runtime: use `script: "Collider"` with a `collider` field and no `visual` field.
- `vibegame run --debug` may show physics bodies for evidence; do not enable debug visuals in project config.
- The engine never infers collision from image pixels.
