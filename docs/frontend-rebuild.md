# 前端重做指南 · 与后端契约对齐

> 现有 `frontend/app` 将**整体删除**,按设计稿 [`frontend/desgin/`](../frontend/desgin/) 重做。
> 本文件是重做的**单一依据**:权威数据契约 + 设计稿↔后端字段映射 + 缺口状态 + 明确不要做什么。
> 重做必须对齐**真实 `data/briefs.json`**,**不要照旧 `frontend/app/src/types.ts`**(它停在旧假设:
> `render_json`、7 行指标、DXY、`link` 可选、假设只有 ifThen/invalidation——全过时)。

---

## 1. 数据契约(权威,= `data/briefs.json`)

后端 `py/newsletter/render.py` 产出、`py/newsletter/models.py` 定义。顶层:

```jsonc
{
  "model": "DeepSeek",            // 生成所用 LLM
  "generatedAt": "2026-06-20",    // 最新一期日期
  "briefs": [ Brief, ... ]        // 按日期倒序,最新在前
}
```

### Brief(单个交易日)

| 字段 | 类型 | 说明 |
|---|---|---|
| `date` | string | `YYYY-MM-DD` |
| `weekday` | string | 中文,如「周五」 |
| `issue` | number | 刊号(年代序,最早=1) |
| `time` | string | 常量「07:00 CST」 |
| `tone` | `risk-on\|risk-off\|neutral` | **驱动时间线圆点染色** |
| `headline` | string | 一句话总览 |
| `metrics` | `Metric[]` | 指标表(当前 **10 行**,长度自适应) |
| `signals` | `Signal[]` | **技术指标(新)**,代码计算,~29 条,带 `group` |
| `regime` | `{[k]: string}` | **代码派生 regime 标签(新)** |
| `facts` | `string[]` | 事实层 |
| `reads` | `string[]` | 解读层(后端 `interpretation`) |
| `hypotheses` | `Hypothesis[]` | **假设层 = 对固定方向的预测(已升级)** |
| `impacts` | `Impact[]` | 影响层观察点 |
| `reviews` | `Review[]` | 假设复盘(可空 → 该节隐藏) |
| `news` | `News[]` | 新闻(已过滤噪音/无链接;`link` 必有) |

### Metric — `{ key, label, value, change, kind }`
- `kind ∈ yield | spread | index | price`;`value`/`change` 单位由 kind 决定(yield/spread→%,index→千分位,price→价格)。
- **当前 10 行**(顺序固定):标普500 / 纳指 / VIX / US2Y / US10Y / 2s10s / 实际10Y / 通胀预期 / 广义美元 / 黄金。
- ⚠️ **只有 `value` + 当日 `change`,没有走势序列**(见 §4 缺口②:sparkline)。
- ⚠️ 没有 `DXY`,是**广义美元 `DTWEXBGS`**。

### Signal — `{ key, label, value, unit, group }`（新)
代码计算的技术指标,前端按 `group` 分节、按 `unit` 格式化。`value` 一律是**原始数值**,前端负责显示:

| `unit` | 含义 | 格式化示例(value → 显示) |
|---|---|---|
| `pct` | 带符号百分比 | `0.0837 → +8.4%` |
| `pct0` | 无符号百分比 | `0.164 → 16.4%` |
| `bp` | 带符号基点 | `-7 → -7bp` |
| `z` | z 分数 | `0.10 → z=0.10` |
| `corr` | 相关系数(−1~1) | `-0.62 → -0.62` |
| `yield` | 利率电平 | `4.49 → 4.49%` |

`group ∈ trend(趋势) | momentum(动量) | vol(波动与风险) | rates(利率与通胀) | dollar(美元) | cross_asset(跨资产相关) | range(52周分位)`。

