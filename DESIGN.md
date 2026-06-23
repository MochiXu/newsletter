# Newsletter — AI 宏观/投研助手 · 设计文档

> 高层单一事实来源:**愿景 / 产品灵魂 / 已锁定决策**。每次迭代前先读这份;决策变了就改这份。
> 最后敲定:2026-06-16(架构层 2026-06-18 随 V1 重构更新)。
>
> 后端自 **2026-06-18** 起已**推平为纯 Python**(Rust 数据平面退役),核心是
> 「**代码算技术特征 → LLM 只解释**」的强制分层 + 多数据源(FRED/TwelveData/Tiingo/Yahoo)+
> parquet 原始层。**架构与分步进度以 [docs/refactor/](docs/refactor/readme.md) 为准**;本文件聚焦愿景与决策。

## 1. 愿景与定位

面向个人投资者(首先是作者本人)的 **research assistant**,不是喊单工具。

核心信念:
- **护城河不是数据也不是 AI,是「一致、可证伪的解读框架」+ 作者公开打磨它的过程。**
- 市场缺的不是新闻,是 **"哪些数据真的重要,以及它如何改变交易假设"**。
- 作者无金融背景、目前靠情绪交易 → 这个工具同时是"学经济学/投资"的载体。"看一个人用系统化方法从零学懂市场"本身就是内容资产。

合规底线:用"观察点/假设"措辞,**绝不**说买/卖;不承诺收益;不代客理财;每篇带免责声明。四层结构本身就是合规外衣——卖的是思考框架,不是信号。

## 2. 产品灵魂:四层结构

每日简报强制分四层(也是数据结构和 prompt 的骨架):

| 层 | 内容 | 纪律 |
|---|---|---|
| 事实层 Facts | 今天的数据/事件 | 每条可溯源到具体数据点,纯客观 |
| 解读层 Interpretation | 现在处于什么 regime、偏离预期多少 | 明确标注"这是判断不是事实" |
| 假设层 Hypotheses | 可证伪命题:"若 X 则预期 Y,失效条件 Z" | 必须能被明天的数据打脸 |
| 影响层 Impact | 对关注资产意味着什么**观察点** | 是观察点,不是买卖指令 |

**假设追踪日志**(M2):记录昨天的假设今天是否成立。几乎没人做——这是信任引擎,也是作者复盘学习的核心。

## 3. 真正的 IP:宏观传导图 (linkage map)

一份人工维护的 markdown,写明宏观传导关系,AI 基于它推理,作者每天复盘修订。
飞轮:**学到 → 编码进图 → AI 应用 → 复盘 → 修订**。

种子规则示例:
- `DXY ↑` → 黄金、新兴市场、大宗承压;美股科技相对受益于实际利率而非 DXY 本身
- `2s10s 走陡(熊陡)` → 警惕通胀/期限溢价;走陡(牛陡)常伴降息预期
- `VIX > 20 且上行` → risk-off,关注信用利差与美元避险买盘
- `实际利率(10Y TIPS)↑` → 黄金最大逆风
- `FedWatch 隐含降息概率骤变` → 重定价利率敏感资产(成长股、黄金、长债)

## 4. 关注市场(当前聚焦宏观)

**当前 scope = 全球宏观分析**:利率/美元/黄金/波动率 + 美股指数(作宏观风险温度计)。
多市场扩展(A股/港股、个股、加密影响层)**刻意搁置**,避免项目摊大成量化平台——
见 [docs/parked-scope.md](docs/parked-scope.md)。

时区:发布档口 = **北京时间早上 7-8 点**,总结隔夜美国 session,给亚洲盘做 pre-market。

## 5. 数据源

> V1 已接入的「强强联合」分工(实测各家免费档能力后定;机读版在 `catalog.py`,
> 完整说明见 [docs/refactor/readme.md](docs/refactor/readme.md) §3)。

| 逻辑指标 | 主源 | 备份 / 代理 | 备注 |
|---|---|---|---|
| 利率 2Y/10Y、2s10s、实际利率 DFII10、通胀预期 T10YIE、广义美元 DTWEXBGS、VIX、月频宏观(CPI/失业/非农/FFR) | **FRED** | — | 权威、免费、无硬限额 |
| 黄金 | **Twelve Data `XAU/USD`**(现货) | Tiingo `GLD` / Yahoo `GC=F` | 真现货、无分红回溯调整;FRED 无可用金价序列 |
| 窄口径美元(DXY 代理) | **Tiingo `UUP`** | — | 免费档均无真 DXY;UUP 作代理,**只比收益率/趋势/标准化,不取绝对价位** |
| 股指长历史(回测用,V2) | **Tiingo `SPY`/`QQQ`** | FRED `SP500`/`NASDAQCOM` | FRED SP500 仅 2016+;SPY 回到 1993、QQQ 回到 1999 |
| 新闻 | RSS(央行/财经媒体) | (V2 可选 GDELT 补历史) | 分类功能输入 |
| FedWatch / CFTC 持仓(COT) / ETF flow | (未接入) | — | 未来扩展,见 §7 M4 与 [docs/TODO.md](docs/TODO.md) |

## 6. 架构:纯 Python 数据管线

