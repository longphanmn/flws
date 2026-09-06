import { useI18n } from '../i18n'
import MetricCard from './MetricCard'

interface Props {
  data: any
}

export default function CrisisTab({ data }: Props) {
  const { t } = useI18n()
  const famine = data?.famine ?? {}
  const extinction = data?.extinction ?? {}
  const unrest = data?.unrest ?? {}

  const horizon = famine.horizon_ticks ?? 9999
  const totalLarder = famine.larder ?? 0
  const burnRate = famine.burn_rate ?? 0
  const regrowth = famine.regrowth ?? 0

  const ne = extinction.Ne ?? 0
  const fertileFemales = extinction.fertile_females ?? 0
  const males = extinction.males ?? 0
  const extAlarm = extinction.alarm ?? false

  const unrestScore = unrest.unrest_score ?? 0
  const schismRisk = unrest.schism_risk ?? false
  const crowding = unrest.crowding ?? 0
  const hungry = unrest.hungry ?? 0
  const tenseClans = unrest.tense_clans ?? 0

  const famineStatus = horizon < 300 ? 'critical' : horizon < 1000 ? 'warning' : 'healthy'
  const famineLabel = horizon < 300
    ? t('analytics.crisis.famine_imminent')
    : horizon < 1000
    ? t('analytics.crisis.famine_lean')
    : t('analytics.crisis.famine_secure')

  const neStatus = extAlarm ? 'critical' : ne < 18 ? 'warning' : 'healthy'
  const neLabel = extAlarm
    ? t('analytics.crisis.ext_cliff')
    : ne < 18
    ? t('analytics.crisis.ext_vulnerable')
    : t('analytics.crisis.ext_viable')

  const unrestStatus = schismRisk ? 'critical' : unrestScore > 5 ? 'warning' : 'healthy'
  const unrestLabel = schismRisk
    ? t('analytics.crisis.unrest_schism')
    : unrestScore > 5
    ? t('analytics.crisis.unrest_tense')
    : t('analytics.crisis.unrest_stable')

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      {/* Crisis Critical Alerts Banner */}
      {(extAlarm || schismRisk || horizon < 300) && (
        <div
          style={{
            background: 'linear-gradient(135deg, #331919 0%, #201010 100%)',
            border: '1px solid #f85149',
            borderRadius: 8,
            padding: '10px 12px',
            display: 'flex',
            flexDirection: 'column',
            gap: 6,
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <span style={{ fontSize: 16 }}>⚠️</span>
            <span style={{ fontSize: 12, fontWeight: 700, color: '#f85149', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
              {t('analytics.crisis.threat_warning')}
            </span>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 2, fontSize: 11, color: '#e6edf3' }}>
            {extAlarm && <div dangerouslySetInnerHTML={{ __html: t('analytics.crisis.ext_danger_desc', { ne, females: fertileFemales, males }) }} />}
            {horizon < 300 && <div dangerouslySetInnerHTML={{ __html: t('analytics.crisis.starve_threat_desc', { horizon }) }} />}
            {schismRisk && <div dangerouslySetInnerHTML={{ __html: t('analytics.crisis.schism_threat_desc', { score: unrestScore }) }} />}
          </div>
        </div>
      )}

      {/* Early Warning Cards Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 8 }}>
        <MetricCard
          title={t('analytics.crisis.famine_horizon_title')}
          value={horizon >= 9999 ? '∞' : `${horizon} t`}
          subvalue={t('analytics.crisis.famine_horizon_sub', { larder: totalLarder.toFixed(0), burn: burnRate.toFixed(1) })}
          status={famineStatus}
          statusLabel={famineLabel}
          icon="⏳"
          hint={t('analytics.hints.famine_horizon')}
        />
        <MetricCard
          title={t('analytics.crisis.effective_pop_title')}
          value={ne}
          subvalue={t('analytics.crisis.effective_pop_sub', { females: fertileFemales, males })}
          status={neStatus}
          statusLabel={neLabel}
          icon="🧬"
          hint={t('analytics.hints.extinction_ne')}
        />
        <MetricCard
          title={t('analytics.crisis.clan_unrest_title')}
          value={unrestScore.toFixed(1)}
          subvalue={t('analytics.crisis.clan_unrest_sub', { crowding, hungry })}
          status={unrestStatus}
          statusLabel={unrestLabel}
          icon="⚡"
          hint={t('analytics.hints.unrest')}
        />
      </div>

      {/* Deep Dive Threat Panels */}
      <div className="analytics-grid-2col">
        {/* Famine Dynamics */}
        <div
          style={{
            background: '#161b22',
            border: '1px solid #30363d',
            borderRadius: 8,
            padding: '10px 12px',
            display: 'flex',
            flexDirection: 'column',
            gap: 6,
          }}
        >
          <span style={{ fontSize: 11, fontWeight: 700, color: '#c9d1d9', textTransform: 'uppercase' }}>
            {t('analytics.crisis.food_metabolism_title')}
          </span>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: 10 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: '#8b949e' }}>{t('analytics.crisis.total_larder_reserves')}</span>
              <b style={{ color: '#e6edf3' }}>{t('analytics.crisis.energy_unit', { val: totalLarder.toFixed(1) })}</b>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: '#8b949e' }}>{t('analytics.crisis.pop_metabolic_drain')}</span>
              <b style={{ color: '#f85149' }}>-{t('analytics.crisis.energy_per_tick', { val: burnRate.toFixed(2) })}</b>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: '#8b949e' }}>{t('analytics.crisis.wild_cultivated_regrowth')}</span>
              <b style={{ color: '#3fb950' }}>+{t('analytics.crisis.energy_per_tick', { val: regrowth.toFixed(2) })}</b>
            </div>
          </div>
        </div>

        {/* Unrest Drivers */}
        <div
          style={{
            background: '#161b22',
            border: '1px solid #30363d',
            borderRadius: 8,
            padding: '10px 12px',
            display: 'flex',
            flexDirection: 'column',
            gap: 6,
          }}
        >
          <span style={{ fontSize: 11, fontWeight: 700, color: '#c9d1d9', textTransform: 'uppercase' }}>
            {t('analytics.crisis.unrest_factors_title')}
          </span>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: 10 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: '#8b949e' }}>{t('analytics.crisis.overcrowded_beds')}</span>
              <b style={{ color: crowding > 0 ? '#d29922' : '#8b949e' }}>{t('analytics.crisis.occupants_unit', { count: crowding })}</b>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: '#8b949e' }}>{t('analytics.crisis.starving_members')}</span>
              <b style={{ color: hungry > 0 ? '#f85149' : '#8b949e' }}>{t('analytics.crisis.creatures_unit', { count: hungry })}</b>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: '#8b949e' }}>{t('analytics.crisis.personality_clashes')}</span>
              <b style={{ color: tenseClans > 0 ? '#f85149' : '#8b949e' }}>{t('analytics.crisis.clans_unit', { count: tenseClans })}</b>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
