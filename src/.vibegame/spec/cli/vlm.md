# vibegame vlm — Vision Language Model Query

Call a Vision Language Model via any OpenAI-compatible endpoint. Supports text-only questions or text + one/more images.

---

## When to use

**Use `vibegame vlm` only when you need a dedicated visual review** that your own native vision isn't suited for:

- Detailed pixel-level quality assessment of generated assets
- Side-by-side comparison of many variants (batch critique)
- Structured scoring / rubric-based evaluation that must be repeatable
- Asking a *different* model for a second opinion (e.g. Gemini vs. GPT-4o)
- Automated pipelines where a human-in-the-loop isn't available

**Do NOT use it for normal image viewing.** Your own vision capability is enough for:
- "Does this sprite look right?"
- "What's in this screenshot?"
- "Did the layout change after my edit?"

Calling an external VLM for those wastes tokens, adds latency, and risks losing context.

---

## What VLM verdicts you can trust (and what you cannot)

VLMs — both `vibegame vlm` and your own native vision — are **semantic judges, not measurement instruments**. They answer "is this aligned / wrong / clipping?" reliably; they do not answer "by how many pixels?" reliably.

**Trust as authoritative**: binary and directional yes/no judgements.
- "is the player's feet on the visible ground, above it, or below it?" → trust the answer
- "is this UI element overlapping that one?" → trust
- "does this sprite read as the wrong proportion?" → trust
- "is the bounding box framed precisely around the subject?" → trust

**Treat as rough hint only**: any numeric estimate the VLM volunteers.
- "feet are about 10 px below" / "the box is roughly 30% too wide" → directionally useful, numerically unreliable
- Use the magnitude bucket (clearly off / barely off / aligned) to pick a step size for an iteration loop, but **never** plug the VLM's number directly into a code value as if it were measured.

**Never ask for**: absolute pixel coordinates, exact offsets, exact scales. The model will give you a confident-looking number that is mostly fiction.

This is why visual fine-tuning is a **binary search loop** (player edits a value, asks the VLM yes/no, iterates) rather than a one-shot correction. The verifier converges through repeated yes/no, not through measurement.

---

## Environment

Requires two env vars (read from `<git_root>/.env`):

```
VLM_BASE_URL=https://api.openai.com/v1              # end at /v1, NOT /chat/completions
VLM_API_KEY=sk-xxxxxxxxxxxxxxxxxxxx
VLM_MODEL=gpt-5-mini                                # optional model id
```

Any OpenAI-compatible provider works (OpenAI, local Ollama with OpenAI shim, or any other endpoint you choose).

---

## Parameters

| Flag | Description |
|---|---|
| `-t`, `--text` | *Required.* User prompt. Plain text, or a path to a text file (auto-loaded). |
| `-i`, `--image` | Image path, URL, or folder (folders are expanded to all contained images). Repeatable. Omit for text-only queries. |
| `-s`, `--system` | System prompt — role / format / persona. Plain text or a path to a text file (auto-loaded). |
| `-m`, `--model` | Override `VLM_MODEL` for this call. |
| `--add-background` | Composite local images onto a solid background before sending them to the VLM. Useful for reviewing transparent sprites, halos, and background-removal artifacts. Accepts `white`, `black`, `magenta`, `green`, `cyan`, `#RRGGBB`, or `R,G,B`. `magenta` means `#FF00FF`. |

### Background compositing

Use `--add-background` when the source image has transparency and the VLM needs a visible backdrop to judge edges, leftover pixels, or silhouette readability.

- The original source image is not modified.
- The CLI creates temporary PNGs and sends those to the VLM.
- This option supports local image files and folders.
- This option does not support image URLs.
- Use `magenta` for strict transparent-background checks because `#FF00FF` makes leftover pixels easy to see.

### Prompt input

`-t/--text` and `-s/--system` accept either a literal string or a path to a text file with one of: `.txt`, `.md`, `.log`, `.rst`. The CLI prints which one it used on the first line:

```
Loaded prompt from prompts/critique_rubric.md
... (model output)
```

```
Using raw text as prompt
... (model output)
```

A path with any other extension (e.g. `.json`, `.yaml`) or to a non-existent file is treated as a literal string.

---

## Examples

```sh
# Text-only query
vibegame vlm -t "what pixel size works best for a top-down RPG character?"

# Single image critique
vibegame vlm -i assets/hero/idle.png -t "critique the silhouette and color palette"

# Compare frames
vibegame vlm -i frame_0.png -i frame_1.png -t "describe what changed between these frames"

# Batch review of a folder
vibegame vlm -i assets/enemies/ -t "pick the frame with the clearest attack pose"

# Check a transparent sprite against magenta
vibegame vlm -i assets/hero/idle.png --add-background magenta -t "is any white halo or leftover background visible?"

# With system prompt and prompt-from-file
vibegame vlm \
  -s "You are a pixel art reviewer. Score 1-10 on: silhouette, palette, readability. Reply in Chinese." \
  -i assets/hero/run_0.png \
  -t prompts/critique_rubric.md

# Use a different model than default
vibegame vlm -i shot.png -t "describe this image" -m gpt-4o
```

---

## Notes

- Output is printed to stdout — pipe or redirect as needed.
- `max_tokens` is fixed at 4096.
- Default timeout is 120s.
- The CLI fails loudly if `VLM_BASE_URL` or `VLM_API_KEY` is missing; it does not fall back to other env vars.
- `--add-background` writes temporary PNGs and does not modify source images. It supports local image paths and folders, not image URLs.
