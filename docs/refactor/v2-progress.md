# v2 重构 · 报告的预测价值评估

> 配合 [readme.md](readme.md)(总纲)与 [v1-progress.md](v1-progress.md)(V1 五步)阅读。
> **V2 使命**:不再只「分析今天」,而是**回答 V1 这套日报到底有没有预测价值**——
> 把历史报告逐日生成出来,用未来真实走势打分,并和朴素基准比较。
>
> **V2 范围锁定(本期)**:回填 **2026 年初 → 今**(机制跑通再延伸多年);评估以 **5d / 20d** 为主。
> 新闻做成**双模式开关**(默认不含 / 可选 GDELT 补历史)。
>
> **现状(2026-06-22)**:V1 日报已实跑(`data/briefs/` 含 06-17..06-20),`target_date` 贯穿管线、
> `news_mode` 双模式已就位、前端 `loadBriefs` 就绪——V2 的前置条件已具备;以下各步全部待建。

---

## 0. 一石二鸟:回填 = 前端真实历史 + 回测语料

V1 已把 `target_date` 贯穿管线,**回填就是对交易日做 for 循环、逐日调同一个 pipeline**。它同时解决两件事:

1. **前端真实历史** —— 回填出的真实报告写进 `data/briefs.json` → 前端直接显示真实历史,**干掉 9 天 mock(`demoBriefs.ts`)**。这就是原 F5「真实数据接管」自然达成。
2. **回测语料** —— 同一批报告 + 结构化判断,交给评估层(L4)打分。

## 1. 关于 vintage / ALFRED(已澄清:V2 不需要)

FRED 给的是**当前已修正**值;CPI/GDP/非农等宏观会被反复修正,回填时用修正值=偷看未来。**ALFRED** 存每日发布时的历史版本(vintage)可解决此问题——**但只对会被修正的宏观序列有意义**。日频市场数据(收益率/VIX/价格)从不修正。既然 V2 的被打分判断**只用市场序列、宏观仅作背景**,就**绕开了 vintage**,不需要 ALFRED。它只在未来把「宏观数据本身」放进被回测信号时(v3+)才相关。

## 2. 总体设计:在 V1 之上点亮 L4 评估层

```
L0 原始层   ──┐
L1 特征层     ├─ V1 已建(逐日可复算,因果)
L3 报告层   ──┘  + V2 新增「结构化判断块」(可打分)
                          │
L4 评估层(V2 核心)  ◀────┘  用 T+h 真实走势给 T 的判断打分 → 命中率 / 校准 / vs-baseline
```

---

## V2-S1 · 结构化判断块(让报告「可打分」)

**目标**:四层叙事是给人读的、机器没法客观打分;给 LLM 输出**加一个结构化判断块**(叙事照旧保留),作为 L4 的唯一打分对象。

**schema(`models.StructuredJudgment`,pydantic)**:
```jsonc
{
  "regime": "risk_on | risk_off | neutral",     // 全局基调
  "horizons": {
    "short_20d": { "equity": "...", "gold": "...", "usd": "...", "rates": "..." },
    "mid_60d":   { "equity": "...", "gold": "...", "usd": "...", "rates": "..." }
  },
  "confidence": 0.0,                              // 0~1,用于校准检验
  "key_factors": ["驱动该判断的特征名/原因"]
}
```
- `equity/gold/usd` 视图 ∈ `bullish | bearish | neutral`;`rates` ∈ `up | down | flat`(收益率方向)。
- 资产口径(用于打分):equity→`SP500`、gold→`XAU/USD`、usd→`DTWEXBGS`(广义)、rates→`DGS10`。
- **由代码喂的特征驱动**(强制分层),LLM 不算数、只判断。

**验收**:回填与实时报告都产出该块并通过 pydantic 校验;前端忽略未知字段(契约不破)。
- [ ] `StructuredJudgment` 模型 + 并入 LLM schema/prompt
- [ ] 回填与实时两路都生成并校验

---

## V2-S2 · 回填引擎(`backfill.py`)

**目标**:逐日生成历史报告,**严格 point-in-time**(不偷看未来),可断点续跑。

