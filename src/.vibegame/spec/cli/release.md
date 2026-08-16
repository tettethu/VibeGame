# Release Branch Guide

Use `vibegame release` to build or refresh a pure release branch for direct deployment.

## Goal

The release branch is a curated runtime branch, not a mirror of the dev branch.

It should contain only:
- root runtime entry files (`index.html`, `project.json`)
- game data (`config/`, `scenes/`, `scripts/`, `engine/`)
- project-specific extra roots declared in `project.json.releaseExtraRoots`
- every manifest listed in `project.json.manifests` and the asset files selected by their merged entries

It should not contain:
- agent and editor support directories (`.claude`, `.codex`, `.vibegame`)
- `assets/artifacts/`
- tests, saves, screenshots, or task docs

## Usage

```bash
# Generate or refresh release branch
vibegame release

# Validate without writing
vibegame release --dry-run

# Custom branch name
vibegame release -b production
```

## Default Runtime Roots

Standard vibegame projects include these by default:
- `index.html`
- `project.json`
- `config/`
- `scenes/`
- `scripts/`
- `engine/`

## Project-Specific Extensions

Projects that have additional runtime files (e.g. a deploy server) can declare extras in `project.json`:

```json
{
  "releaseExtraRoots": [
    "server/package.json",
    "server/package-lock.json",
    "server/src/"
  ]
}
```

These are appended to the default roots during release.

## Asset Rules

Asset collection follows `project.json.manifests`, defaulting to `["assets/manifest.json"]`.

Game release loads manifests in list order. Later entries replace earlier entries with the same key, matching engine merge behavior. Entry `path` and `image` values are resolved relative to the directory containing that manifest.

The payload includes:
- every listed manifest file
- `path`, when present on each final merged entry
- `image`, when present on each final merged entry

An asset referenced only by an overridden earlier entry is not copied. Do not add whole `assets/*/` directories to `releaseExtraRoots`; listed manifests are the authoritative asset source.

If a manifest entry points into `assets/artifacts/`, release will fail fast.

Reason:
- the release branch contract says `assets/artifacts/` is not part of the pure deploy payload
- silently rewriting manifest paths would change runtime behavior
- silently copying artifact-backed files would violate the branch contract

## Git Strategy

Generate the payload in a temporary git worktree.

Do not:
- switch the caller's current branch
- rewrite the source worktree in place
- rely on `git archive` to provide assets, because assets are ignored in the source repo

Do:
- resolve source assets from the real filesystem
- copy only allowlisted runtime roots into the release worktree
- force-add manifest-selected asset files (bypassing .gitignore)
- write a release-specific `.gitignore`
- commit only when the curated payload changed

## Traceability

Each release commit records:
- source branch name
- source HEAD sha
- asset count
- whether the branch was created or refreshed

## Failure Conditions

`vibegame release` stops with a clear error when:
- `project.json` is missing (not a game project)
- `project.json.manifests` is invalid, or a listed manifest is missing or invalid
- a manifest-selected asset file is missing
- any manifest entry points into `assets/artifacts/`
- the release branch is checked out in another worktree
- current branch cannot be determined (detached HEAD)

## Deploy Workflow

The full deployment chain:

1. Local development: `vibegame run`
2. Generate release branch: `vibegame release`
3. Server deploy: `git reset --hard origin/release`
