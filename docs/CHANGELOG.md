# 变更日志 / 工作历史

> 本项目的**时间线视图**:按里程碑记录「做了什么、为什么」。和其它文档分工:
> - **当前状态**总览 → [README](../README.md)
> - **未来路线 / 技术债 / 开放问题** → [TODO](TODO.md)
> - **设计哲学与已锁定决策** → [DESIGN.md](../DESIGN.md)
> - **架构与重构进度** → [docs/refactor/](refactor/readme.md)
>
> 日期为提交日期(项目自 2026-06-16 起步)。最新在前。

> **2026-06-18 起架构已重构**:后端推平为**纯 Python**,Rust 数据平面退役,接缝从
> `observations.csv` 升级为 `data/raw/*.parquet` + 新增数据源(TwelveData/Tiingo)+ 代码算特征层。
> 当前架构与现状以 [README](../README.md) 与 [refactor 文档](refactor/readme.md) 为准;
> 以下各条目是**当时**的工作记录(含已退役的 Rust 数据平面),作为历史时间线保留。

> **工程实践**:每个里程碑收尾跑**多智能体对抗式审查**(找 bug + 核验不变量)再合入,
> 故历史提交里有数处 `fix(...): 处理对抗式审查发现`。

---

## 2026-06-22 — V1.5 内容与体验增强(契约加厚 + LLM 健壮性 + 前端 3 页重建)

V1 之后、V2 之前的一波增强,不改「代码算特征 → LLM 只解释」骨架。详见 [v1.5-progress.md](refactor/v1.5-progress.md)。

- **`briefs.json` 契约加厚**:新增 `signals`(29 条技术指标,带 unit/group,单一源 `features.FEATURE_VIEW`)+ `regime`(代码派生标签);假设层改为**对固定 roster 纳指/黄金/广义美元/2Y 的预测卡**(asset/direction/horizon/confidence/key_factors/可度量失效);`metrics[].spark`(~20 真实收盘,小走势线)+ `priceSeries`(5 资产×30 点,30D 可交互价格图);`facts`/`reads` 从 `str[]` 升级为 `[{tag,text,figures}]`(主题标签 + 数字按方向上色)。
- **通用文本规范化**:`textnorm.normalize_text`(全角标点→ASCII、中英盘古空格、双引号→单引号)落库前统一应用;`llm/style.TEXT_STYLE` 公共 prompt 片段(简报+新闻共用)。
- **LLM 健壮性**:结构化输出改用 **JSON mode**(`response_format`)替代强制 function-calling——后者在复杂 schema 下会让 DeepSeek 提前闭合根对象、丢字段;figures 用扁平字符串 `figs='token|dir;...'` 避免深层嵌套;新闻 fetch/classify 解耦(分类失败不丢新闻)。
- **新闻升级**:优质宏观源(Fed/ECB/MarketWatch/CNBC)+ 过滤噪音/无链接 + 带真实 link。
- **前端按设计稿重建为 3 页 SPA**(简报/时间线/命中率):双栏卡片 + 30D 可交互价格图 + 技术指标面板 + 预测卡 + 事实/解读层数字按方向上色;命中率/区间聚合留空态待 V2(不显示假数字)。详见 [frontend-rebuild.md](frontend-rebuild.md)。**教训**:照设计重建必须读设计的实现源文件(`市场走势简报.dc.html`),不能只读文字稿。
- 后端离线单测 41 → **54**(textnorm 全覆盖 / figures 解析 / 向后兼容旧 str[] facts / 因果性红线)。每个阶段收尾跑多智能体对抗式审查(本轮捕获并修复了 `Brief.facts/reads` 缺向后兼容校验器的回归)。

---

## 2026-06-18 — 数据质量重构 V1(后端推平为纯 Python)

以**数据质量**为核心的整体重构(`feat(refactor)`):把后端推平为纯 Python,核心是
「**代码算技术特征 → LLM 只解释**」的强制分层。设计见 [docs/refactor/](refactor/readme.md)。

- **数据源强强联合**:FRED(利率/利差/实际利率 DFII10/通胀预期 T10YIE/广义美元/VIX/月频宏观)
  + Twelve Data(金现货 `XAU/USD`)+ Tiingo(`UUP` 窄口径美元代理、`SPY`/`QQQ` 长历史)+ Yahoo 兜底。
  统一 `Source` 接口 + catalog 主源/兜底链(整序列级降级,避免跨源尺度跳变)。
