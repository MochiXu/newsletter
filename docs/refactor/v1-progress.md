# v1 重构 · 五步细节与进度

> 配合 [readme.md](readme.md) 阅读(总架构 / 数据源分工 / v2·v3 展望在那里)。
> 本文件是**动手蓝图 + 逐步进度**。每步含:目标 / 设计 / 产出 / 验收 / checklist。
>
> **v1 范围锁定**:扩数据 + 特征层 + 升级**每日**简报。前端 V1 **不改**(LLM 输出沿用现有
> `briefs.json` 契约,前端是 data-driven 的,只要 JSON 形状不变即可)。回测、多周期、
> 结构化 regime 验证 → v2/v3。

---

## Step 1 · 数据源接入与分工

**目标**:用统一接口把四家源(FRED / Twelve Data / Tiingo / Yahoo)接进来,按「主源 + 兜底链」拉日频原始序列。

### 实测探测结论(2026-06-18,用真实 key 跑过)

- **FRED**:利率 `DGS2/DGS10/T10Y2Y/DFII10`、广义美元 `DTWEXBGS`、`VIXCLS`、宏观 `CPILFESL/UNRATE/PAYEMS/FEDFUNDS` 全部健在;`SP500` 仅 2016+(S&P 授权),`NASDAQCOM` 长历史;**无任何可用金价序列**(伦敦金 AM/PM 代码均 `does not exist`),**无窄口径 DXY**。
- **Twelve Data**(免费 800/天、8/分):`XAU/USD` 金现货 ✅ 回溯 2012+;指数 `SPX/IXIC/NDX` 与 `DXY` 在免费档 **404**(不可用)。→ **只取黄金**。
- **Tiingo**(免费 1000/天):`GLD`(2004+)、`SPY`(1993+)、`QQQ`(1999+)、`UUP`(2007+,美元指数 ETF)、`IEF`(2002+)EOD 均可,历史很长。

### 观察集(v1 逻辑指标 → 物理来源)

| 逻辑指标 | series_id | kind | 主源 | 兜底链 |
|---|---|---|---|---|
| 2Y 收益率 | `DGS2` | rate | FRED | — |
| 10Y 收益率 | `DGS10` | rate | FRED | — |
| 2s10s 利差 | `T10Y2Y` | spread | FRED | — |
| 10Y 实际利率 | `DFII10` | rate | FRED | — |
| 10Y 通胀预期 | `T10YIE` | rate | FRED | 派生 `DGS10−DFII10` |
| 广义美元 | `DTWEXBGS` | index | FRED | — |
| 窄口径美元(代理) | `UUP` | index | Tiingo | — |
| VIX | `VIXCLS` | index | FRED | — |
| 标普 500 | `SP500` | index | FRED | Tiingo `SPY` |
| 纳斯达克综合 | `NASDAQCOM` | index | FRED | Tiingo `QQQ`(注:QQQ=NDX 口径,非综合) |
| 黄金现货 | `XAUUSD` | price | Twelve Data | Tiingo `GLD` → Yahoo `GC=F` |
| 核心 CPI(背景) | `CPILFESL` | macro_m | FRED | — |
| 失业率(背景) | `UNRATE` | macro_m | FRED | — |
| 非农(背景) | `PAYEMS` | macro_m | FRED | — |
| 联邦基金利率(背景) | `FEDFUNDS` | macro_m | FRED | — |

> 月频宏观(`macro_m`)v1 **只取最新读数当背景**,不进滚动特征、不进回测(规避 vintage 修正的偷看未来)。

### 兜底规则(降级前必先重试主源)

- 任一逻辑指标:**主源带退避重试 N 次,全部失败才降级**到兜底链下一个;实际命中的源记入 `source` 字段(可追溯)。
- `NASDAQCOM`:**优先 FRED**;仅当 FRED 缺失/挂且重试耗尽,才用 Tiingo `QQQ`。注意**口径不同**(综合指数 vs 纳斯达克 100),降级时必须标注,避免误读为同一序列。
- `UUP`(窄口径美元代理)是 ETF,**只用收益率/趋势/标准化**参与分析,**绝不取绝对价位**(详见 Step 2 美元组)。

