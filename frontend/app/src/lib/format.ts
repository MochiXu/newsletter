// 指标数值 / 变化量格式化(从设计稿 fmtVal/fmtChg 移植)。单位由 metric.kind 决定。
import type { Metric } from '../types'

/** 数值:yield→x.xx%、spread→±xxbp(值为百分点,*100)、index→x.x、price→千分位。 */
export function fmtVal(m: Metric): string {
  const v = m.value
  if (m.kind === 'yield') return v.toFixed(2) + '%'
  if (m.kind === 'spread') return Math.round(v * 100) + 'bp'
  if (m.kind === 'index') return v.toFixed(1)
  if (m.kind === 'price') return v.toLocaleString('en-US')
  return String(v)
}

/** 变化量:正数带 +;yield/spread→bp、index→x.x、price→整数。 */
export function fmtChg(m: Metric): string {
  const c = m.change
  const s = c > 0 ? '+' : ''
  if (m.kind === 'yield' || m.kind === 'spread') return s + Math.round(c * 100) + 'bp'
  if (m.kind === 'index') return s + c.toFixed(1)
  if (m.kind === 'price') return s + Math.round(c)
  return s + String(c)
}
