import { memo, useMemo, useState } from 'react'
import type { StateMessage } from '../types'
import { CASTE_COLORS } from './CanvasRenderer'
import { totemEmoji } from '../totems'
import { useI18n } from '../i18n'

interface Props {
  state: StateMessage | null
  aliveHist?: number[]
  onSelectCreature: (id: number) => void
  onSelectClan: (id: number) => void
}

const AGE_ICONS: Record<string, string> = {
  'Golden Era': '🌟',
  'Golden Age': '🌟',
  'Ice Age': '❄️',
  'Plague Age': '☣️',
  'Chaos Era': '⚡',
  'Chaos Age': '⚡',
  'Age of Harmony': '🕊️',
  'Era of Harmony': '🕊️',
  'Age of Strife': '⚔️',
}
const SEASON_ICONS: Record<string, string> = {
  spring: '🌱',
  summer: '☀️',
  autumn: '🍂',
  winter: '❄️',
}
const WEATHER_ICONS: Record<string, string> = {
  clear: '☀️',
  rain: '🌧️',
  fog: '🌫️',
  storm: '⛈️',
}

function OverviewPanel({
  state,
  aliveHist = [],
  onSelectCreature,
  onSelectClan,
}: Props) {
  const { t } = useI18n()
  const [hoverCaste, setHoverCaste] = useState<string | null>(null)

  const trend = useMemo(() => {
    if (aliveHist.length < 5) return 'stable'
    const recent = aliveHist.slice(-5)
    const delta = recent[recent.length - 1] - recent[0]
    if (delta > 1) return 'growing'
    if (delta < -1) return 'declining'
    return 'stable'
  }, [aliveHist])

  const { casteData, menCount, womenCount } = useMemo(() => {
    if (!state) return { casteData: [], totalCreatures: 0, menCount: 0, womenCount: 0 }
    const pop = state.population ?? {}
    const entries = Object.entries(pop).filter(([k]) => k in CASTE_COLORS && pop[k] > 0)
    const total = entries.reduce((acc, [, v]) => acc + v, 0) || 1
    let women = pop['Woman'] ?? 0
    let men = total - women
    const items = entries
      .sort(([, a], [, b]) => b - a)
      .map(([caste, count]) => ({
        caste,
        count,
        pct: ((count / total) * 100).toFixed(1),
        pctNum: (count / total) * 100,
        color: CASTE_COLORS[caste] ?? '#8b949e',
      }))
    return { casteData: items, totalCreatures: total, menCount: men, womenCount: women }
  }, [state])

  const { healthyCount, sickCount, hungryCount, starvingCount, chilledCount } = useMemo(() => {
    if (!state) return { healthyCount: 0, sickCount: 0, hungryCount: 0, starvingCount: 0, chilledCount: 0 }
    const entities = state.entities ?? []
    const sick = state.infected_count ?? entities.filter((e) => e.infected).length
    const hungry = entities.filter((e) => e.status === 'hungry').length
    const starving = entities.filter((e) => e.status === 'starving').length
    const chilled = entities.filter((e) => (e.chill ?? 0) >= 12).length
    const healthy = Math.max(0, (state.creatures_alive ?? 0) - sick - starving)
    return { healthyCount: healthy, sickCount: sick, hungryCount: hungry, starvingCount: starving, chilledCount: chilled }
  }, [state])

  const mortalityList = useMemo(() => {
    if (!state?.dead_by_cause) return []
    const totalDead = Object.values(state.dead_by_cause).reduce((a, b) => a + b, 0) || 1
    return Object.entries(state.dead_by_cause)
      .filter(([, count]) => count > 0)
      .sort(([, a], [, b]) => b - a)
      .slice(0, 5)
      .map(([cause, count]) => {
        let icon = '💀'
        if (cause.includes('starv') || cause.includes('hunger')) icon = '🌾'
        else if (cause.includes('war') || cause.includes('combat')) icon = '⚔️'
        else if (cause.includes('disease') || cause.includes('plague') || cause.includes('infect')) icon = '☣️'
        else if (cause.includes('age')) icon = '⏳'
        else if (cause.includes('cold') || cause.includes('freeze')) icon = '❄️'
        else if (cause.includes('heat') || cause.includes('burn')) icon = '🔥'
        else if (cause.includes('predat')) icon = '🐺'
        else if (cause.includes('cannibal')) icon = '🍖'
        return { cause, count, icon, pct: ((count / totalDead) * 100).toFixed(0), pctNum: (count / totalDead) * 100 }
      })
  }, [state?.dead_by_cause])

  const { totalGrain, securityStatus } = useMemo(() => {
    if (!state) return { totalGrain: 0, securityStatus: 'famineRisk' }
    const clans = Object.values(state.clans ?? {})
    const grain = clans.reduce((acc, c) => acc + (c.granary ?? 0) + (c.larder ?? 0), 0)
    const alive = Math.max(1, state.creatures_alive ?? 1)
    const ratio = grain / alive
    let status = 'adequate'
    if (ratio >= 2.0) status = 'abundant'
    else if (ratio < 0.6) status = 'famineRisk'
    return { totalGrain: grain, securityStatus: status }
  }, [state])

  const { activeClansCount, hegemonClan, warPairsCount, alliedPairsCount, totalTemples, totalShrines } = useMemo(() => {
    if (!state) return { activeClansCount: 0, hegemonClan: null, warPairsCount: 0, alliedPairsCount: 0, totalTemples: 0, totalShrines: 0 }
    const clanEntries = Object.entries(state.clans ?? {})
    const activeCount = clanEntries.length
    let maxPop = -1
    let hegemon: any = null
    let temples = 0
    let shrines = 0
    for (const [id, c] of clanEntries) {
      const pop = c.population ?? 0
      if (pop > maxPop) { maxPop = pop; hegemon = { id: Number(id), ...c } }
      if ((c.shrine_level ?? 0) >= 2) temples++
      else if ((c.shrine_level ?? 0) >= 1) shrines++
    }
    const relations = state.relations ?? []
    let wars = 0
    let allies = 0
    for (const r of relations) {
      if (r.score < -20) wars++
      else if (r.score > 20) allies++
    }
    return {
      activeClansCount: activeCount,
      hegemonClan: hegemon && maxPop > 0 ? { ...hegemon, pct: (((hegemon.population ?? 0) / Math.max(1, state.creatures_alive ?? 1)) * 100).toFixed(0) } : null,
      warPairsCount: wars, alliedPairsCount: allies, totalTemples: temples, totalShrines: shrines,
    }
  }, [state])

  const { eldestCreature, topChief } = useMemo(() => {
    if (!state?.entities) return { eldestCreature: null, topChief: null }
    let oldest: any = null
    let maxAge = -1
    for (const e of state.entities) {
      if (e.kind !== 'creature') continue
      const a = e.age ?? 0
      if (a > maxAge) { maxAge = a; oldest = e }
    }
    let bestLeader: any = null
    let maxWins = -1
    for (const [clanId, c] of Object.entries(state.clans ?? {})) {
      if (c.leader_id && (c.war_wins ?? 0) > maxWins) {
        maxWins = c.war_wins ?? 0
        bestLeader = { id: c.leader_id, clanName: c.name, clanId: Number(clanId), wins: c.war_wins ?? 0 }
      }
    }
    return { eldestCreature: oldest, topChief: bestLeader }
  }, [state])

  if (!state) {
    return <div style={{ padding: '12px 8px', textAlign: 'center', color: '#8b949e', fontSize: 12 }}>{t('app.overview.hint')}</div>
  }

  const ageName = state.age || 'Golden Era'
  const ageIcon = AGE_ICONS[ageName] ?? '🌟'
  const seasonIcon = SEASON_ICONS[state.season] ?? '🌱'
  const weatherIcon = WEATHER_ICONS[state.weather] ?? '☀️'
  const ageDay = state.age_day ?? ((state.day % 10) + 1)
  const ageTotalDays = state.age_total_days ?? 10
  const agePct = Math.min(100, Math.max(0, (ageDay / ageTotalDays) * 100))
  // season progression within age (approx: day within 4-season cycle)
  const seasonOrder: Record<string, number> = { spring: 0, summer: 1, autumn: 2, winter: 3 }
  const seasonIdx = seasonOrder[state.season] ?? 0

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8, fontSize: 12, color: '#c9d1d9', minWidth: 0 }}>
      {/* 1. Unified Era & Season progress strip — single top strip */}
      <div className="overview-progress-strip" style={{ minWidth: 0 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', marginBottom: 5, gap: 4 }}>
          <span style={{ fontWeight: 700, color: '#e6edf3', display: 'flex', alignItems: 'center', gap: 4, fontSize: 12, minWidth: 0, flex: '1 1 auto', overflow: 'hidden' }}>
            <span style={{ flex: 'none' }}>{ageIcon}</span>
            <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{ageName}</span>
            <span style={{ fontWeight: 400, color: '#8b949e', fontSize: 11, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>· {seasonIcon} {state.season.toUpperCase()} · Day {state.day} · {weatherIcon} {state.weather}</span>
          </span>
          <span style={{ fontSize: 10, color: '#8b949e', whiteSpace: 'nowrap', flex: 'none' }}>Day {ageDay}/{ageTotalDays}</span>
        </div>
        {/* single progress: era fill + season marker */}
        <div style={{ position: 'relative', background: '#21262d', height: 6, borderRadius: 3, overflow: 'hidden' }}>
          <div style={{ width: `${agePct}%`, height: '100%', background: 'linear-gradient(90deg,#58a6ff,#79c0ff)', transition: 'width 0.3s' }} />
          {/* season tick marks */}
          <div style={{ position: 'absolute', inset: 0, display: 'flex' }}>
            {[0, 1, 2, 3].map((i) => (
              <div key={i} style={{ flex: 1, borderLeft: i === 0 ? 'none' : '1px solid rgba(13,17,23,0.6)' }} title={['Spring','Summer','Autumn','Winter'][i]} />
            ))}
          </div>
          <div style={{ position: 'absolute', left: `${(seasonIdx / 4) * 100}%`, width: '25%', height: '100%', background: 'rgba(227,179,65,0.18)', pointerEvents: 'none' }} title={`${state.season} season`} />
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: '#484f58', marginTop: 2 }}>
          <span>Era progress {agePct.toFixed(0)}%</span>
          <span style={{ color: seasonIdx === 3 ? '#79c0ff' : '#8b949e' }}>{state.season} {seasonIdx === 3 ? '· winter chill' : ''}</span>
        </div>
      </div>

      {/* 2. Caste spectrum — interactive proportional bar */}
      <div style={{ background: '#161b22', border: '1px solid #30363d', borderRadius: 8, padding: '7px 8px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 5 }}>
          <span style={{ fontWeight: 700, color: '#e6edf3', fontSize: 11, letterSpacing: '0.04em', textTransform: 'uppercase' }}>{t('app.overview.demographicsTitle')}</span>
          <span style={{ fontSize: 10.5, fontWeight: 700, color: trend === 'growing' ? '#3fb950' : trend === 'declining' ? '#f85149' : '#8b949e', background: '#21262d', padding: '1px 6px', borderRadius: 10 }}>
            {trend === 'growing' ? `▲ ${t('app.overview.growing')}` : trend === 'declining' ? `▼ ${t('app.overview.declining')}` : `● ${t('app.overview.stable')}`}
          </span>
        </div>
        <div className="caste-spectrum" style={{ marginBottom: hoverCaste ? 2 : 6 }}>
          {casteData.map((c) => (
            <div
              key={c.caste}
              className="caste-spectrum-seg"
              style={{ width: `${c.pctNum}%`, background: c.color, opacity: hoverCaste && hoverCaste !== c.caste ? 0.45 : 1 }}
              title={`${c.caste}: ${c.count} (${c.pct}%)`}
              onMouseEnter={() => setHoverCaste(c.caste)}
              onMouseLeave={() => setHoverCaste(null)}
            />
          ))}
        </div>
        {hoverCaste && (() => {
          const h = casteData.find(c => c.caste === hoverCaste)
          return h ? <div style={{ fontSize: 10, color: '#8b949e', marginBottom: 4 }}><span style={{ display: 'inline-block', width: 8, height: 8, borderRadius: '50%', background: h.color, marginRight: 4, verticalAlign: 'middle' }} />{h.caste}: <b style={{ color: '#e6edf3' }}>{h.count}</b> ({h.pct}%)</div> : null
        })()}
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
          {casteData.map((c) => (
            <span key={c.caste} className="chip" style={{ fontSize: 10.5, background: hoverCaste === c.caste ? '#21262d' : '#161b22', border: `1px solid ${hoverCaste === c.caste ? c.color : '#30363d'}`, padding: '2px 6px', display: 'inline-flex', alignItems: 'center', gap: 4, cursor: 'default' }} title={`${c.caste}: ${c.count} alive (${c.pct}%)`} onMouseEnter={() => setHoverCaste(c.caste)} onMouseLeave={() => setHoverCaste(null)}>
              <span style={{ width: 6, height: 6, borderRadius: '50%', background: c.color }} />
              <span>{c.caste}</span>
              <b>{c.count}</b>
            </span>
          ))}
        </div>
      </div>

      {/* 3. Compact 2-row vitals pill strip */}
      <div style={{ background: '#161b22', border: '1px solid #30363d', borderRadius: 8, padding: '6px 8px' }}>
        <div style={{ fontSize: 10, fontWeight: 700, color: '#8b949e', letterSpacing: '0.06em', textTransform: 'uppercase', marginBottom: 5 }}>{t('overviewPanel.vitals')}</div>
        <div className="vitals-strip" style={{ marginBottom: 4 }}>
          <span className="vitals-pill" title={t('overviewPanel.vitalsTooltips.male')}>♂ {t('app.overview.men')} <b style={{ color: '#79c0ff' }}>{menCount}</b></span>
          <span className="vitals-pill" title={t('overviewPanel.vitalsTooltips.female')}>♀ {t('app.overview.women')} <b style={{ color: '#ff9bce' }}>{womenCount}</b></span>
          <span className="vitals-pill" title={t('overviewPanel.vitalsTooltips.healthy')}>✓ {t('app.overview.healthy')} <b style={{ color: '#3fb950' }}>{healthyCount}</b></span>
          <span className="vitals-pill" style={{ borderColor: sickCount > 0 ? '#238636' : undefined, color: sickCount > 0 ? '#3fb950' : undefined }} title={t('overviewPanel.vitalsTooltips.infected')}>☣ {t('app.overview.sick')} <b>{sickCount}</b></span>
        </div>
        <div className="vitals-strip">
          <span className="vitals-pill" style={{ color: hungryCount + starvingCount > 0 ? '#d29922' : undefined }} title={t('overviewPanel.vitalsTooltips.hungryStarving')}>🍖 {t('app.overview.hungry')} <b>{hungryCount + starvingCount}</b>{starvingCount > 0 ? ` · ⚠ ${starvingCount}` : ''}</span>
          <span className="vitals-pill" style={{ color: chilledCount > 0 ? '#79c0ff' : undefined }} title={t('overviewPanel.vitalsTooltips.chilled')}>🥶 {t('app.overview.chilled')} <b>{chilledCount}</b></span>
          <span className="vitals-pill" title={t('overviewPanel.vitalsTooltips.totalAlive')}>💚 <b>{state.creatures_alive}</b> {t('app.hud.alive').toLowerCase()}</span>
          <span className="vitals-pill" title={t('overviewPanel.vitalsTooltips.totalDead')}>💀 <b>{state.creatures_dead}</b> {t('app.hud.dead').toLowerCase()}</span>
        </div>
      </div>

      {/* 4. Ranked mortality cause bars */}
      <div style={{ background: '#161b22', border: '1px solid #30363d', borderRadius: 8, padding: '7px 8px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 5 }}>
          <span style={{ fontWeight: 700, color: '#e6edf3', fontSize: 11, letterSpacing: '0.04em', textTransform: 'uppercase' }}>{t('app.overview.mortalityTitle')}</span>
          <span style={{ fontSize: 11, color: '#8b949e' }}>{state.creatures_dead} {t('history.stats.fallen')}</span>
        </div>
        {mortalityList.length === 0 ? (
          <div style={{ fontSize: 11, color: '#8b949e', fontStyle: 'italic' }}>{t('app.overview.noDeaths')}</div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
            {mortalityList.map((m, idx) => (
              <div key={m.cause} style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 11 }}>
                <span style={{ fontSize: 10, color: '#484f58', minWidth: 12, textAlign: 'right' }}>{idx + 1}</span>
                <span style={{ minWidth: 14 }}>{m.icon}</span>
                <span style={{ flex: 1, textTransform: 'capitalize', color: '#c9d1d9', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{m.cause}</span>
                <div className="mortality-bar-track" style={{ width: 56, flex: 'none' }}>
                  <div className="mortality-bar-fill" style={{ width: `${m.pctNum}%`, background: idx === 0 ? '#f85149' : idx === 1 ? '#d29922' : '#8b949e' }} />
                </div>
                <span style={{ minWidth: 46, textAlign: 'right', color: '#8b949e', fontSize: 10.5 }}><b style={{ color: '#e6edf3' }}>{m.count}</b> {m.pct}%</span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* 5. Granaries & Food Security — compact */}
      <div style={{ background: '#161b22', border: '1px solid #30363d', borderRadius: 8, padding: '7px 8px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 3 }}>
          <span style={{ fontWeight: 700, color: '#e6edf3', fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.04em' }}>{t('app.overview.economyTitle')}</span>
          <span style={{ fontSize: 11, color: '#e3b341', fontWeight: 700 }}>🌾 {totalGrain}</span>
        </div>
        <div style={{ fontSize: 11, marginBottom: 5 }}>
          {securityStatus === 'abundant' && <span style={{ color: '#3fb950' }}>{t('app.overview.abundant')}</span>}
          {securityStatus === 'adequate' && <span style={{ color: '#d29922' }}>{t('app.overview.adequate')}</span>}
          {securityStatus === 'famineRisk' && <span style={{ color: '#f85149' }}>{t('app.overview.famineRisk')}</span>}
        </div>
        <div style={{ display: 'flex', gap: 4, fontSize: 11, color: '#8b949e' }}>
          <span className="chip" style={{ background: '#21262d', padding: '2px 6px', fontSize: 11 }}>🏠 {t('app.overview.housesCount', { count: state.population?.House ?? 0 })}</span>
          <span className="chip" style={{ background: '#21262d', padding: '2px 6px', fontSize: 11 }}>🌱 {t('app.overview.wildFood', { count: state.population?.Food ?? 0 })}</span>
        </div>
      </div>

      {/* 6. Geopolitics */}
      <div style={{ background: '#161b22', border: '1px solid #30363d', borderRadius: 8, padding: '7px 8px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 3 }}>
          <span style={{ fontWeight: 700, color: '#e6edf3', fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.04em' }}>{t('app.overview.geoTitle')}</span>
          <span style={{ fontSize: 11, color: '#8b949e' }}>{t('app.overview.activeClans', { count: activeClansCount })}</span>
        </div>
        {hegemonClan && (
          <div style={{ fontSize: 11, marginBottom: 4, display: 'flex', alignItems: 'center', gap: 4 }}>
            <span style={{ color: '#8b949e' }}>{t('app.overview.hegemon', { name: hegemonClan.name, pct: hegemonClan.pct })}</span>
            {hegemonClan.totem && <span>{totemEmoji(hegemonClan.totem)}</span>}
          </div>
        )}
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, fontSize: 11, color: '#8b949e' }}>
          <span className="chip" style={{ background: '#21262d', padding: '2px 6px' }}>⚔️ {warPairsCount} wars · 🕊️ {alliedPairsCount} allies</span>
          {(totalTemples > 0 || totalShrines > 0) && (
            <span className="chip" style={{ background: '#21262d', padding: '2px 6px', color: '#bc8cff' }}>🏛️ {t('app.overview.templesAndShrines', { temples: totalTemples, shrines: totalShrines })}</span>
          )}
        </div>
      </div>

      {/* 7. Prominent Living Figures */}
      {(eldestCreature || topChief) && (
        <div style={{ background: '#161b22', border: '1px solid #30363d', borderRadius: 8, padding: '7px 8px', minWidth: 0 }}>
          <div style={{ fontWeight: 700, color: '#e6edf3', marginBottom: 4, fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.04em' }}>{t('app.overview.notableTitle')}</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: 11, minWidth: 0 }}>
            {eldestCreature && (
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 6, minWidth: 0 }}>
                <span style={{ color: '#8b949e', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: '1 1 auto', minWidth: 0 }}>⏳ {t('app.overview.eldest', { name: eldestCreature.personal_name || eldestCreature.caste || 'Citizen', id: eldestCreature.id, age: eldestCreature.age ?? 0, gen: eldestCreature.generation ?? 0 })}</span>
                <button onClick={() => onSelectCreature(eldestCreature.id)} style={{ background: 'transparent', border: 'none', color: '#58a6ff', cursor: 'pointer', fontSize: 11, padding: '4px 2px', textDecoration: 'underline', flex: 'none' }}>{t('overviewPanel.inspect')}</button>
              </div>
            )}
            {topChief && (
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 6, minWidth: 0 }}>
                <span style={{ color: '#8b949e', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: '1 1 auto', minWidth: 0 }}>👑 {t('app.overview.topChief', { id: topChief.id, clan: topChief.clanName, wins: topChief.wins })}</span>
                <button onClick={() => onSelectClan(topChief.clanId)} style={{ background: 'transparent', border: 'none', color: '#58a6ff', cursor: 'pointer', fontSize: 11, padding: '4px 2px', textDecoration: 'underline', flex: 'none' }}>{t('overviewPanel.clan')}</button>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

export default memo(OverviewPanel)
