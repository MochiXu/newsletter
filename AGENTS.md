# agents.md — 给 AI 协作者的工作约定

> 本文件给在本仓库里干活的 AI 协作者(Claude / 其它 agent)。记录**容易踩、且踩了代价大**的纪律。
> 高层愿景看 [DESIGN.md](DESIGN.md);架构进度看 [docs/refactor/](docs/refactor/readme.md);
> 新闻采集运营看 [docs/news-sources.md](docs/news-sources.md)。

---

## 头号纪律:point-in-time 正确性(不偷看未来)

这是本项目(一个**投研/回测**系统)的头号红线,也是最容易静默踩中的坑。

**原则**
- 任何"历史回放 / 回填 / 回测 / 重生成过去某天产物"的任务,**第一件事**是确认时间点正确性:
  喂给那一天的所有输入(新闻、价格、特征、抓取的网页、甚至 LLM 自身知识)都必须"截至该日",
  **绝不含该日之后的信息**。look-ahead 泄漏是回测的头号死罪。
- **存在 ≠ 接线**。不要因为代码里"有"一个 backfill/历史模式就相信它生效。从真实入口
  (CLI / cron / API)沿调用链追到底,确认那个模式**真被传进去了**。死代码经常长得像在工作。
- **"跑通了、产出看着合理"≠"正确"**。验证要落在**最关键的不变量**上(回放场景 =
  所有输入时间戳是否都早于目标日),而不是"有没有报错 / 卡片上有没有数据"。
- **同名陷阱**:一个标签可能只覆盖部分含义(如 `source=backfill` 标的是"预测日是历史日",
  **不**保证"新闻尊重了时间边界")。确认它到底保证了什么,别让名字替你做假设。
- **给关键不变量加断言/测试**(如"回放运行中无任何输入晚于目标日"),让违反时**大声失败**,
  而非静默产出脏数据。

**血的教训(2026-06-24 复盘)**
> 6 月历史数据回填时,新闻被挂上了运行日(未来)的新闻 = 先知泄漏。根因:CLI 只能传
> `live`/`none`,`backfill` 时间窗是**死代码**从没被调用;而我看到 pipeline 里"有" backfill 模式
> + docstring 写着"回放日历史新闻",就默认系统处理了,从没去查"抓到的新闻时间戳是否真早于回放日"。
> 特征层一开始就写了"因果滚动,不偷看未来",**但同一条纪律没贯彻到新闻层**——这正是危险所在:
> 局部做对了会给全局虚假的安全感。
>
> 修复:`pipeline._effective_news_mode` 在抓新闻的咽喉点强制"过去日 → backfill",
> 并加了断言式测试(`tests/test_pipeline.py`)。

---

## 本仓库的具体守则

- **历史回放新闻走 backfill**:`build_report` 用 `_effective_news_mode` 自动把"过去日 + live"
  降级为 backfill(TheNewsAPI 时间窗 `published_before<回放日`,实测排他边界;并去掉无法时间过滤的 RSS)。
  改新闻路径时**不要绕过这个咽喉点**。
- **新闻源白名单用真实 source_id**:`/sources` 端点拿到的真实 id(如 `cnbc.com-1`,不是臆造的
  `cnbc.com-124`),且逐源**实测抽取**能拿到真全文才纳入。剔除 paywall/空洞源(Benzinga/FT/SeekingAlpha)。
  见 [news-sources.md §5](docs/news-sources.md)。抽取层有第二道质量门(`_is_hollow` + `_MIN_CHARS`)。
- **forward / backfill 诚实标注**:回填数据含记忆污染 + 历史抓取局限,**只有 forward(前向)数据可用于打分**;
  前端对 backfill 数据要标注,绝不展示伪命中率。
- **代码算数字,LLM 只解释**:数值/特征/基线一律代码算;LLM 只做解释和叙述,不产出被当作事实的数字。

---

## 跑起来 / 验证(本机)

- Python 在 conda env `myTools`(非标准路径):先 `source /Users/mochi/environment/miniconda3/etc/profile.d/conda.sh && conda activate myTools`。
- 在 Claude Code 的 shell 里跑会注入官方 ANTHROPIC_BASE_URL;调用中转站/本项目脚本时需 `env -u ANTHROPIC_BASE_URL`。
- 测试:`PYTHONPATH=py python -m pytest py/newsletter/tests/ -q`。改了管线/新闻/回填逻辑,
  **务必想清楚要断言的那个不变量**(尤其 point-in-time),再补测试。
- 密钥只在 `.env`(已 gitignore),绝不提交/打印。`data/news_cache/` 抓取的全文不入库(版权)。

---

## Git

- **不要自动 commit / push**;每次都先确认(沿用全局 CLAUDE.md)。
