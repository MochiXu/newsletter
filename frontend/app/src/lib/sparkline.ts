// 迷你走势线(从设计稿 makeSpark 移植):确定性合成折线 —— 用 (date+key) 作种子的
// FNV-1a 哈希 + mulberry32 伪随机,叠加按 change 符号的方向漂移。
//
// 说明:这是「氛围」走势线,不是真实历史序列(真实数据才两天、且常停更,画不出 18 点)。
// 同一天同一指标稳定不变;涨/跌通过漂移体现上行/下行趋势。颜色由调用方按 change 决定。

export interface Spark {
  points: string // SVG polyline points
  dotX: number
  dotY: number
}

const N = 18
const W = 100
const H = 30
const PAD = 4

export function makeSpark(seed: string, change: number): Spark {
  let h = 2166136261 >>> 0
  for (let i = 0; i < seed.length; i++) {
    h ^= seed.charCodeAt(i)
    h = Math.imul(h, 16777619) >>> 0
  }
  let s = h
  const rnd = () => {
    s = (s + 0x6d2b79f5) >>> 0
    let t = s
    t = Math.imul(t ^ (t >>> 15), t | 1)
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61)
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }

  const vals: number[] = []
  let v = 0
  const drift = (change > 0 ? 1 : change < 0 ? -1 : 0) * 0.16
  for (let i = 0; i < N; i++) {
    v += (rnd() - 0.5) * 0.95 + drift
    vals.push(v)
  }

  const min = Math.min(...vals)
  const max = Math.max(...vals)
  const range = max - min || 1
  const pts = vals.map((val, i) => {
    const x = PAD + ((W - 2 * PAD) * i) / (N - 1)
    const y = H - PAD - ((H - 2 * PAD) * (val - min)) / range
    return `${x.toFixed(1)},${y.toFixed(1)}`
  })
  const [lx, ly] = pts[pts.length - 1].split(',')
  return { points: pts.join(' '), dotX: +lx, dotY: +ly }
}
