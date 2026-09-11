import { useEffect, useRef, useState } from 'react'
import { TOTEMS, totemEmoji } from '../totems'
import type { ClanHistoryEvent } from '../types'
import { useI18n } from '../i18n'

interface ClanMember {
  id: number
  caste: string
  sex: string
  age: number
  lifespan: number
  stage: string
  energy: number
  health: number
  status: string
  personal_name: string
  glyph: string
}

interface ClanHouse {
  id: number
  x: number
  y: number
  size: number
  is_main?: boolean
}

interface ClanDetailsData {
  id: number
  name: string
  color: string
  totem: string | null
  founder_id: number
  leader_id: number | null
  born_tick: number
  founded_day?: number
  dead_count?: number
  population: number
  house: ClanHouse | null
  houses?: ClanHouse[]
  main_house_id?: number | null
  war_wins: number
  war_losses: number
  territory_radius: number | null
  specialization: { warrior: number; farmer: number; scavenger: number } | null
  culture: string | null
  members: ClanMember[]
  events: any[]
  history?: ClanHistoryEvent[]
  faith?: number
  shrine_level?: number
}

function Bar({ label, value, max, color }: { label: string; value: number; max: number; color: string }) {
  const pct = Math.max(0, Math.min(100, (value / max) * 100))
  return (
    <div className="insp-bar">
      <span className="chip" style={{ minWidth: 80 }}>{label}</span>
      <div className="insp-track">
        <div className="insp-fill" style={{ width: `${pct}%`, background: color }} />
      </div>
      <span className="chip">
        <b>{Math.round(value)}%</b>
      </span>
    </div>
  )
}

interface ClanBiographyData {
  clan: {
    id: number
    name: string
    color: string
    totem: string | null
    founder_id?: number
    leader_id?: number | null
    founded_tick?: number
    peak_population?: number
    current_population?: number
    active?: boolean
  }
  epitaph?: {
    clan_id: number
    clan_name: string
    totem: string | null
    color: string
    founded_tick: number
    extinct_tick: number
    peak_population: number
    peak_tick: number
    wars_fought: number
    battles_won: number
    temples_built: number
    schisms_caused: number
    extinction_cause: string | null
  } | null
  lifespan?: {
    founded_day: number
    extinct_day: number | null
    active: boolean
  }
  stats: {
    wars_fought: number
    wars_won: number
    schisms: number
    temples_built: number
    top_rival: string | null
    peak_population?: number
    extinction_cause?: string | null
  }
  notables?: {
    hero?: { id: number; personal_name: string; title?: string; kill_count: number } | null
    villain?: { id: number; name: string; deed: string } | null
  }
  recent_events?: any[]
}

type TabKey = 'stronghold' | 'roster' | 'warfare' | 'annals' | 'biography'

