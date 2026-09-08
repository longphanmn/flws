import { memo, useEffect, useState, useMemo } from 'react'
import { totemEmoji } from '../totems'
import { useI18n } from '../i18n'

interface ClanKnowledge {
  enemy_clans?: number[]
  danger_zones?: { x: number; y: number; conf: number }[]
  food_spots?: { x: number; y: number; conf: number }[]
  members_with_home_knowledge?: number
}
interface ClanInfo {
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
  house: { x: number; y: number; size: number; is_ruin: boolean } | null
  war_wins: number
  war_losses: number
  territory_radius: number | null
  specialization?: { warrior: number; farmer: number; scavenger: number } | null
  culture?: string | null
  culture_id?: number | null
  knowledge?: ClanKnowledge | null
  coalition_id?: number | null
  larder?: number
  granary?: number
  harvest_total?: number
  feast?: boolean
  dialect?: number
  tribute_to?: number | null
  faith?: number
  shrine_level?: number
}

type SortKey = 'pop' | 'wins' | 'larder' | 'age'

function ClanPanel({ onSelectClan, onSelectCreature, state }: { onSelectClan?: (id: number) => void; onSelectCreature?: (id: number) => void; state?: any }) {
  const { t } = useI18n()
  const [clans, setClans] = useState<ClanInfo[]>([])
  const [tick, setTick] = useState(0)
  const [sortBy, setSortBy] = useState<SortKey>('pop')

  useEffect(() => {
    if (state && state.clans) {
      const arr: ClanInfo[] = Object.entries(state.clans as Record<string, any>).map(([id, info]: any) => ({
        id: Number(id),
        name: info.name ?? `#${id}`,
        color: info.color ?? '#8b949e',
        totem: info.totem ?? null,
        founder_id: info.founder_id ?? 0,
        leader_id: info.leader_id ?? null,
        born_tick: info.born_tick ?? 0,
        founded_day: info.founded_day,
        dead_count: info.dead_count ?? 0,
        population: info.population ?? (state.entities ? state.entities.filter((e: any) => e.clan_id === Number(id)).length : 0),
        house: info.main_house_id ? (() => {
          const h = state.entities?.find((e: any) => e.id === info.main_house_id)
          return h ? { x: h.x, y: h.y, size: h.size ?? 6, is_ruin: !!h.is_ruin } : null
        })() : null,
        war_wins: info.war_wins ?? 0,
        war_losses: info.war_losses ?? 0,
        territory_radius: info.territory_radius ?? null,
        specialization: info.specialization ?? null,
        culture: info.culture ?? null,
        culture_id: info.culture_id ?? null,
        knowledge: info.knowledge ?? null,
        coalition_id: info.coalition_id ?? null,
        larder: info.larder,
        granary: info.granary,
        harvest_total: info.harvest_total,
        feast: info.feast,
        dialect: info.dialect,
        tribute_to: info.tribute_to ?? null,
        faith: info.faith,
        shrine_level: info.shrine_level,
      }))
      setClans(arr)
      setTick(state.tick ?? 0)
      return
    }
    let alive = true
    const load = () =>
      fetch('/api/clans')
        .then((r) => r.json())
        .then((d) => {
          if (!alive) return
          setClans(d.clans ?? [])
          setTick(d.tick ?? 0)
        })
        .catch(() => {})
    load()
    return () => { alive = false }
  }, [state])

  const sorted = useMemo(() => {
    const alive = clans.filter((c) => c.population > 0)
    const copy = [...alive]
    if (sortBy === 'pop') copy.sort((a, b) => b.population - a.population)
    else if (sortBy === 'wins') copy.sort((a, b) => (b.war_wins - a.war_wins) || (b.population - a.population))
    else if (sortBy === 'larder') copy.sort((a, b) => ((b.larder ?? 0) + (b.granary ?? 0)) - ((a.larder ?? 0) + (a.granary ?? 0)))
    else if (sortBy === 'age') copy.sort((a, b) => a.born_tick - b.born_tick)
    return copy
  }, [clans, sortBy])

  if (clans.length === 0) return <p className="chip">{t('clanPanel.noClans')}</p>
  if (sorted.length === 0) return <p className="chip">{t('clanPanel.noClans')} — {t('clanPanel.allFallen')}</p>

  return (
    <div className="clan-panel" style={{ gap: 6, minWidth: 0 }}>
      <div className="clan-sort-bar" style={{ minWidth: 0 }}>
        <span style={{ fontWeight: 600, fontSize: 11, color: '#e6edf3' }}>🏰 {sorted.length} {t('app.mobileSheet.clans').toLowerCase()} · {t('app.hud.tick').toLowerCase()} {tick}</span>
        <span style={{ marginLeft: 'auto', fontSize: 11 }}>{t('clanPanel.sort')}</span>
        <select value={sortBy} onChange={(e) => setSortBy(e.target.value as SortKey)} aria-label="Sort clans">
          <option value="pop">{t('clanPanel.pop')}</option>
          <option value="wins">{t('clanPanel.wins')}</option>
          <option value="larder">{t('clanPanel.larder')}</option>
          <option value="age">{t('clanPanel.age')}</option>
        </select>
      </div>
      <div style={{ display: 'grid', gap: 6 }}>
        {sorted.map((c) => {
          const spec = c.specialization
          const totalSpec = spec ? spec.warrior + spec.farmer + spec.scavenger : 0
          const wPct = totalSpec ? (spec!.warrior / totalSpec) * 100 : 0
          const fPct = totalSpec ? (spec!.farmer / totalSpec) * 100 : 0
          const sPct = totalSpec ? (spec!.scavenger / totalSpec) * 100 : 0
          const larderTotal = Math.round((c.larder ?? 0) + (c.granary ?? 0))
          return (
            <div
              key={c.id}
              className="clan-banner"
              onClick={() => onSelectClan?.(c.id)}
              style={{ borderLeft: `3px solid ${c.color}`, minWidth: 0 }}
              title={onSelectClan ? t('clanPanel.clickForDetails') : undefined}
            >
              <div className="clan-banner-head">
                <span className="clan-crest" style={{ background: `${c.color}22`, borderColor: `${c.color}55` }}>{totemEmoji(c.totem)}</span>
                <b style={{ color: c.color, fontSize: 12, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{c.name}</b>
                <span style={{ fontSize: 10, color: '#8b949e' }}>#{c.id}</span>
                <span className="clan-pop-badge" style={{ background: c.color }}>{c.population} alive</span>
              </div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, fontSize: 10.5, color: '#8b949e', alignItems: 'center' }}>
                <span>👑 <button className="chronicle-name" onClick={(e) => { e.stopPropagation(); c.leader_id != null && onSelectCreature?.(c.leader_id) }} title={t('clanPanel.showLeader')} style={{ fontSize: 10.5 }}>#{c.leader_id ?? '—'}</button></span>
                <span>·</span>
                <span title="Main house coords">{c.house ? (c.house.is_ruin ? `🏚 ruins @${Math.round(c.house.x)},${Math.round(c.house.y)}` : `🏠 @${Math.round(c.house.x)},${Math.round(c.house.y)}`) : 'homeless'}</span>
                <span>·</span>
                <span style={{ color: c.war_wins > 0 ? '#3fb950' : '#8b949e' }}>{c.war_wins}W</span>
                <span style={{ color: c.war_losses > 0 ? '#f85149' : '#8b949e' }}>{c.war_losses}L</span>
                {larderTotal > 0 && <><span>·</span><span>🏺 {larderTotal}</span></>}
                {c.feast && <span>· 🍞 feast</span>}
                {(c.shrine_level ?? 0) >= 1 && <><span>·</span><span style={{ color: '#bc8cff' }}>{(c.shrine_level ?? 0) >= 2 ? '⛪' : '🕯️'}</span></>}
              </div>
              {spec && totalSpec > 0 && (
                <div className="micro-spec-bar" title={`⚔ warrior ${spec.warrior.toFixed(2)} · 🌾 farmer ${spec.farmer.toFixed(2)} · 🦴 scav ${spec.scavenger.toFixed(2)}`}>
                  <div className="micro-spec-seg warrior" style={{ width: `${wPct}%` }} />
                  <div className="micro-spec-seg farmer" style={{ width: `${fPct}%` }} />
                  <div className="micro-spec-seg scavenger" style={{ width: `${sPct}%` }} />
                </div>
              )}
              {c.culture && (
                <div style={{ fontSize: 10, color: '#8b949e' }}>🎭 {c.culture}</div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}

export default memo(ClanPanel)
