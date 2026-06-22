import { useRef, useState, type CSSProperties } from 'react'
import type { PricePoint } from '../../types'
import { CHART_KIND, CHART_LABEL, fmtChartVal } from '../../lib/format'
import { priceGeom } from '../../lib/geometry'
import { Card, SectionHead } from '../../components/Card'

const tabStyle = (active: boolean): CSSProperties => ({
  fontFamily: 'var(--mono)',
  fontSize: 10,
  letterSpacing: '.3px',
  padding: '3px 9px',
  borderRadius: 20,
  cursor: 'pointer',
  border: '1px solid ' + (active ? 'var(--accent)' : 'var(--hair)'),
  background: active ? 'var(--accent)' : 'transparent',
  color: active ? 'var(--paper)' : 'var(--ink2)',
  transition: 'all .15s',
})

const shortDate = (iso: string) => (iso ? iso.slice(5).replace('-', '.') : '')

/** PRICE 30D 可交互价格图:资产 tab + 悬停十字游标读数。 */
export default function PriceChart({ priceSeries }: { priceSeries: Record<string, PricePoint[]> }) {
  const keys = Object.keys(priceSeries).filter((k) => (priceSeries[k]?.length ?? 0) >= 2)
  const [asset, setAsset] = useState<string>(keys[0] ?? '')
  const [hover, setHover] = useState<number | null>(null)
  const svgRef = useRef<SVGSVGElement>(null)

  if (keys.length === 0) return null
  const activeKey = keys.includes(asset) ? asset : keys[0]
  const series = priceSeries[activeKey]
  const geom = priceGeom(series)
  if (!geom) return null

  const kind = CHART_KIND[activeKey] ?? 'index'
  const chg = geom.values[geom.n - 1] - geom.values[0]
  const col = chg >= 0 ? 'var(--up)' : 'var(--down)'
  const hi = hover ?? geom.n - 1
  const hoverVal = geom.values[hi]
  const hoverDate = geom.dates[hi]

  const move = (clientX: number) => {
    const el = svgRef.current
    if (!el) return
    const r = el.getBoundingClientRect()
    const idx = Math.round(((clientX - r.left) / r.width) * (geom.n - 1))
    setHover(Math.max(0, Math.min(geom.n - 1, idx)))
  }

  return (
    <Card>
      <SectionHead label="PRICE" zh="走势 · 30D" />
      <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap', marginBottom: 10 }}>
        {keys.map((k) => (
          <button
            key={k}
            style={tabStyle(k === activeKey)}
            onClick={() => {
              setAsset(k)
              setHover(null)
            }}
          >
            {CHART_LABEL[k] ?? k}
          </button>
        ))}
      </div>

      <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', marginBottom: 4 }}>
        <span style={{ fontFamily: 'var(--mono)', fontSize: 18, fontWeight: 600, color: 'var(--ink)' }}>
          {fmtChartVal(kind, hoverVal)}
        </span>
        <span style={{ fontFamily: 'var(--mono)', fontSize: 10.5, color: 'var(--ink2)' }}>{hoverDate}</span>
      </div>

      <div style={{ position: 'relative', width: '100%' }}>
        <svg
          ref={svgRef}
          viewBox="0 0 320 110"
          preserveAspectRatio="none"
          style={{ width: '100%', height: 110, display: 'block', cursor: 'crosshair', touchAction: 'none' }}
          onMouseMove={(e) => move(e.clientX)}
          onMouseLeave={() => setHover(null)}
          onTouchStart={(e) => move(e.touches[0].clientX)}
          onTouchMove={(e) => move(e.touches[0].clientX)}
        >
          <polyline points={geom.area} fill={col} opacity={0.07} stroke="none" />
          <polyline
            points={geom.line}
            fill="none"
            stroke={col}
            strokeWidth={1.6}
            strokeLinejoin="round"
            strokeLinecap="round"
            vectorEffect="non-scaling-stroke"
          />
          <line
            x1={(geom.xPct(hi) / 100) * 320}
            y1={0}
            x2={(geom.xPct(hi) / 100) * 320}
            y2={110}
            stroke="var(--ink2)"
            strokeWidth={1}
            vectorEffect="non-scaling-stroke"
            opacity={hover != null ? 0.55 : 0}
          />
        </svg>
        <span
          style={{
            position: 'absolute',
            left: `${geom.xPct(hi)}%`,
            top: `${geom.yPct(hi)}%`,
            width: 7,
            height: 7,
            borderRadius: '50%',
            background: col,
            transform: 'translate(-50%,-50%)',
            pointerEvents: 'none',
          }}
        />
      </div>

      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          marginTop: 6,
          fontFamily: 'var(--mono)',
          fontSize: 9,
          color: 'var(--ink2)',
        }}
      >
        <span>{shortDate(geom.dates[0])}</span>
        <span>30 交易日</span>
        <span>{shortDate(geom.dates[geom.n - 1])}</span>
      </div>
    </Card>
  )
}