> 2026-06-18 起后端推平为**纯 Python**(Rust 数据平面退役)。下文为重构后的现状;
> 完整设计与分步进度见 [docs/refactor/](docs/refactor/readme.md),目录结构见 [README.md](README.md#目录结构)。

强制分层,**代码算数字、LLM 只解释**;层间通过共享数据文件协作(git-as-database),
**不走 FFI / 进程内调用 / HTTP service**:

| 层 | 模块 | 负责 |
|---|---|---|
| 数据采集 | `sources/` + `catalog.py` | FRED/TwelveData/Tiingo/Yahoo 适配器 + 观察集主源/兜底链 → 统一 tidy 序列 |
| 原始存储 | `store.py` | parquet 原始层:`data/raw/latest`(全量快照,每日重拉覆盖)+ `history` 归档(point-in-time) |
| 特征 | `features.py` / `regime.py` | pandas 算技术特征(滚动=因果)+ 代码派生 regime 标签 |
| 智能 | `llm/` | 算好的特征块 + 宏观传导图 → 多 provider LLM 强制四层(pydantic 守边界、归一化) |
| 渲染 / 交付 | `render.py` / `deliver/feishu.py` | LLM 输出 → 前端 JSON / markdown / 飞书文本 |
| 编排 | `pipeline.py` / `__main__.py` | fetch→store→features→regime→llm→render→输出;`target_date` 贯穿(为 V2 回填就位) |

- **强制分层是质量的最大杠杆**:数字全由代码算成技术特征,LLM 只判断/解释、不再「心算」。
  任一 LLM 环节失败都 `try/except` 降级,报告仍能基于已算好的特征层产出。
- **接缝(当前契约)**:原始层 `data/raw/latest/series.parquet`(可重建缓存)+ 对外产物
  `data/briefs/<date>.{md,json}`、聚合 `data/briefs.json`(前端 fetch)、`data/hypotheses.csv`
  (假设追踪)——产物走 git,可 diff、有历史。
- **依赖**:`pandas`/`numpy`(特征)、`pyarrow`(parquet)、`pydantic`(边界校验);LLM provider 层仍是纯 `urllib`。
- **模型**:**provider 可插拔**(Anthropic / OpenAI / MiniMax / DeepSeek / Moonshot / Zhipu / 通用 openai-compat),
  换 env 不改码(`LLM_MODELS` 逗号列表选模型)。当前活跃 = **DeepSeek + Claude(claude-opus-4-8)+ OpenAI(gpt-5.5)三模型并行**(经中转站),收敛靠**代码级共识**、不靠 LLM。
- **多模型契约**:`Brief` = 脊柱(模型无关:metrics/signals/regime/priceSeries/news/reviews)+ `views{modelId: ModelView}`(随模型变的六层)+ `consensus`(对固定 roster 跨模型纯代码投票;<2 模型为空)。
- **调度**:**GitHub Actions cron**(北京 07:00)单步 `PYTHONPATH=py python -m newsletter` → `git add data/`
  提交回仓库 →(配了飞书则)推送。密钥缺失自动降级,不让 CI 失败。
- **配置**:`.env`(四家 key + 可选 LLM/飞书),已 gitignore。

> **里程碑现状**:M0 数据采集 / M1 四层简报 / M2 新闻+假设追踪 均已落地并实跑(V1.5 起为 DeepSeek + Claude + GPT 三模型并行 + 代码级共识);
> V1「数据质量重构」(纯 Python 分层 + 多源 + parquet + 代码算特征)已完成并验证。
> 进度总表见 [docs/refactor/readme.md](docs/refactor/readme.md) §4;V2(回填 + 预测价值评估)设计见
> [v2-progress](docs/refactor/v2-progress.md);完整时间线见 [docs/CHANGELOG.md](docs/CHANGELOG.md)。

## 7. 进度与路线

> 早期 M0/M1/M2 建设阶段(数据采集 / 四层简报 / 新闻+假设追踪)的历史时间线见
> [docs/CHANGELOG.md](docs/CHANGELOG.md);数据质量重构(V1/V2)的分步进度见 [docs/refactor/](docs/refactor/readme.md)。

- **已完成**:全球宏观脊柱数据采集 + 每日四层简报 + 新闻分类 + 假设追踪复盘;
  **V1 数据质量重构**(纯 Python 分层 + 多源 + parquet + 代码算特征)已落地并验证(DeepSeek 实跑)。
- **进行中规划**:**V2 — 报告的预测价值评估**(回填历史报告 + 结构化判断 + 用未来走势打分,关键是
  vs naive baseline 的技能差),见 [v2-progress](docs/refactor/v2-progress.md)。
- **近期重心**:dogfood 自用 + 每天维护 linkage map + prompt/内容打磨 + 固定格式/voice。
- **搁置(保持宏观聚焦)**:A股/港股、个股、加密影响层、CFTC、FedWatch、dashboard 等多市场/进阶扩展
  ——见 [docs/parked-scope.md](docs/parked-scope.md)。

> 详细待办与技术债见 [docs/TODO.md](docs/TODO.md);项目总览见 [README.md](README.md)。

**纪律:变现排在最后。** 先用免费受众证明留存,再建支付。当前阶段 = 自用,无支付/无 dashboard 基建。

## 8. 已锁定决策(2026-06-16)

1. 首要目标:**先自用 2-3 个月再公开**(dogfood-first)
2. 关注市场:**当前聚焦全球宏观**(利率/美元/黄金/波动率 + 美股指数);多市场扩展搁置,见 [docs/parked-scope.md](docs/parked-scope.md)
3. 技术栈:**纯 Python 数据管线**(V1 重构后 Rust 数据平面已退役);接缝为 parquet 原始层 + JSON/md 对外产物(git-as-database)
4. 首发交付:**飞书机器人 webhook**(始终存本地 md 兜底;Telegram 暂不可用,后续再加)

## 9. 待定 / Open questions

- Telegram Bot token 的获取(非首发渠道)
- linkage map 初版由谁写第一版规则(作者口述 + AI 整理?)
- 日报里"偏离预期"需要 consensus 数据(经济日历预期值)——来源待定
