import { defineConfig } from 'vite'
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

export default defineConfig({
  plugins: [react(), healthPage()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    // production is reached via http://world.minhnhan.in → :5173, allow all for Edge/Safari
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
})
