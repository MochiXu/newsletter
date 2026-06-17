# 静态站部署计划：Cloudflare Pages + 周期性内容发布

> 状态：计划文档，不包含实现。
> 目标读者：后续实现者 / 未来自己。
> 当前倾向：Web 端先保持静态站，不做大而全 SaaS；为未来 iOS App 复用内容数据契约预留空间。

## 1. 目标

把当前 newsletter 前端部署成一个**周期性更新的静态站**：

- GitHub Actions 每天生成市场数据、AI 简报和前端可消费的 JSON。
- Cloudflare Pages 托管 `frontend/app/dist`。
- 静态站通过 `/data/briefs.json` 或未来拆分后的 `/data/public/*.json` 读取内容。
- 暂不引入登录、支付、多租户、在线 API server。
- 保持后续演进空间：未来 iOS App 可以直接复用同一套公开 JSON 内容源。

核心原则：

1. **先发布、先 dogfood，不做过早平台化。**
2. **Web 只是分发渠道，不是最终 SaaS 架构。**
3. **数据契约尽量 App-friendly，避免只服务当前 React 页面。**
4. **保留当前 Rust/Python 内容生产流水线。**

---

## 2. 当前项目上下文

当前已有结构：

```text
newsletter/
  src/                         # Rust 数据平面：FRED/Yahoo 抓取
  py/newsletter/               # Python 智能平面：LLM 简报、新闻分类、假设复盘
  data/
    observations.csv
    snapshots/<date>.md
    briefs/<date>.md
    briefs/<date>.json
    briefs.json                # 当前前端聚合数据接缝
    hypotheses.csv
  frontend/app/                # React + Vite + TS 小票阅读器
    scripts/copy-data.mjs      # predev/prebuild 拷贝 data/briefs.json 到 public/data/
    src/...
  .github/workflows/daily.yml  # 当前 daily pipeline：抓数 -> 简报 -> commit data/
```

当前部署相关事实：

- `frontend/app` 已能 `npm run build`。
- 前端 build 前会尝试复制仓库根 `data/briefs.json`。
- 若 `data/briefs.json` 缺失，前端回退到内置 demo 数据。
- 当前 GitHub Actions 主要负责每日生成并提交 `data/`。
- 尚未有 Cloudflare Pages 部署 workflow。

---

## 3. 建议的阶段路线

## Phase 1：最小静态发布

目标：最快把当前 Web 小票站发布出去。

```text
GitHub Actions daily
  ├─ cargo run --release --bin fetch
  ├─ PYTHONPATH=py python3 -m newsletter.brief
  ├─ commit data/
  └─ 可选：触发 Cloudflare Pages build

Cloudflare Pages
  └─ frontend/app/dist
      └─ /data/briefs.json
```

实现策略：

- 使用 Cloudflare Pages 连接 GitHub 仓库。
- 设置 build command：

```bash
cd frontend/app && npm ci && npm run build
```

- 设置 build output directory：

```text
frontend/app/dist
```

- 确保 Cloudflare build 时能拿到仓库根的 `data/briefs.json`。
  - 当前 `scripts/copy-data.mjs` 已从仓库根复制到 `frontend/app/public/data/`。
  - 因此只要 `data/briefs.json` 已提交到 repo，Cloudflare build 就能打包进去。

优点：

- 最小改动。
- 不引入额外后端。
- 和当前代码结构一致。

风险：

- 如果 daily workflow 提交 `data/briefs.json` 后没有触发 Cloudflare build，网站不会自动更新。
- 如果 Cloudflare Pages 只在代码变更时 build，而 `data/` 由 GitHub Actions push 到同一分支，通常会触发；但需要实测确认。

验收：

- Cloudflare Pages 首次部署成功。
- 访问站点能看到真实 `data/briefs.json`，不是 demo。
- 每日 GitHub Actions 跑完并 push 后，Cloudflare Pages 自动重新部署。

---

