import { useEffect, useState } from 'react'
import { useI18n } from '../i18n'

type WikiData = {
  laws: string[]
  routes: string[]
  presets: Record<string, Record<string, any>>
  current_preset?: string
  law_details: Record<string, { type: string; default: any; hint?: string }>
  overview: string
}

function matchPreset(laws: Record<string, any> | null, presets?: Record<string, Record<string, any>>): string | null {
  if (!laws || !presets) return null
  for (const [name, p] of Object.entries(presets)) {
    if (Object.entries(p).every(([k, v]) => laws[k] === v)) return name
  }
  for (const [name, p] of Object.entries(presets)) {
    if (
      laws.food_count === p.food_count &&
      laws.carrying_capacity === p.carrying_capacity &&
      laws.max_population === p.max_population
    ) {
      return name
    }
  }
  return null
}

export default function Wiki({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { t, lang } = useI18n()
  const activeLang = lang === 'vn' ? 'vi' : lang
  const [data, setData] = useState<WikiData | null>(null)
  const [tab, setTab] = useState<'guide' | 'book' | 'api' | 'laws' | 'presets'>('guide')
  const [q, setQ] = useState('')
  const [laws, setLaws] = useState<Record<string, any> | null>(null)
  const [currentPreset, setCurrentPreset] = useState<string | null>(null)

  useEffect(() => {
    if (!open) return
    Promise.all([
      fetch(`/api/wiki?lang=${activeLang}`).then(r => r.json()).catch(() => null),
      fetch('/api/laws').then(r => r.json()).catch(() => null),
      fetch('/api/presets').then(r => r.json()).catch(() => null),
    ]).then(([wikiData, lawsData, presetsData]) => {
      if (wikiData) setData(wikiData)
      if (lawsData) setLaws(lawsData)
      if (presetsData?.current) setCurrentPreset(presetsData.current)
      else if (wikiData?.current_preset) setCurrentPreset(wikiData.current_preset)
    })
  }, [open, activeLang])

  if (!open) return null

  const activePreset = matchPreset(laws, data?.presets) || currentPreset || data?.current_preset || null

  // filter helpers
  const match = (s: string) => !q || s.toLowerCase().includes(q.toLowerCase())

  return (
    <div className="wiki-backdrop" onClick={onClose}>
      <div className="wiki-panel" onClick={e => e.stopPropagation()}>
        <header className="god-head" style={{ position: 'sticky', top: 0, background: '#0d1117', zIndex: 1, paddingBottom: 8 }}>
          <h2>{t('wiki.title')}</h2>
          <button className="god-close" onClick={onClose} aria-label="close">×</button>
        </header>

        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center', marginBottom: 12 }}>
          <input
            placeholder={t('wiki.searchPlaceholder')}
            value={q}
            onChange={e => setQ(e.target.value)}
            style={{ flex: 1, minWidth: 160, background: '#161b22', color: '#e6edf3', border: '1px solid #30363d', borderRadius: 6, padding: '6px 8px' }}
          />
          <a href={`/wiki?lang=${activeLang}`} target="_blank" rel="noreferrer" className="chip" style={{ border: '1px solid #30363d', borderRadius: 6, padding: '4px 8px', background: '#161b22', color: '#58a6ff', textDecoration: 'none' }}>/wiki</a>
          <a href="/docs" target="_blank" rel="noreferrer" className="chip" style={{ border: '1px solid #30363d', borderRadius: 6, padding: '4px 8px', background: '#161b22', color: '#58a6ff', textDecoration: 'none' }}>/docs</a>
          <a href="/openapi.json" target="_blank" rel="noreferrer" className="chip" style={{ border: '1px solid #30363d', borderRadius: 6, padding: '4px 8px', background: '#161b22', color: '#58a6ff', textDecoration: 'none' }}>/openapi.json</a>
        </div>

        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 12 }}>
          {(['guide', 'book', 'api', 'laws', 'presets'] as const).map(tt => (
            <button key={tt} onClick={() => setTab(tt)} style={{ background: tab === tt ? '#1f6feb' : '#21262d', color: tab === tt ? '#fff' : '#c9d1d9', borderColor: tab === tt ? '#1f6feb' : '#30363d' }}>
              {t(`wiki.tabs.${tt}`)}
            </button>
          ))}
        </div>

        {tab === 'guide' && (
          <div style={{ fontSize: 13, lineHeight: 1.6, color: '#c9d1d9' }}>
            <h3 style={{ color: '#e6edf3', marginTop: 0 }}>{t('wiki.aboutTitle')}</h3>
            <p>{t('wiki.aboutDesc')}</p>

            <h4 style={{ color: '#e6edf3' }}>{t('wiki.mechanicsTitle')}</h4>
            <ul>
              <li>{t('wiki.sphereDesc')}</li>
              <li>{t('wiki.evolutionDesc')}</li>
              <li>{t('wiki.lifeStagesDesc')}</li>
              <li>{t('wiki.settlementsDesc')}</li>
            </ul>

            <h4 style={{ color: '#e6edf3' }}>{t('wiki.featuresTitle')}</h4>
            <ul>
              <li>{t('wiki.spherePanelDesc')}</li>
              <li>{t('wiki.inspectorDesc')}</li>
              <li>{t('wiki.controlsDesc')}</li>
            </ul>

            <h4 style={{ color: '#38bdf8', marginTop: 18, borderBottom: '1px solid #30363d', paddingBottom: 4 }}>
              🔭 {t('wiki.lensesTitle') || 'Map Lenses & Visual Perspectives'}
            </h4>
            <p style={{ margin: '6px 0 10px' }}>
              {t('wiki.lensesIntro')}
            </p>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10, margin: '10px 0 16px' }}>
              <div style={{ background: '#161b22', border: '1px solid #30363d', borderRadius: 8, padding: '8px 12px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontWeight: 600, color: '#38bdf8', marginBottom: 4 }}>
                  <span style={{ background: '#38bdf8', color: '#0d1117', borderRadius: 4, padding: '1px 6px', fontSize: 11, fontWeight: 700 }}>1</span>
                  <span>{t('wiki.lensClassicName')}</span>
                </div>
                <div style={{ fontSize: 12, color: '#8b949e', marginBottom: 6 }}>{t('wiki.lensClassicDesc')}</div>
                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', fontSize: 11 }}>
                  <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}><span style={{ width: 8, height: 8, borderRadius: '50%', background: '#ff70a6' }} /> Women</span>
                  <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}><span style={{ width: 8, height: 8, borderRadius: '50%', background: '#f97316' }} /> Soldiers</span>
                  <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}><span style={{ width: 8, height: 8, borderRadius: '50%', background: '#facc15' }} /> Artisans</span>
                  <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}><span style={{ width: 8, height: 8, borderRadius: '50%', background: '#4ade80' }} /> Gentlemen</span>
                  <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}><span style={{ width: 8, height: 8, borderRadius: '50%', background: '#60a5fa' }} /> Nobles</span>
                  <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}><span style={{ width: 8, height: 8, borderRadius: '50%', background: '#a78bfa' }} /> Priests</span>
                </div>
              </div>

              <div style={{ background: '#161b22', border: '1px solid #30363d', borderRadius: 8, padding: '8px 12px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontWeight: 600, color: '#f43f5e', marginBottom: 4 }}>
                  <span style={{ background: '#f43f5e', color: '#0d1117', borderRadius: 4, padding: '1px 6px', fontSize: 11, fontWeight: 700 }}>2</span>
                  <span>{t('wiki.lensMutantsName')}</span>
                </div>
                <div style={{ fontSize: 12, color: '#8b949e', marginBottom: 6 }}>{t('wiki.lensMutantsDesc')}</div>
                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', fontSize: 11 }}>
                  <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}><span style={{ width: 8, height: 8, borderRadius: '50%', background: '#64748b' }} /> Normal (&lt;0.04)</span>
                  <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}><span style={{ width: 8, height: 8, borderRadius: '50%', background: '#06b6d4' }} /> Minor (0.04-0.12)</span>
                  <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}><span style={{ width: 8, height: 8, borderRadius: '50%', background: '#a855f7' }} /> Aberrant (0.12-0.22)</span>
                  <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}><span style={{ width: 8, height: 8, borderRadius: '50%', background: '#f43f5e' }} /> Extreme (&ge;0.22)</span>
                </div>
              </div>

              <div style={{ background: '#161b22', border: '1px solid #30363d', borderRadius: 8, padding: '8px 12px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontWeight: 600, color: '#10b981', marginBottom: 4 }}>
                  <span style={{ background: '#10b981', color: '#0d1117', borderRadius: 4, padding: '1px 6px', fontSize: 11, fontWeight: 700 }}>3</span>
                  <span>{t('wiki.lensGenerationsName')}</span>
                </div>
                <div style={{ fontSize: 12, color: '#8b949e', marginBottom: 6 }}>{t('wiki.lensGenerationsDesc')}</div>
                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', fontSize: 11 }}>
                  <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}><span style={{ width: 8, height: 8, borderRadius: '50%', background: '#38bdf8' }} /> Genesis (&le;2)</span>
                  <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}><span style={{ width: 8, height: 8, borderRadius: '50%', background: '#10b981' }} /> Pioneer (&lt;10)</span>
                  <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}><span style={{ width: 8, height: 8, borderRadius: '50%', background: '#c084fc' }} /> Dynastic (&lt;25)</span>
                  <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}><span style={{ width: 8, height: 8, borderRadius: '50%', background: '#f59e0b' }} /> Ancient (&lt;50)</span>
                  <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}><span style={{ width: 8, height: 8, borderRadius: '50%', background: '#fef08a' }} /> Millennial (&ge;50)</span>
                </div>
              </div>

              <div style={{ background: '#161b22', border: '1px solid #30363d', borderRadius: 8, padding: '8px 12px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontWeight: 600, color: '#c084fc', marginBottom: 4 }}>
                  <span style={{ background: '#c084fc', color: '#0d1117', borderRadius: 4, padding: '1px 6px', fontSize: 11, fontWeight: 700 }}>4</span>
                  <span>{t('wiki.lensDynastyName')}</span>
                </div>
                <div style={{ fontSize: 12, color: '#8b949e', marginBottom: 6 }}>{t('wiki.lensDynastyDesc')}</div>
                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', fontSize: 11 }}>
                  <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}><span style={{ width: 8, height: 8, borderRadius: '50%', background: '#58a6ff' }} /> Clan Sworn (Crest Color)</span>
                  <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}><span style={{ width: 8, height: 8, borderRadius: '50%', background: '#475569' }} /> Clanless / Neutral</span>
                </div>
              </div>
            </div>

            <h4 style={{ color: '#e6edf3' }}>{t('wiki.quickstartTitle')}</h4>
            <pre style={{ background: '#161b22', padding: 12, borderRadius: 6, overflow: 'auto', border: '1px solid #30363d' }}><code>{`./run.sh
# Frontend: http://localhost:5173
# Backend API: http://localhost:8000/docs
# Living Wiki: http://localhost:8000/wiki`}</code></pre>

            <h4 style={{ color: '#e6edf3' }}>{t('wiki.docsTitle')}</h4>
            <ul>
              <li><a href={`/wiki?lang=${activeLang}`}>{t('wiki.docWiki')}</a></li>
              <li><a href="/docs">{t('wiki.docApi')}</a> + <a href="/openapi.json">/openapi.json</a></li>
              <li><a href="/docs/god-laws.md">{t('wiki.docLaws')}</a></li>
            </ul>
          </div>
        )}

        {tab === 'book' && (
          <div style={{ fontSize: 13, lineHeight: 1.6, color: '#c9d1d9' }}>
            <h3 style={{ color: '#e6edf3', marginTop: 0 }}>{t('wiki.bookTitle')}</h3>
            <p>{t('wiki.bookDesc')}</p>

            <h4 style={{ color: '#e3b341', borderBottom: '1px solid #30363d', paddingBottom: 4 }}>{t('wiki.bookSection1')}</h4>
            <div style={{ overflowX: 'auto', margin: '8px 0' }}>
              <table style={{ width: '100%', fontSize: 12, borderCollapse: 'collapse' }}>
                <thead>
                  <tr>
                    <th style={{ textAlign: 'left', padding: '6px 8px', background: '#161b22', color: '#e6edf3', borderBottom: '1px solid #30363d' }}>{t('wiki.dimCol')}</th>
                    <th style={{ textAlign: 'left', padding: '6px 8px', background: '#161b22', color: '#e6edf3', borderBottom: '1px solid #30363d' }}>{t('wiki.bookCol')}</th>
                    <th style={{ textAlign: 'left', padding: '6px 8px', background: '#161b22', color: '#e6edf3', borderBottom: '1px solid #30363d' }}>{t('wiki.simCol')}</th>
                  </tr>
                </thead>
                <tbody>
                  <tr style={{ borderBottom: '1px solid #21262d' }}>
                    <td style={{ padding: '6px 8px', fontWeight: 600, color: '#e6edf3' }}>{t('wiki.hierarchy')}</td>
                    <td style={{ padding: '6px 8px' }}><em>{t('wiki.hierarchyBook')}</em></td>
                    <td style={{ padding: '6px 8px' }}>{t('wiki.hierarchySim')}</td>
                  </tr>
                  <tr style={{ borderBottom: '1px solid #21262d' }}>
                    <td style={{ padding: '6px 8px', fontWeight: 600, color: '#ff9bce' }}>{t('wiki.women')}</td>
                    <td style={{ padding: '6px 8px' }}>{t('wiki.womenBook')}</td>
                    <td style={{ padding: '6px 8px' }}>{t('wiki.womenSim')}</td>
                  </tr>
                  <tr style={{ borderBottom: '1px solid #21262d' }}>
                    <td style={{ padding: '6px 8px', fontWeight: 600, color: '#ff7b72' }}>{t('wiki.soldiers')}</td>
                    <td style={{ padding: '6px 8px' }}>{t('wiki.soldiersBook')}</td>
                    <td style={{ padding: '6px 8px' }}>{t('wiki.soldiersSim')}</td>
                  </tr>
                  <tr style={{ borderBottom: '1px solid #21262d' }}>
                    <td style={{ padding: '6px 8px', fontWeight: 600, color: '#f2cc60' }}>{t('wiki.artisans')}</td>
                    <td style={{ padding: '6px 8px' }}>{t('wiki.artisansBook')}</td>
                    <td style={{ padding: '6px 8px' }}>{t('wiki.artisansSim')}</td>
                  </tr>
                  <tr style={{ borderBottom: '1px solid #21262d' }}>
                    <td style={{ padding: '6px 8px', fontWeight: 600, color: '#ffa657' }}>{t('wiki.gentlemen')}</td>
                    <td style={{ padding: '6px 8px' }}>{t('wiki.gentlemenBook')}</td>
                    <td style={{ padding: '6px 8px' }}>{t('wiki.gentlemenSim')}</td>
                  </tr>
                  <tr style={{ borderBottom: '1px solid #21262d' }}>
                    <td style={{ padding: '6px 8px', fontWeight: 600, color: '#e6edf3' }}>{t('wiki.priests')}</td>
                    <td style={{ padding: '6px 8px' }}>{t('wiki.priestsBook')}</td>
                    <td style={{ padding: '6px 8px' }}>{t('wiki.priestsSim')}</td>
                  </tr>
                </tbody>
              </table>
            </div>

            <h4 style={{ color: '#e3b341', borderBottom: '1px solid #30363d', paddingBottom: 4, marginTop: 16 }}>{t('wiki.bookSection2')}</h4>
            <p>{t('wiki.bookSection2Desc')}</p>

            <h4 style={{ color: '#e3b341', borderBottom: '1px solid #30363d', paddingBottom: 4, marginTop: 16 }}>{t('wiki.bookSection3')}</h4>
            <p>{t('wiki.bookSection3Desc')}</p>

            <h4 style={{ color: '#e3b341', borderBottom: '1px solid #30363d', paddingBottom: 4, marginTop: 16 }}>{t('wiki.bookSection4')}</h4>
            <p>{t('wiki.bookSection4Desc')}</p>
          </div>
        )}

        {tab === 'api' && (
          <div>
            <h3 style={{ marginTop: 0, color: '#e6edf3' }}>{t('wiki.apiTitle')}</h3>
            <p className="god-note" style={{ color: '#8b949e', fontSize: 12, margin: '4px 0 10px' }}>{t('wiki.apiDesc')}</p>
            <div style={{ maxHeight: 320, overflowY: 'auto', border: '1px solid #30363d', borderRadius: 6 }}>
              <table style={{ width: '100%', fontSize: 12, borderCollapse: 'collapse' }}>
                <thead><tr><th style={{ textAlign: 'left', padding: '8px 10px', background: '#161b22', color: '#e6edf3', borderBottom: '1px solid #30363d' }}>{t('wiki.routeCol')}</th><th style={{ textAlign: 'left', padding: '8px 10px', background: '#161b22', color: '#e6edf3', borderBottom: '1px solid #30363d' }}>{t('wiki.tryCol')}</th></tr></thead>
                <tbody>
                  {(data?.routes ?? []).filter(r => match(r) && r).sort().map(r => (
                    <tr key={r} style={{ borderBottom: '1px solid #21262d' }}>
                      <td style={{ padding: '6px 10px' }}><code>{r || '/'}</code></td>
                      <td style={{ padding: '6px 10px' }}><code style={{ fontSize: 11, wordBreak: 'break-all' }}>{`curl ${location.origin}${r}`}</code></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <h4 style={{ marginTop: 14, color: '#e6edf3' }}>{t('wiki.curlPlayground')}</h4>
            <pre style={{ background: '#161b22', padding: 12, borderRadius: 6, overflow: 'auto', fontSize: 12, border: '1px solid #30363d' }}><code>{`curl ${location.origin}/api/laws
curl -X POST ${location.origin}/api/laws -H 'content-type: application/json' -H 'X-God-Key: <passkey>' -d '{"food_count": 90}'
curl -X POST ${location.origin}/api/presets/sustainable?reset=true -H 'X-God-Key: <passkey>'
curl ${location.origin}/api/state | jq .tick
curl ${location.origin}/api/history?limit=5 | jq`}</code></pre>
          </div>
        )}

        {tab === 'laws' && (
          <div>
            <h3 style={{ marginTop: 0, color: '#e6edf3' }}>{t('wiki.lawsTitle', { count: data?.laws.length ?? 0 })}</h3>
            <p className="god-note" style={{ color: '#8b949e', fontSize: 12, margin: '4px 0 10px' }}>{t('wiki.lawsNote')}</p>

            <div style={{ maxHeight: 380, overflow: 'auto', border: '1px solid #30363d', borderRadius: 6 }}>
              <table style={{ width: '100%', fontSize: 12, borderCollapse: 'collapse', minWidth: 480 }}>
                <thead><tr><th style={{ textAlign: 'left', padding: '8px 10px', background: '#161b22', color: '#e6edf3', borderBottom: '1px solid #30363d' }}>{t('wiki.lawCol')}</th><th style={{ textAlign: 'left', padding: '8px 10px', background: '#161b22', color: '#e6edf3', borderBottom: '1px solid #30363d' }}>{t('wiki.defaultCol')}</th><th style={{ textAlign: 'left', padding: '8px 10px', background: '#161b22', color: '#e6edf3', borderBottom: '1px solid #30363d' }}>{t('wiki.hintCol')}</th></tr></thead>
                <tbody>
                  {(data?.laws ?? []).filter(n => match(n) || (t(`godHints.${n}`) || ((data?.law_details as any)?.[n]?.hint ?? '')).toLowerCase().includes(q.toLowerCase())).sort().map(name => {
                    const det = (data?.law_details as any)?.[name]
                    const cur = (laws as any)?.[name]
                    const hintText = t(`godHints.${name}`) !== `godHints.${name}` ? t(`godHints.${name}`) : det?.hint ?? ''
                    const lawLabel = t(`godLaws.${name}`) !== `godLaws.${name}` ? t(`godLaws.${name}`) : name
                    return (
                      <tr key={name} style={{ borderBottom: '1px solid #21262d' }}>
                        <td style={{ padding: '6px 10px' }}><code>{name}</code> <span style={{ color: '#8b949e', fontSize: 11 }}>({lawLabel})</span></td>
                        <td style={{ padding: '6px 10px', color: '#ffa657' }}>{String(cur ?? det?.default ?? '—')}</td>
                        <td style={{ padding: '6px 10px', fontSize: 11, color: '#c9d1d9', maxWidth: 300 }}>{hintText} <a href="/docs/god-laws.md" style={{ color: '#58a6ff', fontSize: 10 }}>md</a> · <a href="/wiki#god-laws" style={{ color: '#58a6ff', fontSize: 10 }}>wiki</a></td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {tab === 'presets' && (
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8, flexWrap: 'wrap', gap: 6 }}>
              <h3 style={{ margin: 0 }}>{t('wiki.presetsTitle')}</h3>
              <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                {activePreset && (
                  <span className="chip" style={{ color: '#3fb950', borderColor: '#3fb950', background: 'rgba(63, 185, 80, 0.15)', fontWeight: 600 }}>
                    {t('god.presets.active', { name: t(`god.presets.${activePreset}`) !== `god.presets.${activePreset}` ? t(`god.presets.${activePreset}`) : activePreset })}
                  </span>
                )}
                <span className="chip" style={{ color: '#8b949e', borderColor: '#30363d', background: '#161b22', fontSize: 11 }}>{t('wiki.readOnly') !== 'wiki.readOnly' ? t('wiki.readOnly') : 'read-only · use ⚖ God Panel to apply'}</span>
              </div>
            </div>
            <p className="god-note" style={{ color: '#8b949e', fontSize: 12, margin: '0 0 10px' }}>{t('wiki.presetsReadOnlyNote') !== 'wiki.presetsReadOnlyNote' ? t('wiki.presetsReadOnlyNote') : 'Presets are displayed for reference — apply via The Sphere (⚖ God Panel).'}</p>
            {data?.presets && Object.entries(data.presets).map(([name, pLaws]) => {
              const isCurrent = activePreset === name
              const presetTitle = t(`god.presets.${name}`) !== `god.presets.${name}` ? t(`god.presets.${name}`) : name
              const presetSub = t(`god.presets.${name}Subtitle`) !== `god.presets.${name}Subtitle` ? t(`god.presets.${name}Subtitle`) : ''
              const presetDesc = t(`god.presets.${name}Desc`) !== `god.presets.${name}Desc` ? t(`god.presets.${name}Desc`) : ''
              return (
                <div key={name} style={{ border: `1px solid ${isCurrent ? '#3fb950' : '#21262d'}`, borderRadius: 6, padding: 10, marginBottom: 8, background: isCurrent ? 'rgba(63, 185, 80, 0.06)' : '#161b22' }}>
                  <div style={{ display: 'flex', gap: 8, alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap' }}>
                    <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                      <b style={{ color: isCurrent ? '#3fb950' : '#e6edf3', fontSize: 13 }}>{presetTitle}</b>
                      <code style={{ fontSize: 11, color: '#8b949e' }}>({name})</code>
                      {presetSub && <span style={{ fontSize: 11, color: '#8b949e' }}>— {presetSub}</span>}
                    </div>
                    {isCurrent && <span className="chip" style={{ color: '#3fb950', borderColor: '#3fb950', background: 'rgba(63,185,80,0.12)', fontSize: 11, fontWeight: 700 }}>● {t('wiki.activeTag') || 'ACTIVE'}</span>}
                  </div>
                  {presetDesc && <p style={{ margin: '4px 0 6px', fontSize: 11, color: '#c9d1d9', lineHeight: 1.4 }}>{presetDesc}</p>}
                  <div style={{ fontSize: 11, color: '#8b949e', marginTop: 6, wordBreak: 'break-all' }}>
                    {Object.entries(pLaws).slice(0, 8).map(([k, v]) => <span key={k} style={{ marginRight: 8 }}><code>{k}={String(v)}</code></span>)}
                    {Object.keys(pLaws).length > 8 && <span>{t('wiki.moreLaws', { count: Object.keys(pLaws).length - 8 })}</span>}
                  </div>
                </div>
              )
            })}
          </div>
        )}

        <div style={{ marginTop: 16, paddingTop: 12, borderTop: '1px solid #21262d', fontSize: 11, color: '#8b949e', lineHeight: 1.5 }}>
          {t('wiki.footerLive', { laws: data?.laws.length ?? 0, routes: data?.routes.length ?? 0, presets: Object.keys(data?.presets ?? {}).length })} · <a href="/wiki">/wiki HTML</a> · <a href="/api/wiki">/api/wiki JSON</a>
          <br />{t('wiki.developedBy')} <strong>Long Phan</strong> — <a href="mailto:long@minhnhan.in">long@minhnhan.in</a> · Demo: <a href="https://world.minhnhan.in">world.minhnhan.in</a>
          <br /><span style={{ opacity: 0.85 }}>{t('wiki.inspiration')}</span>
        </div>
      </div>
    </div>
  )
}

