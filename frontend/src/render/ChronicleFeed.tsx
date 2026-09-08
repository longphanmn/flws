import { memo, useMemo, useState, useRef } from 'react'
import type { HistoryEvent } from '../types'
import { useI18n } from '../i18n'

export type EventCategory = 'all' | 'conflict' | 'clan' | 'deaths' | 'plague' | 'nature'

interface Props {
  events: HistoryEvent[]
  clanLabel: (id?: number | null) => string
  onSelectCreature: (id: number) => void
  onSelectClan: (id: number) => void
  onLoadOlder?: () => void
  loadingOlder?: boolean
  noMoreHistory?: boolean
  archiveMode?: boolean
  selectedRunId?: number | null
  maxDisplay?: number
  compact?: boolean
}

const CATEGORIES: Array<{ key: EventCategory; label: string; icon: string }> = [
  { key: 'all', label: 'All', icon: '📜' },
  { key: 'conflict', label: 'Conflict', icon: '⚔️' },
  { key: 'clan', label: 'Clan & Life', icon: '🌱' },
  { key: 'deaths', label: 'Deaths', icon: '💀' },
  { key: 'plague', label: 'Plague', icon: '☣️' },
  { key: 'nature', label: 'Nature', icon: '🌸' },
]

function matchesCategory(ev: any, category: EventCategory): boolean {
  if (category === 'all') {
    return true
  }
  if (category === 'conflict') {
    return [
      'war',
      'betrayal',
      'schism',
      'conquest',
      'takeover',
      'coup',
      'rebellion',
      'duel',
      'siege',
      'raid',
      'feud',
      'clash',
      'assassination',
      'purge',
      'execution',
      'slaughter',
      'battle',
      'strike',
      'revolt',
      'reprisal',
      'skirmish',
      'dispute',
      'riot',
    ].includes(ev.type)
  }
  if (category === 'clan') {
    return [
      'found',
      'extinct',
      'split',
      'reunion',
      'election',
      'succession',
      'culture',
      'alliance',
      'tribute',
      'promotion',
      'demotion',
      'miracle',
      'sermon',
      'synod',
      'temple',
      'epiphany',
      'resonance',
      'hospitality',
      'banquet',
      'market',
      'caravan',
      'omen',
      'regicide',
      'herald',
      'clan_extinction',
    ].includes(ev.type)
  }
  if (category === 'deaths') {
    return ev.type === 'death' || ev.type === 'war' || ev.type === 'predation' || ev.type === 'cannibalism' || ev.type === 'clan_extinction' || ev.type === 'extinction'
  }
  if (category === 'plague') {
    return ev.type === 'outbreak' || ev.type === 'recovery' || (ev.type === 'death' && ev.cause === 'disease')
  }
  if (category === 'nature') {
    return ['bloom', 'wither', 'ruin', 'fire', 'disaster', 'compost', 'anomaly', 'extinction'].includes(ev.type)
  }
  return true
}

function accentFor(ev: any): string {
  if (ev.type === 'outbreak' || ev.type === 'recovery' || (ev.type === 'death' && ev.cause === 'disease')) return 'cat-plague'
  if (['war','betrayal','schism','conquest','takeover','raid','coalition_formed','coalition_joined','coalition_dissolved','peace','peace_envoy','defection','cannibalism','exile','predation','rivalry','clan_extinction','extinction'].includes(ev.type)) return 'cat-conflict'
  if (['birth','settlement','succession','culture','alliance','tribute','promotion','demotion','miracle','sermon','synod','temple','epiphany','resonance','hospitality','banquet','market','caravan','omen','regicide','herald'].includes(ev.type)) return 'cat-clan'
  if (ev.type === 'death' || ev.type === 'war' || ev.type === 'predation' || ev.type === 'cannibalism') return 'cat-deaths'
  if (['bloom','wither','ruin','fire','disaster','compost','anomaly'].includes(ev.type)) return 'cat-nature'
  return 'cat-clan'
}

