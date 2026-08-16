# Generate2dsprite

Follow this for self-contained 2D sprite or animation assets

## Parameters

Infer these from the user request:

- `asset_type`: `player` | `npc` | `creature` | `character` | `spell` | `projectile` | `impact` | `prop` | `summon` | `fx`
- `action`: `single` | `idle` | `cast` | `attack` | `hurt` | `combat` | `walk` | `run` | `hover` | `jump` | `fall` | `dash` | `bounce` | `charge` | `charge_full` | `charge_release` | `projectile` | `impact` | `explode` | `death`
- `view`: `topdown` | `side` | `3/4`
- `sheet`: `auto` | `1x4` | `2x2` | `2x3` | `3x3` | `4x4`
- `frames`: `auto` or explicit count
- `bundle`: `single_asset` | `unit_bundle` | `spell_bundle` | `combat_bundle` | `line_bundle`
- `effect_policy`: `all` | `largest`
- `anchor`: `center` | `bottom` | `feet`
- `margin`: `tight` | `normal` | `safe`
- `reference`: `none` | `attached_image` | `generated_image` | `local_file`
- `prompt`: the user's theme or visual direction
- `role`: only when the asset is clearly an NPC role
- `name`: optional output slug

### Asset Types

- `player`: controllable overworld hero
- `npc`: role-readable town or field character
- `creature`: monster, beast, spirit, boss, summon
- `character`: side-view or non-overworld humanoid unit that is not specifically a player or NPC
- `spell`: castable magic or skill sequence
- `projectile`: loopable traveling object such as orb, arrow, fireball, bullet, beam segment
- `impact`: hit burst, explosion, contact FX
- `prop`: item, weapon, shrine object, pickup, deployable
- `summon`: conjured unit or creature entrance asset
- `fx`: generic visual effect sheet

### Actions

- `single`: one static sprite
- `idle`: looped breathing / stance / aura cycle
- `cast`: spell or skill wind-up / release
- `attack`: attack-only animation
- `hurt`: damage reaction
- `combat`: combined attack + hurt sheet
- `walk`: travel loop
- `run`: faster travel loop
- `hover`: airborne idle / travel loop
- `jump`: ascending / take-off held pose (platformer)
- `fall`: descending held pose (platformer)
- `dash`: horizontal speed-burst held pose, often with afterimage (platformer)
- `bounce`: launched-upward held pose off a spring / trampoline / bounce object (platformer)
- `charge`: power-up build-up (one-shot, plays while the input is held below the peak threshold)
- `charge_full`: at-peak loopable swirl (continues while the input stays held after the threshold; f3 must seam back into f0)
- `charge_release`: charged release strike (one-shot, plays on release; wider arc than `attack`). See `spec/contracts/charge-family.md` for the three-sheet coordination contract.
- `projectile`: loopable travel motion
- `impact`: contact burst
- `explode`: stronger impact or destruction burst
- `death`: defeat / vanish / collapse sequence

### Bundle Presets

- `single_asset`: one sprite or one sheet
- `unit_bundle`
  - default: `idle` + `combat`
  - optional: `walk`
- `spell_bundle`
  - default: `cast` + `projectile` + `impact`
- `combat_bundle`
  - default: `idle` + `attack` + `hurt`
- `pose_bundle`
  - default: the platformer held-pose states (`jump` + `fall` + `dash` + `bounce` + `die`) packed as single poses in one sheet
  - use for states with no intrinsic cyclic body motion (see "Cyclic loop vs held pose")
- `line_bundle`
  - default: 1-3 forms
  - per form, choose only the needed sheets

### Sheet Presets

- `1x4`
  - projectiles
  - simple looping FX
- `2x2`
  - standard idle
  - attack / hurt / impact
  - compact side-view walk
- `2x3`
  - cast sequences
  - death sequences
  - slightly richer combat actions
- `3x3`
  - large creature idle
  - boss aura loops
  - high-value showcase idles
- `4x4`
  - topdown 4-direction player walk sheet

### Agent-First Mapping Hints

