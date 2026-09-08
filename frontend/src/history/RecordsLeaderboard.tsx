import { useMemo } from 'react'
import type { DayRecord } from './WorldHistoryModal'
import { totemEmoji } from '../totems'

interface Props {
  dayRecords: DayRecord[]
  clans: Record<string, any>
  rawEvents: any[]
  onSelectClan?: (clanId: number) => void
  onSelectCreature?: (creatureId: number) => void
}

export default function RecordsLeaderboard({
  dayRecords,
  clans,
  rawEvents,
  onSelectClan,
  onSelectCreature,
}: Props) {
  const records = useMemo(() => {
    // 1. Clan by war wins
    const clanList = Object.values(clans)
    const topWarClan = [...clanList].sort((a, b) => (b.war_wins ?? 0) - (a.war_wins ?? 0))[0] ?? null

    // 2. Clan by population
    const topPopClan = [...clanList].sort((a, b) => (b.population ?? 0) - (a.population ?? 0))[0] ?? null

    // 3. Deadliest Day
    const deadliestDay = [...dayRecords].sort((a, b) => b.totalCasualties - a.totalCasualties)[0] ?? null

    // 4. Most temples raised
    const templeCounts: Record<string, { count: number; name: string; id: number }> = {}
    const kills: Record<string, { id: number; name?: string; caste?: string; count: number }> = {}
    const betrayals: Record<string, { id: number; name?: string; count: number }> = {}
    let largestSchism: { parent: string; child: string; count: number; day: number } | null = null

    for (const ev of rawEvents) {
      const p = (ev.payload ?? {}) as Record<string, any>
      const d = Math.floor(ev.tick / 1200)

      if (ev.type === 'temple') {
        const cid = p.clan_id ?? ev.entity_id
        if (cid) {
          const k = String(cid)
          if (!templeCounts[k]) {
            templeCounts[k] = { count: 0, name: p.clan_name ?? `Clan #${cid}`, id: cid }
          }
          templeCounts[k].count++
        }
      } else if (ev.type === 'war' && p.lethal) {
        const wid = p.winner_id ?? p.killer
        if (wid) {
          const k = String(wid)
          if (!kills[k]) {
            kills[k] = { id: wid, name: p.winner_name ?? p.killer_name, caste: p.winner_caste, count: 0 }
          }
          kills[k].count++
        }
      } else if (ev.type === 'betrayal' || ev.type === 'regicide') {
        const tid = ev.entity_id ?? p.assassin_id ?? p.traitor_id
        if (tid) {
          const k = String(tid)
          if (!betrayals[k]) {
            betrayals[k] = { id: tid, name: p.assassin ?? p.traitor_name, count: 0 }
          }
          betrayals[k].count++
        }
      } else if (ev.type === 'schism') {
        const memCount = Array.isArray(p.members) ? p.members.length : 0
        if (!largestSchism || memCount > largestSchism.count) {
          largestSchism = {
            parent: p.parent_name ?? `Clan #${p.parent}`,
            child: p.new_name ?? `Clan #${p.new_clan}`,
            count: memCount,
            day: d,
          }
        }
      }
    }

    const topTempleClan = Object.values(templeCounts).sort((a, b) => b.count - a.count)[0] ?? null
    const topHero = Object.values(kills).sort((a, b) => b.count - a.count)[0] ?? null
    const topVillain = Object.values(betrayals).sort((a, b) => b.count - a.count)[0] ?? null

    return {
      topWarClan,
      topPopClan,
      deadliestDay,
      topTempleClan,
      topHero,
      topVillain,
      largestSchism,
    }
  }, [clans, dayRecords, rawEvents])

  const items = [
    {
      title: '⚔️ Sovereign of War',
      metric: `${records.topWarClan?.war_wins ?? 0} Victories`,
      holder: records.topWarClan?.name ?? 'None',
      sub: `${records.topWarClan?.war_losses ?? 0} defeats recorded`,
      color: '#ff7b72',
      onClick: records.topWarClan ? () => onSelectClan?.(records.topWarClan.id) : undefined,
    },
    {
      title: '💀 Deadliest Single Day',
      metric: `${records.deadliestDay?.totalCasualties ?? 0} Fallen`,
      holder: records.deadliestDay ? `Day ${records.deadliestDay.day}` : 'None',
      sub: records.deadliestDay?.summaryLine ?? '',
      color: '#f85149',
    },
    {
      title: '👑 Greatest Realm (Population)',
      metric: `${records.topPopClan?.population ?? 0} Living`,
      holder: records.topPopClan?.name ?? 'None',
      sub: `Totem: ${records.topPopClan?.totem ? `${totemEmoji(records.topPopClan.totem)} ${records.topPopClan.totem}` : 'Unknown'}`,
      color: '#79c0ff',
      onClick: records.topPopClan ? () => onSelectClan?.(records.topPopClan.id) : undefined,
    },
    {
      title: '🏛️ Divine Architects',
      metric: `${records.topTempleClan?.count ?? 0} Temples Raised`,
      holder: records.topTempleClan?.name ?? 'None',
      sub: 'Sanctuaries consecrated to the Sphere',
      color: '#e3b341',
      onClick: records.topTempleClan ? () => onSelectClan?.(records.topTempleClan.id) : undefined,
    },
    {
      title: '🗡️ Deadliest Champion (Hero)',
      metric: `${records.topHero?.count ?? 0} Kills`,
      holder: records.topHero ? `${records.topHero.name ?? ''} #${records.topHero.id}` : 'None',
      sub: `${records.topHero?.caste ?? 'Warrior'} · Vanquisher in single combat`,
      color: '#3fb950',
      onClick: records.topHero ? () => onSelectCreature?.(records.topHero.id) : undefined,
    },
    {
      title: '🐍 Infamous Traitor (Villain)',
      metric: `${records.topVillain?.count ?? 0} Treasons`,
      holder: records.topVillain ? `${records.topVillain.name ?? ''} #${records.topVillain.id}` : 'None',
      sub: 'Instigator of regicide and factional betrayal',
      color: '#d2a8ff',
      onClick: records.topVillain ? () => onSelectCreature?.(records.topVillain.id) : undefined,
    },
    {
      title: '⚡ Greatest Tribal Schism',
      metric: `${records.largestSchism?.count ?? 0} Rebels`,
      holder: records.largestSchism ? `${records.largestSchism.child}` : 'None',
      sub: records.largestSchism ? `Seceded from ${records.largestSchism.parent} on Day ${records.largestSchism.day}` : '',
      color: '#f0883e',
    },
  ]

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h3 style={{ margin: 0, fontSize: 15, color: '#e6edf3', fontWeight: 700 }}>
            🏆 Records & Legends of Flatland (BM-13)
          </h3>
          <span style={{ fontSize: 11, color: '#8b949e' }}>
            All-time world records, conquerors, martyrs, and epochal landmarks.
          </span>
        </div>
      </div>

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))',
          gap: 10,
        }}
      >
        {items.map((item) => (
          <div
            key={item.title}
            onClick={item.onClick}
            style={{
              background: '#161b22',
              border: '1px solid #30363d',
              borderLeft: `4px solid ${item.color}`,
              borderRadius: 8,
              padding: '10px 14px',
              display: 'flex',
              flexDirection: 'column',
              gap: 4,
              cursor: item.onClick ? 'pointer' : 'default',
              transition: 'background 0.15s',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
              <span style={{ fontSize: 11, color: '#8b949e', textTransform: 'uppercase', letterSpacing: 0.5, fontWeight: 600 }}>
                {item.title}
              </span>
              <span style={{ fontSize: 12, color: item.color, fontWeight: 800 }}>
                {item.metric}
              </span>
            </div>
            <div style={{ fontSize: 14, fontWeight: 700, color: '#e6edf3', marginTop: 2 }}>
              {item.holder}
              {item.onClick && <span style={{ fontSize: 11, color: '#58a6ff', marginLeft: 6 }}>↗</span>}
            </div>
            {item.sub && (
              <div style={{ fontSize: 10.5, color: '#8b949e', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {item.sub}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
