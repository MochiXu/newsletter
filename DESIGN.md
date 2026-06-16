# Newsletter — AI 宏观/投研助手 · 设计文档

> 单一事实来源。每次迭代前先读这份;决策变了就改这份。
> 最后敲定:2026-06-16。

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
| Gold | M0:FRED `GOLDAMGBD228NLBM`(伦敦定盘价);后续 Yahoo `GC=F`/Stooq | M0 全走 FRED 省一个源 |
| DXY | Yahoo `DX=F`,或 FRED 贸易加权美元 `DTWEXBGS` 代理 | ICE 官方收费,用代理并注明口径 |
| FedWatch | 自己从 30 天联邦基金期货 `ZQ` 算隐含概率 | 无干净免费 API;自己算=最好的学习项目,Phase 2 |
| CFTC 持仓 (COT) | CFTC Socrata API | 免费,每周五发布(周二数据) |
| ETF flow | 无统一免费 API;加密 ETF 用 Farside | 往后放 |
| 新闻 | RSS(各央行/媒体) + GDELT(免费) | 分类功能输入 |

## 6. 架构(Rust + Python 混合,各扬所长)

清晰的接缝是关键:两半**互不直接调用**,只通过共享 SQLite 数据库这一个契约协作。

| 平面 | 语言 | 负责 |
|---|---|---|
| 数据平面 | **Rust** | fetchers(FRED/Stooq/CFTC/RSS)、并发抓取、写 SQLite;编译成二进制,cron 跑,无人值守可靠 |
| 智能平面 | **Python** | 读数据(M1 读 CSV)+ linkage map → 调 Claude(tool use 强制四层)→ 渲染 markdown → 存 md + 推飞书 |
| 接缝 | **SQLite `data/brief.db` + `schema.sql`** | 唯一契约;**不走 FFI/PyO3,不走 HTTP service** |

- **Rust**:`reqwest`+`tokio` 抓取,`sqlx`(编译期校验 SQL)写库;数据源全走 FRED+Stooq+Socrata,避开 yfinance 的接口漂移
- **Python**:**纯 stdlib**(`urllib`/`json`/`csv`/`hmac`/`xml`,零第三方);LLM 走统一 `call_structured`(Anthropic tool use / OpenAI 兼容 function calling),`framework/linkage_map.md` 运行时读取
- **模型**:**provider 可插拔**(Anthropic / OpenAI / MiniMax / DeepSeek 等);默认 `claude-sonnet-4-6`,深度 `claude-opus-4-8`
- **调度**:**GitHub Actions cron**,顺序跑 `cargo run --release`(Rust 抓数)→ `python -m newsletter.brief`(读数据→Claude→渲染→存/推)
- **交付**:Python 推**飞书机器人**(始终先存本地 md 兜底);Telegram/邮件后续再加,交互式 bot 可再用 Rust `teloxide`
- **配置**:`.env`(API keys)

**为什么这个接缝好**:流程是线性的一次交接(Rust 写库 → Python 读库),没有进程内调用所以不需要 FFI/maturin 的构建复杂度;而且本地迭代 prompt 时**只跑 Python 半边**、读上次 Rust 落的库快照——既拿到 Rust 的无人值守可靠性,又保住 Python 改 prompt 即时见效的内循环。

建议仓库结构(复用现有的根 `Cargo.toml`/`src/` 作为数据平面):
```
newsletter/
  Cargo.toml                   # Rust crate:数据平面(复用现有)
  src/                         # Rust fetch 二进制
    main.rs
    sources/ (fred.rs, stooq.rs, cftc.rs, rss.rs)
    store.rs
  schema.sql                   # 共享契约:SQLite 表定义(两边都读)
  pyproject.toml               # Python 包:智能平面
  py/newsletter/
    framework/
      linkage_map.md           # IP:人工维护的宏观传导图
      schema.py                # 四层 pydantic 模型
    brief.py                   # 读库 -> 调 Claude -> 渲染
    render.py
    deliver/feishu.py
  prompts/                     # prompt 模板(运行时读,不重编译)
  data/brief.db                # 接缝(.gitignore)
  .github/workflows/daily.yml  # cargo run --release && python -m newsletter.brief
```

