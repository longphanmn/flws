import { useEffect, useState, useMemo } from 'react'
import type { StateMessage } from '../types'
import { totemEmoji } from '../totems'
import { useI18n } from '../i18n'

interface Props {
  state: StateMessage | null
  onReset: () => void
  onClose: () => void
  onOpenWorldHistory?: () => void
}

function causeLabel(cause: string, t: any): { label: string; icon: string; color: string } {
  const c = cause.toLowerCase()
  if (c.includes('starv') || c.includes('famin') || c.includes('food')) {
    return { label: t('worldEnd.causes.starvation') || 'Famine & Starvation', icon: '🌾', color: '#e3b341' }
  }
  if (c.includes('predat') || c.includes('hunt') || c.includes('kill')) {
    return { label: t('worldEnd.causes.predation') || 'Predation', icon: '🐺', color: '#ff7b72' }
  }
  if (c.includes('plague') || c.includes('disease') || c.includes('sick')) {
    return { label: t('worldEnd.causes.plague') || 'Plague & Outbreak', icon: '☣️', color: '#d29922' }
  }
  if (c.includes('war') || c.includes('battle') || c.includes('clash') || c.includes('combat')) {
    return { label: t('worldEnd.causes.war') || 'Warfare & Strife', icon: '⚔️', color: '#f85149' }
  }
  if (c.includes('age') || c.includes('old')) {
    return { label: t('worldEnd.causes.oldAge') || 'Old Age', icon: '⏳', color: '#8b949e' }
  }
  if (c.includes('disaster') || c.includes('fire') || c.includes('quake') || c.includes('cataclysm')) {
    return { label: t('worldEnd.causes.disaster') || 'Natural Cataclysm', icon: '🌋', color: '#ff7b72' }
  }
  if (c.includes('cold') || c.includes('freeze') || c.includes('winter') || c.includes('frost')) {
    return { label: t('worldEnd.causes.cold') || 'Severe Frost', icon: '❄️', color: '#58a6ff' }
  }
  return { label: cause, icon: '💀', color: '#8b949e' }
}