## Phase 2：把数据契约整理成 App-friendly 静态 Content API

目标：为未来 iOS App 复用内容源做准备，避免一个越来越大的 `briefs.json` 既喂 Web 又喂 App。

建议新增公开静态内容目录：

```text
data/public/
  latest.json
  index.json
  briefs/
    2026-06-17.json
    2026-06-16.json
```

### 2.1 `latest.json`

用途：App / Web 快速发现最新一期。

示例：

```json
{
  "date": "2026-06-17",
  "generatedAt": "2026-06-17T07:00:00+08:00",
  "briefUrl": "/data/public/briefs/2026-06-17.json"
}
```

### 2.2 `index.json`

用途：历史列表、时间线、分页入口。

示例：

```json
{
  "generatedAt": "2026-06-17T07:00:00+08:00",
  "briefs": [
    {
      "date": "2026-06-17",
      "weekday": "周三",
      "issue": 2,
      "headline": "……",
      "tone": "risk-off",
      "url": "/data/public/briefs/2026-06-17.json"
    }
  ]
}
```

### 2.3 单日 brief JSON

用途：Web / iOS 读取某一天完整内容。

可复用当前 `render_json()` 输出结构：

```json
{
  "date": "2026-06-17",
  "weekday": "周三",
  "issue": 2,
  "time": "07:00 CST",
  "tone": "neutral",
  "headline": "……",
  "metrics": [],
  "facts": [],
  "reads": [],
  "hypotheses": [],
  "impacts": [],
  "reviews": [],
  "news": []
}
```

实现建议：

- 保留当前 `data/briefs.json`，避免立刻改前端。
- 新增一个导出器，例如：

```text
py/newsletter/export_public.py
```

- 让 `brief.py` 在生成单日 JSON 后同步维护：
  - `data/briefs.json`：当前 Web 合约；
  - `data/public/latest.json`；
  - `data/public/index.json`；
  - `data/public/briefs/<date>.json`。

这样未来 iOS 可以直接请求：

```text
https://your-domain.com/data/public/latest.json
https://your-domain.com/data/public/index.json
https://your-domain.com/data/public/briefs/2026-06-17.json
```

验收：

- 当前 Web 不受影响。
- 新的 `data/public/` 文件能被 Cloudflare 静态服务。
- 单日 JSON 不依赖 Web 前端实现细节。

---

## Phase 3：Cloudflare Pages 自动发布打磨

目标：让 daily content pipeline 和 Cloudflare Pages 发布稳定联动。

两种可选方式：

### 方案 A：Cloudflare Pages 连接 GitHub 自动构建

流程：

```text
GitHub Actions daily push data/
  ↓
GitHub main branch updated
  ↓
Cloudflare Pages detects push
  ↓
Build frontend/app
```

优点：

- Cloudflare UI 配置简单。
- 不需要在 GitHub Actions 里保存 Cloudflare API token。

缺点：

- 需要确认由 GitHub Actions bot push 的 commit 是否稳定触发 Cloudflare Pages build。
- build 日志主要在 Cloudflare 控制台。

### 方案 B：GitHub Actions 主动触发 Cloudflare Pages Deploy Hook

流程：

```text
GitHub Actions daily
  ├─ generate data
  ├─ commit + push
  └─ curl Cloudflare Pages deploy hook
```

优点：

- 更新链路更显式。
- 即使 Cloudflare 没自动感知，也可以主动触发。

缺点：

- 需要配置 Cloudflare deploy hook secret。
- 多一步凭证管理。

建议：

- 先用方案 A。
- 如果发现数据 commit 后没有自动触发部署，再切方案 B。

---

## 4. 未来 iOS App 的复用方式

未来 iOS App 初版可以完全不需要在线 API server，只作为精美阅读器：

```text
iOS SwiftUI App
  ↓ HTTPS GET
Cloudflare static JSON
  ├─ /data/public/latest.json
  ├─ /data/public/index.json
  └─ /data/public/briefs/<date>.json
```

