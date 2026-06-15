# 模块文档 · 数据平面(Rust)

> 对应 [DESIGN.md](../DESIGN.md) §6 的「数据平面」。本文件记录 M0 的实现细节,随开发更新。

## 职责

从数据源抓取核心宏观指标,落地为仓库内的 CSV / markdown,供后续(M1)Python 智能平面读取。

## M0 范围

- 数据源:**FRED**(单一源 + 单一鉴权,最小化 M0 复杂度)
- 抓取方式:`reqwest` **blocking**(M0 只有 6 个序列,不需要 async/tokio;序列增多后再上并发)
- 存储:**git-as-database**(见下),非 SQLite

### 抓取的序列(`src/series.rs`)

| 指标 | FRED series_id | 单位 | 说明 |
|---|---|---|---|
| 10Y Treasury | `DGS10` | % | |
| 2Y Treasury | `DGS2` | % | |
| 2s10s Spread | `T10Y2Y` | % | 10Y 减 2Y |
| VIX | `VIXCLS` | index | |
| USD Index (Broad) | `DTWEXBGS` | index | **DXY 代理**:贸易加权美元,口径与 ICE DXY 不同 |
| Gold (London AM fix) | `GOLDAMGBD228NLBM` | USD/oz | |

> DXY/Gold 用 FRED 代理是 M0 的取舍;M1/M2 可换 Stooq/Yahoo 精修盘口口径。

## API 调用

`GET https://api.stlouisfed.org/fred/series/observations`
参数:`series_id`、`api_key`、`file_type=json`、`sort_order=desc`、`limit=40`。
取最近 40 条里最新的一条非缺失观测(FRED 用 `"."` 表示缺失);limit 取大以越过
长假/发布滞后造成的连续缺失,避免误判「无有效观测」。

**新鲜度校验**:`main.rs` 比对最新观测日与 `run_date`,若超过 `MAX_STALENESS_DAYS`
(14 天)则视为陈旧、计入失败——防止一条停更/长时间中断的序列把旧值静默当「今日最新」。

**安全**:`api_key` 只通过 query 参数传递;`.send()`/`.text()` 出错时立即
`without_url()` 剥离含 key 的 URL,因此 key 不会进入错误对象 → 不泄漏到日志、
提交回仓库的快照或 CI 日志(由代码保证,而非依赖格式化方式)。

## 回退源:Yahoo Finance(免鉴权)

当 FRED 整体不可用(缺 key / key 无效)时,自动回退到 Yahoo 的
`v8/finance/chart/{symbol}`(读 `meta.regularMarketPrice/Time`),让管道没有 FRED key
也能产出真实数据。

- 回退序列(各自符号**独立记录,不与 FRED 行混用口径**):`^GSPC` S&P500、`^VIX` VIX、
  `^TNX` 10Y 收益率(现直接报 %,不再 ×10)、`DX-Y.NYB` ICE 窄口径 DXY、`GC=F` COMEX 黄金期货
- Yahoo 是非官方接口且按 IP 限流(429):客户端带浏览器 UA、请求间留 ~1.3s 间隔、对失败线性退避重试
- 仅在 FRED 零产出时触发;填入有效 FRED key 后主源即变回 FRED

## 存储:git-as-database

M0 跑在 GitHub Actions 临时 runner 上,SQLite 文件不跨运行持久化。因此把数据
**提交回仓库**,用 git 当数据库:零基建、天然有历史、diff 可读。

- `data/observations.csv` — 按 `run_date` **幂等写入**(读改写:丢弃同 run_date 旧行再写),
  同日重跑不产生重复行;列:`run_date,series_id,label,obs_date,value,unit,source,note`
- `data/snapshots/<run_date>.md` — 人类可读的当日快照(同日重跑覆盖);失败原因经
  单行化/截断/转义后写入,避免破坏 markdown 渲染

SQLite 接缝(DESIGN §6 的契约)待 **M1** Python 需要查询历史时再引入;届时可由 CSV 重建或新增 SQLite writer。

## 运行

```bash
# 本地:把 key 放进 .env(见 .env.example),然后
cargo run --release            # = cargo run --release --bin fetch
cargo test                     # 离线单测:解析 + CSV 转义
```

环境变量:`FRED_API_KEY`(必需)。

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

## 待办 / 后续

- [ ] 用真实 key 跑通一次(M0 验收:连续 3 天产出快照)
- [ ] 确认 `GOLDAMGBD228NLBM` 是否仍更新;若被新鲜度校验判为陈旧则换 Stooq/Yahoo
- [ ] DXY/Gold 换更贴盘口的源(Stooq/Yahoo)
- [ ] 加 CFTC COT(每周)、RSS 新闻(M2)
- [ ] 序列增多后切 async 并发抓取
- [ ] M1:引入 SQLite 接缝供 Python 读取
