/** API client wrappers for the Dashboard editor. */

export async function api(path, opts) {
  const r = await fetch(path, opts)
  return r.json()
}

export async function fetchAssetTree() {
  return api('/api/assets/tree')
}

export async function fetchAssetSubtree(path) {
  return api(`/api/assets/tree?root=${encodeURIComponent(path)}`)
}

export async function fetchManifestRaw(folder) {
  return api(`/api/assets/manifest-raw?folder=${encodeURIComponent(folder)}`)
}

export async function putManifestRaw(folder, data) {
  const resp = await fetch('/api/assets/manifest-raw', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ folder, data }),
  })
  return resp.ok ? { ok: true } : resp.json()
}

export async function fetchNodeTree() {
  return api('/api/nodes/tree')
}

export async function fetchNode(path) {
  return api(`/api/nodes/${encodeURIComponent(path)}`)
}

export async function putNode(path, data, changes = [], action = 'save') {
  const resp = await fetch(`/api/nodes/${encodeURIComponent(path)}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ data, changes, action }),
  })
  return resp.ok ? { ok: true } : resp.json()
}

export async function resolveNodeTexture(key) {
  return api(`/api/nodes/resolve-texture?key=${encodeURIComponent(key)}`)
}