### 设计

- `sources/base.py`:`Source` 协议 —— `fetch(series_id, start, end) -> DataFrame[date, value]`,产出**统一 tidy 格式**(`date, series_id, value`)。
- 每家一个适配器:`fred.py` / `twelvedata.py` / `tiingo.py` / `yahoo.py`,各自封装 URL、鉴权(从 `.env` 读 key)、解析、礼貌间隔与退避。
- `catalog.py`:上表的机读版 —— 每个逻辑指标声明 `(primary, fallbacks, kind)`;抓取时按链路依次尝试,主源失败自动降级并记 `source` 字段(可追溯实际用了谁)。

**产出**:`sources/`、`catalog.py`;能把观察集全历史拉成统一 tidy DataFrame。
**验收**:离线单测(用录制的样例响应)覆盖每家解析;一次真实拉取打通全观察集,缺口被兜底链补上。

- [x] `Source` 协议 + tidy 规范
- [x] FRED / TwelveData / Tiingo / Yahoo 适配器
- [x] `catalog` 主源+兜底链路 + 实际 source 追溯
- [x] 解析单测 + 一次真实全量拉取验证

---

## Step 2 · 特征层(代码算,pandas)

**目标**:把原始序列加工成**有信息量的技术特征**,固定格式喂 LLM。原则:**挑主要的、值得的**,不是越多越好;滚动窗口天然因果(只用过去),不偷看未来。

### 精选特征集(按用途分组,附「为什么」)

**趋势(价格类:指数/黄金/美元)**
- `ma_20 / ma_60 / ma_120 / ma_200`
- `px_vs_ma200`(% 距离)+ `above_ma200`(布尔)——长期多空位置
- `ma50_vs_ma200`(金叉/死叉环境)

**动量**
- 价格类:`ret_5d / ret_20d / ret_60d / ret_120d`
- 利率类(`DGS2/DGS10/DFII10/T10Y2Y`):`chg_5d / chg_20d / chg_60d`(单位 bp;利率算变化量不算收益率)

**波动与风险(指数/黄金)**
- `vol_20d / vol_60d`(年化已实现波动 = std(日收益)×√252)
- `max_drawdown_60d / max_drawdown_252d`
- VIX:`level / ma_20 / z_252d / pct_252d`(z 分数 + 百分位,判极端)

**利率与通胀**(*专家增量*)
- `DGS2/DGS10` level + chg;`T10Y2Y` level + chg + `inverted`(布尔)
- `DFII10`(实际利率)level + chg —— 黄金的核心驱动
- **`breakeven_10y = DGS10 − DFII10`** level + chg —— 盈亏平衡通胀(通胀预期),旧版完全没有,信息量高

**美元**(*专家增量*)—— **UUP 是 ETF 代理,只比收益率/趋势/标准化,绝不取绝对价位**(`UUP_ret≈DXY_ret`、`UUP_trend≈DXY_trend`、`UUP_z≈美元强弱极端度`)
- `DTWEXBGS`(广义)`ret_20d/60d` + `z_252d` + `px_vs_ma`(趋势)
- `UUP`(窄口径代理)`ret_20d/60d` + `z_252d` + `above_ma200`(趋势)——**不输出其绝对价位**
- **`usd_broad_vs_narrow_divergence`** —— 用**收益率之差 / z-score 之差**度量「广义 vs 窄口径美元背离」(非价位差)。找回旧版核心叙事,且口径从"价位差"升级为"趋势/标准化背离",方法上更稳健;诚实标注 UUP 为代理