- `"make a 4-direction main hero"` -> `player` + `player_sheet`
- `"make a healer npc"` -> `npc` + `single_asset`, `role=healer`
- `"make a healer npc walk sheet"` -> `npc` + `walk`
- `"make a boss idle"` -> `creature` + `idle`; prefer `3x3`
- `"make a wizard throwing a magic orb"` -> `spell_bundle`
- `"make a fireball projectile"` -> `projectile` + `projectile`; prefer `1x4`
- `"make a hit explosion"` -> `impact` + `impact`; prefer `2x2`
- `"make a summon entrance"` -> `summon` + `cast` or `impact`
- `"make a full fire samurai creature line"` -> `line_bundle`; plan 1-3 forms, then choose sheets per form

### Legacy Compatibility

Keep these mappings working:

- `player_sheet`: 4-direction overworld walk
- `player_walk`: 2x2 down-facing walk
- `npc_walk`: 2x2 down-facing walk
- `combat`: 2x2 attack + hurt
- `evolution`: legacy concept sheet

## Agent Rules

- Decide the asset plan yourself. Do not force the user to spell out sheet size, frame count, or bundle structure when the request already implies them.
- Write the art prompt yourself.
- If a generated sheet touches cell edges, drifts in scale, or breaks a projectile / impact loop, regenerate the raw sheet.
- Keep the solid pure-color marker background rule (default `#FF00FF` magenta; switch to another saturated pure color like `#00FF00` or `#00FFFF` if the subject contains that hue) so post-processing chroma-key can cleanly remove it.

## Workflow

### 1. Infer the asset plan

Pick the smallest useful output.

Examples:

- controllable hero with four directions -> `player` + `player_sheet`
- healer overworld NPC -> `npc` + `single_asset` or `unit_bundle`
- large boss idle loop -> `creature` + `idle` + `3x3`
- wizard throwing a magic orb -> `spell_bundle`
  - caster cast sheet
  - projectile loop
  - impact burst
- monster line request -> `line_bundle`
  - plan 1-3 forms
  - per form, make the sheets the request actually needs

### 2. Write the prompt manually

If a reference is involved:

- State the reference role explicitly: preserve identity/style, create an animation sheet for the same subject, create an evolution/variant, or derive a matching prop/FX.
- Preserve the stable identity markers from the reference: silhouette, palette, face/eye features, costume marks, major accessories, and material language.
- Let only the requested action or evolution change. Do not redesign the subject unless the user asks.
- Still require exact sheet shape, the chosen marker-color background, frame containment, and same scale across frames.

Keep the strict parts:

- solid pure-color marker background (default `#FF00FF`; pick another saturated pure color if the subject contains magenta)
- exact sheet shape
- same character or asset identity across frames
- same bounding box and same scale across frames
- explicit containment: nothing may cross cell edges

## Defaults

- `idle`
  - small or medium actor -> `2x2`
  - large creature or boss -> `3x3`
- `cast` -> prefer `2x3`
- `projectile` -> prefer `1x4`
- `impact` / `explode` -> prefer `2x2`
- `walk`
  - topdown actor -> `4x4` for four-direction walk
  - side-view asset -> `2x2`

## Prompt Rules

### Global Rules

Always keep these constraints:

- background is 100% solid flat pure-color marker (default `#FF00FF` magenta; switch to another saturated pure color such as `#00FF00` or `#00FFFF` if the subject contains magenta). Use the same marker color across the entire sheet.
- no gradients in the background
- no text
- no labels
- no UI
- no speech bubbles
- exact grid count only
- no borders or frames between cells
- same asset identity across frames
- same bounding box and same scale across frames

### Reference Rules

Use these rules when the user attaches a reference, points to a local image, asks for consistency with an earlier generated image, or asks for an evolution/variant of an existing sprite:

- In the prompt, say `use the image just shown as the visual reference`.
- State what must stay fixed: silhouette family, palette, face/eyes, costume or markings, accessories, material language, and art style.
- State what may change: pose, animation phase, action energy, size progression, evolution traits, or FX intensity.
- For animation sheets, preserve the same character identity in every cell and only change the animation pose or effect state.
- For evolution lines, keep visible lineage markers while allowing larger silhouette, added details, or stronger colors per form.
- Keep the normal marker-color background and containment rules even when using a reference.