初版 iOS 功能建议：

- 今日简报。
- 历史列表。
- 本地收藏。
- 本地已读状态。
- 离线缓存最近 N 天。
- 暗色模式。
- Widget / 本地每日提醒。

此阶段不需要：

- 登录。
- 订阅。
- 多租户。
- 个性化 API。
- 用户数据库。

当未来需要 iOS 收费或个性化时，再新增后端能力：

```text
API backend
  ├─ StoreKit transaction verification
  ├─ user entitlement
  ├─ premium content access
  ├─ watchlist / preferences
  └─ push notification token management
```

当前 Rust/Python 后端依然有价值，但它的定位是：

```text
content generation pipeline
```

而不是现在就做在线 SaaS API。

---

## 5. 需要确认的问题

### Q1：Cloudflare Pages 项目连接方式

选择：

1. **Cloudflare UI 直接连接 GitHub repo**。
   - 推荐默认方案。
   - 简单、少凭证。
2. **GitHub Actions 手动部署到 Cloudflare Pages**。
   - 更可控。
   - 需要 Cloudflare API token。

建议：先选 1。

### Q2：域名

选择：

1. 使用 Cloudflare Pages 默认域名先试跑。
2. 绑定你自己的自定义域名。

建议：先默认域名验证链路；确认没问题后再绑自定义域名。

### Q3：是否现在新增 `data/public/` Content API

选择：

1. 先不新增，只部署当前 `data/briefs.json`。
2. 部署前顺手新增 `data/public/`，为 iOS 预留。

建议：如果只想最快上线，选 1；如果希望少走回头路，选 2。

我的倾向：**选 2，但只做最小版本**：`latest.json`、`index.json`、`briefs/<date>.json`，不要引入 API server。

### Q4：是否保留 demo fallback

选择：

1. 保留 demo fallback。
2. 生产环境如果没有真实数据就显示空态 / 错误态。

建议：

- 开发环境保留 demo。
- 生产环境最好显示“暂无真实数据”，避免用户误以为 demo 是真实市场简报。

后续可以用环境变量控制：

```text
VITE_ALLOW_DEMO_FALLBACK=true/false
```

---

## 6. 具体实施任务草案

> 下面是后续真正实现时的任务拆分；本计划阶段不执行。

### Task 1：确认 Cloudflare Pages 构建配置

目标：确定静态站能从 `frontend/app` 构建。

配置：

```text
Framework preset: None / Vite
Root directory: / 或 frontend/app，二选一后实测
Build command: cd frontend/app && npm ci && npm run build
Build output directory: frontend/app/dist
Node version: 使用 Cloudflare 默认 LTS；如失败再 pin 到项目支持版本
```

验证：

```bash
cd frontend/app
npm ci
npm run build
```

预期：`frontend/app/dist` 生成成功。

### Task 2：确保 `data/briefs.json` 总是存在

目标：避免生产构建回退 demo。

可选实现：

```bash
PYTHONPATH=py python3 -m newsletter.export_json
```

如果 `data/briefs/<date>.json` 已存在，则可重建 `data/briefs.json`。

验收：

```bash
test -f data/briefs.json
```

### Task 3：部署当前 Web 静态站

目标：让 Cloudflare Pages 成功部署当前 React/Vite 前端。

步骤：

1. 在 Cloudflare Pages 创建项目。
2. 连接 GitHub repo。
3. 设置 build command / output directory。
4. 首次 deploy。
5. 打开预览 URL。
6. 在 browser network 中确认 `/data/briefs.json` 返回 200。

验收：

- 页面能打开。
- 时间线和小票渲染正常。
- 显示真实数据，不是 demo。

### Task 4：验证 daily pipeline 是否触发重新部署

目标：确认每日数据更新后网站同步更新。

步骤：

