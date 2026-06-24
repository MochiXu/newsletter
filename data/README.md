# `data/` — 数据目录说明

这是管线的「**git-as-database**」:每天的产物都落在这里,层与层之间靠**共享文件**协作。
核心原则:**代码算数字、LLM 只解释**;路径定义的唯一权威在 [`py/newsletter/config.py`](../py/newsletter/config.py) 的 `Paths`。

> ⚠️ 路径以 `config.py::Paths` 为准。本文件是给人看的导览,改了路径请同步这里。

---

## 速查表

| 路径 | 是什么 | 谁写 | 谁读 | git |
|---|---|---|---|---|
| `raw/latest/series.parquet` | 全量原始观测快照(全历史长表) | `store.write_snapshot` | features / 预测结算 | ✅ 入库 |
| `raw/latest/manifest.json` | 上面快照的元信息(拉取日/行数/序列/日期范围) | `store.write_snapshot` | 排错/审计 | ✅ 入库 |
| `raw/history/series-<date>.parquet` | **PIT 修订档案**:冻结每天拉取时的快照(留存被修订前的原貌) | `store.write_snapshot` | 暂无(为 V2 真·PIT 回测预留) | 🚫 ignored* |
| `features/<date>.parquet` | 当天的特征快照(排错/审计) | `pipeline`(`write_features`) | 人工排错 | 🚫 ignored(可重建) |
| `briefs/<date>.md` | 单日**人读**简报(markdown) | `pipeline.write_outputs` | 人 / 飞书文案 | ✅ 入库 |
| `briefs/<date>.json` | 单日结构化简报(单日存档) | `render.upsert_briefs_json` | 存档 | ✅ 入库 |
| `briefs.json` | **聚合**所有天的简报(前端数据契约) | `render.upsert_briefs_json` | **前端**(copy 进 public) | ✅ 入库 |
| `predictions.csv` | 预测账本(逐条假设 + 到期结算) | `predictions.save` | 评估层 / 简报回填 | ✅ 入库 |
| `scorecard.json` | 评估层产出(技能 vs 基线 + 校准 + Brier) | `evaluate.write_scorecard` | 前端命中率页 | ✅ 入库 |
| `scorecard.md` | 评估层的**人读**版 | `evaluate.write_scorecard` | 人 | ✅ 入库 |
| `news_cache/extracted/*.txt` | 抓来的文章**全文**缓存 | `news/cache.ExtractCache` | 新闻分类/特征(护配额) | 🚫 ignored(**仅因体积**) |

---

## 按管线阶段详解

数据流(强制分层):

```
数据源(FRED/TwelveData/Tiingo/Yahoo)
   └─▶ raw/latest/series.parquet   ← ① 原始层(每日重拉覆盖,旧的归档到 history/)
            │
            ▼
        features/<date>.parquet     ← ② 特征层(代码算技术特征,因果滚动不偷看未来)
            │
            ▼
   LLM 四层简报 + 量化因子 + 新闻
            ├─▶ briefs/<date>.md + .json
            └─▶ briefs.json          ← ③ 智能平面产出(前端读这个)
            │
            ▼
        predictions.csv             ← ④ 预测账本(可证伪假设 + 到期代码裁决)
            │
            ▼
        scorecard.json + .md        ← ⑤ 评估层(技能/校准/Brier,只信 forward)
```

### ① 原始层 `raw/`
- **`latest/series.parquet`**:观察集**全量、全历史**的长表(`series_id × date → value`),每天重拉**覆盖**。
  这是整条管线的事实地基。**入库**,因为它就是「当前真相」。
- **`latest/manifest.json`**:配套元信息 —— `pull_date`(拉取日)、`rows`、`series`(序列清单)、`date_min/date_max`。排错时先看它。
- **`history/series-<date>.parquet`**:每天落新 latest 前,先把**上一份** latest 按其 `pull_date` 冻结到这里。
  它是 **point-in-time(PIT)修订档案** —— 关键价值是留存**被修订前**的原貌。
  > 经济数据会反复修订:6-05 公布非农 +15 万,6-20 可能修订成 +9 万。`latest` 每天覆盖,只会显示
  > **今天**这个修订后的视图;而 `history/series-2026-06-05.parquet` 记的是 **6-05 当天我们实际看到的** +15 万。
  > 诚实回放/回测要用"那天真正已知的数据",而不是今天的修订版,否则就是隐蔽的修订泄漏(同 [AGENTS.md](../AGENTS.md) 的 point-in-time 纪律)。
  - **现状:只写不读**。代码只归档写入(`store.py`),目前**没有任何地方读它** —— 当前回填是"重新 fetch 到 target_date"
    (拿的是今天的修订视图)。它是为 **V2 真·PIT 回测**预留的防御性档案,尚未接上线。
  - **`*` gitignored 但并非完全"可重建"**:一旦 `latest` 被覆盖,过去的修订就找不回了(重拉只会给今天的视图),
    所以它其实是**修订历史的唯一记录**。现在忽略它是因为体积大 + 暂未使用 + 价格类不修订(低风险);
    真要做严肃 PIT 回测时,这份档案需要被妥善保留(考虑入库或单独备份)。