- **原始层 parquet**:`data/raw/latest`(全量快照,每日重拉覆盖)+ `history` 归档(point-in-time)。
- **特征层(pandas)**:趋势/动量/波动/利率·通胀/美元背离/跨资产 60 日相关/52 周分位 + 代码派生
  regime 标签。**全用滚动窗口(因果),全历史算一次按日取行,天然不偷看未来**(有单测红线守护)。
- **LLM 强制分层**:`prompt` 改喂「算好的特征块」而非原始值;`pydantic` 守边界——LLM 输出经
  `LLMBrief` 校验/归一化,**根治旧版 `{'fact': ...}` → `[object Object]` bug**。
- **契约不变**:`briefs.json` 严格对齐 `types.ts`,前端不改即可读真实数据(指标表自适应)。
- **退役 Rust**:删 `src/*.rs` / `Cargo.*`;`daily.yml` 改 `pip install` + `python -m newsletter`;
  新增 `requirements.txt`(pandas/numpy/pyarrow/pydantic)。
- 代码规范:全量 type hints + pydantic 守边界;41 个离线单测(含特征因果性);DeepSeek 端到端实跑验证。
- **V2 待实现**:历史回填 + 结构化判断 + 预测价值评估(vs baseline),见 [v2-progress](refactor/v2-progress.md)。

---

## 2026-06-17 — 展示平面(前端)F0–F4

把每日简报渲染成「暖纸小票」阅读器,1:1 还原设计稿(`frontend/desgin/`)。

**评审先行**:对另一个 AI 写的初版前端计划做了多智能体核验(对照真实后端代码 + 设计稿资源),锁定 4 项决策并修正初版计划的事实错误:
- 决策:① 尽量 1:1(数据不足用 9 天 demo 兜底);② 现在就给 LLM schema 加 `tone` + `direction`;③ 桌面 + 移动都精修;④ 指标表加第 7 行「广义美元 DTWEXBGS」(简报常讲的"广义美元 vs DXY 背离"在表里能看到)。
- 修正:纯函数其实在 `市场走势简报.dc.html` 的 Component 类里(不在 `support.js`,那是设计工具运行时);`tone/dir` 本就必填(非"缺口");字体改**自托管**(@fontsource,不走 Google Fonts CDN,符合"离线可跑/纯静态")。

分阶段交付:
- **F0 数据契约 + 后端导出** `feat(data)`:`emit_brief` schema 加 `tone`(risk-on/off/neutral)+ 每条 impact/news `direction`(up/down/watch);`render.render_json` 产出单日 Brief(7 行指标含广义美元、相邻 run_date 差作变化量);`brief.py` 增量维护聚合 `data/briefs.json`(刊号按年代序);`export_json.py` 重建工具;前端 `types.ts` 契约 + 9 天 demo。离线单测 32 → 38。
- **F1 脚手架 + 主题**:Vite6 + React18 + TS;自托管字体;`theme.css` 搬全部色彩变量/明暗/keyframes;Header 三档主题(auto 跟随系统)+ localStorage;`loadBriefs`(真实 JSON 为空则回退 demo)。
- **F2 时间线 + 小票骨架**:桌面竖直时间线(悬停预览 / 点击锁定)+ 移动横向条(点击直切);撕边 / 抬头 / headline + `receiptIn` 入场动画。
- **F3 五节内容**:7 行指标表 + SVG sparkline、四层简报(事实 / 解读 / 假设 / 影响,带方向箭头)、假设复盘(空则隐藏)、新闻分类(徽章 + 资产 + 方向)、条形码页脚。
- **F4 Tweaks + 响应式**:accent 取色 / 走势线 / 纸纹理三开关(localStorage);加载呼吸占位 + 空态;桌面 / 移动像素级对齐。
- **分区独立滚动**(收尾增强):桌面下时间线列、小票列各自 `overflow-y:auto` + `overscroll-behavior:contain`,鼠标在哪个区就只滚哪个、滚到头不连带滚页面;主题化细滚动条;移动端保持整页滚动。

