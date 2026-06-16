# 展示平面(Frontend)· 开发计划

> 第三个「平面」:把智能平面产出的每日简报渲染成「暖纸小票」阅读器。
> 设计理念见 [`frontend/desgin/design.md`](../frontend/desgin/design.md);本文聚焦**怎么落地**——技术栈、数据接缝、目录结构、组件拆分、里程碑。

---

## 1. 目标与范围(本轮)

- **本轮只做一件事**:把设计稿的「小票阅读器」**1:1 还原**成一个真实可维护的前端工程,并接上**真实数据**。
- 设计稿现在是设计工具导出的私有组件格式(`x-dc` / `DCLogic`,见 `frontend/desgin/resource/*.dc.html`),**不是生产技术栈**,需要用 React 重建。
- **不做**:数据库、HTTP 后端接口、鉴权、付费墙。前后端数据交互**本轮只走本地文件**(见 §3),工程化留到以后。
- 还原范围 = 设计稿信息架构全集:页眉 + 主题切换、左栏时间线(悬停预览/点击锁定)、小票卡片(抬头 → headline → 指标表+sparkline → 四层 AI 简报 → 假设复盘 → 新闻分类 → 条形码页脚)、Tweaks 三开关、明暗主题、加载/空态。

延伸功能(详情走势图、跨日搜索、PDF 导出、多模型对比、失效自动回标)见设计稿 §11,**本轮不做**,但数据契约与目录结构要给它们留位置。

## 2. 技术栈(已与作者对齐)

| 维度 | 选型 | 理由 |
|---|---|---|
| 框架 / 构建 | **React 18 + Vite + TypeScript** | 设计稿逻辑天然是 React 形态(state/props/生命周期),迁移成本最低;Vite 零配置、热更快;TS 适配项目一贯的严谨工程风格;路线图功能(详情图表/搜索/多模型对比)好扩展。 |
| 样式 | **原生 CSS + CSS 变量**(配 CSS Modules 做组件隔离) | 设计稿已围绕 `--bg/--paper/--accent/...` 变量 + `data-theme` 做明暗主题,直接复用全部色彩 token 与 0.35s 过渡,所见即所得,零额外依赖。 |
| 数据源 | **Python 导出 `data/briefs.json`**,前端 `fetch` 静态文件 | 最自然的「本地文件接缝」,且不算数据库/服务端工程(见 §3/§4)。 |
| 字体 | Google Fonts:`IBM Plex Mono` + `Noto Sans SC` | 等宽承载数据/日期/标签,无衬线承载中文正文,与设计稿一致。 |
| 包管理 | 跟随作者环境(`pnpm` 优先,`npm` 兜底) | —— |
| Lint / 格式化 | ESLint + Prettier(默认规则起步) | 轻量,不过度配置。 |

**与项目整体哲学的呼应**:后端坚持「最小依赖、git-as-database」。前端同样克制——不引 UI 组件库、不引状态管理库(单页小票用 React 自带 `useState` 足够)、不引图表库(sparkline 用原生 SVG `polyline`,设计稿已有算法)。

## 3. 数据接缝:`data/briefs.json`

前后端唯一接缝是一个**静态 JSON 文件**(沿用后端「共享数据文件协作、互不直接调用」的范式)。

```
[ 智能平面 · Python ]
   brief 内存 dict + observations.csv + hypotheses.csv
                │  render_json()(新增)
                ▼
        data/briefs.json   ← 新接缝(数组,按日期倒序,最新在前)
                │  构建期拷贝 / dev 期代理
                ▼
        [ 展示平面 · React ]  fetch('/data/briefs.json')
```

为什么是 JSON 而不是让前端解析 Markdown:智能平面在 `brief.py` 内存里**已经持有**前端要的全部结构化字段(`headline / facts / interpretation / hypotheses / impact / news`),渲染 Markdown 时把它丢掉了。直接序列化这个 dict 比让前端反向解析 Markdown 健壮得多(后者字段对不齐、易碎)。

### 3.1 JSON 契约(草案 v1)

顶层是 `{ model, generatedAt, briefs: Brief[] }`,`briefs` 按日期倒序。单日 `Brief`:

```jsonc
{
  "date": "2026-06-17",          // 来自 run_date
  "weekday": "周三",              // 由 date 推导
  "issue": 143,                  // 交易日序号(累计计数)
  "time": "07:00 CST",           // 常量
  "tone": "neutral",             // risk-on | risk-off | neutral(派生,见 §6 开放问题)
  "headline": "……",             // brief.headline
  "metrics": [                   // 固定 6 行,顺序:US10Y/US2Y/2s10s/VIX/DXY/GOLD
    { "key": "us10y", "label": "US10Y", "value": 4.48, "change": 0.0, "kind": "yield" }
    // kind ∈ yield | spread | index | price —— 决定数值/变化量格式化与单位
  ],
  "facts":      ["……"],          // brief.facts
  "reads":      ["……"],          // brief.interpretation
  "hypotheses": [ { "ifThen": "……", "invalidation": "……" } ],     // brief.hypotheses
  "impacts":    [ { "asset": "黄金 XAU", "watch": "……", "dir": "watch" } ], // brief.impact(+dir,见缺口)
  "reviews":    [ { "ifThen": "……", "status": "held", "note": "……" } ],   // hypotheses.csv 当日复盘
  "news": [
    { "title": "……", "source": "Fed", "cat": "fact",
      "assets": ["美债","美元"], "dir": "·", "link": "https://…" }
    // cat: 事实→fact 解读→read 事实+解读→both 噪音→noise
  ]
}
```

