---
name: artist-self-evolve
description: Distill stable art-generation patterns from a completed project, so future projects produce comparable assets without re-discovering the prompts. Lead-dispatched only — orchestrator invokes this skill from its `self-evolve` flow with a `game-slug` message; do not self-trigger.
---

# Artist Self-Evolve

Learn, from a completed project, the prompt patterns and art rules that reliably produced its assets. The lessons are stored in two places:

- `skeletons/<slug>/art-pack.md` — the sub-genre's empirical raw-asset inventory (prompt + layout + Hints per raw image). Direct write, full responsibility.
- `spec/contracts/<x>.md` `#### Artist` chapters — per-pattern asset workflows. You fill the chapter when lead drafts a new or revised contract.

## Input

The lead's dispatch message provides:

- `game-slug` — the project's sub-genre slug. All per-project outputs land under `skeletons/<game-slug>/`.

If `game-slug` is missing from the dispatch message, reply to the lead asking for it. Do not guess from `.vibegame/GDD.md` or `project.json` — the slug is the lead's decision, not yours.

## Workflow

### Phase 0: Find actually-used assets

Scan, in this order:

- `assets/manifest.json` — every registered asset.
- `.vibegame/assets.md` — asset notes and status.
- `.vibegame/GDD.md` — what the design called for.
- The game's runtime code — which manifest keys actually load at runtime.

The output of this phase is the **empirical final-asset list** — the manifest keys actually loaded at runtime, minus anything unused / replaced / stale. This list is internal to your run; you do not write it to a file. Use it as Phase 1's input.

### Phase 1: Trace each final asset back to its raw image; recover prompts; write `art-pack.md`

A final asset rarely equals one raw `vibegame art gen image` output. The same raw image can produce **multiple** final assets — e.g. one decomposed sheet is cut into `icon` + `slot` + `bar`, three final manifest keys. Conversely, every raw image was produced by exactly one prompt invocation (one `imagegen.jsonl` row).

So the art-pack is keyed by **raw image**, not by final asset. Each `### <asset>` heading represents one `vibegame art gen image` call — one prompt, one layout, one `imagegen.jsonl` row. The post-processing that turns a raw into one-or-many final assets is **out of scope** for art-pack; it belongs in the contract's `#### Artist` chapter (Phase 2).

For each distinct raw image behind the final-asset list:

- **Preferred path** — read `.vibegame/logs/imagegen.jsonl` and find the row whose `output` matches the raw image path. The `prompt` field is the verbatim prompt sent to the provider; record it.
- **Fallback path** (the raw has no jsonl record — legacy art, hand-edited, or pre-logging): write a prompt you believe will produce a comparable raw, run `vibegame art gen image` once. Compare the regenerated raw to the original. Iterate the prompt at the **generation** step only — no post-processing tricks. Stop once a fresh single-pass generation meets the same acceptance criterion the original passed.

Write the result to `skeletons/<game-slug>/art-pack.md`. If the file already exists, sync it to the current project state on top of what's there — `art-pack.md` is bound to the project's latest snapshot, refined across runs rather than recreated from scratch.

**Schema** — every `### <asset>` is one raw image.

```
# Art Pack — <game-slug>

## <Group>                          # Background, Player, Boss, FX, UI, Map, Audio, ...

### <raw-asset>                     # name of the raw image, NOT a final manifest key
- prompt                            # verbatim from .vibegame/logs/imagegen.jsonl
  ```
  <verbatim prompt text>
  ```
- layout: <sheet shape>             # 2x2 grid | 1x4 horizontal strip | single frame | 3-section decomposed | ...

**Hints**                           # optional — only when this raw deviates from existing spec/art generic rules
- <delta from the generic rule, e.g. "raw is decomposed into icon+slot+bar; see contract status_bar.md for the cut workflow">

### <raw-asset whose generic rules suffice>
- layout: <sheet shape>             # no Hints block at all
```

Rules:

