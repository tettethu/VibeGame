/**
 * URL helpers for game resources.
 *
 * Game code must resolve project files through appBasePath. Do not hardcode
 * the old /game prefix or root-relative asset paths in gameplay scripts.
 */

function cleanBasePath(value) {
  const raw = String(value || '')
  if (!raw || raw === '/') return ''
  return raw.replace(/\/+$/, '')
}

function cleanResourcePath(path) {
  return String(path || '').replace(/^\/+/, '')
}

export function appBasePath() {
  const cfg = window.__APP_CONFIG__ || {}
  if (cfg.appBasePath !== undefined) {
    return cleanBasePath(cfg.appBasePath)
  }

  const pathname = new URL('.', document.baseURI).pathname
  return cleanBasePath(pathname)
}

export function apiBaseUrl() {
  const cfg = window.__APP_CONFIG__ || {}
  const raw = String(cfg.apiBaseUrl || '')
  return raw.replace(/\/+$/, '')
}

export function apiUrl(path = '') {
  const base = apiBaseUrl()
  const rel = String(path || '').replace(/^\/+/, '')
  if (!base) return `/${rel}`
  return `${base}/${rel}`
}

export function resourceUrl(path = '') {
  const base = appBasePath()
  const rel = cleanResourcePath(path)
  if (!rel) return base || '/'
  return `${base}/${rel}`
}

export function assetRootUrl() {
  return resourceUrl('assets')
}

export function assetUrl(path = '') {
  const rel = cleanResourcePath(path)
  return rel ? resourceUrl(`assets/${rel}`) : assetRootUrl()
}

export async function fetchJson(path, init = undefined) {
  const res = await fetch(resourceUrl(path), init)
  if (!res.ok) {
    throw new Error(`Failed to load ${path}: ${res.status}`)
  }
  return await res.json()
}