### 3.2 字段来源映射

| 前端字段 | 后端来源 | 备注 |
|---|---|---|
| `date / weekday / time / issue` | `run_date` + 派生 | weekday 由日期算;issue = 累计交易日序号 |
| `metrics[].value` | `observations.csv` | 按 series 选 6 个:DGS10/DGS2/T10Y2Y/VIXCLS/DX-Y.NYB/GC=F |
| `metrics[].change` | `observations.csv` 相邻 run_date 差 | 当日值 − 上一交易日值 |
| `metrics[].kind` | series 固定映射 | 收益率→yield、利差→spread、VIX/DXY→index、金价→price |
| `headline / facts / reads` | `brief.headline / .facts / .interpretation` | 直接搬 |
| `hypotheses[]` | `brief.hypotheses[{if_then,invalidation}]` | 改名 `ifThen` |
| `impacts[]` | `brief.impact[{asset,watch}]` | **缺 `dir`**,见缺口 |
| `reviews[]` | `hypotheses.csv` 当日 resolved + 仍 open | status: held/invalidated/open |
| `news[]` | `brief` 内 `news`(merge 后) | cat 中文→英文枚举;**缺 `dir`** |
| `model` | provider(env) | 页脚签名 `GEN <model>` |

### 3.3 数据缺口(契约里先留默认值,后端按需补全)

1. **`tone`(当日基调,染时间线圆点)**:真实数据里没有。先用启发式派生(如 VIX 上行 + 收益率上行 → risk-off;VIX 回落 + 风险资产走强 → risk-on;否则 neutral),后续可让 LLM 直接产出一个 `tone` 字段。**默认 `neutral`**。
2. **`impacts[].dir` / `news[].dir`(方向箭头 ↑/↓/·)**:`brief.impact` 与新闻分类目前不含方向。先**默认 `·`(待观察)**;后续在 `emit_brief` schema 里给每条 impact / 每条新闻加一个 `direction` 字段最干净。
3. **历史回填**:已有的 `2026-06-16 / 06-17` 两天只存了 Markdown,没有结构化 dict。需一次性 backfill(见 §4)。

> 这三处都不阻塞前端开发——前端按契约消费,缺口处显示默认态;后端补全后界面自动变丰富。

## 4. Python 导出适配器

智能平面新增**两个小东西**(纯 stdlib,沿用零依赖约束):

1. **`render.py` 加 `render_json(run_date, obs, brief, news, hyp_rows, meta) -> dict`**:把当前内存里的结构化数据组装成 §3.1 的单日 `Brief`(metrics 的 `change` 需读 observations 历史算相邻差)。
2. **`brief.py` 在写 `.md` 之后,同时写 `data/briefs/<date>.json`**(单日),并刷新聚合的 `data/briefs.json`(全量倒序数组,供前端一次性 fetch)。约几十行,不引入数据库/服务端。
3. **一次性 backfill 脚本** `py/newsletter/export_json.py`:把已有的 `data/briefs/*.md` + 两个 CSV 解析/聚合成首版 `data/briefs.json`,让前端立刻有 ≥2 天真实数据可跑。此后由日常流程增量维护。

> 这步严格属于「给智能平面加一个 JSON 输出口」,不是数据库/接口工程,符合作者「后端工程化以后再说」的边界。先做 backfill 出一版 `briefs.json`,前端即可全程对真实数据开发。

## 5. 前端目录结构

新建 `frontend/app/`(与设计稿 `frontend/desgin/` 平级,设计稿保留作参考):

```
frontend/app/
  index.html
  vite.config.ts
  package.json  tsconfig.json
  public/
    data/briefs.json          # 构建期从 ../../data/briefs.json 拷贝(或 dev 代理)
  src/
    main.tsx
    App.tsx                   # 页眉 + 三段式布局 + 主题/Tweaks 状态
    theme.css                 # :root / [data-theme] 全部 CSS 变量(从设计稿搬)
    types.ts                  # Brief / Metric / News … TS 接口(= §3.1 契约)
    data/loadBriefs.ts        # fetch + 校验 briefs.json
    lib/
      format.ts               # fmtVal / fmtChg(从设计稿搬:yield/spread/index/price)
      sparkline.ts            # makeSpark(确定性 SVG 折线,设计稿已有算法)
      tone.ts                 # tone→色、dir→箭头/色、cat→徽章样式 等映射
    components/
      Header.tsx              # 站标 + 副标题 + 主题 segmented 控件
      Timeline.tsx            # 左栏:倒序交易日,悬停预览/点击锁定
      Receipt.tsx             # 小票容器:撕边 + 抬头 + receiptIn 动画编排
      sections/
        MarketData.tsx        # 6 行指标表 + sparkline
        AiBrief.tsx           # 四层:Facts/Interpretation/Hypothesis/Impact
        Review.tsx            # 假设复盘(空则整段隐藏)
        News.tsx              # 新闻分类徽章 + 资产标签
        ReceiptFooter.tsx     # 免责 + 条形码 + 签名
      TweaksPanel.tsx         # accent / showSparklines / paperTexture
```