- If a prompt cannot be recovered (even via fallback), replace the whole `prompt` bullet with a single line `- prompt missing — see <pointer>`, where `<pointer>` is `spec/art/<file>.md § <X>` or `spec/contracts/<file>.md Pattern <N> <slug>` — whichever document owns the generation rules for this raw class.
- The **Hints** section is omitted when existing `spec/art/*` docs already cover the raw. Hints are deltas, not restatements. When the raw is cut into multiple finals, the Hints should point at the contract that owns the cut workflow (the cut itself lives in the contract's `#### Artist` chapter, not here).
- Per-project specifics (image resolution, runtime path, manifest key) are project variables and do **not** belong in art-pack.

This inventory is the **empirical** raw-asset list for the sub-genre — the prompts a real project of this kind ran to produce the manifest, not what the design ideal called for.

### Phase 2: Fill `#### Artist` chapters when the lead requests

The lead drafts new or revised contracts during `self-evolve` Step 5. For each contract whose asset class touches your domain, the lead sends a message asking you to fill that contract's `#### Artist` chapter. Process one contract per message.

The chapter answers exactly three questions, packaged as one Workflow:

1. **Generate** — what assets does this pattern need, and how does artist produce them.
2. **Package** — how does artist turn raw output into shippable final assets, manifest entries, and node templates.
3. **Verify** — what does artist check before handing off.

Canonical references: [`status_bar.md`](../../.vibegame/spec/contracts/status_bar.md) (3-asset composite, bbox verification loop) and [`charge-family.md`](../../.vibegame/spec/contracts/charge-family.md) (3-sheet decomposition, character-scale alignment). Use these as structural templates; do not invent alternative layouts.

#### Body shape

```markdown
#### Artist

<one-line lead: what scope of work artist owns for this pattern. Example:
"Artist owns three independent sprite sheets covering build / peak / release.">

##### Workflow

1. **Generate**

   <asset breakdown — list every raw image this pattern needs and what each
    contains. Point each at its matching `### <raw-asset>` heading in
    `skeletons/<slug>/art-pack.md`. Inline a project-neutral templated prompt
    per raw image. Add any non-obvious generation rules (style anchor, marker
    color, loop closure, character-scale anchor, ...).>

2. **Package**

   <cut + chroma-key + concat + scale alignment, inlined as concrete CLI
    invocations (`vibegame art rmbg`, `cut`, `concat`). End with final asset
    paths under `assets/...`, manifest entries (with `landmark` if any), and
    the `.node.json` shape consumed by the module.>

3. **Verify**

   <`vibegame art label` overlay + `vibegame vlm` PASS/FAIL prompt, iterated
    until PASS. Cover every check artist must clear before delivery: bbox
    alignment on slot, character-scale consistency across sheets, no marker
    halo, loop seam invisible, etc.>

Common mistakes:

- <anti-patterns specific to this asset class — packing 3 sheets into one,
  baking dynamic text into art, delivering hollow slot, marker-colored
  background instead of transparent, ...>
```

#### Rules

- **Only practice-verified content ships.** If artist has not actually run this pattern on a real project — no art-pack entry, no jsonl-recorded prompt, no concrete cut / verify steps you executed — do not invent a plausible chapter. Replace the whole `#### Artist` body with exactly:

  > Artist does not participate in this contract yet. Fill in this part after a successful project.

  Hallucinated plausibility is worse than an honest placeholder: future agents read the contract as ground truth and waste a project chasing a procedure that was never validated.
- **Lead anchors scope.** Form is flexible: a one-line statement, or a statement followed by a short scope bullet list previewing what artist does across the Workflow. Do not stage **asset breakdown** (the per-raw-image inventory: "this pattern needs X / Y / Z") into the lead — that belongs inside the Generate step.
- **Workflow has exactly three steps**, in this order: Generate / Package / Verify. Sub-bullets and code blocks inside each step are encouraged; do not promote them into a fourth top-level step.
- **Templated prompt rule.** The Generate step's prompt must be derived from an actually-ran prompt recorded in `art-pack.md` — never invented from scratch. Replace project-specific subjects with placeholders (`<icon-shape>`, `<fill-color>`, `<player-character>`); keep structural language (layout description, marker-background rules, "no text / no UI", style-preservation clauses) verbatim. art-pack is the instance, contract is the pattern, both ship.
- **Common mistakes** lives outside the Workflow as a flat bullet list. Include whenever artist has nontrivial work; omit only for patterns where artist's output is genuinely decoration with no class-specific traps.
- **No invented sections.** If the pattern has a quirk (e.g. character-scale alignment across sheets, hover-state bbox alignment), fold it into the relevant Workflow step. Do not introduce ad-hoc H5 subsections under Artist outside the Workflow.

#### Writing back

Write the `#### Artist` chapter directly into the contract file at the path the lead provided. The user gate at `self-evolve` Step 3 already approved the *list* of contracts being touched; chapter content is your domain and does not need a second human round-trip.

If the lead's request lacks the file path or the surrounding pattern context, ask the lead before writing — do not guess. After writing, send the lead a one-line confirmation with the file path and any open questions (e.g. "prompt missing in art-pack, left a TODO marker").