验证:明暗 × 桌面 / 移动 四组合均截图确认;`npm run build` 通过。**F5(真实数据攒够后自动接管 demo + 部署)暂未做。**

---

## 2026-06-17 — 数据平面模块化重构(Rust)

`refactor(data-plane)`:面向"未来扩展更多数据源"重构。引入 `Source` trait 统一 FRED / Yahoo(批量粒度 `fetch(specs) -> SourceData`);`thiserror` 单一 `Error` 枚举(无 `#[from] reqwest::Error`,`without_url()` 是唯一构造路径 → 编译期防 api_key 泄露进日志);`log` + `env_logger` 日志门面;运行期字符串改英文。模块拆分 error / config / model / catalog / source / store / lib / main。新增数据源(CFTC / FedWatch 等)成本极低。(该 Rust 数据平面已于 2026-06-18 随 V1 重构退役,见上方 2026-06-18 条目。)

## 2026-06-17 — M2 关键修复(Python)

`fix(M2)`:① 新增 `config.load_dotenv`,`brief.py` 启动时自读仓库根 `.env`(此前 Python 侧无 dotenvy,`.env` 里的 key 进程不可见,DeepSeek 报"未配置任何 LLM provider");② 新闻分类改按模型回填的 `index` 对齐(早期按标题对齐,DeepSeek 会把英文标题翻成中文 → 零匹配、全退化为未分类);③ 假设 `record_new` 按天幂等,且复盘只针对**往日**假设(今日假设不拿当天数据自我验证)。

## 2026-06-16 — 系统上线

M0 + M1 + M2 合并到 `main` 并删除临时分支;GitHub Actions cron 每日北京 07:00 自动跑(抓数 → 简报 → 提交回仓库 →(配了飞书则)推送)。配齐仓库 secrets(`FRED_API_KEY` / `DEEPSEEK_API_KEY`)+ variable(`LLM_PROVIDER=deepseek`)+ 飞书 webhook,均实测通过。**活跃 provider = DeepSeek**(其余各家基于公开规范实现,尚未逐一冒烟)。重心转入 dogfood(自用 2–3 个月再公开)。

## 2026-06-16 — M2 新闻分类 + 假设追踪

`feat(M2)`:新闻抓取 + 分类(`news.py`,stdlib `urllib`+`xml.etree` 解析 RSS/Atom;LLM 分 事实 / 解读 / 事实+解读 / 噪音 + 受影响资产)+ 假设追踪复盘日志(`hypotheses.py`,`data/hypotheses.csv`,次日起复盘 held / invalidated / open——信任与学习引擎)。

## 2026-06-16 — 多 provider 可插拔

`feat(llm)`:LLM 层抽象(`providers.py`)。同一份四层 schema(`emit_brief`)适配不同家:Anthropic 走 tool use,OpenAI 兼容走 function calling(失败回退解析 JSON)。预设 openai / minimax / deepseek / moonshot / zhipu + 通用 openai-compat;`LLM_PROVIDER` 显式或按存在的 key 自动探测。换模型只改 env、不改代码。

## 2026-06-16 — M1 智能平面

`feat(intelligence-plane)`:读 `observations.csv` + `framework/linkage_map.md`(核心 IP:人工维护的宏观传导图)→ LLM **强制四层简报**(事实层 / 解读层 / 可证伪假设层 / 影响观察层)→ 渲染 markdown 存本地 + 推飞书(签名可选)。纯标准库,零第三方依赖。

## 2026-06-16 — M0 数据平面

`feat(data-plane)`:Rust 抓 FRED(10Y / 2Y / 2s10s / VIX / 广义美元)+ Yahoo 免鉴权回退源补 DXY / 黄金 → CSV + markdown(git-as-database);每日快照 GitHub Actions workflow;移除已下架的 FRED 伦敦金价序列(`GOLDAMGBD228NLBM`),黄金改用 COMEX 期货。

## 2026-06-16 — 项目起步

`init repo`。技术栈定为 **Rust 数据平面 + Python 智能平面**混合,接缝走共享数据文件(临时 runner 上 SQLite 不持久,故用 git 当数据库)。设计哲学(四层结构、宏观传导图、假设追踪、只给观察点不喊单)见 [DESIGN.md](../DESIGN.md)。
