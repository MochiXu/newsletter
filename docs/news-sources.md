# 新闻源使用方式(news sourcing & extraction)

> 本文件 = **我们怎么获取 / 抽取 / 清洗新闻**(数据采集运营手册)。
> 新闻**怎么进预测**(代码特征 + A/B 消融)见 [refactor/v1.6-progress.md §6](refactor/v1.6-progress.md);
> 本文件是它的上游(把"原始新闻"变成"干净、可用、带正文的条目")。
> 现状代码:`py/newsletter/news.py`(RSS 抓取 + LLM 分类),将按 §4 拆成 `news/` 包。

---

## 1. 三个源 + 角色分工(准确版)

> **测试 key(仅本地测试;真实运行从 `.env` 读;公开仓库前重置)**:
> - **TheNewsAPI(主源,3 个免费 key 轮换凑额度,环境变量 `THENEWSAPI_KEYS` 逗号分隔)**:
>   `ntqtPMgbiSFDeA13QVAKqg3lDPzc2AsDNnN7OjvH`、`C13GWFdPL1k0mDjWIUqgwRPuQmWCcV66LlgFsbsL`、`59rkKM7q5ivnAot9p1wdMOPBScgLUACy7zX5vTP8`
> - NewsAPI.org(**本期不实现,留作未来可选源**):`384a255227534a488a4683d2487cf397` → `NEWSAPI_KEY`
>
> **决策(2026-06-24)**:本期**只实现 TheNewsAPI**(3 key 轮换,3×300=900 条/天,够 1 个月回填),
> 但代码按**多源可插拔**(`NewsProvider` 协议)写,以后新闻证明有用再加源。RSS 仍作零配额兜底。

| | RSS(现有) | **TheNewsAPI(本期主源)** | NewsAPI.org(未实现/可选) |
|---|---|---|---|
| 历史 | 无 | **实测很深(≥45 天,域名查询返 2022+)** | 免费 = 1 个月(硬墙) |
| 延迟 | 无 | **实时** | 24 小时(免费) |
| 单次条数 | 抓 feed | 免费 **3 条/请求** | 100 条/页 |
| 日配额 | 无 | 免费 100 次/天/key → **3 key = 900 条/天** | 100 次/天 |
| 端点 | RSS/Atom | `/v1/news/all`+`/sources`(全档) | `/v2/everything` |
| 生产 | 可 | 无明文限制(免费亦可测) | 禁止(仅开发) |
| 正文 | 摘要 ~300 字 | **≈160 字 snippet/description** | 标题+描述 |
| 反爬 | — | **Cloudflare,需浏览器 UA**(否则 403/1010) | — |
| **角色** | **央行一手(Fed/ECB)+ 零配额兜底** | **1 个月回填 + live 主源(3 key 轮换)** | 留接口,未来可加 |

**结论(2026-06-24 实测后)**:TheNewsAPI 免费档**历史足够深 + 实时**,**3 个 key 轮换(900 条/天)既能 1 个月回填、又能 live 每日**——本期**只实现它**。NewsAPI.org 暂不做(`NewsProvider` 协议留好扩展位)。**所有源正文都薄 → 依赖自建正文抽取(§3);裸 search 噪音大 → 必须用 §5 source 白名单。** 需更大量/生产背书再开 TheNewsAPI Basic($19/月)。

---

## 2. TheNewsAPI 准确参考(读自官方文档 + 实测)