function matchesSearch(ev: HistoryEvent, query: string, clanLabel: (id?: number | null) => string): boolean {
  if (!query) return true
  const q = query.toLowerCase().trim()
  const p = (ev.payload ?? {}) as Record<string, any>
  const idStr = String(ev.entity_id)
  if (idStr === q || `#${idStr}` === q || idStr.includes(q)) return true
  if (p.personal_name && String(p.personal_name).toLowerCase().includes(q)) return true
  if (ev.caste && ev.caste.toLowerCase().includes(q)) return true
  if (ev.cause && ev.cause.toLowerCase().includes(q)) return true
  if (ev.type && ev.type.toLowerCase().includes(q)) return true
  if (p.clan_name && String(p.clan_name).toLowerCase().includes(q)) return true
  if (p.culture && String(p.culture).toLowerCase().includes(q)) return true
  if (p.mother && (String(p.mother) === q || `#${p.mother}` === q)) return true
  if (p.father && (String(p.father) === q || `#${p.father}` === q)) return true
  if (p.winner && (String(p.winner) === q || `#${p.winner}` === q)) return true
  if (p.prey && (String(p.prey) === q || `#${p.prey}` === q)) return true
  if (p.clan_id && clanLabel(p.clan_id).toLowerCase().includes(q)) return true
  if (p.a != null && clanLabel(p.a).toLowerCase().includes(q)) return true
  if (p.b != null && clanLabel(p.b).toLowerCase().includes(q)) return true
  if (p.from != null && clanLabel(p.from).toLowerCase().includes(q)) return true
  if (p.to != null && clanLabel(p.to).toLowerCase().includes(q)) return true
  if (p.parent != null && clanLabel(p.parent).toLowerCase().includes(q)) return true
  if (p.new_clan != null && clanLabel(p.new_clan).toLowerCase().includes(q)) return true
  return false
}

