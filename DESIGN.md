# Newsletter — AI 宏观/投研助手 · 设计文档

> 单一事实来源。每次迭代前先读这份;决策变了就改这份。
> 最后敲定:2026-06-16。
>
> **⚠️ 2026-06-18 架构更新**:后端已**推平为纯 Python**(Rust 数据平面退役),引入
> 「**代码算技术特征 → LLM 只解释**」的强制分层 + 新数据源(TwelveData/Tiingo)+ parquet 原始层。
> 愿景/四层结构/设计哲学仍然有效;**技术栈与「数据平面=Rust」部分已被取代**,以
> [docs/refactor/](docs/refactor/readme.md) 为准。

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

## 4. 关注市场与排期(全部在 scope,但分批接入)

宏观是脊柱,四个市场是"影响层"目标,分批接:
- **M1**:只做全球宏观脊柱(利率/美元/黄金/波动率)
- **M2**:接入美股指数/个股 + 加密(BTC/ETH)的影响映射
- **M3**:接入 A股/港股(数据源、时区、合规口径不同,单独处理)

时区:发布档口 = **北京时间早上 7-8 点**,总结隔夜美国 session,给亚洲盘做 pre-market。

## 5. 数据源

| 数据 | 来源 | 备注 |
|---|---|---|
| 10Y / 2Y / 2s10s | FRED `DGS10`/`DGS2`/`T10Y2Y` | 免费 API key,每日,最稳,优先 |
| VIX | FRED `VIXCLS` 或 Yahoo `^VIX` | 免费 |
| Gold | Yahoo `GC=F` | COMEX front futures;FRED 伦敦金价序列已下架,后续可换更贴盘口/更稳定源 |
| DXY | Yahoo `DX-Y.NYB` + FRED `DTWEXBGS` | `DX-Y.NYB` 是用户口径的 ICE 窄口径 DXY 代理;`DTWEXBGS` 是贸易加权广义美元,两者并列展示且不混用 |
| FedWatch | 自己从 30 天联邦基金期货 `ZQ` 算隐含概率 | 无干净免费 API;自己算=最好的学习项目,Phase 2 |
| CFTC 持仓 (COT) | CFTC Socrata API | 免费,每周五发布(周二数据) |
| ETF flow | 无统一免费 API;加密 ETF 用 Farside | 往后放 |
| 新闻 | RSS(各央行/媒体) + GDELT(免费) | 分类功能输入 |

## 6. 架构(Rust + Python 混合,各扬所长)

清晰的接缝是关键:两半**互不直接调用**,当前只通过共享数据文件协作。SQLite 是未来在数据量/查询复杂度上来后的迁移目标,不是当前契约。

| 平面 | 语言 | 负责 |
|---|---|---|
| 数据平面 | **Rust** | fetchers(FRED/Yahoo;后续 CFTC/FedWatch/A股港股等)、写 `data/observations.csv` + `data/snapshots/<date>.md`;编译成二进制,cron 跑,无人值守可靠 |
| 智能平面 | **Python** | 读 CSV + linkage map → 多 provider LLM 强制四层 → 渲染 markdown / JSON → 存本地 + 推飞书 |
| 接缝 | **CSV / Markdown / JSON 数据文件** | 当前契约:`observations.csv`、`briefs/<date>.md|json`、`briefs.json`、`hypotheses.csv`;**不走 FFI/PyO3,不走 HTTP service** |

- **Rust**:`reqwest` blocking 抓取,FRED 为权威主源,Yahoo 作为 DXY/黄金补充与 FRED 全失败时的降级源;序列增多后再切 `tokio` 并发
- **Python**:**纯 stdlib**(`urllib`/`json`/`csv`/`hmac`/`xml`,零第三方);LLM 走统一 `call_structured`(Anthropic tool use / OpenAI 兼容 function calling),`framework/linkage_map.md` 运行时读取
- **模型**:**provider 可插拔**(Anthropic / OpenAI / MiniMax / DeepSeek 等);默认 `claude-sonnet-4-6`,深度 `claude-opus-4-8`
- **调度**:**GitHub Actions cron**,顺序跑 `cargo run --release`(Rust 抓数)→ `python -m newsletter.brief`(读数据→Claude→渲染→存/推)
- **交付**:Python 推**飞书机器人**(始终先存本地 md 兜底);Telegram/邮件后续再加,交互式 bot 可再用 Rust `teloxide`
- **配置**:`.env`(API keys)

**为什么这个接缝好**:流程是线性的一次交接(Rust 写文件 → Python 读文件),没有进程内调用所以不需要 FFI/maturin 的构建复杂度;而且本地迭代 prompt 时**只跑 Python 半边**、读上次 Rust 落的快照——既拿到 Rust 的无人值守可靠性,又保住 Python 改 prompt 即时见效的内循环。GitHub Actions 临时 runner 上 SQLite 文件本身不持久,把数据提交回仓库更适合当前阶段;等需要复杂历史查询、rolling feature、跨表 join 时,再从 CSV 重建/引入 SQLite 或 DuckDB。