> **实测(2026-06-24,用免费 key)**:
> - **Cloudflare 拦截**:urllib 默认/自定义 UA 触发 **HTTP 403 `error code: 1010`**(按客户端签名封禁)。**必须设浏览器 UA**(如 `Mozilla/5.0 ... Chrome/124 Safari/537.36`)才通。provider 实现务必带浏览器 UA;**不能复用 `sources/base.http_get_json` 的 UA**。文章正文抽取(爬第三方站)会遇到同类反爬 → 取不到即丢(已设计)。
> - **免费档历史很深**:实测 10/30/**45 天**前均可拉到(域名查询甚至返回 2022-2023)——**无 NewsAPI.org 那种 ~1 月硬墙**。1 个月回填绰绰有余(未来多年回填也可行)。
> - **裸 `search` 噪音极大**:搜 "gold" 多为印度金价/游戏站/盗版站 → **`domains`/`source_ids` 白名单是刚需**,再叠 LLM 噪音分类。
> - `snippet`/`description` 实测 ≈ **160 字**(官方文档写 60)——仍偏短,**全文抽取(§3)仍必要**。
> - `/v1/news/sources?categories=business&language=en` 实测 **2657 个源**(偏多博客类,需挑)。

Base host:`https://api.thenewsapi.com`。鉴权:`api_token` 查询参数。日期一律 **UTC**。

**我们要用的端点**:
- `GET /v1/news/all` —— **主端点**(live + 历史,全过滤/搜索;全档可用)。
- `GET /v1/news/sources` —— 枚举可用源(建优质源白名单;`limit` 固定 50,翻 `page`)。
- `GET /v1/news/top` —— 备用(按国家的头条)。

**`/v1/news/all` 关键参数**:
- `search` —— 布尔操作符:`+`=AND、`|`=OR、`-`=NOT、`"短语"`、`*`=前缀、`()`=优先级(特殊字符需 URL 编码)。
- `search_fields` —— `title,description,keywords,main_text`(默认 `title,main_text`;注意 `main_text` 可搜但**不在返回里**)。
- `categories` —— 我们用 `business`(还有 general/tech/politics/...);`exclude_categories` 反选。
- `language=en`、`locale=us`(宏观聚焦美国英文)。
- `source_ids` / `domains`(及各自的 `exclude_*`)—— **优质源筛选**(§5)。
- `published_after` / `published_before`(`Y-m-d` 或 `Y-m-d\TH:i:s`)、`published_on`(`Y-m-d`)。
- `sort=published_on | relevance_score`(后者需配 `search`)。
- `limit`(按档封顶,免费 3)、`page`(`limit×page ≤ 20000`)。

**返回结构**:`{ meta:{found,returned,limit,page}, data:[ article ] }`。
**article 字段**:`uuid, title, description, keywords, snippet(正文前 60 字), url, image_url, language, published_at, source(=域名), categories, relevance_score(无 search 则 null), locale`。

**示例**(官方):
```
GET /v1/news/all?api_token=…&search=forex%20%2B%20(usd%20%7C%20gbp)%20-cad&language=en&categories=business&published_after=2026-06-16
GET /v1/news/sources?api_token=…&language=en
```
**错误码**:401 `invalid_api_token`、402 `usage_limit_reached`、403 `endpoint_access_restricted`、429 `rate_limit_reached`。
**配额头**:`X-RateLimit-Limit` / `X-UsageLimit-Limit`(可读剩余额度)。

> NewsAPI.org 对照:`/v2/everything`,`q` + `from`/`to`(ISO UTC)+ `domains`(≤? 无硬限)/`sources`(≤20)+ `pageSize`(≤100)+ `page`(免费禁深翻,`page>1` 报 `maximumResultsReached`)。免费仅 1 个月、24h 延迟、禁生产。

---

## 3. 文章正文抽取模块(`news/extract.py` —— 你提的核心)

**为什么**:API 只给标题 + 60 字 snippet(+ 描述),**信息量太薄**;真正的事实/解读/惊喜在正文里。所以从 `url` **自己抓正文**。这也让 LLM 分类/特征基于全文而非标题,质量更高。

**职责**:`extract(url) -> str | None`
1. HTTP GET(stdlib `urllib` + UA + 超时 ~10s + 1 次重试;复用 `sources/base` 的退避思路)。
2. **正文抽取**(去导航/广告/页脚,留主文):
   - 首选依赖 **`trafilatura`**(业内最稳:处理编码 + boilerplate 去除 + 回退链)。这是**本项目第一个 HTML 抽取依赖**,值得为质量付出(纯 stdlib 抽正文不可靠)。
   - **优雅降级**:未装 `trafilatura` 或抽取为空 → stdlib 启发式(去标签 + 取最大 `<p>` 文本块);再不行 → 退回 API 的 `description`/`snippet`。
3. **清洗**:压空白、去残留 HTML 实体、截断到喂 LLM 的上限(控成本/上下文,如 ~4000 字)。
4. **死链/取不到直接丢**(你的要求):404 / 超时 / 403 paywall / 抽取空 → 返回 `None`,上层**跳过该条**,绝不阻断管线(`log.debug` 记一笔)。

**缓存**:抽到的正文按 `uuid`(或 url 哈希)缓存到 `data/news_cache/extracted/<uuid>.txt`,重跑/回填不重抓(护配额 + 礼貌 + 可复现)。

**礼貌 / 合规**:
- 礼貌爬:合理 UA、单域限速、超时即弃;被拦就丢,不重试轰炸。
- **版权红线**:抓来的**全文仅作内部分析输入**(喂 LLM + 派生特征)。**对外产物(`briefs.json` / 前端 / 飞书)绝不复制文章正文**——只展示 `标题 + 来源 + 链接 + 我们自己写的中文摘要`。遵守 [全局版权约束](../CLAUDE.md 无关,见根 README 免责)。

---

## 4. 抓取流程(discover → extract → classify → features)

```
registry(按 news_mode 选源)
   │  每资产关键词 + 优质源白名单(§5)查询 → 拿 {title, url, source, published_at}
   ▼
extract(§3)  逐条抓 url 全文 + 清洗;死链/抽空 → 丢
   ▼
classify(现有 LLM,改吃全文)  事实/解读/影响资产/方向(+ 可加 event_type)
   ▼
features(v1.6 §6.4)  事件日历 flag / 新闻量 z→波动率 / 惊喜;净情绪→仅前端叙事
```

`news/` 包结构(把现 `news.py` 拆入;复用 `sources/base.http_get_json`):
```
news/  base.py(NewsProvider 协议 + 能力元数据)  rss.py  thenewsapi.py(本期实现,多 key 轮换 + 浏览器 UA)
       newsapi.py(留接口,本期不实现)
       extract.py(§3 正文抽取)  registry.py(选源 + 跨源去重 + 每资产查询)
       classify.py(LLM 分类,迁自 news.py)  cache.py(磁盘缓存)  features.py(v1.6 §6.4)
```
- **多源可插拔**(`NewsProvider` 协议),本期只实例化 TheNewsAPI + RSS;跨源合并去重,详见 v1.6 §6.3。
- **key 从 `.env`**:`THENEWSAPI_KEYS`(逗号分隔多个 free key 轮换护额度)+ `NEWSAPI_KEY`(可选);缺 key 跳过该源;RSS 永远在。
- **TheNewsAPI provider 必须带浏览器 UA**(Cloudflare 1010),不能复用 `sources/base.http_get_json` 的 UA。

---

## 5. 优质源筛选(source allowlist —— 实测重订 2026-06-24)

裸 `search` 噪音极大(印度金价/选股博客/游戏站),**必须用 `source_ids` 白名单**。

> **⚠️ v1 白名单事故(2026-06-24 复盘,见 §6)**:首版白名单的 `source_id` 几乎**全填错**
> (`cnbc.com-124` / `wsj.com-4` / `ft.com-226` … 真实值是 `cnbc.com-1` / `ft.com-2` …),且把
> **Benzinga**(`bengzinga-34`,拼写还错)放进去。TheNewsAPI 对错误 id 静默忽略 → 几乎全部 miss →
> 噪音兜底全落到 **Benzinga**(实测占抓取量 **87%**)。而 Benzinga 正文是 **JS 墙**:抽取只拿到
> 小标题 + "Benzinga does not provide investment advice" 免责,**正文空洞**(还混大量 "unpaid
> external contributor" 寄稿 / PR 定型文)。→ B 臂(新闻臂)被垃圾喂养。**已重订如下。**

**重订方法**:`/v1/news/sources`(business+general+tech,实测 **906 个唯一 source_id**)拿**真实 id** →
逐源拉最新 3 条**实测抽取**,只保留"能抓到真全文"的源(中位本文 >2000 字、无 paywall/免责残文):

```python
# TheNewsAPI source_id 白名单(代码:py/newsletter/news/thenewsapi.py)
# 实测抽取中位本文字数(2026-06-24):
SOURCE_ALLOWLIST = [
    "cnbc.com-1", "cnbc.com-2", "cnbc.com-3",          # CNBC      ~2220 字 ✅ 顶级市场/宏观
    "finance.yahoo.com-2",                              # Yahoo Fin ~3087 字 ✅ 聚合通讯社
    "investing.com-18",                                 # Investing ~3268 字 ✅ 市场/外汇/商品
    "economictimes.indiatimes.com-2", "...-3",         # EconTimes ~4000 字 ✅ 转载 Reuters/AP/Bloomberg 全球宏观
    "fortune.com-1",                                    # Fortune   ~4000 字 ✅
    "businessinsider.com-1", "businessinsider.com-2",  # Bus.Insid ~3119 字 ✅
    "forbes.com-1",                                     # Forbes    ~4000 字 ✅(寄稿偏多,靠下游分类滤)
]
```

**实测剔除(抓不到真全文,留着只是污染)**:
- **Benzinga** —— 正文 JS 墙,抽出来只有小标题 + 免责(见上)。
- **FT / SeekingAlpha** —— 硬 paywall,抽取 **0 字**(`ft.com-2` / `seekingalpha.com-1` 实测全空)。
- **dailyfx** —— 抽取 **0 字**。
- **Reuters / Bloomberg / WSJ / MarketWatch / Kitco / Barron's / Economist** —— 免费档**源列表里根本没有**
  (未索引或归别类)→ 不强求;**Reuters/AP/Bloomberg 的通讯社稿由 economictimes 转载替身覆盖**,
  **央行一手消息由 RSS 的 Fed/ECB 覆盖**。

- 通用过滤再叠:`language=en`、`search_fields=title,description`(避正文偶提的噪音)、按需
  `published_after/before`、`sort=published_at`(回填要时序)。
- 白名单是**常量**,可随效果增删;`source_id` 随 TheNewsAPI 变动时用 `/sources` 重核(**务必核对真实 id**)。
- **第二道防线**:`news/extract.py` 质量门(`_MIN_CHARS=500` + paywall/免责短语黑名单 `_is_hollow`)——
  即便某条 paywall/空洞文漏进来,抽取阶段也会丢弃(实测 live 抓取 22 条 → 抽后 19 条,MarketWatch
  RSS 3 条 paywall 被门挡掉,Benzinga 残留 0)。

---

## 6. 与 v1.6 的衔接

- 本文件产出"**干净、带全文、按资产归属的新闻条目**" → 喂 v1.6 §6.4 的 `news/features.py` 算**代码特征**(事件日历/量 z/惊喜)→ 仅 **B 臂**进 `build_feature_block` → A/B 消融(v1.6 §6.5)由评估层裁决"新闻值多少"。
- 回填澄清:NewsAPI 抓 1 个月新闻 = **建管线 + 攒语料/缓存**,**不是**重生成历史预测;**A/B 打分严格前向**(回填新闻有发布滞后泄漏,见 v1.6 §6.5)。
- 实施步骤见 v1.6 §5 **S5**。

## 7. v1.8 升级(2026-06-25)

- **TheNewsAPI 升级 Basic**:**单 token、25 篇/请求**(免费档是 3 key/3 篇)。`THENEWSAPI_KEYS` 现单 key;
  代码 `thenewsapi.py` `min(limit,25)`、`registry.per_asset=15`。只用 `/v1/news/all`(不需要 `/headlines`/`/top`)。
- **关键词分两层**:`ROSTER_QUERIES`(每资产扩充)+ `MACRO_QUERIES`(跨资产宏观主题:美联储/财政·Trump/地缘·能源/欧日央行)。
  宏观频道 `asset=""`,靠分类 `affected_assets` 回填资产,并贡献全局 EPU/GPR/事件信号。
- **新闻语料库**:`news/store.py` 单一 article-level parquet(`data/news/news-YYYY-MM.parquet`,月分区 + uuid 幂等 + body 列
  + `extra`/`schema_version`),既是语料又是缓存。详见 [v1.8-progress.md](refactor/v1.8-progress.md)。
- **逐篇正文喂 LLM 放宽到 3000 字**(`classify._body`);抽取上限 `extract._MAX_CHARS=4000`。
- 文本信号(EPU/GPR/鹰鸽/事件分类)由 `news/textsignals.py` **代码算**(可复现、免成本),不靠 LLM。
