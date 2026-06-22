# `newsletter` 后端 · 代码现状与设计思路

> 本文件只描述**当前代码实际是什么、为什么这么设计**。
> 项目级的步骤规划/路线图见仓库 [`docs/`](../../docs/refactor/readme.md);愿景与产品哲学见 [`DESIGN.md`](../../DESIGN.md)。

纯 Python 实现的每日宏观简报管线:抓宏观数据 → **代码算技术特征** → LLM 生成分层简报 → 落盘为 md / JSON / 飞书。一条命令出当日简报。

## 设计思路(四条原则)

1. **强制分层:代码算数字,LLM 只解释。** 所有数值(趋势/动量/波动/相关性/regime 标签)都在调用 LLM **之前**由 pandas 算好,打包成文本「特征块」喂给模型;LLM 只做判断、解释、写假设,**绝不参与数值计算**。这是内容质量的最大杠杆,也根治了旧版「让 LLM 心算」导致的模糊与算错。
2. **不偷看未来(因果)。** 特征全部用滚动窗口(只看过去),在全历史上一次算完、按日取行 → 任意 `target_date` 的特征都只依赖该日及之前的数据。有单测红线守护。月频宏观会被事后修正(vintage),故只当背景、不进特征。
3. **`target_date` 贯穿全链路。** `pipeline` 接受目标日期(默认今天),整条链路据此切片。今天只跑「今天」,但接口已为「站在历史任一天复算」就位。
4. **优雅降级 + git-as-database。** 任一数据源失败走兜底链;无 LLM key 仍产出特征/事实层;无飞书 webhook 只存本地 md。层间通过共享文件协作(parquet 原始层 + JSON/md 产物),不走 FFI / 进程内调用 / 常驻服务。

## 管线分层

```
  FRED / TwelveData / Tiingo / Yahoo
            │  catalog:逻辑指标 → 主源 + 兜底链
            ▼
   sources ─▶ store ─▶ data/raw/latest/series.parquet   原始层(全量快照,每日重拉;history 归档=point-in-time)
                          │
                          ▼
   features / regime  pandas 算技术特征(因果滚动)+ 代码派生 regime 标签
                          │
                          ▼
   llm  特征块 + 宏观传导图(linkage_map.md)─▶ LLM(provider 可换)─▶ 四层结构化输出
                          │
   render  LLM 输出 → pydantic 校验/归一化 → 前端 JSON / markdown / 飞书文本
                          │
        ┌─────────────────┼──────────────────────┬─────────────┐
        ▼                 ▼                       ▼             ▼
  briefs/<date>.md   briefs/<date>.json     briefs.json   hypotheses.csv   飞书(可选)
  (人读)             (单日)                 (聚合,前端)   (假设追踪复盘)
```

## 模块职责

| 模块 | 职责 |
|---|---|
| `config.py` | 单一配置源:从仓库根推导所有数据路径(`PATHS`)、集中特征窗口常量(`WINDOWS`)、从 `.env` 类型化加载密钥/开关(`Settings`,pydantic) |
| `models.py` | 边界数据契约(pydantic):① LLM 原始输出的**容错解析**(归一化字符串列表、枚举容错,根治 `{'fact':...}`→`[object Object]`);② 严格对齐前端 `types.ts`(驼峰别名导出)。**多模型契约**:`Brief` = 脊柱(模型无关)+ `views:{modelId: ModelView}` + `consensus:[ConsensusItem]`;`ModelView` 承载随模型变的六层(tone/headline/facts/reads/hypotheses/impacts);`model_validator` 把旧扁平 brief 迁进 `views.archive`(向后兼容)。事实/解读层为 `TaggedItem{tag,text,figures:[Figure{t,dir}]}`(`figs` 扁平串解析、tag 受控词表 `FACT_TAGS`、向后兼容旧 str[]) |
| `sources/` | 数据源适配器:`base`(`Source` 协议 + 带退避的 `urllib` 拉取 + api_key 不入日志)、`fred` / `twelvedata` / `tiingo` / `yahoo`,各自产出统一 tidy 帧 `[date, value]` |
| `catalog.py` | 观察集机读版:每个逻辑指标声明 `(主源, 兜底链, kind)`;抓取时按链路依次尝试,记录实际命中的源(可追溯);`DISPLAY_METRICS` 定义前端指标表 |
| `store.py` | parquet 原始层读写:`write_snapshot`(归档上一份再写 latest)、`write_features`(单日特征快照,gitignore) |
| `features.py` | 技术特征(纯 pandas):趋势(MA/距 MA)、动量(收益率/利率变化 bp)、波动(年化已实现波动/回撤)、利率·通胀、美元(广义 vs 窄口径代理背离)、跨资产 60 日滚动相关、52 周分位、极值;`FEATURE_VIEW`(signals 单一源)、`metric_spark`(小走势序列)、`price_series`(30D 价格序列)|
| `regime.py` | 基于特征**纯代码派生** regime 标签(股票趋势 / 波动率档 / 收益率曲线 / 实际利率 / 美元强弱),不让 LLM 猜 |
| `llm/` | `providers`(多模型可插拔:`select_providers` 读 `LLM_MODELS` 逐个构建;OpenAI 兼容家走 **JSON mode**;`AnthropicProvider` 支持中转站 base_url + AUTH_TOKEN + 三路 tool 解析兜底;`_compat_url` 补 `/v1/...`)、`schema`(四层 + tag/figs 的 JSON Schema)、`prompt`(`build_feature_block`)、`style`(`TEXT_STYLE`)、`service`(`generate_brief` 单模型 / `generate_briefs` 多模型逐个降级) |
| `textnorm.py` | 确定性中英文排版规范化(`normalize_text`:全角标点→ASCII、中英盘古空格、双引号→单引号;不拆 `MA200/2s10s/9bp`)。render 落库前对所有展示文本统一应用 |
| `render.py` | LLM 输出 → pydantic 校验/归一化 + `normalize_text`(+ figure 补单位/去死)→ `build_metrics`(含 spark)/ `build_signals` / `build_price_series` / `build_view`(单模型六层)/ `build_consensus`(跨模型代码投票)/ `build_brief`(脊柱 + views + consensus)/ `_split_asset`(影响层 asset 规范成中文名 + 提取英文 `code`)/ `render_markdown` / `render_text`(取主视图)/ `upsert_briefs_json` |
| `news.py` | RSS/Atom 抓取(stdlib)+ LLM 分类(事实/解读/影响资产);**按模型回填的 `index` 对齐**,免疫 LLM 改写/翻译标题 |
| `hypotheses.py` | 假设追踪复盘(`hypotheses.csv`):登记新假设、对**往日** open 假设复盘 held/invalidated/open(不拿当天数据自我验证),按天幂等 |
| `pipeline.py` | 编排:`fetch_and_store` → `build_report`(算特征→**多模型 LLM**→假设(以主模型为准)→新闻→组装多视图 Brief + 共识)→ `write_outputs`;`target_date` 贯穿,各 LLM 环节独立 try/except 降级 |
| `__main__.py` | CLI:`--date` / `--no-news` / `--history-years` / `-v` |
| `deliver/feishu.py` | 飞书机器人推送(HMAC 签名可选;失败不阻断,已存 md) |
| `framework/linkage_map.md` | 核心 IP:人工维护的宏观传导图,运行时读入喂给 LLM |
| `tests/` | 63 个离线单测(录制响应 + 手算核对 + **特征因果性红线** + textnorm 全覆盖 + figures 解析/补单位 + 多模型视图/共识 + 影响层 asset 规范化 + 向后兼容旧 str[] facts 与旧扁平 brief 迁移) |

