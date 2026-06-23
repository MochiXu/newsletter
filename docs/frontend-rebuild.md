# 前端重建指南 · 忠实复刻 `frontend/desgin` 的 3 页 SPA

> **权威依据 = 设计实现** `frontend/desgin/resource/市场走势简报.dc.html`(顶部 `<x-dc>` = 结构/CSS;底部 `<script data-dc-script>` 的 `class Component` = 全部状态/渲染/交互),数据契约见同目录 `briefs.js`/`track.js`/`timeline.js`。
> `support.js` 是通用 DC 模板引擎,**不移植**(React 已替代)。
> 本文件把设计的真实逻辑抽成可直接照建的规格,并标出与后端真实数据的对齐方式与三个落地决策。

---

## 0. 三个落地决策(2026-06-22,用户拍板)

1. **三页全建**(简报/时间线/命中率);后端不产的数据(命中率打分、月/季/年区间聚合)用**空态/「评估层未就绪(V2)」**呈现,**绝不造假数字**。
2. **后端已加 30 点真实价格序列**(`Brief.priceSeries`,资产 = 纳指/黄金/广义美元/US10Y/VIX;**无 BTC/DXY**,按宏观聚焦)→ 用来画设计的「PRICE 30D 可交互价格图」。
3. **后端独有的 signals/regime/预测富字段**(设计稿没有位置)→ **用设计同款暖纸卡片视觉新增承载**:简报页加 SIGNALS 卡(regime 徽章 + 29 条技术指标分组折叠);HYPOTHESIS 卡升级为预测卡(资产/方向/期限/信心/keyFactors)。

---

## 1. 技术栈与工程骨架

- **React 18 + Vite + TS**,纯静态。`base:'./'`(可挂任意子路径)。
- 字体自托管(`@fontsource/ibm-plex-mono` + `@fontsource/noto-sans-sc`),不走 CDN。
- 构建期 `scripts/copy-data.mjs` 把仓库根 `data/briefs.json` 拷进 `public/data/`,前端 fetch。
- dev 端口 5179;node 经 nvm。

---

## 2. 视觉契约(CSS 变量 + 关键技巧,全部进 theme.css)

两套调色板,`[data-theme=light|dark]` 切换,`auto` 时用 `@media (prefers-color-scheme)`。

| 变量 | light | dark |
|---|---|---|
| `--bg` | `#e7ddc9` | `#16130f` |
| `--paper` | `#fdfaf2` | `#221c15` |
| `--paper2` | `#f3ebd9` | `#2b241b` |
| `--ink` | `#2b2018` | `#ece2cf` |
| `--ink2` | `#8a785b` | `#9a8a6f` |
| `--faint` | `#d6c9af` | `#3c3326` |
| `--hair` | `#ece2cd` | `#2c2618` |
| `--accent` | `#c0612f` | `#e0824a` |
| `--up` | `#2f7d50` | `#5bc486` |
| `--down` | `#c0432a` | `#e8694e` |
| `--warn` | `#c79a2c` | `#d8b24a` |
| `--blue` | `#3a6ea5` | `#7aa6dd` |
| `--shadow` | `0 20px 50px -26px rgba(70,48,18,.55)` | `0 26px 60px -30px rgba(0,0,0,.78)` |

字体:`--mono:"IBM Plex Mono",ui-monospace,...`;`--sans:"Noto Sans SC","IBM Plex Sans",system-ui,...`。**分工是设计灵魂:mono 管一切数字/日期/标签/刻度,sans 管中文正文/标题。**

关键 class:
- **`.mb-card`/纸纹**:`background:var(--paper)` + `background-image:var(--panel-tex)` + `background-size:5px 5px` + `box-shadow:var(--shadow)`。`--panel-tex` 由 JS 按 paperTexture 开关注入(开 = `radial-gradient(color-mix(in srgb,var(--faint),transparent 72%) .5px,transparent .6px)`,关 = `none`)。
- **`.mb-punch`**(小票撕齿边):双层 radial mask + `mask-composite:exclude`:
  ```css
  -webkit-mask-image: radial-gradient(circle 5px at 7px 0,#000 99%,#0000 100%),
    radial-gradient(circle 5px at 7px 9px,#000 99%,#0000 100%), linear-gradient(#000,#000);
  -webkit-mask-size: 14px 9px,14px 9px,100% 100%;
  -webkit-mask-repeat: repeat-x,repeat-x,no-repeat;
  -webkit-mask-position: top,bottom,0 0;
  -webkit-mask-composite: xor; mask-composite: exclude;
  ```
  `Card` 组件 `punch` prop 控制(`<Card punch>`)。**简报页所有卡片**(数据卡 + AI 四层 + 复盘)与时间线小票都开打孔。
