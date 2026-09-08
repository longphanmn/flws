import { useMemo, useState } from 'react'
import type { DayRecord } from './WorldHistoryModal'

interface Props {
  dayRecords: DayRecord[]
  clans: Record<string, any>
  rawEvents: any[]
}

export default function HistoryAnalytics({ dayRecords: _dayRecords, clans, rawEvents }: Props) {
  const [activeTab, setActiveTab] = useState<'rivalry' | 'mortality' | 'faith'>('rivalry')

  // BM-14: Clan Rivalry Matrix
  const clanList = useMemo(() => {
    return Object.values(clans).filter((c: any) => c.name).slice(0, 12)
  }, [clans])

  const rivalryMatrix = useMemo(() => {
    const matrix: Record<string, Record<string, number>> = {}
    for (const c1 of clanList) {
      matrix[String(c1.id)] = {}
      for (const c2 of clanList) {
        matrix[String(c1.id)][String(c2.id)] = 0
      }
    }

    for (const ev of rawEvents) {
      const p = (ev.payload ?? {}) as Record<string, any>
      if (ev.type === 'war' || ev.type === 'battle') {
        const a = String(p.a)
        const b = String(p.b)
        if (matrix[a]?.[b] !== undefined) matrix[a][b] += 1
        if (matrix[b]?.[a] !== undefined) matrix[b][a] += 1
      } else if (ev.type === 'conquest' || ev.type === 'takeover') {
        const a = String(p.invader_clan ?? p.winner_clan)
        const b = String(p.victim_clan ?? p.loser_clan)
        if (matrix[a]?.[b] !== undefined) matrix[a][b] += 2
        if (matrix[b]?.[a] !== undefined) matrix[b][a] += 2
      } else if (ev.type === 'betrayal') {
        const a = String(p.a)
        const b = String(p.b)
        if (matrix[a]?.[b] !== undefined) matrix[a][b] += 3
        if (matrix[b]?.[a] !== undefined) matrix[b][a] += 3
      }
    }
    return matrix
  }, [clanList, rawEvents])

  // BM-15: Cause of death breakdown per 10-day era buckets
  const mortalityBuckets = useMemo(() => {
    const buckets: Record<number, { era: string; combat: number; disease: number; predation: number; hunger: number; other: number; total: number }> = {}

    for (const ev of rawEvents) {
      if (ev.type === 'death') {
        const d = Math.floor(ev.tick / 1200)
        const bucketId = Math.floor(d / 10)
        if (!buckets[bucketId]) {
          buckets[bucketId] = {
            era: `Days ${bucketId * 10}–${(bucketId + 1) * 10 - 1}`,
            combat: 0,
            disease: 0,
            predation: 0,
            hunger: 0,
            other: 0,
            total: 0,
          }
        }
        const b = buckets[bucketId]
        b.total++
        const cause = (ev.cause || '').toLowerCase()
        if (cause === 'combat' || cause === 'war') b.combat++
        else if (cause === 'disease' || cause === 'plague') b.disease++
        else if (cause === 'predation' || cause === 'hunt') b.predation++
        else if (cause === 'starvation' || cause === 'energy' || cause === 'hunger') b.hunger++
        else b.other++
      }
    }

    return Object.entries(buckets)
      .map(([k, v]) => ({ bucketId: Number(k), ...v }))
      .sort((a, b) => a.bucketId - b.bucketId)
  }, [rawEvents])

  // BM-16: Faith index over time (temples, miracles, epiphanies per 5 days)
  const faithBuckets = useMemo(() => {
    const buckets: Record<number, { era: string; temples: number; miracles: number; epiphanies: number; score: number }> = {}

    for (const ev of rawEvents) {
      const d = Math.floor(ev.tick / 1200)
      const bId = Math.floor(d / 5)
      if (!buckets[bId]) {
        buckets[bId] = {
          era: `Days ${bId * 5}–${(bId + 1) * 5 - 1}`,
          temples: 0,
          miracles: 0,
          epiphanies: 0,
          score: 0,
        }
      }
      const b = buckets[bId]
      if (ev.type === 'temple') {
        b.temples++
        b.score += 5
      } else if (ev.type === 'miracle') {
        b.miracles++
        b.score += 3
      } else if (ev.type === 'epiphany' || ev.type === 'sermon' || ev.type === 'synod') {
        b.epiphanies++
        b.score += 2
      }
    }

    return Object.entries(buckets)
      .map(([k, v]) => ({ bucketId: Number(k), ...v }))
      .sort((a, b) => a.bucketId - b.bucketId)
  }, [rawEvents])

  const maxRivalry = useMemo(() => {
    let m = 1
    for (const row of Object.values(rivalryMatrix)) {
      for (const val of Object.values(row)) {
        if (val > m) m = val
      }
    }
    return m
  }, [rivalryMatrix])

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      {/* Analytics Subtabs */}
      <div style={{ display: 'flex', gap: 6, borderBottom: '1px solid #21262d', paddingBottom: 8 }}>
        <button
          type="button"
          className="chip"
          onClick={() => setActiveTab('rivalry')}
          style={{
            background: activeTab === 'rivalry' ? '#388bfd' : '#21262d',
            color: activeTab === 'rivalry' ? '#fff' : '#c9d1d9',
            borderColor: activeTab === 'rivalry' ? '#58a6ff' : '#30363d',
            fontWeight: 600,
            cursor: 'pointer',
          }}
        >
          ⚔️ Clan Rivalry Matrix (BM-14)
        </button>
        <button
          type="button"
          className="chip"
          onClick={() => setActiveTab('mortality')}
          style={{
            background: activeTab === 'mortality' ? '#388bfd' : '#21262d',
            color: activeTab === 'mortality' ? '#fff' : '#c9d1d9',
            borderColor: activeTab === 'mortality' ? '#58a6ff' : '#30363d',
            fontWeight: 600,
            cursor: 'pointer',
          }}
        >
          💀 Mortality Breakdown per Era (BM-15)
        </button>
        <button
          type="button"
          className="chip"
          onClick={() => setActiveTab('faith')}
          style={{
            background: activeTab === 'faith' ? '#388bfd' : '#21262d',
            color: activeTab === 'faith' ? '#fff' : '#c9d1d9',
            borderColor: activeTab === 'faith' ? '#58a6ff' : '#30363d',
            fontWeight: 600,
            cursor: 'pointer',
          }}
        >
          🏛️ Faith Index Over Time (BM-16)
        </button>
      </div>

      {/* BM-14: Rivalry Matrix */}
      {activeTab === 'rivalry' && (
        <div style={{ background: '#161b22', border: '1px solid #30363d', borderRadius: 8, padding: '12px' }}>
          <div style={{ marginBottom: 10 }}>
            <h4 style={{ margin: 0, fontSize: 13, color: '#e6edf3' }}>Pairwise Clan Hostility Heatmap</h4>
            <span style={{ fontSize: 11, color: '#8b949e' }}>
              Hostility points from wars, conquests, and diplomatic betrayals. Darker red indicates ancient blood feuds.
            </span>
          </div>

          {clanList.length === 0 ? (
            <div style={{ color: '#8b949e', fontSize: 12 }}>No formal clans recorded yet.</div>
          ) : (
            <div style={{ overflowX: 'auto' }}>
              <table style={{ borderCollapse: 'collapse', fontSize: 11, width: '100%' }}>
                <thead>
                  <tr>
                    <th style={{ padding: '6px 8px', textAlign: 'left', color: '#8b949e' }}>Clan</th>
                    {clanList.map((c) => (
                      <th
                        key={c.id}
                        style={{ padding: '6px 4px', textAlign: 'center', color: c.color || '#58a6ff', maxWidth: 60, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
                        title={c.name}
                      >
                        #{c.id}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {clanList.map((c1) => (
                    <tr key={c1.id} style={{ borderTop: '1px solid #21262d' }}>
                      <td style={{ padding: '6px 8px', fontWeight: 600, color: c1.color || '#e6edf3', whiteSpace: 'nowrap' }}>
                        {c1.name.length > 16 ? `${c1.name.slice(0, 14)}…` : c1.name}
                      </td>
                      {clanList.map((c2) => {
                        const isSelf = c1.id === c2.id
                        const score = rivalryMatrix[String(c1.id)]?.[String(c2.id)] ?? 0
                        const alpha = isSelf ? 0 : Math.min(0.9, (score / maxRivalry) * 0.9)
                        const bg = isSelf ? '#0d1117' : score > 0 ? `rgba(248, 81, 73, ${alpha})` : 'transparent'

                        return (
                          <td
                            key={c2.id}
                            style={{
                              padding: '6px 4px',
                              textAlign: 'center',
                              background: bg,
                              color: isSelf ? '#484f58' : score > 0 ? '#fff' : '#8b949e',
                              fontWeight: score > 0 ? 700 : 400,
                              borderRadius: 2,
                            }}
                            title={isSelf ? 'Self' : `${c1.name} vs ${c2.name}: ${score} hostility score`}
                          >
                            {isSelf ? '—' : score > 0 ? score : '0'}
                          </td>
                        )
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* BM-15: Cause of Death Stacked Bars */}
      {activeTab === 'mortality' && (
        <div style={{ background: '#161b22', border: '1px solid #30363d', borderRadius: 8, padding: '12px' }}>
          <div style={{ marginBottom: 10 }}>
            <h4 style={{ margin: 0, fontSize: 13, color: '#e6edf3' }}>Mortality Breakdown Across 10-Day Epochs</h4>
            <span style={{ fontSize: 11, color: '#8b949e' }}>
              Shift in demographic fatality causes as civilization scales from early famine into imperial warfare and plagues.
            </span>
          </div>

          <div style={{ display: 'flex', gap: 12, marginBottom: 10, fontSize: 11, color: '#8b949e', flexWrap: 'wrap' }}>
            <span><span style={{ display: 'inline-block', width: 10, height: 10, background: '#f85149', marginRight: 4, borderRadius: 2 }} /> Combat</span>
            <span><span style={{ display: 'inline-block', width: 10, height: 10, background: '#a371f7', marginRight: 4, borderRadius: 2 }} /> Plague / Disease</span>
            <span><span style={{ display: 'inline-block', width: 10, height: 10, background: '#e3b341', marginRight: 4, borderRadius: 2 }} /> Predation</span>
            <span><span style={{ display: 'inline-block', width: 10, height: 10, background: '#f0883e', marginRight: 4, borderRadius: 2 }} /> Starvation</span>
            <span><span style={{ display: 'inline-block', width: 10, height: 10, background: '#8b949e', marginRight: 4, borderRadius: 2 }} /> Natural / Other</span>
          </div>

          {mortalityBuckets.length === 0 ? (
            <div style={{ color: '#8b949e', fontSize: 12 }}>No casualty data recorded.</div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {mortalityBuckets.map((b) => {
                const total = Math.max(1, b.total)
                const pCombat = (b.combat / total) * 100
                const pDisease = (b.disease / total) * 100
                const pPred = (b.predation / total) * 100
                const pHunger = (b.hunger / total) * 100
                const pOther = (b.other / total) * 100

                return (
                  <div key={b.era} style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11 }}>
                      <span style={{ color: '#e6edf3', fontWeight: 600 }}>{b.era}</span>
                      <span style={{ color: '#8b949e' }}>{b.total} casualties</span>
                    </div>
                    <div style={{ display: 'flex', height: 14, borderRadius: 4, overflow: 'hidden', background: '#0d1117' }}>
                      {pCombat > 0 && <div style={{ width: `${pCombat}%`, background: '#f85149' }} title={`Combat: ${b.combat} (${pCombat.toFixed(0)}%)`} />}
                      {pDisease > 0 && <div style={{ width: `${pDisease}%`, background: '#a371f7' }} title={`Plague: ${b.disease} (${pDisease.toFixed(0)}%)`} />}
                      {pPred > 0 && <div style={{ width: `${pPred}%`, background: '#e3b341' }} title={`Predation: ${b.predation} (${pPred.toFixed(0)}%)`} />}
                      {pHunger > 0 && <div style={{ width: `${pHunger}%`, background: '#f0883e' }} title={`Starvation: ${b.hunger} (${pHunger.toFixed(0)}%)`} />}
                      {pOther > 0 && <div style={{ width: `${pOther}%`, background: '#8b949e' }} title={`Other: ${b.other} (${pOther.toFixed(0)}%)`} />}
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </div>
      )}

      {/* BM-16: Faith Index Over Time */}
      {activeTab === 'faith' && (
        <div style={{ background: '#161b22', border: '1px solid #30363d', borderRadius: 8, padding: '12px' }}>
          <div style={{ marginBottom: 10 }}>
            <h4 style={{ margin: 0, fontSize: 13, color: '#e6edf3' }}>Theological & Miraculous Activity</h4>
            <span style={{ fontSize: 11, color: '#8b949e' }}>
              Tracking consecrated temples, celestial avatar miracles, and cosmic epiphanies across epochs.
            </span>
          </div>

          {faithBuckets.length === 0 ? (
            <div style={{ color: '#8b949e', fontSize: 12 }}>No spiritual manifestations recorded.</div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              {faithBuckets.map((b) => (
                <div
                  key={b.era}
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    padding: '6px 8px',
                    background: '#0d1117',
                    border: '1px solid #21262d',
                    borderRadius: 6,
                    fontSize: 11.5,
                  }}
                >
                  <span style={{ fontWeight: 600, color: '#e6edf3' }}>{b.era}</span>
                  <div style={{ display: 'flex', gap: 10, color: '#8b949e' }}>
                    <span>🏛️ <b>{b.temples}</b> Temples</span>
                    <span>🌸 <b>{b.miracles}</b> Miracles</span>
                    <span>🔮 <b>{b.epiphanies}</b> Epiphanies</span>
                    <span style={{ color: '#e3b341', fontWeight: 700 }}>Score: {b.score}</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