设计稿里那些 `makeSpark / fmtVal / fmtChg / colorFor / dirInfo / toneCol / catMap` 都是纯函数,**可直接移植**到 `lib/`,省掉重写。

## 6. 状态与交互(对应设计稿 §5、§8)

- **顶层状态**(`App`):`themeMode`(auto/light/dark,持久化到 `localStorage` 键 `mb_theme`)、Tweaks 三项(`accent / showSparklines / paperTexture`)、`briefs`+`loaded`。
- **时间线选择**:`selectedIdx`(锁定)+ `hoverIdx`(预览),`activeIndex = hoverIdx ?? selectedIdx`——与设计稿一致。悬停淡入预览、离开回锁定、点击锁定。
- **小票切换动画**:`activeIndex` 变化时,对小票元素重放 `receiptIn .42s`(`useEffect` 里清空再设 `animation`,沿用设计稿的 reflow 技巧)。
- **主题**:`data-theme` 属性 + `prefers-color-scheme` 媒体查询联动,0.35s 过渡;`auto` 跟随系统。
- **Tweaks**:`accent` 实时 `setProperty('--accent', …)`;`showSparklines`/`paperTexture` 切换对应渲染。
- **克制动效**:只保留设计稿四处(小票淡入、时间线行高亮、主题过渡、加载呼吸),不加其它。

## 7. 边界状态(对应设计稿 §10)

- 加载中:小票位为 `mbpulse` 呼吸占位块,时间线空。
- 某日无复盘:`Review` 整段隐藏。
- 新闻为空:`News` 仅剩章节头。
- 主题持久化:`localStorage`。
- 窄屏:左右栏垂直堆叠,小票居中,最大宽 442px。

## 8. 里程碑

| 阶段 | 内容 | 产出 |
|---|---|---|
| **F0 数据契约** | 定 `types.ts`;Python 加 `render_json` + backfill 出首版 `data/briefs.json`(≥2 天真实数据) | 前端有真实数据可跑 |
| **F1 脚手架 + 主题** | Vite+React+TS 起项目;搬 `theme.css` 全部变量;页眉 + 主题 segmented 切换 + 持久化 | 空壳页面、明暗可切 |
| **F2 时间线 + 小票骨架** | 左栏倒序时间线(悬停预览/点击锁定)+ 小票撕边/抬头/headline + `receiptIn` 动画 | 能在交易日间切换 |
| **F3 小票内容区** | 指标表+sparkline、四层 AI 简报、假设复盘、新闻分类、条形码页脚 | 小票内容 1:1 还原 |
| **F4 Tweaks + 边界态 + 收尾** | accent/sparkline/texture 三开关;加载/空态;窄屏堆叠;字体与细节像素级对齐设计稿 | 可交付的小票阅读器 |
| **F5(可选)联动后端缺口** | 后端补 `tone` / `dir` 字段,前端去掉默认态 | 时间线染色、方向箭头变真实 |

## 9. 开放问题

1. **`tone` 怎么定**:先启发式(VIX/收益率组合)还是直接让 LLM 产出?——本轮先启发式 + 默认 neutral。
2. **`impacts[].dir` / `news[].dir`**:加进 LLM schema 最干净,但要改 `emit_brief`。本轮先默认 `·`。
3. **`issue` 刊号起点**:设计稿示例从 142 起。需定一个 epoch(某交易日 = 第 1 刊)或直接用累计交易日数。
4. **`briefs.json` 怎么到前端**:dev 期用 Vite 代理读仓库根 `data/briefs.json`,构建期拷进 `public/data/`——两者都不需要服务端;具体取舍 F1 落地时定。
5. **部署**:本轮不涉及(纯静态产物,以后可挂任意静态托管 / GitHub Pages)。

## 10. 后续可拓展(对齐设计稿 §11,本轮不做)

详情走势图(带坐标轴)、跨日关键词/资产搜索、小票导出 PDF/PNG、多模型(DeepSeek/GPT/Claude)同日横向对比、历史假设失效自动回标。目录结构与 JSON 契约已为这些留出扩展位。

---

*对应设计文档:[`frontend/desgin/design.md`](../frontend/desgin/design.md)(设计理念)+ 本文(落地计划)。*
