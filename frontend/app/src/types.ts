// 展示平面数据契约(单一事实来源)。严格对应后端 py/newsletter/models.py 的 Brief。
// 设计/重建指南见 docs/frontend-rebuild.md。原则:完全 data-driven,忽略未知字段。

export type Tone = 'risk-on' | 'risk-off' | 'neutral'
export type Dir = 'up' | 'down' | 'watch'
export type MetricKind = 'yield' | 'spread' | 'index' | 'price'
export type NewsCat = 'fact' | 'read' | 'both' | 'noise'
export type ReviewStatus = 'held' | 'invalidated' | 'open'
export type PredDir = 'up' | 'down' | 'flat'
export type Horizon = 'next_1d' | 'h_5d' | 'h_20d' | 'h_60d'
export type SignalUnit = 'pct' | 'pct0' | 'bp' | 'z' | 'corr' | 'yield'
export type SignalGroup = 'trend' | 'momentum' | 'vol' | 'rates' | 'dollar' | 'cross_asset' | 'range'

export interface PricePoint {
  date: string
  value: number
}

/** text 中需上色强调的关键数字:t=原样子串(text 的子串),dir=方向(up绿/down红/flat中性)。 */
export interface Figure {
  t: string
  dir: PredDir
}

/** 事实层/解读层一条:tag=主题标签(可空),text=正文,figures=后端标注的需上色数字。 */
export interface TaggedItem {
  tag: string
  text: string
  figures: Figure[]
}

/** 指标表一行。spark=最近~20真实收盘点(带日期,因果),供小走势线 + hover。 */
export interface Metric {
  key: string
  label: string
  value: number
  change: number
  kind: MetricKind
  spark: PricePoint[]
}

/** 技术指标一条(代码计算)。value 原始数值,按 unit 格式化、按 group 分节。 */
export interface Signal {
  key: string
  label: string
  value: number
  unit: SignalUnit
  group: SignalGroup
}

/** 假设层 = 对固定方向的可证伪预测(纳指/黄金/广义美元/2Y)。 */
export interface Hypothesis {
  ifThen: string
  invalidation: string
  asset: string
  direction: PredDir
  horizon: Horizon
  confidence: number
  keyFactors: string[]
}

export interface Impact {
  asset: string
  watch: string
  dir: Dir
}

export interface Review {
  ifThen: string
  status: ReviewStatus
  note: string
}

export interface News {
  title: string
  source: string
  cat: NewsCat | null
  assets: string[]
  dir: Dir
  link: string
}

/** 单个交易日的完整简报(= 后端 Brief 契约)。 */
export interface Brief {
  date: string
  weekday: string
  issue: number
  time: string
  tone: Tone
  headline: string
  metrics: Metric[]
  signals: Signal[]
  regime: Record<string, string>
  priceSeries: Record<string, PricePoint[]>
  facts: TaggedItem[]
  reads: TaggedItem[]
  hypotheses: Hypothesis[]
  impacts: Impact[]
  reviews: Review[]
  news: News[]
}

export interface BriefsPayload {
  model: string
  generatedAt: string
  briefs: Brief[]
}

// ── 命中率 / 区间聚合(V2 评估层产出;当前后端不产 → 前端按 null 走空态)──────────
export type Grade = 'green' | 'yellow' | 'red'
export interface TrackData {
  days: Record<string, { score: number; grade: Grade }>
  months: Record<string, { sum: number; n: number; high: number; acc: number }>
  quarters: Record<string, { sum: number; n: number; high: number; acc: number }>
  years: Record<string, { sum: number; n: number; high: number; acc: number }>
}
export interface PeriodStat {
  k: string
  v: string
  d: 'up' | 'down' | 'flat'
}
export interface Period {
  id: string
  label: string
  sub: string
  tone: Tone
  acc: number
  headline: string
  stats: PeriodStat[]
}
export type Periods = Record<'month' | 'quarter' | 'half' | 'year', Period[]>

// ── 前端 UI 状态(非数据契约)─────────────────────────────────────────────
export type ThemeMode = 'auto' | 'light' | 'dark'
export type Granularity = 'day' | 'month' | 'quarter' | 'half' | 'year'
export type TrackMode = 'month' | 'quarter' | 'year' | 'all'

export interface Tweaks {
  accent: string | null
  showSparklines: boolean
  paperTexture: boolean
}

export interface Route {
  page: 'brief' | 'timeline' | 'track'
  date?: string
  gran?: Granularity
  from?: string
  mode?: TrackMode
  period?: string | null
}
