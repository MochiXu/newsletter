import type { Review as ReviewItem } from '../../types'
import SectionHead from '../SectionHead'

const MARK = {
  held: { ch: '✓', col: 'var(--up)', lab: '已兑现' },
  invalidated: { ch: '✕', col: 'var(--down)', lab: '已失效' },
  open: { ch: '○', col: 'var(--accent)', lab: '待观察' },
} as const

interface Props {
  reviews: ReviewItem[]
}

/** 假设复盘:圆形徽章(✓/✕/○)+ 原命题 + 状态标签 + 备注。无复盘则整段隐藏。 */
export default function Review({ reviews }: Props) {
  if (reviews.length === 0) return null
  return (
    <>
      <SectionHead label="REVIEW" zh="假设复盘" margin="22px 0 12px" />
      {reviews.map((r, i) => {
        const m = MARK[r.status]
        return (
          <div key={i} style={{ display: 'flex', gap: 9, marginBottom: 10 }}>
            <span
              style={{
                flex: '0 0 auto',
                width: 18,
                height: 18,
                borderRadius: '50%',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: 10,
                fontWeight: 700,
                color: m.col,
                border: `1.5px solid ${m.col}`,
                marginTop: 1,
              }}
            >
              {m.ch}
            </span>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: 12, lineHeight: 1.45, color: 'var(--ink)', textWrap: 'pretty' }}>{r.ifThen}</div>
              <div style={{ display: 'flex', gap: 8, alignItems: 'baseline', marginTop: 3, flexWrap: 'wrap' }}>
                <span style={{ fontFamily: 'var(--mono)', fontSize: 9.5, color: m.col, letterSpacing: '.5px' }}>
                  {m.lab}
                </span>
                <span style={{ fontSize: 10.5, color: 'var(--ink2)', lineHeight: 1.4 }}>{r.note}</span>
              </div>
            </div>
          </div>
        )
      })}
    </>
  )
}