建议仓库结构(复用现有的根 `Cargo.toml`/`src/` 作为数据平面):
```
newsletter/
  Cargo.toml                   # Rust crate:数据平面(复用现有)
  src/                         # Rust fetch 二进制
    main.rs
    sources/ (fred.rs, stooq.rs, cftc.rs, rss.rs)
    store.rs

  py/newsletter/
    framework/
      linkage_map.md           # IP:人工维护的宏观传导图
    brief.py                   # 读 CSV -> 调 LLM -> 渲染 Markdown/JSON
    render.py
    deliver/feishu.py
  data/observations.csv        # Rust → Python 的事实数据接缝(git-as-database)
  data/briefs.json             # Python → Frontend 的展示接缝
  .github/workflows/daily.yml  # cargo run --release && python -m newsletter.brief
```

> **M0 现状(2026-06-17,代码已落地)**:数据平面用 `reqwest` blocking 抓 FRED 核心序列(10Y/2Y/2s10s/VIX/广义美元),并用 Yahoo 补 DXY/黄金;存为 CSV + markdown 提交回仓库(GitHub Actions 临时 runner 上 SQLite 不持久 → 当前用 git-as-database,SQLite/DuckDB 待复杂查询时再引入)。单测覆盖解析、落库、新鲜度与 api_key 不泄漏。详见 [docs/data-plane.md](docs/data-plane.md)。

> **M1 现状(2026-06-17,代码已就绪并实跑)**:智能平面(Python,纯 stdlib)读 `observations.csv` + 传导图 → 多 provider LLM `emit_brief` 强制四层(事实/解读/可证伪假设/影响,含 `tone` 与 impact `direction`)→ 存 `data/briefs/<date>.md|json` + 增量维护 `data/briefs.json` + 推飞书。无 key / webhook 时优雅降级。详见 [docs/intelligence-plane.md](docs/intelligence-plane.md)。

> **M2 现状(2026-06-17,代码已就绪并实跑)**:新闻分类(`news.py`,stdlib RSS+Atom)+ 假设追踪复盘日志(`hypotheses.py`,git-as-database `hypotheses.csv`)接进简报;新闻与假设复盘均用 `index` 对齐,避免 LLM 改写标题/假设文本导致错配。无 LLM key 时新闻仍展示原始标题。详见 [docs/intelligence-plane.md](docs/intelligence-plane.md)。

## 7. 里程碑

- **M0 · 本周**(✅ 已跑通真实数据)— 数据管道打通。拉 6 个核心数据(10Y/2Y/2s10s/VIX/USD/Gold,FRED 主源 + Yahoo 补 DXY/黄金),存为 CSV + markdown 提交回仓库。
- **M1 · 第 2-3 周**(✅ 已用 DeepSeek 跑通)— 每日四层简报(只给作者)。Python 读数据 + linkage map → LLM 四层简报 → 存本地 md/json + 推**飞书机器人**(无 key 降级仅事实层;无 webhook 仅存 md)。
- **M2 · 第 4-6 周**(✅ 已用 DeepSeek 跑通)— 新闻分类(RSS → 事实/解读/影响资产)+ 假设追踪复盘日志(可证伪假设次日复盘 held/invalidated/open),均接进每日简报。
- **M3 · 第 2 月** — 接入 A股/港股影响层;固定格式/时间/voice。
- **M4 · 第 3 月+** — 单资产交易框架生成器、CFTC、dashboard;考虑公开 + 付费墙(¥99-299/月)。

> 详细的未来任务、技术债与开放问题见 [docs/TODO.md](docs/TODO.md);项目总览见 [README.md](README.md)。

**纪律:变现排在最后。** 先用免费受众证明留存,再建支付。当前阶段 = 自用,无支付/无 dashboard 基建。

## 8. 已锁定决策(2026-06-16)

1. 首要目标:**先自用 2-3 个月再公开**(dogfood-first)
2. 关注市场:全球宏观 + 美股 + 加密 + A股/港股(分批,见 §4)
3. 技术栈:**Rust + Python 混合**——Rust 数据平面 + Python 智能平面;当前接缝为 CSV/Markdown/JSON 数据文件(git-as-database),复杂查询阶段再迁移 SQLite/DuckDB
4. 首发交付:**飞书机器人 webhook**(始终存本地 md 兜底;Telegram 暂不可用,后续再加)

## 9. 待定 / Open questions

- Telegram Bot token 的获取(非首发渠道)
- linkage map 初版由谁写第一版规则(作者口述 + AI 整理?)
- 日报里"偏离预期"需要 consensus 数据(经济日历预期值)——来源待定
