# 数据重构(data-quality refactor)· 总纲

> 本目录是「以**数据质量**为核心的后端重构」的设计与进度中枢。
> 起因:旧版喂给 LLM 的数据太薄(7 个原始值),且让 LLM 既「心算」又「解读」,
> 简报因此模糊、偶有算错。本次重构把后端**推平为纯 Python**,引入
> 「**代码算特征 → LLM 只解释**」的强制分层,并用 **FRED + Twelve Data + Tiingo**
> 三家数据强强联合,显著抬高内容质量的上限。
>
> - 当前代码现状与设计思路 → [`py/newsletter/README.md`](../../py/newsletter/README.md)
> - V1 细节分步设计与进度 → [v1-progress.md](v1-progress.md)(五步已全部完成)
> - V2 细节分步设计与进度 → [v2-progress.md](v2-progress.md)(报告的预测价值评估)
> - 本文件保留:动机 / 总架构 / 数据源分工 / 进度总表 / v2·v3 展望 / 技术栈与安全

---

## 1. 为什么重构

| 旧版痛点 | 重构后 |
|---|---|
| 喂 LLM 的只有 7 个**原始值**,信息量太薄 | 代码先算**技术特征**(趋势/动量/波动/利率·通胀/美元/跨资产相关性/极值),再喂 LLM |
| LLM 既要「心算变化量」又要解读 → 模糊、偶错(如 `{'fact': ...}` 泄漏) | **强制分层**:数字由代码算,LLM 只做判断与解释 |
| 数据源单一(FRED 缺金价、缺窄口径 DXY、SP500 仅 10 年) | **三家强强联合**补齐缺口(见 §3) |
| Rust 抓取 + Python 智能,两语言接缝维护成本 | **推平为纯 Python**,Rust 数据平面退役 |
| 只能分析「今天」 | 代码贯穿 `target_date`,为 v2「历史回放 + 未来验证」留好接口 |

## 2. 总架构:五层管线

```
L0 原始数据层    三家 API 拉日频原始序列 → 本地 parquet(每日全量覆盖,价格类历史不变)
L1 特征层        pandas 算技术特征(滚动=因果,天然不偷看未来)
L2 周期特征层    (v2)按 周/月/季/年 聚合
L3 LLM 报告层    固定格式特征块喂 LLM → LLM 只解释 → 输出前端兼容 JSON
L4 评估层        (v2)用未来真实走势验证 L3 判断 → 命中率/胜率统计
```

**三条贯穿原则**(重构的灵魂):
1. **强制分层**——代码算数字,LLM 只判断。内容质量的最大杠杆。
2. **`target_date` 贯穿**——同一套代码既出「今天」也能站历史任一天 → 天然可回测(v2 兑现)。
3. **不偷看未来**——滚动特征只用过去窗口,因果安全;唯一风险是被修正的宏观数据(vintage),v1 用规避策略(月频宏观只当背景、不进特征/回测)。

## 3. 数据源分工(强强联合)

实测各家免费档能力后的分工(探测结论见 [v1-progress.md](v1-progress.md) §1):

| 逻辑指标 | 主源 | 备份/代理 | 说明 |
|---|---|---|---|
| 利率 2Y/10Y、利差 2s10s、实际利率 DFII10、广义美元 DTWEXBGS、VIX、宏观 CPI/失业/非农 | **FRED** | — | 权威、免费、无硬限额 |
| **黄金** | **Twelve Data `XAU/USD`** | Tiingo `GLD` / Yahoo `GC=F` | 真现货、无分红回溯调整、值最稳;回溯 2012+ |
| **窄口径美元指数(DXY)** | **Tiingo `UUP`**(代理) | — | FRED 与 TD 免费档均无真 DXY;UUP=美元指数 ETF,作**代理**。**只比收益率/趋势/标准化,绝不取绝对价位**(`UUP_ret≈DXY_ret`、`UUP_trend≈DXY_trend`、`UUP_z≈美元强弱极端度`)。据此找回「广义 vs 窄口径」背离叙事(诚实标注代理) |
| **股指长历史**(回测用,v2) | **Tiingo `SPY`/`QQQ`** | FRED `SP500`/`NASDAQCOM` | FRED 的 SP500 仅近 10 年;SPY 回到 1993、QQQ 回到 1999 |
| 通胀预期(派生) | `DGS10 − DFII10` 或 FRED `T10YIE` | — | 盈亏平衡通胀,简报很有用的派生量 |

> 注:ETF 的 `adjClose` 会随分红**回溯调整**(历史值会微变),所以代理类优先用未复权 `close`,
> 或明确接受复权口径——这点直接影响「历史数据不变」的假设。详见 v1-progress §3。

## 4. 进度总表

> 状态:☐ 未开始 · ◐ 进行中 · ✅ 完成。逐步设计与验收见 [v1-progress.md](v1-progress.md)。

| 步骤 | 内容 | 状态 |
|---|---|---|
| **Step 1** | 数据源接入与分工(FRED/TwelveData/Tiingo/Yahoo,统一 Source 接口) | ✅ |
| **Step 2** | 特征层:精选技术特征(pandas,因果滚动) | ✅ |
| **Step 3** | 存储形态(parquet 原始层)+ LLM 输入固定格式 + 前端兼容 JSON 输出 | ✅ |
| **Step 4** | 代码架构整体重设计 + LLM 强制分层(无历史包袱) | ✅ |
| **Step 5** | Rust 数据平面退役 | ✅ |