**跨资产关系(60 日滚动相关)**(*regime 变化探测器*)
- `corr_SP500_DGS10_60d` —— 股/债关系(再通胀 vs 衰退定价)
- `corr_SP500_VIX_60d` —— 杠杆/情绪健全性
- `corr_GOLD_DFII10_60d` —— 黄金还跟实际利率走,还是脱钩(去美元化叙事)
- `corr_GOLD_DTWEXBGS_60d`

**极值/位置**
- `pct_252d`(52 周区间百分位:`(px−min252)/(max252−min252)`)—— 指数/黄金「在一年区间的什么位置」

**代码派生 regime 标签**(轻量,喂 LLM 省心 + 为 v2 L4 埋点)
- `equity_trend`(above/below MA200)、`vol_regime`(VIX 低<15 / 中 15–20 / 高>20 + 升/降)、`curve`(倒挂/平/正 + 走陡/走平)、`real_rate`(升/降)、`dollar`(强/弱 vs MA + 背离 flag)

### 设计

- `features.py`:每类一个纯函数 `add_xxx(df, col, window)`(参考脑暴稿的签名),在**全历史**上一次算完;任意 `target_date` 取对应行即可(因果由滚动保证)。
- `regime.py`:基于特征派生上面的分类标签(纯代码,不喂数让 LLM 猜)。
- 价格类用 `ret`,利率类用 `chg`(bp);窗口集中在 `config` 常量,便于调。

**产出**:`features.py` / `regime.py` + 一份「特征字典」(每个特征的口径说明,供 prompt 与排错)。
**验收**:单测核对手算值(收益率/MA/z-score/相关性/回撤);因果性测试——`target_date` 的特征不依赖其后任何一行。

- [x] 趋势/动量/波动/利率·通胀/美元/相关性/极值 各组特征函数
- [x] regime 标签派生
- [x] 因果性单测(关键:绝不偷看未来)
- [x] 特征字典文档

---

## Step 3 · 存储形态 + LLM 输入/输出格式

**目标**:定清楚「原始数据怎么存、特征怎么传 LLM、LLM 结果怎么变前端 JSON」。

### 存储:`data/raw/{latest,history}`(latest=全量快照,history=每日 point-in-time 档案)

```
data/raw/
  latest/series.parquet          # 当前全量快照:全历史(~10 年全部行),每日重拉覆盖
  history/series-<pull_date>.parquet   # 每日归档的全量快照(gitignored)
```

**关键确认:每个 parquet 都是「全历史全量」**(~10 年全部日频行的长表 `date, series_id, value, source`),**不是当天单行**——因为我们每天全量重拉。

**每日落盘流程**:
1. 读 `latest/series.parquet`(昨天那次拉的全量),按其内记录的 `pull_date` 归档为 `history/series-<pull_date>.parquet`;
2. 三家全量重拉 → 写新的 `latest/series.parquet`(覆盖);
3. 算特征 → 出简报。

> `history/` 因此天然积累出一串「我们在某日看到的完整序列」——**这正是 v2 回测要的 point-in-time / vintage 档案,白赚**。

**容量与额度**:观察集 ~15 序列 × ~10 年日频 ≈ 几万行,parquet 列式压缩后单份仅几 MB;三家额度(FRED 无硬限、TD 800/天、Tiingo 1000/天)绰绰有余,**每日全量重拉完全 OK**。

**「历史不变」假设核验**(已 double-check):价格/收益率/VIX/美元的历史收盘**不会变** → 覆盖写安全。两个例外:① 月频宏观会被**修正**(v1 只当背景、不进特征/回测,规避);② ETF `adjClose` 随分红**回溯调整**(故金价用 `XAU/USD` 现货,不用 GLD 复权价)。