### Containment Rules

For any sheet mode, say this explicitly when consistency matters:

- the entire subject must fit fully inside each cell
- no body part, effect, weapon, tail, wing tip, orb, spark, or smoke trail may cross a cell edge
- leave marker-color margin on all four sides
- use the same silhouette scale in every frame

If detached FX are undesirable, say:

- no floating detached effects outside the main silhouette

If detached FX are required, say:

- detached effects must remain tightly grouped near the main subject and still fit inside the cell

### View Rules

Pick `view` to match the game's camera, not the asset type. The same asset will look different under different cameras.

| `view` | Camera | Typical genres | Canonical orientation |
|---|---|---|---|
| `topdown` | 90° from above | top-down shooter, twin-stick, classic JRPG overworld, tactics | no canonical facing; multi-direction sheets use `4x4` |
| `3/4` | ~45° from above | modern JRPG overworld (Stardew, Pokemon Gen V+), top-down RPG, isometric strategy | same as topdown |
| `side` | 90° from front, profile | platformer, metroidvania, side-scroll brawler, fighting, shmup, all projectiles and directional FX | **faces right**; engine flips horizontally for left. If image-gen returns a left-facing asset, post-process with `vibegame art edit <path> -m hflip --inplace` — never re-prompt over direction alone. |

### Character Style

For `player`, `npc`, and `character`. Three layers — apply all three.

#### Common rules (style-agnostic)

- Strong silhouette, readable at thumbnail size
- Full body visible
- Same scale and proportions across all frames
- Enough margin on all sides for clean engine rendering
- Stable identity markers preserved across frames (palette, face/eyes, costume, accessories)
- **Named / known-IP character: name it, do not hand-describe it.** For a well-known character (e.g. a named anime / game / film character), state the name and forbid substitution ("render <Name> from <Work>, keep the canonical recognizable look, do NOT substitute a generic <archetype>") plus "use the canonical palette, do not improvise replacement colors". The model's built-in likeness is stronger and more consistent than any manual appearance description — spelling out hair / eyes / outfit fights the model and drifts. Reserve manual appearance description for original (non-IP) characters.

#### Per art style

Pick the art style from the GDD (or user instruction), then apply the matching tips:

