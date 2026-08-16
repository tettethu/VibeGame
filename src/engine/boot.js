/**
 * Engine bootstrap: loads project config, scene, assets, scripts,
 * then starts PhaserHost + SceneTree. Extracted from play.html so
 * the engine startup logic lives in one upgradable place.
 */

import { SceneTree } from './SceneTree.js'
import { PhaserHost } from './PhaserHost.js'
import { InputMap } from './InputMap.js'
import { RuntimeBridge } from './RuntimeBridge.js'
import { RuntimeController } from './RuntimeController.js'
import { UiLayer } from './UiLayer.js'
import { appBasePath, assetRootUrl, resourceUrl } from './url.js'

const _appCfg = window.__APP_CONFIG__ || {}
const ENGINE_SCRIPTS = new Set(['TileMap', 'Collider', 'MountPoint'])

function collectSrcPaths(def, paths = new Set()) {
  if (def.src) paths.add(def.src)
  if (def.children) def.children.forEach(c => collectSrcPaths(c, paths))
  return paths
}

/**
 * Given a manifest path like 'assets/player/manifest.json', return the
 * directory portion relative to the global assets root (e.g. 'player/').
 * Returns '' for top-level 'assets/manifest.json' so existing single-manifest
 * projects keep working unchanged.
 */
function manifestDirRelativeToAssets(manifestPath) {
  // Drop leading 'assets/' (or '/assets/'); drop trailing 'manifest.json'.
  let p = manifestPath.replace(/^\/+/, '').replace(/^assets\/?/, '')
  p = p.replace(/manifest\.json$/, '')
  return p  // '' or 'player/' or 'enemies/boss/'
}

/**
 * Return a copy of `entry` with `path` prefixed by `dir`.
 * Leaves the entry untouched when dir is empty.
 */
function prefixManifestEntry(entry, dir) {
  if (!dir) return entry
  const out = { ...entry }
  if (typeof out.path === 'string') out.path = dir + out.path
  return out
}

function collectTilemapSrcs(def, tilemapSrcs = new Set()) {
  if (def.script === 'TileMap' && def.config?.src) {
    tilemapSrcs.add(def.config.src)
  }
  if (def.children) {
    for (const child of def.children) collectTilemapSrcs(child, tilemapSrcs)
  }
  return tilemapSrcs
}

function rendererTypeFromParam(value) {
  const renderer = String(value || '').toLowerCase()
  if (renderer === 'canvas') return Phaser.CANVAS
  if (renderer === 'webgl') return Phaser.WEBGL
  return null
}

// Render FPS cap cascade: ?fps= session override > project settings.fpsLimit >
// engine default (60 for runtime sessions, uncapped for player sessions).
// Phaser follows rAF, so on high-refresh displays (120/180Hz) an uncapped game
// renders at display rate — runtime/test sessions pay 2-3x CPU for frames nobody
// needs. The runtime default keeps automation cost machine-independent.
// 0 means explicitly uncapped.
function resolveFpsLimit(searchParams, settings, runtimeToken) {
  const raw = searchParams.get('fps')
  if (raw !== null && raw !== '') {
    const n = Number(raw)
    if (Number.isFinite(n) && n >= 0) return Math.floor(n)
  }
  const proj = Number(settings?.fpsLimit)
  if (Number.isFinite(proj) && proj > 0) return Math.floor(proj)
  return runtimeToken ? 60 : 0
}

/**
 * Boot the game engine into a container element.
 * @param {HTMLElement} container - DOM element for Phaser canvas
 * @param {object} [options]
 * @param {function} [options.onError] - called with error message on failure
 */
