// 9 个交易日的 demo 数据(最新在前),从设计稿 frontend/desgin/resource/briefs.js 1:1 移植并加类型。
// 用途:真实管线产出的 data/briefs.json 还很稀疏(才上线几天)时,前端回退到这份 demo,
// 让小票阅读器立刻呈现设计稿的完整效果(见 data/loadBriefs.ts)。真实数据攒够后自动接管。
//
// 注意:demo 沿用设计稿的 6 行指标(无「广义美元」)与刊号 134–142;真实数据为 7 行、刊号按年代序。
// 两者都符合 Brief 契约(指标长度自适应),互不冲突。

import type { Brief, BriefsPayload, Metric, MetricKind } from '../types'

const M = (key: string, label: string, value: number, change: number, kind: MetricKind): Metric => ({
  key,
  label,
  value,
  change,
  kind,
})

// 每日六个跟踪指标(显示顺序)。2s10s 由 10Y-2Y 计算得出。
function metrics(
  t10: number, c10: number, t2: number, c2: number,
  vix: number, cvix: number, dxy: number, cdxy: number,
  gold: number, cgold: number,
): Metric[] {
  const spread = +(t10 - t2).toFixed(2)
  const cspread = +(c10 - c2).toFixed(2)
  return [
    M('us10y', 'US10Y', t10, c10, 'yield'),
    M('us2y', 'US2Y', t2, c2, 'yield'),
    M('2s10s', '2s10s', spread, cspread, 'spread'),
    M('vix', 'VIX', vix, cvix, 'index'),
    M('dxy', 'DXY', dxy, cdxy, 'index'),
    M('gold', 'GOLD', gold, cgold, 'price'),
  ]
}