**设计**:
- 交易日历 = 取自 L0 实际有值的日期(只在市场序列有观测的日子出报告)。
- `for target_date in trading_days(2026-01-01 .. today)`:已存在 `briefs/<date>.json` 则跳过(幂等续跑);否则调 `pipeline(target_date, news_mode=...)`。
- **point-in-time 切片**:
  - 市场/特征:只用 `obs_date <= target_date`;滚动特征因果安全。
    - *已知近似*:日频市场数据当日值常**次工作日才发布**(发布滞后 ~1 天),用 `obs_date <= T` 会轻微过包含 → V2 接受此近似并在文档/输出中标注(影响极小)。
  - **新闻 = 双模式开关 `news_mode`**:
    - `none`(**默认**):历史报告不含新闻;新闻分类只对「上线起、向前」的实时报告生效。最干净,杜绝预知未来新闻。
    - `gdelt`:用 **GDELT Doc API** 拉 `target_date` 当日及之前的历史新闻(实测可用:返回带 `seendate` 的文章、可按 `startdatetime/enddatetime` 窗口筛、免费无 key)。**约束(实测)**:① **≤1 请求/5 秒**;② 全球新闻**偏噪**,需 query/域名白名单/主题(如 `ECON_*`)过滤出财经质量;③ 严格 `enddatetime <= target_date 23:59`,只取已发布。
      - **慢查 + 本地缓存(不重复查)**:GDELT 不在回填主循环里同步硬拉,而是**前期单独、慢速地**逐日抓(守 5 秒节流,可分多次/多日填完),抓到的当日新闻**缓存到本地**;回填/重跑时**优先读缓存**,缓存命中就不再打 GDELT。这样既不被限流卡住,也避免重复请求。
      - **缓存格式 = markdown(2026 规模够用)**:每个交易日一份 `data/news_cache/gdelt/<date>.md`(列出当日文章:source / title / link / 摘要,行格式固定便于回读)。人读、可 diff、**提交入库**(小、可复现、省得换机/CI 重抓)。规模上来(多年)再考虑换 parquet/JSON。
- LLM 成本:~115 交易日 × 1 次调用,DeepSeek 量级几美元,续跑可控。

**验收**:回填 2026 全年产出 `briefs/<date>.json`(含结构化判断);抽查某日报告不含其后任何数据/新闻;两种 `news_mode` 均跑通。
- [ ] 交易日历 + 幂等续跑循环
- [ ] point-in-time 市场切片 + 因果校验
- [x] `news_mode=none`(默认)——管线侧已就位(`pipeline.py` / CLI `--no-news`);仅缺回填主循环
- [ ] GDELT 慢查脚本:5 秒节流逐日抓 → 本地 markdown 缓存(`data/news_cache/gdelt/<date>.md`),可分次填、入库
- [ ] `news_mode=gdelt`:优先读缓存(命中不重查)+ 财经过滤 + 严格日期上界
- [ ] 全年回填一次,人工抽查无偷看未来

---

## V2-S3 · 评估层(`eval/`)——V2 核心

**目标**:用未来真实走势给历史判断打分,并回答**「打不打得过朴素基准」**。

### 模块
```
eval/outcomes.py  # 未来实现值:fwd_ret(asset,h)/fwd_drawdown/fwd_vix_chg/fwd_rate_chg @ h∈{5,20,60}d
eval/scoring.py   # (StructuredJudgment, outcomes) → 每个 资产×周期 判 correct/partial/wrong
eval/baselines.py # 朴素基准:永远看多 / 动量(跟随近20d方向) / 随机
eval/metrics.py   # 命中率 · 校准 · vs-baseline 技能差 · (可选)PnL/Sharpe/maxDD
eval/report.py    # 评估汇总 data/eval/summary.json + 人读 md;逐报告标签 data/eval/<date>.json
```

### 打分规则(方向性)
- `equity=bullish` → `fwd_ret(SP500,h) > +ε` 记对;`bearish` → `< −ε`;`neutral` → `|fwd_ret| ≤ ε`(ε 取小带宽,可按波动缩放)。`gold`/`usd` 同理;`rates=up` → `fwd_chg(DGS10,h) > +δbp`。
- `regime=risk_on` → 复合:`fwd_ret(SP500,h)>0` 且 VIX 未显著上行;`risk_off` 反之。

