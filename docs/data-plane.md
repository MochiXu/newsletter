# 模块文档 · 数据平面(Rust)

> 对应 [DESIGN.md](../DESIGN.md) §6 的「数据平面」。本文件记录 M0 的实现细节,随开发更新。

## 职责

从数据源抓取核心宏观指标,落地为仓库内的 CSV / markdown,供后续(M1)Python 智能平面读取。

## 模块结构(重构后,面向多数据源扩展)

按「数据 schema / 信息源 / 存储 / 编排」分层,新增数据源成本极低(新建一个文件 + `impl Source`
+ 在 `catalog` 加一张 spec 表 + 在 `run()` 计划里加一行,**不动** trait/错误/新鲜度/存储):

```
src/
  error.rs      统一错误类型(thiserror);单一 Error 枚举 + Result 别名 + Failure 结构
  config.rs     Config::from_env():FRED_API_KEY / data_dir / 新鲜度阈值 / 是否在 CI
  model.rs      数据 schema:Observation(原始观测)、Record(CSV 接缝,8 列勿改)
  catalog.rs    序列定义(常量):SeriesSpec + FRED_CORE / YAHOO_SUPPLEMENT / YAHOO_DEGRADED
  source/
    mod.rs      Source trait + SourceData + 跨源新鲜度校验(staleness_days / MAX_STALENESS_DAYS)
    fred.rs     FredSource(impl Source)+ 纯函数 parse_latest(离线单测)
    yahoo.rs    YahooSource(impl Source,内部 429 退避重试)+ 纯函数 parse_chart(离线单测)
  store.rs      git-as-database:upsert_csv + write_markdown_snapshot
  lib.rs        编排:run() 两段式计划 + runner collect_from(跑源→新鲜度→组装 Record→并失败)
  main.rs       薄入口:env_logger 初始化、读 Config、调 run()、CI 注解、退出码
```

设计要点:
- **Source trait 批量粒度**:`fetch(&self, specs) -> SourceData`,源自己决定发几次请求——FRED 每序列一次,
  未来 CFTC「一次 GET 多行」/ RSS「按 feed 抓」也能套进同一抽象而无冗余请求。
- **横切逻辑集中**:新鲜度校验、`Record` 组装只在 runner `collect_from` 做一次,所有源流经此处,
  新增源白拿;源只返回原始观测 + 软失败(`Failure`)。
- **软/硬错误一个枚举**:源内产生的 = 软(进 `Failure`,run 继续);从 `run()` 冒出的 = 硬(非零退出)。
- **日志**:`log` 门面 + `env_logger`(默认 INFO,`RUST_LOG` 覆盖);所有运行期字符串英文。
  GitHub Actions `::warning::` 注解走 stdout(workflow-command 协议),与 logger 的 stderr 分离。
- **异步友好**:`fetch` 只借用 `&self`/`specs`,未来可平滑改 `async fn` + `join_all`,签名不必反转。

## M0 范围

- 数据源:**FRED**(单一源 + 单一鉴权,最小化 M0 复杂度)
- 抓取方式:`reqwest` **blocking**(M0 只有 6 个序列,不需要 async/tokio;序列增多后再上并发)
- 存储:**git-as-database**(见下),非 SQLite

### 抓取的序列(`src/catalog.rs`)

FRED 主源(`FRED_CORE`):

| 指标 | FRED series_id | 单位 | 说明 |
|---|---|---|---|
| 10Y Treasury | `DGS10` | % | |
| 2Y Treasury | `DGS2` | % | |
| 2s10s Spread | `T10Y2Y` | % | 10Y 减 2Y |
| VIX | `VIXCLS` | index | |
| USD Index (Broad) | `DTWEXBGS` | index | 贸易加权美元(FRED 可靠);≠ ICE 窄口径 DXY |

Yahoo 补充(`YAHOO_SUPPLEMENT`,FRED 给不了的指标,**每次都补**):

| 指标 | Yahoo symbol | 单位 | 说明 |
|---|---|---|---|
| USD Index (DXY) | `DX-Y.NYB` | index | ICE 窄口径 DXY(用户口径) |
| Gold | `GC=F` | USD/oz | COMEX 期货;FRED 伦敦金价序列已下架 |

> 实跑确认 FRED `GOLDAMGBD228NLBM` 已下架(返回 "series does not exist"),故黄金改走 Yahoo;
> 真 DXY 同理(FRED 只有广义美元 DTWEXBGS)。

## API 调用

`GET https://api.stlouisfed.org/fred/series/observations`
参数:`series_id`、`api_key`、`file_type=json`、`sort_order=desc`、`limit=40`。
取最近 40 条里最新的一条非缺失观测(FRED 用 `"."` 表示缺失);limit 取大以越过
长假/发布滞后造成的连续缺失,避免误判「无有效观测」。

**新鲜度校验**:runner `collect_from`(`lib.rs`)比对最新观测日与 `run_date`,若超过
`MAX_STALENESS_DAYS`(14 天,`source/mod.rs`)则视为陈旧、计入失败——防止一条停更/长时间中断的
序列把旧值静默当「今日最新」。校验集中在 runner 一处,所有源(含未来新增源)统一适用。

