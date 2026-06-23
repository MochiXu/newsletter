import { useState, type CSSProperties } from 'react'
import type { News, NewsCat } from '../../types'
import { dirInfo } from '../../lib/format'
import { Card, SectionHead } from '../../components/Card'

const catMap: Record<NewsCat, { lab: string; col: string; bg: string; bd: string }> = {
  fact: { lab: '事实', col: 'var(--ink)', bg: 'var(--paper2)', bd: 'var(--faint)' },
  read: { lab: '解读', col: 'var(--accent)', bg: 'transparent', bd: 'var(--accent)' },
  both: { lab: '事实+解读', col: 'var(--blue)', bg: 'transparent', bd: 'var(--blue)' },
  noise: { lab: '噪音', col: 'var(--ink2)', bg: 'transparent', bd: 'var(--faint)' },
}

const catChip = (active: boolean): CSSProperties => ({
  display: 'inline-flex',
  alignItems: 'baseline',
  gap: 4,
  fontFamily: 'var(--mono)',
  fontSize: 10,
  padding: '3px 8px',
  borderRadius: 4,
  cursor: 'pointer',
  color: active ? 'var(--paper)' : 'var(--ink2)',
  background: active ? 'var(--accent)' : 'var(--paper2)',
  border: '1px solid ' + (active ? 'var(--accent)' : 'var(--faint)'),
  transition: 'all .15s',
})

/** NEWS 新闻:类目(影响资产)计数 + 可点筛选,列表常显;每条多资产标签 + 事实/解读类型 + 方向 + 链接。 */
export default function NewsCard({ news }: { news: News[] }) {
  const [filter, setFilter] = useState<string | null>(null)
  if (news.length === 0) return null // 数据缺失 → 自动不展示

  // 影响资产 = 多值类目;一条新闻命中多个资产则每个都计数
  const counts = new Map<string, number>()
  for (const n of news) for (const a of n.assets || []) counts.set(a, (counts.get(a) ?? 0) + 1)
  const cats = [...counts.entries()].sort((a, b) => b[1] - a[1])
  const shown = filter ? news.filter((n) => (n.assets || []).includes(filter)) : news

  return (
    <Card punch>
      <SectionHead label="NEWS" zh="新闻分类" margin="0 0 8px" />

      {/* 类目(影响资产)计数,常显;点一下按该类目筛选 */}
      {cats.length > 0 && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 9 }}>
          {cats.map(([a, c]) => (
            <button
              key={a}
              style={catChip(filter === a)}
              onClick={() => setFilter((f) => (f === a ? null : a))}
            >
              {a}
              <span style={{ fontWeight: 700 }}>{c}</span>
            </button>
          ))}
        </div>
      )}

      {/* 筛选时给个计数 + 取消提示;未筛选直接列表 */}
      {filter && (
        <div style={{ fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--ink2)', marginBottom: 6 }}>
          仅看 {filter} · {shown.length}/{news.length} 条(点上方标签取消)
        </div>
      )}

      {shown.map((n, i) => {
          const cat = n.cat ? catMap[n.cat] : null
          const di = dirInfo(n.dir)
          const titleColor = n.cat === 'noise' ? 'var(--ink2)' : 'var(--ink)'
          return (
            <div key={i} style={{ padding: '9px 0', borderBottom: '1px dashed var(--hair)' }}>
              <div style={{ display: 'flex', gap: 8, alignItems: 'flex-start' }}>
                {cat && (
                  <span
                    style={{
                      flex: '0 0 auto',
                      fontFamily: 'var(--mono)',
                      fontSize: 9,
                      letterSpacing: '.5px',
                      padding: '2px 6px',
                      borderRadius: 4,
                      color: cat.col,
                      background: cat.bg,
                      border: `1px solid ${cat.bd}`,
                      whiteSpace: 'nowrap',
                    }}
                  >
                    {cat.lab}
                  </span>
                )}
                {n.link ? (
                  <a
                    href={n.link}
                    target="_blank"
                    rel="noopener noreferrer"
                    title="打开原文 ↗"
                    style={{
                      flex: '1 1 auto',
                      fontSize: 12,
                      lineHeight: 1.45,
                      color: titleColor,
                      textWrap: 'pretty',
                      textDecoration: 'none',
                    }}
                    onMouseEnter={(e) => (e.currentTarget.style.color = 'var(--accent)')}
                    onMouseLeave={(e) => (e.currentTarget.style.color = titleColor)}
                  >
                    {n.title}
                    <span style={{ fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--ink2)', marginLeft: 4 }}>↗</span>
                  </a>
                ) : (
                  <span style={{ flex: '1 1 auto', fontSize: 12, lineHeight: 1.45, color: titleColor, textWrap: 'pretty' }}>
                    {n.title}
                  </span>
                )}
                <span style={{ fontFamily: 'var(--mono)', fontSize: 12, color: di.col, flex: '0 0 auto' }}>{di.ch}</span>
              </div>
              <div style={{ display: 'flex', gap: 6, alignItems: 'center', marginTop: 6, flexWrap: 'wrap' }}>
                <span style={{ fontFamily: 'var(--mono)', fontSize: 9.5, color: 'var(--ink2)' }}>{n.source}</span>
                {(n.assets || []).map((a, j) => (
                  <span
                    key={j}
                    style={{
                      fontFamily: 'var(--mono)',
                      fontSize: 9,
                      color: a === filter ? 'var(--accent)' : 'var(--ink2)',
                      border: '1px solid ' + (a === filter ? 'var(--accent)' : 'var(--hair)'),
                      borderRadius: 3,
                      padding: '1px 5px',
                    }}
                  >
                    {a}
                  </span>
                ))}
              </div>
            </div>
          )
        })}
    </Card>
  )
}
