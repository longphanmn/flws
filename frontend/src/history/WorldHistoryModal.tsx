import { useEffect, useMemo, useState } from 'react'
import type { StateMessage, WorldSummary } from '../types'
import { totemEmoji } from '../totems'
import { useI18n, getTranslator } from '../i18n'
import EpochBar from './EpochBar'
import PopulationSparkline from './PopulationSparkline'
import WarArcGraph from './WarArcGraph'
import RecordsLeaderboard from './RecordsLeaderboard'
import HistoryAnalytics from './HistoryAnalytics'
import { generateAndDownloadWorldCard } from './ShareWorldCard'

interface Props {
  open: boolean
  onClose: () => void
  state: StateMessage | null
  worlds?: WorldSummary[]
  selectedRunId?: number | null
  initialDay?: number | null
  onSelectCreature?: (id: number) => void
  onSelectClan?: (id: number) => void
}

export type MajorCategory = 'all' | 'war' | 'plague' | 'politics' | 'faith' | 'disaster'

const CATEGORY_TABS: Array<{ key: MajorCategory; icon: string }> = [
  { key: 'all', icon: '📅' },
  { key: 'war', icon: '⚔️' },
  { key: 'plague', icon: '☣️' },
  { key: 'politics', icon: '👑' },
  { key: 'faith', icon: '🏛️' },
  { key: 'disaster', icon: '🌋' },
]

interface WarDetail {
  aName: string
  bName: string
  battles: number
  casualties: number
}

interface ConquestDetail {
  invaderName: string
  victimName: string
  houseId: number
  plunderedFood?: number
}

interface OutbreakDetail {
  diseaseId: number
  caste?: string
}

interface DynastyDetail {
  kind: 'succession' | 'regicide' | 'schism' | 'treaty' | 'coalition' | 'betrayal' | 'extinction'
  title: string
  detail: string
  clanName?: string
  targetName?: string
  leaderId?: number
  parentName?: string
  childName?: string
  memberCount?: number
  days?: number
  coalitionName?: string
}

interface FaithDetail {
  kind: 'temple' | 'miracle' | 'epiphany' | 'synod'
  clanName?: string
  detail: string
}

interface DisasterDetail {
  kind: string
  rawKind?: string
  count: number
}

function buildDaySummary(
  d: DayRecord,
  clans: Record<string, any>,
  tr: (key: string, vars?: Record<string, any>) => string
): string {
  const highlights: string[] = []

  // 1. Genesis
  if (d.day === 0) {
    const clanNames = Object.values(clans).slice(0, 3).map((c: any) => c.name).filter(Boolean).join(', ')
    highlights.push(tr('history.details.genesis', { clans: clanNames || 'founding clans' }))
  }

  // 2. High-Impact Dynasties (Clan Schisms / Fracturing / Regicides / Clan Extinctions)
  const schisms = d.dynasties.filter((dyn) => dyn.kind === 'schism')
  const clanExtinctions = d.dynasties.filter((dyn) => dyn.kind === 'extinction')
  const regicides = d.dynasties.filter((dyn) => dyn.kind === 'regicide')

  if (schisms.length > 0 || clanExtinctions.length > 0 || regicides.length > 0) {
    if (schisms.length >= 2) {
      highlights.push(tr('history.details.greatFracturingMultiple', { count: schisms.length }))
    } else if (schisms.length === 1) {
      const s = schisms[0]
      highlights.push(
        s.parentName && s.childName
          ? tr('history.details.schismBreakdown', { parent: s.parentName, child: s.childName, count: s.memberCount ?? 1 })
          : s.detail
      )
    }

    if (clanExtinctions.length > 0) {
      const extSnippets = clanExtinctions
        .map((e) => (e.clanName ? tr('history.details.clanExtinctionTitle', { clan: e.clanName }) : e.title))
        .join(', ')
      highlights.push(extSnippets)
    }

    if (regicides.length > 0) {
      const regSnippets = regicides
        .map((r) => (r.clanName ? tr('history.details.regicideTitle', { clan: r.clanName }) : r.title))
        .join(', ')
      highlights.push(regSnippets)
    }
  }

  // 3. Detailed Major Wars (lethal casualties) & Territorial Conquests
  const lethalWars = d.wars.filter((w) => w.casualties > 0)
  if (lethalWars.length > 0 || d.conquests.length > 0) {
    if (lethalWars.length > 0) {
      const warSnippets = lethalWars.map((w) => {
        const casText = tr('history.details.fallenDigest', { count: w.casualties })
        return `${w.aName} vs ${w.bName}${casText}`
      })
      highlights.push(tr('history.details.warDigest', { wars: warSnippets.join(', ') }))
    }
    if (d.conquests.length > 0) {
      const conqSnippets = d.conquests.slice(0, 2).map((c) => {
        return tr('history.details.conquestDigestItem', { invader: c.invaderName, house: c.houseId, victim: c.victimName })
      })
      highlights.push(tr('history.details.conquestDigest', { conquests: conqSnippets.join(', ') }))
    }
  }

  // 4. Detailed Plagues
  if (d.outbreaks.length > 0) {
    highlights.push(tr('history.details.plagueDigest', { id: d.outbreaks[0].diseaseId }))
  }

  // 5. Detailed Faith
  if (d.faiths.length > 0) {
    const fSnippets = d.faiths.slice(0, 2).map((f) => {
      if (f.kind === 'temple') return tr('history.details.templeDetail', { clan: f.clanName ?? 'Clan' })
      if (f.kind === 'miracle') return tr('history.details.miracleDetail', { clan: f.clanName ?? 'Clan' })
      if (f.kind === 'epiphany') return tr('history.details.epiphanyDetail')
      if (f.kind === 'synod') return tr('history.details.synodDetail')
      return f.detail
    })
    highlights.push(tr('history.details.faithDigest', { faiths: fSnippets.join(' & ') }))
  }

  // 6. Detailed Disasters
  if (d.disasters.length > 0) {
    const disSnippets = d.disasters.map((dis) => {
      const raw = dis.rawKind || dis.kind
      const kindLabel =
        raw === 'river_flood'
          ? tr('history.details.riverFlood')
          : raw === 'flash_flood'
          ? tr('history.details.flashFlood')
          : raw === 'meteor'
          ? tr('history.details.meteor')
          : raw === 'earthquake'
          ? tr('history.details.earthquake')
          : dis.kind
      return dis.count > 1 ? `${kindLabel} (×${dis.count})` : kindLabel
    })
    highlights.push(tr('history.details.cataclysmDigest', { kinds: disSnippets.join(', ') }))
  }

  // 7. Other Political Treaties & Successions
  const otherDynasties = d.dynasties.filter(
    (dyn) => dyn.kind !== 'schism' && dyn.kind !== 'extinction' && dyn.kind !== 'regicide'
  )
  if (otherDynasties.length > 0 && highlights.length < 2) {
    const dSnippets = otherDynasties.slice(0, 2).map((dyn) => {
      if (dyn.kind === 'succession') return tr('history.details.successionTitle', { clan: dyn.clanName ?? '' })
      if (dyn.kind === 'coalition') return tr('history.details.coalitionTitle', { name: dyn.coalitionName ?? 'Defensive League' })
      if (dyn.kind === 'treaty') return tr('history.details.treatyTitle', { a: dyn.clanName ?? '', b: dyn.targetName ?? '' })
      if (dyn.kind === 'betrayal') return tr('history.details.betrayalTitle', { clan: dyn.clanName ?? '' })
      return dyn.title
    })
    highlights.push(tr('history.details.politicsDigest', { politics: dSnippets.join(' · ') }))
  }

  // 8. Peaceful / Flourishing Day
  if (highlights.length === 0) {
    const seasonIndex = Math.floor((d.day % 12) / 3)
    const seasonDesc = [
      tr('history.details.springThaw'),
      tr('history.details.highSummer'),
      tr('history.details.autumnBounty'),
      tr('history.details.deepWinter'),
    ][seasonIndex]

    const clanList = Object.values(clans).filter((c: any) => c.name)
    const leadClan = clanList.length > 0 ? clanList[(d.day * 3 + 7) % clanList.length]?.name : null

    const flavorIndex = d.day % 4
    let flavorDesc = [
      tr('history.details.flavor0'),
      tr('history.details.flavor1'),
      tr('history.details.flavor2'),
      tr('history.details.flavor3'),
    ][flavorIndex]

    if (leadClan) {
      flavorDesc = `${leadClan} ${flavorDesc}`
    }

    highlights.push(`${seasonDesc} · ${flavorDesc}`)
  }

  return highlights.join(' · ')
}

