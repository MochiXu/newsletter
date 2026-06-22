// 格式化 + 颜色/方向工具(1:1 复刻设计 Component 的 fmt*/colorFor/dirInfo/toneCol 等)。
import type { Dir, Horizon, Metric, MetricKind, PredDir, SignalUnit, Tone } from '../types'

const priceFmt = (v: number) => v.toLocaleString('en-US', { maximumFractionDigits: 1 })

/** 指标值:yield→x.xx%、spread→±xxbp(值为百分点*100)、index→x.x、price→千分位。 */
export function fmtVal(m: Metric): string {
  const v = m.value
  if (m.kind === 'yield') return v.toFixed(2) + '%'
  if (m.kind === 'spread') return Math.round(v * 100) + 'bp'
  if (m.kind === 'index') return v.toFixed(1)
  if (m.kind === 'price') return priceFmt(v)
  return String(v)
}

/** 指标日变化:带符号。yield/spread→bp、index→x.x、price→小变动1位/大变动取整。 */
export function fmtChg(m: Metric): string {
  const c = m.change
  const s = c > 0 ? '+' : ''
  if (m.kind === 'yield' || m.kind === 'spread') return s + Math.round(c * 100) + 'bp'
  if (m.kind === 'index') return s + c.toFixed(1)
  if (m.kind === 'price') return s + (Math.abs(c) < 10 ? c.toFixed(1) : String(Math.round(c)))
  return s + String(c)
}

/** 价格图 hover 读数:yield→%、其它按量级。 */
export function fmtChartVal(kind: MetricKind, v: number): string {
  if (kind === 'yield') return v.toFixed(2) + '%'
  if (kind === 'spread') return Math.round(v * 100) + 'bp'
  if (kind === 'index') return v.toFixed(1)
  return Math.round(v).toLocaleString('en-US')
}

/** 单日涨跌% —— 仅价格/指数类有意义;利率/利差返回 null(该列显示 —,bp 才是对的)。 */
export function fmtPctChange(m: Metric): string | null {
  if (m.kind !== 'price' && m.kind !== 'index') return null
  const prev = m.value - m.change
  if (!prev) return null
  const p = (m.change / prev) * 100
  return (p >= 0 ? '+' : '') + p.toFixed(2) + '%'
}

/** 技术指标 value → 显示串(与后端 render._sig_fmt 一致)。 */
export function fmtSignal(unit: SignalUnit, v: number): string {
  switch (unit) {
    case 'pct':
      return (v >= 0 ? '+' : '') + (v * 100).toFixed(1) + '%'
    case 'pct0':
      return (v * 100).toFixed(1) + '%'
    case 'bp':
      return (v >= 0 ? '+' : '') + Math.round(v) + 'bp'
    case 'z':
      return 'z=' + v.toFixed(2)
    case 'yield':
      return v.toFixed(2) + '%'
    case 'corr':
      return v.toFixed(2)
    default:
      return String(v)
  }
}

/** 带符号单位(pct/bp/z/corr)按正负染色;电平(pct0/yield)中性。 */
export const signalSigned = (unit: SignalUnit): boolean =>
  unit === 'pct' || unit === 'bp' || unit === 'z' || unit === 'corr'

/** 涨跌着色。 */
export const colorFor = (c: number): string => (c > 0 ? 'var(--up)' : c < 0 ? 'var(--down)' : 'var(--ink2)')

export interface DirInfo {
  ch: string
  col: string
}
export const dirInfo = (d: Dir): DirInfo =>
  d === 'up'
    ? { ch: '↑', col: 'var(--up)' }
    : d === 'down'
      ? { ch: '↓', col: 'var(--down)' }
      : { ch: '·', col: 'var(--ink2)' }

/** 基调 → 时间线圆点颜色。 */
export const toneCol = (t: Tone): string =>
  t === 'risk-on' ? 'var(--up)' : t === 'risk-off' ? 'var(--down)' : 'var(--ink2)'

// 预测卡映射
export const ASSET_CN: Record<string, string> = {
  NASDAQCOM: '纳指',
  XAUUSD: '黄金',
  DTWEXBGS: '广义美元',
  DGS2: '美债2Y',
}
export const HORIZON_CN: Record<Horizon, string> = {
  next_1d: '次日',
  h_5d: '5日',
  h_20d: '20日',
  h_60d: '60日',
}
export const PRED_DIR: Record<PredDir, { ch: string; col: string; lab: string }> = {
  up: { ch: '↑', col: 'var(--up)', lab: '看涨' },
  down: { ch: '↓', col: 'var(--down)', lab: '看跌' },
  flat: { ch: '→', col: 'var(--ink2)', lab: '横盘' },
}

// 价格图资产 → 中文短名(key = metric.key 小写)
export const CHART_LABEL: Record<string, string> = {
  nasdaqcom: '纳指',
  xauusd: '黄金',
  dtwexbgs: '广义美元',
  dgs10: 'US10Y',
  vixcls: 'VIX',
}
// 价格图资产 → 取数值格式所需的 kind
export const CHART_KIND: Record<string, MetricKind> = {
  nasdaqcom: 'index',
  xauusd: 'price',
  dtwexbgs: 'index',
  dgs10: 'yield',
  vixcls: 'index',
}
