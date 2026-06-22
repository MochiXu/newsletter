// regime 术语库(单一源):键中文 + 值 token 中文 + 中英解释。
// 数据来源是后端 py/newsletter/regime.py 派生的离散标签(代码受控,非 LLM 自由文本)。
// 解释先用中文展示;en 字段先备好,将来可切英文。

export interface Bilingual {
  zh: string
  en: string
}

/** regime 键 → 中文短名。 */
export const REGIME_LABEL: Record<string, string> = {
  equity_trend: '股票趋势',
  vol_regime: '波动',
  curve: '曲线',
  real_rate: '实际利率',
  inflation_expectations: '通胀预期',
  dollar: '美元',
}

/** regime 键 → 这个维度是什么(用什么算的)。 */
export const REGIME_DESC: Record<string, Bilingual> = {
  equity_trend: { zh: '股票中期趋势:以股指相对 200 日均线判断', en: 'Equity medium-term trend vs the 200-day moving average' },
  vol_regime: { zh: '市场波动率状态:看 VIX 水平 + 相对 20 日均线的方向', en: 'Volatility regime: VIX level plus its move vs the 20-day average' },
  curve: { zh: '收益率曲线形态:2 年期与 10 年期国债的利差', en: 'Yield-curve shape: the 2y vs 10y Treasury spread' },
  real_rate: { zh: '实际利率方向:通胀调整后的 10 年期利率,近 20 日变化', en: 'Real-rate direction: inflation-adjusted 10y yield, 20-day change' },
  inflation_expectations: { zh: '通胀预期方向:10 年期盈亏平衡通胀,近 20 日变化', en: 'Inflation expectations: 10y breakeven inflation, 20-day change' },
  dollar: { zh: '美元强弱:相对 200 日均线,并看广义与窄口径是否背离', en: 'USD strength vs 200-day MA, and broad-vs-narrow divergence' },
}

/** 值 token → 中文短显示(徽章上显示的)。 */
export const TOKEN_CN: Record<string, string> = {
  above_ma200: 'MA200上方',
  below_ma200: 'MA200下方',
  low: '低波',
  mid: '中波',
  high: '高波',
  elevated: '抬升',
  easing: '回落',
  normal: '正常',
  flat: '走平',
  inverted: '倒挂',
  steepening: '陡峭化',
  flattening: '平坦化',
  rising: '上行',
  falling: '下行',
  strong: '强',
  weak: '弱',
  diverging: '分化',
  converging: '收敛',
}

/** 值 token → 一句话解释(中英)。 */
export const TOKEN_DESC: Record<string, Bilingual> = {
  above_ma200: { zh: '价格在 200 日均线上方,中期趋势偏多', en: 'Price above the 200-day MA — medium-term uptrend' },
  below_ma200: { zh: '价格在 200 日均线下方,中期趋势偏空', en: 'Price below the 200-day MA — medium-term downtrend' },
  low: { zh: '波动率处于低档(VIX 偏低,市场平静)', en: 'Low volatility (VIX subdued)' },
  mid: { zh: '波动率中档', en: 'Mid volatility' },
  high: { zh: '波动率高档(VIX 偏高,市场紧张)', en: 'High volatility (VIX elevated, market stress)' },
  elevated: { zh: '波动率较 20 日均值在抬升', en: 'Volatility rising vs its 20-day average' },
  easing: { zh: '波动率较 20 日均值在回落', en: 'Volatility easing vs its 20-day average' },
  normal: { zh: '曲线正常:长端利率高于短端', en: 'Normal curve: long-end yields above short-end' },
  flat: { zh: '曲线走平:长短端利差很小', en: 'Flat curve: very small long-short spread' },
  inverted: { zh: '曲线倒挂:短端高于长端,常被视为衰退前兆', en: 'Inverted curve: short above long — a classic recession signal' },
  steepening: { zh: '曲线变陡:长短端利差在扩大', en: 'Steepening: the long-short spread is widening' },
  flattening: { zh: '曲线变平:长短端利差在收窄', en: 'Flattening: the long-short spread is narrowing' },
  rising: { zh: '较 20 日前上行', en: 'Rising vs 20 days ago' },
  falling: { zh: '较 20 日前下行', en: 'Falling vs 20 days ago' },
  strong: { zh: '美元偏强(高于 200 日均线)', en: 'USD strong (above its 200-day MA)' },
  weak: { zh: '美元偏弱(低于 200 日均线)', en: 'USD weak (below its 200-day MA)' },
  diverging: { zh: '广义美元与窄口径美元走势背离', en: 'Broad and narrow USD measures are diverging' },
  converging: { zh: '广义美元与窄口径美元走势收敛', en: 'Broad and narrow USD measures are converging' },
}

