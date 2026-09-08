export interface WorldCardData {
  seed: number
  totalDays: number
  currentTick: number
  aliveCount: number
  deadCount: number
  wars: number
  temples: number
  clans: Array<{ name: string; color?: string; totem?: string; population?: number }>
}

export function generateAndDownloadWorldCard(data: WorldCardData) {
  const width = 1200
  const height = 630
  const canvas = document.createElement('canvas')
  canvas.width = width
  canvas.height = height
  const ctx = canvas.getContext('2d')
  if (!ctx) return

  // Background
  ctx.fillStyle = '#0d1117'
  ctx.fillRect(0, 0, width, height)

  // Decorative border
  ctx.strokeStyle = '#30363d'
  ctx.lineWidth = 4
  ctx.strokeRect(20, 20, width - 40, height - 40)

  // Header Title
  ctx.fillStyle = '#58a6ff'
  ctx.font = 'bold 22px system-ui, -apple-system, sans-serif'
  ctx.fillText('FLATLAND CHRONICLE · WORLD ATLAS', 50, 70)

  // Main Seed Title
  ctx.fillStyle = '#f0f6fc'
  ctx.font = 'bold 44px system-ui, -apple-system, sans-serif'
  ctx.fillText(`World Seed #${data.seed}`, 50, 125)

  // Subtitle
  ctx.fillStyle = '#8b949e'
  ctx.font = '20px system-ui, -apple-system, sans-serif'
  ctx.fillText(`Simulation Era: ${data.totalDays.toFixed(1)} Days (${data.currentTick} Ticks)`, 50, 160)

  // 4 Big Metric Cards
  const cardY = 200
  const cardW = 250
  const cardH = 110
  const metrics = [
    { label: 'POPULATION', value: `${data.aliveCount} Alive`, sub: `${data.deadCount} Fallen`, color: '#3fb950' },
    { label: 'WARFARE', value: `${data.wars} Battles`, sub: 'Conquests & Feuds', color: '#f85149' },
    { label: 'THEOLOGY', value: `${data.temples} Temples`, sub: 'Sanctuaries of the Sphere', color: '#e3b341' },
    { label: 'DYNASTIES', value: `${data.clans.length} Clans`, sub: 'Active & Extinct Tribes', color: '#a371f7' },
  ]

  metrics.forEach((m, idx) => {
    const x = 50 + idx * (cardW + 30)
    // Card background
    ctx.fillStyle = '#161b22'
    ctx.fillRect(x, cardY, cardW, cardH)
    ctx.strokeStyle = '#30363d'
    ctx.lineWidth = 1.5
    ctx.strokeRect(x, cardY, cardW, cardH)

    // Left color pill
    ctx.fillStyle = m.color
    ctx.fillRect(x, cardY, 6, cardH)

    // Metric text
    ctx.fillStyle = '#8b949e'
    ctx.font = 'bold 12px system-ui, -apple-system, sans-serif'
    ctx.fillText(m.label, x + 18, cardY + 28)

    ctx.fillStyle = '#f0f6fc'
    ctx.font = 'bold 22px system-ui, -apple-system, sans-serif'
    ctx.fillText(m.value, x + 18, cardY + 62)

    ctx.fillStyle = '#8b949e'
    ctx.font = '13px system-ui, -apple-system, sans-serif'
    ctx.fillText(m.sub, x + 18, cardY + 88)
  })

  // Clan Roster Section
  ctx.fillStyle = '#f0f6fc'
  ctx.font = 'bold 22px system-ui, -apple-system, sans-serif'
  ctx.fillText('Major Sovereign Clans & Totems', 50, 360)

  const clanCols = 3
  const clanBoxW = 340
  const clanBoxH = 50
  const clanStartY = 385

  data.clans.slice(0, 6).forEach((c, idx) => {
    const col = idx % clanCols
    const row = Math.floor(idx / clanCols)
    const x = 50 + col * (clanBoxW + 25)
    const y = clanStartY + row * (clanBoxH + 15)

    ctx.fillStyle = '#161b22'
    ctx.fillRect(x, y, clanBoxW, clanBoxH)
    ctx.strokeStyle = '#21262d'
    ctx.lineWidth = 1
    ctx.strokeRect(x, y, clanBoxW, clanBoxH)

    // Totem / Color Indicator
    ctx.fillStyle = c.color || '#58a6ff'
    ctx.fillRect(x + 10, y + 15, 20, 20)

    ctx.fillStyle = '#f0f6fc'
    ctx.font = 'bold 16px system-ui, -apple-system, sans-serif'
    ctx.fillText(c.name.length > 22 ? `${c.name.slice(0, 20)}…` : c.name, x + 40, y + 32)

    if (c.population !== undefined) {
      ctx.fillStyle = '#8b949e'
      ctx.font = '13px system-ui, -apple-system, sans-serif'
      ctx.fillText(`${c.population} members`, x + 240, y + 32)
    }
  })

  // Footer Branding
  ctx.fillStyle = '#30363d'
  ctx.fillRect(50, 560, width - 100, 1)

  ctx.fillStyle = '#8b949e'
  ctx.font = '14px system-ui, -apple-system, sans-serif'
  ctx.fillText('Simulated 2D Universe inspired by Edwin A. Abbott · flatland.mnlab.io', 50, 590)

  ctx.fillStyle = '#58a6ff'
  ctx.font = 'bold 14px system-ui, -apple-system, sans-serif'
  ctx.fillText('FLATLAND EVOLUTION ENGINE', width - 280, 590)

  // Download
  canvas.toBlob((blob) => {
    if (!blob) return
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `flatland-world-card-seed-${data.seed}.png`
    a.click()
    URL.revokeObjectURL(url)
  }, 'image/png')
}
