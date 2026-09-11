import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import fs from 'node:fs'
import path from 'node:path'

// Serves public/health.html at the clean /health URL (dev only; nginx.conf
// has the equivalent rule for docker/prod). Registered before Vite's SPA
// fallback so /health doesn't resolve to index.html.
function healthPage() {
  const handler = (req: any, res: any, next: any) => {
    const url = (req.url || '').split('?')[0]
    if (url === '/health' || url === '/health/') {
      try {
        const file = path.resolve(__dirname, 'public/health.html')
        const html = fs.readFileSync(file, 'utf-8')
        res.setHeader('Content-Type', 'text/html; charset=utf-8')
        res.setHeader('Cache-Control', 'no-cache')
        res.end(html)
        return
      } catch {
        // fall through to normal handling
      }
    }
    next()
  }
  return {
    name: 'flatland-health-page',
    configureServer(server: any) {
      server.middlewares.use(handler)
    },
    configurePreviewServer(server: any) {
      server.middlewares.use(handler)
    },
  }
}

const proxyConfig = {
  '/api': {
    target: 'http://localhost:8000',
    changeOrigin: true,
    timeout: 5000,
    // Suppress ECONNREFUSED spam when backend is reloading; retry once
    configure: (proxy: any) => {
      let lastLog = 0
      proxy.on('error', (_err: any, _req: any, _res: any) => {
        const now = Date.now()
        if (now - lastLog > 5000) {
          lastLog = now
          console.log('[proxy] backend unreachable (retrying)…')
        }
      })
    },
  },
  '/ws': { target: 'ws://localhost:8000', ws: true, timeout: 5000 },
  '/healthz': { target: 'http://localhost:8000', changeOrigin: true, timeout: 5000 },
  '/wiki': { target: 'http://localhost:8000', changeOrigin: true, timeout: 5000 },
  '/guide': { target: 'http://localhost:8000', changeOrigin: true, timeout: 5000 },
  '/docs': { target: 'http://localhost:8000', changeOrigin: true, timeout: 5000 },
  '/openapi.json': { target: 'http://localhost:8000', changeOrigin: true, timeout: 5000 },
  '/redoc': { target: 'http://localhost:8000', changeOrigin: true, timeout: 5000 },
}

export default defineConfig(({ mode }) => {
  const rootDir = path.resolve(__dirname, '..')
  const env = loadEnv(mode, rootDir, ['API_', 'BACKEND_', 'VITE_', 'WS_', 'FRONTEND_', 'DEMO_', 'LANDING_'])

  const rawApiUrl = process.env.VITE_DEMO_API_URL || process.env.API_URL || env.API_URL || env.VITE_BACKEND_URL || env.BACKEND_URL || ''
  const cleanApiUrl = rawApiUrl.replace(/\/+$/, '')

  const rawFrontendUrl = process.env.VITE_FRONTEND_URL || process.env.FRONTEND_URL || env.FRONTEND_URL || process.env.VITE_DEMO_URL || process.env.DEMO_URL || env.DEMO_URL || ''
  const cleanFrontendUrl = rawFrontendUrl.replace(/\/+$/, '')

  const rawLandingUrl = process.env.VITE_LANDING_URL || process.env.LANDING_URL || env.LANDING_URL || ''
  const cleanLandingUrl = rawLandingUrl.replace(/\/+$/, '')

  let rawWsUrl = process.env.VITE_DEMO_WS_URL || process.env.WS_URL || env.WS_URL || env.VITE_WS_URL || ''
  if (!rawWsUrl && cleanApiUrl) {
    if (cleanApiUrl.startsWith('https://')) {
      rawWsUrl = cleanApiUrl.replace(/^https:\/\//, 'wss://') + '/ws'
    } else if (cleanApiUrl.startsWith('http://')) {
      rawWsUrl = cleanApiUrl.replace(/^http:\/\//, 'ws://') + '/ws'
    }
  }

  const isDemo = process.env.VITE_IS_DEMO === 'true' || env.VITE_IS_DEMO === 'true'

  return {
    base: process.env.VITE_BASE || './',
    envDir: rootDir,
    envPrefix: ['VITE_', 'API_', 'BACKEND_', 'WS_', 'FRONTEND_', 'DEMO_', 'LANDING_'],
    define: {
      '__ENV_API_URL__': JSON.stringify(isDemo && cleanApiUrl ? Buffer.from(cleanApiUrl).toString('base64') : cleanApiUrl),
      '__ENV_WS_URL__': JSON.stringify(isDemo && rawWsUrl ? Buffer.from(rawWsUrl).toString('base64') : rawWsUrl),
      '__ENV_FRONTEND_URL__': JSON.stringify(cleanFrontendUrl),
      '__ENV_DEMO_URL__': JSON.stringify(cleanFrontendUrl),
      '__ENV_LANDING_URL__': JSON.stringify(cleanLandingUrl),
      '__VITE_IS_DEMO__': JSON.stringify(isDemo),
    },
    plugins: [
      react(),
      healthPage(),
      {
        name: 'flatland-html-transform',
        transformIndexHtml(html: string) {
          const frontend = cleanFrontendUrl || './'
          const landing = cleanLandingUrl || '../'
          return html
            .replaceAll('%FRONTEND_URL%', frontend)
            .replaceAll('%DEMO_URL%', frontend)
            .replaceAll('%LANDING_URL%', landing)
        },
      },
    ],
  server: {
    host: '0.0.0.0',
    port: 5173,
    // production is reached via reverse proxy → :5173, allow all for Edge/Safari
    allowedHosts: true,
    cors: true,
    proxy: proxyConfig,
  },
  preview: {
    host: '0.0.0.0',
    port: 5173,
    allowedHosts: true,
    cors: true,
    proxy: proxyConfig,
  },
    build: {
      minify: 'esbuild',
      cssMinify: true,
      sourcemap: false,
      chunkSizeWarningLimit: 1000,
      rollupOptions: {
        output: {
          manualChunks: {
            vendor: ['react', 'react-dom'],
          },
        },
      },
    },
  }
})