### ② 特征层 `features/<date>.parquet`
代码在 raw 上算的技术特征快照(趋势/动量/波动/利率·通胀/美元/跨资产相关/极值,**因果滚动,不偷看未来**)。
纯排错/审计用,**gitignored**(可由 raw 重算)。

### ③ 智能平面产出 `briefs*`
- **`briefs/<date>.md`**:单日**人读**简报(四层结构 + 技术特征 + 因子),也是飞书推送的文案来源。
- **`briefs/<date>.json`**:单日的结构化简报对象(单日存档)。
- **`briefs.json`**:**聚合版**(`{model, generatedAt, briefs:[...]}`),按日期倒序、刊号按年代序。
  **前端唯一消费的数据契约**(构建时 `copy-data.mjs` 拷进 `public/data/`)。每次运行会用最新账本
  把所有保留简报里"还是沙漏"的预测刷新成已结算(不必重生成历史简报)。

### ④ 预测账本 `predictions.csv`
逐条记录可证伪假设 + 到期后的**代码裁决**。列:
```
created_date, model, asset, direction, horizon, confidence,
status, resolved_date, realized_dir, realized_text, hit, note,
base_dir, base_conf,      ← 代码基线(陪练标尺)
arm,                      ← A/B 消融臂(A=纯价格因子 / B=加新闻 / 空=单臂)
source                    ← forward(前向,干净)/ backfill(回放,含记忆污染)
```
- **结算靠代码**:到期那天用真实价格算 `realized_dir` / `hit`;`note` 是 LLM 写的复盘叙述。
- **`source` 是诚实红线**:只有 `forward` 数据可用于打分;`backfill` 仅展示、不算命中率。

### ⑤ 评估层 `scorecard.*`
- **`scorecard.json`**:`{asOf, source, buckets, models}`。`models` 按 **lane(=模型·臂,如 `deepseek·B`,或 `_factor`)**
  拆分,给出技能(命中 − 基线)、信心校准分桶、Brier(vs climatology)。前端命中率页读它。
- **`scorecard.md`**:同内容的人读版。
- 只统计 `source=forward` 的样本;混入 backfill 会在 `source` 字段标 `mixed`/`backfill` 诚实告知。

### 新闻缓存 `news_cache/extracted/*.txt`
抓来的文章**全文**按 `uuid`(或 url 哈希)落盘缓存,重跑/回填不重抓(护 API 配额 + 礼貌 + 可复现)。
**gitignored 仅因体积**(批量正文会撑肥 git);个人非商用项目,全文本地随便存随便用 —— 喂 LLM 分析、派生特征都放开。
(对外简报只展示 标题/来源/链接/我们写的摘要,是产品形态选择,不是版权限制。)

---

## 入库 vs 忽略(为什么)

**入库(`✅`)= 当前真相 / 前端要用 / 不可重建的账本**:
`raw/latest/`、`briefs/`、`briefs.json`、`predictions.csv`、`scorecard.*`。

**忽略(`🚫`,见 [`.gitignore`](../.gitignore))= 可重建 / 版权 / 暂未使用**:
`features/`(可从 raw 重算)、`news_cache/`(版权,且可重抓)、
`raw/history/`(PIT 修订档案,**当前只写不读**;严格说**不完全可重建** —— 覆盖后修订原貌就丢了,见上文)。

---

## 重新生成

- 单日:`PYTHONPATH=py python -m newsletter --date 2026-06-18`
  (历史日会**自动**走 backfill 新闻时间窗,防先知泄漏;详见 [AGENTS.md](../AGENTS.md))。
- `features/` `news_cache/` 删了都能重算/重抓;`raw/latest/` 删了下次运行会重拉。
- `raw/history/` 例外:删了**无法找回过去的修订原貌**(重拉只给今天的视图)。当前没人读它,删了不影响运行;
  但若日后要做真·PIT 回测,这份档案就是不可再生的,删前三思。
- `briefs.json` / `predictions.csv` / `scorecard.*` 是**账本性**产物 —— 删除等于丢历史,删前先想清楚(git 里有版本兜底)。
