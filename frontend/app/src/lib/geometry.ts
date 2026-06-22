// SVG 几何:纯坐标映射(复刻设计 sparkGeom / 价格图)。末点用 HTML span 定位(避免非等比缩放变椭圆)。
import type { PricePoint } from '../types'

export interface Spark {
  points: string
  n: number
  xPct: (i: number) => number // 第 i 点 x 百分比(0..100),供 HTML 游标定位
  yPct: (i: number) => number // 第 i 点 y 百分比(0..100)
  dotTop: number // 末点圆心垂直百分比
}

/** 指标行迷你走势(viewBox 100×30)。点数 < 2 返回 null(不画)。 */
export function sparkGeom(vals: number[]): Spark | null {
  if (!vals || vals.length < 2) return null
  const W = 100,
    H = 30,
    pad = 4
  const min = Math.min(...vals)
  const max = Math.max(...vals)
  const range = max - min || 1
  const n = vals.length
  const xs = vals.map((_, i) => pad + ((W - 2 * pad) * i) / (n - 1))
  const ys = vals.map((v) => H - pad - ((H - 2 * pad) * (v - min)) / range)
  const points = xs.map((x, i) => `${x.toFixed(1)},${ys[i].toFixed(1)}`).join(' ')
  return { points, n, xPct: (i) => (xs[i] / W) * 100, yPct: (i) => (ys[i] / H) * 100, dotTop: (ys[n - 1] / H) * 100 }
}

export interface PriceGeom {
  line: string
  area: string
  n: number
  xPct: (i: number) => number // x 百分比(0..100)
  yPct: (i: number) => number // y 百分比(0..100)
  values: number[]
  dates: string[]
}

/** 30D 价格图(viewBox 320×110 pad9)。返回折线/面积点串 + 索引→百分比定位。 */
export function priceGeom(series: PricePoint[]): PriceGeom | null {
  if (!series || series.length < 2) return null
  const W = 320,
    H = 110,
    pad = 9
  const values = series.map((p) => p.value)
  const dates = series.map((p) => p.date)
  const mn = Math.min(...values)
  const mx = Math.max(...values)
  const rg = mx - mn || 1
  const n = values.length
  const xs = values.map((_, i) => (W * i) / (n - 1))
  const ys = values.map((v) => H - pad - ((H - 2 * pad) * (v - mn)) / rg)
  const line = xs.map((x, i) => `${x.toFixed(1)},${ys[i].toFixed(1)}`).join(' ')
  const area = `0,${H} ${line} ${W},${H}`
  return {
    line,
    area,
    n,
    values,
    dates,
    xPct: (i) => (xs[i] / W) * 100,
    yPct: (i) => (ys[i] / H) * 100,
  }
}
