// 展示平面数据契约(单一事实来源)。
// 与后端 py/newsletter/render.py 的 render_json() 输出严格对应;详见 docs/frontend-plane.md §3.1。
// 注意:tone / impacts[].dir / news[].dir 均为必填——它们驱动时间线染色与方向箭头,
// 不是「可选缺口」(后端已在 emit_brief schema 产出)。

export type Tone = 'risk-on' | 'risk-off' | 'neutral'
export type Dir = 'up' | 'down' | 'watch'
export type MetricKind = 'yield' | 'spread' | 'index' | 'price'
export type NewsCat = 'fact' | 'read' | 'both' | 'noise'
export type ReviewStatus = 'held' | 'invalidated' | 'open'

/** 指标表一行。value/change 的单位由 kind 决定(见 lib/format.ts)。 */
export interface Metric {
  key: string
  label: string
  value: number
  change: number
  kind: MetricKind
}

/** 假设层:可证伪命题 + 失效条件。 */
export interface Hypothesis {
  ifThen: string
  invalidation: string
}

/** 影响层:资产观察点 + 方向(非买卖建议)。 */
export interface Impact {
  asset: string
  watch: string
  dir: Dir
}

/** 假设复盘一条。 */
export interface Review {
  ifThen: string
  status: ReviewStatus
  note: string
}

/** 新闻分类一条。cat 为 null 表示未分类(无 LLM provider 时)。link 真实数据有、demo 无。 */
export interface News {
  title: string
  source: string
  cat: NewsCat | null
  assets: string[]
  dir: Dir
  link?: string
}

/** 单个交易日的完整简报(= render_json 的输出)。 */
export interface Brief {
  date: string // YYYY-MM-DD,来自 run_date
  weekday: string // 中文,如「周三」
  issue: number // 刊号:按年代序(最早=1)
  time: string // 常量「07:00 CST」
  tone: Tone
  headline: string
  metrics: Metric[] // 通常 7 行(含广义美元);长度自适应
  facts: string[]
  reads: string[] // 解读层(后端 interpretation)
  hypotheses: Hypothesis[]
  impacts: Impact[]
  reviews: Review[] // 可能为空 → 复盘节隐藏
  news: News[]
}

/** 聚合文件 data/briefs.json 的顶层结构(briefs 按日期倒序,最新在前)。 */
export interface BriefsPayload {
  model: string
  generatedAt: string
  briefs: Brief[]
}

// ── 前端 UI 状态(非数据契约)─────────────────────────────────────────────

export type ThemeMode = 'auto' | 'light' | 'dark'

/** 用户可调项(Tweaks 面板)。 */
export interface Tweaks {
  accent: string | null // null = 用主题默认 --accent
  showSparklines: boolean
  paperTexture: boolean
}
