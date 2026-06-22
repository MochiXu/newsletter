import { useRef, useState, type CSSProperties } from 'react'
import { createPortal } from 'react-dom'
import type { Metric } from '../../types'
import { colorFor, fmtChartVal, fmtChg, fmtPctChange, fmtVal } from '../../lib/format'
import { sparkGeom } from '../../lib/geometry'
import { Card, SectionHead } from '../../components/Card'

const GRID = '48px 1fr 60px 48px 58px'

interface Hover {
  key: string
  idx: number
  cx: number
  cy: number
}

/** MARKET DATA 指标表:名称 / 近20日走势(逐行可 hover) / 数值 / 单日Δ / 单日%。 */
export default function MarketData({ metrics, showSparklines }: { metrics: Metric[]; showSparklines: boolean }) {
  const [hover, setHover] = useState<Hover | null>(null)
  const cellRefs = useRef<Record<string, SVGSVGElement | null>>({})

  const onMove = (m: Metric, clientX: number, clientY: number) => {
    const el = cellRefs.current[m.key]
    if (!el || m.spark.length < 2) return
    const r = el.getBoundingClientRect()
    const idx = Math.round(((clientX - r.left) / r.width) * (m.spark.length - 1))
    setHover({ key: m.key, idx: Math.max(0, Math.min(m.spark.length - 1, idx)), cx: clientX, cy: clientY })
  }

  const hoveredMetric = hover ? metrics.find((m) => m.key === hover.key) : undefined
  const hoveredPt = hoveredMetric ? hoveredMetric.spark[hover!.idx] : undefined

  const headCell: CSSProperties = {
    fontFamily: 'var(--mono)',
    fontSize: 8.5,
    letterSpacing: '.5px',
    color: 'var(--ink2)',
    textTransform: 'uppercase',
  }

  return (
    <Card punch>
      <SectionHead label="MARKET DATA" zh="当日指标" />

      {/* 列头 */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: GRID,
          gap: 8,
          alignItems: 'center',
          padding: '0 0 5px',
          borderBottom: '1px solid var(--hair)',
        }}
      >
        <span style={headCell}>指标</span>
        <span style={headCell}>走势 · 近20日</span>
        <span style={{ ...headCell, textAlign: 'right' }}>数值</span>
        <span style={{ ...headCell, textAlign: 'right' }}>单日Δ</span>
        <span style={{ ...headCell, textAlign: 'right' }}>单日%</span>
      </div>

      {metrics.map((m) => {
        const col = colorFor(m.change)
        const sp = showSparklines ? sparkGeom(m.spark.map((p) => p.value)) : null
        const pct = fmtPctChange(m)
        const isHovered = hover?.key === m.key
        return (
          <div
            key={m.key}
            style={{
              display: 'grid',
              gridTemplateColumns: GRID,
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
                    ref={(el) => {
                      cellRefs.current[m.key] = el
                    }}
                    viewBox="0 0 100 30"
                    preserveAspectRatio="none"
                    style={{ width: '100%', height: 26, display: 'block', overflow: 'visible', cursor: 'crosshair' }}
                    onMouseMove={(e) => onMove(m, e.clientX, e.clientY)}
                    onMouseLeave={() => setHover((h) => (h?.key === m.key ? null : h))}
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
                    {isHovered && (
                      <line
                        x1={sp.xPct(hover!.idx)}
                        y1={0}
                        x2={sp.xPct(hover!.idx)}
                        y2={30}
                        stroke="var(--ink2)"
                        strokeWidth={1}
                        vectorEffect="non-scaling-stroke"
                        opacity={0.5}
                      />
                    )}
                  </svg>
                  {/* 末点(当日) */}
                  <span
                    style={{
                      position: 'absolute',
                      left: `${sp.xPct(sp.n - 1)}%`,
                      top: `${sp.dotTop}%`,
                      width: 5,
                      height: 5,
                      borderRadius: '50%',
                      background: col,
                      transform: 'translate(-50%,-50%)',
                      pointerEvents: 'none',
                    }}
                  />
                  {/* hover 游标点 */}
                  {isHovered && (
                    <span
                      style={{
                        position: 'absolute',
                        left: `${sp.xPct(hover!.idx)}%`,
                        top: `${sp.yPct(hover!.idx)}%`,
                        width: 6,
                        height: 6,
                        borderRadius: '50%',
                        background: 'var(--accent)',
                        transform: 'translate(-50%,-50%)',
                        pointerEvents: 'none',
                      }}
                    />
                  )}
                </>
              )}
            </span>
            <span style={{ fontFamily: 'var(--mono)', fontSize: 12.5, color: 'var(--ink)', textAlign: 'right' }}>
              {fmtVal(m)}
            </span>
            <span style={{ fontFamily: 'var(--mono)', fontSize: 11.5, textAlign: 'right', color: col }}>{fmtChg(m)}</span>
            <span
              style={{
                fontFamily: 'var(--mono)',
                fontSize: 11.5,
                textAlign: 'right',
                color: pct ? col : 'var(--ink2)',
              }}
            >
              {pct ?? '—'}
            </span>
          </div>
        )
      })}

      {/* hover 浮动读数(日期 + 值)。portal 到 body:脱离被 receiptIn 动画 transform 的小票子树,
          否则 position:fixed 会相对那个 transform 祖先定位而非视口,导致气泡漂移。 */}
      {hover &&
        hoveredMetric &&
        hoveredPt &&
        createPortal(
          <div
            style={{
              position: 'fixed',
              left: Math.min(hover.cx + 12, window.innerWidth - 180),
              top: Math.min(hover.cy + 14, window.innerHeight - 30),
              zIndex: 80,
              pointerEvents: 'none',
              background: 'var(--ink)',
              color: 'var(--paper)',
              fontFamily: 'var(--mono)',
              fontSize: 10,
              padding: '3px 7px',
              borderRadius: 4,
              whiteSpace: 'nowrap',
              boxShadow: '0 4px 12px -4px rgba(0,0,0,.5)',
            }}
          >
            {hoveredMetric.label} · {hoveredPt.date} · {fmtChartVal(hoveredMetric.kind, hoveredPt.value)}
          </div>,
          document.getElementById('mb-root') ?? document.body,
        )}
    </Card>
  )
}