const BRIEFS: Brief[] = [
  {
    date: '2026-06-16', weekday: '周二', issue: 142, time: '07:00 CST', tone: 'risk-off',
    headline: 'FOMC 鹰派暂停:点阵图上修,10Y 与美元齐升,VIX 跳上 17。',
    metrics: metrics(4.49, 0.12, 4.92, 0.16, 17.2, 3.7, 104.9, 1.1, 2410, -30),
    facts: [
      '联储维持基准利率不变,点阵图中值较 3 月上修,年内降息指引收窄至一次。',
      '10Y 收 4.49%(+12bp),2Y 4.92%(+16bp),2s10s 倒挂走深至 -43bp。',
      'VIX 自 13.5 跳升至 17.2;DXY 升 1.1 至 104.9;黄金回落 30 至 2,410。',
    ],
    reads: [
      '短端涨幅大于长端,市场重新计入「更高更久」的政策路径。',
      '倒挂走深叠加美元走强,属典型鹰派 surprise 反应,而非增长预期改善。',
    ],
    hypotheses: [
      { ifThen: '若下周核心 PCE 不弱,10Y 有望站稳 4.50% 上方、延续推迟降息定价。', invalidation: '10Y 跌破 4.40% 且 2Y 同步走低。' },
      { ifThen: '若 VIX 三日内回落至 15 下方,本次跳升属事件性冲击而非趋势转向。', invalidation: 'VIX 连续两日收于 18 上方。' },
    ],
    impacts: [
      { asset: '美债 UST', watch: '4.50% 关口与 10Y 招标需求', dir: 'up' },
      { asset: '美元 DXY', watch: '105 前高是否被突破', dir: 'up' },
      { asset: '黄金 XAU', watch: '2,400 关口的实际利率敏感度', dir: 'down' },
    ],
    news: [
      { title: 'Fed holds rates, dot plot signals fewer cuts in 2026', source: 'Federal Reserve', cat: 'fact', assets: ['UST', 'DXY'], dir: 'up' },
      { title: 'Powell: policy stays restrictive until inflation path is clear', source: 'CNBC', cat: 'both', assets: ['UST', 'Equities'], dir: 'down' },
      { title: 'Traders slash bets on a September rate cut', source: 'MarketWatch', cat: 'read', assets: ['Rates'], dir: 'up' },
      { title: 'Gold slips as real yields climb post-FOMC', source: 'MarketWatch', cat: 'fact', assets: ['XAU'], dir: 'down' },
    ],
    reviews: [
      { ifThen: '若 FOMC 维持中性措辞,波动率维持低位。', status: 'invalidated', note: '点阵图上修触发 VIX 跳升,假设失效。' },
      { ifThen: '若决议日前 DXY 守住 103.5,美元下行动能减弱。', status: 'held', note: 'DXY 守住并于会后走强,已兑现。' },
    ],
  },
  {
    date: '2026-06-15', weekday: '周一', issue: 141, time: '07:00 CST', tone: 'neutral',
    headline: '决议前波动收敛,两年期窄幅整理,市场屏息等待点阵图。',
    metrics: metrics(4.37, 0.02, 4.76, 0.02, 13.5, -0.3, 103.8, 0.2, 2440, -8),
    facts: [
      '10Y 4.37%(+2bp),2Y 4.76%(+2bp),曲线基本持平于 -39bp。',
      'VIX 续降至 13.5,创近月新低;DXY 微升至 103.8。',
      '黄金小幅回落至 2,440。',
    ],
    reads: ['低波动加窄幅整理,是典型的事件前 de-risking 与仓位收敛。'],
    hypotheses: [
      { ifThen: '若 FOMC 维持中性措辞,波动率维持低位、曲线延续区间震荡。', invalidation: '点阵图上修或 Powell 转鹰,VIX 跳升。' },
      { ifThen: '若决议日前 DXY 守住 103.5,美元下行动能减弱、等待催化。', invalidation: 'DXY 跌破 103.2。' },
    ],
    impacts: [
      { asset: '波动率 VIX', watch: '事件前低波动是否被决议打破', dir: 'watch' },
      { asset: '美债 UST', watch: '点阵图与 SEP 对短端的冲击', dir: 'watch' },
      { asset: '美元 DXY', watch: '103.5 支撑', dir: 'watch' },
    ],
    news: [
      { title: 'Markets in holding pattern ahead of Fed decision', source: 'CNBC', cat: 'read', assets: ['Equities', 'Rates'], dir: 'watch' },
      { title: 'Two-year yield steadies near 4.75% before FOMC', source: 'MarketWatch', cat: 'fact', assets: ['UST'], dir: 'watch' },
      { title: 'Crypto rallies on ETF inflows, decoupling from macro', source: 'CoinDesk', cat: 'noise', assets: ['BTC'], dir: 'up' },
    ],
    reviews: [
      { ifThen: '若降息预期重燃,2s10s 延续陡峭化。', status: 'open', note: '曲线持平待决议,暂未证实或证伪。' },
      { ifThen: '若 DXY 跌破 104,美元转弱确认。', status: 'held', note: 'DXY 收 103.6,已跌破,兑现。' },
    ],
  },
  {
    date: '2026-06-12', weekday: '周五', issue: 140, time: '07:00 CST', tone: 'risk-on',
    headline: 'CPI 余温延续:曲线陡峭化,美元走弱,黄金逼近 2,450。',
    metrics: metrics(4.35, -0.04, 4.74, -0.06, 13.8, -0.5, 103.6, -0.5, 2448, 17),
    facts: [
      '10Y 4.35%(-4bp),2Y 4.74%(-6bp),2s10s 收窄至 -39bp(陡峭化)。',
      'VIX 13.8;DXY 跌 0.5 至 103.6;黄金涨 17 至 2,448。',
    ],
    reads: [
      '短端跌幅大于长端,市场计入更早降息,bull steepening 特征明显。',
      '美元走弱与黄金走强共同确认实际利率下行预期。',
    ],
    hypotheses: [
      { ifThen: '若降息预期持续,2s10s 延续陡峭化、年内有望转正。', invalidation: 'FOMC 点阵图上修使短端反弹。' },
      { ifThen: '若 DXY 跌破 104,美元中期转弱确认。', invalidation: 'DXY 重回 105 上方。' },
    ],
    impacts: [
      { asset: '美债曲线', watch: '2s10s 能否年内转正', dir: 'up' },
      { asset: '美元 DXY', watch: '104 失守后的 103 支撑', dir: 'down' },
      { asset: '黄金 XAU', watch: '2,450 前高', dir: 'up' },
    ],
    news: [
      { title: 'Soft CPI aftermath: September cut odds jump', source: 'CNBC', cat: 'both', assets: ['Rates', 'Equities'], dir: 'up' },
      { title: 'Dollar slides to one-month low', source: 'MarketWatch', cat: 'fact', assets: ['DXY'], dir: 'down' },
      { title: 'Gold extends gains on softer dollar', source: 'MarketWatch', cat: 'fact', assets: ['XAU'], dir: 'up' },
    ],
    reviews: [
      { ifThen: '若 CPI 确认放缓,10Y 回落、风险偏好回升。', status: 'held', note: '10Y 续跌、股指走强,已兑现。' },
      { ifThen: '若通胀超预期,收益率反弹。', status: 'invalidated', note: 'CPI 低于预期,该路径未发生。' },
    ],
  },
  {
    date: '2026-06-11', weekday: '周四', issue: 139, time: '07:00 CST', tone: 'risk-on',
    headline: 'CPI 不及预期:10Y 单日大跌 17bp,VIX 回落,黄金跳涨。',
    metrics: metrics(4.39, -0.17, 4.80, -0.19, 14.3, -2.6, 104.1, -1.2, 2431, 36),
    facts: [
      '5 月核心 CPI 同比低于市场一致预期;10Y 4.39%(-17bp),2Y 4.80%(-19bp)。',
      'VIX 自 16.9 回落至 14.3;DXY 跌 1.2 至 104.1;黄金涨 36 至 2,431。',
    ],
    reads: [
      '通胀降温缓解了「更高更久」的担忧,risk-on 全面展开。',
      '短端跌幅最大,反映降息预期被显著前移。',
    ],
    hypotheses: [
      { ifThen: '若 CPI 确认通胀放缓趋势,10Y 回落且股票风险偏好回升。', invalidation: '次周 PPI/PCE 反弹打消放缓叙事。' },
      { ifThen: '若实际利率下行,黄金延续反弹。', invalidation: '美元重新走强压制金价。' },
    ],
    impacts: [
      { asset: '美债 UST', watch: '4.40% 下方能否企稳', dir: 'down' },
      { asset: '美股', watch: '利率敏感成长股的反弹持续性', dir: 'up' },
      { asset: '黄金 XAU', watch: '实际利率与美元的双重驱动', dir: 'up' },
    ],
    news: [
      { title: 'US core CPI cools more than expected in May', source: 'Bureau of Labor Statistics', cat: 'fact', assets: ['Rates', 'Equities'], dir: 'up' },
      { title: 'Treasury yields tumble as cut bets revive', source: 'CNBC', cat: 'both', assets: ['UST'], dir: 'down' },
      { title: 'Wall Street rallies on inflation relief', source: 'MarketWatch', cat: 'both', assets: ['Equities'], dir: 'up' },
      { title: "Analyst: one print doesn't make a trend", source: 'CNBC', cat: 'read', assets: ['Rates'], dir: 'watch' },
    ],
    reviews: [
      { ifThen: '若 CPI 前避险升温,VIX 维持偏高。', status: 'invalidated', note: 'CPI 利好,VIX 大幅回落。' },
      { ifThen: '若黄金避险买盘延续,站稳 2,390。', status: 'held', note: '黄金跳涨至 2,431,已兑现。' },
    ],
  },
  {
    date: '2026-06-10', weekday: '周三', issue: 138, time: '07:00 CST', tone: 'risk-off',
    headline: 'CPI 前夕避险升温:VIX 抬升至 17 附近,黄金获买盘。',
    metrics: metrics(4.56, -0.02, 4.99, -0.01, 16.9, 1.8, 105.3, 0.3, 2395, 33),
    facts: [
      '10Y 4.56%(-2bp),2Y 4.99%(-1bp),曲线持平于 -43bp。',
      'VIX 自 15.1 升至 16.9;DXY 105.3(+0.3);黄金涨 33 至 2,395。',
    ],
    reads: ['数据空窗叠加关键 CPI 临近,资金转向防御,VIX 与黄金同向上行。'],
    hypotheses: [
      { ifThen: '若 CPI 前避险情绪延续,VIX 维持 16 上方。', invalidation: 'CPI 利好使波动率迅速回落。' },
      { ifThen: '若黄金避险买盘延续,站稳 2,390 上方。', invalidation: '美元走强压制金价回落 2,360。' },
    ],
    impacts: [
      { asset: '波动率 VIX', watch: 'CPI 事件溢价', dir: 'up' },
      { asset: '黄金 XAU', watch: '避险与实际利率拉锯', dir: 'up' },
      { asset: '美元 DXY', watch: '105 上方的避险买盘', dir: 'up' },
    ],
    news: [
      { title: 'Investors hedge ahead of key inflation report', source: 'CNBC', cat: 'read', assets: ['VIX', 'Equities'], dir: 'up' },
      { title: 'Gold firms as haven demand builds', source: 'MarketWatch', cat: 'fact', assets: ['XAU'], dir: 'up' },
      { title: 'Oil steadies after a volatile week', source: 'MarketWatch', cat: 'noise', assets: ['Oil'], dir: 'watch' },
    ],
    reviews: [
      { ifThen: '若油价扰动推升通胀担忧,10Y 续升。', status: 'held', note: '10Y 维持高位,基本兑现。' },
      { ifThen: '若风险偏好稳定,VIX 维持 15 下方。', status: 'invalidated', note: '避险升温,VIX 升破 16。' },
    ],
  },
  {
    date: '2026-06-09', weekday: '周二', issue: 137, time: '07:00 CST', tone: 'risk-off',
    headline: '油价扰动推升通胀担忧,10Y 续升站上 4.58%。',
    metrics: metrics(4.58, 0.06, 5.00, 0.05, 15.1, 0.5, 105.0, 0.2, 2362, -13),
    facts: [
      '10Y 4.58%(+6bp),2Y 5.00%(+5bp),2s10s -42bp。',
      'VIX 15.1(+0.5);DXY 105.0(+0.2);黄金跌 13 至 2,362。',
    ],
    reads: ['能源驱动的通胀预期升温压制长端债券,黄金受名义利率上行拖累。'],
    hypotheses: [
      { ifThen: '若油价扰动推升通胀担忧,10Y 续升、逼近 4.60%。', invalidation: '油价回落且通胀预期回稳。' },
      { ifThen: '若风险偏好维持稳定,VIX 维持 15 下方。', invalidation: '出现外生冲击推升避险。' },
    ],
    impacts: [
      { asset: '美债 UST', watch: '4.60% 阻力', dir: 'up' },
      { asset: '黄金 XAU', watch: '名义利率上行压力', dir: 'down' },
      { asset: '原油', watch: '地缘扰动的持续性', dir: 'watch' },
    ],
    news: [
      { title: 'Oil jumps on supply concerns', source: 'MarketWatch', cat: 'fact', assets: ['Oil'], dir: 'up' },
      { title: 'Yields climb as inflation worries resurface', source: 'CNBC', cat: 'both', assets: ['UST'], dir: 'up' },
      { title: 'Gold dips on stronger dollar, higher yields', source: 'MarketWatch', cat: 'fact', assets: ['XAU'], dir: 'down' },
    ],
    reviews: [
      { ifThen: '若周末无重大冲击,VIX 延续回落。', status: 'held', note: 'VIX 回落区间,兑现。' },
      { ifThen: '若美元走强,黄金承压。', status: 'held', note: '黄金续跌,兑现。' },
    ],
  },
  {
    date: '2026-06-08', weekday: '周一', issue: 136, time: '07:00 CST', tone: 'neutral',
    headline: '非农余波消化:VIX 回落,曲线企稳,黄金延续承压。',
    metrics: metrics(4.52, -0.03, 4.95, -0.03, 14.6, -1.2, 104.8, -0.3, 2375, -13),
    facts: [
      '10Y 4.52%(-3bp),2Y 4.95%(-3bp),2s10s -43bp。',
      'VIX 自 15.8 回落至 14.6;DXY 104.8(-0.3);黄金跌 13 至 2,375。',
    ],
    reads: ['强非农冲击被市场逐步消化,波动率回吐,风险偏好温和修复。'],
    hypotheses: [
      { ifThen: '若周末无重大冲击,VIX 延续回落、风险偏好修复。', invalidation: '出现地缘或政策意外。' },
      { ifThen: '若美元维持强势,黄金延续承压。', invalidation: '美元转弱、实际利率回落。' },
    ],
    impacts: [
      { asset: '波动率 VIX', watch: '14 下方的低波动区间', dir: 'down' },
      { asset: '黄金 XAU', watch: '2,360 支撑', dir: 'down' },
      { asset: '美股', watch: '风险偏好修复的持续性', dir: 'up' },
    ],
    news: [
      { title: 'Volatility eases as markets digest payrolls', source: 'CNBC', cat: 'read', assets: ['VIX', 'Equities'], dir: 'down' },
      { title: "Dollar steadies after Friday's jobs-driven spike", source: 'MarketWatch', cat: 'fact', assets: ['DXY'], dir: 'watch' },
      { title: 'Gold under pressure near a one-week low', source: 'MarketWatch', cat: 'fact', assets: ['XAU'], dir: 'down' },
    ],
    reviews: [
      { ifThen: '若非农强劲,降息预期推后、收益率上行。', status: 'held', note: '10Y/2Y 跳升,完全兑现。' },
      { ifThen: '若收益率上行,黄金回落。', status: 'held', note: '黄金回落至 2,388,兑现。' },
    ],
  },
  {
    date: '2026-06-05', weekday: '周五', issue: 135, time: '07:00 CST', tone: 'risk-off',
    headline: '非农强于预期:10Y 跳升 13bp,降息预期再被推后。',
    metrics: metrics(4.55, 0.13, 4.98, 0.12, 15.8, 1.6, 105.1, 0.9, 2388, -24),
    facts: [
      '5 月非农新增就业高于市场预期,失业率持平。',
      '10Y 4.55%(+13bp),2Y 4.98%(+12bp),2s10s -43bp;VIX 15.8(+1.6)。',
      'DXY 升 0.9 至 105.1;黄金跌 24 至 2,388。',
    ],
    reads: [
      '劳动力市场韧性削弱了近期降息的理由,短端与长端同步上行。',
      '美元走强叠加黄金走弱,印证收益率主导的定价。',
    ],
    hypotheses: [
      { ifThen: '若非农延续强劲,降息预期推后、收益率维持高位。', invalidation: '后续数据显示劳动力市场转弱。' },
      { ifThen: '若收益率上行,黄金短期回落。', invalidation: '避险买盘盖过利率压力。' },
    ],
    impacts: [
      { asset: '美债 UST', watch: '4.55% 上方的持续性', dir: 'up' },
      { asset: '美元 DXY', watch: '105 关口', dir: 'up' },
      { asset: '黄金 XAU', watch: '2,380 支撑', dir: 'down' },
    ],
    news: [
      { title: 'US payrolls beat expectations in May', source: 'Bureau of Labor Statistics', cat: 'fact', assets: ['Rates', 'DXY'], dir: 'up' },
      { title: 'Treasury yields spike as cut bets get pushed out', source: 'CNBC', cat: 'both', assets: ['UST'], dir: 'up' },
      { title: 'Dollar strengthens broadly on jobs data', source: 'MarketWatch', cat: 'fact', assets: ['DXY'], dir: 'up' },
    ],
    reviews: [
      { ifThen: '若 NFP 前市场观望,曲线维持区间。', status: 'invalidated', note: '非农大超预期打破区间。' },
    ],
  },
  {
    date: '2026-06-04', weekday: '周四', issue: 134, time: '07:00 CST', tone: 'neutral',
    headline: '数据空窗,曲线窄幅:市场静待周五非农指引。',
    metrics: metrics(4.42, 0.01, 4.86, -0.02, 14.2, -0.4, 104.2, -0.1, 2412, 5),
    facts: [
      '10Y 4.42%(+1bp),2Y 4.86%(-2bp),2s10s 倒挂 -44bp。',
      'VIX 14.2(-0.4);DXY 104.2;黄金 2,412(+5)。',
    ],
    reads: ['缺乏催化下市场维持区间,倒挂深度变化不大,定价等待劳动力数据。'],
    hypotheses: [
      { ifThen: '若周五非农符合预期,曲线维持区间震荡。', invalidation: '非农显著偏离预期触发重定价。' },
      { ifThen: '若波动率维持低位,风险资产温和走强。', invalidation: '事件冲击推升 VIX。' },
    ],
    impacts: [
      { asset: '美债 UST', watch: '非农前的区间边界', dir: 'watch' },
      { asset: '波动率 VIX', watch: '事件前的低波动', dir: 'watch' },
      { asset: '黄金 XAU', watch: '2,400 整数关口', dir: 'watch' },
    ],
    news: [
      { title: "Markets quiet ahead of Friday's jobs report", source: 'CNBC', cat: 'read', assets: ['Equities', 'Rates'], dir: 'watch' },
      { title: 'Weekly jobless claims little changed', source: 'Department of Labor', cat: 'fact', assets: ['Rates'], dir: 'watch' },
      { title: 'Gold holds near $2,400', source: 'MarketWatch', cat: 'fact', assets: ['XAU'], dir: 'watch' },
    ],
    reviews: [],
  },
]

export const DEMO_PAYLOAD: BriefsPayload = {
  model: 'DeepSeek',
  generatedAt: '2026-06-16',
  briefs: BRIEFS,
}
