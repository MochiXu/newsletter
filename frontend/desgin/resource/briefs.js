// Mock data for the AI macro newsletter — 9 trading days (newest first).
// Shape mirrors the project's intelligence-plane four-layer brief + news
// classification + hypothesis-tracking review. No backend required.

export const MODEL = "DeepSeek";

const M = (key, label, value, change, kind) => ({ key, label, value, change, kind });

// Each day's six tracked series, in display order.
function metrics(t10, c10, t2, c2, vix, cvix, dxy, cdxy, gold, cgold) {
  const spread = +(t10 - t2).toFixed(2);
  const cspread = +(c10 - c2).toFixed(2);
  return [
    M("us10y", "US10Y", t10, c10, "yield"),
    M("us2y", "US2Y", t2, c2, "yield"),
    M("2s10s", "2s10s", spread, cspread, "spread"),
    M("vix", "VIX", vix, cvix, "index"),
    M("dxy", "DXY", dxy, cdxy, "index"),
    M("gold", "GOLD", gold, cgold, "price"),
  ];
}

const RECENT = [
  {
    date: "2026-06-16", weekday: "周二", issue: 142, time: "07:00 CST", tone: "risk-off",
    headline: "FOMC 鹰派暂停:点阵图上修,10Y 与美元齐升,VIX 跳上 17。",
    metrics: metrics(4.49, 0.12, 4.92, 0.16, 17.2, 3.7, 104.9, 1.1, 2410, -30),
    q: { nasdaq: [17680, -180], btc: [64200, -1500] },
    facts: [
      "联储维持基准利率不变,点阵图中值较 3 月上修,年内降息指引收窄至一次。",
      "10Y 收 4.49%(+12bp),2Y 4.92%(+16bp),2s10s 倒挂走深至 -43bp。",
      "VIX 自 13.5 跳升至 17.2;DXY 升 1.1 至 104.9;黄金回落 30 至 2,410。",
    ],
    reads: [
      "短端涨幅大于长端,市场重新计入「更高更久」的政策路径。",
      "倒挂走深叠加美元走强,属典型鹰派 surprise 反应,而非增长预期改善。",
    ],
    hypotheses: [
      { ifThen: "若下周核心 PCE 不弱,10Y 有望站稳 4.50% 上方、延续推迟降息定价。", invalidation: "10Y 跌破 4.40% 且 2Y 同步走低。" },
      { ifThen: "若 VIX 三日内回落至 15 下方,本次跳升属事件性冲击而非趋势转向。", invalidation: "VIX 连续两日收于 18 上方。" },
    ],
    impacts: [
      { asset: "美债 UST", watch: "4.50% 关口与 10Y 招标需求", dir: "up" },
      { asset: "美元 DXY", watch: "105 前高是否被突破", dir: "up" },
      { asset: "黄金 XAU", watch: "2,400 关口的实际利率敏感度", dir: "down" },
    ],
    news: [
      { title: "Fed holds rates, dot plot signals fewer cuts in 2026", source: "Federal Reserve", cat: "fact", assets: ["UST", "DXY"], dir: "up" },
      { title: "Powell: policy stays restrictive until inflation path is clear", source: "CNBC", cat: "both", assets: ["UST", "Equities"], dir: "down" },
      { title: "Traders slash bets on a September rate cut", source: "MarketWatch", cat: "read", assets: ["Rates"], dir: "up" },
      { title: "Gold slips as real yields climb post-FOMC", source: "MarketWatch", cat: "fact", assets: ["XAU"], dir: "down" },
    ],
    reviews: [
      { ifThen: "若 FOMC 维持中性措辞,波动率维持低位。", status: "invalidated", note: "点阵图上修触发 VIX 跳升,假设失效。" },
      { ifThen: "若决议日前 DXY 守住 103.5,美元下行动能减弱。", status: "held", note: "DXY 守住并于会后走强,已兑现。" },
    ],
  },
  {
    date: "2026-06-15", weekday: "周一", issue: 141, time: "07:00 CST", tone: "neutral",
    headline: "决议前波动收敛,两年期窄幅整理,市场屏息等待点阵图。",
    metrics: metrics(4.37, 0.02, 4.76, 0.02, 13.5, -0.3, 103.8, 0.2, 2440, -8),
    q: { nasdaq: [17860, 20], btc: [65700, 300] },
    facts: [
      "10Y 4.37%(+2bp),2Y 4.76%(+2bp),曲线基本持平于 -39bp。",
      "VIX 续降至 13.5,创近月新低;DXY 微升至 103.8。",
      "黄金小幅回落至 2,440。",
    ],
    reads: [
      "低波动加窄幅整理,是典型的事件前 de-risking 与仓位收敛。",
    ],
    hypotheses: [
      { ifThen: "若 FOMC 维持中性措辞,波动率维持低位、曲线延续区间震荡。", invalidation: "点阵图上修或 Powell 转鹰,VIX 跳升。" },
      { ifThen: "若决议日前 DXY 守住 103.5,美元下行动能减弱、等待催化。", invalidation: "DXY 跌破 103.2。" },
    ],
    impacts: [
      { asset: "波动率 VIX", watch: "事件前低波动是否被决议打破", dir: "watch" },
      { asset: "美债 UST", watch: "点阵图与 SEP 对短端的冲击", dir: "watch" },
      { asset: "美元 DXY", watch: "103.5 支撑", dir: "watch" },
    ],
    news: [
      { title: "Markets in holding pattern ahead of Fed decision", source: "CNBC", cat: "read", assets: ["Equities", "Rates"], dir: "watch" },
      { title: "Two-year yield steadies near 4.75% before FOMC", source: "MarketWatch", cat: "fact", assets: ["UST"], dir: "watch" },
      { title: "Crypto rallies on ETF inflows, decoupling from macro", source: "CoinDesk", cat: "noise", assets: ["BTC"], dir: "up" },
    ],
    reviews: [
      { ifThen: "若降息预期重燃,2s10s 延续陡峭化。", status: "open", note: "曲线持平待决议,暂未证实或证伪。" },
      { ifThen: "若 DXY 跌破 104,美元转弱确认。", status: "held", note: "DXY 收 103.6,已跌破,兑现。" },
    ],
  },
  {
    date: "2026-06-12", weekday: "周五", issue: 140, time: "07:00 CST", tone: "risk-on",
    headline: "CPI 余温延续:曲线陡峭化,美元走弱,黄金逼近 2,450。",
    metrics: metrics(4.35, -0.04, 4.74, -0.06, 13.8, -0.5, 103.6, -0.5, 2448, 17),
    q: { nasdaq: [17840, 150], btc: [65400, 900] },
    facts: [
      "10Y 4.35%(-4bp),2Y 4.74%(-6bp),2s10s 收窄至 -39bp(陡峭化)。",
      "VIX 13.8;DXY 跌 0.5 至 103.6;黄金涨 17 至 2,448。",
    ],
    reads: [
      "短端跌幅大于长端,市场计入更早降息,bull steepening 特征明显。",
      "美元走弱与黄金走强共同确认实际利率下行预期。",
    ],
    hypotheses: [
      { ifThen: "若降息预期持续,2s10s 延续陡峭化、年内有望转正。", invalidation: "FOMC 点阵图上修使短端反弹。" },
      { ifThen: "若 DXY 跌破 104,美元中期转弱确认。", invalidation: "DXY 重回 105 上方。" },
    ],
    impacts: [
      { asset: "美债曲线", watch: "2s10s 能否年内转正", dir: "up" },
      { asset: "美元 DXY", watch: "104 失守后的 103 支撑", dir: "down" },
      { asset: "黄金 XAU", watch: "2,450 前高", dir: "up" },
    ],
    news: [
      { title: "Soft CPI aftermath: September cut odds jump", source: "CNBC", cat: "both", assets: ["Rates", "Equities"], dir: "up" },
      { title: "Dollar slides to one-month low", source: "MarketWatch", cat: "fact", assets: ["DXY"], dir: "down" },
      { title: "Gold extends gains on softer dollar", source: "MarketWatch", cat: "fact", assets: ["XAU"], dir: "up" },
    ],
    reviews: [
      { ifThen: "若 CPI 确认放缓,10Y 回落、风险偏好回升。", status: "held", note: "10Y 续跌、股指走强,已兑现。" },
      { ifThen: "若通胀超预期,收益率反弹。", status: "invalidated", note: "CPI 低于预期,该路径未发生。" },
    ],
  },
  {
    date: "2026-06-11", weekday: "周四", issue: 139, time: "07:00 CST", tone: "risk-on",
    headline: "CPI 不及预期:10Y 单日大跌 17bp,VIX 回落,黄金跳涨。",
    metrics: metrics(4.39, -0.17, 4.80, -0.19, 14.3, -2.6, 104.1, -1.2, 2431, 36),
    q: { nasdaq: [17690, 320], btc: [64500, 1800] },
    facts: [
      "5 月核心 CPI 同比低于市场一致预期;10Y 4.39%(-17bp),2Y 4.80%(-19bp)。",
      "VIX 自 16.9 回落至 14.3;DXY 跌 1.2 至 104.1;黄金涨 36 至 2,431。",
    ],
    reads: [
      "通胀降温缓解了「更高更久」的担忧,risk-on 全面展开。",
      "短端跌幅最大,反映降息预期被显著前移。",
    ],
    hypotheses: [
      { ifThen: "若 CPI 确认通胀放缓趋势,10Y 回落且股票风险偏好回升。", invalidation: "次周 PPI/PCE 反弹打消放缓叙事。" },
      { ifThen: "若实际利率下行,黄金延续反弹。", invalidation: "美元重新走强压制金价。" },
    ],
    impacts: [
      { asset: "美债 UST", watch: "4.40% 下方能否企稳", dir: "down" },
      { asset: "美股", watch: "利率敏感成长股的反弹持续性", dir: "up" },
      { asset: "黄金 XAU", watch: "实际利率与美元的双重驱动", dir: "up" },
    ],
    news: [
      { title: "US core CPI cools more than expected in May", source: "Bureau of Labor Statistics", cat: "fact", assets: ["Rates", "Equities"], dir: "up" },
      { title: "Treasury yields tumble as cut bets revive", source: "CNBC", cat: "both", assets: ["UST"], dir: "down" },
      { title: "Wall Street rallies on inflation relief", source: "MarketWatch", cat: "both", assets: ["Equities"], dir: "up" },
      { title: "Analyst: one print doesn't make a trend", source: "CNBC", cat: "read", assets: ["Rates"], dir: "watch" },
    ],
    reviews: [
      { ifThen: "若 CPI 前避险升温,VIX 维持偏高。", status: "invalidated", note: "CPI 利好,VIX 大幅回落。" },
      { ifThen: "若黄金避险买盘延续,站稳 2,390。", status: "held", note: "黄金跳涨至 2,431,已兑现。" },
    ],
  },
  {
    date: "2026-06-10", weekday: "周三", issue: 138, time: "07:00 CST", tone: "risk-off",
    headline: "CPI 前夕避险升温:VIX 抬升至 17 附近,黄金获买盘。",
    metrics: metrics(4.56, -0.02, 4.99, -0.01, 16.9, 1.8, 105.3, 0.3, 2395, 33),
    q: { nasdaq: [17370, -120], btc: [62700, -900] },
    facts: [
      "10Y 4.56%(-2bp),2Y 4.99%(-1bp),曲线持平于 -43bp。",
      "VIX 自 15.1 升至 16.9;DXY 105.3(+0.3);黄金涨 33 至 2,395。",
    ],
    reads: [
      "数据空窗叠加关键 CPI 临近,资金转向防御,VIX 与黄金同向上行。",
    ],
    hypotheses: [
      { ifThen: "若 CPI 前避险情绪延续,VIX 维持 16 上方。", invalidation: "CPI 利好使波动率迅速回落。" },
      { ifThen: "若黄金避险买盘延续,站稳 2,390 上方。", invalidation: "美元走强压制金价回落 2,360。" },
    ],
    impacts: [
      { asset: "波动率 VIX", watch: "CPI 事件溢价", dir: "up" },
      { asset: "黄金 XAU", watch: "避险与实际利率拉锯", dir: "up" },
      { asset: "美元 DXY", watch: "105 上方的避险买盘", dir: "up" },
    ],
    news: [
      { title: "Investors hedge ahead of key inflation report", source: "CNBC", cat: "read", assets: ["VIX", "Equities"], dir: "up" },
      { title: "Gold firms as haven demand builds", source: "MarketWatch", cat: "fact", assets: ["XAU"], dir: "up" },
      { title: "Oil steadies after a volatile week", source: "MarketWatch", cat: "noise", assets: ["Oil"], dir: "watch" },
    ],
    reviews: [
      { ifThen: "若油价扰动推升通胀担忧,10Y 续升。", status: "held", note: "10Y 维持高位,基本兑现。" },
      { ifThen: "若风险偏好稳定,VIX 维持 15 下方。", status: "invalidated", note: "避险升温,VIX 升破 16。" },
    ],
  },
  {
    date: "2026-06-09", weekday: "周二", issue: 137, time: "07:00 CST", tone: "risk-off",
    headline: "油价扰动推升通胀担忧,10Y 续升站上 4.58%。",
    metrics: metrics(4.58, 0.06, 5.00, 0.05, 15.1, 0.5, 105.0, 0.2, 2362, -13),
    q: { nasdaq: [17490, -90], btc: [63600, -700] },
    facts: [
      "10Y 4.58%(+6bp),2Y 5.00%(+5bp),2s10s -42bp。",
      "VIX 15.1(+0.5);DXY 105.0(+0.2);黄金跌 13 至 2,362。",
    ],
    reads: [
      "能源驱动的通胀预期升温压制长端债券,黄金受名义利率上行拖累。",
    ],
    hypotheses: [
      { ifThen: "若油价扰动推升通胀担忧,10Y 续升、逼近 4.60%。", invalidation: "油价回落且通胀预期回稳。" },
      { ifThen: "若风险偏好维持稳定,VIX 维持 15 下方。", invalidation: "出现外生冲击推升避险。" },
    ],
    impacts: [
      { asset: "美债 UST", watch: "4.60% 阻力", dir: "up" },
      { asset: "黄金 XAU", watch: "名义利率上行压力", dir: "down" },
      { asset: "原油", watch: "地缘扰动的持续性", dir: "watch" },
    ],
    news: [
      { title: "Oil jumps on supply concerns", source: "MarketWatch", cat: "fact", assets: ["Oil"], dir: "up" },
      { title: "Yields climb as inflation worries resurface", source: "CNBC", cat: "both", assets: ["UST"], dir: "up" },
      { title: "Gold dips on stronger dollar, higher yields", source: "MarketWatch", cat: "fact", assets: ["XAU"], dir: "down" },
    ],
    reviews: [
      { ifThen: "若周末无重大冲击,VIX 延续回落。", status: "held", note: "VIX 回落区间,兑现。" },
      { ifThen: "若美元走强,黄金承压。", status: "held", note: "黄金续跌,兑现。" },
    ],
  },
  {
    date: "2026-06-08", weekday: "周一", issue: 136, time: "07:00 CST", tone: "neutral",
    headline: "非农余波消化:VIX 回落,曲线企稳,黄金延续承压。",
    metrics: metrics(4.52, -0.03, 4.95, -0.03, 14.6, -1.2, 104.8, -0.3, 2375, -13),
    q: { nasdaq: [17580, 60], btc: [64300, 200] },
    facts: [
      "10Y 4.52%(-3bp),2Y 4.95%(-3bp),2s10s -43bp。",
      "VIX 自 15.8 回落至 14.6;DXY 104.8(-0.3);黄金跌 13 至 2,375。",
    ],
    reads: [
      "强非农冲击被市场逐步消化,波动率回吐,风险偏好温和修复。",
    ],
    hypotheses: [
      { ifThen: "若周末无重大冲击,VIX 延续回落、风险偏好修复。", invalidation: "出现地缘或政策意外。" },
      { ifThen: "若美元维持强势,黄金延续承压。", invalidation: "美元转弱、实际利率回落。" },
    ],
    impacts: [
      { asset: "波动率 VIX", watch: "14 下方的低波动区间", dir: "down" },
      { asset: "黄金 XAU", watch: "2,360 支撑", dir: "down" },
      { asset: "美股", watch: "风险偏好修复的持续性", dir: "up" },
    ],
    news: [
      { title: "Volatility eases as markets digest payrolls", source: "CNBC", cat: "read", assets: ["VIX", "Equities"], dir: "down" },
      { title: "Dollar steadies after Friday's jobs-driven spike", source: "MarketWatch", cat: "fact", assets: ["DXY"], dir: "watch" },
      { title: "Gold under pressure near a one-week low", source: "MarketWatch", cat: "fact", assets: ["XAU"], dir: "down" },
    ],
    reviews: [
      { ifThen: "若非农强劲,降息预期推后、收益率上行。", status: "held", note: "10Y/2Y 跳升,完全兑现。" },
      { ifThen: "若收益率上行,黄金回落。", status: "held", note: "黄金回落至 2,388,兑现。" },
    ],
  },
  {
    date: "2026-06-05", weekday: "周五", issue: 135, time: "07:00 CST", tone: "risk-off",
    headline: "非农强于预期:10Y 跳升 13bp,降息预期再被推后。",
    metrics: metrics(4.55, 0.13, 4.98, 0.12, 15.8, 1.6, 105.1, 0.9, 2388, -24),
    q: { nasdaq: [17520, -210], btc: [64100, -1900] },
    facts: [
      "5 月非农新增就业高于市场预期,失业率持平。",
      "10Y 4.55%(+13bp),2Y 4.98%(+12bp),2s10s -43bp;VIX 15.8(+1.6)。",
      "DXY 升 0.9 至 105.1;黄金跌 24 至 2,388。",
    ],
    reads: [
      "劳动力市场韧性削弱了近期降息的理由,短端与长端同步上行。",
      "美元走强叠加黄金走弱,印证收益率主导的定价。",
    ],
    hypotheses: [
      { ifThen: "若非农延续强劲,降息预期推后、收益率维持高位。", invalidation: "后续数据显示劳动力市场转弱。" },
      { ifThen: "若收益率上行,黄金短期回落。", invalidation: "避险买盘盖过利率压力。" },
    ],
    impacts: [
      { asset: "美债 UST", watch: "4.55% 上方的持续性", dir: "up" },
      { asset: "美元 DXY", watch: "105 关口", dir: "up" },
      { asset: "黄金 XAU", watch: "2,380 支撑", dir: "down" },
    ],
    news: [
      { title: "US payrolls beat expectations in May", source: "Bureau of Labor Statistics", cat: "fact", assets: ["Rates", "DXY"], dir: "up" },
      { title: "Treasury yields spike as cut bets get pushed out", source: "CNBC", cat: "both", assets: ["UST"], dir: "up" },
      { title: "Dollar strengthens broadly on jobs data", source: "MarketWatch", cat: "fact", assets: ["DXY"], dir: "up" },
    ],
    reviews: [
      { ifThen: "若 NFP 前市场观望,曲线维持区间。", status: "invalidated", note: "非农大超预期打破区间。" },
    ],
  },
  {
    date: "2026-06-04", weekday: "周四", issue: 134, time: "07:00 CST", tone: "neutral",
    headline: "数据空窗,曲线窄幅:市场静待周五非农指引。",
    metrics: metrics(4.42, 0.01, 4.86, -0.02, 14.2, -0.4, 104.2, -0.1, 2412, 5),
    q: { nasdaq: [17730, 40], btc: [66000, 150] },
    facts: [
      "10Y 4.42%(+1bp),2Y 4.86%(-2bp),2s10s 倒挂 -44bp。",
      "VIX 14.2(-0.4);DXY 104.2;黄金 2,412(+5)。",
    ],
    reads: [
      "缺乏催化下市场维持区间,倒挂深度变化不大,定价等待劳动力数据。",
    ],
    hypotheses: [
      { ifThen: "若周五非农符合预期,曲线维持区间震荡。", invalidation: "非农显著偏离预期触发重定价。" },
      { ifThen: "若波动率维持低位,风险资产温和走强。", invalidation: "事件冲击推升 VIX。" },
    ],
    impacts: [
      { asset: "美债 UST", watch: "非农前的区间边界", dir: "watch" },
      { asset: "波动率 VIX", watch: "事件前的低波动", dir: "watch" },
      { asset: "黄金 XAU", watch: "2,400 整数关口", dir: "watch" },
    ],
    news: [
      { title: "Markets quiet ahead of Friday's jobs report", source: "CNBC", cat: "read", assets: ["Equities", "Rates"], dir: "watch" },
      { title: "Weekly jobless claims little changed", source: "Department of Labor", cat: "fact", assets: ["Rates"], dir: "watch" },
      { title: "Gold holds near $2,400", source: "MarketWatch", cat: "fact", assets: ["XAU"], dir: "watch" },
    ],
    reviews: [],
  },
];

