# 展示平面(Frontend)· 开发计划

> 第三个「平面」:把智能平面产出的每日简报渲染成「暖纸小票」阅读器。
> 设计理念见 [`frontend/desgin/design.md`](../frontend/desgin/design.md);本文聚焦**怎么落地**——技术栈、数据接缝、目录结构、组件拆分、里程碑。

> **决策与现状(2026-06-17 评审后锁定)**
> 1. **范围**:尽量 1:1 还原(含装饰);真实数据不足处用设计稿 9 天 mock 兜底。
> 2. **LLM 字段**:现在就给 `emit_brief` 加 `tone` + 每条 impact/news 的 `direction`(已落地,见 §3/§4)。
> 3. **移动端**:桌面 + 移动**都精修**(不是窄屏堆叠了事)。
> 4. **指标表**:**7 行**(新增「广义美元 DTWEXBGS」,紧邻 DXY,直接展示简报常讲的「广义美元 vs DXY 背离」)。
>
> **对初版计划的几处修正**(原文有误,实现以此为准):
> - 纯函数(`makeSpark/fmtVal/fmtChg/colorFor/dirInfo/toneCol/catMap`)在 [`市场走势简报.dc.html`](../frontend/desgin/resource/市场走势简报.dc.html) 的 `<script data-dc-script>` Component 类里,**不在 `support.js`**(那是设计工具的 dc-runtime,整体弃用、不可移植)。
> - `tone / impacts[].dir / news[].dir` 是**必填**(驱动时间线染色与方向箭头),不是「可选缺口」——后端已产出。
> - 真实 key 是 `reads / impacts / reviews`;`dir` 枚举是 `up | down | watch`(非字面 `·`)。
> - **字体自托管**(`@fontsource`),不走 Google Fonts CDN——与「离线可跑 / 纯静态」一致。
> - 基准参考 = `.dc.html` + `briefs.js`(非 6.6MB 的 standalone 变体)。
>
> **进度**:F0–F4 ✅ 全部完成(后端导出 + 脚手架/主题 + 时间线/小票 + 五节内容 + Tweaks/响应式),
> `npm run build` 通过、明暗/桌面/移动均截图验证;F5(真实数据接管 + 部署)暂不做。

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
| 字体 | **自托管** `@fontsource/ibm-plex-mono` + `@fontsource/noto-sans-sc` | 等宽承载数据/日期/标签,无衬线承载中文正文。**不走 Google Fonts CDN**——构建期打进产物,离线/CI 可跑,与项目「纯静态、最小运行时依赖」一致。 |
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
  "tone": "neutral",             // risk-on | risk-off | neutral;由 LLM 产出,无 LLM 时退 neutral
  "headline": "……",             // brief.headline
  "metrics": [                   // 固定映射 7 行:US10Y/US2Y/2s10s/VIX/DXY/广义美元/GOLD
    { "key": "us10y", "label": "US10Y", "value": 4.48, "change": 0.0, "kind": "yield" }
    // kind ∈ yield | spread | index | price —— 决定数值/变化量格式化与单位
  ],
  "facts":      ["……"],          // brief.facts
  "reads":      ["……"],          // brief.interpretation
  "hypotheses": [ { "ifThen": "……", "invalidation": "……" } ],     // brief.hypotheses
  "impacts":    [ { "asset": "黄金 XAU", "watch": "……", "dir": "watch" } ], // brief.impact.direction 映射而来
  "reviews":    [ { "ifThen": "……", "status": "held", "note": "……" } ],   // hypotheses.csv 当日复盘
  "news": [
    { "title": "……", "source": "Fed", "cat": "fact",
      "assets": ["美债","美元"], "dir": "watch", "link": "https://…" }
    // cat: 事实→fact 解读→read 事实+解读→both 噪音→noise
  ]
}
```

### 3.2 字段来源映射

| 前端字段 | 后端来源 | 备注 |
|---|---|---|
| `date / weekday / time / issue` | `run_date` + 派生 | weekday 由日期算;issue = 累计交易日序号 |
| `metrics[].value` | `observations.csv` | 按 series 选 7 个:DGS10/DGS2/T10Y2Y/VIXCLS/DX-Y.NYB/DTWEXBGS/GC=F |
| `metrics[].change` | `observations.csv` 相邻 run_date 差 | 当日值 − 上一交易日值 |
| `metrics[].kind` | series 固定映射 | 收益率→yield、利差→spread、VIX/DXY→index、金价→price |
| `headline / facts / reads` | `brief.headline / .facts / .interpretation` | 直接搬 |
| `hypotheses[]` | `brief.hypotheses[{if_then,invalidation}]` | 改名 `ifThen` |
| `impacts[]` | `brief.impact[{asset,watch,direction}]` | `direction` 映射为前端 `dir`;枚举 `up/down/watch` |
| `reviews[]` | `hypotheses.csv` 当日 resolved + 仍 open | status: held/invalidated/open |
| `news[]` | `brief` 内 `news`(merge 后) | cat 中文→英文枚举;`direction` 映射为前端 `dir` |
| `model` | provider(env) | 页脚签名 `GEN <model>` |

### 3.3 数据来源说明(评审后已收口)

1. **`tone`(当日基调,染时间线圆点)**:**已让 LLM 直接产出**(`emit_brief` schema 加 `tone` 枚举 risk-on/risk-off/neutral)。不再用启发式——LLM 本就在写判断当日基调的 headline,由它给最自然;两天停更的收益率上跑启发式只会全塌成中性灰。`brief=None`(无 LLM)时退 `neutral`。
2. **`impacts[].dir` / `news[].dir`(方向箭头 ↑/↓/·)**:**已加进 LLM schema**(impact 每条 `direction`、新闻分类每条 `direction`,枚举 up/down/watch)。`watch` 渲染为 `·`。无 LLM 时缺省 `watch`。
3. **历史回填**:不反解析旧 `.md`(易碎,正是用 JSON 接缝要避免的)。存量两天的观感由 9 天 demo 兜底;真实结构化数据从下一次管线运行起逐日累积进 `data/briefs.json`。
4. **第 7 行广义美元**:`observations.csv` 本就有 `DTWEXBGS`(贸易加权美元);指标映射加这一行即可,无需新数据源。demo 沿用设计稿 6 行(指标长度自适应,不冲突)。

## 4. Python 导出适配器 ✅(F0 已落地)

智能平面新增的 JSON 输出口(纯 stdlib,沿用零依赖约束),均已实现并有单测覆盖:

1. **`render.render_json(run_date, obs, history, brief, news, hyp_rows, issue) -> dict`**:把内存里的结构化数据组装成 §3.1 的单日 `Brief`。`history`(`data.load_all`,全量观测)只用于算 `metrics[].change`(相邻 `run_date` 之差);`brief=None` 时四层留空、tone 退 neutral。7 行指标映射见 `_METRIC_SPECS`。
2. **`brief.py` 写完 `.md` 后**,调 `_write_json_outputs`:写单日 `data/briefs/<date>.json`,并**增量维护**聚合 `data/briefs.json`(按日期 upsert + 倒序 + 按年代序重算 `issue`)。约几十行,不引入数据库/服务端。
3. **`py/newsletter/export_json.py`**:从所有 `data/briefs/<date>.json` **重建**聚合文件的工具(`python3 -m newsletter.export_json`),用于一次性重建或手工修数据后刷新。
4. **数据缺口处理**:`tone`/`direction` 已进 `emit_brief`/`classify` schema(见 §3.3),下次管线运行即产出真值;不反解析旧 `.md`。

> 这步严格属于「给智能平面加一个 JSON 输出口」,不是数据库/接口工程,符合「后端工程化以后再说」的边界。
> 已用真实 `observations.csv` 冒烟:`render_json` 正确产出 7 行指标(含广义美元)与相邻日变化量。

## 5. 前端目录结构(实际产出)

`frontend/app/`(与设计稿 `frontend/desgin/` 平级,设计稿保留作参考):

```
frontend/app/
  index.html  vite.config.ts  package.json  tsconfig.json  .gitignore
  scripts/
    copy-data.mjs            # predev/prebuild:拷仓库根 data/briefs.json -> public/data/(缺失则跳过)
    dev.sh                   # 预览/dev 包装:补 nvm node 到 PATH 再起 vite(供 .claude/launch.json)
  public/data/briefs.json    # 构建期拷入(产物,gitignore;缺失时前端用内置 demo)
  src/
    main.tsx                 # 入口:自托管字体 import + 挂载
    App.tsx                  # 三段式布局 + 主题/Tweaks 状态 + 桌面/移动响应式编排
    theme.css                # :root / [data-theme] / @media 全部 CSS 变量 + keyframes(从 helmet 搬)
    types.ts                 # Brief/Metric/News/… 契约(= §3.1)+ ThemeMode/Tweaks UI 类型
    vite-env.d.ts            # vite/client 类型(import.meta.env)
    demo/demoBriefs.ts       # 9 天 demo 数据(从设计稿 briefs.js 1:1 移植)
    data/loadBriefs.ts       # fetch 真实 briefs.json;空/失败回退 demo
    lib/
      format.ts              # fmtVal / fmtChg(yield/spread/index/price)
      sparkline.ts           # makeSpark(确定性合成折线)
      tone.ts                # toneCol / colorForChange / dirInfo / catMap
      useMediaQuery.ts       # useIsNarrow(移动端判定,≤720px)
    components/
      Header.tsx             # 站标 + 副标题 + 主题 segmented 三档
      Timeline.tsx           # 桌面竖直(悬停预览/点击锁定)+ 移动横向条(点击直切)
      Receipt.tsx            # 小票容器:撕边 + 抬头 + headline + receiptIn 重放 + 内容区 children
      ReceiptFooter.tsx      # 免责 + 条形码 + 签名
      SectionHead.tsx        # 通用章节小标题(· LABEL 中文 ----)
      TweaksPanel.tsx        # 右下浮层:accent 取色 / showSparklines / paperTexture
      sections/
        MarketData.tsx       # 7 行指标表(含广义美元)+ SVG sparkline
        AiBrief.tsx          # 四层:Facts / Interpretation / Hypothesis / Impact(方向箭头)
        Review.tsx           # 假设复盘(空则整段隐藏)
        News.tsx             # 新闻分类徽章 + 资产标签 + 方向