export default function WorldEndSummary({
  state,
  onReset,
  onClose,
  onOpenWorldHistory,
}: Props) {
  const { t } = useI18n()
  const [clans, setClans] = useState<any[]>([])
  const [history, setHistory] = useState<any[]>([])
  const [summary, setSummary] = useState<any>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let active = true
    Promise.all([
      fetch('/api/clans?include_extinct=true').then(r => r.json()).catch(() => ({ clans: [] })),
      fetch('/api/history?limit=1000').then(r => r.json()).catch(() => ({ events: [] })),
      fetch('/api/history/summary').then(r => r.json()).catch(() => null),
    ]).then(([clanData, histData, sumData]) => {
      if (!active) return
      setClans(clanData.clans ?? [])
      setHistory(histData.events ?? [])
      setSummary(sumData)
      setLoading(false)
    })
    return () => { active = false }
  }, [])

  if (!state || state.creatures_alive !== 0) return null

  const totalDays = (state.tick / 1200).toFixed(1)
  const deadByCause = state.dead_by_cause ?? {}

  // 1. Extinction Cause breakdown
  const causeBreakdown = useMemo(() => {
    const totalDead = state.creatures_dead || 1
    const entries = Object.entries(deadByCause)
      .map(([cause, count]) => {
        const num = Number(count)
        const meta = causeLabel(cause, t)
        return {
          cause,
          count: num,
          pct: Math.round((num / totalDead) * 100),
          ...meta,
        }
      })
      .sort((a, b) => b.count - a.count)
    return entries
  }, [deadByCause, state.creatures_dead, t])

  const primaryCause = causeBreakdown[0] ?? null

  // 2. Chronicle Legends & Records
  const records = useMemo(() => {
    const clanMap: Record<number, any> = {}
    for (const c of clans) {
      clanMap[c.id] = c
    }

    const lastSeenTick: Record<number, number> = {}
    const memberBirthCounts: Record<number, number> = {}
    const dayCasualties: Record<number, number> = {}

    let finalSoul: {
      name: string
      caste?: string
      clanId?: number
      clanName?: string
      clanColor?: string
      cause?: string
      day: number
      tick: number
    } | null = null

    for (const ev of history) {
      const p = (ev.payload ?? {}) as Record<string, any>
      const tick = ev.tick ?? 0
      const d = Math.floor(tick / 1200)

      // Attribute event to clans
      const touchedClans = new Set<number>()
      if (p.clan_id != null) touchedClans.add(Number(p.clan_id))
      if (p.a != null) touchedClans.add(Number(p.a))
      if (p.b != null) touchedClans.add(Number(p.b))
      if (p.from != null) touchedClans.add(Number(p.from))
      if (p.to != null) touchedClans.add(Number(p.to))
      if (p.winner_clan != null) touchedClans.add(Number(p.winner_clan))
      if (p.loser_clan != null) touchedClans.add(Number(p.loser_clan))
      if (p.invader_clan != null) touchedClans.add(Number(p.invader_clan))
      if (p.victim_clan != null) touchedClans.add(Number(p.victim_clan))
      if (p.parent != null) touchedClans.add(Number(p.parent))
      if (p.new_clan != null) touchedClans.add(Number(p.new_clan))
      if (ev.type === 'clan_extinction' && ev.entity_id != null) touchedClans.add(Number(ev.entity_id))

      for (const cid of touchedClans) {
        lastSeenTick[cid] = Math.max(lastSeenTick[cid] ?? 0, tick)
      }

      if (ev.type === 'birth' && p.clan_id != null) {
        const cid = Number(p.clan_id)
        memberBirthCounts[cid] = (memberBirthCounts[cid] ?? 0) + 1
      }

      if (ev.type === 'death' || (ev.type === 'war' && p.lethal)) {
        dayCasualties[d] = (dayCasualties[d] ?? 0) + 1
      }

      if (ev.type === 'death') {
        if (!finalSoul || tick >= finalSoul.tick) {
          const cid = p.clan_id ?? p.clan
          const clanInfo = cid != null ? clanMap[Number(cid)] : null
          finalSoul = {
            name: p.personal_name ? `${p.personal_name} #${ev.entity_id}` : `#${ev.entity_id}`,
            caste: ev.caste,
            clanId: cid != null ? Number(cid) : undefined,
            clanName: p.clan_name ?? clanInfo?.name ?? (cid ? `Clan #${cid}` : 'Nomad'),
            clanColor: clanInfo?.color ?? '#8b949e',
            cause: ev.cause ?? p.cause ?? 'unknown',
            day: d,
            tick,
          }
        }
      }
    }

    // Longest Surviving Clan
    let longestClan: { clan: any; durationDays: number; startDay: number; endDay: number } | null = null
    for (const c of clans) {
      const bornTick = c.born_tick ?? 0
      const lastTick = lastSeenTick[c.id] ?? state.tick
      const duration = Math.max(0, lastTick - bornTick)
      if (!longestClan || duration > (longestClan.durationDays * 1200)) {
        longestClan = {
          clan: c,
          durationDays: Number((duration / 1200).toFixed(1)),
          startDay: Math.floor(bornTick / 1200),
          endDay: Math.floor(lastTick / 1200),
        }
      }
    }

    // Biggest Clan by member history / peak population
    const sortedByMembers = [...clans].sort((a, b) => {
      const aTotal = Math.max(memberBirthCounts[a.id] ?? 0, (a.dead_count ?? 0) + (a.population ?? 0))
      const bTotal = Math.max(memberBirthCounts[b.id] ?? 0, (b.dead_count ?? 0) + (b.population ?? 0))
      return bTotal - aTotal
    })
    const biggestClan = sortedByMembers[0] ? {
      clan: sortedByMembers[0],
      totalMembers: Math.max(
        memberBirthCounts[sortedByMembers[0].id] ?? 0,
        (sortedByMembers[0].dead_count ?? 0) + (sortedByMembers[0].population ?? 0),
      ),
    } : null

    // Most Won Clan
    const sortedByWars = [...clans].sort((a, b) => (b.war_wins ?? 0) - (a.war_wins ?? 0))
    const topWarClan = (sortedByWars[0] && (sortedByWars[0].war_wins ?? 0) > 0) ? sortedByWars[0] : null

    // Deadliest Day
    let deadliestDay: { day: number; casualties: number } | null = null
    if (summary?.days?.length) {
      for (const d of summary.days) {
        const cas = d.casualties ?? 0
        if (!deadliestDay || cas > deadliestDay.casualties) {
          deadliestDay = { day: d.day, casualties: cas }
        }
      }
    }
    if (!deadliestDay) {
      for (const [dStr, cas] of Object.entries(dayCasualties)) {
        const d = Number(dStr)
        if (!deadliestDay || cas > deadliestDay.casualties) {
          deadliestDay = { day: d, casualties: cas }
        }
      }
    }

    return {
      longestClan,
      biggestClan,
      topWarClan,
      finalSoul,
      deadliestDay,
    }
  }, [clans, history, summary, state.tick])

  return (
    <div className="world-end-backdrop" onClick={onClose}>
      <div className="world-end-panel" onClick={e => e.stopPropagation()}>
        <header className="god-head" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <h2 style={{ color: '#f85149', margin: 0, fontSize: 16, display: 'flex', alignItems: 'center', gap: 6 }}>
            <span>☠</span>
            <span>{t('worldEnd.title').replace(/^[☠💀]\s*/, '')}</span>
          </h2>
          <button className="god-close" onClick={onClose} aria-label={t('worldEnd.close')}>×</button>
        </header>

        {/* Memorial Hero Banner */}
        <div style={{ textAlign: 'center', padding: '12px 0 10px', borderBottom: '1px solid #21262d', marginBottom: 12 }}>
          <div style={{ fontSize: 44, marginBottom: 4, lineHeight: 1 }}>💀</div>
          <div style={{ fontSize: 18, color: '#e6edf3', fontWeight: 700 }}>{t('worldEnd.allPerished')}</div>
          <div className="chip" style={{ marginTop: 6, fontSize: 11, background: '#161b22', borderColor: '#30363d' }}>
            {t('worldEnd.tick', { tick: state.tick, days: totalDays, day: state.day, season: state.season, seed: state.seed })}
          </div>
        </div>

        {/* Extinction Causes & Demographics Breakdown */}
        <div className="world-end-cause-breakdown">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 6 }}>
            <span style={{ fontSize: 11, color: '#8b949e', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
              {t('worldEnd.extinctionBreakdown') || 'Mortality & Causes Breakdown'}
            </span>
            {primaryCause && (
              <span style={{ fontSize: 11, color: primaryCause.color, fontWeight: 700 }}>
                {primaryCause.icon} {primaryCause.label} ({primaryCause.pct}%)
              </span>
            )}
          </div>

          {/* Color-coded proportional mortality progress bar */}
          {causeBreakdown.length > 0 && (
            <div className="world-end-cause-bar-track">
              {causeBreakdown.map((c) => (
                <div
                  key={c.cause}
                  className="world-end-cause-bar-seg"
                  style={{ width: `${Math.max(2, c.pct)}%`, background: c.color }}
                  title={`${c.label}: ${c.count} (${c.pct}%)`}
                />
              ))}
            </div>
          )}

          <div className="world-end-cause-chips">
            {causeBreakdown.map((c) => (
              <span
                key={c.cause}
                className="chip"
                style={{
                  fontSize: 10.5,
                  padding: '2px 7px',
                  background: 'rgba(22, 27, 34, 0.8)',
                  borderColor: '#30363d',
                  color: '#e6edf3',
                }}
              >
                <span>{c.icon}</span>
                <span>{c.label}: <b>{c.count}</b></span>
              </span>
            ))}
          </div>
        </div>

        {/* Chronicle Records & Legends Grid */}
        <h3 style={{ fontSize: 13, color: '#e6edf3', margin: '14px 0 8px', display: 'flex', alignItems: 'center', gap: 6 }}>
          <span>📜</span>
          <span>{t('worldEnd.chronicleLegends') || 'Chronicle Records & Legends'}</span>
        </h3>

        <div className="world-end-records-grid">
          {/* 1. Longest Surviving Clan */}
          <div className="world-end-card">
            <div className="world-end-card-head">
              <span>{t('worldEnd.longestSurviving') || '⏳ Longest Surviving Clan'}</span>
              <span style={{ color: '#58a6ff' }}>{records.longestClan ? `${records.longestClan.durationDays}d` : '—'}</span>
            </div>
            <div className="world-end-card-val">
              {records.longestClan ? (
                <>
                  <span style={{ width: 8, height: 8, borderRadius: '50%', background: records.longestClan.clan.color, display: 'inline-block' }} />
                  <span>{records.longestClan.clan.name}</span>
                  {records.longestClan.clan.totem && <span style={{ fontSize: 13 }}>{totemEmoji(records.longestClan.clan.totem)}</span>}
                </>
              ) : (
                <span style={{ color: '#8b949e' }}>—</span>
              )}
            </div>
            <div className="world-end-card-sub">
              {records.longestClan ? (
                t('worldEnd.longestSurvivingDesc', {
                  days: records.longestClan.durationDays,
                  start: records.longestClan.startDay,
                  end: records.longestClan.endDay,
                }) || `Endured ${records.longestClan.durationDays} days (Day ${records.longestClan.startDay} → Day ${records.longestClan.endDay})`
              ) : (
                t('worldEnd.noClans')
              )}
            </div>
          </div>

          {/* 2. Biggest Clan / Greatest Realm */}
          <div className="world-end-card">
            <div className="world-end-card-head">
              <span>{t('worldEnd.biggestClan') || '👑 Greatest Realm'}</span>
              <span style={{ color: '#e3b341' }}>{records.biggestClan ? `${records.biggestClan.totalMembers} souls` : '—'}</span>
            </div>
            <div className="world-end-card-val">
              {records.biggestClan ? (
                <>
                  <span style={{ width: 8, height: 8, borderRadius: '50%', background: records.biggestClan.clan.color, display: 'inline-block' }} />
                  <span>{records.biggestClan.clan.name}</span>
                  {records.biggestClan.clan.totem && <span style={{ fontSize: 13 }}>{totemEmoji(records.biggestClan.clan.totem)}</span>}
                </>
              ) : (
                <span style={{ color: '#8b949e' }}>—</span>
              )}
            </div>
            <div className="world-end-card-sub">
              {records.biggestClan ? (
                t('worldEnd.biggestClanDesc', { count: records.biggestClan.totalMembers }) || `${records.biggestClan.totalMembers} total members recorded`
              ) : (
                t('worldEnd.noClans')
              )}
            </div>
          </div>

          {/* 3. Most Won Clan / Sovereign of War */}
          <div className="world-end-card">
            <div className="world-end-card-head">
              <span>{t('worldEnd.mostWonClan') || '⚔️ Sovereign of War'}</span>
              <span style={{ color: '#ff7b72' }}>{records.topWarClan ? `${records.topWarClan.war_wins}W` : '0W'}</span>
            </div>
            <div className="world-end-card-val">
              {records.topWarClan ? (
                <>
                  <span style={{ width: 8, height: 8, borderRadius: '50%', background: records.topWarClan.color, display: 'inline-block' }} />
                  <span>{records.topWarClan.name}</span>
                  {records.topWarClan.totem && <span style={{ fontSize: 13 }}>{totemEmoji(records.topWarClan.totem)}</span>}
                </>
              ) : (
                <span style={{ color: '#8b949e' }}>{t('worldEnd.noVictories')}</span>
              )}
            </div>
            <div className="world-end-card-sub">
              {records.topWarClan ? (
                t('worldEnd.mostWonDesc', { wins: records.topWarClan.war_wins, losses: records.topWarClan.war_losses ?? 0 }) ||
                `${records.topWarClan.war_wins} victories (${records.topWarClan.war_wins}W / ${records.topWarClan.war_losses ?? 0}L)`
              ) : (
                t('worldEnd.peaceReigned')
              )}
            </div>
          </div>

          {/* 4. Final Living Soul */}
          <div className="world-end-card">
            <div className="world-end-card-head">
              <span>{t('worldEnd.lastStanding') || '🕯️ Final Living Soul'}</span>
              <span style={{ color: '#d2a8ff' }}>{records.finalSoul ? `Day ${records.finalSoul.day}` : '—'}</span>
            </div>
            <div className="world-end-card-val">
              {records.finalSoul ? (
                <>
                  {records.finalSoul.clanColor && (
                    <span style={{ width: 8, height: 8, borderRadius: '50%', background: records.finalSoul.clanColor, display: 'inline-block' }} />
                  )}
                  <span>{records.finalSoul.name}</span>
                </>
              ) : (
                <span style={{ color: '#8b949e' }}>—</span>
              )}
            </div>
            <div className="world-end-card-sub">
              {records.finalSoul ? (
                t('worldEnd.lastStandingDesc', {
                  name: records.finalSoul.name,
                  clan: records.finalSoul.clanName,
                  day: records.finalSoul.day,
                  cause: records.finalSoul.cause,
                }) || `${records.finalSoul.name} (${records.finalSoul.clanName}) perished on Day ${records.finalSoul.day} of ${records.finalSoul.cause}`
              ) : (
                'All perished in silence'
              )}
            </div>
          </div>
        </div>

        {/* Clans of Flatland Table */}
        <h3 style={{ fontSize: 13, color: '#e6edf3', margin: '14px 0 6px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span>{t('worldEnd.clansAtEnd', { count: clans.length })}</span>
          <span style={{ fontSize: 10.5, color: '#8b949e', fontWeight: 500 }}>
            {clans.length > 0 ? `${clans.length} realms recorded` : ''}
          </span>
        </h3>

        {clans.length === 0 ? (
          <p className="chip" style={{ width: '100%', textAlign: 'center', margin: '6px 0' }}>
            {loading ? '⏳ Loading clans…' : t('worldEnd.noClans')}
          </p>
        ) : (
          <div style={{ display: 'grid', gap: 6, maxHeight: 180, overflow: 'auto', paddingRight: 2 }}>
            {clans.map((c: any) => {
              const isLongest = records.longestClan?.clan.id === c.id
              const isBiggest = records.biggestClan?.clan.id === c.id
              const isWarTop = records.topWarClan?.id === c.id
              const isFinalSoul = records.finalSoul?.clanId === c.id

              return (
                <div
                  key={c.id}
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    padding: '6px 10px',
                    background: 'rgba(110,118,129,0.08)',
                    borderRadius: 6,
                    borderLeft: `4px solid ${c.color}`,
                    fontSize: 12,
                    gap: 8,
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6, minWidth: 0, flex: 1, flexWrap: 'wrap' }}>
                    <b style={{ color: c.color }}>{c.name}</b>
                    <span style={{ color: '#8b949e', fontSize: 10.5 }}>#{c.id}</span>
                    {c.totem && (
                      <span className="chip" style={{ fontSize: 10, padding: '1px 5px' }}>
                        {totemEmoji(c.totem)} {c.totem}
                      </span>
                    )}
                    {isLongest && (
                      <span className="chip" style={{ fontSize: 9.5, padding: '1px 5px', color: '#58a6ff', borderColor: '#58a6ff' }}>
                        ⏳ Longest
                      </span>
                    )}
                    {isBiggest && (
                      <span className="chip" style={{ fontSize: 9.5, padding: '1px 5px', color: '#e3b341', borderColor: '#e3b341' }}>
                        👑 Biggest
                      </span>
                    )}
                    {isWarTop && (
                      <span className="chip" style={{ fontSize: 9.5, padding: '1px 5px', color: '#ff7b72', borderColor: '#ff7b72' }}>
                        ⚔️ Victor
                      </span>
                    )}
                    {isFinalSoul && (
                      <span className="chip" style={{ fontSize: 9.5, padding: '1px 5px', color: '#d2a8ff', borderColor: '#d2a8ff' }}>
                        🕯️ Last Soul
                      </span>
                    )}
                  </div>
                  <span className="chip" style={{ flexShrink: 0, fontSize: 10.5 }}>
                    {c.war_wins ?? 0}W/{c.war_losses ?? 0}L
                  </span>
                </div>
              )
            })}
          </div>
        )}

        {/* Final Moments from the Chronicle */}
        <h3 style={{ fontSize: 13, color: '#e6edf3', margin: '14px 0 6px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span>{t('worldEnd.lastEvents', { count: history.length })}</span>
          <span style={{ fontSize: 10.5, color: '#8b949e', fontWeight: 500 }}>
            {history.length > 0 ? `${Math.min(15, history.length)} final events` : ''}
          </span>
        </h3>

        <div style={{ maxHeight: 150, overflow: 'auto', border: '1px solid #21262d', borderRadius: 6, padding: '6px 8px', background: '#161b22', display: 'flex', flexDirection: 'column', gap: 4 }}>
          {history.slice(0, 15).map((ev: any, i: number) => {
            const d = Math.floor(ev.tick / 1200)
            const p = ev.payload ?? {}
            let evIcon = '💀'
            if (ev.type === 'war') evIcon = '⚔️'
            else if (ev.type === 'outbreak') evIcon = '☣️'
            else if (ev.type === 'birth') evIcon = '🌱'
            else if (ev.type === 'schism') evIcon = '👑'
            else if (ev.type === 'temple') evIcon = '🏛️'
            else if (ev.type === 'disaster') evIcon = '🌋'
            else if (ev.type === 'extinction' || ev.type === 'clan_extinction') evIcon = '☠️'

            return (
              <div key={i} style={{ fontSize: 11, padding: '3px 4px', borderBottom: '1px solid rgba(48,54,61,0.4)', display: 'flex', alignItems: 'center', gap: 6, color: '#c9d1d9' }}>
                <span style={{ flexShrink: 0 }}>{evIcon}</span>
                <span className="chip" style={{ fontSize: 9.5, padding: '1px 5px', flexShrink: 0 }}>D{d}</span>
                <b style={{ color: '#e6edf3', textTransform: 'capitalize', flexShrink: 0 }}>{ev.type}</b>
                <span style={{ color: '#8b949e', flex: 1, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {p.personal_name ? `${p.personal_name} ` : ''}#{ev.entity_id} {ev.cause ? `· ${ev.cause}` : ''} {p.winner ? `vs ${p.winner}` : ''}
                </span>
              </div>
            )
          })}
          {history.length === 0 && <div className="chip">{t('worldEnd.noHistory')}</div>}
        </div>

        {/* Clean Action Dock: Single Icons Guaranteed */}
        <div className="world-end-actions">
          {onOpenWorldHistory && (
            <button
              type="button"
              onClick={onOpenWorldHistory}
              className="world-end-btn world-end-btn-history"
              title={t('worldEnd.historyExport')}
            >
              <span className="world-end-btn-icon">📜</span>
              <span className="world-end-btn-label">
                {t('worldEnd.historyBtn') || t('worldEnd.historyExport').replace(/^📜\s*/, '')}
              </span>
            </button>
          )}
          <button
            type="button"
            onClick={onReset}
            className="world-end-btn world-end-btn-reset"
            title={t('worldEnd.reset')}
          >
            <span className="world-end-btn-icon">🔄</span>
            <span className="world-end-btn-label">
              {t('worldEnd.resetBtn') || t('worldEnd.reset').replace(/^🔄\s*/, '')}
            </span>
          </button>
          <button
            type="button"
            onClick={onClose}
            className="world-end-btn world-end-btn-close"
          >
            <span>{t('worldEnd.close')}</span>
          </button>
        </div>

        <p className="god-note" style={{ textAlign: 'center', marginTop: 10, fontSize: 10.5 }}>
          {t('worldEnd.note')}
        </p>
      </div>
    </div>
  )
}
