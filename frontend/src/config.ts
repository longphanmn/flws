/**
 * Global Flatland API and WebSocket configuration.
 *
 * Automatically detects whether the app is running on a static host (e.g. GitHub Pages)
 * or same-origin (production server / localhost).
 */

const isGitHubPages = typeof window !== 'undefined' && window.location.hostname.endsWith('github.io')

const params = typeof window !== 'undefined' ? new URLSearchParams(window.location.search) : null
const paramBackend = params?.get('backend') || null
const paramWs = params?.get('ws') || null

export const DEFAULT_REMOTE_BACKEND = 'https://world.minhnhan.in'
export const DEFAULT_REMOTE_WS = 'wss://world.minhnhan.in/ws'

export function getBackendBaseUrl(): string {
  if (paramBackend) return paramBackend.replace(/\/+$/, '')
  const metaEnv = (import.meta as any).env
  if (metaEnv?.VITE_BACKEND_URL) return (metaEnv.VITE_BACKEND_URL as string).replace(/\/+$/, '')
  if (isGitHubPages) return DEFAULT_REMOTE_BACKEND
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
  if (isGitHubPages) return DEFAULT_REMOTE_WS
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
