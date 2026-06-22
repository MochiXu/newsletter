import type { CSSProperties } from 'react'
import { nav } from '../lib/hooks'

const navTab = (active: boolean): CSSProperties => ({
  padding: '10px 14px',
  marginBottom: -1,
  fontSize: 12.5,
  fontFamily: 'var(--sans)',
  fontWeight: active ? 700 : 500,
  border: 'none',
  background: 'transparent',
  color: active ? 'var(--ink)' : 'var(--ink2)',
  borderBottom: active ? '2px solid var(--accent)' : '2px solid transparent',
  cursor: 'pointer',
  transition: 'color .18s',
})

const TABS: { page: string; hash: string; zh: string; en: string }[] = [
  { page: 'brief', hash: '#/brief', zh: '简报', en: 'Briefing' },
  { page: 'timeline', hash: '#/timeline', zh: '时间线', en: 'Timeline' },
  { page: 'track', hash: '#/track', zh: '命中率', en: 'Track Record' },
]

/** 一级导航 tab(下边框选中态)。 */
export default function NavTabs({ page }: { page: string }) {
  return (
    <div
      style={{
        display: 'flex',
        gap: 4,
        margin: '20px 0 0',
        borderBottom: '1px solid var(--hair)',
        alignItems: 'flex-end',
        flexWrap: 'wrap',
      }}
    >
      {TABS.map((t) => (
        <button key={t.page} style={navTab(page === t.page)} onClick={() => nav(t.hash)}>
          {t.zh} · {t.en}
        </button>
      ))}
    </div>
  )
}
