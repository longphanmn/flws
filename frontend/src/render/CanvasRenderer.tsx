import { useEffect, useRef } from 'react'
import type { LensMode, StateMessage } from '../types'
import {
  Camera,
  CASTE_COLORS,
  EMOTE_ICONS,
  MAX_SCALE,
  MIN_SCALE_FACTOR,
  pickCreatureAt,
  renderWorldFrame,
} from './renderCore'
import { isWebGLRendererAvailable, renderWorldFrameWebGL } from './webglRenderer'

export { CASTE_COLORS, EMOTE_ICONS }

interface Props {
  stateRef: React.RefObject<StateMessage | null>
  selectedRef?: React.RefObject<number | null>
  selectedClanRef?: React.RefObject<number | null>
  onTapCreature?: (id: number | null) => void
  lensMode?: LensMode
}

export default function CanvasRenderer({
  stateRef,
  selectedRef,
  selectedClanRef,
  onTapCreature,
  lensMode = 'mutants',
}: Props) {

  const canvasRef = useRef<HTMLCanvasElement>(null)
  const camRef = useRef<Camera>({ scale: 1, ox: 0, oy: 0, initialized: false })
  const lensModeRef = useRef<LensMode>(lensMode)
  lensModeRef.current = lensMode

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    // AY M-3: WebGL batch renderer is opt-in via ?webgl=1 (default: Canvas2D for full fidelity grid/terrain).
    // Auto-enable caused black map (grid/terrain not yet in WebGL path) — keep fallback.
    const useWebGL = false && isWebGLRendererAvailable()
    let ctx: CanvasRenderingContext2D | null = null
    if (!useWebGL) {
      ctx = canvas.getContext('2d')
      if (!ctx) return
    } else {
      // WebGL requested via ?webgl=1 — try to acquire, fallback to 2d on failure
      const hasWebGL = isWebGLRendererAvailable()
      if (!hasWebGL) {
        ctx = canvas.getContext('2d')
        if (!ctx) return
      }
    }

    const cam = camRef.current
    let raf = 0
    let baseFit = 1
    let lastTrackedId: number | null = null
    let targetZoomScale: number | null = null
    let lastTrackedClanId: number | null = null
    let targetClanScale: number | null = null

    const isMobileClient = typeof window !== 'undefined' && (window.innerWidth <= 768 || 'ontouchstart' in window)
    const dpr = () => Math.min(isMobileClient ? 1.25 : 1.5, window.devicePixelRatio || 1)

    const resize = () => {
      canvas.width = Math.max(1, Math.floor(canvas.clientWidth * dpr()))
      canvas.height = Math.max(1, Math.floor(canvas.clientHeight * dpr()))
    }
    resize()
    const ro = new ResizeObserver(resize)
    ro.observe(canvas)

    const fitCamera = (state: StateMessage) => {
      baseFit = Math.min(canvas.width / state.width, canvas.height / state.height)
      cam.scale = baseFit
      cam.ox = (canvas.width - state.width * cam.scale) / 2
      cam.oy = (canvas.height - state.height * cam.scale) / 2
      cam.initialized = true
      targetZoomScale = null
      lastTrackedId = null
      lastTrackedClanId = null
      targetClanScale = null
    }

    const clampCamera = (state: StateMessage) => {
      const cxw = (canvas.width / 2 - cam.ox) / cam.scale
      const cyw = (canvas.height / 2 - cam.oy) / cam.scale
      const tx = Math.min(Math.max(cxw, 0), state.width)
      const ty = Math.min(Math.max(cyw, 0), state.height)
      cam.ox += (tx - cxw) * cam.scale
      cam.oy += (ty - cyw) * cam.scale
    }

    const zoomAt = (state: StateMessage, factor: number, ax: number, ay: number) => {
      const next = Math.min(
        Math.max(cam.scale * factor, baseFit * MIN_SCALE_FACTOR),
        MAX_SCALE,
      )
      const wx = (ax - cam.ox) / cam.scale
      const wy = (ay - cam.oy) / cam.scale
      cam.ox = ax - wx * next
      cam.oy = ay - wy * next
      cam.scale = next
      clampCamera(state)
      if (selectedRef?.current != null) {
        targetZoomScale = next
      }
    }

    const onFit = () => {
      const st = stateRef.current
      if (st) fitCamera(st)
    }
    window.addEventListener('flatworld-fit', onFit)

    const onZoomEvent = (ev: Event) => {
      const state = stateRef.current
      if (!state || !cam.initialized) return
      const factor = (ev as CustomEvent<{ factor?: number }>).detail?.factor ?? 1.2
      zoomAt(state, factor, canvas.width / 2, canvas.height / 2)
    }
    window.addEventListener('flatworld-zoom', onZoomEvent)

    // Pointer events
    interface P {
      x: number
      y: number
    }
    const pointers = new Map<number, P>()
    let lastPinchDist = 0
    let lastMid: P | null = null
    let tapStart: { x: number; y: number; t: number } | null = null
    let lastTap: { x: number; y: number; t: number } | null = null

    const dist = (a: P, b: P): number => Math.hypot(a.x - b.x, a.y - b.y)
    const mid = (a: P, b: P): P => ({ x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 })
    const twoPointers = (): [P, P] => {
      const it = [...pointers.values()]
      return [it[0], it[1]]
    }

    const onPointerDown = (ev: PointerEvent) => {
      if (ev.target !== canvas) return
      canvas.setPointerCapture(ev.pointerId)
      pointers.set(ev.pointerId, { x: ev.clientX, y: ev.clientY })
      if (pointers.size === 2) {
        const [a, b] = twoPointers()
        lastPinchDist = dist(a, b)
        lastMid = mid(a, b)
      }
      tapStart = { x: ev.clientX, y: ev.clientY, t: performance.now() }
      canvas.style.cursor = 'grab'
      if (ev.cancelable) ev.preventDefault()
    }

    const onPointerMove = (ev: PointerEvent) => {
      const prev = pointers.get(ev.pointerId)
      if (!prev || !cam.initialized) return
      const state = stateRef.current
      if (!state) return
      pointers.set(ev.pointerId, { x: ev.clientX, y: ev.clientY })
      const ratio = dpr()

      if (pointers.size === 1) {
        if (tapStart) {
          const dragDist = Math.hypot(ev.clientX - tapStart.x, ev.clientY - tapStart.y) * ratio
          if (dragDist < 6 * ratio) return
        }
        canvas.style.cursor = 'grabbing'
        cam.ox += (ev.clientX - prev.x) * ratio
        cam.oy += (ev.clientY - prev.y) * ratio
        clampCamera(state)
        return
      }

      if (pointers.size >= 2) {
        const [a, b] = twoPointers()
        const m = mid(a, b)
        const d = dist(a, b)
        if (lastMid && lastPinchDist > 0 && d > 0) {
          cam.ox += (m.x - lastMid.x) * ratio
          cam.oy += (m.y - lastMid.y) * ratio
          zoomAt(state, d / lastPinchDist, m.x * ratio, m.y * ratio)
        }
        lastPinchDist = d
        lastMid = m
      }
    }

    const onPointerUp = (ev: PointerEvent) => {
      pointers.delete(ev.pointerId)
      if (pointers.size < 2) {
        lastPinchDist = 0
        lastMid = null
      }
      if (pointers.size === 0) canvas.style.cursor = 'grab'
      if (!tapStart || !onTapCreature) {
        tapStart = null
        return
      }
      const isTap =
        performance.now() - tapStart.t < 500 &&
        Math.hypot(ev.clientX - tapStart.x, ev.clientY - tapStart.y) * dpr() < 10 * dpr()
      if (!isTap) {
        tapStart = null
        return
      }
      const now = performance.now()
      const isDoubleTap =
        lastTap &&
        now - lastTap.t < 300 &&
        Math.hypot(tapStart.x - lastTap.x, tapStart.y - lastTap.y) < 24

      const state = stateRef.current
      const id = pickCreatureAt(state, tapStart.x, tapStart.y, cam, dpr())

      if (isDoubleTap) {
        if (id !== null) {
          onTapCreature(id)
          const ent = state?.entities.find((e) => e.id === id)
          if (ent && state) {
            const targetScale = Math.min(MAX_SCALE, cam.scale * 1.6)
            cam.ox = canvas.width / 2 - ent.x * targetScale
            cam.oy = canvas.height / 2 - ent.y * targetScale
            cam.scale = targetScale
            clampCamera(state)
          }
        }
        lastTap = null
      } else {
        onTapCreature(id)
        lastTap = { x: tapStart.x, y: tapStart.y, t: now }
      }
      tapStart = null
    }

    const onWheel = (ev: WheelEvent) => {
      if (ev.target !== canvas) return
      ev.preventDefault()
      const state = stateRef.current
      if (!state || !cam.initialized) return
      const factor = Math.exp(-ev.deltaY * 0.0015)
      zoomAt(state, factor, ev.clientX * dpr(), ev.clientY * dpr())
    }

    const onDblClick = (ev: MouseEvent) => {
      if (ev.target !== canvas) return
      ev.preventDefault()
      const state = stateRef.current
      if (!state || !cam.initialized) return
      const out = ev.shiftKey || ev.altKey
      zoomAt(state, out ? 1 / 1.8 : 1.8, ev.clientX * dpr(), ev.clientY * dpr())
    }

    canvas.style.cursor = 'grab'
    canvas.addEventListener('pointerdown', onPointerDown)
    canvas.addEventListener('pointermove', onPointerMove)
    canvas.addEventListener('pointerup', onPointerUp)
    canvas.addEventListener('pointercancel', onPointerUp)
    canvas.addEventListener('wheel', onWheel, { passive: false })
    canvas.addEventListener('dblclick', onDblClick)

    // Render loop
    const draw = () => {
      raf = requestAnimationFrame(draw)
      const state = stateRef.current
      const cw = canvas.width
      const ch = canvas.height


      if (!state) {
        if (ctx) {
          ctx.setTransform(1, 0, 0, 1, 0, 0)
          ctx.fillStyle = '#0b0f14'
          ctx.fillRect(0, 0, cw, ch)
        }
        return
      }

      if (!cam.initialized || cam.scale <= 0) fitCamera(state)

      const sel = selectedRef?.current ?? null
      const selClanId = selectedClanRef?.current ?? null

      // Auto-follow selected creature or clan
      if (sel !== null) {
        lastTrackedClanId = null
        targetClanScale = null
        const selEnt = state.entities.find((e) => e.id === sel && e.kind === 'creature')
        if (selEnt) {
          if (sel !== lastTrackedId) {
            lastTrackedId = sel
            const minFollowScale = Math.min(MAX_SCALE, Math.max(baseFit * 3.5, 8.0))
            targetZoomScale = Math.max(cam.scale, minFollowScale)
          }
          if (pointers.size === 0 && !tapStart) {
            const desiredScale = targetZoomScale ?? cam.scale
            cam.scale += (desiredScale - cam.scale) * 0.12
            const targetOx = cw / 2 - selEnt.x * cam.scale
            const targetOy = ch / 2 - selEnt.y * cam.scale
            if (Math.abs(targetOx - cam.ox) > cw * 0.75 || Math.abs(targetOy - cam.oy) > ch * 0.75) {
              cam.ox = targetOx
              cam.oy = targetOy
            } else {
              cam.ox += (targetOx - cam.ox) * 0.15
              cam.oy += (targetOy - cam.oy) * 0.15
            }
            clampCamera(state)
          }
        }
      } else if (selClanId !== null) {
        lastTrackedId = null
        targetZoomScale = null
        const clanHouses = state.entities.filter((e) => e.kind === 'house' && e.clan_id === selClanId && !e.is_ruin)
        const clanMembers = state.entities.filter((e) => e.kind === 'creature' && e.clan_id === selClanId)
        const clanEntities = clanHouses.length > 0 ? clanHouses : clanMembers

        if (clanEntities.length > 0) {
          let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity
          for (const e of clanEntities) {
            if (e.x < minX) minX = e.x
            if (e.x > maxX) maxX = e.x
            if (e.y < minY) minY = e.y
            if (e.y > maxY) maxY = e.y
          }
          const pad = 24
          minX -= pad; maxX += pad
          minY -= pad; maxY += pad
          const spanX = Math.max(50, maxX - minX)
          const spanY = Math.max(50, maxY - minY)
          const centerX = (minX + maxX) / 2
          const centerY = (minY + maxY) / 2

          if (selClanId !== lastTrackedClanId) {
            lastTrackedClanId = selClanId
            const fitClanScale = Math.min((cw * 0.8) / spanX, (ch * 0.8) / spanY)
            targetClanScale = Math.max(baseFit * 0.9, Math.min(fitClanScale, 3.6))
          }

          if (pointers.size === 0 && !tapStart) {
            const desiredScale = targetClanScale ?? cam.scale
            cam.scale += (desiredScale - cam.scale) * 0.08
            const targetOx = cw / 2 - centerX * cam.scale
            const targetOy = ch / 2 - centerY * cam.scale
            cam.ox += (targetOx - cam.ox) * 0.1
            cam.oy += (targetOy - cam.oy) * 0.1
            clampCamera(state)
          }
        }
      } else {
        lastTrackedId = null
        targetZoomScale = null
        lastTrackedClanId = null
        targetClanScale = null
      }

      // AY M-3: GPU path — instanced WebGL sprite buffers for 5k+ entities @ 60-120 FPS
      if (useWebGL) {
        const ok = renderWorldFrameWebGL(canvas, state, cam)
        if (ok) return
        // fallback: acquire 2d context if WebGL failed mid-run
        if (!ctx) {
          const c2 = canvas.getContext('2d')
          if (c2) { ctx = c2 }
        }
        if (ctx) renderWorldFrame(ctx, state, cw, ch, cam, sel, selClanId, lensModeRef.current)
        return
      }
      renderWorldFrame(ctx!, state, cw, ch, cam, sel, selClanId, lensModeRef.current)
    }
    raf = requestAnimationFrame(draw)

    return () => {
      cancelAnimationFrame(raf)
      ro.disconnect()
      window.removeEventListener('flatworld-fit', onFit)
      window.removeEventListener('flatworld-zoom', onZoomEvent)
      canvas.removeEventListener('pointerdown', onPointerDown)
      canvas.removeEventListener('pointermove', onPointerMove)
      canvas.removeEventListener('pointerup', onPointerUp)
      canvas.removeEventListener('pointercancel', onPointerUp)
      canvas.removeEventListener('wheel', onWheel)
      canvas.removeEventListener('dblclick', onDblClick)
    }
  }, [stateRef])

  return <canvas ref={canvasRef} className="world-canvas" />
}
