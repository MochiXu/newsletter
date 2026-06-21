# 路线图 / 详细 TODO

> 本文件是项目的**中央待办**:汇总未来里程碑、按模块的任务、已知技术债、开放问题与变现路线。
> 全局待办看这里;完成的项打 `[x]`。架构与已完成进度见 [refactor 文档](refactor/readme.md)。

> **当前状态(2026-06-22):V1 数据质量重构已完成。** 后端为**纯 Python 分层管线**
> (代码算特征 → LLM 只解释),Rust 数据平面已退役;M0/M1/M2 + V1 重构均已合并 `main`,
> 每日 cron(北京 07:00)用 DeepSeek 产出四层简报 + 新闻分类 + 假设复盘并推飞书。
> V2(回填 + 预测价值评估)设计已成稿待实现,见 [refactor/v2-progress](refactor/v2-progress.md)。
> 重心为「dogfood 使用 + 内容打磨」——见 §6。

---

## 1. 路线

> 早期 M0/M1/M2 建设阶段的历史时间线见 [CHANGELOG](CHANGELOG.md);数据质量重构(V1/V2)分步进度见
> [refactor/readme](refactor/readme.md)。多市场/进阶扩展(A股/港股、个股、CFTC、FedWatch、dashboard 等)
> **已搁置以保持宏观聚焦**,见 [parked-scope](parked-scope.md)。

### ✅ 已完成
- 全球宏观脊柱数据采集(FRED/TwelveData/Tiingo/Yahoo 兜底)+ 每日四层简报 + 新闻分类 + 假设追踪复盘。
- **V1 数据质量重构**:纯 Python 分层管线、代码算特征、parquet 原始层,DeepSeek 端到端实跑验证。

### 🚧 进行中规划 — V2 报告的预测价值评估
回填历史报告 + 结构化判断 + 用未来走势打分(关键:vs naive baseline 的技能差)。
设计与分步进度见 [refactor/v2-progress](refactor/v2-progress.md)。

### 近期(dogfood + 打磨,见 §6)
- [ ] 固定简报格式、固定发布时间、建立 voice
- [ ] 连续运行让 `hypotheses.csv` 攒出真实复盘记录(信任引擎的价值靠时间)
- [ ] 开始发给 5–10 个朋友收反馈(免费,先证明留存)

---

## 2. 按模块的 TODO

### 数据采集层(`py/newsletter/sources/` + `catalog.py`)
- [x] 黄金改用 Twelve Data `XAU/USD` 现货、窄口径美元用 Tiingo `UUP` 代理(V1 已落地;FRED 无可用金价/真 DXY)
- [ ] 数据校验/告警:某序列连续 N 天缺失或异常跳变时显式报警
- [ ] 序列增多后评估并发抓取(目前 `sources/base.py` 用 stdlib `urllib` + 礼貌间隔/退避,够用)
- 进阶数据源(CFTC/FedWatch/ETF flow)与多市场(A股/港股)数据源**已搁置**,见 [parked-scope](parked-scope.md)。

### 智能平面(Python,`py/newsletter/`)
- [x] **用真实 LLM key 跑出完整四层 + 新闻分类 + 假设复盘**(已用 **DeepSeek** 端到端实跑验证)
- [x] Python 侧自动加载 `.env`(`config.load_dotenv`;Python 无 dotenvy,之前 key 写进 `.env` 也读不到)
- [x] 新闻分类对齐改为 `index`(模型回填序号),解决 LLM 翻译标题导致的零匹配/全退化为未分类
- [ ] prompt 迭代与**评测**:建小评测集,比较不同 model/provider 的简报质量
- [ ] `linkage_map.md` 持续维护:这是核心 IP,需作者每天复盘后修订(飞轮:学到→编码→AI 应用→复盘)
- [ ] 新闻源扩充 + 质量过滤:`DEFAULT_FEEDS` 现为 Fed/CNBC/MarketWatch;加央行/财经源,去广告/低质
- [ ] 假设复盘质量:LLM 判定 held/invalidated/open 需人工抽查;考虑给「依据数据点」要求
- [ ] 「偏离预期」需要 consensus / 经济日历预期值——数据源待定(见 §4)

### 多模型 provider(`providers.py`)
- [x] **DeepSeek** 真实 key 端到端冒烟(OpenAI 兼容端点 + function calling 路径验证通过)
- [ ] 其余各家(Anthropic/OpenAI/MiniMax/Moonshot/Zhipu)真实 key 各跑一次冒烟
- [ ] **MiniMax**:域名/模型会变(已从 `api.minimax.chat` 更新为 `api.minimaxi.com`、模型 `MiniMax-M2`);
      上线前核对最新域名/模型,必要时用 `MINIMAX_BASE_URL` / `MINIMAX_MODEL` 覆盖;注意部分账户可能需 GroupId
- [ ] 流式 / 超时 / 重试 / 速率退避(目前一次性请求 + 异常降级)
- [ ] 成本 / token 用量记录(每次调用记 usage,便于选 model)
- [ ] prompt 缓存(Anthropic 支持;大 system + linkage map 可缓存降本)

