# v2 重构 · 报告的预测价值评估

> 配合 [readme.md](readme.md)(总纲)与 [v1-progress.md](v1-progress.md)(V1 五步)阅读。
> **V2 使命**:不再只「分析今天」,而是**回答 V1 这套日报到底有没有预测价值**——
> 把历史报告逐日生成出来,用未来真实走势打分,并和朴素基准比较。
>
> **V2 范围锁定(本期)**:回填 **2026 年初 → 今**(机制跑通再延伸多年);评估以 **5d / 20d** 为主。
> 新闻做成**双模式开关**(默认不含 / 可选 GDELT 补历史)。
>
> **现状(2026-06-23)**:V1 日报 + **V1.5 多模型(每模型一份 view + 代码级共识)+ 中转站**已实跑;
> `target_date` 贯穿管线、`news_mode` 双模式已就位、前端 `loadBriefs` + 模型切换器就绪——V2 前置条件已具备。
> 注:开发迭代期**历史简报数据按需弃用、只留最新单日重跑**(产品未稳,不做旧契约兼容),故 `data/briefs/` 非全历史;
> 回填(S2)是补齐真实历史的正式手段。以下 V2 各步仍全部待建。

---

## 0. 一石二鸟:回填 = 前端真实历史 + 回测语料

V1 已把 `target_date` 贯穿管线,**回填就是对交易日做 for 循环、逐日调同一个 pipeline**。它同时解决两件事:

1. **前端真实历史** —— 回填出的真实报告写进 `data/briefs.json` → 前端直接显示真实历史,**干掉 9 天 mock(`demoBriefs.ts`)**。这就是原 F5「真实数据接管」自然达成。
2. **回测语料** —— 同一批报告 + 结构化判断,交给评估层(L4)打分。

## 1. 关于 vintage / ALFRED(已澄清:V2 不需要)

FRED 给的是**当前已修正**值;CPI/GDP/非农等宏观会被反复修正,回填时用修正值=偷看未来。**ALFRED** 存每日发布时的历史版本(vintage)可解决此问题——**但只对会被修正的宏观序列有意义**。日频市场数据(收益率/VIX/价格)从不修正。既然 V2 的被打分判断**只用市场序列、宏观仅作背景**,就**绕开了 vintage**,不需要 ALFRED。它只在未来把「宏观数据本身」放进被回测信号时(v3+)才相关。

## 1b. 关于 LLM 回填的「记忆污染」(比 vintage 更根本,落地前必须对齐)

回填时**市场数据是 point-in-time 切的(干净)**,但 **LLM 的权重/知识是「现在」的**——它可能
「记得」`target_date` 之后发生了什么(训练语料里就有)。于是回填出的「历史预测」可能是**用记忆作弊**,
命中率虚高,**测的不是预测能力,是记忆力**。

- 污染程度取决于 **provider 的知识截止**:截止早于回填区间→较干净;覆盖该区间→污染重。
  **落地第一件事:确认所用模型的知识截止。**
- **多年回填(S5)几乎必然污染**(模型当然知道 2010–2020)→ 只能当**前端历史素材**,**不能当能力评估**。
- **唯一完全诚实的评估 = 向前/实时积累**:从上线起每天产预测,随时间用真实走势打分。慢但干净;
  日报本就天天产 → 前向 track record 自然增长。

→ **把「命中率」分两类、分开标注**:
  - **(a) 前向实盘命中率** = 诚实主结论(上线后逐日累积);
  - **(b) 回填命中率** = 辅助/历史填充,**必须标注「含模型记忆污染,仅供参考」**,且仅「模型截止后」的日子稍可信。

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
- **红利**:这条让复盘从「LLM 主观判 held/invalidated」升级为「到期限按阈值客观判定」——**V1.5 的 `predictions.py` 预测账本已落地此客观化**(到期代码算命中,LLM 仅写复盘 note)。

### 前端契约升级(向后兼容)

新增 `signals` + `regime` + `judgment` + 假设/影响的 `horizon`/`asset`/`direction` 字段;旧字段不动,
旧前端忽略未知字段即可。前端反正要按 `frontend/design` 重做,届时直接渲染丰富的结构化指标。

**验收**:实时报告产出 `signals` / `regime` / 带预测字段的假设,并通过 pydantic 校验;前端契约不破。
- [x] 「特征视图」注册表(`features.FEATURE_VIEW`)+ `signals` 块序列化进 briefs.json
      (prompt 文本块仍独立,但与 signals 同读一份 `snap`,数值一致)