/** regime 原始值(可能含 `/` 复合,如 mid/easing)→ 徽章中文显示。 */
export const translateRegime = (v: string): string =>
  v
    .split('/')
    .map((t) => TOKEN_CN[t] ?? t)
    .join('·')

/** 组合一条 regime 徽章的 hover 文案(中文):维度说明 + 当前各 token 的解释。 */
export function regimeTooltip(key: string, rawValue: string): string {
  const dim = REGIME_DESC[key]?.zh ?? REGIME_LABEL[key] ?? key
  const parts = (rawValue || '')
    .split('/')
    .map((t) => TOKEN_DESC[t]?.zh)
    .filter(Boolean)
  return parts.length ? `${dim}。当前:${parts.join(';')}。` : `${dim}。`
}

// ── 正文术语高亮(Phase 2):事实/解读正文里出现的 regime token + 行话 → hover 解释 ──
// 不改 LLM 输出(保留各模型的专业措辞),只在前端给已知术语加虚下划线 + hover。

const REGIME_KEYS = ['equity_trend', 'vol_regime', 'curve', 'real_rate', 'inflation_expectations', 'dollar']

/** 非 regime 的行话(LLM 自由文本里常见,代码里无离散来源)。 */
export const JARGON: Record<string, string> = {
  'higher-for-longer': '市场预期央行把利率维持在高位更久(降息更晚或更慢),对成长股与黄金估值是逆风',
  熊平: '熊市平坦化:利率整体上行、且短端涨得比长端多,导致收益率曲线变平',
  牛陡: '牛市陡峭化:利率整体下行、且短端跌得比长端多,导致收益率曲线变陡',
  倒挂: '收益率曲线倒挂:短端利率高于长端,常被视为衰退前兆',
}

// token 按长度降序,避免 flat 抢在 flattening 前匹配
const _TOK = Object.keys(TOKEN_DESC).sort((a, b) => b.length - a.length).join('|')
// 裸 token 只收"明确不会误伤中文/英文普通词"的长 token(low/mid/flat 等歧义短词不单独匹配)
const _BARE = ['above_ma200', 'below_ma200', 'steepening', 'flattening', 'inverted', 'diverging', 'converging', 'elevated', 'easing'].join('|')

/** 匹配正文里的术语:key=value / token-slash 复合 / 裸长 token / 行话。 */
export const GLOSSARY_RE = new RegExp(
  `(?:${REGIME_KEYS.join('|')})=(?:${_TOK})(?:\\/(?:${_TOK}))?` +
    `|(?:${_TOK})\\/(?:${_TOK})` +
    `|${_BARE}` +
    `|${Object.keys(JARGON).join('|')}`,
  'g',
)

/** 给匹配到的术语返回中文解释;无则 null。 */
export function glossaryExplain(term: string): string | null {
  const eq = term.indexOf('=')
  if (eq > 0) {
    const dim = REGIME_DESC[term.slice(0, eq)]?.zh
    const vals = term.slice(eq + 1).split('/').map((t) => TOKEN_DESC[t]?.zh).filter(Boolean)
    if (dim && vals.length) return `${dim}。当前:${vals.join(';')}。`
  }
  const toks = term.split('/')
  if (toks.every((t) => TOKEN_DESC[t])) return toks.map((t) => TOKEN_DESC[t].zh).join(';') + '。'
  return JARGON[term] ?? null
}
