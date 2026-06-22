import { useEffect, useState } from 'react'
import type { Route, ThemeMode, Tweaks } from '../types'

// ── hash 路由 ─────────────────────────────────────────────────────────────
function parseHash(): Route {
  const raw = (location.hash || '').replace(/^#\/?/, '')
  const parts = raw.split('/').filter(Boolean)
  if (parts.length === 0) return { page: 'brief' }
  const [head, a, b] = parts
  if (head === 'timeline') {
    const gran = (['day', 'month', 'quarter', 'half', 'year'] as const).find((g) => g === a) || 'day'
    return { page: 'timeline', gran }
  }
  if (head === 'track') {
    if (!a) return { page: 'track', mode: 'year', period: null }
    if (['month', 'quarter', 'year', 'all'].includes(a))
      return { page: 'track', mode: a as Route['mode'], period: b || null }
    if (/^\d{4}-Q\d$/.test(a)) return { page: 'track', mode: 'quarter', period: a }
    if (/^\d{4}-\d{2}$/.test(a)) return { page: 'track', mode: 'month', period: a }
    if (/^\d{4}$/.test(a)) return { page: 'track', mode: 'year', period: a }
    return { page: 'track', mode: 'year', period: null }
  }
  if (head === 'brief') {
    let gran: Route['gran'] = 'day'
    if (/^\d{4}-\d{2}-\d{2}$/.test(a)) gran = 'day'
    else if (/^\d{4}-Q\d$/.test(a)) gran = 'quarter'
    else if (/^\d{4}-H\d$/.test(a)) gran = 'half'
    else if (/^\d{4}-\d{2}$/.test(a)) gran = 'month'
    else if (/^\d{4}$/.test(a)) gran = 'year'
    return { page: 'brief', date: a, gran, from: b }
  }
  return { page: 'brief' }
}

export const nav = (hash: string) => {
  location.hash = hash
}

export function useHashRoute(): Route {
  const [route, setRoute] = useState<Route>(() => parseHash())
  useEffect(() => {
    const onHash = () => setRoute(parseHash())
    window.addEventListener('hashchange', onHash)
    return () => window.removeEventListener('hashchange', onHash)
  }, [])
  return route
}

// ── 主题 ──────────────────────────────────────────────────────────────────
const THEME_KEY = 'mb_theme'
export function readTheme(): ThemeMode {
  try {
    const t = localStorage.getItem(THEME_KEY)
    if (t === 'auto' || t === 'light' || t === 'dark') return t
  } catch {
    /* ignore */
  }
  return 'auto'
}
export function writeTheme(m: ThemeMode) {
  try {
    localStorage.setItem(THEME_KEY, m)
  } catch {
    /* ignore */
  }
}

// ── Tweaks ────────────────────────────────────────────────────────────────
const TWEAKS_KEY = 'mb_tweaks'
export const DEFAULT_TWEAKS: Tweaks = { accent: null, showSparklines: true, paperTexture: true }
export function readTweaks(): Tweaks {
  try {
    const raw = localStorage.getItem(TWEAKS_KEY)
    if (raw) return { ...DEFAULT_TWEAKS, ...(JSON.parse(raw) as Partial<Tweaks>) }
  } catch {
    /* ignore */
  }
  return DEFAULT_TWEAKS
}
export function writeTweaks(t: Tweaks) {
  try {
    localStorage.setItem(TWEAKS_KEY, JSON.stringify(t))
  } catch {
    /* ignore */
  }
}

// ── 窄屏断点(760）──────────────────────────────────────────────────────────
export function useIsMobile(): boolean {
  const [mob, setMob] = useState(() => typeof window !== 'undefined' && window.innerWidth < 760)
  useEffect(() => {
    const onResize = () => setMob(window.innerWidth < 760)
    window.addEventListener('resize', onResize)
    return () => window.removeEventListener('resize', onResize)
  }, [])
  return mob
}
