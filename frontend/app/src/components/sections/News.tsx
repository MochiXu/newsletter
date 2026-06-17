import type { News as NewsItem } from '../../types'
import { catMap, dirInfo } from '../../lib/tone'
import SectionHead from '../SectionHead'

interface Props {
  news: NewsItem[]
}

/** 新闻分类:分类徽章(事实/解读/事实+解读/噪音)+ 标题 + 方向箭头 + 来源/受影响资产标签。 */
export default function News({ news }: Props) {
  return (
    <>
      <SectionHead label="NEWS" zh="新闻分类" margin="22px 0 6px" />
      {news.map((n, i) => {
        const cat = n.cat ? catMap[n.cat] : null
        const di = dirInfo(n.dir)
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
              <span
                style={{
                  flex: '1 1 auto',
                  fontSize: 12,
                  lineHeight: 1.45,
                  color: n.cat === 'noise' ? 'var(--ink2)' : 'var(--ink)',
                  textWrap: 'pretty',
                }}
              >
                {n.title}
              </span>
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
    </>
  )
}