真实样例(节选):
```jsonc
"signals": [
  { "key": "SP500_px_vs_ma200", "label": "标普500 距MA200", "value": 0.0837, "unit": "pct", "group": "trend" },
  { "key": "DGS10_chg_20",      "label": "10Y 近20日",      "value": -7,     "unit": "bp",  "group": "momentum" },
  { "key": "VIXCLS_z_252",      "label": "VIX z分数",        "value": 0.10,   "unit": "z",   "group": "vol" },
  { "key": "DGS2_level",        "label": "2Y 收益率",         "value": 4.20,   "unit": "yield","group": "rates" },
  { "key": "corr_XAUUSD_DFII10_60", "label": "黄金~实际利率", "value": -0.46,  "unit": "corr","group": "cross_asset" }
]
```
> 维护点:这份列表的「单一事实源」在后端 `features.FEATURE_VIEW`,增删指标改那里即可,前端 data-driven 自适应。

### regime — `{[label]: string}`（新)
代码判定的市场状态,适合做小标签/徽章。键与示例值:
```jsonc
"regime": {
  "equity_trend": "above_ma200",          // 股票趋势:above_ma200 / below_ma200
  "vol_regime": "mid/elevated",           // 波动:low|mid|high (+/elevated|/easing)
  "curve": "normal/flattening",           // 曲线:inverted|flat|normal (+/steepening|/flattening)
  "real_rate": "rising",                  // 实际利率:rising|falling|flat
  "inflation_expectations": "falling",    // 通胀预期:rising|falling|flat
  "dollar": "weak/diverging"              // 美元:strong|weak (+/diverging)
}
```

### Hypothesis — `{ ifThen, invalidation, asset, direction, horizon, confidence, keyFactors }`（已升级为「预测卡」）
- `asset ∈ NASDAQCOM | XAUUSD | DTWEXBGS | DGS2`(固定 roster:纳指/黄金/广义美元/2Y;**每天恰好 4 条,一方向一条**)。
- `direction ∈ up | down | flat`;`horizon ∈ next_1d | h_5d | h_20d | h_60d`(次日/5日/20日/60日)。
- `confidence`:0~1;`keyFactors`:`string[]`,驱动该预测的特征。
- `ifThen` / `invalidation`:人读的「若 X 则 Y」+ 可度量失效条件。
- 建议渲染成**预测卡**:`资产 + 方向箭头 + 期限 + 信心`(头)/ ifThen(主)/ ✕ 失效条件 / key_factors 小标签。

### Impact — `{ asset, watch, dir }`；`dir ∈ up | down | watch`(箭头 ↑/↓/·)。
### Review — `{ ifThen, status, note }`；`status ∈ held(✓兑现) | invalidated(✕失效) | open(○待观察)`。
### News — `{ title, source, cat, assets, dir, link }`
- `cat ∈ fact | read | both | noise | null`(后端已**过滤掉 noise 与无 link 项**,故实际基本只有 fact/read/both;`null`=无 LLM 时未分类)。
- `link`:**真实数据稳定有**(后端保证),做成**可点按钮 → 新标签页打开源新闻**;并显示 `source` 与 `assets` 小标签。

---

## 2. 设计稿(`frontend/desgin/`)↔ 后端字段映射

| 设计稿小节(前端设计文档.md) | 后端字段 | 备注 |
|---|---|---|
| §5 时间线(tone 染色) | `briefs[].tone` + `date` | ✅ 直接可用 |
| §6.1 抬头 | `date` / `weekday` / `issue` / `time` | ✅ |
| §6.2 Headline | `headline` | ✅ |
| §6.3 指标表 MARKET DATA | `metrics[]` | ⚠️ 改 **10 行 data-driven**;去掉 DXY/固定6行;sparkline 见缺口② |
| §6.4 四层简报 | `facts` / `reads` / `hypotheses` / `impacts` | 假设层升级为**预测卡**(新字段) |
| §6.5 假设复盘 REVIEW | `reviews[]` | ✅ 逐条 held/invalidated/open |
| §6.6 新闻 NEWS | `news[]` | 加**链接按钮**;噪音 badge 基本用不上(已滤) |
| §6.7 页脚 | `model` / `date` | `★ <date> · GEN <model> ★` |
| **(设计稿无此节)技术指标面板** | `signals[]` + `regime` | **新增板块**:按 group 分节展示技术指标 + regime 徽章 |

