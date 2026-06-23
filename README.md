# newsletter — AI 宏观投研助手

面向个人投资者的**研究助手**(research assistant),不是喊单工具。每天自动抓宏观数据、
**用代码算技术特征**、生成分层的市场简报、把新闻按「事实 / 解读 / 影响资产」分类、并把
可证伪的交易假设记下来次日复盘。

> 卖的是**思考框架**,不是信号:严格区分事实与判断、假设必须可证伪、只给「观察点」、
> 不承诺收益。详见 [设计哲学](#设计哲学) 与 [DESIGN.md](DESIGN.md)。

> **重构进行中(V1 已落地)**:后端已**推平为纯 Python**,核心是「**代码算特征 → LLM 只解释**」
> 的强制分层。设计与进度见 [docs/refactor/](docs/refactor/readme.md)。

## 现状

| 里程碑 | 内容 | 状态 |
|---|---|---|
| **数据平面**(Python) | FRED + Twelve Data(金现货)+ Tiingo(美元代理/长历史)+ Yahoo 兜底 → parquet | ✅ |
| **特征层** | pandas 算趋势/动量/波动/利率·通胀/美元/跨资产相关/极值(因果滚动,不偷看未来) | ✅ |
| **智能平面** | 特征 + 宏观传导图 → LLM 四层简报(事实/解读/假设/影响)→ md + briefs.json + 飞书 | ✅(DeepSeek 实跑) |
| **多模型** | LLM 可插拔:Anthropic / OpenAI / MiniMax / DeepSeek / …(换 env 不改码) | ✅ |
| **新闻 + 假设追踪** | RSS → 事实/解读/影响资产分类 + 可证伪假设次日复盘 | ✅ |
| **展示平面**(前端) | React「暖纸小票」阅读器:JSON 接缝 + 明暗主题 + 时间线 + 四层/复盘/新闻 | ✅(读 briefs.json) |
| **V2** | 历史回填 + 结构化判断 + **预测价值评估**(vs baseline) | ⏳ [v2-progress](docs/refactor/v2-progress.md) |

**优雅降级**:任一数据源失败走兜底链;没有 LLM key 也能跑(产出数据快照 + 技术特征);
没有飞书 webhook 就只存本地 md。

## 架构:纯 Python 数据管线

强制分层,**代码算数字、LLM 只解释**;层间通过共享文件协作(git-as-database):

```
  FRED / TwelveData / Tiingo / Yahoo
            │  catalog(主源 + 兜底链)
            ▼
   [ sources ] ─▶ data/raw/latest/series.parquet   ← 原始层(全量快照,每日重拉)
                          │                            history/ 归档 = point-in-time
                          ▼
   [ features / regime ] 代码算技术特征(因果滚动)
                          │
                          ▼
   [ llm ] 特征块 + 宏观传导图 ─▶ LLM(provider 可换)─▶ 四层简报
                          │
        ┌─────────────────┼──────────────────────┐
        ▼                 ▼                       ▼
  data/briefs/<date>.md  data/briefs.json   data/hypotheses.csv   飞书(可选)
  (人读)                (前端接缝)          (假设追踪复盘)
```

- **数据源强强联合**:FRED(利率/利差/实际利率/广义美元/VIX/月频宏观)+ Twelve Data(金现货
  `XAU/USD`)+ Tiingo(`UUP` 窄口径美元代理、`SPY`/`QQQ` 长历史)+ Yahoo 兜底。见
  [docs/refactor/readme.md](docs/refactor/readme.md) §3。
- **不偷看未来**:特征全用滚动窗口(只看过去);全历史算一次、按日取行,天然 point-in-time。
- **接缝**:原始层 parquet(可重建缓存)+ 对外产物 JSON/md 走 git。

## 目录结构

```
py/newsletter/             # 纯 Python 数据管线
  README.md                # 后端代码现状与设计思路
  config.py                # 配置(密钥/路径/特征窗口,类型化)
  models.py                # pydantic 契约(LLM 输出归一化 + 前端 Brief)
  sources/                 # 数据源适配:base + fred/twelvedata/tiingo/yahoo
  catalog.py               # 观察集:逻辑指标 → 主源/兜底链 + kind
  store.py                 # parquet 原始层(latest/history)
  features.py regime.py    # 技术特征(因果)+ 代码派生 regime 标签
  llm/                     # providers(多模型)+ schema(四层)+ prompt(特征块)+ service
  render.py                # → 前端 JSON / markdown / 飞书文本
  news.py hypotheses.py    # 新闻分类 + 假设追踪复盘
  pipeline.py __main__.py  # 编排(target_date 贯穿)+ CLI
  framework/linkage_map.md # 核心 IP:人工维护的宏观传导图
  tests/                   # 64 个离线单测(含特征因果性红线)
data/                      # git-as-database
  raw/latest/*.parquet     # 原始全量快照(history/ 归档已 gitignore)
  briefs/<date>.{md,json}  # 每日简报(人读 + 单日 JSON)
  briefs.json              # 展示平面接缝:聚合简报(供前端 fetch)
  hypotheses.csv           # 假设追踪日志
frontend/app/              # 展示平面:React+Vite+TS 小票阅读器
.github/workflows/daily.yml# 每日 cron:拉数 → 简报 → 提交回仓库 →(可选)推飞书
DESIGN.md  docs/           # 设计哲学 + 重构设计/路线图/变更日志
```

## 快速开始

### 前置
- Python ≥ 3.11;依赖 `pandas` / `numpy` / `pyarrow` / `pydantic`(见 [requirements.txt](requirements.txt))
- 免费 **FRED API key**:https://fred.stlouisfed.org/docs/api/api_key.html
- 免费 **Twelve Data** key(金价)、**Tiingo** token(美元代理/长历史)
- (可选)任一 **LLM provider key** → 出 AI 四层内容;(可选)**飞书 webhook** → 推送

把配置写进 `.env`(已 gitignore,见 [`.env.example`](.env.example)):
```bash
cp .env.example .env            # 填入 FRED / TWELVEDATA / TIINGO / LLM key
pip install -r requirements.txt # 或用现成的 conda 环境
```

### 运行
```bash
PYTHONPATH=py python -m newsletter                 # 生成今天的简报
PYTHONPATH=py python -m newsletter --date 2026-06-18
PYTHONPATH=py python -m newsletter --no-news       # 不抓新闻(历史回填用)
PYTHONPATH=py python -m unittest discover -s py/newsletter/tests -t py -p 'test_*.py'
```
产物:`data/briefs/<date>.md`(人读)+ `data/briefs.json`(前端)+(配了飞书则推送)。

## 配置(环境变量)

| 变量 | 作用 | 必需 |
|---|---|---|
| `FRED_API_KEY` | FRED 数据 | 是 |
| `TWELVEDATA_API_KEY` | 黄金现货 `XAU/USD` | 推荐 |
| `TIINGO_API_TOKEN` | 窄口径美元代理 `UUP` / 长历史 `SPY`·`QQQ` | 推荐 |
| `LLM_PROVIDER` | 显式选 provider;缺省按存在的 key 自动探测 | 否 |
| `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` / `DEEPSEEK_API_KEY` / … | LLM provider(任一) | 否 |
| `<NAME>_BASE_URL` / `<NAME>_MODEL` | 覆盖某预设的域名/模型 | 否 |
| `FEISHU_WEBHOOK` / `FEISHU_SECRET` | 飞书机器人(签名可选) | 否 |
| `NEWS_DISABLED` | 设为非空则跳过新闻抓取 | 否 |

## 自动化(GitHub Actions)

[`daily.yml`](.github/workflows/daily.yml) 每天北京时间 07:00 跑:`pip install` → 拉数 → 生成简报 →
`git add data/` 提交回仓库 →(配了飞书则)推送。**定时任务只在默认分支生效。** 在仓库 Settings 配
Secrets(`FRED_API_KEY` / `TWELVEDATA_API_KEY` / `TIINGO_API_TOKEN` / provider key / 飞书)+ Variables
(`LLM_PROVIDER` 等)。缺了走降级,不让 CI 失败。

## 设计哲学

1. **强制分层**(本次重构核心):数字由代码算成技术特征,LLM 只解释、不心算——质量的最大杠杆。
2. **四层结构**(简报灵魂):事实 / 解读 / 可证伪假设 / 影响观察点。强制区分客观事实与主观判断
   ——既是差异化,也是合规外衣,还是给 LLM 的缰绳。
3. **宏观传导图**([linkage_map.md](py/newsletter/framework/linkage_map.md)):人工维护的因果/传导
   关系清单,是核心 IP,也是作者学经济的载体。
4. **假设追踪**:每条假设可证伪、带失效条件,次日复盘 held/invalidated/open——信任引擎。
5. **不承诺收益**:只给「观察点」,绝不喊买卖。每篇带免责声明。

## 文档

- [py/newsletter/README.md](py/newsletter/README.md) — **后端代码现状与设计思路**(读代码先看这份)
- [DESIGN.md](DESIGN.md) — 愿景、产品哲学、四层结构、已锁定决策
- [docs/refactor/](docs/refactor/readme.md) — **数据质量重构**:架构/进度总纲 + [V1](docs/refactor/v1-progress.md) + [V2](docs/refactor/v2-progress.md)
- [docs/frontend-rebuild.md](docs/frontend-rebuild.md) — 前端重做指南(数据契约 + 设计稿映射 + 缺口状态)
- [docs/TODO.md](docs/TODO.md) — 路线图 / 技术债 / 开放问题
- [docs/parked-scope.md](docs/parked-scope.md) — 搁置范围(多市场等,保持宏观聚焦)
- [docs/CHANGELOG.md](docs/CHANGELOG.md) — 工作历史 / 进度日志

## 免责声明

本项目产出的所有内容均由程序/AI 自动生成,仅为研究框架与观察点,**不构成投资建议,不承诺
任何收益**。投资决策与风险由使用者自行承担。
