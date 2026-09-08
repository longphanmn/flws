import { createContext, useContext, useEffect, useState, ReactNode } from 'react'
import en from './locales/en.json'
import fr from './locales/fr.json'
import vi from './locales/vi.json'

const locales: Record<string, any> = { en, fr, vi, vn: vi }
export type Lang = 'en' | 'fr' | 'vi' | 'vn'
const STORAGE_KEY = 'flatland_lang'

function safeGet(key: string): string | null {
  try {
    return typeof localStorage !== 'undefined' ? localStorage.getItem(key) : null
  } catch {
    try { return typeof sessionStorage !== 'undefined' ? sessionStorage.getItem(key) : null } catch { return null }
  }
}
function safeSet(key: string, val: string) {
  try { localStorage.setItem(key, val); } catch {
    try { sessionStorage.setItem(key, val); } catch {}
  }
}
function getInitialLang(): Lang {
  const saved = safeGet(STORAGE_KEY) as Lang | null
  if (saved && locales[saved]) return saved === 'vn' ? 'vi' : saved
  const nav = typeof navigator !== 'undefined' ? navigator.language.slice(0, 2).toLowerCase() : 'en'
  if (nav === 'vi' || nav === 'vn') return 'vi'
  if (nav === 'fr') return 'fr'
  return 'en'
}

function resolve(path: string, dict: any): string {
  const parts = path.split('.')
  let cur = dict
  for (const p of parts) {
    if (cur && typeof cur === 'object' && p in cur) cur = cur[p]
    else return path
  }
  return typeof cur === 'string' ? cur : path
}

function interpolate(str: string, vars?: Record<string, any>): string {
  if (!vars) return str
  return str.replace(/\{\{(\w+)\}\}/g, (_, k) => (vars[k] != null ? String(vars[k]) : `{{${k}}}`))
}

interface I18nCtx {
  lang: Lang
  setLang: (l: Lang) => void
  t: (key: string, vars?: Record<string, any>) => string
}

const Ctx = createContext<I18nCtx>({ lang: 'en', setLang: () => {}, t: (k) => k })

export function I18nProvider({ children }: { children: ReactNode }) {
  const [lang, setLangRaw] = useState<Lang>(getInitialLang)
  const setLang = (l: Lang) => {
    const normalized = l === 'vn' ? 'vi' : (l as Lang)
    safeSet(STORAGE_KEY, normalized)
    setLangRaw(normalized)
    document.documentElement.lang = normalized
  }
  useEffect(() => {
    document.documentElement.lang = lang
  }, [lang])
  const dict = locales[lang] ?? en
  const t = (key: string, vars?: Record<string, any>) => interpolate(resolve(key, dict), vars)
  return <Ctx.Provider value={{ lang, setLang, t }}>{children}</Ctx.Provider>
}

export function useI18n() {
  return useContext(Ctx)
}
export function useT() {
  return useContext(Ctx).t
}

export function getTranslator(lang: string) {
  const normalized = lang === 'vn' ? 'vi' : lang
  const dict = locales[normalized] ?? en
  return (key: string, vars?: Record<string, any>) => interpolate(resolve(key, dict), vars)
}