**git 策略**:
- `data/raw/history/` → **gitignore**(每日全量二进制档案,本地/可重建,不入库);
- `data/raw/latest/series.parquet` → **tracked**(按你的设计提交)。**注意权衡**:它每日全量改写,git 对 parquet 二进制无法 delta 压缩 → 仓库每天增量 ≈ 一份完整快照(几 MB),长期会涨。备选:`latest` 也 gitignore(反正每天重拉可重建,CI 不依赖它),仅提交报告 JSON/md。**默认按你的方案(latest 提交);若后续嫌仓库膨胀再切备选。**
- `data/features/<date>.parquet`(报告当天特征快照,供排错/审计)→ **gitignore**(可派生)。
- **对外产物(走 git,可 diff、有历史)**:`data/briefs/<date>.json` + 聚合 `data/briefs.json`(前端 fetch)+ `data/briefs/<date>.md`(人读)。

> CI(临时 runner)每次从 API 重拉重建 → 出 JSON 提交回仓库;`history/` 在 CI 上不持久(每次空),仅在本地累积。v2 若要 CI 侧持久 vintage,再议(提交 history 或挂对象存储)。

### LLM 输入(固定格式)

- `prompt.py` 的 `build_user`:把**算好的特征**渲染成紧凑、带白话标签的「特征块」(分组:趋势/动量/波动/利率·通胀/美元/相关性/极值/regime 标签)+ 月频宏观最新读数 + 宏观传导图。
- **不再丢原始值让 LLM 心算**——这是质量提升的核心。

### LLM 输出(前端兼容,V1 不改前端)

- 沿用现有四层契约:`headline / tone / facts / interpretation(reads) / hypotheses / impacts(+direction) / metrics / reviews / news`。
- `metrics[]` 仍是 `{key,label,value,change,kind}` 形状(前端 data-driven),v1 用新观察集填充(谁缺自适应跳过)。
- **修掉旧 bug**:对 `facts`/`interpretation` 做归一化(LLM 偶尔返 `{"fact": "..."}` 对象 → 统一抽成字符串),杜绝 `[object Object]`。
- *(可选)* 额外输出轻量 `regime` 块(前端忽略未知字段,为 v2 L4 提前留存判断)。

**产出**:`store.py`(parquet 读写)、`prompt.py`(特征块格式)、`render.py`(前端 JSON + md);`.env.example` 补三家 key 占位符。
**验收**:跑一次真实管线,产出符合现有 `types.ts` 契约的 `briefs.json`;前端不改、能正常渲染;无 `[object Object]`。

- [x] parquet 读写 + 每日全量重拉 + 幂等覆盖
- [x] git 策略落地(.gitignore 调整,只提交 JSON/md)
- [x] `build_user` 特征块固定格式
- [x] 前端兼容 JSON + facts/interpretation 归一化
- [x] `.env.example` 占位符补全

---

## Step 4 · 代码架构整体重设计(无历史包袱)

**目标**:整体重构,不背历史包袱;可参考旧代码,但为更好的架构与数据分析重新设计模块。

### 目标模块布局(纯 Python)

```
py/newsletter/
  config.py        # pydantic-settings 从 .env 读 key + 集中常量(symbols / windows / paths),全类型化
  models.py        # pydantic 数据模型(边界契约):Brief/Metric/Hypothesis/Impact/News/Review/Regime
  sources/         # 数据源适配(Step 1)
    base.py fred.py twelvedata.py tiingo.py yahoo.py   # 响应解析用 pydantic 校验
  catalog.py       # 观察集 + 主源/兜底链 + kind(dataclass/pydantic)
  store.py         # parquet 原始层(latest/history)/ 特征快照 读写
  features.py      # 技术特征(Step 2,pandas)
  regime.py        # 代码派生 regime 标签
  llm/
    providers.py   # 多模型(沿用旧版,几乎不动)
    schema.py      # 喂 LLM 的 JSON Schema(四层 + tone/direction(+ 可选 regime))
    prompt.py      # build_user:特征块固定格式
  render.py        # LLM 输出 → pydantic 校验(含 facts 归一化)→ 前端 JSON / md / 飞书文本
  news.py          # 新闻抓取+分类(沿用,微调)
  hypotheses.py    # 假设追踪(沿用;V1.5 起被 predictions.py 预测账本替代)
  pipeline.py      # 编排:fetch→store→features→regime→llm→render→输出(+ deliver)
  deliver/feishu.py
  tests/
```