> **M0 现状(2026-06-16,代码已落地)**:数据平面用 `reqwest` blocking 抓 6 个 FRED 序列,存为 CSV + markdown 提交回仓库(GitHub Actions 临时 runner 上 SQLite 不持久 → M0 用 git-as-database,SQLite 接缝待 M1);单测覆盖解析与落库。**另加 Yahoo 免鉴权回退源**:在无有效 FRED key 时也用真实数据(S&P/VIX/10Y/DXY/Gold)跑通了管道并提交首个快照。详见 [docs/data-plane.md](docs/data-plane.md)。

> **M1 现状(2026-06-16,代码已就绪)**:智能平面(Python,纯 stdlib)读 `observations.csv` + 传导图 → Claude `emit_brief` 工具强制四层(事实/解读/可证伪假设/影响)→ 存 `data/briefs/<date>.md` + 推飞书。已用真实 M0 数据跑通**回退路径**(无 ANTHROPIC_API_KEY → 仅事实层;无 FEISHU_WEBHOOK → 仅存 md);6 单测过。完整 AI 四层待填 `ANTHROPIC_API_KEY`。详见 [docs/intelligence-plane.md](docs/intelligence-plane.md)。

> **M2 现状(2026-06-16,代码已就绪)**:新闻分类(`news.py`,stdlib RSS+Atom,已实测抓取真实新闻)+ 假设追踪复盘日志(`hypotheses.py`,git-as-database `hypotheses.csv`)接进简报;无 LLM key 时新闻仍展示原始标题。LLM 层已重构为**多 provider 可插拔**(Anthropic/OpenAI/MiniMax 等)。21 单测过。详见 [docs/intelligence-plane.md](docs/intelligence-plane.md)。

## 7. 里程碑

- **M0 · 本周**(✅ 已跑通真实数据)— 数据管道打通。拉 6 个核心数据(10Y/2Y/2s10s/VIX/USD/Gold,FRED 主源 + Yahoo 补 DXY/黄金),存为 CSV + markdown 提交回仓库。
- **M1 · 第 2-3 周**(代码已就绪)— 每日四层简报(只给作者)。Python 读数据 + linkage map → Claude 四层简报 → 存本地 md + 推**飞书机器人**(无 key 降级仅事实层;无 webhook 仅存 md)。✅ 验收:作者每天真读、觉得比刷推特信息量大(待填 ANTHROPIC_API_KEY 出完整四层)。
- **M2 · 第 4-6 周**(代码已就绪)— 新闻分类(RSS → 事实/解读/影响资产)+ 假设追踪复盘日志(可证伪假设次日复盘 held/invalidated/open),均接进每日简报。发给朋友收反馈待 LLM key 跑出完整内容。
- **M3 · 第 2 月** — 接入 A股/港股影响层;固定格式/时间/voice。
- **M4 · 第 3 月+** — 单资产交易框架生成器、CFTC、dashboard;考虑公开 + 付费墙(¥99-299/月)。

**纪律:变现排在最后。** 先用免费受众证明留存,再建支付。当前阶段 = 自用,无支付/无 dashboard 基建。

## 8. 已锁定决策(2026-06-16)

1. 首要目标:**先自用 2-3 个月再公开**(dogfood-first)
2. 关注市场:全球宏观 + 美股 + 加密 + A股/港股(分批,见 §4)
3. 技术栈:**Rust + Python 混合**——Rust 数据平面 + Python 智能平面,接缝为共享 SQLite(见 §6;现有 Rust 骨架复用)
4. 首发交付:**飞书机器人 webhook**(始终存本地 md 兜底;Telegram 暂不可用,后续再加)

## 9. 待定 / Open questions

- FRED API key、Telegram Bot token 的获取
- linkage map 初版由谁写第一版规则(作者口述 + AI 整理?)
- 日报里"偏离预期"需要 consensus 数据(经济日历预期值)——来源待定
