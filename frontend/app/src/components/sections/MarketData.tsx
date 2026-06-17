import type { Metric } from '../../types'
import { colorForChange } from '../../lib/tone'
import { fmtChg, fmtVal } from '../../lib/format'
import { makeSpark } from '../../lib/sparkline'
import SectionHead from '../SectionHead'

interface Props {
  metrics: Metric[]
  date: string
  showSparklines: boolean
}

/** 当日指标表:固定网格 52px / 走势线 / 数值 / 变化量,每行一条虚线分隔。 */
export default function MarketData({ metrics, date, showSparklines }: Props) {
  return (
    <>
      <SectionHead label="MARKET DATA" zh="当日指标" margin="20px 0 12px" />
      {metrics.map((m) => {
        const col = colorForChange(m.change)
        const sp = makeSpark(date + m.key, m.change)
        return (
          <div
            key={m.key}
            style={{
              display: 'grid',
              gridTemplateColumns: '52px 1fr 66px 50px',
              alignItems: 'center',
              gap: 8,
              padding: '5px 0',
              borderBottom: '1px dashed var(--hair)',
            }}
          >
            <span style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--ink2)', letterSpacing: '.3px' }}>
              {m.label}
            </span>
            <span style={{ display: 'block', minWidth: 0, height: 26 }}>
              {showSparklines && (
                <svg
                  viewBox="0 0 100 30"
                  preserveAspectRatio="none"
                  style={{ width: '100%', height: 26, display: 'block', overflow: 'visible' }}
                >
                  <polyline
                    points={sp.points}
                    fill="none"
                    stroke={col}
                    strokeWidth={1.5}
                    strokeLinejoin="round"
                    strokeLinecap="round"
                    vectorEffect="non-scaling-stroke"
                  />
                  <circle cx={sp.dotX} cy={sp.dotY} r={2.4} fill={col} />
                </svg>
              )}
            </span>
            <span style={{ fontFamily: 'var(--mono)', fontSize: 12.5, color: 'var(--ink)', textAlign: 'right' }}>
              {fmtVal(m)}
            </span>
            <span style={{ fontFamily: 'var(--mono)', fontSize: 12, textAlign: 'right', color: col }}>
              {fmtChg(m)}
            </span>
          </div>
        )
      })}
    </>
  )
}