```

> 设计稿里 `makeSpark / fmtVal / fmtChg / colorFor / dirInfo / toneCol / catMap` 等纯函数从
> [`市场走势简报.dc.html`](../frontend/desgin/resource/市场走势简报.dc.html) 的 Component 类移植到 `lib/`;
> 那些 inline style 对象(时间线行样式、徽章样式等)也按原值移植到各组件,确保 1:1。

### 运行(前端)

```bash
cd frontend/app
npm install                 # 首次;需 node(本仓库用 nvm,见根 .claude/launch.json)
npm run dev                 # 开发服务器(http://localhost:5179)
npm run build               # 类型检查 + 打包到 dist/(纯静态产物)
```

> `npm run dev/build` 前会自动跑 `scripts/copy-data.mjs`,把仓库根 `data/briefs.json` 拷进
> `public/data/`;该文件由智能平面产出(目前为空则前端用 9 天 demo,管线跑过后自动接管)。
> 已知:`npm audit` 报 3 条 high(esbuild 开发期 RCE,经 vite 传递)——仅影响构建工具、不进
> 生产产物;修复需破坏性升级 vite,暂不动(见 [TODO.md](TODO.md))。

## 6. 状态与交互(对应设计稿 §5、§8)

- **顶层状态**(`App`):`themeMode`(auto/light/dark,持久化到 `localStorage` 键 `mb_theme`)、Tweaks 三项(`accent / showSparklines / paperTexture`)、`briefs`+`loaded`。
- **时间线选择**:`selectedIdx`(锁定)+ `hoverIdx`(预览),`activeIndex = hoverIdx ?? selectedIdx`——与设计稿一致。悬停淡入预览、离开回锁定、点击锁定。
- **小票切换动画**:`activeIndex` 变化时,对小票元素重放 `receiptIn .42s`(`useEffect` 里清空再设 `animation`,沿用设计稿的 reflow 技巧)。
- **主题**:`data-theme` 属性 + `prefers-color-scheme` 媒体查询联动,0.35s 过渡;`auto` 跟随系统。
- **Tweaks**:`accent` 实时 `setProperty('--accent', …)`;`showSparklines`/`paperTexture` 切换对应渲染。
- **克制动效**:只保留设计稿四处(小票淡入、时间线行高亮、主题过渡、加载呼吸),不加其它。
- **分区独立滚动(桌面)**:时间线列与小票列各自 `overflow-y:auto` + 限高 `calc(100vh-32px)` + `position:sticky` + `overscroll-behavior:contain`——鼠标在小票上只滚小票、在时间线上只滚时间线(滚到头不连带滚页面),在别处才滚整页。滚动条走 `.mb-scroll`(细、暖色 `--faint`、跟随主题)。移动端不分区,保持整页滚动。

## 7. 边界状态(对应设计稿 §10)

- 加载中:小票位为 `mbpulse` 呼吸占位块,时间线空。
- 某日无复盘:`Review` 整段隐藏。
- 新闻为空:`News` 仅剩章节头。
- 主题持久化:`localStorage`。
- 窄屏:左右栏垂直堆叠,小票居中,最大宽 442px。

## 8. 里程碑

| 阶段 | 内容 | 产出 |
|---|---|---|
| **F0 数据契约** ✅ | `types.ts` 契约 + 9 天 demo;Python `render_json` + 聚合 `data/briefs.json` + `export_json` 重建工具;38 个单测过 | 前端有数据可跑(真实 + demo 兜底) |
| **F1 脚手架 + 主题** ✅ | Vite6+React18+TS;自托管字体;`theme.css` 全部变量/明暗/keyframes;Header + 主题三档 + `localStorage` 持久化;`loadBriefs`(真实→demo 回退);`npm run build` 通过 | 空壳页面、明暗可切 |
| **F2 时间线 + 小票骨架** ✅ | 时间线(桌面竖直悬停预览/点击锁定 + 移动横向条点击直切)+ 小票撕边/抬头/headline + `receiptIn` 重放;明暗 + 桌面/移动均截图验证 | 能在交易日间切换 |
| **F3 小票内容区** ✅ | 7 行指标表+SVG sparkline、四层(含方向箭头)、假设复盘(空则隐藏)、新闻分类(徽章+资产+方向)、条形码页脚;明暗均截图验证 | 小票内容 1:1 还原 |
| **F4 Tweaks + 边界态 + 收尾** ✅ | accent 取色 / sparkline / texture 三开关(localStorage 持久化);加载呼吸占位、空复盘隐藏;桌面/移动像素级对齐;`npm run build` 通过 | 可交付的小票阅读器 |
| **F5(可选)联动后端缺口** ⏳ | `tone` / `dir` 已在 F0 进 schema;F5 主要剩「真实数据攒够后自动接管 demo」+ 部署。本轮不做 | 时间线染色、方向箭头随真实数据生效 |

## 9. 已决策与剩余开放问题

已决策 / 已落地:
1. **`tone` 怎么定**:由 LLM 在 `emit_brief` schema 中直接产出(`risk-on/risk-off/neutral`);无 LLM 时退 `neutral`。
2. **`impacts[].dir` / `news[].dir`**:已进 LLM schema,后端用 `direction` 产出 `up/down/watch`,前端渲染成方向箭头/观察符号。
3. **`briefs.json` 怎么到前端**:后端产出仓库根 `data/briefs.json`;前端 `predev/prebuild` 通过 `scripts/copy-data.mjs` 拷到 `public/data/`,缺失时回退 9 天 demo。

仍开放:
1. **真实数据接管时机**:管线连续运行后让 `data/briefs.json` 攒够真实内容,前端自动从 demo 切换到真实数据。
2. **部署**:纯静态产物,后续挂 GitHub Pages / 任意静态托管。
3. **`issue` 刊号起点**:当前按聚合文件中的日期年代序重算(最早=1);若公开发行需要营销化刊号,再定 epoch。

## 10. 后续可拓展(对齐设计稿 §11,本轮不做)

详情走势图(带坐标轴)、跨日关键词/资产搜索、小票导出 PDF/PNG、多模型(DeepSeek/GPT/Claude)同日横向对比、历史假设失效自动回标。目录结构与 JSON 契约已为这些留出扩展位。

---

*对应设计文档:[`frontend/desgin/design.md`](../frontend/desgin/design.md)(设计理念)+ 本文(落地计划)。*