- **`Tooltip` 组件**(`components/Tooltip.tsx`):统一 hover 提示。内容 `createPortal` 到 `#mb-root`(非 transform 祖先)用 `position:fixed`,故①不被 `mb-punch` 的 mask 裁剪 ②不受 `receiptIn` 残留 transform 漂移。水平夹取防溢出、靠顶翻到下方;**词条跨行(getClientRects>1)时改用鼠标位置**定位。信心标注 / regime 徽章 / 术语高亮 / 影响层代码都复用它。
- **`.mb-scroll`**:细滚动条(thin / `--faint` thumb / hover `--ink2`)。
- keyframes:`receiptIn{from{opacity:0;translateY(12px)}to{opacity:1;translateY(0)}}`、`mbpulse{0%,100%{opacity:.5}50%{opacity:.85}}`。`@media (prefers-reduced-motion:reduce){*{animation/transition .01ms}}`。
- 根容器 `transition: background .35s, color .35s`。
- 圆角:卡片/小票无圆角;段控件容器 9 / 内按钮 7;徽章 pill 20;新闻标签/格子 2–4。

**Tweaks**(浮层面板,设计文档 §9):`accent`(色)/`showSparklines`(布尔)/`paperTexture`(布尔),持久化到 localStorage。

---

## 3. 状态 / 路由 / 响应式

state:`route`(hash 解析)、`themeMode('auto'|'light'|'dark', localStorage key=mb_theme)`、`selectedModel`(全局多模型选择,默认主模型;切换器在 Header 右上,`allModels(briefs).length>1` 才显示)、`chartAsset('nasdaqcom')`、`chartHover(null|0..n-1)`、`tlHover/tlSelected/tlExpanded`、`isMobile(innerWidth<760)`、`tweaks`。

**hash 路由表**(`#/` 去前缀按 `/` 分段):
- 空 → `{page:'brief'}`(最新一刊)
- `brief/<id>/<from>`:id 形态推粒度(`\d{4}-\d{2}-\d{2}`=day,`-Q\d`=quarter,`-H\d`=half,`\d{4}-\d{2}`=month,`\d{4}`=year);`from∈timeline|track` 决定返回条目标
- `timeline/<gran>`:gran∈day/month/quarter/half/year(默认 day)
- `track/<mode>/<period>`:mode∈month/quarter/year/all(默认 year);也接受 `2026-Q2`/`2026-06`/`2026` 自动推断
- `nav(hash)` = 改 `location.hash`;`hashchange` → 重解析 + 清 chartHover/tlHover/tlSelected。

**响应式**:唯一 JS 断点 `innerWidth<760` → isMobile;其余靠 flex-wrap + flex-basis/min-width。

---

## 4. 页面结构

根 `div[data-theme]`(min-height 100vh,padding 30px 22px 72px)→ `max-width:1080px` 居中。
- **页眉**:左标题块(`DAILY MACRO BRIEF` mono accent / `市场走势简报` 27px·700 / 副标题);右主题段控件(自动/浅色/深色)。
- **一级导航 tab**(下边框):`简报·Briefing` / `时间线·Timeline` / `命中率·Track Record`,选中 `border-bottom:2px solid accent` + 700。
- 三页 `isBrief`/`isTimeline`/`isTrack` 互斥。

### 4.1 简报页(`brief`)
- 钻入态(route.date 存在)顶部**返回条**:`‹ 时间线`/`‹ 命中率` + 虚线 + 右 `第 N 刊 · DETAIL`。
- 未加载 → 520px `mbpulse` 骨架。
- **日详情**(`isBriefDay`,取 `briefs[routeIdx]`):
  - 头:`MACRO BRIEF · {weekday} · 第{issue}刊` / 大号 mono 日期(34px,= 美东交易日)+ 浅色时区标签 `tzLabel(brief.tz)`(如「美东」)/ 下一行浅色「美股收盘 · 本地 {时刻} · {时区}」(`usCloseLocal`,锚 16:00 ET 收盘换算到浏览器时区)/ headline(17px·700)。**发布时间不再显示在头部**(歧义「07:00 CST」已去)。右侧命中率徽章 **仅 hasScore 时**(后端无 track → 不显示)。
  - **声明式两列排版**(BriefPage 一处定义左/右两个区块数组,顺序即布局;两列等宽 `flex:1 1 360px` + flex-wrap → 宽屏两列、窄屏自动并一列,无手写断点)。所有区块都是打孔小票(`<Card punch>`)。AI BRIEF 四层是 4 个**独立面板**(`FactsPanel/ReadsPanel/HypothesisPanel/ImpactPanel`,从 AiBrief.tsx 分别导出),可跨列自由摆放:
    - **左栏**:① MARKET DATA(§5.1)② PRICE 30D 价格图(§5.2)③ **SIGNALS 技术指标**(§5.6)④ **HYPOTHESIS 假设层**(§5.4,技术指标下)
    - **右栏**:① FACTS 事实层 ② INTERPRETATION 解读层 ③ IMPACT 影响层(§5.4)④ **NEWS 新闻**(§5.3,影响层下,缺失自动隐藏)⑤ REVIEW 复盘(`hasReviews` 才显,§5.5)
  - 页脚:`...NOT INVESTMENT ADVICE · GEN {modelLabel(activeModel)}`(当前视图模型)。
