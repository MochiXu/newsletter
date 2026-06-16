# 模块文档 · 智能平面(Python)

> 对应 [DESIGN.md](../DESIGN.md) §6 的「智能平面」。本文件记录 M1 的实现细节。

## 职责

读取数据平面产出(`data/observations.csv`)→ 结合宏观传导图 → 调 Claude 生成**四层简报**
→ 渲染 markdown → 存本地 + 推飞书。

## 设计取舍:纯标准库,零第三方依赖

只用 `urllib`/`json`/`csv`/`hmac`/`hashlib` 等 stdlib——不引入 `anthropic` SDK / `pydantic` /
`requests`。理由:任何有 python3 的机器/CI 都能直接跑,免去 venv/pip 安装的脆弱性;此项目
瓶颈在 prompt 与框架迭代,不在库生态。后续若需要可再换官方 SDK。

## 数据流

```
data/observations.csv ──(data.load_latest)──▶ 最新 run_date 的观测
                                                    │
              framework/linkage_map.md ─────────────┤
                                                    ▼
                                       llm.generate_brief(data, linkage)
                                          │            │
                       有 ANTHROPIC_API_KEY            无 key / 调用失败
                                          ▼            ▼
                              四层结构化简报          None(仅事实层)
                                          └──────┬─────┘
                                                 ▼
                          render.render_markdown / render_text
                                                 │
                        ┌────────────────────────┼─────────────────────┐
                        ▼                                               ▼
            data/briefs/<run_date>.md(始终存,git-as-database)   deliver.feishu.push_text
                                                                  (配了 FEISHU_WEBHOOK 才推)
```

## 四层结构(产品灵魂)

`llm.py` 用 **tool use 强制结构化输出**(工具 `emit_brief`,`tool_choice` 锁定该工具):

| 层 | 字段 | 纪律 |
|---|---|---|
| 事实层 | `facts[]` | 只复述数据,不加判断 |
| 解读层 | `interpretation[]` | regime/偏离含义,标注为判断 |
| 假设层 | `hypotheses[]`(`if_then`+`invalidation`) | 可证伪,必带失效条件 |
| 影响层 | `impact[]`(`asset`+`watch`) | 观察点,**非买卖建议** |

外加 `headline` 一句话总览。system prompt 写死纪律:区分事实/判断、假设可证伪、只给观察点、
不承诺收益、中文输出。

## LLM provider(可换模型,`providers.py`)

底层大模型**可插拔**——同一份四层 schema(`emit_brief`)适配不同家:

| provider | 端点 / 机制 | key |
|---|---|---|
| `anthropic` | Messages API + tool use(`tool_choice` 强制 emit_brief) | `ANTHROPIC_API_KEY` |
| `openai` | Chat Completions + function calling | `OPENAI_API_KEY` |
| `minimax`/`deepseek`/`moonshot`/`zhipu` | OpenAI 兼容端点(预设 base_url) | 各自 `*_API_KEY` |
| `openai-compat` | 任意 OpenAI 兼容端点 | `LLM_BASE_URL`+`LLM_API_KEY`+`LLM_MODEL` |

- **选择**:`LLM_PROVIDER` 显式;缺省按存在的 key 自动探测(anthropic>openai>minimax>…)
- **结构化输出**:Anthropic 走 tool use 读 `tool_use.input`;OpenAI 兼容走 function calling 读
  `tool_calls[0].function.arguments`,无 tool_calls 时回退 `_extract_json(content)`
- **模型名**用 `<PREFIX>_MODEL` 或 `LLM_MODEL` 覆盖(预设默认可能随各家目录更新)
- `llm.generate_brief()` 只调 `select_provider()`;无任何 key → 返回 None → 仅事实层

## 交付:飞书机器人(`deliver/feishu.py`)

- 自定义机器人 webhook,`msg_type=text`
- `FEISHU_SECRET` 存在时按飞书算法签名(HMAC-SHA256,`{timestamp}\n{secret}` 为 key)
- **始终先把简报存 `data/briefs/<run_date>.md`**(本地兜底);配了 `FEISHU_WEBHOOK` 才额外推送
- Telegram/邮件后续再加

## M2:新闻分类 + 假设追踪

