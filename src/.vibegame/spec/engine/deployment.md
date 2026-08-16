# Deployment Guide

How vibegame projects go from local dev to production deployment.

---

## Three Stages

| Stage | Tool | Purpose |
|-------|------|---------|
| Local dev | `vibegame run` | Serve game page + inject dev config |
| Release branch | `vibegame release` | Generate pure deployment branch |
| Server deploy | `git reset --hard origin/release` | Deploy the clean branch |

---

## Runtime Config Injection

### The Config Object

`window.__APP_CONFIG__` is the single configuration entry point consumed by the page. It has two fields:

| Field | Type | Description |
|-------|------|-------------|
| `appBasePath` | string | URL path prefix for sub-path serving (e.g. `/games/trpg/`) |
| `apiBaseUrl` | string | Business API base URL (e.g. `http://127.0.0.1:3001`) |

### project.json Declaration

```json
{
  "runtimeDefaults": {
    "dev": {
      "appBasePath": "",
      "apiBaseUrl": "http://127.0.0.1:3001"
    },
    "deploy": {
      "appBasePath": "",
      "apiBaseUrl": ""
    }
  }
}
```

- `dev` block: used by `vibegame run` to inject local development defaults.
- `deploy` block: used by project's deploy server as baseline, overridable by env vars.

### Injection Flow

```
project.json.runtimeDefaults.dev
         |
         v
   vibegame run reads dev defaults
         |
         v
   Injects <script>window.__APP_CONFIG__ = {...}</script>
   before the fallback script in index.html
         |
         v
   index.html fallback: window.__APP_CONFIG__ = window.__APP_CONFIG__ || { appBasePath: '', apiBaseUrl: '' }
         |
         v
   boot.js reads __APP_CONFIG__.appBasePath -> resolves project resource URLs
   game scripts read __APP_CONFIG__.apiBaseUrl -> constructs API request URLs
```

For deploy servers, the flow is the same but reads `runtimeDefaults.deploy` and layers env vars (`APP_BASE_PATH`, `API_BASE_URL`) on top.

### API URL Priority

When game scripts construct API request URLs, the resolution order is:

1. **URL query `?serverUrl=`** - emergency runtime override
2. **Scene config `serverUrl`** - per-scene override
3. **`window.__APP_CONFIG__.apiBaseUrl`** - injected from project.json
4. **`location.origin + appBasePath`** - same-origin fallback

### Resource Path Resolution

`boot.js` resolves project resource URLs through `engine/url.js`:

- `resourceUrl('project.json')` -> `${appBasePath}/project.json`
- `resourceUrl('config/player.json')` -> `${appBasePath}/config/player.json`
- `assetUrl('ui/icon_heart.svg')` -> `${appBasePath}/assets/ui/icon_heart.svg`

`appBasePath` is the only project path prefix. `vibegame run` intentionally does not provide a `/game/...` alias, so static previews and normal deployment catch the same path bugs.

### index.html Template

The HTML template has two key elements:

1. **Fallback config script** (before `</head>`):
```html
<script>window.__APP_CONFIG__ = window.__APP_CONFIG__ || { appBasePath: '', apiBaseUrl: '' }</script>
```
The `||` idiom means: keep server-injected values if present, otherwise use empty-string defaults.

2. **Dynamic boot import** (in `<body>`):
```html
<script type="module">
  const cfg = window.__APP_CONFIG__ || {}
  const base = String(cfg.appBasePath || '').replace(/\/+$/, '')
  const { boot } = await import(`${base}/engine/boot.js`)
  boot(document.getElementById('game-container'))
</script>
```

---

## Release Branch Generation

### Overview

`vibegame release` generates a pure deployment branch containing only runtime-needed files.

```bash
vibegame release              # generate/update 'release' branch
vibegame release --dry-run    # validate without writing
vibegame release -b prod      # custom branch name
```

### What Goes Into Release

**Default runtime roots** (always included):
- `index.html`, `project.json`
- `config/`, `scenes/`, `scripts/`, `engine/`

**Project-specific extras** via `project.json.releaseExtraRoots`:
```json
{
  "releaseExtraRoots": [
    "server/package.json",
    "server/package-lock.json",
    "server/src/"
  ]
}
```

**Manifest-selected assets**: every file in `project.json.manifests` plus files referenced by the final merged entries. Entry `path` and `image` values resolve relative to their manifest directory. Later manifests override earlier entries with the same key.

### What Does NOT Go Into Release

- `.claude/`, `.codex/`, `.vibegame/` (dev tooling)
- `assets/artifacts/` (build intermediates)
- Tests, saves, screenshots, task docs

### Asset Rules

- Assets are collected from `project.json.manifests`, defaulting to `["assets/manifest.json"]`.
- Do not add whole asset subdirectories to `releaseExtraRoots`.
- Manifest entries pointing into `assets/artifacts/` cause immediate failure (fail-fast).
- Missing referenced asset files cause immediate failure.
- Force-add is used to include assets that are `.gitignore`d in the source repo.

### Git Strategy

1. Creates a temporary git worktree (no pollution of dev branch).
2. Clears everything except `.git` in the worktree.
3. Copies allowlisted runtime roots and manifest assets.
4. Writes a release-specific `.gitignore`.
5. Commits only if content changed (idempotent).

### Release Commit Message

```
release: main@4a9177b

source: main
sha: 4a9177b...
assets: 12
```

### Failure Conditions

| Condition | Exit Code |
|-----------|-----------|
| Not a game project (no project.json) | 1 |
| manifest.json missing or invalid | 2 |
| Referenced asset file missing | 3 |
| Manifest entry points to artifacts/ | 4 |
| Release branch in active worktree | 1 |
| Detached HEAD | 1 |

### Deploy Server Workflow

On the server:

```bash
git fetch origin
git reset --hard origin/release
# restart server if needed
```

The release branch is directly deployable - no build step required.