### 代码规范(对齐业内实践)

- **全量 type hints**:所有函数签名、关键变量;`mypy`/`pyright` 友好。
- **pydantic 守边界**(不是到处套):① `config` 用 `pydantic-settings` 从 `.env` 读 key,类型化校验;② `sources/*` 解析外部 API 响应用 pydantic 模型;③ LLM 输出在 `render` 入口用 `models.Brief` 校验——**`{'fact': ...}` 归一化做成 field validator**,根治旧 bug。
- **内部值对象**用 `dataclass`(轻量、无校验开销);**数值帧**保持 `pandas.DataFrame`(不套 pydantic)。
- 目标运行环境:conda env `myTools`(Python 3.11 / pandas 3.0 / numpy 2.4 / pyarrow 24 / pydantic 2.13)。注意 pandas 3.0 的 copy-on-write 默认与若干弃用 API。

### 取舍

- **沿用**(质量已验证):`providers`(多模型)、`news`、`hypotheses`(V1.5 起改 `predictions` 预测账本)、`deliver/feishu`、四层 schema 的纪律。
- **重写**:数据获取(Rust→Python 多源)、存储(CSV run_date 日志 → parquet 干净序列)、**新增特征/regime 层**、`build_user`(改喂特征)、`render`(pydantic 校验 + 归一化)、`pipeline` 编排。
- **`target_date` 参数**:`pipeline` 接受 `target_date`(默认今天),全链路据此切片 —— v1 只跑「今天」,但接口为 v2 回测就位。

**产出**:可运行的纯 Python 管线,一条命令出当日简报(md + JSON + 可选飞书)。
**验收**:端到端用真实 key 跑通;离线单测(无 key 时优雅降级:出事实层+特征,不崩);四层内容明显比旧版扎实(特征驱动)。

- [x] 模块骨架落地
- [x] `pipeline` 编排 + `target_date` 接口
- [x] 端到端真实跑通 + 离线降级测试
- [x] 新旧简报内容质量对比(留样)

---

## Step 5 · Rust 数据平面退役

**目标**:Rust 模块直接废弃(数据获取已迁 Python)。

### 设计

- 删除 `src/*.rs`、`Cargo.toml`、`Cargo.lock`、`/target`;`.github/workflows/daily.yml` 改为纯 Python(`pip install` + 跑 `pipeline`)。
- 文档同步:`README.md`(架构图去掉 Rust 平面)、`docs/data-plane.md`(归档或标注「已退役,见 refactor」)、`docs/CHANGELOG.md` 记一笔。
- 保留 git 历史即可(需要时可回溯旧 Rust 实现)。

**产出**:单语言(Python)代码库;CI 绿。
**验收**:`daily.yml` 在干净环境跑通;仓库无 Rust 残留引用。

- [x] 删除 Rust 源 + 构建产物
- [x] `daily.yml` 改纯 Python
- [x] 文档同步(README / data-plane / CHANGELOG)

---

## 跨步注意事项

- **密钥**:四家 key(`FRED`/`TWELVEDATA`/`TIINGO`/`DEEPSEEK`)仅在 `.env`(已 gitignore),绝不入库/打印/写文档。
- **优雅降级**:任一源失败走兜底链;无 LLM key 时仍产出「事实层 + 特征」快照,不崩。
- **不偷看未来**:Step 2 因果性单测是红线;月频宏观 v1 不进特征/回测。
- **前端不动**:V1 只保证 `briefs.json` 形状不变;前端契约升级留到真实数据接管(原 F5)那一步统一做。
- **本地开发**:Python 一律跑在 conda env `myTools`(`source /Users/mochi/environment/miniconda3/etc/profile.d/conda.sh && conda activate myTools`);CI 走 `pip install`(锁版本)。
- **代码规范**:全量 type hints + pydantic 守边界(配置 / API 解析 / LLM 输出),见 Step 4。