## 数据源分工(已接入)

| 逻辑指标 | 主源 | 备份 / 代理 |
|---|---|---|
| 利率 2Y/10Y、2s10s、实际利率 DFII10、通胀预期 T10YIE、广义美元 DTWEXBGS、VIX、月频宏观(CPI/失业/非农/FFR) | FRED | — |
| 黄金 | Twelve Data `XAU/USD`(现货) | Tiingo `GLD` / Yahoo `GC=F` |
| 窄口径美元(DXY 代理) | Tiingo `UUP` | — (只比收益率/趋势/标准化,不取绝对价位) |
| 股指长历史 | Tiingo `SPY`/`QQQ` | FRED `SP500`/`NASDAQCOM` |

## 数据落盘(`data/`)

```
data/
  raw/latest/series.parquet    原始全量快照(入库;history/、features/ 已 gitignore,可重建)
  raw/latest/manifest.json     本次拉取元信息(pull_date / 行数 / 序列 / 日期范围)
  briefs/<date>.{md,json}      每日简报(人读 + 单日结构化)
  briefs.json                  聚合简报(前端 fetch 的接缝)
  hypotheses.csv               假设追踪日志(created_date/if_then/invalidation/status/verdict/...)
```

## 运行

```bash
PYTHONPATH=py python -m newsletter                  # 生成今天的简报
PYTHONPATH=py python -m newsletter --date 2026-06-20
PYTHONPATH=py python -m newsletter --no-news        # 不抓新闻(历史回填用)
PYTHONPATH=py python -m unittest discover -s py/newsletter/tests -t py -p 'test_*.py'
```

依赖:`pandas` / `numpy` / `pyarrow` / `pydantic`(见仓库 `requirements.txt`);LLM provider 层仍是纯 `urllib`。密钥写入仓库根 `.env`(已 gitignore)。

**多模型**:`.env` 设 `LLM_MODELS=deepseek,anthropic,openai`(逗号列表,[0]=主模型,缺 key 自动跳过)。各家 key/可选 base_url 由 `llm.providers` 直接读环境(如 `ANTHROPIC_AUTH_TOKEN`/`ANTHROPIC_BASE_URL`/`ANTHROPIC_MODEL`、`OPENAI_API_KEY`/`OPENAI_BASE_URL`/`OPENAI_MODEL`)。经中转站时:**base_url 只填 host**(代码补 `/v1/...`),**各模型族用各自的 key**。运行环境(cron/CI)须备齐这些 key,否则只出主模型一家。
> 坑:在 Claude Code 自己的 shell 里手动跑,会被注入的 `ANTHROPIC_BASE_URL=官方` 盖过 `.env`(`load_dotenv` 不覆盖 shell),需 `env -u ANTHROPIC_BASE_URL python -m newsletter ...`。
