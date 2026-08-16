# Prototype / Polish Contract

A common two-task workflow for early-project asset development: the first task implements gameplay on manifest-level placeholder entries; a later task swaps those manifest entries to real art. The contract describes the workflow-specific defaults that apply when a task explicitly belongs to this flow.

This contract is **not mandatory** — many tasks (real-asset-from-day-1 work, pure logic, refactors with no visual changes) do not fit the workflow. Orchestrator opts in by naming `prototype_polish` in `prd.md` `Reuse / Constraints` when the task is part of this flow. The base `Assets:` line is separate and always required for art-touching tasks.

## Pattern 1: prototype

### When to use

The task is the first phase of the prototype-polish workflow: gameplay implementation on placeholder art, with the explicit intent that a follow-up `polish` task will swap to real assets. `prd.md` `Reuse / Constraints` carries both:
- `Assets: Use placeholder visuals via manifest placeholder_atlas / placeholder_image entries; node.json must already use final texture keys and semantic atlas frame names.`
- `Contracts: Use prototype_polish pattern prototype because <task-specific reason>.`

A simpler placeholder task without the `prototype_polish` contract is also valid — for example, throwaway prototypes, experiments, or single-iteration tasks that never reach polish. Those use placeholder via the base `Assets:` rule but do NOT activate the workflow-specific defaults below.

### Responsibility

#### Orchestrator

- Writes the placeholder `Assets:` sentence AND the `prototype_polish` prototype contract sentence in `prd.md` `Reuse / Constraints`.
- Enumerates each controllable entity's required animation clip names (e.g. `idle`, `move`, `attack`, `hurt`). Architect does not invent clip names; missing list is `[MISSING LEAD DECISION] animation clips: <entity>`.
- May leave per-clip frame counts unspecified — architect uses the default below.

#### Architect

- Creates or plans `placeholder_atlas` manifest entries for animated / framed prototype texture keys. The texture key and frame names must be the same names expected from the future real atlas.
- Creates or plans `placeholder_image` manifest entries for static prototype texture keys. The texture key must be the same key expected from the future real image.
- If a clip's frame count is not specified by prd, default to **4 frames**. Architect names frames semantically, e.g. `idle_0` through `idle_3`, `attack_0` through `attack_3`.
- Drives entity behavior via state machine (`animator`) + clip `duration` (seconds). Gameplay logic reads `state`, never raw frame indices.
- **Frame-coupled events exception**: clips whose gameplay IS frame-coupled (attack hitbox window, dash active window, charge release commit) are flagged in `plan.md` under a `Frame-coupled events` sub-section. List the clip + the gameplay-meaningful frame(s) + what should happen there. Polish must preserve these.

#### Programmer

- Implements per plan. Treats placeholder texture keys and frame names as authoritative. Do not insert `// TODO: real art` comments; polish work is tracked by `grep 'placeholder_.*' assets/manifest.json`.

#### Reviewer

- Does NOT penalize "the art looks like color blocks" — that is the expected prototype state.
- DOES penalize gameplay logic that reads raw frame indices outside the declared `Frame-coupled events`, because that breaks the polish swap.

### Manifest and asset boundary

`placeholder_atlas` and `placeholder_image` entries are registered in `assets/manifest.json` and have no `path`. The engine maps them onto placeholder assets:

- `__placeholder_atlas__`: atlas placeholder, 8x8 grid, 64 named 32x32 cells.
- `__placeholder_image__`: built-in static fallback image for direct low-level use.
- `placeholder_image`: generated semantic image placeholder with optional `shape` and `color`.

Use manifest entries instead of referencing built-in keys directly in task code, because semantic manifest keys let polish swap only the manifest entry while leaving node.json unchanged.

```json
{
  "player_idle": {
    "type": "placeholder_atlas",
    "frames": ["idle_0", "idle_1", "idle_2", "idle_3"],
    "pivot": [0.5, 1]
  },
  "sword_icon": {
    "type": "placeholder_image",
    "shape": "circle",
    "color": "#ff3366",
    "pivot": [0.5, 0.5]
  }
}
```

`shape` is limited to `rectangle`, `circle`, or `hex`. `color` is a concrete hex value such as `#ff3366` or `0xff3366`. These fields are only valid for `placeholder_image`; real `image` and `atlas` entries get their shape and color from asset files. Circle and hex placeholders still use a rectangular source texture; the shape is drawn inside the smallest flat bounding rectangle.

The public placeholder contract has exactly these two built-in keys: `__placeholder_atlas__` and `__placeholder_image__`.

---

## Pattern 2: polish

### When to use

The task is the second phase of the prototype-polish workflow: a previously-prototyped entity (or set) swaps from placeholder manifest entries to real art. `prd.md` `Reuse / Constraints` carries both:
- `Assets: Use real assets; every referenced visual must exist in assets/manifest.json and on disk under assets/.`
- `Contracts: Use prototype_polish pattern polish because <task-specific reason>.`
The behavior contract is already in place — this task is a visual + per-frame-tuning pass, not a redesign.

A fresh real-asset task with no prior prototype does NOT use this Pattern — it goes through the standard real-asset path in architect.md without the swap + frame-coupled tuning conventions below.

### Responsibility

#### Orchestrator

- Writes the real-assets `Assets:` sentence AND the `prototype_polish` polish contract sentence in `prd.md` `Reuse / Constraints`.
- Names which entities are in scope (polish is not always whole-project).
- Confirms real assets are produced and registered, or commissions artist first.

#### Artist

- Produces real atlases for the in-scope entities; registers each in `assets/manifest.json`. See [`spec/art/sprite.md`](../art/sprite.md).

#### Architect

- **Asset existence cross-check** (first pass): for every in-scope entity, every required real-asset key must be registered in `assets/manifest.json` AND the file must exist under `assets/`. If anything is missing, stop and report `[ASSETS GAP] <key1>, <key2>, ...` — do not write the rest of `plan.md`.
- Plans the swap:
  1. For each in-scope manifest entry: replace `type: "placeholder_atlas"` with real `type: "atlas"`, `path`, and `sprites` bboxes, or replace `type: "placeholder_image"` with real `type: "image"` and `path`. Remove placeholder-only `shape` / `color`. Keep the same manifest key and frame names whenever possible.
  2. For each clip listed in the prototype `plan.md`'s `Frame-coupled events`, name the per-frame tuning needed on the real art:
     - **Dash**: hold a mid-clip frame longer via per-frame `duration` override for the active window.
     - **Attack**: bind hitbox-on / hitbox-off to specific real frames.
     - **Charge release**: align the commit frame with the impact visual.
     - Other clip-specific timing/effect callouts come from the original prototype plan.
  3. Confirms `grep 'placeholder_.*' assets/manifest.json` matches are either addressed or explicitly listed as out-of-scope for this pass.

#### Programmer

- Executes the swap per plan. Does NOT change script behavior unless `Frame-coupled events` tuning explicitly requires it.

#### Reviewer

- Verifies in-scope manifest entries no longer use `type: "placeholder_atlas"` or `type: "placeholder_image"`.
- Verifies `Frame-coupled events` behave correctly on the real art (hitbox opens on the swing frame, not the wind-up frame; dash active window aligns with the lunge frame; etc.).

### Manifest and asset boundary

Real-asset entries follow [`spec/art/sprite.md`](../art/sprite.md). Polish does NOT remove placeholder support - entities out of scope this pass may still use `placeholder_atlas` or `placeholder_image`.
