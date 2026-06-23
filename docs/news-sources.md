# 新闻源使用方式(news sourcing & extraction)

> 本文件 = **我们怎么获取 / 抽取 / 清洗新闻**(数据采集运营手册)。
> 新闻**怎么进预测**(代码特征 + A/B 消融)见 [refactor/v1.6-progress.md §6](refactor/v1.6-progress.md);
> 本文件是它的上游(把"原始新闻"变成"干净、可用、带正文的条目")。
> 现状代码:`py/newsletter/news.py`(RSS 抓取 + LLM 分类),将按 §4 拆成 `news/` 包。

---

## 1. 三个源 + 角色分工(准确版)

> **测试 key(仅本地测试;真实运行从 `.env` 读;公开仓库前重置)**:
> - NewsAPI.org:`384a255227534a488a4683d2487cf397` → 环境变量 `NEWSAPI_KEY`
> - TheNewsAPI:`ntqtPMgbiSFDeA13QVAKqg3lDPzc2AsDNnN7OjvH` → 环境变量 `THENEWSAPI_KEY`

| | RSS(现有) | NewsAPI.org | TheNewsAPI |
|---|---|---|---|
| 历史 | 无 | **免费 = 1 个月**(硬墙) | 历史档位未公示(需 key 实测) |
| 延迟 | 无 | **24 小时**(免费) | **实时** |
| 单次条数 | 抓 feed | 100 条/页 | **3 条/请求**(免费);Basic 25 |
| 日配额 | 无 | 100 次/天 | **100 次/天**(免费)→ 300 条/天 |
| 端点限制 | — | `/v2/everything` 全档 | `/v1/news/all`+`/top` **全档**;Headlines 需 $49 |
| 生产 | 可 | **禁止**(仅开发) | 无明文限制(免费亦可测) |
| 正文 | 摘要 ~300 字 | 标题+描述 | **仅 60 字 snippet** |
| **角色** | **live 兜底**(零配额) | **1 个月密集回填**(100 条/页是杀手锏) | **live 每日**(实时;300 条/天精准查询够用) |

**结论(纠正前评估)**:TheNewsAPI 免费档对 **live 每日简报够用**(实时 + 300 条/天 + 精准按资产/优质源查询);它不擅长的是**密集回填**(3 条/请求),那交给 NewsAPI.org(100 条/页)。**三者都只给薄正文 → 全部依赖我们自建的正文抽取(§3)。** 付费 TheNewsAPI Basic($19/月)只在需要更大量 / 生产背书时再开。

---

## 2. TheNewsAPI 准确参考(读自官方文档)

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
news/  base.py(NewsProvider 协议 + 能力元数据)  rss.py  newsapi.py  thenewsapi.py
       extract.py(§3 正文抽取)  registry.py(选源 + 跨源去重 + 每资产查询)
       classify.py(LLM 分类,迁自 news.py)  cache.py(磁盘缓存)  features.py(v1.6 §6.4)
```
- **按角色选源,跨源合并去重**(新闻是多源并集,非"首个成功"),详见 v1.6 §6.3。
- **key 从 `.env`**(`NEWSAPI_KEY`/`THENEWSAPI_KEY`);缺 key 跳过该源;RSS 永远在。

---

## 5. 优质源筛选(source allowlist)

主动只取可靠发布方,降噪。建一份**优质源白名单**常量(类似 `catalog`):
- TheNewsAPI:用 `source_ids`(先 `GET /v1/news/sources?categories=business&language=en` 枚举,挑 reuters/cnbc/marketwatch/... 的 `source_id`)或 `domains`。
- NewsAPI.org:用 `domains=reuters.com,cnbc.com,marketwatch.com,ft.com,wsj.com,bloomberg.com,apnews.com`(免费档 `sources`≤20,`domains` 更灵活)。
- 通用:`categories=business` + `language=en` + `locale=us`。
- **上线前实测**:两家都**未公开保证** Reuters/Bloomberg/WSJ/FT 一定被索引(且常 paywall)→ 用 `/sources` + domain 查询各自实测覆盖,白名单只放实测可用的。

---

## 6. 与 v1.6 的衔接

- 本文件产出"**干净、带全文、按资产归属的新闻条目**" → 喂 v1.6 §6.4 的 `news/features.py` 算**代码特征**(事件日历/量 z/惊喜)→ 仅 **B 臂**进 `build_feature_block` → A/B 消融(v1.6 §6.5)由评估层裁决"新闻值多少"。
- 回填澄清:NewsAPI 抓 1 个月新闻 = **建管线 + 攒语料/缓存**,**不是**重生成历史预测;**A/B 打分严格前向**(回填新闻有发布滞后泄漏,见 v1.6 §6.5)。
- 实施步骤见 v1.6 §5 **S5**。
