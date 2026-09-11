/**
 * Global Flatland API and WebSocket configuration.
 *
 * Automatically detects whether the app is running on a static host (e.g. GitHub Pages)
 * or same-origin (production server / localhost).
 */

const isGitHubPages = typeof window !== 'undefined' && window.location.hostname.endsWith('github.io')
const isDemoBuild = typeof __VITE_IS_DEMO__ !== 'undefined' ? Boolean(__VITE_IS_DEMO__) : false
const isDemoEnvironment = isGitHubPages || isDemoBuild

const params = typeof window !== 'undefined' ? new URLSearchParams(window.location.search) : null
const paramBackend = params?.get('backend') || null
const paramWs = params?.get('ws') || null

function decodeEnvUrl(val: unknown): string {
  if (typeof val !== 'string' || !val) return ''
  const str = val.replace(/\\/g, '').trim()
  try {
    if (typeof window !== 'undefined' && window.atob && /^[A-Za-z0-9+/=]+$/.test(str)) {
      const decoded = window.atob(str).replace(/\\/g, '').trim()
      if (decoded.startsWith('http://') || decoded.startsWith('https://') || decoded.startsWith('ws://') || decoded.startsWith('wss://')) {
        return decoded
      }
    }
  } catch {
    // ignore decoding errors
  }
  return str
}

// Configured from .env (API_URL / BACKEND_URL / VITE_BACKEND_URL) via Vite define/import.meta.env
const envApiUrl = decodeEnvUrl(
  (typeof __ENV_API_URL__ !== 'undefined' && __ENV_API_URL__) ||
  ((import.meta as any).env?.VITE_DEMO_API_URL as string) ||
  ((import.meta as any).env?.API_URL as string) ||
  ''
)

const envWsUrl = decodeEnvUrl(
  (typeof __ENV_WS_URL__ !== 'undefined' && __ENV_WS_URL__) ||
  ((import.meta as any).env?.VITE_DEMO_WS_URL as string) ||
  ((import.meta as any).env?.WS_URL as string) ||
  ''
)

export const DEFAULT_REMOTE_BACKEND = (envApiUrl || 'https://world.minhnhan.in').replace(/\/+$/, '')
export const DEFAULT_REMOTE_WS = (envWsUrl && (envWsUrl.startsWith('ws://') || envWsUrl.startsWith('wss://')))
  ? envWsUrl
  : (
    DEFAULT_REMOTE_BACKEND.startsWith('https')
      ? DEFAULT_REMOTE_BACKEND.replace(/^https/, 'wss') + '/ws'
      : DEFAULT_REMOTE_BACKEND.replace(/^http/, 'ws') + '/ws'
  )

export function getBackendBaseUrl(): string {
  if (paramBackend) return paramBackend.replace(/\/+$/, '')
  const metaEnv = (import.meta as any).env
  if (metaEnv?.VITE_BACKEND_URL) return (metaEnv.VITE_BACKEND_URL as string).replace(/\/+$/, '')
  if (isDemoEnvironment) return DEFAULT_REMOTE_BACKEND
  return ''
}

export function getWebSocketUrl(): string {
  if (paramWs) return paramWs
  const metaEnv = (import.meta as any).env
  if (metaEnv?.VITE_WS_URL) return metaEnv.VITE_WS_URL as string
  if (paramBackend) {
    const wsProto = paramBackend.startsWith('https') ? 'wss:' : 'ws:'
    const host = paramBackend.replace(/^https?:\/\//, '').replace(/\/+$/, '')
    return `${wsProto}//${host}/ws`
  }
  if (isDemoEnvironment) return DEFAULT_REMOTE_WS
  const proto = typeof window !== 'undefined' && window.location.protocol === 'https:' ? 'wss' : 'ws'
  const host = typeof window !== 'undefined' ? window.location.host : 'localhost:8000'
  return `${proto}://${host}/ws`
}

const envFrontendUrl = (typeof __ENV_FRONTEND_URL__ !== 'undefined' && __ENV_FRONTEND_URL__) ||
  ((import.meta as any).env?.VITE_FRONTEND_URL as string) ||
  ((import.meta as any).env?.FRONTEND_URL as string) ||
  (typeof __ENV_DEMO_URL__ !== 'undefined' && __ENV_DEMO_URL__) ||
  ((import.meta as any).env?.VITE_DEMO_URL as string) ||
  ((import.meta as any).env?.DEMO_URL as string) ||
  ''

const envLandingUrl = (typeof __ENV_LANDING_URL__ !== 'undefined' && __ENV_LANDING_URL__) ||
  ((import.meta as any).env?.VITE_LANDING_URL as string) ||
  ((import.meta as any).env?.LANDING_URL as string) ||
  ''

export function getFrontendUrl(): string {
  if (envFrontendUrl) return envFrontendUrl.replace(/\/+$/, '') + '/'
  if (typeof window !== 'undefined') {
    const loc = window.location
    if (loc.pathname.includes('/demo')) {
      const demo = loc.pathname.replace(/\/demo(\/.*)?$/, '/demo/')
      return `${loc.origin}${demo}`
    }
    return `${loc.origin}/`
  }
  return ''
}

export function getDemoUrl(): string {
  return getFrontendUrl()
}

export function getLandingUrl(): string {
  if (envLandingUrl) return envLandingUrl.replace(/\/+$/, '') + '/'
  if (typeof window !== 'undefined') {
    const loc = window.location
    if (loc.pathname.includes('/demo')) {
      const parent = loc.pathname.replace(/\/demo(\/.*)?$/, '') || '/'
      return `${loc.origin}${parent.endsWith('/') ? parent : parent + '/'}`
    }
    return `${loc.origin}/`
  }
  return ''
}

/**
 * Resolves user-facing documentation / page links.
 * When running in demo mode, resolves to relative demo paths
 * so the backend domain is completely hidden and links depend on the host from .env.
 */
export function docUrl(path: string): string {
  if (isDemoEnvironment) {
    if (path.startsWith('/wiki')) {
      const rest = path.slice('/wiki'.length)
      return `./wiki/${rest}`
    }
    if (path.startsWith('/docs')) {
      const rest = path.slice('/docs'.length)
      return `./docs/${rest}`
    }
    if (path.startsWith('/health')) {
      const rest = path.slice('/health'.length)
      return `./health/${rest}`
    }
    if (path.startsWith('/openapi.json')) {
      return './openapi.json'
    }
    if (path.startsWith('/api/wiki')) {
      return './wiki/'
    }
    return `./${path.replace(/^\/+/, '')}`
  }
  return path.startsWith('/') ? path : `/${path}`
}

export function apiUrl(path: string): string {
  return docUrl(path)
}

/**
 * Automatically transparently rewrite `/api/*` fetch requests to target the
 * remote backend when running on a static host (like GitHub Pages).
 */
export function initApiInterceptor(): void {
  if (typeof window === 'undefined') return
  const base = getBackendBaseUrl()
  if (!base) return

  const originalFetch = window.fetch
  window.fetch = function (input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
    if (typeof input === 'string' && input.startsWith('/api/')) {
      return originalFetch(`${base}${input}`, init)
    }
    if (typeof input === 'string' && input.startsWith('/healthz')) {
      return originalFetch(`${base}${input}`, init)
    }
    if (input instanceof URL && (input.pathname.startsWith('/api/') || input.pathname.startsWith('/healthz'))) {
      return originalFetch(`${base}${input.pathname}${input.search}`, init)
    }
    return originalFetch(input, init)
  }
}