**安全**:`api_key` 只通过 query 参数传递;`.send()`/`.text()` 出错时立即 `without_url()` 剥离含
key 的 URL,**再据此构造 `Error::Http`**。`error.rs` 故意不给 `reqwest::Error` 实现 `#[from]`,因此
`?` 无法把仍含 key 的原始错误偷渡进来——这是唯一构造路径,key 无论 `{e}`/`{e:#}`/`{e:?}` 都不泄漏到
日志、提交回仓库的快照或 CI 日志(由编译期保证 + 离线回归测试 `http_error_strips_api_key`)。

## Yahoo Finance(免鉴权,补充 + 降级)

用 Yahoo 的 `v8/finance/chart/{symbol}`(读 `meta.regularMarketPrice/Time`)。两种用途:

- **补充(`YAHOO_SUPPLEMENT`,每次都跑)**:FRED 给不了的指标——真 DXY(`DX-Y.NYB`)、黄金(`GC=F`)。
- **降级(`YAHOO_DEGRADED`,仅 FRED 零产出时)**:用 Yahoo 顶上 FRED 那部分——`^GSPC`/`^VIX`/`^TNX`(现直接报 %)。

Yahoo 是非官方接口且按 IP 限流(429):客户端带浏览器 UA、请求间留 ~1.3s 间隔、对失败线性退避重试。
口径**不与 FRED 行混用**(各自符号独立记录)。

## 存储:git-as-database

M0 跑在 GitHub Actions 临时 runner 上,SQLite 文件不跨运行持久化。因此把数据
**提交回仓库**,用 git 当数据库:零基建、天然有历史、diff 可读。

- `data/observations.csv` — 按 `run_date` **幂等写入**(读改写:丢弃同 run_date 旧行再写),
  同日重跑不产生重复行;列:`run_date,series_id,label,obs_date,value,unit,source,note`
- `data/snapshots/<run_date>.md` — 人类可读的当日快照(同日重跑覆盖);失败原因经
  单行化/截断/转义后写入,避免破坏 markdown 渲染

SQLite/DuckDB 接缝不再是 M1 的前置条件。当前契约就是 `observations.csv` + markdown 快照(git-as-database);等需要复杂历史查询、rolling feature、跨表 join 或更大数据量时,再由 CSV 重建或新增 SQLite/DuckDB writer。

## 运行

```bash
# 本地:把 key 放进 .env(见 .env.example),然后
cargo run --release            # = cargo run --release --bin fetch
RUST_LOG=newsletter=debug cargo run --release   # 看 Yahoo 重试/退避等详细日志
cargo test                     # 离线单测:解析 + CSV 转义 + 新鲜度 + api_key 不泄漏
cargo clippy --all-targets     # 静态检查(应无告警)
```

环境变量:`FRED_API_KEY`(必需);`RUST_LOG`(可选,默认 `info`)。

## 调度(`.github/workflows/daily.yml`)

- `cron: "0 23 * * *"`(UTC)= 北京时间每天 07:00,总结隔夜美国 session
- 也支持 `workflow_dispatch` 手动触发
- 需在仓库 Settings → Secrets 添加 **`FRED_API_KEY`**
- 跑完自动 `git add data/ && commit && push`(`permissions: contents: write`)
- 注意:定时任务只在**默认分支**生效,合并到 main 后才会按 cron 跑

## 已加固(M0 审查后)

- [x] 新鲜度校验:停更/长中断序列不再被静默当「今日最新」
- [x] `limit=40` 越过长假/发布滞后,避免误判无数据
- [x] api_key 用 `without_url()` 从错误对象剥离(代码保证不泄漏)
- [x] CSV 按 `run_date` 幂等写入;空/缺失文件也正确写表头
- [x] 失败文本单行化/截断后再写快照
- [x] CI:`concurrency` 防并发 + push 失败 rebase 重试
- [x] 部分序列失败时输出 `::warning::` 注解(CI 可见)
- [x] Yahoo 免鉴权回退源:无 FRED key 也能产出真实数据(限流退避;口径不与 FRED 混用)
- [x] 重构为模块化、面向多源扩展:`Source` trait 统一 FRED/Yahoo;`thiserror` 取代 anyhow;
      `log`+`env_logger` 日志门面;运行期字符串英文;`#[from] reqwest::Error` 禁用 + 离线回归测试守 api_key

## 待办 / 后续

> 全局路线 / 技术债 / 开放问题见 [TODO.md](TODO.md)。

- [x] 用真实 key 跑通并连续产出快照(见 README/TODO 当前状态)
- [x] 黄金从已下架的 FRED `GOLDAMGBD228NLBM` 切到 Yahoo `GC=F`;DXY 用 Yahoo `DX-Y.NYB`,并保留 FRED `DTWEXBGS` 作为广义美元口径
- [ ] DXY/Gold 换更贴盘口/更稳定的源(当前 Yahoo 可用但非官方,后续可加替代源或 fallback)
- [ ] 加 CFTC COT(每周)、FedWatch/ZQ、ETF flow 等新数据源
- [ ] 序列增多后切 async 并发抓取
- [ ] 复杂查询阶段引入 SQLite/DuckDB 接缝供 Python / frontend analytics 读取