**V1.5(内容与体验增强,见 [v1.5-progress.md](v1.5-progress.md)):** V1 之后、V2 之前的一波增强,不改骨架。

| 项 | 内容 | 状态 |
|---|---|---|
| **契约加厚** | `briefs.json` 增 signals + regime + 预测卡 roster + metric.spark + priceSeries;facts/reads 升级为带 figures 的标签条 | ✅ |
| **文本规范化** | `textnorm.normalize_text`(标点/空格/引号)+ `llm/style.TEXT_STYLE` 公共 prompt 片段 | ✅ |
| **LLM 健壮性** | 结构化输出改 JSON mode(修 DeepSeek 复杂 schema 失稳);新闻升级 + fetch/classify 解耦 | ✅ |
| **前端 3 页 SPA** | 按设计稿(`市场走势简报.dc.html`)重建为 简报/时间线/命中率 三页,详见 [frontend-rebuild.md](../frontend-rebuild.md) | ✅ |
| **多模型 + 中转站** | `Brief` 拆「脊柱 + 按模型 views + 代码级共识」;`LLM_MODELS` 多模型生成、前端右上角切换器 + 共识行;Claude/OpenAI 经中转站接入(各模型族不同 key) | ✅ |

**V2(预测价值评估,见 [v2-progress.md](v2-progress.md)):**

| 步骤 | 内容 | 状态 |
|---|---|---|
| **V2-S1** | 结构化判断块(让报告可打分) | ☐ |
| **V2-S2** | 回填引擎(`target_date` 循环 + point-in-time + 新闻双模式 none/gdelt) | ☐ |
| **V2-S3** | 评估层 L4(命中率 / 校准 / **vs-baseline 技能差**) | ☐ |
| **V2-S4** | 前端真实历史接管(命中率页/区间聚合接评估层产出) | ☐ |
| **V2-S5** | 延伸多年(机制跑通后,统计意义 + 全周期) | ☐ |

**当前阶段:V1 + V1.5 已落地实现并验证**(纯 Python 管线端到端实跑 DeepSeek + Claude Opus 4.8 + GPT-5.5 **三模型**、
**62** 个离线单测通过、Rust 退役、CI 改 Python、前端按设计 3 页 SPA + 模型切换器/跨模型共识)。V2 设计已成稿,待实现。

## 5. v2 / v3 展望

- **v2 · 报告的预测价值评估**(设计已成稿 → [v2-progress.md](v2-progress.md)):回填 2026 全年报告(=前端真实历史 + 回测语料)→ 结构化判断 → L4 用未来走势打分,关键是**和朴素基准比技能差**。新闻双模式(默认不含 / 可选 GDELT 历史)。机制跑通后延伸多年(Tiingo 长历史)。**不需要 ALFRED**——宏观不进被打分信号即可绕开 vintage。
- **v3 · 评估深化**(仍在宏观轨道内):多 prompt / 多模型质量评测集;若要把**宏观数据本身**放进被回测信号,这时才需 ALFRED vintage;历史新闻规模化(GDELT 多年)。
- **更远(已搁置,保持宏观聚焦)**:多周期报告(周/月/季/年)、A股/港股/个股影响层、CFTC 持仓、FedWatch 隐含概率、Web dashboard —— 见 [docs/parked-scope.md](../parked-scope.md)。

## 6. 技术栈与安全

- **语言**:纯 Python(Rust 退役)。HTTP 用 stdlib `urllib`(沿用旧版,零额外依赖)。
- **新增依赖**:`pandas` / `numpy`(特征计算)、`pyarrow`(parquet)、`pydantic`(边界数据校验)。打破旧版「纯标准库零依赖」——这是本次有意的权衡,CI 需 `pip install`。
- **代码规范**(对齐业内实践):**全量 type hints**;**pydantic 守边界**——环境配置(`.env`)、外部 API 响应解析、LLM 输出校验都用 pydantic 模型(LLM 输出校验顺带把旧版 `{'fact': ...}` 归一化做成 validator);内部值对象用 `dataclass`;数值帧用 `pandas`(不套 pydantic)。
- **本地开发环境**:conda env **`myTools`**(已含 Python 3.11 + pandas 3.0 / numpy 2.4 / pyarrow 24 / pydantic 2.13)。激活:`source /Users/mochi/environment/miniconda3/etc/profile.d/conda.sh && conda activate myTools`。CI 走 `pip install`(锁版本)。
- **存储**:原始序列 → parquet(`data/raw/{latest,history}/`,见 v1-progress §3);对外产物(报告 JSON、`briefs.json`、md)仍走 git-as-database(可 diff、有历史)。
- **密钥**:`FRED_API_KEY` / `TWELVEDATA_API_KEY` / `TIINGO_API_TOKEN` / `DEEPSEEK_API_KEY` 等**仅存 `.env`(已 gitignore),绝不入库、不打印、不写进任何文档**。`.env.example` 只放占位符。