### 关键:vs-baseline 才是"价值"的真正检验
> 股市长期上行 → **"永远看多标普"本身就有 ~55–60% 的日子对**。所以只报"准确率>50%"会骗自己。
> **技能 = LLM 命中率 − 基准命中率**(逐 资产×周期)。只有正技能才叫有预测价值。

### 产出指标
- 命中率(逐 资产×周期)、**vs-baseline 技能差**;
- **置信度校准**:按 confidence 分桶看准确率——LLM 说"高置信"时是否真更准;
- **可评估覆盖**:逐周期能打分的报告数(见下样本约束);
- (可选,进阶)按判断调仓的假想 PnL / Sharpe / 最大回撤 vs 买入持有。

### 样本与周期硬约束(必须在报告里写明,不能假装覆盖)

| 周期 | 需未来 | 2026 回填(~115 日)可评估点 | 结论 |
|---|---|---|---|
| 5d | T+5 | ~110 | 可评 |
| 20d | T+20 | ~95 | 可评(主力) |
| 60d | T+60 | ~55 | 勉强,统计弱 |
| 120d | T+120 | ~0 | **2026 内无法评**,需延伸多年 |

### 方法论红线
- **重叠窗口**:逐日 20d 收益高度重叠/自相关 → 普通显著性检验会高估置信度;用 **block bootstrap** 给区间,并报**有效样本量**。
- **多重比较**:资产×周期×基准格子很多 → 谨慎解读"某格显著"。

**验收**:对 2026 回填全量出评估汇总;能明确给出"5d/20d 上 equity/gold/usd/rates 各自的技能差为正/负";校准曲线可读。
- [ ] outcomes / scoring / baselines / metrics / report
- [ ] vs-baseline 技能差(核心结论)
- [ ] 置信度校准 + block bootstrap 区间
- [ ] 覆盖与样本约束如实标注

---

## V2-S4 · 前端真实历史接管(干掉 mock)

**目标**:回填后 `briefs.json` 已是真实历史 → 前端从 9 天 demo 切到真实(`loadBriefs` 已就绪:真实非空即用真实)。

**设计**:跑完回填提交 `briefs.json` → 前端自动用真实数据;`demoBriefs.ts` 降为「真实为空时的最终兜底」或移除。历史报告 `news_mode=none` 时无新闻节(前端空态已支持);指标表用 V1 新特征填充。
- *(可选,后续)* 把 L4 逐报告标签(✅/✕/部分)显示到前端历史报告上——属前端契约升级,留到那时统一做。

**验收**:前端显示 2026 真实历史、无 `[object Object]`、空新闻节正常。
- [ ] 回填产出并提交 `briefs.json`
- [ ] 前端切真实(demo 降兜底/移除)

---

## V2-S5 · 延伸多年(机制跑通后,本期不强求)

2026 内无法评中长周期(无足够未来)。机制验证后,把回填**延到 2010+**(标普用 FRED 2016+ / Tiingo `SPY` 1993+,黄金 `XAU/USD` 2012+ / Tiingo `GLD` 2004+,实际利率 2003+,UUP 2007+),获得统计意义与全周期评估。GDELT 模式在多年下太慢 → 多年回填默认 `news_mode=none`。
- [ ] 多年回填(分批、续跑)
- [ ] 全周期(含 60/120d)评估 + 跨年 regime 复盘

---

## 与 V1「假设追踪」的关系

V1 的假设追踪(`hypotheses.py`)是**人读、逐条**的定性验证;V2 的 L4 是**系统化、可统计**的定量评估。二者互补:L4 接管"打分/统计",假设追踪保留为人面向的叙事层。后续可让结构化判断与假设共用一套复盘出口。

## 跨步注意事项

- **point-in-time 是红线**:市场切 `obs_date<=T`;新闻按 `news_mode` 严格日期上界;宏观不进被打分信号。
- **诚实优先**:覆盖不足/无法评估的周期**如实标注**,不假装覆盖。
- **密钥/环境/规范**:四家 key 仅存 `.env`(已 gitignore);本地跑 conda env `myTools`;全量 type hints + pydantic 守边界。