export interface DayRecord {
  day: number
  startTick: number
  endTick: number
  summaryLine: string
  primaryIcon: string
  badgeColor: string
  categories: Set<MajorCategory>
  wars: WarDetail[]
  conquests: ConquestDetail[]
  outbreaks: OutbreakDetail[]
  dynasties: DynastyDetail[]
  faiths: FaithDetail[]
  disasters: DisasterDetail[]
  totalCasualties: number
}

type StoryStyle = 'saga' | 'chronicle' | 'mythos' | 'tragedy'

const STYLE_LABELS: Record<StoryStyle, string> = {
  saga: '⚔️ Epic Novel Saga',
  chronicle: '📜 Ancient Historical Chronicle',
  mythos: '🔮 Spiritual & Mythological Lore',
  tragedy: '💀 Tragic Extinction & Decline',
}

const STYLE_PROMPTS: Record<StoryStyle, string> = {
  saga: 'Write a dramatic, multi-chapter historical epic saga following specific chieftains, named warriors, and priests across the daily chronicle. Emphasize character journeys, tactical battles between named clans, political betrayals, and survival during harsh winters.',
  chronicle: 'Write an ancient, scholarly historical chronicle recording the day-by-day rise and fall of named geometric clans, territorial conquests, legal philosophy, demographic curves, and military campaigns.',
  mythos: 'Write a spiritual and philosophical mythos focusing on the 2D inhabitants discovering the divine 3D Sphere, worshipping sacred avatars, raising glowing temples, and experiencing cosmic epiphanies.',
  tragedy: 'Write a poignant tragedy recording the golden heights of the geometric civilization, its slow descent into plague and ice, and the solemn extinction of the final living creature.',
}

const ADJECTIVES = ['Silent', 'Ancient', 'Crimson', 'Silver', 'Golden', 'Shadow', 'Azure', 'Iron', 'Emerald', 'Solar', 'Lunar', 'Obsidian', 'Dawn', 'Dusk', 'Misty', 'Starlight', 'Verdant', 'Echoing', 'Storm', 'Radiant']
const NOUNS = ['Spire', 'Shield', 'Circle', 'Blade', 'Monolith', 'Sanctum', 'Vertex', 'Lineage', 'Hearth', 'Haven', 'Vanguard', 'Beacon', 'Sovereigns', 'Keepers', 'Pillars', 'Wardens', 'Foundry', 'Sands', 'Bridges', 'Valley']

function generateClanName(id: number): string {
  const adj = ADJECTIVES[Math.abs(id * 7 + 13) % ADJECTIVES.length]
  const noun = NOUNS[Math.abs(id * 11 + 37) % NOUNS.length]
  return `Clan of the ${adj} ${noun}`
}

