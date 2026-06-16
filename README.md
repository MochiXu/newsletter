# newsletter — AI 宏观投研助手

面向个人投资者的**研究助手**(research assistant),不是喊单工具。每天自动抓宏观数据、生成
分层的市场简报、把新闻按「事实 / 解读 / 影响资产」分类、并把可证伪的交易假设记下来次日复盘。

> 卖的是**思考框架**,不是信号:严格区分事实与判断、假设必须可证伪、只给「观察点」、
> 不承诺收益。详见 [设计哲学](#设计哲学) 与 [DESIGN.md](DESIGN.md)。

## 现状

| 里程碑 | 内容 | 状态 |
|---|---|---|
| **M0** 数据平面(Rust) | FRED 抓利率/利差/VIX/美元 + Yahoo 补 DXY/黄金 → CSV+markdown | ✅ 已跑通真实数据 |
| **M1** 智能平面(Python) | 数据 + 宏观传导图 → LLM 四层简报 → 存 md + 推飞书 | ✅ 代码就绪(需 LLM key 出 AI 内容) |
| **多模型** | LLM 可插拔:Anthropic / OpenAI / MiniMax / DeepSeek / … | ✅ |
| **M2** | 新闻分类(RSS→事实/解读/影响资产)+ 假设追踪复盘日志 | ✅ |
| M3 / M4 | A股港股、交易框架生成器、CFTC、dashboard、付费墙 | ⏳ 见 [docs/TODO.md](docs/TODO.md) |

**优雅降级**:没有 LLM key 也能跑——产出事实层数据快照 + 原始新闻标题;没有飞书 webhook 就只
存本地 md。配上 key 后自动补齐 AI 四层、新闻分类、假设复盘。

## 架构:Rust + Python 混合

两半**互不直接调用**,只通过共享的数据文件(git-as-database)协作:

```
  FRED / Yahoo ──▶ [ 数据平面 · Rust ] ──▶ data/observations.csv   ← 唯一接缝
                                            data/snapshots/<date>.md
                                                   │
   RSS 新闻 ───────────────────────┐               │ 读
                                   ▼               ▼
                          [ 智能平面 · Python ] ── LLM(provider 可换)
                                   │
                    ┌──────────────┼───────────────────────┐
                    ▼              ▼                        ▼
       data/briefs/<date>.md   data/hypotheses.csv     飞书机器人
       (四层简报+新闻+复盘)    (可证伪假设追踪)        (可选,否则仅存 md)
```

- **数据平面**(`src/*.rs`):可靠的无人值守抓取,编译成二进制,cron 跑。
- **智能平面**(`py/newsletter/`):**纯标准库**,零第三方依赖(`urllib`/`json`/`csv`/`xml`/`hmac`)。
- **接缝**:`data/observations.csv`,不走 FFI/HTTP service。GitHub Actions 临时 runner 上 SQLite
  不持久,所以用 git 当数据库——零基建、天然有历史、diff 可读。

## 目录结构

```
src/                       # 数据平面(Rust)
  main.rs  fred.rs  yahoo.rs  series.rs  store.rs
py/newsletter/             # 智能平面(Python,纯 stdlib)
  data.py                  # 读 observations.csv
  providers.py             # 多模型 provider(Anthropic / OpenAI 兼容)
  llm.py                   # generate_brief 分发
  news.py                  # RSS 抓取 + 分类
  hypotheses.py            # 假设追踪复盘日志
  render.py                # 渲染 markdown / 飞书文本
  brief.py                 # 入口:编排上面所有
  deliver/feishu.py        # 飞书机器人推送
  framework/linkage_map.md # 核心 IP:人工维护的宏观传导图
  tests/test_brief.py      # 26 个离线单测
data/                      # git-as-database
  observations.csv         # 机器可读时序(append/upsert)
  snapshots/<date>.md      # 每日数据快照(人读)
  briefs/<date>.md         # 每日简报(人读)
  hypotheses.csv           # 假设追踪日志
.github/workflows/daily.yml# 每日 cron:抓数 → 简报 → 提交回仓库 →(可选)推飞书
DESIGN.md                  # 高层设计与已锁定决策
docs/                      # 模块文档 + 路线图
```

## 快速开始

### 前置
- Rust toolchain(`cargo`)、`python3`(≥3.10,纯 stdlib 无需 pip 安装)
- 免费 **FRED API key**:https://fred.stlouisfed.org/docs/api/api_key.html
- (可选)任一 **LLM provider key**(Anthropic / OpenAI / MiniMax / …)→ 出 AI 内容
- (可选)**飞书自定义机器人 webhook** → 推送

把配置写进 `.env`(已 gitignore,见 [`.env.example`](.env.example)):
```bash
cp .env.example .env   # 然后填入 FRED_API_KEY 等
```

### M0 数据平面(Rust)
```bash
cargo run --release            # 抓数据 → data/observations.csv + data/snapshots/<date>.md
cargo test                     # 数据平面单测
```

### M1 / M2 智能平面(Python)
```bash
# 先确保 data/observations.csv 已由数据平面生成
PYTHONPATH=py python3 -m newsletter.brief        # 生成简报 → data/briefs/<date>.md(+推飞书)
PYTHONPATH=py python3 -m unittest newsletter.tests.test_brief -v   # 26 个离线单测
```

## 配置(环境变量)

| 变量 | 作用 | 必需 |
|---|---|---|
| `FRED_API_KEY` | FRED 数据(M0) | 是 |
| `LLM_PROVIDER` | 显式选 provider;缺省按存在的 key 自动探测 | 否 |
| `ANTHROPIC_API_KEY` / `ANTHROPIC_MODEL` | Claude(默认 `claude-sonnet-4-6`) | 否 |
| `OPENAI_API_KEY` / `OPENAI_MODEL` | ChatGPT(默认 `gpt-4o-mini`) | 否 |
| `MINIMAX_API_KEY` / `DEEPSEEK_API_KEY` / `MOONSHOT_API_KEY` / `ZHIPU_API_KEY` | OpenAI 兼容端点 | 否 |
| `<NAME>_BASE_URL` / `<NAME>_MODEL` | 覆盖某预设的域名/模型(各家会变) | 否 |
| `LLM_BASE_URL` / `LLM_API_KEY` / `LLM_MODEL` | 任意 OpenAI 兼容端点(`LLM_PROVIDER=openai-compat`) | 否 |
| `FEISHU_WEBHOOK` / `FEISHU_SECRET` | 飞书机器人(签名可选) | 否 |
| `NEWS_DISABLED` | 设为非空则跳过新闻抓取(离线调试) | 否 |

**多模型**:同一份四层 schema(`emit_brief`)适配各家——Anthropic 走 tool use,OpenAI 兼容走
function calling(失败回退解析 JSON)。换模型只改 env,不改代码。

## 自动化(GitHub Actions)

[`daily.yml`](.github/workflows/daily.yml) 每天北京时间 07:00 跑:抓数 → 生成简报 → `git add data/`
提交回仓库 →(配了飞书则)推送。**定时任务只在默认分支生效**,需先把分支合并到 `main`。

在仓库 Settings 配置(都可选,缺了走降级):
- **Secrets**:`FRED_API_KEY`、`ANTHROPIC_API_KEY`(或其他 provider key)、`FEISHU_WEBHOOK`/`FEISHU_SECRET`
- **Variables**:`LLM_PROVIDER`、`ANTHROPIC_MODEL` 等

> commit 步骤带 `if: always()`——即便简报步骤失败,也保证已抓取的数据快照被提交。

## 设计哲学

1. **四层结构**(简报灵魂):事实 / 解读 / 可证伪假设 / 影响观察点。强制区分客观事实与主观判断
   ——这既是差异化,也是合规外衣(做 research 不喊单),还是给 LLM 的缰绳。
2. **宏观传导图**([linkage_map.md](py/newsletter/framework/linkage_map.md)):人工维护的因果/传导
   关系清单,是核心 IP,也是作者学经济的载体。AI 据此推理,作者每天复盘修订。
3. **假设追踪**:每条假设可证伪、带失效条件,次日复盘 held/invalidated/open——信任引擎,
   几乎没人做。
4. **不承诺收益**:只给「观察点」,绝不喊买卖。每篇带免责声明。

## 文档

- [DESIGN.md](DESIGN.md) — 高层设计、四层结构、已锁定决策、里程碑
- [docs/data-plane.md](docs/data-plane.md) — 数据平面(Rust)模块细节
- [docs/intelligence-plane.md](docs/intelligence-plane.md) — 智能平面(Python)模块细节
- [docs/TODO.md](docs/TODO.md) — **详细路线图 / 未来 TODO / 技术债 / 开放问题**

## 免责声明

本项目产出的所有内容均由程序/AI 自动生成,仅为研究框架与观察点,**不构成投资建议,不承诺
任何收益**。投资决策与风险由使用者自行承担。
