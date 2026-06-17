// 基调 / 方向 / 新闻分类 -> 颜色与字形的纯映射(从设计稿 renderVals 移植)。
// 返回 CSS 变量字符串,直接用于 inline style;随主题自动切换明暗。

import type { Dir, NewsCat, Tone } from '../types'

/** 当日基调 -> 时间线圆点颜色。 */
export const toneCol = (t: Tone): string =>
  t === 'risk-on' ? 'var(--up)' : t === 'risk-off' ? 'var(--down)' : 'var(--ink2)'

/** 变化量符号 -> 涨跌色(>0 绿 / <0 红 / 0 灰)。 */
export const colorForChange = (c: number): string =>
  c > 0 ? 'var(--up)' : c < 0 ? 'var(--down)' : 'var(--ink2)'

export interface DirInfo {
  ch: string
  col: string
}

/** 方向 -> 箭头字形 + 颜色。watch / 未知 -> 中性点。 */
export const dirInfo = (d: Dir): DirInfo =>
  d === 'up'
    ? { ch: '↑', col: 'var(--up)' }
    : d === 'down'
      ? { ch: '↓', col: 'var(--down)' }
      : { ch: '·', col: 'var(--ink2)' }

export interface CatStyle {
  lab: string
  col: string
  bg: string
  bd: string
}

/** 新闻分类英文枚举 -> 中文标签 + 徽章配色。 */
export const catMap: Record<NewsCat, CatStyle> = {
  fact: { lab: '事实', col: 'var(--ink)', bg: 'var(--paper2)', bd: 'var(--faint)' },
  read: { lab: '解读', col: 'var(--accent)', bg: 'transparent', bd: 'var(--accent)' },
  both: { lab: '事实+解读', col: 'var(--blue)', bg: 'transparent', bd: 'var(--blue)' },
  noise: { lab: '噪音', col: 'var(--ink2)', bg: 'transparent', bd: 'var(--faint)' },
}
