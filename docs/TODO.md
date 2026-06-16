# 路线图 / 详细 TODO

> 本文件是项目的**中央待办**:汇总未来里程碑、按模块的任务、已知技术债、开放问题与变现路线。
> 模块文档([data-plane](data-plane.md) / [intelligence-plane](intelligence-plane.md))里的「待办」是局部视图,
> 全局看这里。完成的项打 `[x]`。

---

## 1. 里程碑路线

### M0 数据平面 — ✅ 已完成
真实 FRED + Yahoo 数据每日入库(CSV + markdown,git-as-database)。

### M1 智能平面 — ✅ 代码就绪
四层简报 + 飞书推送;待用户填 LLM key 跑出完整 AI 内容。

### M2 新闻分类 + 假设追踪 — ✅ 代码就绪
RSS 抓取 + 分类(事实/解读/影响资产)+ 可证伪假设次日复盘。

### M3 · 第 2 月 — 接入更多市场 + 公开前打磨
- [ ] **A股 / 港股影响层**:数据源(新浪/东财/AkShare 口径)、时区(北京白天)、合规口径单独处理
- [ ] 美股指数 / 个股、加密(BTC/ETH)的「影响层」映射做细
- [ ] 固定简报格式、固定发布时间、建立 voice
- [ ] 开始发给 5–10 个朋友收反馈(免费,先证明留存)
- [ ] **假设追踪积累**:连续运行,让 hypotheses.csv 攒出真实复盘记录(信任引擎的价值靠时间)

### M4 · 第 3 月+ — 深度功能 + 考虑变现
- [ ] **单一资产交易框架生成器**(给某资产生成结构化交易假设)
- [ ] **CFTC 持仓(COT)**:CFTC Socrata API(免费,每周五发布周二数据)
- [ ] **ETF flow**:加密 ETF 用 Farside;股/债 ETF 暂无免费 API,往后放
- [ ] **FedWatch**:从 30 天联邦基金期货(ZQ)自己算隐含加息/降息概率(无免费 API;也是学习项目)
- [ ] Web dashboard(可视化数据 + 历史假设命中率)
- [ ] 考虑公开 + 付费墙(见 §5)

---

## 2. 按模块的 TODO

### 数据平面(Rust,`src/`)
- [ ] DXY / 黄金换更贴盘口的源(目前 DXY 用 Yahoo `DX-Y.NYB`、黄金用 COMEX 期货;FRED 伦敦金价序列已下架)
- [ ] 序列增多后从 blocking 切 async 并发抓取(`tokio`)
- [ ] 加 CFTC COT、FedWatch(ZQ 隐含概率)、ETF flow(见 M4)
- [ ] A股/港股数据源(M3)
- [ ] **引入 SQLite 接缝**:目前 M0/M1/M2 全用 CSV(git-as-database);量大或需复杂查询时,Rust 写 SQLite、Python 读 SQLite,替代直接读 CSV
- [ ] 数据校验/告警:某序列连续 N 天缺失或异常跳变时显式报警(现有新鲜度校验 >14 天判陈旧)

### 智能平面(Python,`py/newsletter/`)
- [x] **用真实 LLM key 跑出完整四层 + 新闻分类 + 假设复盘**(已用 **DeepSeek** 端到端实跑验证)
- [x] Python 侧自动加载 `.env`(`config.load_dotenv`;Python 无 dotenvy,之前 key 写进 `.env` 也读不到)
- [x] 新闻分类对齐改为 `index`(模型回填序号),解决 LLM 翻译标题导致的零匹配/全退化为未分类
- [ ] prompt 迭代与**评测**:建小评测集,比较不同 model/provider 的简报质量
- [ ] `linkage_map.md` 持续维护:这是核心 IP,需作者每天复盘后修订(飞轮:学到→编码→AI 应用→复盘)
- [ ] 新闻源扩充 + 质量过滤:`DEFAULT_FEEDS` 现为 Fed/CNBC/MarketWatch;加央行/财经源,去广告/低质
- [ ] 假设复盘质量:LLM 判定 held/invalidated/open 需人工抽查;考虑给「依据数据点」要求
- [ ] 「偏离预期」需要 consensus / 经济日历预期值——数据源待定(见 §4)
- [ ] M1 从直接读 CSV 改为读 SQLite 接缝(配合数据平面)

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
- [ ] Web dashboard(M4)

### 基础设施 / CI
- [ ] CI 缓存 Rust 构建(已用 `Swatinem/rust-cache`);Python 无依赖无需缓存
- [ ] 失败可见性:简报部分序列失败/无分类时,除日志外发通知(现有 `::warning::` 注解)
- [ ] `data/briefs`、`data/snapshots`、`hypotheses.csv` 随 cron 累积,定期归档/清理脚本
- [ ] 回填脚本:用历史数据重建 observations / 重跑简报

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
- **SQLite 接缝尚未引入**:DESIGN 设想 SQLite 作两半接缝,目前实际用 CSV/markdown(git-as-database)。
  够用;复杂查询/大数据量时再引入。
- **数据源脆弱性**:Yahoo 限流(已加礼貌间隔+退避)、Stooq 反爬(已弃用)、RSS 源可能失效/限流
  (单源失败静默跳过)。
- **仓库体积**:每日往 `data/` 提交快照+简报,长期会变大;需归档策略。

---

## 4. 开放问题

- **consensus / 经济日历预期值**:简报里「偏离预期」需要市场预期值数据,来源待定(Investing.com /
  TradingEconomics / 自建?多数有反爬或付费)。
- **linkage map v1 的迭代**:由作者口述规则、AI 整理成 markdown?还是从简报复盘里自动提炼?
- **默认 provider / model**:成本 vs 质量怎么权衡(日报 sonnet/gpt-4o-mini,深度 opus)。
- **发布时区与多市场**:美国数据凌晨定、A股白天、加密 7×24——单一 07:00 发布是否够,还是分场次。

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

1. ✅ LLM 路径已用 **DeepSeek** 跑通完整 AI 简报;下一步配 **FEISHU_WEBHOOK** 验证推送
2. 在 GitHub Secrets 配 `FRED_API_KEY` + `DEEPSEEK_API_KEY`(及可选 `FEISHU_WEBHOOK`),
   合并分支到 `main` 让每日 cron 真正跑起来,开始积累快照 + 假设追踪记录
3. 持续维护 `linkage_map.md`(每天 5 分钟复盘 → 修订)
4. M3:接入 A股/港股影响层 + 固定格式,开始发给朋友