- **区间详情**(`isBriefAgg`):后端无聚合 → **空态卡**「区间聚合待 V2 评估层」。

### 4.2 时间线页(`timeline`)
- 头:`TIMELINE·时间线` + granNote;右**粒度段控件** 日/月/季/半年/年。
- 主行(桌面 flex gap30,窄屏竖排):
  - 左 `tlList`(`.mb-scroll`,桌面 `flex:0 0 266px` + 竖轴线 + 上下渐隐 mask;窄屏横向胶囊滚动):每行圆点(toneCol)+ 主标签(日 `MM.DD`/区间 label)+ 次标签 + 桌面 headline(2 行截断)。桌面 hover 预览(tlHover)/click 锁定(tlSelected);窄屏仅 click。激活行 `paper2` 底 + 圆点放大双 ring。
  - 右小票概览(`width:min(430px,100%)` `.mb-punch`):票头(居中 mono 日期 + 命中徽章[无则省])→ headline → MARKET DATA(sparkline 高 24)→ THE CALL(假设 ifThen)→ **可展开 NEWS**(▾ 旋转)→ 票脚「完整四层/复盘 见详情 ↗」。右上「详情 →」按钮 → `#/brief/<date>/timeline`。
- **day 粒度用真实 briefs**;**month/quarter/half/year → 空态**「区间聚合待 V2」(后端无 PERIODS)。

### 4.3 命中率页(`track`)
- 头:`TRACK RECORD·命中率` + 维度段控件 月度/季度/年度/ALL。
- **后端无 track 打分 → 整页空态**:暖纸卡居中,`评估层未就绪(V2)` + 一句说明(逐条复盘 ✓/✕/○ 已在简报页 REVIEW;聚合命中率统计待 V2 评估层 backfill+scoring 落地)。维度 tab 仍可点但都显示同一空态。
- (设计原图:年热力图 / 月日历+折线 / 季度 / ALL 柱状 + 浮动 tooltip——**待 V2 评估层产出 `track.json` 后按 §7 算法接入**,本期不画假数据。)

---

## 5. 各区块渲染规格

### 5.1 MARKET DATA(指标表)
`metrics` data-driven(后端 10 行)。每行 grid `48px 1fr 60px 48px 58px`(5 列),虚线下边框:标签(mono `--ink2`)/ sparkline / 值 `fmtVal` / 单日Δ `fmtChg` / 单日% `fmtPctChange`(返回 `string|null`,空显 `—`;后两列同用色 `colorFor(change)`)。sparkline 受 showSparklines 控制。
- `fmtVal`:yield→`v.toFixed(2)%`;spread→`round(v*100)bp`;index→`v.toFixed(1)`;price→`toLocaleString(maxFrac 1)`。
- `fmtChg`:带 `+`;yield/spread→`round(c*100)bp`;index→`c.toFixed(1)`;price→`|c|<10?toFixed(1):round`。

### 5.2 PRICE 30D 价格图(可交互)
资产 tab = `priceSeries` 的 key(纳指/黄金/广义美元/US10Y/VIX,中文 label)。`viewBox 320×110` pad9:
- `xs[i]=W*i/(n-1)`;`ys=H-pad-(H-2pad)*(v-mn)/rg`。折线 `chartLine`,面积 `'0,H '+line+' W,H'` opacity.07。色 `chg>=0?up:down`,line strokeWidth1.6,`preserveAspectRatio=none` + `vectorEffect:non-scaling-stroke`。
- hover:`onChartMove` 取 `getBoundingClientRect`,`idx=round(cx/width*(n-1))` clamp;十字线 `<line>` opacity `hover?.55:0`;游标点用绝对定位 HTML span(`left=xs/W%`,`top=ys/H%`,7px 圆)。读数行:`fmtChartVal(kind,v)` + 该点 date。`onChartLeave`→null(看末点)。触屏 `e.touches` + `touch-action:none`。
- 底部刻度:起始 date / `30 交易日` / 末 date。