export async function boot(container, options = {}) {
  const onError = options.onError || ((msg) => {
    container.textContent = 'Error: ' + msg
  })

  try {
    const projRes = await fetch(resourceUrl('project.json'))
    if (!projRes.ok) { onError('project.json not found'); return }
    const proj = await projRes.json()

    const sceneRes = await fetch(resourceUrl(proj.startScene))
    if (!sceneRes.ok) {
      onError('start scene not found (' + proj.startScene + ')')
      return
    }
    const sceneJson = await sceneRes.json()

    const sceneTree = new SceneTree()

    // Asset manifests (multiple, merged).
    //
    // Each manifest's entry `path` is interpreted as
    // relative to **that manifest's own directory** (not the project's
    // assetBasePath). At merge time we prefix each entry path with the
    // manifest's directory relative to assetBasePath, so PhaserHost can
    // join them all to a single base.
    //
    // Example: project.json.manifests = ['assets/manifest.json',
    //                                    'assets/player/manifest.json']
    //   - assets/manifest.json:        { hp: { path: 'hp.png' } }
    //     -> stays { hp: { path: 'hp.png' } }
    //   - assets/player/manifest.json: { idle: { path: 'idle.png' } }
    //     -> rewritten to { idle: { path: 'player/idle.png' } }
    const manifestPaths = proj.manifests || ['assets/manifest.json']
    const mergedManifest = {}
    for (const mp of manifestPaths) {
      try {
        const mRes = await fetch(resourceUrl(mp))
        if (!mRes.ok) continue
        const data = await mRes.json()
        const dir = manifestDirRelativeToAssets(mp)
        for (const [key, entry] of Object.entries(data)) {
          mergedManifest[key] = prefixManifestEntry(entry, dir)
        }
      } catch {}
    }
    if (Object.keys(mergedManifest).length) sceneTree.assetManifest = mergedManifest

    // .node.json definitions (src fields)
    const srcPaths = collectSrcPaths(sceneJson.root)
    for (const p of srcPaths) {
      try {
        const res = await fetch(resourceUrl(p))
        if (res.ok) sceneTree.nodeDefinitions[p] = await res.json()
      } catch {}
    }

    // Register tilesets from manifest (inline tile data, no external file needed)
    if (sceneTree.assetManifest) {
      for (const [key, entry] of Object.entries(sceneTree.assetManifest)) {
        if (entry.type !== 'tileset') continue
        sceneTree.tilesets[key] = { name: key, ...entry }
      }
    }

    // External tilemaps
    const tilemapSrcs = collectTilemapSrcs(sceneJson.root)
    for (const src of tilemapSrcs) {
      try {
        const res = await fetch(resourceUrl(src))
        if (res.ok) sceneTree.tilemaps[src] = await res.json()
      } catch {}
    }

    // Warn for tilemaps referencing tilesets not in manifest
    if (sceneTree.assetManifest) {
      for (const src of tilemapSrcs) {
        const tmData = sceneTree.tilemaps[src]
        if (tmData?.tileset && !sceneTree.tilesets[tmData.tileset]) {
          console.warn(`Tilemap "${src}" references tileset "${tmData.tileset}" not found in manifest`)
        }
      }
    }

    // Load scripts
    // Resolution order by name:
    //   1. Built-in engine scripts (TileMap, Collider, MountPoint) -> engine/scripts/
    //   2. Names ending with "Module" -> modules/ (shipped reusable components)
    //   3. Everything else -> scripts/ (project-owned game scripts)
    const _t = '?_=' + Date.now()
    const scriptNames = SceneTree.collectScripts(
      sceneJson.root, new Set(), sceneTree.nodeDefinitions
    )
    for (const name of scriptNames) {
      let base
      if (ENGINE_SCRIPTS.has(name)) base = resourceUrl('engine/scripts')
      else if (name.endsWith('Module')) base = resourceUrl('modules')
      else base = resourceUrl('scripts')
      await sceneTree.loadScript(name, base + '/' + name + '.js' + _t)
    }

    // Input map
    let inputMapJson = {}
    try {
      const imRes = await fetch(resourceUrl(proj.inputMap || 'config/input-map.json'))
      if (imRes.ok) inputMapJson = await imRes.json()
    } catch {}

    // Start game
    const searchParams = new URLSearchParams(location.search)
    const runtimeToken = searchParams.get('runtime')
    const runtimeActivate = runtimeToken && (
      searchParams.get('activate') === '1' || searchParams.get('debug') === '1'
    )
    // physicsDebug URL param only applies for manual local debugging (no runtime/bot token).
    // Bot test sessions always use project.json settings so screenshots stay clean.
    const physicsDebug = searchParams.get('physicsDebug') === '1'
    const runtimeProjectConfig = physicsDebug
      ? {
          ...proj,
          settings: {
            ...(proj.settings || {}),
            physics: { ...((proj.settings || {}).physics || {}), debug: true },
          },
        }
      : proj
    // Install console/network buffers early so script-load errors are captured
    if (runtimeToken) RuntimeBridge.installBuffers()
    const host = new PhaserHost()
    host.rendererType = rendererTypeFromParam(searchParams.get('renderer'))
    host.fpsLimit = resolveFpsLimit(searchParams, proj.settings, runtimeToken)
    host.sceneTree = sceneTree
    host.assetManifest = sceneTree.assetManifest
    host.assetBasePath = assetRootUrl()
    sceneTree.apiBaseUrl = _appCfg.apiBaseUrl || ''

    host.onReady = async (phaserScene) => {
      sceneTree.phaserScene = phaserScene
      sceneTree.inputMap = new InputMap(phaserScene, inputMapJson)
      sceneTree.ui = new UiLayer({
        container,
        canvas: host.game.canvas,
        logicalWidth: Number(runtimeProjectConfig.settings?.width || 800),
        logicalHeight: Number(runtimeProjectConfig.settings?.height || 600),
        manifest: sceneTree.assetManifest,
        assetBasePath: host.assetBasePath,
      })
      await sceneTree.load(sceneJson)
      sceneTree.running = true

      // Always construct a RuntimeController so __vibegameTest.snapshot() works
      // in bot mode without forcing runtime control (which would pause the game).
      // Only activate it (pause + step semantics) when the URL flag asks for it.
      sceneTree.runtimeController = new RuntimeController(sceneTree)
      if (runtimeActivate) {
        sceneTree.runtimeController.activate()
      }

      // Connect RuntimeBridge when launched with runtime token (by Playwright)
      if (runtimeToken) {
        const proto = location.protocol === 'https:' ? 'wss:' : 'ws:'
        const bridge = new RuntimeBridge(host, sceneTree)
        bridge.connect(`${proto}//${location.host}${appBasePath()}/ws/runtime?token=${runtimeToken}`)
      }

      // In-process testing surface for `vibegame run --bot`. Same data as
      // GET /api/runtime/snapshot but synchronous (no HTTP roundtrip).
      // `activate()` is for the breakpoint path: bot returns ("breakpoint", ...)
      // and the runner flips engine into stepped runtime-control mode.
      window.__vibegameTest = {
        snapshot: () => sceneTree.runtimeController.snapshot(),
        activate: () => sceneTree.runtimeController.activate(),
        gameToClient: (x, y) => {
          const cam = host.phaserScene.cameras.main
          const cx = (x - cam.scrollX) * cam.zoom
          const cy = (y - cam.scrollY) * cam.zoom
          const rect = host.game.canvas.getBoundingClientRect()
          const scale = host.game.scale.displayScale
          return {
            x: cx * scale.x + rect.left,
            y: cy * scale.y + rect.top,
          }
        },
      }

      // Signal that the engine is fully ready (used by Playwright wait)
      window.__vibegame_ready = true
    }

    host.init(container, runtimeProjectConfig)
  } catch (err) {
    console.error('Game init error:', err)
    onError(err.message)
  }
}
