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
L3 报告层   ──┘  + V2:特征快照(signals,代码填)+ 结构化判断(带 horizon,LLM)→ 可打分
                          │
L4 评估层(V2 核心)  ◀────┘  用 T+h 真实走势给 T 的判断打分 → 命中率 / 校准 / vs-baseline
```

---

## V2-S1 · 让报告「可打分」(结构化输出 + 时间界限)

四层叙事是给人读的、机器没法客观打分。V2 在**叙事照旧保留**的前提下,额外让产物产出三块
可机读、可打分的结构化数据。共享纪律:**数字/特征由代码算,LLM 只判断与解释**。

### 固定预测方向(roster)—— 一方向一条,禁止凑数

为避免「LLM 随便列几条、T+1 一堆未触发」,把预测对象**锁死成固定 roster,每个方向给且只给一条**
由特征驱动的预测:

| 方向 | 序列 | 宏观角色 |
|---|---|---|
| 纳指 | `NASDAQCOM` | 风险偏好/成长(对利率最敏感) |
| 黄金 | `XAUUSD` | 实际利率 + 美元 + 避险/去美元化 |
| 广义美元 | `DTWEXBGS` | 宏观总开关(压制黄金/新兴/大宗) |
| 2Y 利率 | `DGS2` | 美联储路径 / 短端 |

- 代码常量 `PREDICTION_TARGETS` 锁定;schema 用 `asset` 枚举 + `minItems=maxItems=4` 强制「不超不漏」。
- **「假设层」=「对这 4 个方向的预测」**——B 的结构化判断与 C 的可证伪假设在此合一:每条 =
  `{asset, direction, horizon, confidence, key_factors, if_then(人读), 可度量 invalidation}`。
- **禁止凑数**:不列低信心命题;每条必须能追溯到驱动它的特征(`key_factors`)。
- 标普 / VIX / 2s10s 曲线等先不纳入(冗余 / 难方向预测 / 进阶),保持干净;roster 可后续扩。

### A. 特征快照持久化(`signals` 块 —— 代码填,不经 LLM)

现状缺口:`features.compute_features` / `regime` 已算出丰富特征(距 MA200 / 动量 / 年化波动 /
z / 52 周分位 / 跨资产 60 日相关 / 美元背离 / regime 标签),但**只喂给 LLM 就丢了**——产物里
只有 10 行 level+日变化的 headline 表,丰富特征既不落盘进契约、也不可机读。

做法:把 `snap`(=`features.snapshot_at`)+ `regime` **结构化序列化进 brief 契约**:

```jsonc
"signals": {
  "trend":    [{ "key": "SP500_px_vs_ma200", "label": "标普500 距MA200", "value": -0.012, "unit": "pct", "group": "trend" }],
  "momentum": [ ... ], "vol": [ ... ], "rates": [ ... ], "dollar": [ ... ], "cross_asset": [ ... ]
},
"regime": { "equity_trend": "above_ma200", "vol_regime": "mid/elevated", "curve": "normal/flattening",
            "real_rate": "rising", "inflation_expectations": "falling", "dollar": "weak/diverging" }