- [x] `regime` 块落进契约(代码派生标签:equity_trend/vol_regime/curve/real_rate/inflation_expectations/dollar)
- [x] 假设层 = 对固定 roster 的预测,带 `asset`/`direction`/`horizon`/`confidence`/`key_factors`/可度量失效
      (结构化判断与可证伪假设合一,无需单独 `StructuredJudgment` 模型)
- [ ] 回填路径产出并校验(待 S2 回填引擎)

---

## V2-S1c · 多模型预测账本 + 共识实际走势列(2026-06-23 增补;v1.5 多模型落地后)

S1 当初按单模型设计。v1.5 落地了多模型(每模型一份 `ModelView` + 代码级 `consensus`),几处要具体化。**本节 (1)(2) 的预测账本 + 共识实际走势列已在 V1.5 落地**(`predictions.py` / `render.apply_actuals` / 前端 `ActualLine`);**剩余的聚合命中率 / 校准 / 命中率页仍待 S2/S3。**

**(1) 预测账本升级到「逐预测结构化、分模型」**
- 升级前的 `hypotheses.py`/`hypotheses.csv` 只存**主模型**的 `if_then/invalidation` 文本——没有结构化 `asset/direction/horizon`、不分模型 → 无法分模型打分、无法算共识命中。
- **已落地**(`predictions.py`):逐预测行 `{created_date, model, asset, direction, horizon, confidence, status, resolved_date, realized_dir, realized_text, hit, note}`,分模型;共识不单独存(代码由当日各模型预测重算)。

**(2) 跨模型共识行加「实际走势」列(代码算,非 LLM)**
- 共识行右侧加**已实现方向 + 涨跌幅**:`预测日收盘` vs `预测日+h 收盘`,纯代码——契合「代码算数字、LLM 只解释」。
- **双标准窗 5d / 20d** 各算一份(对齐 §S3 评估周期);未到期标 `pending`。
- **flat 死区**:`|涨跌| < ε` 记 flat(ε 可按波动缩放),否则没有真横盘。
- **horizon 歧义**(关键):同资产各模型 horizon 可能不同(例:06-22 黄金 5d/20d/20d)→ 共识实际按**固定窗**算,而非按某条预测的 horizon;每条预测自身的命中仍在 §S3 按其 horizon 打分。
- per-model 也记已实现命中 → 喂 §S3 `byAsset`,并为 `build_consensus` 按战绩加权铺路(目前等权,加权入参待加)。

**(3) 页面分工(对齐 §S4)**
- **brief 页**:复盘卡瘦身——只显示**当日新产生的 4 条预测**(+ 当日刚结算的),不再铺开全部历史 `open`;共识行带「实际走势(到期回填)」。
- **命中率 / track 专页**(现为空态):承载**全部待验证(pending)+ 已结算**预测、命中率/校准/vs-baseline、per-model 战绩——即用户要的「单独页面看所有预测」。

**(4) 诚实性**:实际走势**前向积累最干净**(§1b);回填历史预测的实际虽是真实市场值,但预测本身可能含模型记忆污染 → 专页须标 `source=forward/backfill`。

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
- [x] `news_mode=none`(回填用;日常实时默认 `live`)——管线侧已就位(`pipeline.py` / CLI `--no-news`);仅缺回填主循环
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
eval/report.py    # 评估汇总 data/eval/summary.json + 人读 md;逐报告标签 data/eval/<date>.json;前端 track-record data/eval/track.json
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

### 前端命中率对齐:track-record 契约(`data/eval/track.json`)

前端 `frontend/desgin/resource/track.js` 想要「每日 score(0-100)+ grade(绿/黄/红)+ 月/季/年 accuracy」,
但本层是按**资产×周期**打分,要桥三处:

- **gap A(4 资产×多周期 → 每日一个 0-100)**:每日 score = 当日 4 条预测在**固定 5d 周期**的命中率
  (5d 最快结算,可按 confidence 加权);深周期(20/60d)进 `byAsset` 表,不混进每日 heatmap。
  **grade 不用裸命中率(会自欺)→ 用 vs 基准的技能带**(hit−baseline:正=绿/平=黄/负=红)。
- **gap B(最近的日子还没法打分)**:5d 预测要 T+5 才结算 → 当周预测 `status="pending"`,前端染灰
  (track.js 本就把无数据日染灰)。