---

## 3. 相对旧设计 / 旧前端的净变化

**加**
- **技术指标面板**(`signals` 按 group 分节 + `regime` 徽章)—— 设计稿原本没有,是本次核心新增。
- **预测卡**:假设层带 `asset/direction/horizon/confidence/keyFactors`。
- **新闻链接按钮**(新标签页打开)。

**删 / 降级**
- `DXY` → 广义美元 `DTWEXBGS`;固定 6 行 → 动态 10 行。
- 噪音 badge:后端已过滤 noise,前端无需重点处理(保留兜底样式即可)。
- **命中率 / track-record(`track.js`)**:见 §4 缺口③,**先不做**。

---

## 4. 三个缺口的状态

- **① 技术指标面板 — ✅ 数据已就绪**:`signals` + `regime` 已落进 `briefs.json`,可以直接按 §1 规格渲染。
- **② Sparkline 走势线 — ⏳ 待定**:后端**只给 `value`+当日 `change`,没有走势序列**;旧前端的走势线是合成装饰。要画真实 sparkline 需后端给每个 Metric 加 `spark: number[]`(最近 ~20 收盘)——尚未决定。**在后端给序列前,指标表先不画 sparkline**(设计稿 Tweaks 本就有开关)。
- **③ 命中率 / track-record — ⛔ 延后(= V2 评估层)**:设计稿 `track.js` 假设后端产出「每日 score + grade + 月/季/年命中率」,但后端**不产**——它是 V2-S3 评估层(L4)的产物,尚未实现。**红线:在真打分跑出来前,前端绝不显示任何「命中率」数字**(否则就是编的)。这块整体推迟到 V2 eval 落地后再接。
  - 注:`reviews[]`(逐条 ✓/✕/○ 复盘)≠ 命中率统计;前者已有、可展示,后者是聚合统计、未有。

---

## 5. 技术约束 / 注意事项

- **完全 data-driven**:渲染只依赖 `briefs.json` 字段;**忽略未知字段**(后端会持续加字段,如未来的 `spark` / eval 标签)。
- **空态**:`reviews` 空 → 复盘节隐藏;历史回填的天 `news` 可能为空(默认不带新闻,防偷看未来)→ 新闻节空态;`signals`/`regime` 理论上恒有,但也要容空。
- **明暗主题**:跟随系统 + 手动切换,色彩走 CSS 变量(见设计稿 §7.2 配色表)。
- **字体自托管**(@fontsource,不走 Google CDN,符合纯静态/离线)。
- **纯静态部署**:产物可挂 GitHub Pages / 任意静态托管;数据通过 fetch `briefs.json`。
- 数据来源:构建期把 `data/briefs.json` 拷进前端 public(旧前端有 `scripts/copy-data.mjs` 可参考)。

---

## 6. 建议构建顺序

1. **契约层**:照 §1 写新 `types.ts`(含 `Signal`/`regime`/预测字段/`news.link`),作为前端单一事实源。
2. **骨架 + 主题**:页眉 / 三段式布局 / 明暗主题 / 时间线(tone 染色)。
3. **小票主体**:抬头 → headline → 指标表(10 行,先不画 sparkline)→ 四层(预测卡)→ 复盘 → 新闻(带链接按钮)→ 页脚。
4. **技术指标面板**:`signals` 按 group 分节 + `regime` 徽章(本次新增,数据已就绪)。
5. **Tweaks / 响应式 / 空态**;命中率板块**留空位**,等 V2 eval。

> 后端契约若再变(如加 `spark` 序列、eval 标签),回到本文件 §1 更新,再让前端跟进。