### 5.3 NEWS(类目计数 + 多标签,列表常显)
- **类目(影响资产)计数常显**:把 `news[].assets`(多值)汇总成 chip「资产 N」按条数降序(一条多资产则每个都计);点 chip 按该类目**筛选**(命中资产标签高亮 accent),筛选时显示「仅看 X · N/总 条(点标签取消)」。
- **列表常显**(不折叠;早先的展开/收起已去掉)。
- 每条:`catMap` 分类徽章(fact 事实/read 解读/both 事实+解读/noise 噪音)+ **标题(后端有 link → `<a target=_blank rel=noopener>` + ↗)** + 方向 `dirInfo(dir)`;次行来源(mono)+ 多个 assets chips。noise 标题用 ink2。
- **缺失自动隐藏**:`news` 为空 → 组件返回 null(数据缺失则不展示)。复用现有 `news.assets`,无后端改动。

### 5.4 AI BRIEF 四层(4 个独立打孔面板,渲染**当前选中模型的 view**,见 §3 模型切换)
- **FACTS / INTERPRETATION**:正文用 `renderRichText(text, figures)` = ① figures 按 dir 给数字上色 ② 已知术语(regime 的 `key=value`/复合 token + 行话 higher-for-longer/熊平/牛陡/倒挂)加**虚下划线 + hover 中文解释**(`glossary.ts` 单一源;保留 LLM 原文措辞,不改 prompt)。
- **HYPOTHESIS=预测卡**:多模型时上方先给一行**跨模型共识**(`consensus`:资产 + 多数方向 + `agree/n 认同` + 均值信心 + 各方向票数;平票=分歧→横盘)。每条预测卡:头(资产中文 + 方向箭头↑↓→ + 期限 + 信心 % + 信心条 + **信心 tooltip**:模型自评、未校准、非真实概率)/ ifThen / `✕ 失效`+invalidation / **关键因子 chip**(`KeyFactorChip`:常显短标签 `label`,完整读数 `detail` 进 hover,`detail≠label` 才挂 Tooltip)。资产映射:NASDAQCOM→纳指,XAUUSD→黄金,DTWEXBGS→广义美元,DGS2→美债2Y。
- **IMPACT**:每条 `dirInfo(dir)` + **资产中文名**(`im.asset`,后端已规范化)+ watch;若 `im.code` 有英文代码 → 放 hover。

### 5.5 REVIEW 复盘(hasReviews 才显)
状态:held{✓,up,已兑现} / invalidated{✕,down,已失效} / open{○,accent,待观察}。18px 圆描边徽标 + ifThen + 状态标签 + note。

### 5.6 SIGNALS 技术指标(新增卡,设计同款视觉)
- **regime 徽章**常显:6 个 chip(键中文 + 值翻译;token map:above_ma200→MA200上方 等,`/` 拆开 `·` 连),每个 chip 包 `Tooltip`,hover 出该维度的中文解释(`glossary.regimeTooltip`)。
- **29 条 signals 按 group 折叠**(默认收起):开关行「展开技术指标 · N 项」;展开后按 7 组(trend趋势/momentum动量/vol波动与风险/rates利率与通胀/dollar美元/cross_asset跨资产相关/range52周分位)列:label … 值 `fmtSignal`。带符号单位(pct/bp/z/corr)按正负染色,电平(pct0/yield)中性。

---

## 6. 颜色/方向工具(贯穿全站)
- `colorFor(c)`:c>0 up / c<0 down / 0 ink2。
- `dirInfo(d)`:up{↑,up} / down{↓,down} / 其他{·,ink2}。
- `toneCol(t)`:risk-on up / risk-off down / 其他 ink2(时间线圆点)。
- `fmtSignal(unit,v)`:pct→`±(v*100).1%`;pct0→`(v*100).1%`;bp→`±round`;z→`z=v.2`;yield→`v.2%`;corr→`v.2`。
- `signalSigned(unit)`:pct/bp/z/corr 为真(染色)。

---