export default function WorldHistoryModal({
  open,
  onClose,
  state,
  selectedRunId,
  initialDay,
  onSelectCreature,
  onSelectClan,
}: Props) {
  const { t } = useI18n()
  const [rawEvents, setRawEvents] = useState<any[]>([])
  const [clans, setClans] = useState<Record<string, any>>({})
  const [clanNames, setClanNames] = useState<Record<string, string>>({})
  const [loading, setLoading] = useState(false)
  const [activeTab, setActiveTab] = useState<'timeline' | 'records' | 'analytics' | 'llm'>('timeline')
  const [category, setCategory] = useState<MajorCategory>('all')
  const [search, setSearch] = useState('')
  const [copied, setCopied] = useState(false)
  const [expandedDay, setExpandedDay] = useState<number | null>(null)
  const [promptLang, setPromptLang] = useState<'en' | 'vi' | 'fr'>('en')
  const [isWeeklyDigest, setIsWeeklyDigest] = useState(false)
  const [miniStoryCopiedDay, setMiniStoryCopiedDay] = useState<number | null>(null)
  const [copiedDayUrl, setCopiedDayUrl] = useState<number | null>(null)

  // BM-7: Pinned / bookmarked days with notes in localStorage
  const [pinnedDays, setPinnedDays] = useState<Record<number, string>>(() => {
    try {
      return JSON.parse(localStorage.getItem('flatland_pinned_days') || '{}')
    } catch {
      return {}
    }
  })

  const togglePinDay = (day: number) => {
    setPinnedDays((prev) => {
      const next = { ...prev }
      if (next[day] !== undefined) {
        delete next[day]
      } else {
        next[day] = ''
      }
      try {
        localStorage.setItem('flatland_pinned_days', JSON.stringify(next))
      } catch {}
      return next
    })
  }

  const setDayNote = (day: number, note: string) => {
    setPinnedDays((prev) => {
      const next = { ...prev, [day]: note }
      try {
        localStorage.setItem('flatland_pinned_days', JSON.stringify(next))
      } catch {}
      return next
    })
  }

  const [storyStyle, setStoryStyle] = useState<StoryStyle>(() => {
    try {
      const s = sessionStorage.getItem('history-story-style') as StoryStyle | null
      if (s && s in STYLE_LABELS) return s
    } catch { /* ignore */ }
    return 'saga'
  })
  const [showTimelineChart, setShowTimelineChart] = useState<boolean>(() => {
    try {
      return sessionStorage.getItem('history-show-chart') === 'true'
    } catch {
      return false
    }
  })
  const [isMobile, setIsMobile] = useState(() => typeof window !== 'undefined' && window.innerWidth <= 768)

  useEffect(() => {
    const onResize = () => setIsMobile(window.innerWidth <= 768)
    window.addEventListener('resize', onResize)
    return () => window.removeEventListener('resize', onResize)
  }, [])

  // BM-19: Deep link to specific day
  useEffect(() => {
    if (open && initialDay != null) {
      setExpandedDay(initialDay)
      setTimeout(() => {
        const el = document.getElementById(`history-day-${initialDay}`)
        if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' })
      }, 350)
    }
  }, [open, initialDay])

  // Persist the chosen writing style across modal reopens
  useEffect(() => {
    try { sessionStorage.setItem('history-story-style', storyStyle) } catch { /* ignore */ }
  }, [storyStyle])

  // Close on Escape key
  useEffect(() => {
    if (!open) return
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [open, onClose])

  // Fetch major events and clans
  useEffect(() => {
    if (!open) return
    setLoading(true)
    Promise.all([
      fetch('/api/history?major=true&limit=2000').then((r) => r.json()),
      fetch('/api/clans').then((r) => r.json()),
    ])
      .then(([histData, clanData]) => {
        setRawEvents(histData.events ?? [])
        const clanMap: Record<string, any> = {}
        const nameMap: Record<string, string> = {
          ...(histData.clan_names ?? {}),
          ...(clanData.names ?? {}),
        }
        for (const c of clanData.clans ?? []) {
          clanMap[String(c.id)] = c
          if (c.name) nameMap[String(c.id)] = c.name
        }
        setClans(clanMap)
        setClanNames(nameMap)
      })
      .catch((err) => console.error('Failed to load world history:', err))
      .finally(() => setLoading(false))
  }, [open, selectedRunId])

  const clanName = (id?: number | null, fallbackName?: string | null) => {
    if (fallbackName && !fallbackName.startsWith('Clan #') && !fallbackName.startsWith('#')) {
      return fallbackName
    }
    if (id == null) return 'Independent Realm'
    const fromMap = clanNames[String(id)] ?? clans[String(id)]?.name ?? state?.clans?.[String(id)]?.name
    if (fromMap && !fromMap.startsWith('Clan #') && !fromMap.startsWith('#')) {
      return fromMap
    }
    return generateClanName(id)
  }

  // Aggregate raw events into DayRecords (1 Day = 1200 ticks)
  const dayRecords = useMemo<DayRecord[]>(() => {
    const currentTick = state?.tick ?? 0
    const maxDay = Math.max(0, Math.floor(currentTick / 1200))
    const daysMap: Map<number, DayRecord> = new Map()

    // Initialize days
    for (let d = 0; d <= maxDay; d++) {
      daysMap.set(d, {
        day: d,
        startTick: d * 1200,
        endTick: (d + 1) * 1200 - 1,
        summaryLine: '',
        primaryIcon: '🌱',
        badgeColor: '#3fb950',
        categories: new Set<MajorCategory>(['all']),
        wars: [],
        conquests: [],
        outbreaks: [],
        dynasties: [],
        faiths: [],
        disasters: [],
        totalCasualties: 0,
      })
    }

    // Temporary war tracker per day: Map<dayNumber, Map<pairKey, WarDetail>>
    const dayWarMap: Map<number, Map<string, WarDetail>> = new Map()

    for (const ev of rawEvents) {
      const dayNum = Math.floor(ev.tick / 1200)
      let dRec = daysMap.get(dayNum)
      if (!dRec) {
        dRec = {
          day: dayNum,
          startTick: dayNum * 1200,
          endTick: (dayNum + 1) * 1200 - 1,
          summaryLine: '',
          primaryIcon: '🌱',
          badgeColor: '#3fb950',
          categories: new Set<MajorCategory>(['all']),
          wars: [],
          conquests: [],
          outbreaks: [],
          dynasties: [],
          faiths: [],
          disasters: [],
          totalCasualties: 0,
        }
        daysMap.set(dayNum, dRec)
      }

      const p = ev.payload ?? {}

      if (ev.type === 'war') {
        dRec.categories.add('war')
        const a = p.a ?? 0
        const b = p.b ?? 0
        const pairKey = [Math.min(a, b), Math.max(a, b)].join(':')
        let warMap = dayWarMap.get(dayNum)
        if (!warMap) {
          warMap = new Map()
          dayWarMap.set(dayNum, warMap)
        }
        let w = warMap.get(pairKey)
        if (!w) {
          w = {
            aName: clanName(a, p.a_name),
            bName: clanName(b, p.b_name),
            battles: 0,
            casualties: 0,
          }
          warMap.set(pairKey, w)
        }
        w.battles++
        if (p.lethal) {
          w.casualties++
          dRec.totalCasualties++
        }
      } else if (ev.type === 'takeover' || ev.type === 'conquest') {
        dRec.categories.add('war')
        const invaderName = clanName(p.invader_clan ?? p.clan_id, p.invader_name)
        const victimName = clanName(p.victim_clan ?? p.rival, p.victim_name)
        dRec.conquests.push({
          invaderName,
          victimName,
          houseId: p.house_id ?? ev.entity_id,
          plunderedFood: p.plundered_food,
        })
      } else if (ev.type === 'regicide') {
        dRec.categories.add('war')
        dRec.categories.add('politics')
        dRec.totalCasualties++
        const victimClan = clanName(p.victim_clan ?? p.clan_id, p.clan_name)
        dRec.dynasties.push({
          kind: 'regicide',
          title: t('history.details.regicideTitle', { clan: victimClan }),
          detail: t('history.details.regicideDetail', { clan: victimClan }),
          clanName: victimClan,
        })
      } else if (ev.type === 'outbreak') {
        dRec.categories.add('plague')
        dRec.outbreaks.push({
          diseaseId: p.disease_id ?? 1,
          caste: ev.caste ?? 'citizen',
        })
      } else if (ev.type === 'schism') {
        dRec.categories.add('politics')
        const parentClan = clanName(p.parent ?? p.from_clan ?? p.clan_id, p.parent_name ?? p.from_name)
        const newClan = clanName(p.new_clan ?? p.to_clan, p.new_name ?? p.to_name)
        const count = (p.members?.length ?? p.member_count) || 1
        dRec.dynasties.push({
          kind: 'schism',
          title: t('history.details.schismTitle', { clan: parentClan }),
          detail: t('history.details.schismBreakdown', { parent: parentClan, child: newClan, count }),
          parentName: parentClan,
          childName: newClan,
          memberCount: count,
        })
      } else if (ev.type === 'clan_extinction') {
        dRec.categories.add('politics')
        const cName = clanName(p.clan_id, p.clan_name)
        const days = p.lifespan_days ?? (p.lifespan_ticks ? Math.round(p.lifespan_ticks / 1200) : 0)
        dRec.dynasties.push({
          kind: 'extinction',
          title: t('history.details.clanExtinctionTitle', { clan: cName }),
          detail: t('history.details.clanExtinctionDetail', { clan: cName, days }),
          clanName: cName,
          days,
        })
      } else if (ev.type === 'succession') {
        dRec.categories.add('politics')
        const cName = clanName(p.clan_id, p.clan_name)
        dRec.dynasties.push({
          kind: 'succession',
          title: t('history.details.successionTitle', { clan: cName }),
          detail: t('history.details.successionDetail', { leader: p.new_leader, clan: cName }),
          clanName: cName,
          leaderId: p.new_leader,
        })
      } else if (ev.type === 'alliance' || ev.type === 'coalition_formed') {
        dRec.categories.add('politics')
        const cAName = clanName(p.a ?? p.founder, p.a_name)
        const cBName = p.b ? clanName(p.b, p.b_name) : ''
        dRec.dynasties.push({
          kind: ev.type === 'coalition_formed' ? 'coalition' : 'treaty',
          title: ev.type === 'coalition_formed' ? t('history.details.coalitionTitle', { name: p.name ?? 'Grand Coalition' }) : t('history.details.treatyTitle', { a: cAName, b: cBName }),
          detail: ev.type === 'coalition_formed' ? t('history.details.coalitionDetail', { clan: cAName }) : t('history.details.treatyDetail'),
          clanName: cAName,
          targetName: cBName,
          coalitionName: p.name ?? 'Grand Coalition',
        })
      } else if (ev.type === 'betrayal') {
        dRec.categories.add('politics')
        const cName = clanName(p.clan_id, p.clan_name)
        const tName = clanName(p.target_clan, p.target_name)
        dRec.dynasties.push({
          kind: 'betrayal',
          title: t('history.details.betrayalTitle', { clan: cName }),
          detail: t('history.details.betrayalDetail', { target: tName }),
          clanName: cName,
          targetName: tName,
        })
      } else if (ev.type === 'temple') {
        dRec.categories.add('faith')
        const cName = clanName(p.clan_id, p.clan_name)
        dRec.faiths.push({
          kind: 'temple',
          clanName: cName,
          detail: t('history.details.templeDetail', { clan: cName }),
        })
      } else if (ev.type === 'miracle') {
        dRec.categories.add('faith')
        const cName = clanName(p.clan_id)
        dRec.faiths.push({
          kind: 'miracle',
          clanName: cName,
          detail: t('history.details.miracleDetail', { clan: cName }),
        })
      } else if (ev.type === 'epiphany') {
        dRec.categories.add('faith')
        dRec.faiths.push({
          kind: 'epiphany',
          detail: t('history.details.epiphanyDetail'),
        })
      } else if (ev.type === 'synod') {
        dRec.categories.add('faith')
        dRec.faiths.push({
          kind: 'synod',
          detail: t('history.details.synodDetail'),
        })
      } else if (ev.type === 'disaster') {
        dRec.categories.add('disaster')
        const rawKind = String(p.kind ?? 'Cataclysm')
        const kindLabel = rawKind === 'river_flood' ? t('history.details.riverFlood')
          : rawKind === 'flash_flood' ? t('history.details.flashFlood')
          : rawKind === 'meteor' ? t('history.details.meteor')
          : rawKind === 'earthquake' ? t('history.details.earthquake')
          : rawKind
        const existing = dRec.disasters.find((dis) => dis.rawKind ? dis.rawKind === rawKind : dis.kind === kindLabel)
        if (existing) {
          existing.count++
        } else {
          dRec.disasters.push({
            kind: kindLabel,
            rawKind,
            count: 1,
          })
        }
      } else if (ev.type === 'extinction') {
        dRec.categories.add('disaster')
        dRec.disasters.push({
          kind: t('history.details.worldExtinction') || 'World Extinction',
          rawKind: 'extinction',
          count: 1,
        })
      }
    }

    // Attach consolidated wars to DayRecords
    for (const [dayNum, warMap] of dayWarMap.entries()) {
      const dRec = daysMap.get(dayNum)
      if (dRec) {
        dRec.wars = Array.from(warMap.values())
      }
    }

    // Build rich, specific One-Line Daily Digest Sentence
    const sortedDays = Array.from(daysMap.values()).sort((a, b) => a.day - b.day)

    for (const d of sortedDays) {
      if (d.day === 0) {
        d.primaryIcon = '🌱'
        d.badgeColor = '#3fb950'
      } else {
        const schisms = d.dynasties.filter((dyn) => dyn.kind === 'schism')
        const clanExtinctions = d.dynasties.filter((dyn) => dyn.kind === 'extinction')
        const regicides = d.dynasties.filter((dyn) => dyn.kind === 'regicide')

        if (schisms.length > 0 || clanExtinctions.length > 0 || regicides.length > 0) {
          d.primaryIcon = schisms.length > 0 ? '👑' : regicides.length > 0 ? '🗡️' : '💀'
          d.badgeColor = schisms.length > 0 ? '#e3b341' : '#f85149'
        } else {
          const lethalWars = d.wars.filter((w) => w.casualties > 0)
          if (lethalWars.length > 0 || d.conquests.length > 0) {
            d.primaryIcon = '⚔️'
            d.badgeColor = '#f85149'
          } else if (d.outbreaks.length > 0) {
            d.primaryIcon = '☣️'
            d.badgeColor = '#3fb950'
          } else if (d.faiths.length > 0) {
            d.primaryIcon = '🏛️'
            d.badgeColor = '#bc8cff'
          } else if (d.disasters.length > 0) {
            d.primaryIcon = '🌋'
            d.badgeColor = '#f85149'
          } else if (d.dynasties.length > 0) {
            d.primaryIcon = '👑'
            d.badgeColor = '#e3b341'
          } else {
            const seasonIndex = Math.floor((d.day % 12) / 3)
            d.primaryIcon = ['🌱', '☀️', '🍂', '❄️'][seasonIndex]
            d.badgeColor = ['#3fb950', '#e3b341', '#f0883e', '#79c0ff'][seasonIndex]
          }
        }
      }

      d.summaryLine = buildDaySummary(d, clans, t)
    }

    // Return newest day first for timeline UI
    return sortedDays.reverse()
  }, [rawEvents, clans, state?.tick])

  // Filter day records
  const filteredDays = useMemo(() => {
    return dayRecords.filter((d) => {
      if (category !== 'all' && !d.categories.has(category)) return false
      if (search.trim()) {
        const q = search.toLowerCase().trim()
        const text = `day ${d.day} ${d.summaryLine}`.toLowerCase()
        if (!text.includes(q)) return false
      }
      return true
    })
  }, [dayRecords, category, search])

  // BM-7: Pinned days floated to top or marked with badge
  const sortedAndFilteredDays = useMemo(() => {
    return filteredDays.slice().sort((a, b) => {
      const aPinned = pinnedDays[a.day] !== undefined ? 1 : 0
      const bPinned = pinnedDays[b.day] !== undefined ? 1 : 0
      if (aPinned !== bPinned) return bPinned - aPinned
      return b.day - a.day
    })
  }, [filteredDays, pinnedDays])

  // BM-3: Hero / Villain Auto-Callout
  const { hero, villain } = useMemo(() => {
    const kills: Record<string, { id: number; name?: string; caste?: string; clan?: string; count: number }> = {}
    const betrayals: Record<string, { id: number; name?: string; count: number }> = {}

    for (const ev of rawEvents) {
      const p = (ev.payload ?? {}) as Record<string, any>
      if (ev.type === 'war' && p.lethal) {
        const killerId = p.winner_id ?? p.killer
        const killerName = p.winner_name ?? p.killer_name
        if (killerId) {
          const k = String(killerId)
          if (!kills[k]) kills[k] = { id: killerId, name: killerName, caste: p.winner_caste, clan: p.winner_clan, count: 0 }
          kills[k].count++
        }
      } else if (ev.type === 'betrayal' || ev.type === 'regicide') {
        const traitorId = ev.entity_id ?? p.assassin_id ?? p.traitor_id
        if (traitorId) {
          const k = String(traitorId)
          if (!betrayals[k]) betrayals[k] = { id: traitorId, name: p.assassin ?? p.traitor_name, count: 0 }
          betrayals[k].count++
        }
      }
    }

    const topHero = Object.values(kills).sort((a, b) => b.count - a.count)[0] ?? null
    const topVillain = Object.values(betrayals).sort((a, b) => b.count - a.count)[0] ?? null
    return { hero: topHero, villain: topVillain }
  }, [rawEvents])

  // Per-day mini-story button
  const generateMiniStory = (d: DayRecord) => {
    const trPrompt = getTranslator(promptLang)
    const summary = buildDaySummary(d, clans, trPrompt)
    const langPrompt =
      promptLang === 'vi'
        ? 'Viết toàn bộ câu chuyện bằng Tiếng Việt.'
        : promptLang === 'fr'
        ? 'Écrivez l’intégralité de l’histoire en français.'
        : 'Respond in English.'

    const promptText = `# The Chronicles of Flatland: Day ${d.day}

## Writing Objective:
You are an epic bard in Flatland. Write a dramatic, atmospheric story describing the pivotal events of **Day ${d.day}** (${d.startTick}–${d.endTick} ticks). ${langPrompt}

## Events on Day ${d.day}:
- Summary: ${summary}
- Total Casualties: ${d.totalCasualties}
${d.wars.length > 0 ? `- Battles:\n${d.wars.map((w) => `  * ${w.aName} vs ${w.bName}: ${w.battles} clashes, ${w.casualties} dead`).join('\n')}` : ''}
${d.conquests.length > 0 ? `- Outpost Conquests:\n${d.conquests.map((c) => `  * ${c.invaderName} captured outpost #${c.houseId} from ${c.victimName}`).join('\n')}` : ''}
${d.outbreaks.length > 0 ? `- Epidemics:\n${d.outbreaks.map((o) => `  * Outbreak of contagion #${o.diseaseId}`).join('\n')}` : ''}
${d.dynasties.length > 0 ? `- Dynastic Shifts:\n${d.dynasties.map((dyn) => {
  const dTitle = dyn.kind === 'schism' ? trPrompt('history.details.schismTitle', { clan: dyn.parentName ?? '' })
    : dyn.kind === 'extinction' ? trPrompt('history.details.clanExtinctionTitle', { clan: dyn.clanName ?? '' })
    : dyn.kind === 'regicide' ? trPrompt('history.details.regicideTitle', { clan: dyn.clanName ?? '' })
    : dyn.kind === 'succession' ? trPrompt('history.details.successionTitle', { clan: dyn.clanName ?? '' })
    : dyn.kind === 'coalition' ? trPrompt('history.details.coalitionTitle', { name: dyn.coalitionName ?? '' })
    : dyn.kind === 'treaty' ? trPrompt('history.details.treatyTitle', { a: dyn.clanName ?? '', b: dyn.targetName ?? '' })
    : dyn.kind === 'betrayal' ? trPrompt('history.details.betrayalTitle', { clan: dyn.clanName ?? '' })
    : dyn.title
  const dDetail = dyn.kind === 'schism' ? trPrompt('history.details.schismBreakdown', { parent: dyn.parentName ?? '', child: dyn.childName ?? '', count: dyn.memberCount ?? 1 })
    : dyn.kind === 'extinction' ? trPrompt('history.details.clanExtinctionDetail', { clan: dyn.clanName ?? '', days: dyn.days ?? 0 })
    : dyn.kind === 'regicide' ? trPrompt('history.details.regicideDetail', { clan: dyn.clanName ?? '' })
    : dyn.kind === 'succession' ? trPrompt('history.details.successionDetail', { leader: dyn.leaderId ?? '', clan: dyn.clanName ?? '' })
    : dyn.kind === 'coalition' ? trPrompt('history.details.coalitionDetail', { clan: dyn.clanName ?? '' })
    : dyn.kind === 'treaty' ? trPrompt('history.details.treatyDetail')
    : dyn.kind === 'betrayal' ? trPrompt('history.details.betrayalDetail', { target: dyn.targetName ?? '' })
    : dyn.detail
  return `  * ${dTitle}: ${dDetail}`
}).join('\n')}` : ''}
${d.faiths.length > 0 ? `- Sacred Rites:\n${d.faiths.map((f) => {
  const fDetail = f.kind === 'temple' ? trPrompt('history.details.templeDetail', { clan: f.clanName ?? 'Clan' })
    : f.kind === 'miracle' ? trPrompt('history.details.miracleDetail', { clan: f.clanName ?? 'Clan' })
    : f.kind === 'epiphany' ? trPrompt('history.details.epiphanyDetail')
    : f.kind === 'synod' ? trPrompt('history.details.synodDetail')
    : f.detail
  return `  * ${f.kind}: ${fDetail}`
}).join('\n')}` : ''}
${d.disasters.length > 0 ? `- Cataclysms:\n${d.disasters.map((dis) => {
  const raw = dis.rawKind || dis.kind
  const kindLabel = raw === 'river_flood' ? trPrompt('history.details.riverFlood')
    : raw === 'flash_flood' ? trPrompt('history.details.flashFlood')
    : raw === 'meteor' ? trPrompt('history.details.meteor')
    : raw === 'earthquake' ? trPrompt('history.details.earthquake')
    : dis.kind
  return `  * ${kindLabel} (${dis.count} occurrences)`
}).join('\n')}` : ''}
`
    try {
      navigator.clipboard.writeText(promptText)
      setMiniStoryCopiedDay(d.day)
      setTimeout(() => setMiniStoryCopiedDay(null), 2500)
    } catch {}
  }

  // Total stats
  const totalStats = useMemo(() => {
    let wars = 0
    let lethalWars = 0
    let outbreaks = 0
    let schisms = 0
    let clanExtinctions = 0
    let disasters = 0
    let temples = 0
    let miracles = 0
    let successions = 0

    for (const d of dayRecords) {
      wars += d.wars.reduce((acc, w) => acc + w.battles, 0)
      lethalWars += d.totalCasualties
      outbreaks += d.outbreaks.length
      schisms += d.dynasties.filter((dyn) => dyn.kind === 'schism').length
      clanExtinctions += d.dynasties.filter((dyn) => dyn.kind === 'extinction').length
      successions += d.dynasties.filter((dyn) => dyn.kind === 'succession').length
      temples += d.faiths.filter((f) => f.kind === 'temple').length
      miracles += d.faiths.filter((f) => f.kind === 'miracle').length
      disasters += d.disasters.reduce((acc, dis) => acc + dis.count, 0)
    }

    return { wars, lethalWars, outbreaks, schisms, clanExtinctions, disasters, temples, miracles, successions }
  }, [dayRecords])

  const totalDays = state ? (state.tick / 1200).toFixed(1) : '0'

  // Build the LLM Story Prompt (Chronological Rich Day-by-Day Historical Chronicle)
  const llmPrompt = useMemo(() => {
    const seed = state?.seed ?? 42
    const aliveCount = state?.creatures_alive ?? 0
    const deadCount = state?.creatures_dead ?? 0
    const deadByCause = state?.dead_by_cause ?? {}

    const clanSummary = Object.values(clans).map((c) => {
      const avatar = c.totem ? `${totemEmoji(c.totem)} ${c.totem}` : 'Unknown'
      return `- **${c.name}** (#${c.id}): Avatar ${avatar} | Pop: ${c.population} | Record: ${c.war_wins}W - ${c.war_losses}L | Faith: ${c.faith ?? 0}`
    }).join('\n')

    // Chronological order (Day 0, Day 1, Day 2...)
    const chronologicalDays = [...dayRecords].reverse()

    // This Week in Flatland (last 7 days) vs full chronicle
    const targetDays = isWeeklyDigest ? chronologicalDays.slice(-7) : chronologicalDays

    const trPrompt = getTranslator(promptLang)
    const dayTimeline = targetDays.map((d) => {
      return `- **Day ${d.day}**: ${buildDaySummary(d, clans, trPrompt)}`
    }).join('\n')

    const styleLabel = STYLE_LABELS[storyStyle]
    const stylePrompt = STYLE_PROMPTS[storyStyle]

    const langInstruction =
      promptLang === 'vi'
        ? '\n\n**HƯỚNG DẪN NGÔN NGỮ**: Hãy viết toàn bộ câu chuyện bằng Tiếng Việt sinh động, hấp dẫn, đúng văn phong sử thi.'
        : promptLang === 'fr'
        ? '\n\n**INSTRUCTION DE LANGUE**: Rédigez l’intégralité du récit en français avec un ton épique et soigné.'
        : '\n\n**LANGUAGE INSTRUCTION**: Write the narrative in evocative, epic English prose.'

    return `# The Chronicles of Flatland: World Seed ${seed} ${isWeeklyDigest ? '(Weekly Digest)' : ''}

## Writing Style — ${styleLabel}
${stylePrompt}

## Context & World Lore
You are an epic historian and bard recording the true history of a simulated 2D world inspired by Edwin A. Abbott's *Flatland*.
- **Society**: Women are razor-sharp line segments; Men are regular polygons whose status ascends by side count (Isosceles Triangles -> Soldiers -> Equilateral Artisans -> Squares -> Pentagons -> Hexagonal Nobles -> Multi-sided Priests/Circles).
- **Faith & Avatars**: Clans revere Sacred 2D Avatars of the 3D Sphere (Radiant Circle, Celestial Strike, All-Seeing Vertex, Indomitable Monolith, Sacred Spiral, Cosmic Scales, Tactical Rift, Eternal Hearth).
- **Environment**: The world cycles through 4 Great Ages (Golden Era, Ice Age, Chaos Era, Plague Age) and dynamic seasons.

## World Statistics
- **Total Duration**: ${totalDays} Days (${state?.tick ?? 0} Ticks)
- **World Seed**: ${seed}
- **Current Population**: ${aliveCount} Alive | ${deadCount} Fallen
- **Mortality Breakdown**: ${Object.entries(deadByCause).map(([k, v]) => `${k}: ${v}`).join(', ') || 'None recorded'}
- **Major Milestone Tallies**: ${totalStats.wars} Battles (${totalStats.lethalWars} fallen), ${totalStats.outbreaks} Pandemics, ${totalStats.schisms} Rebellions, ${totalStats.temples} Temples Raised, ${totalStats.disasters} Cataclysms.

## Legendary Figures of Renown
${hero ? `- ⚔️ **Legendary Champion (Hero)**: ${hero.name ? `**${hero.name}** ` : ''}#${hero.id} (${hero.caste ?? 'Warrior'}, ${clanName(hero.clan as any)}) — Vanquished ${hero.count} enemies in mortal combat.` : '- ⚔️ **Legendary Champion**: No prominent slayer identified yet.'}
${villain ? `- 🗡️ **Infamous Traitor (Villain)**: ${villain.name ? `**${villain.name}** ` : ''}#${villain.id} — Instigator of ${villain.count} betrayals and dynastic coups.` : '- 🗡️ **Infamous Traitor**: No notable treason recorded.'}

## Clan Roster & Avatars
${clanSummary || 'No formal clans recorded.'}

## Detailed Historical Chronicle (${targetDays.length} Days ${isWeeklyDigest ? '— Past 7 Days' : ''})
${dayTimeline || 'No daily records recorded yet.'}

---

## Story Writing Instructions for LLM:
${stylePrompt}
${langInstruction}

**Guidelines**:
1. Follow the chronological day-by-day turning points above with the exact clan names, casualties, and milestones.
2. Portray the unique geometric nature of Flatland characters (angles, vertex sharpness, fog perception, line speed).
3. Weave the historical milestones (named wars, house conquests, outbreaks, temples, schisms) into pivotal chapter turns.`
  }, [state, clans, dayRecords, totalStats, totalDays, storyStyle, hero, villain, isWeeklyDigest, promptLang])

  const copyToClipboard = async () => {
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(llmPrompt)
      } else {
        throw new Error('no clipboard')
      }
    } catch {
      // fallback for iOS / insecure context: textarea + execCommand + prompt
      try {
        const ta = document.createElement('textarea')
        ta.value = llmPrompt
        ta.style.position = 'fixed'
        ta.style.opacity = '0'
        document.body.appendChild(ta)
        ta.select()
        document.execCommand('copy')
        document.body.removeChild(ta)
      } catch {
        window.prompt('Copy the chronicle (⌘C / Ctrl+C):', llmPrompt)
        return
      }
    }
    setCopied(true)
    setTimeout(() => setCopied(false), 2500)
  }

  const triggerDownload = (blob: Blob, filename: string) => {
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    a.style.display = 'none'
    document.body.appendChild(a)
    a.click()
    setTimeout(() => {
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
    }, 1000)
    // iOS fallback: if download didn't trigger, open in new tab
    if (navigator.userAgent.match(/iPhone|iPad|iPod/i)) {
      setTimeout(() => window.open(url, '_blank') ?? undefined, 100)
    }
  }

  const downloadMarkdown = () => {
    const blob = new Blob([llmPrompt], { type: 'text/markdown;charset=utf-8' })
    triggerDownload(blob, `flatland_detailed_daily_history_seed_${state?.seed ?? 42}.md`)
  }

  const downloadJSON = () => {
    const blob = new Blob([JSON.stringify({ state, totalStats, clans, dayRecords }, null, 2)], { type: 'application/json' })
    triggerDownload(blob, `flatland_detailed_daily_history_seed_${state?.seed ?? 42}.json`)
  }

  // BM-21: Generate and download shareable 1200x630 card
  const handleShareCard = () => {
    generateAndDownloadWorldCard({
      seed: state?.seed ?? 42,
      totalDays: Number(totalDays),
      currentTick: state?.tick ?? 0,
      aliveCount: state?.creatures_alive ?? 0,
      deadCount: state?.creatures_dead ?? 0,
      wars: totalStats.wars,
      temples: totalStats.temples,
      clans: Object.values(clans).map((c: any) => ({
        name: c.name,
        color: c.color,
        totem: c.totem,
        population: c.population,
      })),
    })
  }

  if (!open) return null

  return (
    <div
      className="clan-details-backdrop"
      onClick={onClose}
      style={{
        zIndex: 100,
        padding: isMobile ? 0 : undefined,
        paddingTop: isMobile ? 'env(safe-area-inset-top)' : undefined,
        paddingBottom: isMobile ? 'env(safe-area-inset-bottom)' : undefined,
        overflow: 'auto',
        WebkitOverflowScrolling: 'touch' as any,
      }}
    >
      <div
        className="clan-details-panel"
        onClick={(e) => e.stopPropagation()}
        style={{
          width: isMobile ? '100vw' : 'min(900px, 96vw)',
          height: isMobile ? '100dvh' : 'auto',
          maxHeight: isMobile ? '100dvh' : '92vh',
          minHeight: isMobile ? '100dvh' : undefined,
          display: 'flex',
          flexDirection: 'column',
          padding: 0,
          background: '#0d1117',
          border: isMobile ? 'none' : '1px solid #30363d',
          boxShadow: '0 20px 48px rgba(0,0,0,0.8)',
          borderRadius: isMobile ? 0 : 12,
          overflow: 'hidden',
        }}
      >
        {/* Header */}
        <header className="history-modal-head">
          <div className="history-head-title-wrap">
            <div className="history-head-title-left">
              <span className="history-head-icon">📜</span>
              <div>
                <h2 className="history-head-title">
                  {t('history.title')}
                </h2>
                <div className="history-head-subtitle">
                  {t('history.subtitle', { seed: state?.seed ?? 42, days: dayRecords.length, alive: state?.creatures_alive ?? 0 })}
                </div>
              </div>
            </div>
            <div className="history-head-title-actions">
              <button
                type="button"
                className="history-tool-btn history-share-btn-mobile"
                onClick={handleShareCard}
                title={t('history.actions.shareCardTooltip') || 'Download 1200x630 share card PNG'}
              >
                <span>📸</span>
                <span className="history-tool-label">{t('history.actions.shareCard') || 'Share'}</span>
              </button>
              <button
                className="history-close-btn history-close-btn-mobile"
                onClick={onClose}
                aria-label={t('history.close') || 'Close'}
              >
                ✕
              </button>
            </div>
          </div>

          <div className="history-head-controls">
            <div className="history-segmented-nav" role="tablist">
              <button
                type="button"
                role="tab"
                aria-selected={activeTab === 'timeline'}
                className={`history-nav-item ${activeTab === 'timeline' ? 'active' : ''}`}
                onClick={() => setActiveTab('timeline')}
              >
                <span className="history-nav-icon">📅</span>
                <span className="history-nav-text">{t('history.tabs.timelineTab') || 'Timeline'}</span>
                <span className="history-nav-badge">{filteredDays.length}</span>
              </button>
              <button
                type="button"
                role="tab"
                aria-selected={activeTab === 'records'}
                className={`history-nav-item ${activeTab === 'records' ? 'active' : ''}`}
                onClick={() => setActiveTab('records')}
              >
                <span className="history-nav-icon">🏆</span>
                <span className="history-nav-text">{t('history.tabs.recordsTab') || 'Records'}</span>
              </button>
              <button
                type="button"
                role="tab"
                aria-selected={activeTab === 'analytics'}
                className={`history-nav-item ${activeTab === 'analytics' ? 'active' : ''}`}
                onClick={() => setActiveTab('analytics')}
              >
                <span className="history-nav-icon">🧮</span>
                <span className="history-nav-text">{t('history.tabs.analyticsTab') || 'Matrix'}</span>
              </button>
              <button
                type="button"
                role="tab"
                aria-selected={activeTab === 'llm'}
                className={`history-nav-item ${activeTab === 'llm' ? 'active' : ''}`}
                onClick={() => setActiveTab('llm')}
              >
                <span className="history-nav-icon">✨</span>
                <span className="history-nav-text">{t('history.tabs.aiTab') || 'AI Story'}</span>
              </button>
            </div>

            <div className="history-head-actions">
              <button
                type="button"
                className="history-tool-btn"
                onClick={handleShareCard}
                title={t('history.actions.shareCardTooltip') || 'Download 1200x630 share card PNG'}
              >
                <span>📸</span>
                <span className="history-tool-label">{t('history.actions.shareCard') || 'Share'}</span>
              </button>

              <button
                type="button"
                className="history-close-btn"
                onClick={onClose}
                aria-label={t('history.close') || 'Close'}
              >
                ✕
              </button>
            </div>
          </div>
        </header>

        {/* Major Stats Ticker */}
        <div className="history-stats-ticker">
          <span className="history-stat-item" title={t('history.statsTooltips.battles')}>
            ⚔️ <b>{totalStats.wars}</b> {t('history.stats.battles')} ({totalStats.lethalWars} {t('history.stats.fallen')})
          </span>
          <span className="history-stat-dot">·</span>
          <span className="history-stat-item" title={t('history.statsTooltips.plagues')}>
            ☣️ <b>{totalStats.outbreaks}</b> {t('history.stats.plagues')}
          </span>
          <span className="history-stat-dot">·</span>
          <span className="history-stat-item" title={t('history.statsTooltips.schisms')}>
            ⚡ <b>{totalStats.schisms}</b> {t('history.stats.schisms')}
          </span>
          <span className="history-stat-dot">·</span>
          <span className="history-stat-item" title={t('history.statsTooltips.successions')}>
            👑 <b>{totalStats.successions}</b> {t('history.stats.successions')}
          </span>
          <span className="history-stat-dot">·</span>
          <span className="history-stat-item" title={t('history.statsTooltips.temples')}>
            🏛️ <b>{totalStats.temples}</b> {t('history.stats.temples')}
          </span>
          <span className="history-stat-dot">·</span>
          <span className="history-stat-item" title={t('history.statsTooltips.miracles')}>
            🌸 <b>{totalStats.miracles}</b> {t('history.stats.miracles')}
          </span>
          <span className="history-stat-dot">·</span>
          <span className="history-stat-item" title={t('history.statsTooltips.cataclysms')}>
            🌋 <b>{totalStats.disasters}</b> {t('history.stats.cataclysms')}
          </span>
        </div>

        {/* Main Body */}
        <div style={{ flex: 1, overflow: 'auto', padding: isMobile ? '10px 12px' : '16px 20px' }}>
          {activeTab === 'timeline' ? (
            <div>
              {/* Category Pills, Search & Chart Toggle */}
              <div className="history-filter-bar">
                <div className="history-category-pills">
                  {CATEGORY_TABS.map((tab) => (
                    <button
                      key={tab.key}
                      type="button"
                      onClick={() => setCategory(tab.key)}
                      className={`history-cat-pill ${category === tab.key ? 'active' : ''}`}
                    >
                      <span>{tab.icon}</span>
                      <span>{t(`history.tabs.${tab.key}`)}</span>
                    </button>
                  ))}
                </div>

                <div className="history-search-row">
                  <div className="history-search-wrap">
                    <span className="history-search-icon">🔍</span>
                    <input
                      type="text"
                      placeholder={t('history.searchPlaceholder')}
                      value={search}
                      onChange={(e) => setSearch(e.target.value)}
                      className="history-search-input"
                    />
                    {search && (
                      <button
                        type="button"
                        className="history-search-clear"
                        onClick={() => setSearch('')}
                      >
                        ✕
                      </button>
                    )}
                  </div>

                  <button
                    type="button"
                    className={`history-chart-toggle-btn ${showTimelineChart ? 'active' : ''}`}
                    onClick={() => {
                      setShowTimelineChart((v) => {
                        const next = !v
                        try { sessionStorage.setItem('history-show-chart', String(next)) } catch {}
                        return next
                      })
                    }}
                    title={t('history.actions.toggleChart') || 'Toggle Epoch & Sparkline chart'}
                  >
                    {showTimelineChart ? (t('history.actions.hideChart') || '📉 Hide Chart') : (t('history.actions.showChart') || '📈 Chart')}
                  </button>
                </div>
              </div>

              {/* Collapsible Timeline Charts (BM-8 & BM-9 & BM-10) */}
              {showTimelineChart && (
                <div style={{ marginBottom: 12 }}>
                  <EpochBar
                    totalDays={dayRecords.length}
                    currentDay={Math.floor((state?.tick ?? 0) / 1200)}
                    selectedDay={expandedDay}
                    onSelectDay={(d) => {
                      setExpandedDay(d)
                      setTimeout(() => {
                        const el = document.getElementById(`history-day-${d}`)
                        if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' })
                      }, 60)
                    }}
                    compact={isMobile}
                  />
                  <PopulationSparkline
                    dayRecords={dayRecords}
                    selectedDay={expandedDay}
                    onSelectDay={(d) => {
                      setExpandedDay(d)
                      setTimeout(() => {
                        const el = document.getElementById(`history-day-${d}`)
                        if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' })
                      }, 60)
                    }}
                    currentPopulation={state?.creatures_alive}
                  />
                </div>
              )}

              {/* Day Feed */}
              {loading ? (
                <div style={{ textAlign: 'center', padding: 40, color: '#8b949e' }}>
                  {t('history.analyzing')}
                </div>
              ) : sortedAndFilteredDays.length === 0 ? (
                <div style={{ textAlign: 'center', padding: 40, color: '#8b949e' }}>
                  {t('history.empty')}
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                  {sortedAndFilteredDays.map((d) => {
                    const isExpanded = expandedDay === d.day
                    const isPinned = pinnedDays[d.day] !== undefined
                    return (
                      <div
                        key={d.day}
                        id={`history-day-${d.day}`}
                        onClick={() => setExpandedDay(isExpanded ? null : d.day)}
                        style={{
                          background: isExpanded ? '#1c2128' : isPinned ? '#161e2e' : '#161b22',
                          border: '1px solid',
                          borderColor: isExpanded ? '#444c56' : isPinned ? '#388bfd' : '#21262d',
                          borderLeft: `4px solid ${d.badgeColor}`,
                          borderRadius: 8,
                          padding: '10px 14px',
                          fontSize: 12,
                          cursor: 'pointer',
                          transition: 'background 0.15s',
                        }}
                      >
                        {/* Day Row (vertical layout on mobile, horizontal on desktop) */}
                        <div className="history-day-row">
                          <div className="history-day-meta-line">
                            <div className="history-day-badges">
                              {/* BM-7: Star pin button */}
                              <button
                                type="button"
                                onClick={(e) => {
                                  e.stopPropagation()
                                  togglePinDay(d.day)
                                }}
                                className="history-pin-btn"
                                title={isPinned ? t('history.actions.unpinDay') : t('history.actions.pinDay')}
                              >
                                {isPinned ? '⭐' : '☆'}
                              </button>

                              <span
                                className="chip"
                                style={{
                                  background: isPinned ? 'rgba(56,139,253,0.2)' : '#21262d',
                                  color: isPinned ? '#58a6ff' : '#e3b341',
                                  fontWeight: 700,
                                  fontSize: 11,
                                  padding: '2px 8px',
                                  flexShrink: 0,
                                }}
                              >
                                {t('history.dayNumber', { day: d.day })}
                              </span>
                              <span style={{ fontSize: 16, flexShrink: 0 }}>{d.primaryIcon}</span>
                            </div>

                            <span className="history-day-expand-chevron mobile-only">
                              {isExpanded ? '▲' : '▼'}
                            </span>
                          </div>

                          <span className="history-day-summary-text">
                            {d.summaryLine}
                          </span>

                          <span className="history-day-expand-chevron desktop-only">
                            {isExpanded ? '▲' : '▼'}
                          </span>
                        </div>

                        {/* Expanded Day Details (if clicked) */}
                        {isExpanded && (
                          <div
                            style={{
                              marginTop: 10,
                              paddingTop: 10,
                              borderTop: '1px solid #30363d',
                              display: 'flex',
                              flexDirection: 'column',
                              gap: 8,
                              fontSize: 12,
                              color: '#c9d1d9',
                            }}
                          >
                            <div style={{ fontWeight: 600, color: '#8b949e', fontSize: 11 }}>
                              {t('history.dossier', { start: d.startTick, end: d.endTick })}
                            </div>

                            {/* Note editor if pinned */}
                            {isPinned && (
                              <div
                                style={{ display: 'flex', gap: 6, alignItems: 'center', background: '#0d1117', padding: '4px 8px', borderRadius: 6, border: '1px solid #30363d' }}
                                onClick={(e) => e.stopPropagation()}
                              >
                                <span style={{ fontSize: 11, color: '#e3b341', fontWeight: 600 }}>📌 {t('history.actions.note')}</span>
                                <input
                                  type="text"
                                  placeholder={t('history.actions.notePlaceholder')}
                                  value={pinnedDays[d.day] || ''}
                                  onChange={(e) => setDayNote(d.day, e.target.value)}
                                  style={{ flex: 1, background: 'transparent', border: 'none', color: '#e6edf3', fontSize: 11, outline: 'none' }}
                                />
                              </div>
                            )}

                            {/* BM-11: War Arc Connectors */}
                            {d.wars.length > 0 && <WarArcGraph wars={d.wars} />}

                            {/* Wars */}
                            {d.wars.length > 0 && (
                              <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                                <span style={{ color: '#f85149', fontWeight: 600 }}>{t('history.sections.military')}</span>
                                {d.wars.map((w, idx) => (
                                  <div key={idx} style={{ paddingLeft: 12, color: '#c9d1d9' }}>
                                    {t('history.details.warEntry', { a: w.aName, b: w.bName, battles: w.battles, casualties: w.casualties })}
                                  </div>
                                ))}
                              </div>
                            )}

                            {/* Conquests */}
                            {d.conquests.length > 0 && (
                              <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                                <span style={{ color: '#d29922', fontWeight: 600 }}>{t('history.sections.conquests')}</span>
                                {d.conquests.map((c, idx) => (
                                  <div key={idx} style={{ paddingLeft: 12, color: '#c9d1d9' }}>
                                    {t('history.details.conquestEntry', { invader: c.invaderName, house: c.houseId, victim: c.victimName, food: c.plunderedFood ? t('history.details.conquestFood', { food: c.plunderedFood }) : '' })}
                                  </div>
                                ))}
                              </div>
                            )}

                            {/* Plagues */}
                            {d.outbreaks.length > 0 && (
                              <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                                <span style={{ color: '#3fb950', fontWeight: 600 }}>{t('history.sections.plagues')}</span>
                                {d.outbreaks.map((o, idx) => (
                                  <div key={idx} style={{ paddingLeft: 12, color: '#c9d1d9' }}>
                                    {t('history.details.plagueEntry', { id: o.diseaseId, caste: o.caste })}
                                  </div>
                                ))}
                              </div>
                            )}

                            {/* Dynasties */}
                            {d.dynasties.length > 0 && (
                              <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                                <span style={{ color: '#e3b341', fontWeight: 600 }}>{t('history.sections.dynasties')}</span>
                                {d.dynasties.map((dyn, idx) => (
                                  <div key={idx} style={{ paddingLeft: 12, color: '#c9d1d9' }}>
                                    • <b>{dyn.title}</b>: {dyn.detail}
                                  </div>
                                ))}
                              </div>
                            )}

                            {/* Faith */}
                            {d.faiths.length > 0 && (
                              <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                                <span style={{ color: '#bc8cff', fontWeight: 600 }}>{t('history.sections.faith')}</span>
                                {d.faiths.map((f, idx) => (
                                  <div key={idx} style={{ paddingLeft: 12, color: '#c9d1d9' }}>
                                    • {f.detail}
                                  </div>
                                ))}
                              </div>
                            )}

                            {/* Disasters */}
                            {d.disasters.length > 0 && (
                              <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                                <span style={{ color: '#f85149', fontWeight: 600 }}>{t('history.sections.cataclysms')}</span>
                                {d.disasters.map((dis, idx) => (
                                  <div key={idx} style={{ paddingLeft: 12, color: '#c9d1d9' }}>
                                    {t('history.details.disasterEntry', { kind: dis.count > 1 ? `${dis.kind} (×${dis.count})` : dis.kind })}
                                  </div>
                                ))}
                              </div>
                            )}

                            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 6, marginTop: 8 }} onClick={(e) => e.stopPropagation()}>
                              <button
                                type="button"
                                className="chip"
                                onClick={() => {
                                  const url = `${window.location.origin}${window.location.pathname}?history=${d.day}`
                                  navigator.clipboard?.writeText(url)
                                  setCopiedDayUrl(d.day)
                                  setTimeout(() => setCopiedDayUrl(null), 2000)
                                }}
                                style={{
                                  background: copiedDayUrl === d.day ? '#238636' : 'rgba(255, 255, 255, 0.08)',
                                  borderColor: copiedDayUrl === d.day ? '#2ea043' : '#30363d',
                                  color: copiedDayUrl === d.day ? '#fff' : '#c9d1d9',
                                  cursor: 'pointer',
                                  fontSize: 11,
                                  padding: '4px 10px',
                                  fontWeight: 600,
                                }}
                                title={t('history.actions.shareDayTooltip')}
                              >
                                {copiedDayUrl === d.day ? t('history.actions.linkCopied') : t('history.actions.shareDay', { day: d.day })}
                              </button>
                              <button
                                type="button"
                                className="chip"
                                onClick={() => generateMiniStory(d)}
                                style={{
                                  background: miniStoryCopiedDay === d.day ? '#238636' : 'rgba(56, 139, 253, 0.15)',
                                  borderColor: miniStoryCopiedDay === d.day ? '#2ea043' : 'rgba(56, 139, 253, 0.4)',
                                  color: miniStoryCopiedDay === d.day ? '#fff' : '#58a6ff',
                                  cursor: 'pointer',
                                  fontSize: 11,
                                  padding: '4px 10px',
                                  fontWeight: 600,
                                }}
                                title={t('history.actions.miniStoryTooltip')}
                              >
                                {miniStoryCopiedDay === d.day ? t('history.actions.promptCopied') : t('history.actions.miniStory', { day: d.day })}
                              </button>
                            </div>
                          </div>
                        )}
                      </div>
                    )
                  })}
                </div>
              )}
            </div>
          ) : activeTab === 'records' ? (
            <RecordsLeaderboard
              dayRecords={dayRecords}
              clans={clans}
              rawEvents={rawEvents}
              onSelectClan={onSelectClan}
              onSelectCreature={onSelectCreature}
            />
          ) : activeTab === 'analytics' ? (
            <HistoryAnalytics
              dayRecords={dayRecords}
              clans={clans}
              rawEvents={rawEvents}
            />
          ) : (
            /* LLM Exporter Tab */
            <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
              <div
                style={{
                  background: '#161b22',
                  border: '1px solid #30363d',
                  borderRadius: 8,
                  padding: 14,
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 8 }}>
                  <div>
                    <h3 style={{ fontSize: 14, margin: 0, color: '#e6edf3', fontWeight: 700 }}>
                      {t('history.aiTitle')}
                    </h3>
                    <p style={{ fontSize: 11, color: '#8b949e', margin: '4px 0 0' }}>
                      {t('history.aiDesc')}
                    </p>
                    {/* Controls Row: Language, Weekly Digest, Style Badge */}
                    <div style={{ marginTop: 8, display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
                      <div style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                        <span style={{ fontSize: 10.5, color: '#8b949e', fontWeight: 600 }}>{t('history.aiLang')}:</span>
                        {(['en', 'vi', 'fr'] as const).map((lang) => (
                          <button
                            key={lang}
                            type="button"
                            className="chip"
                            onClick={() => setPromptLang(lang)}
                            style={{
                              fontSize: 10,
                              padding: '2px 7px',
                              background: promptLang === lang ? '#388bfd' : '#21262d',
                              color: promptLang === lang ? '#fff' : '#c9d1d9',
                              borderColor: promptLang === lang ? '#58a6ff' : '#30363d',
                              fontWeight: 600,
                              cursor: 'pointer',
                              borderRadius: 4,
                            }}
                          >
                            {lang.toUpperCase()}
                          </button>
                        ))}
                      </div>

                      <label style={{ display: 'inline-flex', alignItems: 'center', gap: 5, fontSize: 10.5, color: '#c9d1d9', cursor: 'pointer' }}>
                        <input
                          type="checkbox"
                          checked={isWeeklyDigest}
                          onChange={(e) => setIsWeeklyDigest(e.target.checked)}
                          style={{ cursor: 'pointer' }}
                        />
                        <span>📰 {t('history.aiWeeklyDigest')}</span>
                      </label>

                      <span
                        style={{
                          fontSize: 10.5,
                          fontWeight: 700,
                          padding: '2px 8px',
                          borderRadius: 10,
                          background: 'rgba(56,139,253,0.18)',
                          border: '1px solid #388bfd',
                          color: '#79c0ff',
                        }}
                      >
                        {t(`history.styles.${storyStyle}`) || STYLE_LABELS[storyStyle]}
                      </span>
                    </div>
                  </div>

                  <div
                    style={{
                      display: 'flex',
                      flexDirection: isMobile ? 'column' : 'row',
                      alignItems: isMobile ? 'stretch' : 'center',
                      gap: 8,
                      width: isMobile ? '100%' : 'auto',
                      marginTop: isMobile ? 8 : 0,
                    }}
                  >
                    <select
                      value={storyStyle}
                      onChange={(e) => setStoryStyle(e.target.value as any)}
                      style={{
                        background: '#21262d',
                        border: '1px solid #30363d',
                        color: '#c9d1d9',
                        padding: isMobile ? '10px 10px' : '6px 10px',
                        borderRadius: 6,
                        fontSize: 12,
                        width: isMobile ? '100%' : 'auto',
                        minHeight: isMobile ? 44 : undefined,
                      }}
                    >
                      {(Object.keys(STYLE_LABELS) as StoryStyle[]).map((k) => (
                        <option key={k} value={k}>{t(`history.styles.${k}`) || STYLE_LABELS[k]}</option>
                      ))}
                    </select>

                    <div style={{ display: 'flex', gap: 6, width: isMobile ? '100%' : 'auto' }}>
                      <button
                        onClick={copyToClipboard}
                        style={{
                          flex: isMobile ? 1 : 'none',
                          background: copied ? '#238636' : '#1f6feb',
                          border: '1px solid',
                          borderColor: copied ? '#2ea043' : '#388bfd',
                          color: '#fff',
                          padding: isMobile ? '10px 14px' : '6px 14px',
                          borderRadius: 6,
                          fontSize: 12,
                          cursor: 'pointer',
                          fontWeight: 600,
                          minHeight: isMobile ? 44 : undefined,
                          touchAction: 'manipulation',
                          WebkitTapHighlightColor: 'transparent' as any,
                          textAlign: 'center',
                        }}
                      >
                        {copied ? (t('history.copied') || '✓ Copied Prompt!') : (t('history.copyPrompt') || '📋 Copy Prompt')}
                      </button>
                      <button
                        onClick={downloadMarkdown}
                        style={{
                          background: '#21262d',
                          border: '1px solid #30363d',
                          color: '#c9d1d9',
                          padding: isMobile ? '10px 10px' : '6px 10px',
                          borderRadius: 6,
                          fontSize: 12,
                          cursor: 'pointer',
                          minHeight: isMobile ? 44 : undefined,
                          touchAction: 'manipulation',
                          WebkitTapHighlightColor: 'transparent' as any,
                        }}
                        title={t('history.downloadMdTooltip') || 'Download Markdown'}
                      >
                        {t('history.downloadMd') || '⬇️ .md'}
                      </button>
                      <button
                        onClick={downloadJSON}
                        style={{
                          background: '#21262d',
                          border: '1px solid #30363d',
                          color: '#c9d1d9',
                          padding: isMobile ? '10px 10px' : '6px 10px',
                          borderRadius: 6,
                          fontSize: 12,
                          cursor: 'pointer',
                          minHeight: isMobile ? 44 : undefined,
                          touchAction: 'manipulation',
                          WebkitTapHighlightColor: 'transparent' as any,
                        }}
                        title={t('history.downloadJsonTooltip') || 'Download JSON'}
                      >
                        {t('history.downloadJson') || '⬇️ JSON'}
                      </button>
                    </div>
                  </div>
                </div>
              </div>

              {/* Prompt Preview Box */}
              <div
                style={{
                  background: '#090d13',
                  border: '1px solid #21262d',
                  borderRadius: 6,
                  padding: isMobile ? 10 : 14,
                  maxHeight: isMobile ? 300 : 440,
                  overflow: 'auto',
                  fontFamily: 'ui-monospace, monospace',
                  fontSize: isMobile ? 10 : 11,
                  lineHeight: 1.5,
                  color: '#c9d1d9',
                  whiteSpace: 'pre-wrap',
                  wordBreak: 'break-word',
                }}
              >
                {llmPrompt}
              </div>
            </div>
          )}
        </div>

        {/* Footer — sticky so Close always reachable on phone */}
        <footer
          style={{
            padding: isMobile ? '8px 12px max(12px, env(safe-area-inset-bottom))' : '10px 18px',
            borderTop: '1px solid #21262d',
            background: '#161b22',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            fontSize: isMobile ? 10.5 : 11,
            color: '#8b949e',
            position: isMobile ? ('sticky' as const) : undefined,
            bottom: isMobile ? 0 : undefined,
            flexShrink: 0,
          }}
        >
          <span>{isMobile ? t('history.synthesizedMobile') : t('history.synthesized')}</span>
          <button
            onClick={onClose}
            style={{
              padding: isMobile ? '10px 16px' : '6px 16px',
              background: '#21262d',
              border: '1px solid #30363d',
              borderRadius: 6,
              color: '#c9d1d9',
              cursor: 'pointer',
              fontSize: isMobile ? 11 : 12,
              minHeight: isMobile ? 44 : undefined,
              touchAction: 'manipulation',
              WebkitTapHighlightColor: 'transparent' as any,
            }}
          >
            {t('history.close')}
          </button>
        </footer>
      </div>
    </div>
  )
}