1. 手动触发 `.github/workflows/daily.yml`。
2. 确认 workflow push 了新的 `data/` commit。
3. 观察 Cloudflare Pages 是否自动构建。
4. 打开网站确认最新日期更新。

若没有自动构建：

- 增加 Cloudflare Pages Deploy Hook。
- 在 GitHub Actions commit 后 curl deploy hook。

### Task 5：新增 App-friendly Content API（可选但建议）

目标：生成 `data/public/` 静态 JSON，为 iOS 复用。

可能修改文件：

```text
py/newsletter/export_public.py          # 新增
py/newsletter/brief.py                  # 在每日流程里调用导出
py/newsletter/tests/test_brief.py       # 增加导出测试
frontend/app/scripts/copy-data.mjs      # 可选：复制整个 data/public
frontend/app/src/data/loadBriefs.ts     # 暂不改，保持当前 briefs.json 合约
```

验收：

```bash
PYTHONPATH=py python3 -m unittest newsletter.tests.test_brief -v
PYTHONPATH=py python3 -m newsletter.export_public
find data/public -maxdepth 3 -type f | sort
```

预期文件：

```text
data/public/latest.json
data/public/index.json
data/public/briefs/<date>.json
```

### Task 6：生产环境 demo fallback 策略

目标：避免生产站无数据时展示 demo 市场简报。

可能修改文件：

```text
frontend/app/src/data/loadBriefs.ts
frontend/app/src/App.tsx
frontend/app/.env.production.example 或 docs/frontend-plane.md
```

建议逻辑：

- 开发环境：允许 demo fallback。
- 生产环境：如果真实数据缺失，显示空态和错误说明。

验收：

```bash
cd frontend/app
npm run build
```

并手动测试：

- 有 `data/briefs.json`：显示真实数据。
- 无 `data/briefs.json` 且生产模式：显示空态，不显示 demo。

---

## 7. 风险和取舍

### 风险 1：Cloudflare build 是否能稳定拿到 daily data commit

缓解：

- 首先实测 GitHub bot push 是否触发 Cloudflare build。
- 如不稳定，使用 Deploy Hook。

### 风险 2：`briefs.json` 越来越大

短期可接受。中期用 `data/public/index.json + briefs/<date>.json` 拆分。

### 风险 3：生产环境展示 demo

需要在上线前决定是否禁用生产 demo fallback。

### 风险 4：未来 iOS 与 Web 数据需求分叉

缓解：

- 不让 iOS 直接依赖 Web UI 形状。
- 用 `data/public/` 作为稳定 content API。
- Web 当前 `briefs.json` 可继续保留为兼容层。

### 风险 5：过早引入后端

当前不建议引入。只有当出现以下需求再做：

- 付费订阅。
- 登录。
- 个性化 watchlist。
- 多设备同步。
- push notification server。
- premium/private content access control。

---

## 8. 推荐决策

当前推荐：

1. **Web 部署选 Cloudflare Pages。**
2. **先用 GitHub repo 自动构建，不急着写 Cloudflare API 部署脚本。**
3. **保留当前 `data/briefs.json` 合约，最快上线。**
4. **随后新增 `data/public/` 静态 Content API，为 iOS 做准备。**
5. **暂不做用户、支付、多租户、在线 API server。**
6. **未来 iOS 初版直接读 Cloudflare 静态 JSON，等收费/个性化信号明确后再加后端。**

最小上线路径：

```text
1. 确保 data/briefs.json 存在
2. Cloudflare Pages 连接 GitHub repo
3. 配置 frontend/app build
4. 首次部署
5. 手动触发 daily workflow
6. 验证 Cloudflare 自动更新
```

---

## 9. 后续如果进入实现，建议先问清楚的 4 个问题

1. Cloudflare Pages 是否已经有账号/项目，还是要从零创建？
2. 是否有准备绑定的域名？
3. 上线第一版是否允许 demo fallback？
4. 是否这次就一起做 `data/public/`，还是只部署当前 `briefs.json`？
