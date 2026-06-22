import type { Metric } from '../../types'
import { colorFor, fmtChg, fmtVal } from '../../lib/format'
import { sparkGeom } from '../../lib/geometry'
import { Card, SectionHead } from '../../components/Card'

/** MARKET DATA 指标表:名称 / 真实 sparkline / 值 / 日变化。 */
export default function MarketData({ metrics, showSparklines }: { metrics: Metric[]; showSparklines: boolean }) {
  return (
    <Card>
      <SectionHead label="MARKET DATA" zh="当日指标" />
      {metrics.map((m) => {
        const col = colorFor(m.change)
        const sp = showSparklines ? sparkGeom(m.spark) : null
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
            <span style={{ position: 'relative', display: 'block', minWidth: 0, height: 26 }}>
              {sp && (
                <>
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
                  </svg>
                  <span
                    style={{
                      position: 'absolute',
                      right: 0,
                      top: `${sp.dotTop}%`,
                      width: 5,
                      height: 5,
                      borderRadius: '50%',
                      background: col,
                      transform: 'translate(50%,-50%)',
                    }}
                  />
                </>
              )}
            </span>
            <span style={{ fontFamily: 'var(--mono)', fontSize: 12.5, color: 'var(--ink)', textAlign: 'right' }}>
              {fmtVal(m)}
            </span>
            <span style={{ fontFamily: 'var(--mono)', fontSize: 12, textAlign: 'right', color: col }}>{fmtChg(m)}</span>
          </div>
        )
      })}
    </Card>
  )
}
