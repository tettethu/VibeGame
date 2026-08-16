---
name: self-evolve
description: Capture reusable patterns from a finished project and lift them into framework-level priors (contracts, modules, skeletons) that future projects inherit. Run only when the user explicitly requests self-evolution; the orchestrator executes the workflow.
---

# Self-Evolve

Run at the end of a project to promote what worked in this project into framework-level priors. Future projects then start ahead because `vibegame init` ships the priors.

## Workflow

The orchestrator coordinates this workflow and owns code and architecture outputs (modules, skeletons, and contracts excluding the Artist chapter). Skeleton-specific errors belong inside the matching skeleton. Art-recipe distillation belongs to artist via the `artist-self-evolve` skill — dispatch it in parallel.

0. **Self Check.** Before promoting or syncing a skeleton, audit the finished project itself. The project will become a future starting point, so fix these issues in the project before opening a task to convert it into `skeletons/<slug>/`:

   - **Engine-owned runtime facts stay engine-owned.** Anything the engine can express — especially visual `scale`, `width` / `height`, `offset`, `pivot`, `depth`, collider `width` / `height`, collider `offset`, collider `pivot`, scroll factor, animation clip timing, and similar runtime visual / collision behavior — must be declared in scene JSON, node JSON, manifest metadata, or config that the engine reads. Do not bypass the engine by setting visual scale / offset / pivot or collider scale / offset / pivot imperatively in scripts when an engine parameter exists.
   - **No unexplained hard-coded numbers.** Gameplay, physics, visual sizing, hitbox dimensions, spawn timing, camera bounds, UI placement, and animation timing must come from scene JSON, node JSON, manifest metadata, or config. Numeric constants in scripts are allowed only for local math identities or tiny implementation defaults that are not game tuning; otherwise move them to config before evolve.
   - **Single-node config stays inline.** If a config value only applies to one node instance, put it in that node's inline `config` in the scene / node JSON. Create `config/*.json` only for shared tuning used by multiple nodes, reusable rosters/tables, large state machines, or values intentionally edited as a named subsystem.

   If any of the above fail, stop the evolve run, fix the project, and re-test before continuing. Do not record a skeleton that depends on script-side overrides to compensate for missing engine parameters.