function ChronicleFeed({
  events,
  clanLabel,
  onSelectCreature,
  onSelectClan: _onSelectClan,
  onLoadOlder,
  loadingOlder = false,
  noMoreHistory = false,
  archiveMode = false,
  selectedRunId = null,
  maxDisplay = 200,
  compact = false,
}: Props) {
  const { t } = useI18n()
  const [category, setCategory] = useState<EventCategory>('all')
  const [search, setSearch] = useState('')
  const [visibleLimit, setVisibleLimit] = useState(maxDisplay)
  const listRef = useRef<HTMLUListElement>(null)

  // BM-1: Compute top 5 dramatic moments across events (day buckets)
  const majorMoments = useMemo(() => {
    const dayMap = new Map<number, { day: number; startTick: number; wars: number; casualties: number; disasters: number; outbreaks: number; schisms: number; extinctions: number; score: number }>()
    for (const ev of events) {
      const d = Math.floor(ev.tick / 1200)
      let cur = dayMap.get(d)
      if (!cur) {
        cur = { day: d, startTick: d * 1200, wars: 0, casualties: 0, disasters: 0, outbreaks: 0, schisms: 0, extinctions: 0, score: 0 }
        dayMap.set(d, cur)
      }
      const p = (ev.payload ?? {}) as Record<string, any>
      const evType = String(ev.type)
      if (evType === 'war' || evType === 'battle') {
        cur.wars++
        cur.score += 4
        if (p.lethal) {
          cur.casualties++
          cur.score += 3
        }
      } else if (evType === 'death' && (ev.cause === 'combat' || ev.cause === 'war' || ev.cause === 'predation')) {
        cur.casualties++
        cur.score += 2
      } else if (evType === 'conquest' || evType === 'takeover') {
        cur.score += 5
      } else if (evType === 'schism' || evType === 'regicide' || evType === 'coup') {
        cur.schisms++
        cur.score += 4
      } else if (evType === 'disaster' || evType === 'fire' || evType === 'earthquake') {
        cur.disasters++
        cur.score += 5
      } else if (evType === 'outbreak') {
        cur.outbreaks++
        cur.score += 3
      } else if (evType === 'clan_extinction' || evType === 'extinction') {
        cur.extinctions++
        cur.score += 6
      }
    }

    const sorted = Array.from(dayMap.values())
      .filter((m) => m.score > 0)
      .sort((a, b) => b.score - a.score)
      .slice(0, 5)

    return sorted.map((m) => {
      let icon = '⚡'
      let typeKey = 'strife'
      if (m.extinctions > 0) {
        icon = '💀'
        typeKey = 'extinction'
      } else if (m.disasters > 0) {
        icon = '🌋'
        typeKey = 'disaster'
      } else if (m.wars > 0 || m.casualties > 0) {
        icon = '⚔️'
        typeKey = m.wars > 1 ? 'wars' : 'war'
      } else if (m.outbreaks > 0) {
        icon = '☣️'
        typeKey = 'plague'
      } else if (m.schisms > 0) {
        icon = '👑'
        typeKey = 'schism'
      }
      const dayLabel = t('chronicle.moments.day', { day: m.day }) || `Day ${m.day}`
      const typeLabel = typeKey === 'wars'
        ? (t('chronicle.moments.wars', { count: m.wars }) || `${m.wars} Wars`)
        : (t(`chronicle.moments.${typeKey}`) || typeKey)
      return {
        day: m.day,
        startTick: m.startTick,
        label: `${icon} ${dayLabel} ${typeLabel}`,
        score: m.score,
      }
    })
  }, [events, t])

  const handleJumpToTick = (targetTick: number) => {
    if (isNaN(targetTick) || events.length === 0) return
    let bestIdx = 0
    let bestDiff = Infinity
    for (let i = 0; i < filtered.length; i++) {
      const diff = Math.abs(filtered[i].tick - targetTick)
      if (diff < bestDiff) {
        bestDiff = diff
        bestIdx = i
      }
    }
    if (bestIdx >= visibleLimit) {
      setVisibleLimit(bestIdx + 40)
    }
    setTimeout(() => {
      const targetEv = filtered[bestIdx]
      if (!targetEv) return
      const el = listRef.current?.querySelector(`[data-tick="${targetEv.tick}"]`) as HTMLElement | null
      if (el) {
        el.scrollIntoView({ behavior: 'smooth', block: 'center' })
        el.classList.add('chronicle-highlight-pulse')
        setTimeout(() => el.classList.remove('chronicle-highlight-pulse'), 2000)
      }
    }, 60)
  }

  const filtered = useMemo(() => {
    return events.filter(
      (ev) => matchesCategory(ev, category) && matchesSearch(ev, search, clanLabel),
    )
  }, [events, category, search, clanLabel])

  const displayed = useMemo(() => filtered.slice(0, visibleLimit), [filtered, visibleLimit])

  return (
    <div
      className={`chronicle-feed-container ${compact ? 'chronicle-compact' : ''}`}
      style={{ display: 'flex', flexDirection: 'column', gap: compact ? 6 : 8, height: '100%', minHeight: 0, flex: '1 1 0' }}
    >
      {archiveMode && selectedRunId !== null && (
        <p className="archive-banner" style={{ margin: 0 }}>
          {t('chronicleEvents.archive', { id: selectedRunId })}
        </p>
      )}

      {/* Streamlined Filter Controls Bar */}
      <div
        className="chronicle-controls"
        style={{
          display: 'flex',
          flexDirection: 'column',
          gap: 6,
          background: 'rgba(22, 27, 34, 0.75)',
          border: '1px solid #30363d',
          borderRadius: 8,
          padding: '6px 8px',
        }}
      >
        {/* Full-width clean search bar with smart Enter-to-jump */}
        <div className="chronicle-search-bar">
          <span className="chronicle-search-icon">🔍</span>
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                const trimmed = search.trim()
                const num = parseInt(trimmed.replace(/^#/, ''), 10)
                if (!isNaN(num)) {
                  handleJumpToTick(num)
                }
              }
            }}
            placeholder={t('chronicle.searchPlaceholder') || t('chronicleEvents.searchPlaceholder') || 'Search or #tick…'}
            className="chronicle-search-input"
          />
          {search && (
            <button
              type="button"
              onClick={() => setSearch('')}
              className="chronicle-search-clear"
              title={t('chronicle.clearSearch') || 'Clear search'}
            >
              ✕
            </button>
          )}
        </div>

        {/* Single-row horizontal scroll category pills */}
        <div className="chronicle-controls-pill-row">
          {CATEGORIES.map((cat) => {
            const active = category === cat.key
            const label = t(`chronicle.categories.${cat.key}`) !== `chronicle.categories.${cat.key}` ? t(`chronicle.categories.${cat.key}`) : cat.label
            return (
              <button
                key={cat.key}
                type="button"
                onClick={() => setCategory(cat.key)}
                style={{
                  padding: '2px 8px',
                  fontSize: 11,
                  fontWeight: active ? 700 : 500,
                  borderRadius: 12,
                  background: active ? '#21262d' : '#161b22',
                  borderColor: active ? '#58a6ff' : '#30363d',
                  color: active ? '#58a6ff' : '#8b949e',
                  whiteSpace: 'nowrap',
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 4,
                  minHeight: 24,
                  flex: 'none',
                  cursor: 'pointer',
                }}
              >
                <span>{cat.icon}</span>
                <span>{label}</span>
              </button>
            )
          })}
        </div>

        {/* BM-1: Subtle Major Moments Jump Chips (desktop only to save space) */}
        {!compact && majorMoments.length > 0 && (
          <div className="chronicle-moments-row">
            <span className="chronicle-moments-tag">
              ⚡ {t('chronicle.momentsTitle') || 'Moments'}:
            </span>
            <div className="chronicle-moments-list">
              {majorMoments.map((m) => (
                <button
                  key={m.day}
                  type="button"
                  className="chronicle-moment-chip"
                  onClick={() => handleJumpToTick(m.startTick)}
                  title={t('chronicle.jumpTo', { day: m.day, tick: m.startTick }) || `Jump to Day ${m.day} (tick ${m.startTick})`}
                >
                  {m.label}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Status Count & Clear */}
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            fontSize: 11,
            color: '#8b949e',
            paddingTop: 2,
          }}
        >
          <span>
            {t('chronicleEvents.showing', { displayed: displayed.length, filtered: filtered.length, unit: filtered.length === 1 ? t('chronicleEvents.event') : t('chronicleEvents.events'), total: events.length })}{filtered.length !== events.length ? '' : (t('chronicle.total', { count: events.length }) || ` (${events.length} total)`)}
          </span>
          {(category !== 'all' || search) && (
            <button
              type="button"
              onClick={() => {
                setCategory('all')
                setSearch('')
              }}
              style={{
                background: 'transparent',
                border: 'none',
                color: '#58a6ff',
                fontSize: 11,
                cursor: 'pointer',
                padding: 0,
                textDecoration: 'underline',
              }}
            >
              {t('chronicleEvents.resetFilter')}
            </button>
          )}
        </div>
      </div>

      {!archiveMode && onLoadOlder && (
        <button
          type="button"
          className="chron-btn"
          onClick={onLoadOlder}
          disabled={loadingOlder || noMoreHistory}
          style={{ width: '100%', minHeight: 28, fontSize: 11 }}
        >
          {loadingOlder ? t('chronicleEvents.loadingOlder') : noMoreHistory ? t('chronicleEvents.noOlder') : t('chronicleEvents.loadOlder')}
        </button>
      )}

      {/* Event Items List */}
      {displayed.length === 0 ? (
        <p className="chip" style={{ margin: '8px 0', textAlign: 'center' }}>
          {search || category !== 'all' ? t('chronicleEvents.noMatch') : t('chronicleEvents.noMajor')}
        </p>
      ) : (
        <ul
          ref={listRef}
          className="chronicle-feed-list"
          style={{ margin: 0, padding: 0, listStyle: 'none', flex: '1 1 0', overflowY: 'auto', minHeight: 0 }}
        >
          {displayed.map((ev: any, idx: number) => {
            const key = `${ev.tick}:${ev.entity_id}:${ev.type}`
            const p = (ev.payload ?? {}) as Record<string, any>
            const accent = accentFor(ev)
            const isLive = idx < 3 && !archiveMode
            const liveCls = isLive ? ' live-pulse' : ''
            const accentCls = 'chronicle-accent ' + accent + liveCls

            if (ev.type === 'birth') {
              const nm = p.personal_name ?? ev.caste
              const gl = p.glyph ? ` ${p.glyph}` : ''
              return (
                <li key={key} data-tick={ev.tick} className={"ev-birth " + accentCls}>
                  <button className="chronicle-name" onClick={() => onSelectCreature(ev.entity_id)} title={t('chronicle.showProfile') || 'show profile'}>
                    <b>{nm}{gl}</b> #{ev.entity_id}
                  </button>{' '}
                  {t('chronicleEvents.bornTo', { mother: p.mother ?? '?', father: p.father ?? '?', gen: p.generation ?? 0, tick: ev.tick })}
                </li>
              )
            }

            if (ev.type === 'promotion') {
              const nm = p.personal_name ? `${p.personal_name} ` : ''
              return (
                <li key={key} data-tick={ev.tick} className={"ev-promo " + accentCls}>
                  <button className="chronicle-name" onClick={() => onSelectCreature(ev.entity_id)} title={t('chronicle.showProfile') || 'show profile'}>
                    <b>{nm}#{ev.entity_id}</b>
                  </button>{' '}
                  {t('chronicleEvents.roseTo', { from: String(p.from ?? 'Soldier'), to: String(p.to ?? ev.caste), tick: ev.tick })}
                </li>
              )
            }

            if (ev.type === 'demotion') {
              const nm = p.personal_name ?? ev.caste
              const gl = p.glyph ? ` ${p.glyph}` : ''
              return (
                <li key={key} data-tick={ev.tick} className={"ev-demote " + accentCls}>
                  <button className="chronicle-name" onClick={() => onSelectCreature(ev.entity_id)} title={t('chronicle.showProfile') || 'show profile'}>
                    <b>{nm}{gl}</b> #{ev.entity_id}
                  </button>{' '}
                  {t('chronicleEvents.demotedToWoman', { tick: ev.tick })}
                </li>
              )
            }

            if (ev.type === 'predation') {
              const nm = p.personal_name ?? ev.caste
              const gl = p.glyph ? ` ${p.glyph}` : ''
              return (
                <li key={key} data-tick={ev.tick} className={"ev-predation " + accentCls}>
                  <button className="chronicle-name" onClick={() => onSelectCreature(ev.entity_id)} title={t('chronicle.showPredator') || 'show predator'}>
                    <b>{nm}{gl}</b> #{ev.entity_id}
                  </button>{' '}
                  {t('chronicleEvents.predatedPrey', { preyCaste: p.prey_caste ?? 'Creature', prey: p.prey ?? '?', tick: ev.tick })}
                </li>
              )
            }

            if (ev.type === 'war') {
              const nm = p.personal_name ?? ev.caste
              const gl = p.glyph ? ` ${p.glyph}` : ''
              return (
                <li key={key} data-tick={ev.tick} className={"ev-war " + accentCls}>
                  <button className="chronicle-name" onClick={() => onSelectCreature(ev.entity_id)} title={t('chronicle.showFallen') || 'show fallen'}>
                    <b>{nm}{gl}</b> #{ev.entity_id}
                  </button>{' '}
                  {t('chronicleEvents.fellInWar', { winner: p.winner ?? '?', tick: ev.tick })}
                </li>
              )
            }

            if (ev.type === 'alliance' || ev.type === 'rivalry') {
              return (
                <li key={key} data-tick={ev.tick} className={(ev.type === 'alliance' ? 'ev-alliance' : 'ev-rivalry') + ' ' + accentCls}>
                  {t('chronicleEvents.clansAlliance', { a: clanLabel(p.a), b: clanLabel(p.b), type: ev.type, score: p.score, tick: ev.tick })}
                </li>
              )
            }

            if (ev.type === 'schism') {
              return (
                <li key={key} data-tick={ev.tick} className={"ev-schism " + accentCls}>
                  {t('chronicleEvents.schismBreak', { parent: p.parent_name ?? clanLabel(p.parent), child: p.new_name ?? clanLabel(p.new_clan), count: (p.members as number[])?.length ?? 0, tick: ev.tick })}
                </li>
              )
            }

            if (ev.type === 'conquest') {
              return (
                <li key={key} data-tick={ev.tick} className={"ev-war " + accentCls}>
                  {t('chronicleEvents.conquestHouse', { winner: clanLabel(p.winner_clan), house: p.house_id, loser: clanLabel(p.loser_clan), tick: ev.tick })}
                </li>
              )
            }

            if (ev.type === 'takeover') {
              return (
                <li key={key} data-tick={ev.tick} className={"ev-war " + accentCls}>
                  {t('chronicleEvents.takeoverHouse', { invader: p.invader_name ?? clanLabel(p.invader_clan), house: p.house_id, victim: p.victim_name ?? clanLabel(p.victim_clan), tick: ev.tick })}
                </li>
              )
            }

            if (ev.type === 'coalition_formed' || ev.type === 'coalition_joined' || ev.type === 'coalition_dissolved') {
              const who = ev.type === 'coalition_joined'
                ? t('chronicleEvents.coalitionJoined', { clan: clanLabel(p.clan) })
                : ev.type === 'coalition_dissolved'
                  ? `${p.reason ?? 'dissolved'} —`
                  : t('chronicleEvents.coalitionFounded', { clan: clanLabel(p.leader_clan) })
              return (
                <li key={key} data-tick={ev.tick} className={"ev-alliance " + accentCls} style={{ color: '#7ee787' }}>
                  {t('chronicleEvents.coalitionLine', { formed: ev.type === 'coalition_formed' ? 'coalition: ' : '', who, name: String(p.name ?? `coalition #${p.coalition}`), count: (p.members as number[] | undefined)?.length ?? 0, tick: ev.tick })}
                </li>
              )
            }

            if (ev.type === 'peace') {
              return (
                <li key={key} data-tick={ev.tick} className={"ev-alliance " + accentCls}>
                  {t('chronicleEvents.peaceArms', { a: clanLabel(p.a), b: clanLabel(p.b), tick: ev.tick })}
                </li>
              )
            }

            if (ev.type === 'tribute') {
              return (
                <li key={key} data-tick={ev.tick} className={"ev-alliance " + accentCls}>
                  {t('chronicleEvents.tributePay', { from: clanLabel(p.from), amount: p.amount ?? '?', to: clanLabel(p.to), tick: ev.tick })}
                </li>
              )
            }

            if (ev.type === 'betrayal') {
              return (
                <li key={key} data-tick={ev.tick} className={"ev-war " + accentCls}>
                  {t('chronicleEvents.betrayalTurn', { a: clanLabel(p.a), b: clanLabel(p.b), tick: ev.tick })}
                </li>
              )
            }

            if (ev.type === 'defection') {
              return (
                <li key={key} data-tick={ev.tick} className={"ev-schism " + accentCls}>
                  {t('chronicleEvents.defectionLeave', { id: ev.entity_id, from: clanLabel(p.from), to: clanLabel(p.to), tick: ev.tick })}
                </li>
              )
            }

            if (ev.type === 'cannibalism') {
              return (
                <li key={key} data-tick={ev.tick} className={"ev-predation " + accentCls}>
                  {t('chronicleEvents.cannibalismEat', { caste: ev.caste ?? 'Creature', id: ev.entity_id, kin: p.kin ? 'kin' : 'enemy', preyCaste: p.prey_caste ?? 'Creature', prey: p.prey ?? '?', tick: ev.tick })}
                </li>
              )
            }

            if (ev.type === 'exile') {
              return (
                <li key={key} data-tick={ev.tick} className={"ev-demote " + accentCls}>
                  {t('chronicleEvents.exileCast', { name: String(p.personal_name ?? '') + String(p.glyph ?? ''), id: ev.entity_id, clan: p.former_name ?? clanLabel(p.former_clan), tick: ev.tick })}
                </li>
              )
            }

            if (ev.type === 'miracle') {
              return (
                <li key={key} data-tick={ev.tick} className={"ev-bloom " + accentCls} style={{ color: '#7ee787' }}>
                  {t('chronicleEvents.miracleBounty', { avatar: String(p.avatar ?? 'avatar'), clan: p.clan_name ?? clanLabel(p.clan_id), tick: ev.tick })}
                </li>
              )
            }

            if (ev.type === 'sermon') {
              return (
                <li key={key} data-tick={ev.tick} className={"ev-alliance " + accentCls} style={{ color: '#d2a8ff' }}>
                  {t('chronicleEvents.sermonLaw', { caste: ev.caste ?? 'Priest', id: ev.entity_id, clan: p.clan_name ?? clanLabel(p.clan_id), text: String(p.text ?? ''), tick: ev.tick })}
                </li>
              )
            }

            if (ev.type === 'synod') {
              return (
                <li key={key} data-tick={ev.tick} className={"ev-alliance " + accentCls} style={{ color: '#e3b341' }}>
                  {t('chronicleEvents.synodSphere', { count: (p.clans as number[] | undefined)?.length ?? '?', age: String(p.age ?? 'crisis'), tick: ev.tick })}
                </li>
              )
            }

            if (ev.type === 'temple') {
              return (
                <li key={key} data-tick={ev.tick} className={"ev-settlement " + accentCls} style={{ color: '#e3b341' }}>
                  {t('chronicleEvents.templeRaise', { clan: p.clan_name ?? clanLabel(p.clan_id), avatar: String(p.avatar ?? 'avatar'), tick: ev.tick })}
                </li>
              )
            }

            if (ev.type === 'epiphany') {
              return (
                <li key={key} data-tick={ev.tick} className={"ev-miracle " + accentCls} style={{ color: '#bc8cff' }}>
                  {t('chronicleEvents.epiphanyBehold', { name: String(p.personal_name ?? '') + String(p.glyph ?? ''), id: ev.entity_id, tick: ev.tick })}
                </li>
              )
            }

            if (ev.type === 'resonance') {
              return (
                <li key={key} data-tick={ev.tick} className={"ev-alliance " + accentCls} style={{ color: '#e3b341' }}>
                  {t('chronicleEvents.resonanceChimes', { laws: String(((p.laws as string[]) ?? []).join(', ') || 'the laws'), chimes: String(p.chimes ?? 0), sermons: String(p.sermons ?? 0), tick: ev.tick })}
                </li>
              )
            }

            if (ev.type === 'settlement') {
              const byClan = p.clan_id ? t('chronicleEvents.settlementByClan', { clan: clanLabel(p.clan_id) }) : ''
              return (
                <li key={key} data-tick={ev.tick} className={"ev-bloom " + accentCls}>
                  {t('chronicleEvents.settlementFounded', { byClan, x: Math.round(ev.x), y: Math.round(ev.y), tick: ev.tick })}
                </li>
              )
            }

            if (ev.type === 'succession') {
              return (
                <li key={key} data-tick={ev.tick} className={"ev-promo " + accentCls}>
                  {t('chronicleEvents.successionLeader', { clan: p.clan_name ?? clanLabel(p.clan_id), newLeader: p.new_leader ?? '?', prevLeader: p.prev_leader ?? '?', tick: ev.tick })}
                </li>
              )
            }

            if (ev.type === 'culture') {
              return (
                <li key={key} data-tick={ev.tick} className={"ev-bloom " + accentCls}>
                  {t('chronicleEvents.cultureEmbrace', { clan: clanLabel(p.clan_id), culture: p.culture, tick: ev.tick })}
                </li>
              )
            }

            if (ev.type === 'bloom' || ev.type === 'wither') {
              return (
                <li key={key} data-tick={ev.tick} className={(ev.type === 'bloom' ? 'ev-bloom' : 'ev-wither') + ' ' + accentCls} style={{ color: ev.type === 'bloom' ? '#3fb950' : '#8b949e' }}>
                  {t('chronicleEvents.bloomWither', { type: ev.type, x: Math.round(ev.x), y: Math.round(ev.y), tick: ev.tick })}
                </li>
              )
            }

            if (ev.type === 'outbreak' || ev.type === 'recovery') {
              const nm = p.personal_name ?? ev.caste
              const gl = p.glyph ? ` ${p.glyph}` : ''
              return (
                <li key={key} data-tick={ev.tick} className={(ev.type === 'outbreak' ? 'ev-outbreak' : 'ev-recovery') + ' ' + accentCls}>
                  <button className="chronicle-name" onClick={() => onSelectCreature(ev.entity_id)} title={t('chronicle.showCreature') || 'show creature'}>
                    <b>{nm}{gl}</b> #{ev.entity_id}
                  </button>{' '}
                  {t('chronicleEvents.outbreakAction', { action: ev.type, tick: ev.tick })}
                </li>
              )
            }

            if (ev.type === 'raid') {
              return (
                <li key={key} data-tick={ev.tick} className={accentCls} style={{ color: '#f85149' }}>
                  {t('chronicleEvents.raidGranary', { a: p.a_name ?? clanLabel(p.a), b: p.b_name ?? clanLabel(p.b), loot: p.loot ?? '?', tick: ev.tick })}
                </li>
              )
            }
            if (ev.type === 'banquet') {
              return (
                <li key={key} data-tick={ev.tick} className={accentCls} style={{ color: '#e3b341' }}>
                  {t('chronicleEvents.banquetFeast', { clan: p.clan_name ?? clanLabel(p.clan_id), tick: ev.tick })}
                </li>
              )
            }
            if (ev.type === 'compost') {
              const nm = p.personal_name ?? ev.caste
              return (
                <li key={key} data-tick={ev.tick} className={accentCls} style={{ color: '#3fb950' }}>
                  {t('chronicleEvents.compostFields', { name: nm, id: ev.entity_id, clan: p.clan_name ?? clanLabel(p.clan_id), tick: ev.tick })}
                </li>
              )
            }
            if (ev.type === 'hospitality') {
              return (
                <li key={key} data-tick={ev.tick} className={accentCls} style={{ color: '#79c0ff' }}>
                  {t('chronicleEvents.hospitalityBread', { a: p.a_name ?? clanLabel(p.a), b: p.b_name ?? clanLabel(p.b), tick: ev.tick })}
                </li>
              )
            }
            if (ev.type === 'peace_envoy') {
              return (
                <li key={key} data-tick={ev.tick} className={accentCls} style={{ color: '#d2a8ff' }}>
                  {t('chronicleEvents.peaceEnvoyTerms', { a: p.a_name ?? clanLabel(p.a), b: p.b_name ?? clanLabel(p.b), tick: ev.tick })}
                </li>
              )
            }
            if (ev.type === 'market') {
              return (
                <li key={key} data-tick={ev.tick} className={accentCls} style={{ color: '#e3b341' }}>
                  {t('chronicleEvents.marketOpen', { a: p.a_name ?? clanLabel(p.a), b: p.b_name ?? clanLabel(p.b), tick: ev.tick })}
                </li>
              )
            }
            if (ev.type === 'caravan') {
              return (
                <li key={key} data-tick={ev.tick} className={accentCls} style={{ color: '#8b949e' }}>
                  {t('chronicleEvents.caravanTrade', { a: p.a_name ?? clanLabel(p.a), b: p.b_name ?? clanLabel(p.b), tick: ev.tick })}
                </li>
              )
            }
            if (ev.type === 'regicide') {
              return (
                <li key={key} data-tick={ev.tick} className={accentCls} style={{ color: '#f85149' }}>
                  {t('chronicleEvents.regicideMurder', { assassin: p.assassin ?? 'assassin', clanA: p.assassin_clan_name ?? clanLabel(p.assassin_clan), victim: p.victim ?? '?', clanB: p.victim_clan_name ?? clanLabel(p.victim_clan), tick: ev.tick })}
                </li>
              )
            }
            if (ev.type === 'herald') {
              return (
                <li key={key} data-tick={ev.tick} className={accentCls} style={{ color: '#8b949e' }}>
                  {t('chronicleEvents.heraldTerms', { a: p.a_name ?? clanLabel(p.a), b: p.b_name ?? clanLabel(p.b), tick: ev.tick })}
                </li>
              )
            }
            if (ev.type === 'omen') {
              const nm = p.personal_name ?? ev.caste
              return (
                <li key={key} data-tick={ev.tick} className={accentCls} style={{ color: '#e3b341' }}>
                  {t('chronicleEvents.omenBehold', { name: nm, clan: p.clan_name ?? clanLabel(p.clan_id), season: String(p.season), tick: ev.tick })}
                </li>
              )
            }

            if (ev.type === 'disaster') {
              const kind = p.kind === 'river_flood' ? 'river flood' : p.kind === 'flash_flood' ? 'flash flood' : (p.kind ?? 'disaster')
              return (
                <li key={key} data-tick={ev.tick} className={"ev-war " + accentCls} style={{ color: '#f85149' }}>
                  {t('chronicleEvents.disasterEvent', { kind, x: Math.round(ev.x), y: Math.round(ev.y), tick: ev.tick })}
                </li>
              )
            }
            if (ev.type === 'clan_extinction') {
              const cName = p.clan_name ?? clanLabel(p.clan_id)
              const days = p.lifespan_days ?? (p.lifespan_ticks ? Math.round(p.lifespan_ticks / 1200) : 0)
              return (
                <li key={key} data-tick={ev.tick} className={"ev-demote " + accentCls} style={{ color: '#f85149', fontWeight: 600 }}>
                  {t('chronicleEvents.clanExtinction', { clan: cName, days, tick: ev.tick })}
                </li>
              )
            }
            if (ev.type === 'extinction') {
              return (
                <li key={key} data-tick={ev.tick} className={"ev-war " + accentCls} style={{ color: '#f85149', fontWeight: 700 }}>
                  {t('chronicleEvents.extinctionWorld', { tick: ev.tick })}
                </li>
              )
            }
            if (ev.type === 'fire') {
              return (
                <li key={key} data-tick={ev.tick} className={"ev-war " + accentCls} style={{ color: '#f0883e' }}>
                  {t('chronicleEvents.fireEvent', { kind: String(p.kind ?? 'wildfire'), x: Math.round(ev.x), y: Math.round(ev.y), tick: ev.tick })}
                </li>
              )
            }
            if (ev.type === 'ruin') {
              return (
                <li key={key} data-tick={ev.tick} className={"ev-wither " + accentCls} style={{ color: '#8b949e' }}>
                  {t('chronicleEvents.ruinEvent', { id: ev.entity_id, x: Math.round(ev.x), y: Math.round(ev.y), tick: ev.tick })}
                </li>
              )
            }
            if (ev.type === 'anomaly') {
              return (
                <li key={key} data-tick={ev.tick} className={"ev-miracle " + accentCls} style={{ color: '#bc8cff' }}>
                  {t('chronicleEvents.anomalyEvent', { x: Math.round(ev.x), y: Math.round(ev.y), tick: ev.tick })}
                </li>
              )
            }

            // Default: death
            const nm = p.personal_name ?? ev.caste
            const gl = p.glyph ? ` ${p.glyph}` : ''
            return (
              <li key={key} data-tick={ev.tick} className={accentCls}>
                {t('chronicleEvents.deathEvent', { name: `${nm}${gl}`, id: ev.entity_id, cause: ev.cause ?? 'unknown', tick: ev.tick, x: Math.round(ev.x), y: Math.round(ev.y) })}
              </li>
            )
          })}
        </ul>
      )}

      {filtered.length > visibleLimit && (
        <button
          type="button"
          className="chron-btn"
          onClick={() => setVisibleLimit((l) => l + 100)}
          style={{ width: '100%', minHeight: 28, fontSize: 11, marginTop: 4 }}
        >
          {t('chronicleEvents.showMore', { remaining: filtered.length - visibleLimit })}
        </button>
      )}
    </div>
  )
}

export default memo(ChronicleFeed)