### 交付(`deliver/`)
- [ ] 飞书 text → **富文本卡片**(`lark_md`),四层简报渲染更好看
- [ ] 邮件 newsletter(Resend / Buttondown / beehiiv)——未来付费的主渠道
- [ ] Telegram(若之后可用)

### 展示平面(前端,`frontend/app/`)
- 前端将**按 `frontend/design` 重新设计改写**(旧实现 + 旧前端文档已作废);改写时以新设计为准。
- [ ] 真实历史数据接管:回填后 `data/briefs.json` 为真实历史,前端切真实(与 V2 回填配合)。
- [ ] 部署:纯静态产物,挂 GitHub Pages / 任意静态托管。

### 基础设施 / CI
- [x] CI 改纯 Python(`setup-python` + `pip` 缓存;无 Rust 构建)
- [ ] 失败可见性:简报部分序列失败/无分类时,除日志外发通知(现有 `::warning::` 注解)
- [ ] `data/briefs`、`data/raw`、`hypotheses.csv` 随 cron 累积,定期归档/清理脚本
- [ ] 回填脚本(V2):逐日 `target_date` 重跑简报(严格 point-in-time),见 [refactor/v2-progress](refactor/v2-progress.md)

---

## 3. 已知局限 / 技术债

- **LLM 路径**:已用 **DeepSeek** 真实 key 端到端验证(四层简报 + 新闻分类 + 假设复盘均跑通)。
  其余 provider(Anthropic/OpenAI/MiniMax/Moonshot/Zhipu)的 API 形状基于公开规范实现并经对抗式
  审查,但尚未各自冒烟,上线前需逐一验证。
- **MiniMax / 其他兼容端点**:域名与模型名随各家更新而漂移;预设可能过期,用 `<NAME>_BASE_URL` /
  `<NAME>_MODEL` 覆盖。Moonshot/Zhipu 的预设尚未实测(DeepSeek 已实测通过)。
- **新闻分类靠 `index` 对齐**:模型回填我们给的序号(对翻译/改写标题免疫)。若模型连 index 都填错
  且标题也对不上,该条退化为未分类(不会错位贴到别条——有意的安全取舍)。
- **假设复盘依赖 LLM 判断**:held/invalidated/open 的判定质量取决于模型,需人工抽查。
- **原始层用 parquet(git-as-database)**:V1 已把数据落盘从 CSV 改为 `data/raw/*.parquet`;
  对外产物(briefs JSON/md、`hypotheses.csv`)走 git。复杂查询/大数据量时再评估 DuckDB。
- **数据源脆弱性**:Yahoo 限流(已加礼貌间隔+退避)、Stooq 反爬(已弃用)、RSS 源可能失效/限流
  (单源失败静默跳过)。
- **仓库体积**:每日往 `data/` 提交快照+简报,长期会变大;需归档策略。

---

## 4. 开放问题

- **consensus / 经济日历预期值**:简报里「偏离预期」需要市场预期值数据,来源待定(Investing.com /
  TradingEconomics / 自建?多数有反爬或付费)。
- **linkage map v1 的迭代**:由作者口述规则、AI 整理成 markdown?还是从简报复盘里自动提炼?
- **默认 provider / model**:成本 vs 质量怎么权衡(日报 sonnet/gpt-4o-mini,深度 opus)。
- **发布时区**:美国数据凌晨定盘,单一北京 07:00 发布(总结隔夜美国 session)是否够。

---

## 5. 变现路线(谨慎,排在最后)

**先免费受众证明留存,再建支付**(先建支付是个人项目最常见的死法)。

- [ ] 免费 newsletter / 群,固定发布、建立 voice 和受众
- [ ] 付费 newsletter ¥99–299/月 / 私人 Telegram·微信群 / 面向交易员的小工具
- [ ] **合规底线**:不喊单、不承诺收益、research framing、每篇免责声明、不代客理财
- [ ] 差异化卖点:不是「又一个新闻聚合」,而是「哪些数据真的重要、它如何改变交易假设」+
      公开打磨框架的过程 + 假设追踪的诚实记录(对了错了都留痕)

---

## 6. 近期优先级(next up)

基建已就绪(✅ DeepSeek 跑通、✅ 飞书配置实测、✅ 合并 main、✅ cron + secrets 齐全),
重心转为 **dogfood 使用 + 内容打磨**(对应锁定决策「先自用 2-3 个月再公开」):

1. **每天读简报**,判断是否比刷推特信息量大、哪里没用——这是四层简报的真正验收
2. **每天维护 `linkage_map.md`**(5 分钟复盘 → 修订):核心 IP + 学经济的载体 + 飞轮发动机
3. **让假设追踪攒数据**:连续运行,`hypotheses.csv` 才会出现真实的 ✅已兑现/❌已失效 记录
4. **盯前几天的 cron**:推送是否每天到、有无序列失败(Yahoo 限流/RSS 挂)、简报质量 → 调 prompt
5. 固定简报格式/voice,开始发给 5–10 个朋友收反馈(多市场扩展已搁置,见 [parked-scope](parked-scope.md))
