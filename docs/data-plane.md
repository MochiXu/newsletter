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
参数:`series_id`、`api_key`、`file_type=json`、`sort_order=desc`、`limit=10`。
取最新一条非缺失观测(FRED 用 `"."` 表示缺失)。

**安全**:`api_key` 只通过 query 参数传递,**不写进任何错误信息或提交的快照**(见 `src/fred.rs`)。

## 存储:git-as-database

M0 跑在 GitHub Actions 临时 runner 上,SQLite 文件不跨运行持久化。因此把数据
**提交回仓库**,用 git 当数据库:零基建、天然有历史、diff 可读。

- `data/observations.csv` — append-only,列:
  `run_date,series_id,label,obs_date,value,unit,source,note`
- `data/snapshots/<run_date>.md` — 人类可读的当日快照(同日重跑覆盖)

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

## 待办 / 后续

- [ ] 用真实 key 跑通一次(M0 验收:连续 3 天产出快照)
- [ ] DXY/Gold 换更贴盘口的源(Stooq/Yahoo)
- [ ] 加 CFTC COT(每周)、RSS 新闻(M2)
- [ ] 序列增多后切 async 并发抓取
- [ ] M1:引入 SQLite 接缝供 Python 读取