1. **Dispatch art-side evolve.** At the start of the run, send the persistent `artist` teammate this minimal message:

   ```
   game-slug: <slug>
   Use your `artist-self-evolve` skill for this run.
   ```

   Artist runs the skill and:
   - **Writes `skeletons/<slug>/art-pack.md` directly** (Phase 1) — sub-genre-bound, no gate.
   - **Stands by for per-contract `#### Artist` chapter requests** from you in Step 5 (Phase 2).

   The art-pack is part of the skeleton output. Contract Artist chapters are part of the approved contract output.

   If artist replies that the skill is unavailable (harness doesn't expose it), abort the evolve run and report to user. Running self-evolve without art-side coverage leaves `art-pack.md` empty and contracts' Artist chapters uncovered.

2. **Search for candidates per destination, independently.** Run the skeleton / modules / contracts searches in parallel. Do not "find candidates first, then classify". Each target's search rule and qualification bar lives in `Evolve Targets`. Search reusable failure modes while evaluating skeletons; they are part of the skeleton update, not a separate destination.

3. **Present each list to the user and wait for approval.** Show one list per destination: skeletons / modules / contracts. Include skeleton-owned error notes under the relevant skeleton item, not as a fourth list. Do not force a unified table; each list's shape can fit its content. The user may merge / split / drop items — accept their direction. This gate is about *which priors get touched*, not their content. Lifting priors silently locks in framework defaults for every future project, so this gate is non-negotiable.

4. **Convert approved skeletons via task workflow.** For each approved skeleton candidate, open a task whose `prd.md` explicitly requires converting the finished project into a runnable placeholder skeleton under `skeletons/<slug>/`. Do not hand-convert the skeleton inside the orchestrator session; let the task workflow produce and verify it. Use the PRD requirements and review bar in `Evolve Targets / skeletons`.

5. **Draft contracts, delegate the Artist chapter.** When you write a contract (new file or new Pattern), author the structure and every non-Artist responsibility chapter (`#### Architect/Programmer`, `#### Player`, `#### Reviewer`, optional `### Manifest and asset boundary`). Then send `artist` a per-contract request with the file path and the surrounding pattern context; artist writes `#### Artist` (and its nested `##### Workflow`) directly into that file (Phase 2). Do not have artist return a draft for you to relay — chapter content is artist's domain.

6. **Verify.** Run `vibegame check` from the project root; resolve naming / structural failures before promotion.

7. **Promote through the CLI.** Run one command for each user-approved prior:

   ```sh
   vibegame evolve skeleton -n <kebab-case-slug> --dry-run
   vibegame evolve module -n <PascalCaseModule> --dry-run
   vibegame evolve contract -n <kebab-case-slug> --dry-run
   ```

   Review the `copied files` and `not copied` lists. After the dry run passes, rerun without `--dry-run`. The CLI finds the VibeGame source checkout from its installed code and writes only to the fixed destination for that prior type. Do not use `cp`, `rsync`, or manual whole-directory copying to promote shared priors. The CLI never commits or pushes.

   If a destination exists, stop. Compare and resolve the conflict manually; the CLI does not replace or merge existing priors.

8. **Update the source index manually.** After a successful promotion, the CLI prints the absolute path of the source index that requires a manual edit. Do not infer the source checkout path from the game project. If the printed path is outside the current game project, obtain user permission to edit it, then update that exact file. The CLI never copies or edits an index.

## Global Rules

- Project specifics never leak into priors — no character names, no PvP-vs-PvE assumptions, no "current KOF" snapshots. Use neutral identifiers (`p1` / `p2`, `fighter`, `bar`).
- Framework-shared outputs must be reproducible from the shipped repo alone. Shared outputs are files under `modules/`, `skeletons/`, `.vibegame/spec/contracts/`, and `.vibegame/spec/engine/`. Other project files are not shared priors.
- No absolute paths, seed-project references, private worktree paths, or project-specific file references in shared outputs. Do not cite `REFLECTION.md`, `plan.md`, `log.md`, screenshots, prompt artifacts, or other source-project files as if future projects can read them. Distill the lesson into the shared file instead.
- Do not refer to a "seed project", "source project", "current project", "sibling project", "attached image", or "user-provided file" from a shared output. If a reference image is required, ship it explicitly under `skeletons/<slug>/art-pack-assets/` and refer to that relative path.
- `art-pack.md` records the verified generation method and useful candidate outputs. `assets/manifest.json` records only assets selected by the runtime. Generated but unused assets do not belong in the runtime manifest; remove their entries and runtime files before promotion.
- Skeleton promotion copies only the standard skeleton files: root `project.json`, `index.html`, `index.md`, `art-pack.md`, and `errors.md`; JSON under `config/`; `*.scene.json` under `scenes/`; `*.node.json` under `entities/`; JavaScript under `scripts/`; reference images under `art-pack-assets/`; and manifest-selected files under `assets/`. It does not copy project-local `engine/`, `modules/`, `stages/`, `vendor/`, `.vibegame/`, `tests/`, or any other unlisted content.
- Modules are promoted independently through `vibegame evolve module`. Never place or copy a `modules/` directory inside a skeleton.
- Ship only what was load-bearing in a real task. Do not invent priors that were never used.
- Your job is to let future orchestrators choose, not to force a choice. Keep `### When to use` grounded in verified capability, not plausible genre extrapolation.
- **Modules / contracts qualification**: extract only when the pattern is plausibly reusable in **other** sub-genres OR is a standard part of **every** project in the same sub-genre. One-off conveniences stay in the project.
- **Modules require real encapsulation**, not copy-and-rename. Promote `scripts/X.js` only after refactoring it into a properly parameterized module — all tunables flow through `this.config`, no hard-coded project assumptions, public methods are documented at the top of the file. If it cannot be cleanly encapsulated, it does not qualify.
- **Contracts and modules are independent evolve targets**:
  - Extract a contract when a recurring feature needs a special cross-role production workflow that the ordinary task workflow does not express. Its implementation may use engine APIs, an existing module, a new module, or project-owned code.
  - Extract a module when a real project has proved a reusable, encapsulated runtime behavior. Do not create a module only because a contract includes programming work.
  - When a verified module implements part of a contract, reference it from the relevant responsibility chapter. The contract owns the cross-role workflow; the module source owns its code interface.
  - A module with no cross-role concerns does not need a contract. Document its purpose, config fields, public methods, and minimal usage in its source header.

---

## Evolve Targets

### modules

Scan `scripts/` and current `modules/` usage for code that passes the qualification gates. List each as `scripts/<X>.js, scripts/<Y>.js (if multiple scripts merge into one module) => modules/<X>Module.js` with one sentence describing what the module achieves. Every promoted module must also gain a row in `modules/index.md` with one line description and one line interface.

#### **How to choose functionality for module extraction**

Prioritize functionality that:

- **Owns frontend rendering effects that users accepted.**
- **Couples assets, collision, and behavior into one runtime unit.**

Pure gameplay logic is usually easy to rewrite correctly. Code that affects visuals and real runtime feel is easier to get subtly wrong and harder to test, so it is more valuable to preserve as a module.

#### **How to turn project logic into a module**

**Step 1: Define the module behavior**

A well-encapsulated module is used through these surfaces:

1. `xxx.node.json`: `script: "XxxModule"` turns the module into a node that works once placed in `scene.json` through normal lifecycle methods such as `ready` and `update`. Store all tunables in `config`; reuse engine-native fields such as `animator`, `visual`, and `collider` for animation and collision.
2. `manifest.json`: records the asset keys the module needs.
3. Project code: wires the module interface into game logic. A module often detects and emits events; project code consumes those events for damage, story, scoring, or other project-specific outcomes.

A module must have a clear behavior boundary. Other scripts should only provide inputs, consume outputs/events, or read public state; they must not maintain the module's core behavior. The module should work by itself. If it is coupled to another object, either split the coupling and expose that object's data/methods as module inputs, optionally through parent/child nodes, or turn the other object into a module too.

Define the module's configuration and behavior before moving code.

**Step 2: Modularize the project**

Move the relevant functionality into `modules/`, change the original node reference to `XxxModule`, then implement the module according to the behavior boundary defined in Step 1.

**Step 3: Test**

The module implementation is acceptable only after a real project proves that the module works correctly.

**Step 4: Self-check**

When possible, implement module self-check logic callable through `vibegame check xxx.node.json`. `check` detects module nodes and calls the matching module check code. This is especially useful for:

- Errors that can be found before runtime, such as missing required config keys.
- Multi-structure consistency, such as collider alignment against animation frame size and position. If it cannot be fully asserted, output review images; this is easier than detecting it at runtime.

**Self-check code schema**

Module self-check has two layers:

1. Runtime self-check: lives in `modules/XxxModule.js` and catches runtime configuration errors.
2. Static module check: lives in `modules/check/XxxModule.check.py` and is auto-discovered by `vibegame check xxx.node.json`.

#### Runtime self-check

Runtime self-check uses `_selfCheck()` and usually runs from `ready()`.

Use it to:

- Check objects that only exist at runtime: physics body, animator instance, child node instances, tag query results.
- Emit clear `console.error` / `console.warn` messages.
- Avoid generating images. This does not replace `vibegame check`.

Minimal shape:

```js
ready() {
  this._selfCheck()
}

_selfCheck() {
  const tag = `XxxModule[${this.name}]`
  const errors = []
  const warns = []

  if (!this.animator) errors.push('node.json must define animator')
  if (!this.getPhysicsObject?.()?.body) errors.push('node.json must define collider')
  if (!this.config.requiredKey) errors.push('config.requiredKey is required')

  for (const e of errors) console.error(`${tag}: ${e}`)
  for (const w of warns) console.warn(`${tag}: ${w}`)
  if (!errors.length && !warns.length) console.log(`${tag}: self-check passed`)
}
```

#### Static module check

Static module check is the preferred self-check path. The file name must match the module script:

```text
modules/XxxModule.js
modules/check/XxxModule.check.py
```

`vibegame check` discovery rules:

- The node declares `"script": "XxxModule"`.
- `vibegame check entities/foo.node.json` looks for `modules/check/XxxModule.check.py`.
- Whole-project `vibegame check .` scans all `*.node.json` files and calls matching `.check.py` files for `*Module` nodes.
- The check file exposes `check(project: Path, node_path: Path, opts: dict | None = None) -> list[str]`.
- Message prefixes determine report level: `ERROR`, `WARN`, `PREVIEW`, `PASS`.

Minimal shape:

```py
import json
from pathlib import Path


def check(project: Path, node_path: Path, opts: dict | None = None) -> list[str]:
    opts = opts or {}
    messages: list[str] = []
    node = json.loads(node_path.read_text())

    config = node.get("config") if isinstance(node.get("config"), dict) else {}
    animator = node.get("animator") if isinstance(node.get("animator"), dict) else {}
    children = {
        child.get("name")
        for child in node.get("children", [])
        if isinstance(child, dict) and isinstance(child.get("name"), str)
    }

    if not config.get("requiredKey"):
        messages.append("ERROR config.requiredKey: required")
    if "Hitbox" not in children:
        messages.append('WARN child "Hitbox" not found')
    if "idle" not in animator.get("states", {}):
        messages.append('ERROR animator.states.idle: required')

    if not any(m.startswith("ERROR") for m in messages):
        messages.insert(0, "PASS static check passed")
    return messages
```

#### What to assert

Assert anything that can be asserted directly. Do not generate an image and make reviewers guess.

- Required `config` keys.
- Manifest key existence.
- Animator state / parameter / clip existence.
- Texture / frame existence for animation clip references.
- Child node, tag, hitbox name, and action name existence.
- Missing or invalid collider / visual / sensor / body fields.
- Cross-structure references, such as `config.actions[*].state` pointing to an existing animator state, and `config.actions[*].fx` pointing to an existing child node.

#### What to preview

For anything requiring visual review, generate `PREVIEW` images instead of describing the issue in text. Default output:

```text
assets/artifacts/module-check/
```

Good preview targets:

- Sprite visual and collider alignment.
- Animation frame strip and active-frame correctness.
- Whether attack / hurt / sensor hitboxes cover the correct frames and body regions.
- Whether module-owned DOM / canvas / Phaser visuals match configured size, pivot, and offset.

#### Preview coordinate rule

Preview must reproduce real runtime coordinate logic. Otherwise the image misleads the reviewer.

If the module's visual behavior relies on the engine, preview must use the same rules as engine `visual` / `collider` / `animator`:

- Visual source size comes from manifest sprite bbox or image size.
- Display size comes from engine fields such as `visual.ratio`, `visual.width`, and `visual.height`.
- Collider size / offset / pivot come from node `collider`, including engine default pivot inheritance.
- Child hitbox placement uses the same parent/child, pivot, offset, and scale conversion as runtime.
- Animation preview uses the real `animations.clips[*].frames` order, and active frames use the real frame indexes from module config.

If the module defines its own visual behavior, preview must reproduce the module's own coordinate logic:

- Use the real anchor / origin / pivot rules from the module code.
- Use the real scale / layout / clipping / mask rules from the module code.
- Use the real event active window / hit test rules from the module code.

Do not write approximate coordinates just to make preview easier. If the preview cannot reproduce the real behavior, emit a `WARN` explaining what it does not cover.

### art-side evolve

Art-recipe distillation belongs to artist via `artist-self-evolve`.

Lead responsibilities:

- Dispatch artist at the start with `game-slug`.
- Do not write `skeletons/<slug>/art-pack.md` yourself.
- For each contract that needs an Artist chapter, write the non-Artist chapters first, then ask artist to fill `#### Artist` directly in that file.

Artist responsibilities:

- Write `skeletons/<slug>/art-pack.md`.
- Fill contract `#### Artist` chapters when requested.

### contracts

Files under `.vibegame/spec/contracts/` are contracts guiding orchestrator how to delegate jobs to different teammates and how teammates should behave to build some special features.

Scan task artifacts (`plan.md` and the `# Auditor` / `# Player` sections of each task's `log.md`, plus `REFLECTION.md`) for cross-role coordination rules not yet captured in any contract. List each as a new/extended contract file or Pattern.

**Schema**

```
## Pattern 1: slug-1

### When to use

<what this pattern achieves: the produced artifact, input/output shape, runtime behavior, and coordination boundary. Also state the exact type of game or feature slice where this pattern has been practice-verified. Do not mention any other game type or scenario unless that scenario was actually verified by a completed project.>

### Basic Knowledge

<Use this when this pattern needs extra prior common knowledge to exactly know **WHY need to do this**. Task contracts/tilemap.md for example, which demonstrates why we need prior knowledge otherwise nobody knows why face/top split.>

### Responsibility

#### Artist

<one-line lead, then a mandatory ##### Workflow with three steps:
 Generate / Package / Verify, then a flat "Common mistakes" bullet list.
 Artist fills this chapter via the artist-self-evolve skill — see that
 SKILL's Phase 2 for the body shape and templated-prompt rule.>

##### Workflow                          (MANDATORY when artist has nontrivial
                                         work. Exactly three steps:
                                         Generate / Package / Verify.)

#### Architect/Programmer/Auditor/Player/Reviewer/...

<what each remaining teammate owns; not every teammate has to appear>

### Manifest and asset boundary   (OPTIONAL — only when this pattern has rules
                                   that span multiple roles, e.g. which assets
                                   must / must not be registered in manifest.json
                                   regardless of who creates them)

## Pattern 2: slug-2

...
```

**Rules**

- Slugs are kebab-case (`sprite-backed-status-bar`, `fighting-hud-dom`).
- Not all patterns involve every teammate.
- Architect, Programmer, Auditor, Player may take the same responsibility, when they should do the same things in their lifecycle. They may also have different responsibilities.
- **Not specific project related.** We extract reusable patterns from specific projects but share contracts in totally different projects. So expressions like *"This is the current KOF project pattern."* should not exist.
- **Code examples must use neutral identifiers.** Do not bake project-specific assumptions like single-player vs PvP, AI-only opponents, or a specific demo's character names. Prefer `p1` / `p2` over `player` / `cpu`; prefer generic placeholders (`fighter`, `bar`, `slot`) over named entities. The example is a template, not a snapshot.
- **`### When to use` is capability-first.** It must say what the pattern achieves, its IO shape, runtime behavior, and what teammate coordination it covers. It is not a genre recommendation list.
- **Verified scope only.** State the exact game type or feature slice where the pattern was practice-verified. Do not "reasonably" infer other game types that could also use it. No "also works for", "good fit for", or game-name lists unless those exact cases came from completed projects.
- **Cross-pattern guards are minimal and evidence-bound.** Only write sibling exclusions that follow directly from artifact capability / IO boundary, or from a verified failure. Do not create plausible "when NOT to use" lists from genre intuition.
- **`### When to use` does not reference its own slug.** The orchestrator commissions in natural language and does not know the contract slug. Write the trigger conditions in terms of produced artifacts and behavior, not slug names.

### skeletons

Skeletons are runnable placeholder game baselines for a sub-genre, not stripped file bundles or a parallel best-practice store. Every successful project can produce or refine one when its structure is reusable.

- If the project has the same structure and feature shape as an existing skeleton: replace that skeleton only when this project is clearly better (more complete, simpler, cleaner, or more reusable). If it is not better, reflect why the existing skeleton was not used and add this project shape to that skeleton's `When to use`. If it started from a skeleton but made meaningful structural/feature changes, create a suffixed skeleton slug instead of overwriting the original.

When Step 4 opens the conversion task, write these requirements into that task's `prd.md`:

```
Goal: convert this finished game into a runnable placeholder skeleton at `skeletons/<slug>/`.
Requirements:
- Preserve scene flow, entity dimensions, colliders, camera, tuning, timing, HUD layout, scripts, config, and runtimeState shape.
- Replace project-specific real assets with manifest `placeholder_atlas` / `placeholder_image` entries, or project-local placeholder-safe assets, unless an asset is intentionally shipped under `art-pack-assets/` as reference material.
- Remove private paths, source-project references, character names, and project-specific content.
- Remove manifest entries and runtime asset files that the skeleton does not use.
- Keep the skeleton openable and playable enough that a future orchestrator can feel the original proportions before swapping real art.
- Run `vibegame check .` and a runtime smoke check before handoff.
```

Review the converted skeleton before updating indexes. Reject skeletons that are only file bundles, stripped manifests with no playable baseline, or copied real-asset projects.

Skeletons have three layers:

1. **Game logic.** A task workflow converts the refined project mostly losslessly into `skeletons/<slug>/`: `project.json`, `scenes/`, `scripts/`, `entities/`, `config/`, CSS, font choices, theme/layout files, placeholder-safe `assets/manifest.json`, and `index.md`. The best conversion only changes texture references to placeholders. It must preserve scene flow, visual proportions, display sizes, collider dimensions, camera bounds, timing, layout, and `runtimeState` shape. The result must be openable as a placeholder game; disconnected scripts, prose-only reconstruction notes, or non-runnable stripped manifests are not a skeleton.
2. **Art assets.** `artist-self-evolve` owns art extraction: `skeletons/<slug>/art-pack.md`, optional `skeletons/<slug>/art-pack-assets/`, and artist-related contract chapters. The game-logic task may replace real visual references with manifest `placeholder_atlas` / `placeholder_image` entries, or project-local placeholder-safe assets, but it must not write art recipes or copy binary real assets outside `art-pack-assets/`.
3. **Errors.** Orchestrator owns reusable failure memory in `skeletons/<slug>/errors.md`, using the rules below. Errors are part of the skeleton, not a separate evolve destination.

All layers do minimal de-projecting: remove private paths, source-project references, character names, and project-specific content. Keep the assembled architecture and natural script names when they describe reusable roles. `skeletons/<slug>/index.md` records sub-genre features, layout, visual proportions, runtime shape, and other starting-point facts. `When to use` belongs only in `skeletons/index.md`.

#### Skeleton errors

Skeleton errors are reusable failure modes found in `REFLECTION.md`, reviewer rejection history, and task logs. They belong to `skeletons/<slug>/errors.md` unless the fix is a framework doc update, a contract `Common mistakes` entry, or an automated module check/test.

Do not treat `skeletons/<slug>/errors.md` as a memory dump. Classify each error by the fix future projects need, then write it to the right destination.

Error categories:

- **Implicit Framework Behavior:** framework-owned behavior was real but undocumented. Fix the relevant framework doc directly with 1-2 clear lines. This covers engine behavior, `vibegame` CLI behavior, module loading, `vibegame check`, `vibegame init`, release behavior, and similar facts.
- **Constraints Ignore:** the relevant doc or contract already said the rule, but the project ignored it. Write to `skeletons/<slug>/errors.md` or the contract's `Common mistakes`; do not rewrite the spec unless the wording was genuinely unclear.
- **Technical Error:** implementation was simply wrong: bad state update, wrong condition, missed listener cleanup, wrong unit conversion, incorrect frame index. Write to `skeletons/<slug>/errors.md` when the failure is sub-genre-specific, or to a module check/test when it can be caught automatically.
- **Best Practices:** old implementation worked, but a better reusable implementation was found. Prefer promoting it into module/contract; write an error only when future agents need a warning against the old approach.
- **Do Not Preserve:** project taste, one-off tuning, temporary misunderstanding, or a lesson fully captured by the code change. Do not write it into shared errors.

Rules:

- Scan `REFLECTION.md` and reviewer rejection history for failure modes worth preserving, then classify before writing.
- Each preserved error records category, symptom, cause, fix, and a `**Spec update**:` line.
- The `**Spec update**:` line points at the skeleton, module, contract, or spec that was changed so the loop closes.
- `skeletons/<slug>/errors.md` is for future action, not guilt. If the future reader cannot use the entry to avoid or detect the same failure, do not add it.