```
- `unit ∈ pct | bp | z | corr | level | bool | ratio`(异构特征各带单位,前端按单位格式化)。
- **headline 指标表保持干净**(就那 10 行关键电平+日变化);丰富特征进独立 `signals` 块,前端渲染成可展开的几节。
- **单一事实源(防漂移)**:抽出一份「特征视图」注册表(feature → label/unit/group),让**喂 LLM 的特征文本块**
  (现 `prompt.build_feature_block`)与 **`signals` JSON** 都从它生成,杜绝两边显示不一致。
- 价值:① 数据/事实层稳定地厚、可机读,不靠 LLM 心情;② L4 打分/归因要用「当时的特征值」留痕,这里正好提供。

### B. 结构化判断块(`models.StructuredJudgment` —— L4 打分主力)

给 LLM 输出加一个结构化判断块,作为 L4 的主要打分对象。**horizon 用固定枚举,不要自由 N**——
回测要跨日聚合同周期判断(还要处理重叠窗口),自由 N 会把统计桶打碎、也没法和 baseline 比。

```jsonc
{
  "regime": "risk_on | risk_off | neutral",
  "horizons": {                                  // 固定档,对齐 S3 评估周期
    "h_5d":  { "equity": "...", "gold": "...", "usd": "...", "rates": "..." },
    "h_20d": { ... },
    "h_60d": { ... }                              // 60d 统计弱、120d 本期不评(见 S3)
  },
  "confidence": 0.0,                              // 0~1,用于校准检验
  "key_factors": ["驱动该判断的特征名/原因"]
}
```
- `equity/gold/usd` ∈ `bullish | bearish | neutral`;`rates` ∈ `up | down | flat`。
- 资产口径(= 固定 roster,见上):纳指→`NASDAQCOM`、黄金→`XAUUSD`、美元→`DTWEXBGS`、利率→`DGS2`。
- **由代码喂的特征驱动**(强制分层),LLM 不算数、只判断。

### C. 叙事假设/影响带「时间界限 + 可度量失效」(让人读的那层也可证伪)

现状痛点:假设写「若 2Y 后续交易日继续上行突破」——**没期限、没阈值、失效不可度量 → 永远不结算、
机器判不了对错**。V2 给每条可证伪命题强制四要素:

| 要素 | 现状 | 需要 |
|---|---|---|
| 指向哪个序列 | 自由文本 | 机读 `asset`(如 `DGS2`) |
| 方向/阈值 | 自由文本 | `direction` + 可度量阈值 |
| **时间界限** | **缺(痛点)** | `horizon ∈ {next_1d, h_5d, h_20d, h_60d}` |
| 失效/确认条件 | 自由文本 | 绑定「序列+阈值+期限」,代码能判 |

```jsonc
{
  "statement": "2Y 上行压力未消,短端利率领涨",        // 人读叙事保留
  "asset": "DGS2", "direction": "up", "horizon": "h_5d",
  "invalidation": "5 个交易日内 DGS2 未突破 4.30%(或回落至 4.10% 下)"
}
```
- **阈值锚定代码给的真实数字**:LLM 基于收到的「当前 2Y=4.20%、20 日 +15bp」给阈值,而非凭空编 —— 守住「代码算数字、LLM 只解释」。
- 影响层同理:`{asset, watch, dir, horizon}`,观察点也带时间界限。
- **红利**:这条让现在 `hypotheses.py` 的复盘从「LLM 主观判 held/invalidated」升级为「到期限按阈值客观判定」,**V1 假设追踪质量一起提上去**。

### 前端契约升级(向后兼容)

新增 `signals` + `regime` + `judgment` + 假设/影响的 `horizon`/`asset`/`direction` 字段;旧字段不动,
旧前端忽略未知字段即可。前端反正要按 `frontend/design` 重做,届时直接渲染丰富的结构化指标。

**验收**:回填与实时报告都产出 `signals` / `judgment` / 带 horizon 的假设,并通过 pydantic 校验;前端契约不破。
- [ ] 「特征视图」注册表 + `signals` 块序列化(prompt 文本块与 JSON 同源)
- [ ] `StructuredJudgment` 模型(固定 horizon 枚举)+ 并入 LLM schema/prompt
- [ ] 假设/影响加 `asset`/`direction`/`horizon`/可度量 `invalidation`,阈值锚定特征值
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
- `纳指=bullish` → `fwd_ret(NASDAQCOM,h) > +ε` 记对;`bearish` → `< −ε`;`neutral` → `|fwd_ret| ≤ ε`(ε 取小带宽,可按波动缩放)。`黄金`/`美元` 同理;`利率=up` → `fwd_chg(DGS2,h) > +δbp`。
- `regime=risk_on` → 复合:`fwd_ret(NASDAQCOM,h)>0` 且 VIX 未显著上行;`risk_off` 反之。
- **条件型假设(S1-C)单独打分**:到 `horizon` 检查阈值是否触发——触发且方向对=对、触发但反向=错、
  **未触发 = 不计入命中率**(单列「未触发率」,别当对/错)。`StructuredJudgment`(B,固定 horizon、无条件)
  是统计主力,条件假设是补充视图(事件驱动、样本更稀)。

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
- [ ] 条件型假设打分(含「未触发」单列)
- [ ] 覆盖与样本约束如实标注

---

## V2-S4 · 前端真实历史接管(干掉 mock)

**目标**:回填后 `briefs.json` 已是真实历史 → 前端从 9 天 demo 切到真实(`loadBriefs` 已就绪:真实非空即用真实)。

**设计**:跑完回填提交 `briefs.json` → 前端自动用真实数据;`demoBriefs.ts` 降为「真实为空时的最终兜底」或移除。历史报告 `news_mode=none` 时无新闻节(前端空态已支持);除 headline 指标表外,前端还渲染 S1-A 的 `signals` 块 + S1-B 的结构化判断。
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

V1 的假设追踪(`hypotheses.py`)是**人读、逐条**的定性验证;V2 的 L4 是**系统化、可统计**的定量评估。二者互补:L4 接管"打分/统计",假设追踪保留为人面向的叙事层。**S1-C 给假设加上 horizon + 可度量失效条件后,现在 `hypotheses.py` 的复盘可从「LLM 主观判 held/invalidated」升级为「到期限按阈值客观判定」——这是 V2 顺带给 V1 假设追踪的质量升级**;后续可让结构化判断与假设共用一套复盘出口。

## 跨步注意事项

- **point-in-time 是红线**:市场切 `obs_date<=T`;新闻按 `news_mode` 严格日期上界;宏观不进被打分信号。
- **诚实优先**:覆盖不足/无法评估的周期**如实标注**,不假装覆盖。
- **密钥/环境/规范**:四家 key 仅存 `.env`(已 gitignore);本地跑 conda env `myTools`;全量 type hints + pydantic 守边界。
