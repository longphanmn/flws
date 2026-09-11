import { useCallback, useEffect, useRef, useState } from 'react'
import CanvasRenderer from './render/CanvasRenderer'
import OverviewPanel from './render/OverviewPanel'
import ClanPanel from './render/ClanPanel'
import ChronicleFeed from './render/ChronicleFeed'
import GodPanel from './god/GodPanel'
import { AuthModal, ensureGodKey, forgetKey, getCachedKey } from './god/auth'
import Wiki from './wiki/Wiki'
import ClanDetails from './clan/ClanDetails'
import Observatory from './analytics/Observatory'
import WorldEndSummary from './summary/WorldEndSummary'
import WorldHistoryModal from './history/WorldHistoryModal'
import Inspector from './inspect/Inspector'
import { WorldSocket, type ConnStatus } from './websocket'
import type { HelloMessage, HistoryEvent, LensMode, StateMessage, WorldSummary } from './types'
import { useI18n } from './i18n'
import ConfirmModal from './components/ConfirmModal'
import { apiUrl, getLandingUrl, getWebSocketUrl } from './config'


const SPEEDS = [1, 5, 10, 20, 40]
const HISTORY_PAGE = 200
const MAX_LOG = 600

const STATUS_LABEL: Record<ConnStatus, string> = {
  connecting: 'connecting',
  open: 'live',
  closed: 'reconnecting',
}

const eventKey = (ev: HistoryEvent) => `${ev.tick}:${ev.entity_id}:${ev.type}`

/** Newest-first: later ticks on top, insertion id as tiebreak (live rows have none). */
const newestFirst = (a: HistoryEvent, b: HistoryEvent) =>
  b.tick - a.tick || (b.id ?? 0) - (a.id ?? 0)

/** "2026-08-22T06:47:01+00:00" → "06:47" for compact run labels. */
const fmtStart = (iso: string) => iso.slice(11, 16) || iso



