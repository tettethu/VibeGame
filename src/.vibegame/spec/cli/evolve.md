# Evolve

`vibegame evolve` copies one user-approved shared prior from a finished game project into the VibeGame source checkout used by the installed CLI.

```sh
vibegame evolve skeleton -n <kebab-case-slug>
vibegame evolve module -n <PascalCaseModule>
vibegame evolve contract -n <kebab-case-slug>
```

Use `--project <path>` when the game project is not the current directory. Use `--dry-run` to validate and show the exact copy plan without writing it.

## Destinations

| Type | Game project candidate | Source destination |
|---|---|---|
| `skeleton` | `skeletons/<name>/` | `src/skeletons/<name>/` |
| `module` | `modules/<name>.js` and optional `modules/check/<name>.check.py` | Matching files under `src/modules/` |
| `contract` | `.vibegame/spec/contracts/<name>.md` | `src/.vibegame/spec/contracts/<name>.md` |

If any destination already exists, the command stops without changing the source checkout. Compare and resolve the existing prior manually. The command does not support replacement or merging.

The command never changes an `index.md`. After a successful promotion, it prints the absolute path of the source index that requires a manual edit. Do not infer the source checkout from the game project. If that path is outside the current game project, obtain user permission before editing it. The command never commits or pushes.

## Skeleton copy boundary

A skeleton promotion copies only these root files:

```text
project.json
index.html
index.md
art-pack.md
errors.md
```

It recursively copies only the matching files in these directories:

```text
config/**/*.json
scenes/**/*.scene.json
entities/**/*.node.json
scripts/**/*.js
art-pack-assets/**/*.{png,jpg,jpeg,webp}
```

Under `assets/`, it copies only the manifests listed by `project.json.manifests` and the files referenced by those manifests. An asset path is relative to the directory containing its manifest.

Everything else is shown as `not copied`. This includes local `engine/`, `modules/`, `stages/`, `vendor/`, `.vibegame/`, `tests/`, logs, caches, screenshots, videos, and unselected assets.

Before writing, the command copies the allowlisted files into staging, runs `vibegame check` against that staged skeleton, and boots the staged skeleton in the runtime. This verifies the result without relying on unlisted project directories.

## Validation

The command rejects invalid names, selected symlinks, non-UTF-8 selected text, invalid selected JSON, private absolute paths, invalid reference images, missing manifest assets, asset paths outside `assets/`, and staged skeletons that do not pass check or boot.

The complete prior is staged before the final write. A failure does not leave a partial destination.

The command finds the source checkout from its installed code location. Do not pass or hardcode a source repo path, and do not promote shared priors with `cp`, `rsync`, or manual whole-directory copying.
