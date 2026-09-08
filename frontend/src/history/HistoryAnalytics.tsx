import { useMemo, useState } from 'react'
import type { DayRecord } from './WorldHistoryModal'
import { useI18n } from '../i18n'

interface Props {
  dayRecords: DayRecord[]
  clans: Record<string, any>
  rawEvents: any[]
}

export default function HistoryAnalytics({ dayRecords: _dayRecords, clans, rawEvents }: Props) {
  const { t } = useI18n()
  const [activeTab, setActiveTab] = useState<'rivalry' | 'mortality' | 'faith'>('rivalry')

  // Clan Rivalry Matrix
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

  // Cause of death breakdown per 10-day era buckets
  const mortalityBuckets = useMemo(() => {
    const buckets: Record<number, { era: string; combat: number; disease: number; predation: number; hunger: number; other: number; total: number }> = {}

    for (const ev of rawEvents) {
      if (ev.type === 'death') {
        const d = Math.floor(ev.tick / 1200)
        const bucketId = Math.floor(d / 10)
        if (!buckets[bucketId]) {
          buckets[bucketId] = {
            era: t('history.dayRange', { start: bucketId * 10, end: (bucketId + 1) * 10 - 1 }),
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
  }, [rawEvents, t])

  // Faith index over time (temples, miracles, epiphanies per 5 days)
  const faithBuckets = useMemo(() => {
    const buckets: Record<number, { era: string; temples: number; miracles: number; epiphanies: number; score: number }> = {}

    for (const ev of rawEvents) {
      const d = Math.floor(ev.tick / 1200)
      const bId = Math.floor(d / 5)
      if (!buckets[bId]) {
        buckets[bId] = {
          era: t('history.dayRange', { start: bId * 5, end: (bId + 1) * 5 - 1 }),
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
  }, [rawEvents, t])

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
            background: activeTab === 'rivalry' ? 'rgba(56,139,253,0.15)' : '#161b22',
            color: activeTab === 'rivalry' ? '#58a6ff' : '#8b949e',
            borderColor: activeTab === 'rivalry' ? 'rgba(88,166,255,0.4)' : '#30363d',
            fontWeight: activeTab === 'rivalry' ? 700 : 500,
            cursor: 'pointer',
            padding: '5px 12px',
            borderRadius: 6,
            fontSize: 12,
          }}
        >
          {t('history.analytics.rivalryTab')}
        </button>
        <button
          type="button"
          className="chip"
          onClick={() => setActiveTab('mortality')}
          style={{
            background: activeTab === 'mortality' ? 'rgba(56,139,253,0.15)' : '#161b22',
            color: activeTab === 'mortality' ? '#58a6ff' : '#8b949e',
            borderColor: activeTab === 'mortality' ? 'rgba(88,166,255,0.4)' : '#30363d',
            fontWeight: activeTab === 'mortality' ? 700 : 500,
            cursor: 'pointer',
            padding: '5px 12px',
            borderRadius: 6,
            fontSize: 12,
          }}
        >
          {t('history.analytics.mortalityTab')}
        </button>
        <button
          type="button"
          className="chip"
          onClick={() => setActiveTab('faith')}
          style={{
            background: activeTab === 'faith' ? 'rgba(56,139,253,0.15)' : '#161b22',
            color: activeTab === 'faith' ? '#58a6ff' : '#8b949e',
            borderColor: activeTab === 'faith' ? 'rgba(88,166,255,0.4)' : '#30363d',
            fontWeight: activeTab === 'faith' ? 700 : 500,
            cursor: 'pointer',
            padding: '5px 12px',
            borderRadius: 6,
            fontSize: 12,
          }}
        >
          {t('history.analytics.faithTab')}
        </button>
      </div>

      {/* Rivalry Matrix */}
      {activeTab === 'rivalry' && (
        <div style={{ background: '#161b22', border: '1px solid #30363d', borderRadius: 8, padding: '12px' }}>
          <div style={{ marginBottom: 10 }}>
            <h4 style={{ margin: 0, fontSize: 13, color: '#e6edf3' }}>{t('history.analytics.rivalryTitle')}</h4>
            <span style={{ fontSize: 11, color: '#8b949e' }}>
              {t('history.analytics.rivalryDesc')}
            </span>
          </div>

          {clanList.length === 0 ? (
            <div style={{ color: '#8b949e', fontSize: 12 }}>{t('history.analytics.noClans')}</div>
          ) : (
            <div style={{ overflowX: 'auto' }}>
              <table style={{ borderCollapse: 'collapse', fontSize: 11, width: '100%' }}>
                <thead>
                  <tr>
                    <th style={{ padding: '6px 8px', textAlign: 'left', color: '#8b949e' }}>{t('history.analytics.clanCol')}</th>
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
                            title={isSelf ? t('history.analytics.self') : `${c1.name} vs ${c2.name}: ${score}`}
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

      {/* Cause of Death Stacked Bars */}
      {activeTab === 'mortality' && (
        <div style={{ background: '#161b22', border: '1px solid #30363d', borderRadius: 8, padding: '12px' }}>
          <div style={{ marginBottom: 10 }}>
            <h4 style={{ margin: 0, fontSize: 13, color: '#e6edf3' }}>{t('history.analytics.mortalityTitle')}</h4>
            <span style={{ fontSize: 11, color: '#8b949e' }}>
              {t('history.analytics.mortalityDesc')}
            </span>
          </div>

          <div style={{ display: 'flex', gap: 12, marginBottom: 10, fontSize: 11, color: '#8b949e', flexWrap: 'wrap' }}>
            <span><span style={{ display: 'inline-block', width: 10, height: 10, background: '#f85149', marginRight: 4, borderRadius: 2 }} /> {t('history.analytics.combat')}</span>
            <span><span style={{ display: 'inline-block', width: 10, height: 10, background: '#a371f7', marginRight: 4, borderRadius: 2 }} /> {t('history.analytics.disease')}</span>
            <span><span style={{ display: 'inline-block', width: 10, height: 10, background: '#e3b341', marginRight: 4, borderRadius: 2 }} /> {t('history.analytics.predation')}</span>
            <span><span style={{ display: 'inline-block', width: 10, height: 10, background: '#f0883e', marginRight: 4, borderRadius: 2 }} /> {t('history.analytics.hunger')}</span>
            <span><span style={{ display: 'inline-block', width: 10, height: 10, background: '#8b949e', marginRight: 4, borderRadius: 2 }} /> {t('history.analytics.other')}</span>
          </div>

          {mortalityBuckets.length === 0 ? (
            <div style={{ color: '#8b949e', fontSize: 12 }}>{t('history.analytics.noCasualties')}</div>
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
                      <span style={{ color: '#8b949e' }}>{t('history.analytics.casualtiesCount', { count: b.total })}</span>
                    </div>
                    <div style={{ display: 'flex', height: 14, borderRadius: 4, overflow: 'hidden', background: '#0d1117' }}>
                      {pCombat > 0 && <div style={{ width: `${pCombat}%`, background: '#f85149' }} title={`${t('history.analytics.combat')}: ${b.combat} (${pCombat.toFixed(0)}%)`} />}
                      {pDisease > 0 && <div style={{ width: `${pDisease}%`, background: '#a371f7' }} title={`${t('history.analytics.disease')}: ${b.disease} (${pDisease.toFixed(0)}%)`} />}
                      {pPred > 0 && <div style={{ width: `${pPred}%`, background: '#e3b341' }} title={`${t('history.analytics.predation')}: ${b.predation} (${pPred.toFixed(0)}%)`} />}
                      {pHunger > 0 && <div style={{ width: `${pHunger}%`, background: '#f0883e' }} title={`${t('history.analytics.hunger')}: ${b.hunger} (${pHunger.toFixed(0)}%)`} />}
                      {pOther > 0 && <div style={{ width: `${pOther}%`, background: '#8b949e' }} title={`${t('history.analytics.other')}: ${b.other} (${pOther.toFixed(0)}%)`} />}
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </div>
      )}

      {/* Faith Index Over Time */}
      {activeTab === 'faith' && (
        <div style={{ background: '#161b22', border: '1px solid #30363d', borderRadius: 8, padding: '12px' }}>
          <div style={{ marginBottom: 10 }}>
            <h4 style={{ margin: 0, fontSize: 13, color: '#e6edf3' }}>{t('history.analytics.faithTitle')}</h4>
            <span style={{ fontSize: 11, color: '#8b949e' }}>
              {t('history.analytics.faithDesc')}
            </span>
          </div>

          {faithBuckets.length === 0 ? (
            <div style={{ color: '#8b949e', fontSize: 12 }}>{t('history.analytics.noFaith')}</div>
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
                    <span>🏛️ <b>{b.temples}</b> {t('history.analytics.temples')}</span>
                    <span>🌸 <b>{b.miracles}</b> {t('history.analytics.miracles')}</span>
                    <span>🔮 <b>{b.epiphanies}</b> {t('history.analytics.epiphanies')}</span>
                    <span style={{ color: '#e3b341', fontWeight: 700 }}>{t('history.analytics.faithScore')}: {b.score}</span>
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