- **gap C(裸命中率骗人)**:展示必须带 **vs baseline 技能差 + 样本量 + 周期**;孤零零一个分数 = 误导。

契约(镜像 track.js 形状 + 诚实字段):
```jsonc
{
  "source": "forward | backfill",        // 诚实标注来源(backfill 含记忆污染,见 §1b)
  "primaryHorizon": "h_5d",
  "days":    { "2026-06-13": { "score": 75, "grade": "green", "n": 4, "status": "final" },
               "2026-06-20": { "status": "pending" } },          // 喂 heatmap
  "byAsset": { "NASDAQCOM": { "h_5d": { "hit": 0.62, "baseline": 0.55, "skill": 0.07, "n": 40 } } },  // 诚实主结论
  "rollups": { "months": { "2026-06": { "acc": 68, "skill": 6, "n": 18 } } }   // track.js 要的月/季/年
}
```

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
- [ ] 产出 `data/eval/track.json`(days/byAsset/rollups + source 标注)供前端
- [ ] forward / backfill 分开标注;命中率展示带 baseline+样本量(诚实底线)
- [ ] 覆盖与样本约束如实标注

---

## V2-S4 · 前端真实历史接管(干掉 mock)

**目标**:回填后 `briefs.json` 已是真实历史 → 前端从 9 天 demo 切到真实(`loadBriefs` 已就绪:真实非空即用真实)。

**设计**:跑完回填提交 `briefs.json` → 前端自动用真实数据;`demoBriefs.ts` 降为「真实为空时的最终兜底」或移除。历史报告 `news_mode=none` 时无新闻节(前端空态已支持);除 headline 指标表外,前端还渲染 S1-A 的 `signals` 块 + S1-B 的结构化判断。

**命中率 / track-record 展示(对齐 §S3 契约)**:
- **先上**:`reviews[]`(逐条 held/invalidated/open)是**已有的真实** track record,前端先展示它,别等聚合命中率。
- **再上**:聚合命中率读 `data/eval/track.json`——heatmap 用 `days`(pending 染灰)、技能表用 `byAsset`、月/季/年用 `rollups`。
- **红线**:真打分跑出来前,前端**绝不显示命中率数字**;展示必带 baseline + 样本量;backfill 来源要标注(见 §1b)。

**验收**:前端显示 2026 真实历史、无 `[object Object]`、空新闻节正常。
- [ ] 回填产出并提交 `briefs.json`
- [ ] 前端切真实(demo 降兜底/移除)
- [ ] track.json 接入前端(heatmap/技能表/rollups;pending 染灰、带 baseline、标 source)

---

## V2-S5 · 延伸多年(机制跑通后,本期不强求)

2026 内无法评中长周期(无足够未来)。机制验证后,把回填**延到 2010+**(标普用 FRED 2016+ / Tiingo `SPY` 1993+,黄金 `XAU/USD` 2012+ / Tiingo `GLD` 2004+,实际利率 2003+,UUP 2007+),获得统计意义与全周期评估。GDELT 模式在多年下太慢 → 多年回填默认 `news_mode=none`。
- [ ] 多年回填(分批、续跑)
- [ ] 全周期(含 60/120d)评估 + 跨年 regime 复盘

---

## 与 V1「假设追踪」的关系

V1 的假设追踪(旧 `hypotheses.py`,**V1.5 已由 `predictions.py` 预测账本替代**)是**人读、逐条**的定性验证;V2 的 L4 是**系统化、可统计**的定量评估。二者互补:L4 接管"打分/统计",逐条预测的实际结果(`predictions.py` 已产出)保留为人面向的叙事层。**给预测加上 horizon + 可度量失效后,复盘已从「LLM 主观判 held/invalidated」升级为「到期限按代码客观判定命中」(V1.5 `predictions.py` 落地);LLM 仅写复盘 note**;聚合打分/校准仍待 L4。

## 跨步注意事项

- **point-in-time 是红线**:市场切 `obs_date<=T`;新闻按 `news_mode` 严格日期上界;宏观不进被打分信号。
- **诚实优先**:覆盖不足/无法评估的周期**如实标注**,不假装覆盖。
- **回填记忆污染是红线**(§1b):命中率以**前向实盘**为主;回填命中率必标「仅供参考」;真打分前前端不显示任何命中率。
- **密钥/环境/规范**:四家 key 仅存 `.env`(已 gitignore);本地跑 conda env `myTools`;全量 type hints + pydantic 守边界。