## 7. 几何算法(SVG,纯坐标映射,末点用 HTML span 避免椭圆)
- `sparkGeom(vals)`:viewBox100×30 pad4;`x=pad+(W-2pad)*i/(N-1)`,`y=H-pad-(H-2pad)*(v-min)/range`;返回 points + dotX/dotY。
- 价格图:见 §5.2。
- `miniLine(series,{W,H,padX6,padY14})`:y 域 `lo=max(0,min-8)`,`hi=min(100,max+8)`;60/75 分级虚线(`t∈[lo,hi]` 才画);用于 track 月线{380,150}/季月线{220,70}。
- `buildCalendar`(周一首,有 brief 加 `1.6px solid ink` 描边)、`buildMonthBlocks`(年热力图,周日首列网格,gradeCol 着色)、ALL 柱状(每日一柱 height=score%)。
- `gradeCol`:green up / yellow warn / red down / 其他 hair;`accColOf`:≥75 up / ≥60 warn / else down。
- **以上 track 几何在 V2 评估层产出 `track.json` 后才接入;本期 track 页为空态。**

---

## 8. 数据契约(= 真实 `data/briefs.json`)与后端映射

顶层 `{model, generatedAt, briefs:[Brief]}`(briefs 倒序)。Brief 字段:
**脊柱(模型无关)**:`date/weekday/issue/time/tz`(`tz` = `date` 所属时区 IANA,默认 `America/New_York`;前端据此在大日期旁标「美东」并把美股收盘换算到浏览器本地)· `metrics[key,label,value,change,kind,spark:[{date,value}]]` · `signals[key,label,value,unit,group]` · `regime{}` · `priceSeries{key:[{date,value}]}`(5 资产×30 点)· `reviews[ifThen,status,note]` · `news[title,source,cat,assets,dir,link]`。
**多模型**:`models[]`(模型 id,有序,[0]=主)· `views{modelId: ModelView}` · `consensus[{asset,direction,votes{up,down,flat},n,agree,meanConfidence,actual?}]`(≥2 模型才有)。
`ModelView` = `tone/headline · facts[{tag,text,figures:[{t,dir}]}] · reads[同]`(`renderRichText` 按 figures 给数字上色 + 给已知术语加 hover)`· hypotheses[ifThen,invalidation,asset,direction,horizon,confidence,keyFactors:[{label,detail}],actual?] · impacts[{asset(中文名),watch,dir,code(英文代码,可空→hover)}]`。`keyFactors` 每条 = 短标签(`label`,chip 常显)+ 完整读数(`detail`,hover);后端由 LLM 扁平串 `'label|detail'` 解析。`Actual` = `{status(pending|settled),realizedDir,realizedText,hit,resolvedDate,note}`:预测账本(`data/predictions.csv`)到 horizon 期满后**代码**算真实走势 + 命中、LLM 写 `note`,由 `render.apply_actuals` join 进所有保留简报;未到期 → 前端沙漏。预测卡 + 共识行均显示实际结果。
前端用 `viewOf(brief, selectedModel)` 取当前视图(选中模型缺失则回退主模型);切换器选项 = `allModels(briefs)`(>1 才显示)。所有展示文本后端已过 `textnorm.normalize_text`(英文标点 + 中英空格 + 数字单位上色);影响层 `asset` 经 `render._split_asset` 规范成中文名 + 提取 `code`。

- **设计有、后端无**:`q`(nasdaq/btc 报价)、BTC/DXY 价格序列 → 不做(纳指已在 metrics;BTC 不加)。`track`(命中率)、`PERIODS`(区间聚合)→ 空态待 V2。
- **后端有、设计无**:`signals`/`regime`/预测富字段/`news.link` → 决策 3:新增卡片 + 升级预测卡 + 链接。
- 完全 data-driven,忽略未知字段;空态:reviews 空→隐藏复盘;signals/regime 容空;news 空→隐藏。

---

## 9. 构建顺序
1. 骨架 + theme.css(变量/punch/纹理/keyframes)+ 字体 + copy-data。
2. 基础:types.ts(契约)/ lib/format.ts(fmt+颜色)/ lib/geometry.ts / hooks(useHashRoute/useTheme/useIsMobile)/ Card+SectionHead+Header+NavTabs。
3. 简报页(MARKET DATA / PRICE 图 / SIGNALS 卡 / NEWS / AI BRIEF 预测卡 / REVIEW)。
4. 时间线页(day 真实 + 区间空态)。
5. 命中率页(空态)。
6. Tweaks 浮层 / 响应式 / 空态;preview 实测明暗+窄屏。
> 命中率/区间聚合的真实接入,等 V2 评估层产出 `track.json`/`periods.json` 后回到 §4.3/§7。