- **Pixel art** (Stardew, Celeste, Dead Cells): chunky readable forms, **crisp dark outlines**, limited palette, integer pixel scale. Default for top-down RPGs and roguelikes when the GDD does not specify otherwise.
- **Painterly / illustrative** (Hollow Knight, Hades): soft edges, layered colors, atmospheric rim lighting, no hard outlines.
- **Vector / flat** (Mini Metro, Monument Valley): bold shapes, high contrast, thin or no outline, limited palette.
- **Hand-drawn cartoon** (Cuphead, Don't Starve): visible line-weight variation, textured fill, exaggerated proportions.

#### Per genre / camera

- **Top-down RPG / roguelike overworld** (Stardew, Pokemon, Hades top-down combat): `view=3/4` from slightly above, full body, chunky proportions
- **Side-view action / metroidvania / platformer** (Hollow Knight, Celeste, Dead Cells): `view=side`, dynamic action poses, **canonical facing = right**. If the generated sheet faces left, flip with `vibegame art edit <path> -m hflip --inplace` instead of regenerating.
- **Top-down shooter / twin-stick** (Gungeon, Nuclear Throne): `view=topdown`, weapon visible from above, head-down silhouette

### Creature and FX Style

For `creature`, `spell`, `projectile`, `impact`, `summon`, and `fx`.

#### Common rules

- Strong silhouette
- Readable body colors or effect shape
- Battle-ready or gameplay-readable pose
- Avoid painterly composition drift between frames
- If humanoid, keep it clearly non-player unless the user explicitly wants a player-like unit

#### Directional FX (projectile, arrow, meteor, magic bolt, beam, anything with implied motion)

- The asset **must face right** (canonical direction)
- Why: engines render other directions by horizontal flip or rotation; a single canonical direction lets the runtime transform cleanly
- If the generation comes out facing the wrong direction, post-process rotate (e.g. `vibegame art edit --rotate <angle>`) to make it face right before delivery. Do not re-prompt over direction alone — only re-prompt when rotation breaks the asset.

#### Non-directional FX (explosion, ground splash, hit burst, AOE ring, aura, fire pillar, geyser)

- No left/right facing — the "face right" rule does not apply
- View follows the **game camera**, not the FX itself. The same explosion looks different under each camera:
  - `topdown` game: effect collapses to a radial plane (flat circle of fire, debris flying outward in 2D)
  - `side` game: effect shows full vertical axis (mushroom cloud rising, debris arcing down)
  - `3/4` game: oblique compromise (ellipse with partial vertical column)
- Pure planar effects (AOE ring on the ground, ground splash) flatten to a line under `side` — switch to `topdown` or `3/4` for those.

### Action Rules

#### `idle`

Use:

- neutral stance
- subtle motion
- weight shift or aura pulse
- strongest idle accent before looping

Prefer:

- `2x2` for standard actors
- `3x3` for large creatures and showcase idles

##### Practice Experience

Write the 4-frame motion block as a single continuous micro-cycle, not 4 independent poses or a list of parallel events.

- Pick exactly one driving wave (`breathing`, `hover bob`, `aura pulse`).
- Add 1-2 secondary motions from the character's natural cloth/hair/mist parts. They must sync with the driving wave and reverse direction at frame 4.
- Subject conservation: every motion subject (chest, cloak, hair, ...) must appear in every frame's description. Never introduce a new subject mid-cycle.
- Phase progression: the same subject across all frames traces 4 sample points of one continuous physical process (e.g. cloak: `settled → drift → fully drifted → recoil`).
- Reverse closure: the last frame's secondary motion must reverse direction (not "return to neutral"), so the loop joins seamlessly.
- Each frame description must contain at least one restraint word: `subtle / slight / gently / softly / faint / barely`.
- Use relative deltas, not absolute states (`chest rises`, not `stands tall`).
- Use anatomy + verb, not pose labels (`antlers tip forward`, not `alert pose frame`).

Reusable shape:

```
Animation (4 idle frames, [driving wave] + [secondary], looping seamlessly):
- frame 1 (top-left): neutral standing, [body part] at rest, [secondary subject] settled
- frame 2 (top-right): subtle [driving wave verb], [body part] slightly [direction], [secondary] drifts gently to one side
- frame 3 (bottom-left): peak of [driving wave], body slightly raised, [secondary] fully extended
- frame 4 (bottom-right): [reverse driving wave], body sinks back toward neutral, [secondary] recoils the OTHER way
```

#### `cast`

A `2x3` cast is often the best default:

- readiness
- energy gather
- stronger gather
- release start
- release peak
- settle or hold

#### `attack`

For a compact attack-only sheet, describe:

- wind-up
- strike
- follow-through
- recovery

#### `hurt`

For a hurt-only sheet, describe:

- impact
- recoil
- stagger
- recovery

#### `combat`

For a compact combined sheet:

- top-left: attack wind-up
- top-right: attack strike
- bottom-left: hurt impact
- bottom-right: hurt recovery

#### `projectile`

Usually prefer `1x4` or `2x2`.

Describe:

- same projectile identity in all frames
- travel direction stays consistent
- shape changes are small and loopable
- glow or trail stays inside the frame

#### `impact` / `explode`

Usually prefer `2x2`.

Describe:

- ignition or contact
- expansion
- peak burst
- fade or collapse

#### `walk` / `run` / `hover`

State the travel behavior clearly:

- grounded stride
- hover bob
- crawl
- slither
- mechanical glide

#### Cyclic loop vs held pose (how many frames a state needs)

Frame count is decided by the state's **intrinsic body motion**, not by whether the engine moves the character through the world. Position is engine / transform-driven for *every* state (idle, run, jump — all get their world position from code), so "the engine drives position" is NOT the discriminator.

- **Cyclic in-place motion → multi-frame loop.** `idle` (breathing), `walk` / `run` (leg cycle), `hover` (bob): the body animates in place regardless of where it is in the world, so it needs several frames.
- **One held characteristic pose → single frame.** `jump`, `fall`, `dash`, `bounce`: the body holds one readable pose while the engine translates it through space, so one representative frame per state is enough.

Pack the held-pose states into one sheet (see `pose_bundle`) so scale, palette, and outline weight stay identical across all of them in a single generation.

#### `jump` / `fall` / `dash` / `bounce` (platformer held poses)

Each is one representative held pose (not a loop). Keep the same character identity, scale, and canonical facing across the set.

- `jump`: ascending / take-off read — body tilted into the rise, legs gathered / tucked, hair or cloth blown down-and-back by upward motion.
- `fall`: descending read — legs reaching down, arms out slightly for balance, hair or cloth blown up by downward motion. Must be visually distinct from `jump`.
- `dash`: horizontal speed-burst — body extended along the travel axis, limbs streamlined back. Optional small afterimage / speed lines kept tight and inside the cell (or the cut merges the trail as a separate component).
- `bounce`: launched-upward-off-something read — body kicked up, arms thrown up, an energetic / surprised expression that reads differently from a controlled `jump`.

### Sheet-Specific Rules

#### `4x4` player sheet

Use:

- row 1: down
- row 2: left
- row 3: right
- row 4: up
- column 1: neutral
- column 2: left foot forward
- column 3: neutral again
- column 4: right foot forward

#### `3x3` large idle

Say:

- exactly 9 equal cells in a `3x3` grid
- same bounding box in all 9 cells
- subject fills only about 55% to 65% of each cell
- no edge crossing anywhere

#### `1x4` projectile

Say:

- exactly 4 equal cells in one row
- same projectile size in every frame
- only the internal energy or shape pulse changes

#### Variant-rows × animation-columns grid

Use when the same animation is needed for several recolored / re-skinned variants (e.g. red / blue / gold pop effects, elemental spell variants, palette-swap enemy deaths). One generation produces all variants in visual lockstep.

- rows = variants, columns = the shared animation frames (e.g. `3x4` = 3 variants × 4 frames).
- Say: frame N is **structurally identical across every row** (same silhouette / fragment layout / timing), only the dominant color changes row-to-row.
- keeps every variant's animation on the same timing and shape language, so they read as one family.
- after cut, name frames `<variant>_<n>` (e.g. `red_0..3`, `blue_0..3`) so the engine can play one variant's row as a clip.

### Bundle Prompting

When generating a bundle, write each asset prompt independently.

Good default decomposition:

- caster unit
- projectile
- impact

or:

- idle
- combat
- walk

Do not try to force unrelated assets into one giant sheet.

### Quick Prompt Pattern

1. state the asset type and sheet shape
2. describe the subject identity
3. if applicable, state the reference role and invariants
4. describe frame-by-frame motion
5. restate same-scale and containment rules
6. restate marker-color background and no-text rules

## Troubleshooting

### Marker-color drift in chroma-key removal

Some providers deliver the marker color slightly off from the prompted value — a prompt asking for `#FF00FF` may come back as `RGB(248, 13, 228)` or similar. Default `vibegame art rmbg -t 10` then leaves a visible halo around the subject. When that happens, sample the actual corner pixel and re-run with explicit color + wider tolerance:

```python
import numpy as np; from PIL import Image
bg = np.array(Image.open('raw.png'))[0, 0, :3]
print(bg)  # e.g. [248 13 228]
```

```bash
vibegame art rmbg raw.png -c 248,13,228 -t 50 --defringe 3 -o clean.png
```

The same fix applies for any other pure marker color (`#00FF00`, `#00FFFF`) — sample, supply explicit `-c`, raise `-t` until the halo is gone, add `--defringe` to clean residual edge bleed.
