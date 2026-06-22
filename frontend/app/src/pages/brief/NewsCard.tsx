import type { News, NewsCat } from '../../types'
import { dirInfo } from '../../lib/format'
import { Card, SectionHead } from '../../components/Card'

const catMap: Record<NewsCat, { lab: string; col: string; bg: string; bd: string }> = {
  fact: { lab: '事实', col: 'var(--ink)', bg: 'var(--paper2)', bd: 'var(--faint)' },
  read: { lab: '解读', col: 'var(--accent)', bg: 'transparent', bd: 'var(--accent)' },
  both: { lab: '事实+解读', col: 'var(--blue)', bg: 'transparent', bd: 'var(--blue)' },
  noise: { lab: '噪音', col: 'var(--ink2)', bg: 'transparent', bd: 'var(--faint)' },
}

/** NEWS 新闻分类:分类徽章 + 可点标题(新标签页)+ 方向 + 来源/资产标签。 */
export default function NewsCard({ news }: { news: News[] }) {
  if (news.length === 0) return null
  return (
    <Card>
      <SectionHead label="NEWS" zh="新闻分类" margin="0 0 6px" />
      {news.map((n, i) => {
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
              {n.assets.map((a, j) => (
                <span
                  key={j}
                  style={{
                    fontFamily: 'var(--mono)',
                    fontSize: 9,
                    color: 'var(--ink2)',
                    border: '1px solid var(--hair)',
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