export default function App() {
  const { t, lang, setLang } = useI18n()
  const [status, setStatus] = useState<ConnStatus>('connecting')
  const [hello, setHello] = useState<HelloMessage | null>(null)
  const [state, setState] = useState<StateMessage | null>(null)
  const [paused, setPaused] = useState(false)
  const [speed, setSpeed] = useState(10)
  const [godOpen, setGodOpen] = useState(false)
  const [resetConfirmOpen, setResetConfirmOpen] = useState(false)
  const [chronicleOpen, setChronicleOpen] = useState(() => {
    if (typeof window !== 'undefined' && window.innerWidth <= 768) return false
    return true
  })
  const [helpOpen, setHelpOpen] = useState(false)
  const [wikiOpen, setWikiOpen] = useState(false)
  const [historyInitialDay] = useState<number | null>(() => {
    if (typeof window !== 'undefined') {
      const p = new URLSearchParams(window.location.search).get('history')
      if (p !== null && !isNaN(Number(p))) return Number(p)
    }
    return null
  })
  const [worldHistoryOpen, setWorldHistoryOpen] = useState(() => {
    if (typeof window !== 'undefined') {
      const p = new URLSearchParams(window.location.search).get('history')
      if (p !== null && !isNaN(Number(p))) return true
    }
    return false
  })
  const [analyticsOpen, setAnalyticsOpen] = useState(false)
  const [isMobile, setIsMobile] = useState(() => typeof window !== 'undefined' && window.innerWidth <= 768)
  const [statusExpanded, setStatusExpanded] = useState(false)
  const [sheetState, setSheetState] = useState<'hidden' | 'peek' | 'half' | 'full'>('hidden')
  const [sheetTab, setSheetTab] = useState<'world' | 'clans' | 'chronicle'>('world')
  const [rightTab, setRightTab] = useState<'overview' | 'clans' | 'chronicle'>(() => {
    if (typeof window !== 'undefined') {
      const v = sessionStorage.getItem('right-stack-tab')
      if (v === 'overview' || v === 'clans' || v === 'chronicle') return v
    }
    return 'overview'
  })
  useEffect(() => {
    try { sessionStorage.setItem('right-stack-tab', rightTab) } catch {}
  }, [rightTab])
  const [rightCollapsed, setRightCollapsed] = useState<boolean>(() => {
    try { return sessionStorage.getItem('right-stack-collapsed') === '1' } catch { return false }
  })
  useEffect(() => {
    try { sessionStorage.setItem('right-stack-collapsed', rightCollapsed ? '1' : '0') } catch {}
  }, [rightCollapsed])
  const [versionInfo, setVersionInfo] = useState<{ version: string; revision: string } | null>(null)
  const [log, setLog] = useState<HistoryEvent[]>([])
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [initialClanTab, setInitialClanTab] = useState<'stronghold' | 'roster' | 'warfare' | 'annals' | 'biography' | undefined>(() => {
    if (typeof window !== 'undefined') {
      const c = new URLSearchParams(window.location.search).get('clan')
      if (c !== null && !isNaN(Number(c))) return 'biography'
    }
    return undefined
  })
  const [selectedClanId, setSelectedClanId] = useState<number | null>(() => {
    if (typeof window !== 'undefined') {
      const c = new URLSearchParams(window.location.search).get('clan')
      if (c !== null && !isNaN(Number(c))) return Number(c)
    }
    return null
  })
  const [showWorldEnd, setShowWorldEnd] = useState(false)
  const [aliveHist, setAliveHist] = useState<number[]>([])
  const [worlds, setWorlds] = useState<WorldSummary[]>([])
  /** null = follow the live run; a number = pinned to that (past) run. */
  const [selectedRunId, setSelectedRunId] = useState<number | null>(null)
  const [loadingOlder, setLoadingOlder] = useState(false)
  const [noMoreHistory, setNoMoreHistory] = useState(false)
  const lensMode: LensMode = 'mutants'

  /** §Y clan display name from live state, falling back to bare #id. */
  const clanLabel = (id?: number | null): string => {
    if (id == null) return '#?'
    return state?.clans?.[String(id)]?.name ?? `#${id}`
  }

  const selectCreature = (id: number | null) => {
    setSelectedId(id)
    if (id !== null) {
      setSelectedClanId(null)
    }
  }

  const selectClan = (cid: number | null, tab?: 'stronghold' | 'roster' | 'warfare' | 'annals' | 'biography') => {
    setSelectedClanId(cid)
    if (tab) setInitialClanTab(tab)
    if (cid !== null) {
      setSelectedId(null)
    }
  }

  const stateRef = useRef<StateMessage | null>(null)
  const sockRef = useRef<WorldSocket | null>(null)
  const seenEventsRef = useRef(new Set<string>())
  const selectedRef = useRef<number | null>(null)
  const selectedClanRef = useRef<number | null>(null)
  const archiveModeRef = useRef(false)

  const oldestLoadedRef = useRef<number | null>(null)
  const fetchedByIdRef = useRef(new Map<string, HistoryEvent>())
  const seededRef = useRef(false)
  const loadingOlderRef = useRef(false)
  const prevTickRef = useRef<number | null>(null)
  const prevSeedRef = useRef<number | null>(null)
  const lastUiUpdateRef = useRef<number>(0)
  const queuedEventsRef = useRef<HistoryEvent[]>([])
  const prevDayHistRef = useRef<number | null>(null)
  const [estTps, setEstTps] = useState<number | null>(null)
  const lastTpsTimeRef = useRef<number>(0)
  const lastTpsTickRef = useRef<number | null>(null)
  useEffect(() => {
    selectedRef.current = selectedId
  }, [selectedId])
  useEffect(() => {
    selectedClanRef.current = selectedClanId
  }, [selectedClanId])

  const liveWorld = worlds.find((w) => w.ended_at === null)
  const liveWorldId = liveWorld?.id ?? null
  const archiveMode = selectedRunId !== null && selectedRunId !== liveWorldId

  useEffect(() => {
    archiveModeRef.current = archiveMode
  }, [archiveMode])

  useEffect(() => {
    fetch('/api/version')
      .then((r) => r.json())
      .then((d) => setVersionInfo({ version: d.version ?? '0.1.6', revision: d.revision ?? '' }))
      .catch(() => setVersionInfo({ version: '0.1.6', revision: '' }))
  }, [])

  useEffect(() => {
    const onResize = () => setIsMobile(window.innerWidth <= 768)
    onResize()
    window.addEventListener('resize', onResize)
    return () => window.removeEventListener('resize', onResize)
  }, [])

  // Phone: never leave the detail dropdown open on desktop, and never stack
  // the bottom sheet under the creature/clan inspectors.
  useEffect(() => {
    if (!isMobile) setStatusExpanded(false)
  }, [isMobile])
  useEffect(() => {
    if (isMobile && (selectedId !== null || selectedClanId !== null)) {
      setSheetState('hidden')
      setStatusExpanded(false)
    }
  }, [isMobile, selectedId, selectedClanId])

  const [tooltip, setTooltip] = useState<{ text: string; x: number; y: number } | null>(null)
  // Custom tooltip for HUD chips and law hints — works on hover (desktop) and tap (mobile)
  useEffect(() => {
    let hideTimer: number | null = null
    const show = (el: HTMLElement, x: number, y: number) => {
      const txt = el.getAttribute('title') || el.getAttribute('data-hint')
      if (!txt) return
      // suppress native title
      el.setAttribute('data-title', txt)
      el.removeAttribute('title')
      setTooltip({ text: txt, x, y })
      if (hideTimer) window.clearTimeout(hideTimer)
    }
    const hide = (el: HTMLElement) => {
      const orig = el.getAttribute('data-title')
      if (orig) {
        el.setAttribute('title', orig)
        el.removeAttribute('data-title')
      }
      if (hideTimer) window.clearTimeout(hideTimer)
      hideTimer = window.setTimeout(() => setTooltip(null), 120) as unknown as number
    }
    const onEnter = (e: Event) => {
      const raw = e.target as HTMLElement | null
      if (!raw || !(raw instanceof Element)) return
      const chip = raw.closest('[title], [data-hint]') as HTMLElement | null
      if (!chip) return
      const rect = chip.getBoundingClientRect()
      show(chip, rect.left + rect.width / 2, rect.top)
    }
    const onLeave = (e: Event) => {
      const raw = e.target as HTMLElement | null
      if (!raw || !(raw instanceof Element)) return
      const chip = raw.closest('[title], [data-hint]') as HTMLElement | null
      if (chip) hide(chip)
      else setTooltip(null)
    }
    const onClick = (e: Event) => {
      const raw = e.target as HTMLElement | null
      if (!raw || !(raw instanceof Element)) return
      const chip = raw.closest('.hud [title], .hud [data-hint], .chip[data-hint]') as HTMLElement | null
      if (chip && !chip.closest('button, select, input, a, .collapsible-head, .right-stack')) {
        const txt = chip.getAttribute('title') || chip.getAttribute('data-hint') || chip.getAttribute('data-title')
        if (txt) {
          const rect = chip.getBoundingClientRect()
          setTooltip({ text: txt, x: rect.left + rect.width / 2, y: rect.top })
          if (hideTimer) window.clearTimeout(hideTimer)
          hideTimer = window.setTimeout(() => setTooltip(null), 2800) as unknown as number
        }
      }
    }
    document.addEventListener('mouseenter', onEnter, true)
    document.addEventListener('mouseleave', onLeave, true)
    document.addEventListener('mousemove', (e: MouseEvent) => {
      if (tooltip) {
        const raw = e.target as HTMLElement | null
        if (!raw || !(raw instanceof Element)) return
        const t = raw.closest('[title], [data-hint]') as HTMLElement | null
        if (t) {
          const rect = t.getBoundingClientRect()
          setTooltip((prev) => prev ? { ...prev, x: rect.left + rect.width / 2, y: rect.top } : prev)
        }
      }
    })
    document.addEventListener('click', onClick, false)
    return () => {
      document.removeEventListener('mouseenter', onEnter, true)
      document.removeEventListener('mouseleave', onLeave, true)
      document.removeEventListener('click', onClick, false)
      if (hideTimer) window.clearTimeout(hideTimer)
    }
  }, [tooltip])

  const refreshWorlds = useCallback(async () => {
    try {
      const d = await fetch('/api/worlds').then((r) => r.json())
      setWorlds(Array.isArray(d.worlds) ? d.worlds : [])
    } catch {
      // backend briefly unreachable — keep previous list
    }
  }, [])

  useEffect(() => {
    refreshWorlds()
  }, [refreshWorlds])

  useEffect(() => {
    const sock = new WorldSocket(getWebSocketUrl(), {
      onStatus: setStatus,
      onAuthError: () => {
        // the stored passkey stopped working (db reset, wrong world) — re-ask next time
        forgetKey()
      },
      onHello: (msg) => {
        setHello(msg)
        setSpeed(msg.tick_rate)
        if (msg.paused !== undefined) {
          setPaused(msg.paused)
        }
        refreshWorlds()
      },
      onControl: (msg) => {
        setPaused(msg.paused)
        if (msg.speed) {
          setSpeed(msg.speed)
        }
      },
      onState: (msg) => {
        if (msg.paused !== undefined && !archiveModeRef.current) {
          setPaused(msg.paused)
        }
        // New world detection: tick reset or seed change → clear chronicle
        const isNewWorld =
          (prevTickRef.current !== null && msg.tick < prevTickRef.current) ||
          (prevSeedRef.current !== null && msg.seed !== prevSeedRef.current)
        if (isNewWorld && !archiveModeRef.current) {
          setLog([])
          setAliveHist([])
          prevDayHistRef.current = null
          seenEventsRef.current.clear()
          fetchedByIdRef.current.clear()
          oldestLoadedRef.current = null
          seededRef.current = false
          setNoMoreHistory(false)
          setPaused(false)
          setShowWorldEnd(false)
          refreshWorlds()
        }
        prevTickRef.current = msg.tick
        prevSeedRef.current = msg.seed
        stateRef.current = msg

        // Estimate true ticks/s from WS stream (wall-clock), independent of UI throttle
        {
          const nowMs = performance.now()
          if (lastTpsTickRef.current !== null && lastTpsTimeRef.current) {
            const dt = (nowMs - lastTpsTimeRef.current) / 1000
            const dTick = msg.tick - (lastTpsTickRef.current ?? msg.tick)
            if (dt >= 0.5 && dTick > 0) {
              const tps = dTick / dt
              setEstTps(Math.round(tps * 10) / 10)
              lastTpsTimeRef.current = nowMs
              lastTpsTickRef.current = msg.tick
            }
          } else {
            lastTpsTimeRef.current = nowMs
            lastTpsTickRef.current = msg.tick
          }
          // Reset on new world
          if (isNewWorld) {
            lastTpsTimeRef.current = nowMs
            lastTpsTickRef.current = msg.tick
            setEstTps(null)
          }
        }

        // AF & §BL-5: Throttle React virtual DOM re-renders to ~4 Hz (every 250ms) for sidebars & HUDs.
        // CanvasRenderer continues to read stateRef.current at full 60 FPS without main thread stalls.
        const now = performance.now()
        const isExtinct = msg.creatures_alive === 0
        const shouldUpdateReactState =
          isNewWorld ||
          isExtinct ||
          now - (lastUiUpdateRef.current || 0) >= 250

        if (!archiveModeRef.current && msg.events && msg.events.length > 0) {
          for (const ev of msg.events) {
            const key = eventKey(ev)
            if (!seenEventsRef.current.has(key)) {
              seenEventsRef.current.add(key)
              queuedEventsRef.current.push(ev)
            }
          }
        }

        if (shouldUpdateReactState) {
          lastUiUpdateRef.current = now
          setState(msg)
          // BC day-based trend: aliveHist stores one sample per in-game day, not per tick.
          setAliveHist((prev) => {
            if (isNewWorld && !archiveModeRef.current) {
              prevDayHistRef.current = msg.day
              return [msg.creatures_alive]
            }
            if (archiveModeRef.current) return prev
            if (prevDayHistRef.current === msg.day) return prev
            prevDayHistRef.current = msg.day
            return [...prev.slice(-59), msg.creatures_alive]
          })
          if (!archiveModeRef.current && queuedEventsRef.current.length > 0) {
            const batch = queuedEventsRef.current.splice(0)
            setLog((prev) => [...batch.reverse(), ...prev].slice(0, MAX_LOG))
          }
        }
      },

    })
    sock.connect()
    sockRef.current = sock
    return () => sock.dispose()
  }, [])

  // World end detection — extinction summary & pause; also resume when new alive world appears
  useEffect(() => {
    if (state && state.creatures_alive === 0 && state.tick > 30 && !showWorldEnd && !archiveMode) {
      setShowWorldEnd(true)
      setPaused(true)
    }
    if (state && state.creatures_alive > 0 && showWorldEnd) {
      setShowWorldEnd(false)
      // world is alive again (reset after extinction) — clear stale pause HUD
      setPaused(false)
    }
  }, [state?.creatures_alive, state?.tick, showWorldEnd, archiveMode])

  const sendControl = useCallback(async (action: 'pause' | 'resume' | 'step' | 'reset', after?: () => void) => {
    const key = await ensureGodKey()
    if (!key) return // cancelled dialog — world untouched
    sockRef.current?.send({ action, key })
    after?.()
  }, [])
  const sendPause = useCallback(() => {
    void sendControl('pause', () => setPaused(true))
  }, [sendControl])
  const sendResume = useCallback(() => {
    void sendControl('resume', () => setPaused(false))
  }, [sendControl])
  const sendStep = useCallback(() => void sendControl('step'), [sendControl])
  const sendReset = useCallback(() => void sendControl('reset', () => setPaused(false)), [sendControl])
  const confirmReset = useCallback(() => setResetConfirmOpen(true), [])
  const doReset = useCallback(() => void sendControl('reset', () => setPaused(false)), [sendControl])
  const changeSpeed = useCallback(
    (v: number) => {
      setSpeed(v)
      void ensureGodKey().then((key) => {
        if (!key) return
        sockRef.current?.send({ action: 'set_speed', value: v, key })
      })
    },
    [],
  )

  // Keyboard controls: space pause · S step · R reset · +/- zoom · F fit.
  useEffect(() => {
    const onKey = (ev: KeyboardEvent) => {
      const t = ev.target as HTMLElement | null
      if (t && ['INPUT', 'SELECT', 'TEXTAREA'].includes(t.tagName)) return
      switch (ev.code) {
        case 'Space':
          ev.preventDefault()
          setPaused((p) => {
            void sendControl(p ? 'resume' : 'pause', () => setPaused(!p))
            return !p
          })
          break
        case 'KeyS':
          sendStep()
          break
        case 'KeyR':
          confirmReset()
          break
        case 'KeyH':
          setWorldHistoryOpen((o) => !o)
          break
        case 'KeyF':
          window.dispatchEvent(new Event('flatworld-fit'))
          break
        case 'Equal':
        case 'NumpadAdd':
          window.dispatchEvent(new CustomEvent('flatworld-zoom', { detail: { factor: 1.25 } }))
          break
        case 'Minus':
        case 'NumpadSubtract':
          window.dispatchEvent(new CustomEvent('flatworld-zoom', { detail: { factor: 0.8 } }))
          break
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [sendControl, sendStep, sendReset, confirmReset])


  /** Merge fetched (id-bearing) events into the log newest-first, deduped by tick+entity_id+type. */
  const mergeFetched = useCallback((fetched: HistoryEvent[]) => {
    if (fetched.length === 0) return
    let minId: number | null = null
    for (const ev of fetched) {
      if (typeof ev.id === 'number') {
        fetchedByIdRef.current.set(String(ev.id), ev)
        if (minId === null || ev.id < minId) minId = ev.id
      }
      // Register keys so a later live rebroadcast of the same window is dropped.
      seenEventsRef.current.add(eventKey(ev))
    }
    if (minId !== null && (oldestLoadedRef.current === null || minId < oldestLoadedRef.current)) {
      oldestLoadedRef.current = minId
    }
    setLog((prev) => {
      const byKey = new Map<string, HistoryEvent>()
      for (const ev of fetched) byKey.set(eventKey(ev), ev)
      for (const ev of prev) {
        const k = eventKey(ev)
        if (!byKey.has(k)) byKey.set(k, ev)
      }
      return [...byKey.values()].sort(newestFirst).slice(0, MAX_LOG)
    })
  }, [])

  useEffect(() => {
    const shouldFetchChronicle = chronicleOpen || (isMobile && sheetTab === 'chronicle' && sheetState !== 'hidden')
    if (!shouldFetchChronicle || archiveMode || seededRef.current) return
    seededRef.current = true
    fetch(`/api/history?limit=${HISTORY_PAGE}`)
      .then((r) => r.json())
      .then((d) => mergeFetched(Array.isArray(d.events) ? d.events : []))
      .catch(() => {})
  }, [chronicleOpen, isMobile, sheetTab, sheetState, archiveMode, mergeFetched])

  const loadOlder = useCallback(async () => {
    const since = oldestLoadedRef.current
    if (since === null || loadingOlderRef.current) return
    loadingOlderRef.current = true
    setLoadingOlder(true)
    try {
      const d = await fetch(`/api/history?since=${since}&limit=${HISTORY_PAGE}`).then((r) =>
        r.json(),
      )
      const events: HistoryEvent[] = Array.isArray(d.events) ? d.events : []
      if (events.length === 0) setNoMoreHistory(true)
      else mergeFetched(events)
    } catch {
      // transient failure — button stays usable for a retry
    } finally {
      loadingOlderRef.current = false
      setLoadingOlder(false)
    }
  }, [mergeFetched])

  const selectRun = useCallback(
    async (raw: string) => {
      const key = await ensureGodKey()
      if (!key) return
      const id = Number(raw)
      // Picking the live run canonicalizes back to follow-live mode.
      setSelectedRunId(id === liveWorldId ? null : id)
    },
    [liveWorldId],
  )


  const hungryCount = state?.entities.filter((e) => e.status === 'hungry').length ?? 0
  const starvingCount = state?.entities.filter((e) => e.status === 'starving').length ?? 0
  const chilledCount = state?.entities.filter((e) => (e.chill ?? 0) >= 12).length ?? 0
  const deadBreakdown = state
    ? Object.entries(state.dead_by_cause)
        .sort((a, b) => b[1] - a[1])
        .map(([cause, n]) => `${cause}: ${n}`)
        .join(' · ') || 'no deaths yet'
    : ''

  const isNight = state ? state.time_of_day < 0.22 || state.time_of_day > 0.78 : false
  const raining = state?.weather === 'rain' || state?.weather === 'storm'
  const exposedCount = raining
    ? (state?.entities.filter(
        (e) => e.kind === 'creature' && e.sleeping === false && e.indoors === false && e.infected === false,
      ).length ?? 0)
    : 0
  const weatherIcon =
    state?.weather === 'rain' ? '🌧' : state?.weather === 'fog' ? '🌫' : state?.weather === 'storm' ? '⛈' : ''
  const ageDay = state?.age_day ?? (state?.age_tick !== undefined ? Math.floor(state.age_tick / 1200) + 1 : 1)
  const ageTotalDays = state?.age_total_days ?? 10
  const isSafeguardActive = Boolean(state?.safeguard_active)
  const isSoftcapActive = Boolean(state?.softcap_active)

  return (
    <div className="app">
      <header className={`hud ${isMobile ? 'hud-compact' : ''}`}>
        <span className="title">{t('app.title')}</span>
        <span className={`dot ${status}`} title={t("app.hints.connection", { status: t(`app.status.${STATUS_LABEL[status]}`) } as any)} data-hint={t("app.hints.connection", { status: t(`app.status.${STATUS_LABEL[status]}`) } as any)} />
        {status !== 'open' && <span className="chip" style={{ color: status === 'connecting' ? '#d29922' : '#f85149' }}>{t(`app.status.${STATUS_LABEL[status]}`)}</span>}
        {paused && <span className="chip paused">{t("app.status.paused")}</span>}
        {state && (
          <span className="chip" title={t('app.hints.timeOfDay', { time: state.time_of_day, season: state.season, weather: state.weather } as any)}>
            {isNight ? '🌙' : '☀'} {t('app.hud.day')} <b>{state.day}</b> · {state.season}
            {weatherIcon && ` · ${weatherIcon}`}
          </span>
        )}
        {!isMobile && (
          <span className="chip" title={t('app.hints.currentTick')}>
            {t('app.hud.tick')} <b>{state?.tick ?? 0}</b>{estTps !== null && ` · ${estTps} t/s`}
          </span>
        )}
        <span
          className="chip alive"
          title={t('app.hints.alive', { label: t('app.hud.alive'), count: state?.creatures_alive ?? 0 } as any)}
          data-hint={`${t('app.hud.alive')}: ${state?.creatures_alive ?? 0}`}
        >
          💚{isMobile ? '' : ` ${t('app.hud.alive')}`} <b>{state?.creatures_alive ?? 0}</b>
        </span>
        <span
          className="chip dead desktop-only"
          title={t('app.hints.dead', { label: t('app.hud.dead'), count: state?.creatures_dead ?? 0, breakdown: deadBreakdown } as any)}
          data-hint={`${t('app.hud.dead')}: ${state?.creatures_dead ?? 0} (${deadBreakdown})`}
        >
          💀 {t('app.hud.dead')} <b>{state?.creatures_dead ?? 0}</b>
        </span>
        {hungryCount > 0 && (
          <span
            className="chip hungry desktop-only"
            title={t('app.hints.hungry', { count: hungryCount } as any)}
            data-hint={`${t('app.hud.hungry')}: ${hungryCount}`}
          >
            🍖 <b>{hungryCount}</b>
          </span>
        )}
        {starvingCount > 0 && (
          <span
            className="chip starving desktop-only"
            title={t('app.hints.starving', { count: starvingCount } as any)}
            data-hint={`${t('app.hud.starving')}: ${starvingCount}`}
          >
            ⚠️ <b>{starvingCount}</b>
          </span>
        )}
        {(state?.infected_count ?? 0) > 0 && (
          <span
            className="chip sick desktop-only"
            title={t('app.hints.infected', { count: state?.infected_count } as any)}
            data-hint={`${t('app.hud.infected')}: ${state?.infected_count}`}
          >
            ☣️ <b>{state?.infected_count}</b>
          </span>
        )}
        {chilledCount > 0 && (
          <span
            className="chip desktop-only"
            style={{ color: '#79c0ff' }}
            title={t('app.hints.chilled', { count: chilledCount } as any)}
            data-hint={`${t('app.hud.chilled')}: ${chilledCount}`}
          >
            🥶 <b>{chilledCount}</b>
          </span>
        )}
        {raining && exposedCount > 0 && (
          <span
            className="chip exposed desktop-only"
            title={t('app.hints.exposed', { count: exposedCount } as any)}
            data-hint={`${t('app.hud.exposed')}: ${exposedCount}`}
          >
            ⛈ <b>{exposedCount}</b>
          </span>
        )}
        {state && state.age && (
          <span
            className="chip desktop-only"
            title={t('app.hints.age', { age: state.age, day: ageDay, total: ageTotalDays } as any)}
            data-hint={`${t('app.hud.age')} ${state.age} · ${t('app.hud.day')} ${ageDay}/${ageTotalDays}`}
          >
            🗓 {t('app.hud.age')} <b>{state.age}</b> · {t('app.hud.day')} {ageDay}/{ageTotalDays}
          </span>
        )}

        {isMobile && <span className="chip" onClick={(e) => { e.stopPropagation(); setStatusExpanded(o => !o) }} style={{ marginLeft: 'auto', fontSize: 10, color: '#58a6ff', cursor: 'pointer' }}>{statusExpanded ? `▲ ${t('common.close')}` : `▼ ${t('common.more')}`}</span>}

        <div className="top-right-panel" style={{ display: 'flex', gap: 4, alignItems: 'center', flexWrap: 'nowrap', flexShrink: 0 }}>
          <select
            value={lang}
            onChange={e => setLang(e.target.value as any)}
            onClick={e => e.stopPropagation()}
            style={{
              background: '#161b22',
              color: '#c9d1d9',
              border: '1px solid #30363d',
              borderRadius: 6,
              padding: '2px 4px',
              fontSize: 11,
              cursor: 'pointer',
              minHeight: 28,
              maxHeight: 28,
            }}
            title={t('common.language')}
            aria-label={t('common.language')}
          >
            <option value="en">EN</option>
            <option value="fr">FR</option>
            <option value="vi">VI</option>
          </select>
          <button className="god-btn" onClick={() => setWorldHistoryOpen(true)} title={t('app.controls.history')} data-hint={t('app.controls.history')}>
            📜
          </button>
          <button className="god-btn wiki-btn" onClick={() => setWikiOpen(true)} title={t('wiki.open') || 'Wiki'} data-hint={t('wiki.open') || 'Wiki'}>
            📖
          </button>
          <button className="god-btn" onClick={() => setAnalyticsOpen(true)} title={t('analytics.hint')} data-hint={t('analytics.hint')}>
            📊
          </button>
          <button className="god-btn god-main-btn" onClick={() => setGodOpen(true)} title={t('god.tooltip')} data-hint={t('god.tooltip')}>
            ⚖
          </button>
        </div>
      </header>
      {isMobile && statusExpanded && (
        <>
        <div className="hud-detail-backdrop" onClick={() => setStatusExpanded(false)} />
        <div className="hud-detail-sheet" onClick={(e) => { if ((e.target as HTMLElement).tagName !== 'SELECT' && (e.target as HTMLElement).tagName !== 'BUTTON') setStatusExpanded(false); }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', width: '100%', marginBottom: 4, gap: 8 }}>
            <span style={{ fontSize: 13, fontWeight: 600, color: '#e6edf3', flex: 1, whiteSpace: 'normal', wordBreak: 'break-word' as any }}>{t('app.hud.worldDetails')}</span>
            <select
              value={lang}
              onChange={e => setLang(e.target.value as any)}
              onClick={e => e.stopPropagation()}
              style={{ background: '#161b22', color: '#c9d1d9', border: '1px solid #30363d', borderRadius: 6, padding: '4px 6px', fontSize: 11, cursor: 'pointer', minHeight: 28, flex: 'none' }}
              title={t('common.language')}
              aria-label={t('common.language')}
            >
              <option value="en">EN</option>
              <option value="fr">FR</option>
              <option value="vi">VI</option>
            </select>
            <button onClick={() => setStatusExpanded(false)} style={{ background: 'transparent', border: 'none', color: '#8b949e', fontSize: 16, cursor: 'pointer', padding: 0, minHeight: 24, flex: 'none' }}>✕</button>
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, wordBreak: 'break-word', overflowWrap: 'anywhere' as any }}>
            <span className="chip" style={{ whiteSpace: 'normal', wordBreak: 'break-word' as any, borderColor: '#e3b341', color: '#e3b341', flex: '0 0 100%', width: '100%', boxSizing: 'border-box' as any, justifyContent: 'flex-start' }}>{t('app.hud.tick')} <b>{state?.tick ?? 0}</b>{estTps !== null && ` · ${estTps} t/s`}</span>
            <span className="chip" style={{ whiteSpace: 'normal', wordBreak: 'break-word' }}>{t('app.hud.entities')} <b>{state?.entities.length ?? 0}</b></span>
            <span className="chip dead" style={{ whiteSpace: 'normal', wordBreak: 'break-word' }}>{t('app.hud.dead')} <b>{state?.creatures_dead ?? 0}</b></span>
            <span className="chip" style={{ fontSize: 10, color: '#8b949e', whiteSpace: 'normal', wordBreak: 'break-word', overflowWrap: 'anywhere' as any, flex: '0 0 100%', width: '100%', boxSizing: 'border-box' as any }}>{deadBreakdown}</span>
            {(state?.infected_count ?? 0) > 0 && <span className="chip sick" style={{ whiteSpace: 'normal' }}>{t('app.hud.infected')} <b>{state?.infected_count}</b></span>}
            {(state?.entities.filter((e) => (e.chill ?? 0) >= 12).length ?? 0) > 0 && <span className="chip" style={{ color: '#79c0ff', whiteSpace: 'normal' }}>🥶 {t('app.hud.chilled')} <b>{state?.entities.filter((e) => (e.chill ?? 0) >= 12).length}</b></span>}
            {raining && exposedCount > 0 && <span className="chip exposed" style={{ whiteSpace: 'normal' }}>⛈ {t('app.hud.exposed')} <b>{exposedCount}</b></span>}
            {hello && <span className="chip" style={{ whiteSpace: 'normal', wordBreak: 'break-word', overflowWrap: 'anywhere' as any }}>{t('app.hud.seed')} <b>{state?.seed ?? hello.seed}</b> · {state?.width ?? hello.width}×{state?.height ?? hello.height} · {state?.boundary ?? hello.boundary}</span>}
            {state?.age && <span className="chip" style={{ whiteSpace: 'normal' }}>🗓 {t('app.hud.age')} <b>{state.age}</b> · {t('app.hud.day')} {ageDay}/{ageTotalDays}</span>}
            <span className="chip" style={{ whiteSpace: 'normal' }}>{t('app.hud.hungry')} <b>{hungryCount}</b> · {t('app.hud.starving')} <b>{starvingCount}</b></span>
          </div>
          {worlds.length > 0 && (
            <div style={{ display: 'flex', flexDirection: isMobile ? 'column' as const : 'row' as const, flexWrap: 'wrap', alignItems: isMobile ? 'stretch' : 'center', gap: 8, marginTop: 6, paddingTop: 6, borderTop: '1px solid #21262d', wordBreak: 'break-word', overflowWrap: 'anywhere' as any }}>
              <span style={{ fontSize: 12, color: '#8b949e', flex: isMobile ? '0 0 100%' : 'none', whiteSpace: 'normal', wordBreak: 'break-word' as any }}>{t('app.hud.historyRun')}</span>
              <select
                className="run-select"
                value={String(selectedRunId ?? liveWorldId ?? '')}
                onPointerDown={async (e) => {
                  if (!getCachedKey()) {
                    e.preventDefault()
                    await ensureGodKey()
                  }
                }}
                onChange={(e) => void selectRun(e.target.value)}
                style={{ flex: isMobile ? '0 0 100%' : 1, minHeight: 32, fontSize: 12, minWidth: 0, width: isMobile ? '100%' : undefined }}
              >
                {worlds.map((w) => (
                  <option key={w.id} value={String(w.id)}>
                    #{w.id} · seed {w.seed} · {fmtStart(w.started_at)}
                    {w.ended_at === null ? ' · (live)' : ''}
                  </option>
                ))}
              </select>
            </div>
          )}
          <div style={{ display: 'flex', gap: 6, marginTop: 8, flexWrap: 'wrap' }}>
            <button className="god-btn" onClick={() => { setStatusExpanded(false); setWorldHistoryOpen(true); }} style={{ flex: 1, minHeight: 34, fontSize: 12 }}>
              📜 {t('history.title') || 'World History'}
            </button>
            <button className="god-btn" onClick={() => { setStatusExpanded(false); setWikiOpen(true); }} style={{ flex: 1, minHeight: 34, fontSize: 12 }}>
              📖 {t('wiki.open') || 'Wiki'}
            </button>
            <button className="god-btn" onClick={() => { setStatusExpanded(false); setAnalyticsOpen(true); }} style={{ flex: 1, minHeight: 34, fontSize: 12 }}>
              📊 {t('analytics.open')}
            </button>
            <a className="god-btn" href={apiUrl('/health')} target="_blank" rel="noopener noreferrer" style={{ flex: '0 0 auto', padding: '0 10px', minHeight: 34, fontSize: 12, display: 'inline-flex', alignItems: 'center', justifyContent: 'center', textDecoration: 'none', color: '#c9d1d9' }}>
              🏥 Health ↗
            </a>
          </div>
        </div>
        </>
      )}

      <main className="stage">
        <CanvasRenderer
          stateRef={stateRef}
          selectedRef={selectedRef}
          selectedClanRef={selectedClanRef}
          onTapCreature={selectCreature}
          lensMode={lensMode}
        />

        {(isSafeguardActive || isSoftcapActive) && (
          <div
            className="regulation-status-container"
            style={{
              position: isMobile ? 'fixed' : 'absolute',
              top: 'auto',
              right: 'auto',
              left: !isMobile && (selectedId !== null || selectedClanId !== null) ? 406 : (isMobile ? 8 : 14),
              bottom: isMobile ? 'calc(var(--thumb-h) + env(safe-area-inset-bottom) + 8px)' : 12,
              width: 'fit-content',
              transform: 'none',
            }}
          >
            {isSafeguardActive && (
              <div className="regulation-status-badge safeguard">
                <span className="regulation-status-dot" />
                <span>{t('app.status.safeguard_active') || 'Safeguard Active'}</span>
              </div>
            )}
            {isSoftcapActive && (
              <div className="regulation-status-badge softcap">
                <span className="regulation-status-dot" />
                <span>{t('app.status.softcap_active') || 'Softcap Active'}</span>
              </div>
            )}
          </div>
        )}
      </main>

      {/* Mobile thumb bar — persistent bottom bar */}
      {isMobile && (
        <div className="mobile-thumb-bar" role="toolbar" aria-label="World controls">
          <button onClick={paused ? sendResume : sendPause} title={paused ? t('app.controls.resume') : t('app.controls.pause')} aria-label={paused ? t('app.controls.resume') : t('app.controls.pause')}>{paused ? '▶' : '⏸'}</button>
          <button onClick={sendStep} title={t('app.controls.step')} aria-label={t('app.controls.step')}>⏭</button>
          <button onClick={confirmReset} title={t('app.controls.reset')} aria-label={t('app.controls.reset')} style={{ color: '#ff7b72' }}>🔄</button>
          <button onClick={() => setGodOpen(true)} title={t('app.controls.god')} aria-label={t('app.controls.god')}>⚖</button>
          <button
            className={sheetState !== 'hidden' ? 'active-sheet-btn' : ''}
            onClick={() => {
              if (sheetState === 'hidden') {
                setSheetTab('chronicle')
                setSheetState('half')
              } else {
                setSheetState('hidden')
              }
            }}
            title={t('app.rightStack.chronicle')}
            aria-label={t('app.rightStack.chronicle')}
            aria-expanded={sheetState !== 'hidden'}
          >
            📜
          </button>
          <button onClick={() => window.dispatchEvent(new Event('flatworld-fit'))} title={t('app.controls.fit')} aria-label={t('app.controls.fit')}>⛶</button>
          <select value={speed} onChange={e => changeSpeed(Number(e.target.value))} title="ticks/s" aria-label="ticks/s">
            {SPEEDS.map(v => <option key={v} value={v}>{v}t/s</option>)}
          </select>
        </div>
      )}

      {/* Mobile tabbed sheet — World / Clans / Chronicle */}
      {isMobile && sheetState !== 'hidden' && (
        <div className="mobile-sheet" data-state={sheetState}>
          <button
            type="button"
            className="mobile-sheet-handle"
            onClick={() => setSheetState(s => s === 'peek' ? 'half' : s === 'half' ? 'full' : 'peek')}
            aria-label="Resize sheet"
          />
          <div className="mobile-sheet-header">
            <div className="mobile-sheet-tabs" role="tablist" aria-label="Sheet panels">
              <button role="tab" aria-selected={sheetTab === 'world'} className={sheetTab === 'world' ? 'active' : ''} onClick={() => setSheetTab('world')}>{t('app.controls.world')}</button>
              <button role="tab" aria-selected={sheetTab === 'clans'} className={sheetTab === 'clans' ? 'active' : ''} onClick={() => setSheetTab('clans')}>{t('app.controls.clans')}</button>
              <button role="tab" aria-selected={sheetTab === 'chronicle'} className={sheetTab === 'chronicle' ? 'active' : ''} onClick={() => setSheetTab('chronicle')}>{t('app.controls.chronicle')}</button>
            </div>
            <button
              className="mobile-sheet-close"
              onClick={(e) => {
                e.stopPropagation()
                e.preventDefault()
                setSheetState('hidden')
              }}
              title="Hide sheet"
              aria-label="Close bottom sheet"
            >
              ✕
            </button>
          </div>
          <div className="mobile-sheet-body">
            {sheetTab === 'world' && (
              <OverviewPanel
                state={state}
                aliveHist={aliveHist}
                onSelectCreature={selectCreature}
                onSelectClan={selectClan}
              />
            )}
            {sheetTab === 'clans' && <ClanPanel state={state} onSelectClan={selectClan} onSelectCreature={selectCreature} />}
            {sheetTab === 'chronicle' && (
              <div className="chronicle" style={{ background: 'transparent', border: 'none', padding: 0, maxHeight: 'none', height: '100%', display: 'flex', flexDirection: 'column', minHeight: 0, overflow: 'hidden', flex: '1 1 0' }}>
                <ChronicleFeed
                  events={log}
                  clanLabel={clanLabel}
                  onSelectCreature={selectCreature}
                  onSelectClan={selectClan}
                  onLoadOlder={loadOlder}
                  loadingOlder={loadingOlder}
                  noMoreHistory={noMoreHistory}
                  archiveMode={archiveMode}
                  selectedRunId={selectedRunId}
                  compact
                />
              </div>
            )}
          </div>
        </div>
      )}

      {!isMobile && (
        <>
          <footer className="controls">
            {paused ? (
              <button onClick={sendResume} title={t('app.controls.resume')} data-hint={t('app.controls.resume')}>▶</button>
            ) : (
              <button onClick={sendPause} title={t('app.controls.pause')} data-hint={t('app.controls.pause')}>⏸</button>
            )}
            <button onClick={sendStep} title={t('app.controls.step')} data-hint={t('app.controls.step')}>⏭</button>
            <button onClick={confirmReset} title={t('app.controls.reset')} data-hint={t('app.controls.reset')}>🔄</button>
            <button onClick={() => window.dispatchEvent(new Event('flatworld-fit'))} title={t('app.controls.fit')} data-hint={t('app.controls.fit')}>
              ⛶
            </button>
            <button onClick={() => setChronicleOpen((o) => !o)} title={chronicleOpen ? t('app.controls.hideChronicle') : t('app.controls.showChronicle')} data-hint={chronicleOpen ? t('app.controls.hideChronicle') : t('app.controls.showChronicle')}>
              {chronicleOpen ? '▤' : '📜'}
            </button>
            <label className="chip" htmlFor="speed" title={t('app.controls.tps')} data-hint={t('app.controls.tps')}>
              ⚡
            </label>
            <select
              id="speed"
              value={speed}
              onChange={(e) => changeSpeed(Number(e.target.value))}
              title={t('app.controls.speedTps')}
              data-hint={t('app.controls.speedTps')}
            >
              {SPEEDS.map((v) => (
                <option key={v} value={v}>
                  {v}
                </option>
              ))}
            </select>
            {worlds.length > 0 && (
              <div className="run-switcher">
                <label className="chip run-label" htmlFor="run-bottom" title={t('app.controls.runSelect')} data-hint={t('app.controls.runSelect')}>
                  ⚖ run
                  <select
                    id="run-bottom"
                    className="run-select"
                    value={String(selectedRunId ?? liveWorldId ?? '')}
                    onPointerDown={async (e) => {
                      if (!getCachedKey()) {
                        e.preventDefault()
                        await ensureGodKey()
                      }
                    }}
                    onChange={(e) => void selectRun(e.target.value)}
                  >
                    {worlds.map((w) => (
                      <option key={w.id} value={String(w.id)}>
                        #{w.id} · seed {w.seed} · {fmtStart(w.started_at)}
                        {w.ended_at === null ? ' · (live)' : ''}
                      </option>
                    ))}
                  </select>
                </label>
              </div>
            )}

          </footer>

          <p className="key-hints">{t("app.footer.spacePause")} · {t("app.footer.step")} · {t("app.footer.reset")} · {t("app.footer.fit")} · {t("app.footer.zoom")}</p>
        </>
      )}


      {!isMobile && (() => {
        const clanCount = state ? Object.keys(state.clans ?? {}).length : 0
        if (rightCollapsed) {
          return (
            <button
              className="right-stack-expand"
              onClick={() => setRightCollapsed(false)}
              title={t('app.rightStack.expand')}
              aria-label={t('app.rightStack.expand')}
            >
              ◀
            </button>
          )
        }
        return (
        <div
          className="right-stack"
          onPointerDown={(e) => e.stopPropagation()}
          onMouseDown={(e) => e.stopPropagation()}
          onTouchStart={(e) => e.stopPropagation()}
          onWheel={(e) => e.stopPropagation()}
        >
          <div className="right-stack-header">
            <div className="right-stack-tabs" role="tablist" aria-label="Right stack panels">
              <button
                role="tab"
                aria-selected={rightTab === 'overview'}
                className={`right-stack-tab ${rightTab === 'overview' ? 'active' : ''}`}
                onClick={() => setRightTab('overview')}
              >
                📊 {t('app.rightStack.overview')}
              </button>
              <button
                role="tab"
                aria-selected={rightTab === 'clans'}
                className={`right-stack-tab ${rightTab === 'clans' ? 'active' : ''}`}
                onClick={() => setRightTab('clans')}
              >
                🏰 {t('app.rightStack.clans')} ({clanCount})
              </button>
              <button
                role="tab"
                aria-selected={rightTab === 'chronicle'}
                className={`right-stack-tab ${rightTab === 'chronicle' ? 'active' : ''}`}
                onClick={() => setRightTab('chronicle')}
              >
                📜 {t('app.rightStack.chronicle')}
              </button>
            </div>
            <button
              className="right-stack-collapse"
              onClick={() => setRightCollapsed(true)}
              title={t('app.rightStack.collapse')}
              aria-label={t('app.rightStack.collapse')}
            >
              ▶
            </button>
          </div>
          <div className="right-stack-body">
            {rightTab === 'overview' && (
              <OverviewPanel
                state={state}
                aliveHist={aliveHist}
                onSelectCreature={selectCreature}
                onSelectClan={selectClan}
              />
            )}
            {rightTab === 'clans' && (
              <ClanPanel state={state} onSelectClan={selectClan} onSelectCreature={selectCreature} />
            )}
            {rightTab === 'chronicle' && (
              <ChronicleFeed
                events={log}
                clanLabel={clanLabel}
                onSelectCreature={selectCreature}
                onSelectClan={selectClan}
                onLoadOlder={loadOlder}
                loadingOlder={loadingOlder}
                noMoreHistory={noMoreHistory}
                archiveMode={archiveMode}
                selectedRunId={selectedRunId}
              />
            )}
          </div>
        </div>
        )
      })()}

      {selectedId !== null && (
        <Inspector
          id={selectedId}
          state={state}
          onClose={() => setSelectedId(null)}
          onNavigate={(nid) => setSelectedId(nid)}
          onSelectClan={selectClan}
        />
      )}

      <GodPanel open={godOpen} onClose={() => setGodOpen(false)} />
      <Wiki open={wikiOpen} onClose={() => setWikiOpen(false)} />
      {analyticsOpen && (
        <div className="wiki-backdrop" onClick={() => setAnalyticsOpen(false)}>
          <div className="wiki-panel" style={{ maxHeight: '90vh', width: 'min(900px, 96vw)' }} onClick={(e) => e.stopPropagation()}>
            <header className="god-head">
              <h2>🔭 {t('analytics.title')}</h2>
              <button className="god-close" onClick={() => setAnalyticsOpen(false)} aria-label={t('common.close')}>×</button>
            </header>
            <div style={{ maxHeight: '70vh', overflowY: 'auto', padding: '8px 0' }}>
              <Observatory
                state={state}
                onSelectCreature={(id) => {
                  selectCreature(id)
                  setAnalyticsOpen(false)
                }}
              />
            </div>
          </div>
        </div>
      )}
      {selectedClanId !== null && (
        <ClanDetails
          clanId={selectedClanId}
          state={state}
          initialTab={initialClanTab}
          onClose={() => {
            setSelectedClanId(null)
            setInitialClanTab(undefined)
          }}
          onSelectCreature={selectCreature}
        />
      )}
      {showWorldEnd && state && (
        <WorldEndSummary
          state={state}
          onReset={() => { sendReset(); setShowWorldEnd(false) }}
          onClose={() => setShowWorldEnd(false)}
          onOpenWorldHistory={() => { setShowWorldEnd(false); setWorldHistoryOpen(true); }}
        />
      )}
      <WorldHistoryModal
        open={worldHistoryOpen}
        onClose={() => setWorldHistoryOpen(false)}
        initialDay={historyInitialDay}
        state={state}
        worlds={worlds}
        selectedRunId={selectedRunId}
        onSelectClan={(cid) => selectClan(cid, 'biography')}
        onSelectCreature={selectCreature}
      />
      <ConfirmModal open={resetConfirmOpen} onClose={() => setResetConfirmOpen(false)} onConfirm={doReset} />

      {helpOpen && (
        <div className="help-backdrop" onClick={() => setHelpOpen(false)}>
          <div className="help-panel" onClick={(e) => e.stopPropagation()}>
            <header className="god-head">
              <h3>{t('app.hintsModal.title')}</h3>
              <button className="god-close" onClick={() => setHelpOpen(false)}>×</button>
            </header>
            <p className="god-note">{t('app.hintsModal.subtitle')}</p>
            <ul>
              <li><b>{t('app.hud.tick')}</b>: {t('app.hintsModal.tick')}</li>
              <li><b>{t('app.hud.entities')}</b>: {t('app.hintsModal.entities')}</li>
              <li><b>{t('app.hud.alive')}/{t('app.hud.dead')}</b>: {t('app.hintsModal.aliveDead')}</li>
              <li><b>{t('app.hud.hungry')}/{t('app.hud.starving')}</b>: {t('app.hintsModal.hungryStarving')}</li>
              <li><b>{t('app.hud.infected')}</b>: {t('app.hintsModal.infected')}</li>
              <li><b>{t('app.hud.exposed')}</b>: {t('app.hintsModal.exposed')}</li>
              <li><b>{t('app.hud.chilled')}</b>: {t('app.hintsModal.chilled')}</li>
              <li><b>{t('app.hud.seed')}·WxH·boundary</b>: {t('app.hintsModal.seedDimensions')}</li>
              <li><b>{t('app.hud.day')}/{t('app.hud.season')}/{t('app.hud.weather')}</b>: {t('app.hintsModal.weatherSeasons')}</li>
              <li><b>{t('app.hud.age')}</b>: {t('app.hintsModal.age')}</li>
              <li><b>{t('app.rightStack.overview')}</b>: {t('app.hintsModal.overview')}</li>
              <li><b>{t('app.hintsModal.tapCreature').split(':')[0] || 'Tap creature'}</b>: {t('app.hintsModal.tapCreature')}</li>
              <li><b>{t('app.hintsModal.controls').split(':')[0] || 'Controls'}</b>: {t('app.hintsModal.controls')}</li>
              <li><b>{t('app.topNav.history')}</b>: {t('app.hintsModal.historyChronicle')}</li>
            </ul>
          </div>
        </div>
      )}
      {!isMobile && (
        <div className="version-bar" title={versionInfo ? `v${versionInfo.version} · ${versionInfo.revision} · Developed by Long Phan <long@minhnhan.in> · Built with OpenCode & Antigravity` : 'Flatland · Developed by Long Phan <long@minhnhan.in>'}>
          {versionInfo ? `v${versionInfo.version} · ${versionInfo.revision}` : 'v0.1.6'} · <span style={{ opacity: 0.85 }}>Developed by Long Phan · <a href="mailto:long@minhnhan.in" style={{ color: 'inherit', textDecoration: 'underline' }}>long@minhnhan.in</a> · <a href={getLandingUrl()} target="_blank" rel="noopener noreferrer" style={{ color: 'inherit', textDecoration: 'underline' }}>Landing</a> · <a href={apiUrl('/wiki')} target="_blank" rel="noopener noreferrer" style={{ color: 'inherit', textDecoration: 'underline' }}>Wiki</a> · <a href={apiUrl('/docs')} target="_blank" rel="noopener noreferrer" style={{ color: 'inherit', textDecoration: 'underline' }}>Docs</a> · <a href={apiUrl('/health')} target="_blank" rel="noopener noreferrer" style={{ color: 'inherit', textDecoration: 'underline' }}>Health</a></span>
        </div>
      )}
      <AuthModal />
    </div>
  )
}