**新闻分类(`news.py`)** —— 用户最初要的核心功能之一。
- stdlib `urllib`+`xml.etree` 抓取/解析 RSS+Atom(`DEFAULT_FEEDS`:Fed/CNBC/MarketWatch,可覆盖;单源失败静默跳过)
- `classify()` 用 provider 的 `call_structured` 把每条分为「事实 / 解读 / 事实+解读 / 噪音」+ 受影响资产 + 方向性影响
- **对齐靠 `index`(非标题)**:让模型回填我们给的序号,`_merge_news` 按序号贴回原始新闻。
  早期按标题对齐,但 DeepSeek 等会把英文标题翻译成中文 → 零匹配、全退化为未分类;index 对翻译
  免疫,且因模型显式回填(非位置推断),漏条/乱序也不会张冠李戴。
- 无 LLM provider → 简报里仍展示原始新闻标题(未分类)
- 注:抓取放在 Python(与 LLM 分类紧耦合);DESIGN 原设想 Rust RSS,量大后再迁移

**假设追踪日志(`hypotheses.py`)** —— 信任 / 学习引擎,几乎没人做。
- 简报产出的可证伪假设记进 `data/hypotheses.csv`(列:`created_date/if_then/invalidation/status/resolved_date/verdict/note`)
- `record_new` **按天幂等**:`run_date` 已记录过则整体跳过(与 `observations.csv` 一致)。
  原因:LLM(temperature>0)每次措辞略不同,靠 if_then 原文去重挡不住同日重跑的近似重复。
- 复盘只针对**往日**的 open 假设(`brief.py` 过滤掉 `created_date == run_date`):今日假设不拿
  今天数据自我验证(循环论证),次日起才复盘——与 DESIGN「次日起复盘」一致。
- `review()` 用 LLM 对照最新数据判定每条 held/invalidated/open,`apply_reviews()` 按序号写回日志
- 简报新增「假设复盘」节(✅ 已兑现 / ❌ 已失效 / ⏳ 待观察)

编排(`brief.py`):四层简报 → 复盘历史假设 + 登记今日假设 → 抓取并分类新闻 → 渲染(数据 + 四层 + 假设复盘 + 新闻)→ 存 md + 推飞书。

## 运行

```bash
# 仓库根目录;先确保 data/observations.csv 已由数据平面生成
PYTHONPATH=py python3 -m newsletter.brief
PYTHONPATH=py python3 -m unittest newsletter.tests.test_brief -v   # 离线单测
```

环境变量(均可选,见 `.env.example`):`ANTHROPIC_API_KEY`、`ANTHROPIC_MODEL`、
`FEISHU_WEBHOOK`、`FEISHU_SECRET`。

> **`.env` 自动加载**:Python 侧没有 Rust 的 `dotenvy`,故 `brief.py` 启动时用 `config.load_dotenv`
> 读仓库根的 `.env`(纯 stdlib;**不覆盖**已存在的 shell 变量,与 dotenvy 行为一致)。所以把 key
> 写进 `.env` 即可,无需 `export`。CI 里走 GitHub Secrets 注入的真实环境变量,`.env` 不存在则跳过。

## 优雅降级

- 无 `ANTHROPIC_API_KEY`(或 LLM 调用异常)→ 只产出事实层简报,并在正文标注「配置后自动生成 AI 层」
- 无 `FEISHU_WEBHOOK` → 跳过推送,本地 md 即交付物
- 无数据 → 退出码 1,提示先跑数据平面

## 待办 / 后续

> 全局路线 / 技术债 / 开放问题见 [TODO.md](TODO.md)。

- [x] M2:新闻分类(`news.py`)+ 假设追踪复盘日志(`hypotheses.py`)
- [x] 配 provider key 跑出完整四层简报 + 新闻分类 + 假设复盘(**已用 DeepSeek 实跑验证**)
- [ ] 其余 provider(Anthropic/OpenAI/MiniMax/…)各自冒烟一次
- [ ] 配飞书机器人(webhook + 可选签名)跑通推送
- [ ] M3:接入 A股/港股影响层
- [ ] 飞书 text → 富文本卡片(lark_md)
- [ ] RSS 抓取量大后迁到 Rust 数据平面;引入 SQLite 接缝