export default function ClanDetails({
  clanId,
  state: _state,
  initialTab,
  onClose,
  onSelectCreature,
}: {
  clanId: number
  state?: any
  initialTab?: TabKey
  onClose: () => void
  onSelectCreature?: (id: number) => void
}) {
  const { t } = useI18n()
  const [data, setData] = useState<ClanDetailsData | null>(null)
  const [loading, setLoading] = useState(true)
  const [snap, setSnap] = useState<'peek' | 'half' | 'full'>('half')
  const [copiedClanLink, setCopiedClanLink] = useState(false)
  const [bioData, setBioData] = useState<ClanBiographyData | null>(null)
  const [loadingBio, setLoadingBio] = useState(false)
  const [storyCopied, setStoryCopied] = useState(false)
  const startYRef = useRef<number | null>(null)
  const snapRef = useRef(snap)
  useEffect(() => { snapRef.current = snap }, [snap])
  const handleDragStart = (e: React.TouchEvent) => {
    startYRef.current = e.touches[0].clientY
  }
  const handleDragEnd = (e: React.TouchEvent) => {
    if (startYRef.current === null) return
    const dy = e.changedTouches[0].clientY - startYRef.current
    startYRef.current = null
    const cur = snapRef.current
    if (dy < -30) {
      if (cur === 'peek') setSnap('half')
      else if (cur === 'half') setSnap('full')
    } else if (dy > 30) {
      if (cur === 'full') setSnap('half')
      else if (cur === 'half') setSnap('peek')
      else if (cur === 'peek') onClose()
    }
  }
  const cycleSnap = () => setSnap((s) => (s === 'peek' ? 'half' : s === 'half' ? 'full' : 'peek'))
  const [activeTab, setActiveTab] = useState<TabKey>(() => {
    if (initialTab) return initialTab
    try {
      const s = sessionStorage.getItem('clan-tab') as TabKey | null
      if (s && ['stronghold','roster','warfare','annals','biography'].includes(s)) return s
    } catch {}
    return 'stronghold'
  })
  const [rosterFilter, setRosterFilter] = useState<'all'|'warriors'|'harvesters'|'elders'|'sick'>('all')

  useEffect(() => {
    if (initialTab) {
      setActiveTab(initialTab)
    }
  }, [initialTab])

  useEffect(() => {
    try { sessionStorage.setItem('clan-tab', activeTab) } catch {}
  }, [activeTab])

  useEffect(() => {
    if (activeTab === 'biography' || !bioData) {
      setLoadingBio(true)
      fetch(`/api/clan/${clanId}/biography`)
        .then((r) => r.json())
        .then((d) => {
          setBioData(d)
          setLoadingBio(false)
        })
        .catch(() => setLoadingBio(false))
    }
  }, [clanId, activeTab])

  useEffect(() => {
    setLoading(true)
    let alive = true
    const load = () => {
      fetch(`/api/clans/${clanId}`)
        .then((r) => r.json())
        .then((d) => {
          if (alive) {
            setData(d)
            setLoading(false)
          }
        })
        .catch(() => {
          if (alive) setLoading(false)
        })
    }
    load()
    const t = setInterval(() => {
      if (document.hidden) return
      load()
    }, 2500)
    return () => {
      alive = false
      clearInterval(t)
    }
  }, [clanId])

  if (loading && !data) {
    return (
      <aside className="inspector clan-inspector" data-snap={snap}>
        <div className="inspector-handle" role="button" aria-label="drag handle" onClick={cycleSnap} onTouchStart={handleDragStart} onTouchEnd={handleDragEnd} />
        <header className="insp-head" onTouchStart={handleDragStart} onTouchEnd={handleDragEnd}>
          <h2>Clan #{clanId}</h2>
          <button type="button" className="insp-close-btn" onClick={onClose} aria-label={t('common.close')}>×</button>
        </header>
        <p className="god-note">{t('clanDetails.loading')}</p>
      </aside>
    )
  }

  if (!data) {
    return (
      <aside className="inspector clan-inspector" data-snap={snap}>
        <div className="inspector-handle" role="button" aria-label="drag handle" onClick={cycleSnap} onTouchStart={handleDragStart} onTouchEnd={handleDragEnd} />
        <header className="insp-head" onTouchStart={handleDragStart} onTouchEnd={handleDragEnd}>
          <h2>Clan #{clanId}</h2>
          <button type="button" className="insp-close-btn" onClick={onClose} aria-label={t('common.close')}>×</button>
        </header>
        <p className="god-note">{t('clanDetails.notFound')}</p>
      </aside>
    )
  }

  const totemInfo = data.totem ? TOTEMS[data.totem] : null

  const filteredMembers = data.members.filter(m => {
    if (rosterFilter === 'all') return true
    if (rosterFilter === 'warriors') return m.caste === 'Soldier' || m.caste === 'Predator'
    if (rosterFilter === 'harvesters') return m.caste === 'Artisan' || m.caste === 'Gentleman'
    if (rosterFilter === 'elders') return m.stage === 'elder'
    if (rosterFilter === 'sick') return m.status === 'hungry' || m.status === 'starving' || m.health < 60
    return true
  })

  const generateClanStoryPrompt = () => {
    if (!bioData) return
    const c = bioData.clan
    const s = bioData.stats
    const l = bioData.lifespan
    const n = bioData.notables
    const prompt = [
      `# Clan Chronicle: The Saga of ${c.name} (Clan #${c.id})`,
      ``,
      `Write a rich, immersive mythological saga chronicling the rise, trials, and legacy of Clan ${c.name} in Flatland.`,
      ``,
      `## Historical Profile:`,
      `- Totem: ${c.totem ? `${c.totem} (${totemEmoji(c.totem)})` : 'None'}`,
      `- Lifespan: Founded on Day ${l?.founded_day ?? 0}, ${l?.active ? 'thriving to the present day' : `met its doom on Day ${l?.extinct_day ?? '?'} due to ${s.extinction_cause || 'collapse'}`}`,
      `- Peak Population: ${s.peak_population ?? c.peak_population ?? 'Unknown'} members at its zenith`,
      `- Warfare: Fought in ${s.wars_fought} wars, victorious in ${s.wars_won} conflicts`,
      `- Primary Rival: ${s.top_rival || 'None recognized'}`,
      `- Spiritual Legacy: ${s.temples_built} holy temples erected`,
      `- Internal Strife: Endured ${s.schisms} internal schisms and splits`,
      n?.hero ? `- Legendary Champion: ${n.hero.personal_name}${n.hero.title ? ` the ${n.hero.title}` : ''} (#${n.hero.id}) with ${n.hero.kill_count} confirmed kills` : '',
      n?.villain ? `- Infamous Antagonist: ${n.villain.name} (#${n.villain.id}) remembered for ${n.villain.deed}` : '',
      ``,
      `Narrate this history across 3 distinct eras: The Genesis & Founding, The Golden Age & Crucible of War, and the Enduring Legacy. Keep it cinematic and evocative.`
    ].filter(Boolean).join('\n')

    navigator.clipboard?.writeText(prompt)
    setStoryCopied(true)
    setTimeout(() => setStoryCopied(false), 2000)
  }

  return (
    <aside className="inspector clan-inspector" data-snap={snap}>
      <div className="inspector-handle" role="button" aria-label="drag handle" onClick={cycleSnap} onTouchStart={handleDragStart} onTouchEnd={handleDragEnd} />

      {/* Hero Header & Clan Dossier Card */}
      <div className="clan-hero-card" style={{ borderLeftColor: data.color }}>
        <div className="clan-hero-top">
          <div className="clan-totem-badge" style={{ borderColor: data.color, background: `${data.color}22` }}>
            {data.totem ? totemEmoji(data.totem) : '🚩'}
          </div>
          <div className="clan-hero-info">
            <div className="clan-hero-title-row">
              <h2 className="clan-hero-name" style={{ color: data.color }}>
                {data.name}
              </h2>
              <span className="clan-id-tag">#{data.id}</span>
              <button
                type="button"
                onClick={() => {
                  const url = `${window.location.origin}${window.location.pathname}?clan=${data.id}`
                  navigator.clipboard?.writeText(url)
                  setCopiedClanLink(true)
                  setTimeout(() => setCopiedClanLink(false), 2000)
                }}
                style={{
                  background: copiedClanLink ? '#238636' : 'rgba(255, 255, 255, 0.08)',
                  border: '1px solid',
                  borderColor: copiedClanLink ? '#2ea043' : '#30363d',
                  color: copiedClanLink ? '#fff' : '#8b949e',
                  borderRadius: 4,
                  fontSize: 10.5,
                  padding: '1px 6px',
                  cursor: 'pointer',
                  marginLeft: 4,
                }}
                title={t('clanDetails.copyLinkTitle')}
              >
                {copiedClanLink ? '✓ Link Copied' : '🔗 Share'}
              </button>
            </div>
            <div className="clan-hero-sub">
              <span>{t('clanDetails.founded', { day: data.founded_day ?? Math.floor((data.born_tick ?? 0)/1200) })}</span>
              <span>·</span>
              <span style={{ color: '#3fb950', fontWeight: 600 }}>{data.population} {t('clanDetails.aliveShort') !== 'clanDetails.aliveShort' ? t('clanDetails.aliveShort') : 'alive'}</span>
              {typeof data.dead_count === 'number' && data.dead_count > 0 ? (
                <span style={{ color: '#8b949e' }}>({data.dead_count} †)</span>
              ) : null}
            </div>
          </div>
          <button type="button" className="insp-close-btn" onClick={onClose} aria-label={t('common.close')}>×</button>
        </div>

        {/* Quick Meta Row: Shrine/Faith + Leader + Totem Buff */}
        <div className="clan-meta-row">
          {(data.faith != null || (data.shrine_level ?? 0) >= 1) && (
            <span className="clan-meta-chip">
              {(data.shrine_level ?? 0) >= 2 ? `🏛️ ${t('clanDetails.templeOfSphere')}` : (data.shrine_level ?? 0) >= 1 ? `⛩️ ${t('clanDetails.shrine')}` : t('clanDetails.noShrine')}
              {typeof data.faith === 'number' && data.faith > 0 ? ` ✨ ${Math.round(data.faith)}` : ''}
            </span>
          )}
          {data.leader_id && (
            <button
              type="button"
              onClick={() => onSelectCreature?.(data.leader_id!)}
              className="clan-leader-btn"
              style={{ background: `${data.color}22`, borderColor: data.color, color: data.color }}
              title={t('clanDetails.inspectCreature', { id: data.leader_id })}
            >
              👑 #{data.leader_id} ↗
            </button>
          )}
          {totemInfo && (
            <span className="clan-totem-buff" title={totemInfo.buff}>
              {data.totem && t(`totems.${data.totem}`) !== `totems.${data.totem}` ? t(`totems.${data.totem}`) : totemInfo.buff}
            </span>
          )}
        </div>
      </div>

      {/* 5-Tab Codex */}
      <div className="insp-tabs">
        {(
          [
            {
              key: 'stronghold',
              icon: '🏰',
              short: t('clanDetails.tabStrongholdShort') !== 'clanDetails.tabStrongholdShort' ? t('clanDetails.tabStrongholdShort') : 'Stronghold',
              full: t('clanDetails.tabStronghold') !== 'clanDetails.tabStronghold' ? t('clanDetails.tabStronghold') : 'Stronghold',
            },
            {
              key: 'biography',
              icon: '🏛️',
              short: t('clanDetails.tabBioShort') !== 'clanDetails.tabBioShort' ? t('clanDetails.tabBioShort') : 'Bio',
              full: t('clanDetails.tabBiography') !== 'clanDetails.tabBiography' ? t('clanDetails.tabBiography') : 'Clan Biography & Heritage',
            },
            {
              key: 'roster',
              icon: '👥',
              short: t('clanDetails.tabRosterShort') !== 'clanDetails.tabRosterShort' ? t('clanDetails.tabRosterShort') : 'Roster',
              full: t('clanDetails.tabRoster') !== 'clanDetails.tabRoster' ? t('clanDetails.tabRoster') : 'Roster',
              count: data.members.length,
            },
            {
              key: 'warfare',
              icon: '⚔️',
              short: t('clanDetails.tabWarfareShort') !== 'clanDetails.tabWarfareShort' ? t('clanDetails.tabWarfareShort') : 'Warfare',
              full: t('clanDetails.tabWarfare') !== 'clanDetails.tabWarfare' ? t('clanDetails.tabWarfare') : 'Warfare & Diplomacy',
            },
            {
              key: 'annals',
              icon: '📜',
              short: t('clanDetails.tabAnnalsShort') !== 'clanDetails.tabAnnalsShort' ? t('clanDetails.tabAnnalsShort') : 'Annals',
              full: t('clanDetails.tabAnnals') !== 'clanDetails.tabAnnals' ? t('clanDetails.tabAnnals') : 'Annals',
              count: data.history?.length,
            },
          ] as Array<{ key: TabKey; icon: string; short: string; full: string; count?: number }>
        ).map((tab) => (
          <button
            key={tab.key}
            type="button"
            className={activeTab === tab.key ? 'active' : ''}
            onClick={() => setActiveTab(tab.key)}
            title={tab.full}
            aria-selected={activeTab === tab.key}
          >
            <span className="tab-icon">{tab.icon}</span>
            <span className="tab-label">{tab.short}</span>
            {typeof tab.count === 'number' && tab.count > 0 && (
              <span className="tab-badge">{tab.count}</span>
            )}
          </button>
        ))}
      </div>

      {activeTab === 'stronghold' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8, minWidth: 0 }}>
          <div className="insp-grid insp-2col">
            <span className="chip">{t('clanDetails.founded', { day: data.founded_day ?? Math.floor((data.born_tick ?? 0)/1200) })}</span>
            <span className="chip dead">{t('clanDetails.dead', { count: data.dead_count ?? 0 })}</span>
            <span className="chip">{t('clanDetails.founder')} {data.founder_id ? <button onClick={() => onSelectCreature?.(data.founder_id)} className="chronicle-name" style={{ fontWeight: 600 }}>#{data.founder_id} ↗</button> : '—'}</span>
            <span className="chip">{t('clanDetails.leader')} {data.leader_id ? <button onClick={() => onSelectCreature?.(data.leader_id!)} className="chronicle-name" style={{ fontWeight: 600, color: data.color }}>#{data.leader_id} ↗</button> : 'none'}</span>
          </div>
          <div style={{ background: 'rgba(22,27,34,0.6)', padding: '6px 8px', borderRadius: 6, border: '1px solid #30363d', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 6 }}>
            <span style={{ display: 'inline-flex', gap: 5, alignItems: 'center' }}>👑 {data.house ? <b style={{ color: '#e6edf3' }}>{t('clanDetails.mainHouse', { id: data.house.id, x: Math.round(data.house.x), y: Math.round(data.house.y) })}</b> : <span style={{ color: '#8b949e' }}>{t('clanDetails.homeless')}</span>}</span>
            {data.territory_radius && <span className="chip" style={{ fontSize: 11 }}>{t('clanDetails.radius', { r: data.territory_radius })}</span>}
          </div>
          {(data.houses && data.houses.length > 0) && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              <div style={{ fontSize: 11, color: '#8b949e', textTransform: 'uppercase', letterSpacing: 0.5 }}>{t('clanDetails.housesTitle', { count: data.houses.length })}</div>
              {data.houses.map((h) => (
                <div key={h.id} className="chip" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '5px 8px', background: h.is_main ? 'rgba(227,179,65,0.12)' : 'rgba(22,27,34,0.7)', border: h.is_main ? '1px solid #e3b341' : `1px solid ${data.color}`, borderRadius: 6 }}>
                  <span>{h.is_main ? t('clanDetails.mainHouseLabel') : t('clanDetails.outpost')} #{h.id} ({Math.round(h.x)}, {Math.round(h.y)})</span>
                  <span style={{ fontSize: 10.5, color: h.is_main ? '#e3b341' : '#8b949e', fontWeight: 600 }}>{h.is_main ? t('clanDetails.leaderResidence') : t('clanDetails.size', { n: h.size.toFixed(1) })}</span>
                </div>
              ))}
            </div>
          )}
          {data.culture && <div style={{ background: 'rgba(22,27,34,0.6)', padding: '6px 8px', borderRadius: 6, border: '1px solid #30363d', fontSize: 12, color: '#e6edf3' }}>🎭 {data.culture}</div>}
        </div>
      )}

      {activeTab === 'biography' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {loadingBio && !bioData ? (
            <p className="chip" style={{ margin: '8px 0' }}>{t('clanDetails.loadingBio') !== 'clanDetails.loadingBio' ? t('clanDetails.loadingBio') : 'Loading clan biography...'}</p>
          ) : bioData ? (
            <>
              {/* Lifespan & Status Banner */}
              <div style={{ background: '#161b22', border: '1px solid #30363d', borderRadius: 8, padding: '10px 12px', display: 'flex', flexDirection: 'column', gap: 6 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ fontSize: 13, fontWeight: 700, color: '#e6edf3' }}>
                    {bioData.lifespan?.active ? `🌟 ${t('clanDetails.activeClan') !== 'clanDetails.activeClan' ? t('clanDetails.activeClan') : 'Active Clan'}` : `💀 ${t('clanDetails.extinctClan') !== 'clanDetails.extinctClan' ? t('clanDetails.extinctClan') : 'Extinct Clan'}`}
                  </span>
                  <span className="chip" style={{ fontSize: 11, background: bioData.lifespan?.active ? 'rgba(63,185,80,0.15)' : 'rgba(248,81,73,0.15)', color: bioData.lifespan?.active ? '#3fb950' : '#f85149', fontWeight: 600 }}>
                    {bioData.lifespan?.active
                      ? `Day ${bioData.lifespan.founded_day} – Present`
                      : `Day ${bioData.lifespan?.founded_day ?? 0} – Day ${bioData.lifespan?.extinct_day ?? '?'}`}
                  </span>
                </div>
                {bioData.stats.extinction_cause && (
                  <div style={{ fontSize: 11, color: '#f85149' }}>
                    <b>{t('clanDetails.extinctionCause') !== 'clanDetails.extinctionCause' ? t('clanDetails.extinctionCause') : 'Extinction Cause'}:</b> {bioData.stats.extinction_cause}
                  </div>
                )}
              </div>

              {/* Clan Heritage Metrics Grid */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6 }}>
                <div className="chip" style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-start', padding: '6px 10px', gap: 2 }}>
                  <span style={{ fontSize: 10, color: '#8b949e', textTransform: 'uppercase' }}>{t('clanDetails.peakPop') !== 'clanDetails.peakPop' ? t('clanDetails.peakPop') : 'Peak Population'}</span>
                  <span style={{ fontSize: 14, fontWeight: 700, color: '#e6edf3' }}>{bioData.stats.peak_population ?? data.population} members</span>
                </div>
                <div className="chip" style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-start', padding: '6px 10px', gap: 2 }}>
                  <span style={{ fontSize: 10, color: '#8b949e', textTransform: 'uppercase' }}>{t('clanDetails.warfareRecord') !== 'clanDetails.warfareRecord' ? t('clanDetails.warfareRecord') : 'Warfare Record'}</span>
                  <span style={{ fontSize: 14, fontWeight: 700, color: '#ff7b72' }}>{bioData.stats.wars_fought} wars ({bioData.stats.wars_won} won)</span>
                </div>
                <div className="chip" style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-start', padding: '6px 10px', gap: 2 }}>
                  <span style={{ fontSize: 10, color: '#8b949e', textTransform: 'uppercase' }}>{t('clanDetails.schismsSplits') !== 'clanDetails.schismsSplits' ? t('clanDetails.schismsSplits') : 'Schisms & Splits'}</span>
                  <span style={{ fontSize: 14, fontWeight: 700, color: '#e3b341' }}>{bioData.stats.schisms}</span>
                </div>
                <div className="chip" style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-start', padding: '6px 10px', gap: 2 }}>
                  <span style={{ fontSize: 10, color: '#8b949e', textTransform: 'uppercase' }}>{t('clanDetails.templesFounded') !== 'clanDetails.templesFounded' ? t('clanDetails.templesFounded') : 'Temples Founded'}</span>
                  <span style={{ fontSize: 14, fontWeight: 700, color: '#58a6ff' }}>{bioData.stats.temples_built}</span>
                </div>
              </div>

              {/* Top Rival */}
              <div style={{ background: 'rgba(22,27,34,0.6)', border: '1px solid #30363d', borderRadius: 8, padding: '8px 10px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontSize: 11, color: '#8b949e', textTransform: 'uppercase' }}>{t('clanDetails.topRival') !== 'clanDetails.topRival' ? t('clanDetails.topRival') : 'Arch-Rival Clan'}</span>
                <span style={{ fontSize: 12, fontWeight: 700, color: bioData.stats.top_rival ? '#ff7b72' : '#8b949e' }}>
                  {bioData.stats.top_rival ? `⚔️ ${bioData.stats.top_rival}` : (t('clanDetails.noRival') !== 'clanDetails.noRival' ? t('clanDetails.noRival') : 'None recorded')}
                </span>
              </div>

              {/* Hall of Notables (Hero & Villain) */}
              <div style={{ background: '#161b22', border: '1px solid #30363d', borderRadius: 8, padding: '8px 10px', display: 'flex', flexDirection: 'column', gap: 6 }}>
                <div style={{ fontSize: 11, color: '#8b949e', textTransform: 'uppercase', letterSpacing: 0.5 }}>{t('clanDetails.hallOfNotables') !== 'clanDetails.hallOfNotables' ? t('clanDetails.hallOfNotables') : 'Hall of Notables'}</div>
                {bioData.notables?.hero ? (
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: 11 }}>
                    <span>🗡️ {t('clanDetails.champion') !== 'clanDetails.champion' ? t('clanDetails.champion') : 'Champion'}: <button type="button" onClick={() => onSelectCreature?.(bioData.notables!.hero!.id)} style={{ background: 'none', border: 'none', color: '#58a6ff', cursor: 'pointer', fontWeight: 600, padding: 0 }}>{bioData.notables.hero.personal_name} (#{bioData.notables.hero.id}) ↗</button></span>
                    <span className="chip" style={{ color: '#ff7b72', fontWeight: 600 }}>{bioData.notables.hero.kill_count} kills</span>
                  </div>
                ) : (
                  <div style={{ fontSize: 11, color: '#8b949e' }}>🗡️ {t('clanDetails.noChampion') !== 'clanDetails.noChampion' ? t('clanDetails.noChampion') : 'Champion: No celebrated warrior recorded'}</div>
                )}
                {bioData.notables?.villain ? (
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: 11 }}>
                    <span>🐍 {t('clanDetails.antagonist') !== 'clanDetails.antagonist' ? t('clanDetails.antagonist') : 'Antagonist'}: {bioData.notables.villain.id ? <button type="button" onClick={() => onSelectCreature?.(bioData.notables!.villain!.id)} style={{ background: 'none', border: 'none', color: '#f85149', cursor: 'pointer', fontWeight: 600, padding: 0 }}>{bioData.notables.villain.name} (#{bioData.notables.villain.id}) ↗</button> : bioData.notables.villain.name}</span>
                    <span className="chip" style={{ color: '#f85149', fontWeight: 600 }}>{bioData.notables.villain.deed}</span>
                  </div>
                ) : (
                  <div style={{ fontSize: 11, color: '#8b949e' }}>🐍 {t('clanDetails.noAntagonist') !== 'clanDetails.noAntagonist' ? t('clanDetails.noAntagonist') : 'Antagonist: No known traitor or assassin'}</div>
                )}
              </div>

              {/* AI Clan Saga Generator Button */}
              <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                <button
                  type="button"
                  onClick={generateClanStoryPrompt}
                  className="chip"
                  style={{
                    flex: 1,
                    background: storyCopied ? '#238636' : 'rgba(56, 139, 253, 0.15)',
                    borderColor: storyCopied ? '#2ea043' : 'rgba(56, 139, 253, 0.4)',
                    color: storyCopied ? '#fff' : '#58a6ff',
                    cursor: 'pointer',
                    fontSize: 11,
                    padding: '6px 10px',
                    fontWeight: 600,
                    textAlign: 'center',
                  }}
                  title={t('clanDetails.genStoryPromptTitle')}
                >
                  {storyCopied ? '✓ Prompt Copied to Clipboard!' : (t('clanDetails.genStoryPrompt') !== 'clanDetails.genStoryPrompt' ? t('clanDetails.genStoryPrompt') : '📖 Generate Clan Chronicle Story Prompt')}
                </button>
              </div>

              {/* Clan Chronicles Feed */}
              {bioData.recent_events && bioData.recent_events.length > 0 && (
                <div style={{ background: '#0d1117', border: '1px solid #21262d', borderRadius: 6, padding: '6px 8px' }}>
                  <div style={{ fontSize: 11, color: '#8b949e', textTransform: 'uppercase', marginBottom: 4 }}>{t('clanDetails.historicalEvents') !== 'clanDetails.historicalEvents' ? t('clanDetails.historicalEvents') : 'Historical Events'}</div>
                  <ul className="insp-events" style={{ maxHeight: 160, overflowY: 'auto', margin: 0, padding: 0 }}>
                    {bioData.recent_events.map((ev: any, i: number) => (
                      <li key={i} className={`ev-${ev.type}`} style={{ fontSize: 11.5 }}>
                        Day {Math.floor(ev.tick / 1200)} (tick {ev.tick}): <b>{ev.type}</b> {ev.payload?.a_name && ev.payload?.b_name ? `· ${ev.payload.a_name} vs ${ev.payload.b_name}` : ''} {ev.payload?.detail || ''}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </>
          ) : (
            <p className="chip" style={{ margin: '8px 0' }}>{t('clanDetails.noBioData') !== 'clanDetails.noBioData' ? t('clanDetails.noBioData') : 'No biography data available.'}</p>
          )}
        </div>
      )}

      {activeTab === 'roster' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          <div className="clan-filter-bar">
            {(['all','warriors','harvesters','elders','sick'] as const).map((k) => (
              <button
                key={k}
                type="button"
                className={`clan-filter-pill ${rosterFilter === k ? 'active' : ''}`}
                onClick={() => setRosterFilter(k)}
              >
                {k === 'all' ? `All (${data.members.length})` : k === 'warriors' ? `⚔ Warriors` : k === 'harvesters' ? `🌾 Harvesters` : k === 'elders' ? `👴 Elders` : `🤒 Sick`}
              </button>
            ))}
          </div>
          {filteredMembers.length === 0 ? (
            <p className="chip" style={{ margin: '4px 0' }}>{t('clanDetails.noMembers')}</p>
          ) : (
            <div className="clan-roster-list" style={{ display: 'flex', flexDirection: 'column', gap: 4, maxHeight: 320, overflowY: 'auto', minWidth: 0 }}>
              {filteredMembers.map((m) => (
                <button
                  key={m.id}
                  type="button"
                  className="kin-node"
                  onClick={() => onSelectCreature?.(m.id)}
                  style={{ textAlign: 'left', borderLeft: `3px solid ${data.color}`, display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8, padding: '6px 8px', cursor: 'pointer', background: '#161b22', borderRadius: 6, border: '1px solid #21262d', borderLeftColor: data.color, minWidth: 0, width: '100%' }}
                  title={t('clanDetails.inspectCreature', { id: m.id })}
                >
                  <span style={{ display: 'flex', flexDirection: 'column', gap: 1, minWidth: 0, flex: 1 }}>
                    <span style={{ fontWeight: 700, color: '#e6edf3', fontSize: 12, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}><b>{m.personal_name}</b> {m.glyph} #{m.id} · {m.caste} <span style={{ color: m.sex === 'female' ? '#ff9bce' : '#79c0ff', fontSize: 10 }}>{m.stage}</span></span>
                    <span style={{ fontSize: 10, color: '#8b949e', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{m.status ? `${m.status} · ` : ''}Age {m.age}/{Math.round(m.lifespan)} · {m.energy.toFixed(0)}⚡ {m.health.toFixed(0)}❤</span>
                  </span>
                  <span style={{ fontSize: 11, color: '#58a6ff', flex: 'none' }}>↗</span>
                </button>
              ))}
            </div>
          )}
        </div>
      )}

      {activeTab === 'warfare' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          <div style={{ background: '#161b22', border: '1px solid #30363d', borderRadius: 8, padding: '8px 10px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontWeight: 700, color: '#e6edf3', fontSize: 12 }}>{t('clanDetails.war', { wins: data.war_wins, losses: data.war_losses })} </span>
            <span style={{ fontSize: 11, color: data.war_wins > data.war_losses ? '#3fb950' : data.war_losses > data.war_wins ? '#f85149' : '#8b949e', fontWeight: 700 }}>
              {data.war_wins > data.war_losses ? '▲ Dominant' : data.war_losses > data.war_wins ? '▼ Struggling' : '— Balanced'}
            </span>
          </div>
          {data.specialization && (
            <div style={{ background: '#161b22', border: '1px solid #30363d', borderRadius: 8, padding: '8px 10px' }}>
              <div style={{ fontSize: 11, color: '#8b949e', textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 6 }}>{t('clanDetails.specialization')}</div>
              <Bar label="⚔ warrior" value={data.specialization.warrior * 100} max={100} color="#ff7b72" />
              <Bar label="🌾 farmer" value={data.specialization.farmer * 100} max={100} color="#3fb950" />
              <Bar label="🦴 scavenger" value={data.specialization.scavenger * 100} max={100} color="#8b949e" />
              {/* tri-wheel visual */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 6, marginTop: 8, textAlign: 'center', fontSize: 11 }}>
                {[
                  { k: 'warrior', v: data.specialization.warrior, icon: '⚔️', color: '#ff7b72' },
                  { k: 'farmer', v: data.specialization.farmer, icon: '🌾', color: '#3fb950' },
                  { k: 'scavenger', v: data.specialization.scavenger, icon: '🦴', color: '#8b949e' },
                ].map(o => (
                  <div key={o.k} style={{ background: `${o.color}12`, border: `1px solid ${o.color}44`, borderRadius: 8, padding: '6px 4px' }}>
                    <div style={{ fontSize: 16 }}>{o.icon}</div>
                    <div style={{ fontWeight: 700, color: o.color }}>{Math.round(o.v*100)}%</div>
                    <div style={{ color: '#8b949e', fontSize: 10, textTransform: 'uppercase' }}>{o.k}</div>
                  </div>
                ))}
              </div>
            </div>
          )}
          <div style={{ background: '#161b22', border: '1px solid #30363d', borderRadius: 8, padding: '8px 10px', fontSize: 12, color: '#8b949e' }}>
            <div style={{ fontWeight: 600, color: '#e6edf3', marginBottom: 4, fontSize: 11, textTransform: 'uppercase' }}>{t('clanDetails.diplomaticIntel')}</div>
            <p style={{ margin: 0 }}>Relations drift {data.territory_radius ? `@ ${data.territory_radius} radius` : ''} · War pairs and alliances tracked in Overview’s Geopolitics. Clan-specific Casus Belli (famine/territory/blood feud) surfaced via `war_declared` history.</p>
            {data.events.length > 0 && <div style={{ marginTop: 6, fontSize: 11 }}>{data.events.slice(0,3).map((ev: any,i:number)=>(<div key={i} style={{ padding: '2px 0', borderBottom: '1px solid #21262d' }}><b>{ev.type}</b> tick {ev.tick} {ev.cause?`· ${ev.cause}`:''}</div>))}</div>}
          </div>
        </div>
      )}

      {activeTab === 'annals' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {data.history && data.history.length > 0 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 5, maxHeight: 180, overflowY: 'auto' }}>
              {data.history.slice().reverse().map((h, i) => (
                <div key={i} style={{ background: 'rgba(22,27,34,0.7)', borderLeft: `3px solid ${h.event === 'founded' ? '#3fb950' : h.event === 'leader_change' ? '#e3b341' : '#58a6ff'}`, borderRadius: 4, padding: '4px 8px', fontSize: 11 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', color: '#8b949e', fontSize: 10 }}>
                    <span style={{ textTransform: 'capitalize', fontWeight: 600, color: '#c9d1d9' }}>
                      {h.event === 'founded' ? t('clanDetails.foundation') : h.event === 'leader_change' ? t('clanDetails.succession') : h.event === 'hq_relocated' ? t('clanDetails.hq') : h.event === 'war_declared' ? t('clanDetails.warEvent') : h.event === 'tribute_paid' ? t('clanDetails.treaty') : h.event}
                    </span>
                    <span>Day {h.day} · tick {h.tick}</span>
                  </div>
                  <div style={{ color: '#e6edf3', marginTop: 1 }}>{h.desc}</div>
                </div>
              ))}
            </div>
          )}
          <div style={{ background: '#0d1117', border: '1px solid #21262d', borderRadius: 6, padding: '6px 8px' }}>
            <div style={{ fontSize: 11, color: '#8b949e', textTransform: 'uppercase', marginBottom: 4 }}>{t('clanDetails.recentActivity')}</div>
            {data.events.length === 0 ? (
              <p className="chip" style={{ margin: '4px 0' }}>{t('clanDetails.noEvents')}</p>
            ) : (
              <ul className="insp-events" style={{ maxHeight: 120, overflowY: 'auto', margin: 0, padding: 0 }}>
                {data.events.slice().reverse().slice(0,8).map((ev: any, i: number) => (
                  <li key={i} className={`ev-${ev.type}`} style={{ fontSize: 11.5 }}>tick {ev.tick}: <b>{ev.type}</b> {ev.caste ? `· ${ev.caste}` : ''} {ev.cause ? `· ${ev.cause}` : ''}</li>
                ))}
              </ul>
            )}
          </div>
          <FullHistory clanId={data.id} color={data.color} />
        </div>
      )}
    </aside>
  )
}

function FullHistory({ clanId, color }: { clanId: number; color: string }) {
  const { t } = useI18n()
  const [open, setOpen] = useState(false)
  const [events, setEvents] = useState<any[]>([])
  const [page, setPage] = useState(0)
  const [hasMore, setHasMore] = useState(false)
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)

  const loadPage = (p: number, replace: boolean) => {
    setLoading(true)
    fetch(`/api/clans/${clanId}/history?page=${p}&size=50`)
      .then((r) => r.json())
      .then((d) => {
        setEvents((prev) => (replace ? d.events : [...prev, ...d.events]))
        setHasMore(d.has_more)
        setTotal(d.total)
        setPage(p)
        setLoading(false)
      })
      .catch(() => setLoading(false))
  }

  if (!open) {
    return (
      <button type="button" className="chip" style={{ margin: '4px 0', cursor: 'pointer', textAlign: 'left', borderLeft: `3px solid ${color}` }} onClick={() => { setOpen(true); loadPage(0, true) }}>
        {t('clanDetails.fullHistory')}
      </button>
    )
  }
  return (
    <div style={{ marginTop: 4 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
        <span className="chip">{t('clanDetails.fullHistoryTitle', { total })}</span>
        <button type="button" className="chip" style={{ cursor: 'pointer' }} onClick={() => setOpen(false)}>{t('clanDetails.close')}</button>
      </div>
      <ul className="insp-events" style={{ maxHeight: 220, overflowY: 'auto', margin: 0, padding: 0 }}>
        {events.map((ev: any, i: number) => (
          <li key={`${ev.tick}-${ev.entity_id}-${i}`} className={`ev-${ev.type}`} style={{ fontSize: 11.5 }}>tick {ev.tick}: <b>{ev.type}</b> {ev.caste ? `· ${ev.caste}` : ''} {ev.cause ? `· ${ev.cause}` : ''}</li>
        ))}
        {events.length === 0 && !loading && <li className="chip" style={{ fontSize: 11.5 }}>{t('clanDetails.noRecorded')}</li>}
      </ul>
      {hasMore && (
        <button type="button" className="chip" style={{ margin: '4px auto 0', display: 'block', cursor: 'pointer' }} disabled={loading} onClick={() => loadPage(page + 1, false)}>
          {loading ? t('clanDetails.loading') : t('clanDetails.loadOlder')}
        </button>
      )}
    </div>
  )
}
