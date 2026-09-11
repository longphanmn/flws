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

// Configured from .env (API_URL / BACKEND_URL / VITE_BACKEND_URL) via Vite define/import.meta.env
const envApiUrl = (typeof __ENV_API_URL__ !== 'undefined' && __ENV_API_URL__) ||
  ((import.meta as any).env?.VITE_DEMO_API_URL as string) ||
  ((import.meta as any).env?.API_URL as string) ||
  'https://world.minhnhan.in'

const envWsUrl = (typeof __ENV_WS_URL__ !== 'undefined' && __ENV_WS_URL__) ||
  ((import.meta as any).env?.VITE_DEMO_WS_URL as string) ||
  ((import.meta as any).env?.WS_URL as string) ||
  ''

export const DEFAULT_REMOTE_BACKEND = envApiUrl.replace(/\/+$/, '')
export const DEFAULT_REMOTE_WS = envWsUrl || (
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

export function apiUrl(path: string): string {
  const base = getBackendBaseUrl()
  const cleanPath = path.startsWith('/') ? path : `/${path}`
  return `${base}${cleanPath}`
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
