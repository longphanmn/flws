import { useI18n } from '../i18n'
import MetricCard from './MetricCard'

interface Props {
  data: any
}

export default function SociologyTab({ data }: Props) {
  const { t } = useI18n()
  const hegemony = data?.hegemony ?? {}
  const gini = data?.gini ?? {}
  const trade = data?.trade ?? {}
  const casus = data?.casus ?? {}

  const hhi = hegemony.hhi ?? 0.0
  const clanCount = hegemony.clan_count ?? 0
  const territories: Record<string, any> = hegemony.territories ?? {}

  const larderGini = gini.larder_gini ?? 0.0
  const basketGini = gini.basket_gini ?? 0.0

  const marketCount = trade.market_count ?? 0
  const caravanRoutes = trade.caravan_routes ?? 0

  const warRisk = casus.war_risk ?? 0.0
  const tensions: any[] = casus.tensions ?? []

  const hhiStatus = hhi > 0.4 ? 'critical' : hhi > 0.25 ? 'warning' : 'healthy'
  const hhiLabel = hhi > 0.4
    ? t('analytics.society.hhi_monopoly')
    : hhi > 0.25
    ? t('analytics.society.hhi_oligopoly')
    : t('analytics.society.hhi_plural')

  const giniStatus = larderGini > 0.5 ? 'critical' : larderGini > 0.35 ? 'warning' : 'healthy'
  const giniLabel = larderGini > 0.5
    ? t('analytics.society.gini_hoarding')
    : larderGini > 0.35
    ? t('analytics.society.gini_unequal')
    : t('analytics.society.gini_egalitarian')

  const warStatus = warRisk > 0.7 ? 'critical' : warRisk > 0.3 ? 'warning' : 'healthy'
  const warLabel = warRisk > 0.7
    ? t('analytics.society.war_imminent')
    : warRisk > 0.3
    ? t('analytics.society.war_tense')
    : t('analytics.society.war_peaceful')

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      {/* 6 Stats: 3 rows with 2 columns on web desktop */}
      <div className="analytics-grid-2col">
        <MetricCard
          title={t('analytics.society.hhi_title')}
          value={hhi.toFixed(3)}
          subvalue={t('analytics.society.active_clans', { count: clanCount })}
          status={hhiStatus}
          statusLabel={hhiLabel}
          icon="👑"
          hint={t('analytics.hints.hhi')}
        />
        <MetricCard
          title={t('analytics.society.larder_gini_title')}
          value={larderGini.toFixed(3)}
          subvalue={t('analytics.society.granary_disparity')}
          status={giniStatus}
          statusLabel={giniLabel}
          icon="⚖️"
          hint={t('analytics.hints.larder_gini')}
        />
        <MetricCard
          title={t('analytics.society.basket_gini_title')}
          value={basketGini.toFixed(3)}
          subvalue={t('analytics.society.foraging_disparity')}
          status="neutral"
          icon="🧺"
          hint={t('analytics.hints.basket_gini')}
        />
        <MetricCard
          title={t('analytics.society.war_risk_title')}
          value={`${(warRisk * 100).toFixed(0)}%`}
          subvalue={t('analytics.society.feud_escalation')}
          status={warStatus}
          statusLabel={warLabel}
          icon="⚔️"
          hint={t('analytics.society.war_hint')}
        />
        <MetricCard
          title={t('analytics.society.trade_markets_title')}
          value={marketCount}
          subvalue={t('analytics.society.trade_markets_sub')}
          status="neutral"
          icon="🎪"
          hint={t('analytics.society.trade_markets_hint')}
        />
        <MetricCard
          title={t('analytics.society.caravan_routes_title')}
          value={caravanRoutes}
          subvalue={t('analytics.society.caravan_routes_sub')}
          status="neutral"
          icon="🐪"
          hint={t('analytics.society.caravan_routes_hint')}
        />
      </div>

      {/* Clan Hegemony & Territory Breakdown */}
      <div
        style={{
          background: '#161b22',
          border: '1px solid #30363d',
          borderRadius: 8,
          padding: '10px 12px',
          display: 'flex',
          flexDirection: 'column',
          gap: 8,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <span style={{ fontSize: 13 }}>🏰</span>
            <span style={{ fontSize: 11, fontWeight: 700, color: '#c9d1d9', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
              {t('analytics.society.demographics_title')}
            </span>
          </div>
        </div>

        {Object.keys(territories).length === 0 ? (
          <div style={{ padding: '8px', color: '#8b949e', fontSize: 10, textAlign: 'center' }}>
            {t('analytics.society.no_settlements')}
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {Object.entries(territories).map(([cid, tInfo]) => {
              const domPct = ((tInfo.dominance ?? 0) * 100).toFixed(1)
              return (
                <div key={cid} style={{ display: 'grid', gridTemplateColumns: '80px 1fr 140px', alignItems: 'center', gap: 8, fontSize: 10 }}>
                  <span style={{ fontWeight: 600, color: '#f0f6fc' }}>
                    {t('analytics.society.clan_label', { id: cid })}
                  </span>
                  <div style={{ height: 6, background: '#0d1117', borderRadius: 3, overflow: 'hidden' }}>
                    <div style={{ height: '100%', width: `${domPct}%`, background: '#58a6ff', borderRadius: 3 }} />
                  </div>
                  <span style={{ textAlign: 'right', color: '#8b949e', fontSize: 10 }}>
                    {t('analytics.society.clan_pop_houses', { pop: tInfo.population, pct: domPct, houses: tInfo.houses })}
                  </span>
                </div>
              )
            })}
          </div>
        )}
      </div>

      {/* Diplomatic Tensions Radar */}
      {tensions.length > 0 && (
        <div
          style={{
            background: '#161b22',
            border: '1px solid #da363344',
            borderRadius: 8,
            padding: '10px 12px',
            display: 'flex',
            flexDirection: 'column',
            gap: 6,
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <span style={{ fontSize: 13 }}>🔥</span>
            <span style={{ fontSize: 11, fontWeight: 700, color: '#f85149', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
              {t('analytics.society.tensions_title')}
            </span>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            {tensions.map((tItem, idx) => (
              <div
                key={idx}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  background: '#0d1117',
                  border: '1px solid #21262d',
                  borderRadius: 4,
                  padding: '4px 8px',
                  fontSize: 10,
                }}
              >
                <span style={{ color: '#e6edf3', fontWeight: 600 }}>
                  {t('analytics.society.clan_label', { id: tItem.a })} ⚔️ {t('analytics.society.clan_label', { id: tItem.b })}
                </span>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span style={{ color: '#8b949e' }}>{t('analytics.society.score_label', { score: tItem.score })}</span>
                  <span style={{ color: '#f85149', fontWeight: 700 }}>
                    {t('analytics.society.tension_label', { pct: (tItem.tension * 100).toFixed(0) })}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