// ---- Deterministic generator for older trading days (templated mock) ----
// Extends the hand-authored RECENT array backward so the timeline scrolls and
// the heatmap fills. Replace wholesale once the Python pipeline emits real data.
function rng(seed) {
  let h = 2166136261 >>> 0;
  for (let i = 0; i < seed.length; i++) { h ^= seed.charCodeAt(i); h = Math.imul(h, 16777619) >>> 0; }
  let s = h;
  return () => { s = (s + 0x6D2B79F5) >>> 0; let t = s; t = Math.imul(t ^ (t >>> 15), t | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
}
const WD = ["周日", "周一", "周二", "周三", "周四", "周五", "周六"];
const p2 = (n) => (n < 10 ? "0" + n : "" + n);

function genOlder(startISO, issueStart, count) {
  const out = [];
  const r = rng("older-" + startISO);
  const d = new Date(startISO + "T00:00:00");
  let issue = issueStart;
  // running levels (will drift)
  let t10 = 4.42, t2 = 4.86, vix = 14.5, dxy = 104.2, gold = 2412, nasdaq = 17730, btc = 66000;
  while (out.length < count) {
    d.setDate(d.getDate() - 1);
    const wd = d.getDay();
    if (wd === 0 || wd === 6) continue;
    const iso = d.getFullYear() + "-" + p2(d.getMonth() + 1) + "-" + p2(d.getDate());
    // daily changes
    const c10 = +(((r() - 0.5) * 0.18)).toFixed(2);
    const c2 = +(((r() - 0.5) * 0.2)).toFixed(2);
    const cvix = +(((r() - 0.45) * 2.4)).toFixed(1);
    const cdxy = +(((r() - 0.5) * 0.9)).toFixed(1);
    const cgold = Math.round((r() - 0.5) * 46);
    const cnq = Math.round((r() - 0.48) * 240);
    const cbt = Math.round((r() - 0.48) * 1700);
    t10 = +(t10 - c10).toFixed(2); t2 = +(t2 - c2).toFixed(2);
    vix = +Math.max(10.5, vix - cvix).toFixed(1); dxy = +(dxy - cdxy).toFixed(1);
    gold -= cgold; nasdaq -= cnq; btc -= cbt;
    const riskScore = (c10 > 0 ? 1 : -1) + (cvix > 0 ? 1 : -1) + (cnq < 0 ? 1 : -1);
    const tone = riskScore >= 2 ? "risk-off" : riskScore <= -2 ? "risk-on" : "neutral";
    const upDn = (c) => (c > 0 ? "up" : c < 0 ? "down" : "watch");
    const dir10 = upDn(c10);
    const themes = [
      "数据空窗,曲线窄幅整理,资金等待下一个宏观催化。",
      "收益率温和波动,美元区间运行,风险偏好中性。",
      "通胀预期反复,长短端分化,黄金跟随实际利率。",
      "避险情绪小幅升温,VIX 抬升,美元获得支撑。",
      "降息定价回摆,曲线小幅陡峭,成长股领涨。",
    ];
    const theme = themes[Math.floor(r() * themes.length)];
    const sign = (x, suf) => (x > 0 ? "+" : "") + x + (suf || "");
    out.push({
      date: iso, weekday: WD[wd], issue: issue--, time: "07:00 CST", tone,
      headline: theme,
      metrics: metrics(t10, c10, t2, c2, vix, cvix, dxy, cdxy, gold, cgold),
      q: { nasdaq: [nasdaq, cnq], btc: [btc, cbt] },
      facts: [
        "10Y " + t10.toFixed(2) + "%(" + sign(c10 * 100 | 0, "bp") + "),2Y " + t2.toFixed(2) + "%(" + sign(c2 * 100 | 0, "bp") + "),2s10s " + ((t10 - t2) * 100 | 0) + "bp。",
        "VIX " + vix.toFixed(1) + "(" + sign(cvix) + ");DXY " + dxy.toFixed(1) + "(" + sign(cdxy) + ");黄金 " + gold.toLocaleString("en-US") + "(" + sign(cgold) + ")。",
        "NASDAQ " + nasdaq.toLocaleString("en-US") + "(" + sign(cnq) + ");BTC " + btc.toLocaleString("en-US") + "(" + sign(cbt) + ")。",
      ],
      reads: [
        tone === "risk-off" ? "短端相对坚挺,市场计入「更高更久」的政策路径。" : tone === "risk-on" ? "短端跌幅领先,降息预期被前移,风险偏好回升。" : "缺乏催化下区间运行,曲线形态变化有限。",
      ],
      hypotheses: [
        { ifThen: "若后续数据延续当前方向,10Y 有望" + (c10 > 0 ? "站稳上沿" : "测试下沿") + "。", invalidation: "出现反向的通胀或就业意外。" },
        { ifThen: "若波动率维持当前区间,风险资产延续" + (tone === "risk-on" ? "修复" : "震荡") + "。", invalidation: "外生冲击推升 VIX 突破区间。" },
      ],
      impacts: [
        { asset: "美债 UST", watch: t10.toFixed(2) + "% 附近的多空分歧", dir: dir10 },
        { asset: "美元 DXY", watch: dxy.toFixed(1) + " 的支撑/阻力", dir: upDn(-cdxy) },
        { asset: "黄金 XAU", watch: gold.toLocaleString("en-US") + " 关口", dir: upDn(cgold) },
      ],
      news: [
        { title: "Yields drift as markets weigh the data calendar", source: "CNBC", cat: "read", assets: ["UST"], dir: dir10 },
        { title: "Dollar holds range amid mixed signals", source: "MarketWatch", cat: "fact", assets: ["DXY"], dir: upDn(-cdxy) },
        { title: "Gold tracks real yields in quiet trade", source: "MarketWatch", cat: "fact", assets: ["XAU"], dir: upDn(cgold) },
      ],
      reviews: out.length % 3 === 0 ? [
        { ifThen: "若前一交易日的方向延续,曲线维持当前形态。", status: r() > 0.45 ? "held" : "invalidated", note: "次日走势" + (r() > 0.5 ? "确认" : "部分偏离") + "了该判断。" },
      ] : [],
    });
  }
  return out;
}

// RECENT ends at 2026-06-04 (issue 134); generate backward from there.
export const BRIEFS = [...RECENT, ...genOlder("2026-06-04", 133, 40)];

// ── Chart series — data contract ───────────────────────────────────────────
// Every chart/sparkline in the UI consumes a series of { date:'YYYY-MM-DD',
// value:number }. They are deterministically synthesized HERE (the mock data
// layer) so the render layer only maps a series → coordinates and never invents
// data. To wire a real backend, replace this whole block with series straight
// from JSON — the components need no change.
const _p2 = (n) => (n < 10 ? "0" + n : "" + n);
const _isoOf = (d) => d.getFullYear() + "-" + _p2(d.getMonth() + 1) + "-" + _p2(d.getDate());

// `n` trading days (Mon–Fri) ending at endISO, oldest-first.
function tradingBack(endISO, n) {
  const out = []; const d = new Date(endISO + "T00:00:00");
  while (out.length < n) { const wd = d.getDay(); if (wd !== 0 && wd !== 6) out.unshift(_isoOf(d)); d.setDate(d.getDate() - 1); }
  return out;
}
// 30-pt price walk anchored so the final point equals `endVal`.
function priceSeries(seed, endISO, endVal, amp, n = 30) {
  const rnd = rng(seed); const walk = []; let v = 0;
  for (let i = 0; i < n; i++) { v += rnd() - 0.48; walk.push(v); }
  const last = walk[n - 1], dates = tradingBack(endISO, n);
  return walk.map((w, i) => ({ date: dates[i], value: endVal + (w - last) * amp }));
}
// 18-pt sparkline walk (shape only; drift follows the day's change sign).
function sparkSeries(seed, change, endISO, n = 18) {
  const rnd = rng(seed); const vals = []; let v = 0;
  const drift = (change > 0 ? 1 : change < 0 ? -1 : 0) * 0.16;
  for (let i = 0; i < n; i++) { v += (rnd() - 0.5) * 0.95 + drift; vals.push(v); }
  const dates = tradingBack(endISO, n);
  return vals.map((val, i) => ({ date: dates[i], value: val }));
}
// Attach series to every brief: a sparkline per metric + a 30D price series per
// chart asset. Amplitudes are per-asset volatility scales (mock only).
BRIEFS.forEach((b) => {
  b.metrics.forEach((m) => { m.spark = sparkSeries(b.date + m.key, m.change, b.date); });
  const mv = (k) => b.metrics.find((m) => m.key === k).value;
  b.priceSeries = {
    nasdaq: priceSeries(b.date + "nasdaq", b.date, b.q.nasdaq[0], b.q.nasdaq[0] * 0.022),
    gold:   priceSeries(b.date + "gold",   b.date, mv("gold"),    mv("gold") * 0.018),
    dxy:    priceSeries(b.date + "dxy",    b.date, mv("dxy"),     1.4),
    us10y:  priceSeries(b.date + "us10y",  b.date, mv("us10y"),   0.22),
    vix:    priceSeries(b.date + "vix",    b.date, mv("vix"),     3.2),
    btc:    priceSeries(b.date + "btc",    b.date, b.q.btc[0],    b.q.btc[0] * 0.05),
  };
});
