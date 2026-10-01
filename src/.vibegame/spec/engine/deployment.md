# Game deployment

This guide covers packaging a game, not publishing the VibeGame toolkit. Local development and testing are in [the main guide](index.md#runtime-control).

## Release payload

Run from a Git-backed game project:

~~~sh
vibegame release --dry-run
vibegame release
vibegame release -b prod
~~~

The default destination is the local release branch. A dry run validates and reports the payload without updating that branch. Normal release commits only when its content changes. It does not push or deploy anything.

Default roots are index.html, project.json, config/, scenes/, scripts/ and engine/. Explicitly add other runtime directories, including entities/, modules/ and maps/ when your game uses them:

~~~json
{
  "releaseExtraRoots": [
    "entities/",
    "modules/",
    "maps/",
    "server/package.json",
    "server/package-lock.json",
    "server/src/"
  ]
}
~~~

List only files/directories needed by the shipped game. Do not add whole asset directories to releaseExtraRoots to bypass manifest selection.

Every manifest listed in project.json.manifests is included, together with the files referenced by the final merged entries. Later manifests override earlier keys. Entry path and image values resolve relative to their own manifest. If manifests is omitted, the default is ["assets/manifest.json"].

Missing referenced files or references into assets/artifacts/ fail the release. Dev tooling, task documents, screenshots, tests and unreferenced asset files are not part of the normal payload. Never put private keys into runtime files.

The command uses a temporary worktree; it does not switch the source branch. Do not keep the destination branch checked out in another worktree while regenerating it. Release needs a source branch, not detached HEAD.

## URLs and hosting

Keep the initialized index.html boot entry. Serve the generated branch over HTTP; it needs no frontend build step. A game with a custom backend still needs that backend installed and started by its deployment environment.

window.__APP_CONFIG__ supplies two independent values:

Field -> Purpose:
- appBasePath: Project resource prefix, e.g. /games/demo
- apiBaseUrl: Business API base URL; empty means origin-root API paths

vibegame run injects project.json.runtimeDefaults.dev. A custom deployment server must implement its own configuration injection, before the boot entry; runtimeDefaults.deploy is available as project data, not an automatic server.

~~~json
{
  "runtimeDefaults": {
    "dev": {"appBasePath": "", "apiBaseUrl": "http://127.0.0.1:3001"},
    "deploy": {"appBasePath": "/games/demo", "apiBaseUrl": "https://api.example.com"}
  }
}
~~~

From scripts/, import helpers from ../engine/url.js:

Helper -> Example result:
- resourceUrl('config/input-map.json'): /games/demo/config/input-map.json
- assetUrl('ui/heart.svg'): /games/demo/assets/ui/heart.svg
- apiUrl('api/save'): https://api.example.com/api/save

Use resourceUrl/assetUrl for project files and apiUrl for business endpoints. There is no /game alias. apiUrl does not automatically prepend appBasePath. Query-string or per-scene serverUrl overrides are not a general engine rule.

Before publishing, test the release payload at its actual URL prefix and check network failures, all scenes, dynamically spawned entities and DOM assets. Push the release branch and update the host only when the user requests it.
