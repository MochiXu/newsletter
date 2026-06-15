# 模块文档 · 智能平面(Python)

> 对应 [DESIGN.md](../DESIGN.md) §6 的「智能平面」。本文件记录 M1 的实现细节。

## 职责

读取数据平面产出(`data/observations.csv`)→ 结合宏观传导图 → 调 Claude 生成**四层简报**
→ 渲染 markdown → 存本地 + 推飞书。

## 设计取舍:纯标准库,零第三方依赖

只用 `urllib`/`json`/`csv`/`hmac`/`hashlib` 等 stdlib——不引入 `anthropic` SDK / `pydantic` /
`requests`。理由:任何有 python3 的机器/CI 都能直接跑,免去 venv/pip 安装的脆弱性;此项目
瓶颈在 prompt 与框架迭代,不在库生态。后续若需要可再换官方 SDK。

## 数据流

```
data/observations.csv ──(data.load_latest)──▶ 最新 run_date 的观测
                                                    │
              framework/linkage_map.md ─────────────┤
                                                    ▼
                                       llm.generate_brief(data, linkage)
                                          │            │
                       有 ANTHROPIC_API_KEY            无 key / 调用失败
                                          ▼            ▼
                              四层结构化简报          None(仅事实层)
                                          └──────┬─────┘
                                                 ▼
                          render.render_markdown / render_text
                                                 │
                        ┌────────────────────────┼─────────────────────┐
                        ▼                                               ▼
            data/briefs/<run_date>.md(始终存,git-as-database)   deliver.feishu.push_text
                                                                  (配了 FEISHU_WEBHOOK 才推)
```

## 四层结构(产品灵魂)

`llm.py` 用 **tool use 强制结构化输出**(工具 `emit_brief`,`tool_choice` 锁定该工具):

| 层 | 字段 | 纪律 |
|---|---|---|
| 事实层 | `facts[]` | 只复述数据,不加判断 |
| 解读层 | `interpretation[]` | regime/偏离含义,标注为判断 |
| 假设层 | `hypotheses[]`(`if_then`+`invalidation`) | 可证伪,必带失效条件 |
| 影响层 | `impact[]`(`asset`+`watch`) | 观察点,**非买卖建议** |

外加 `headline` 一句话总览。system prompt 写死纪律:区分事实/判断、假设可证伪、只给观察点、
不承诺收益、中文输出。

## Claude API 调用(`llm.py`)

- 端点:`POST https://api.anthropic.com/v1/messages`
- headers:`x-api-key`、`anthropic-version: 2023-06-01`、`content-type: application/json`
- 模型:默认 `claude-sonnet-4-6`(`ANTHROPIC_MODEL` 可覆盖为 `claude-opus-4-8`)
- `max_tokens: 4096`;`tools=[emit_brief]` + `tool_choice={"type":"tool","name":"emit_brief"}`
- 读取:遍历 `content`,取 `type=="tool_use"` 且 `name=="emit_brief"` 块的 `input`

## 交付:飞书机器人(`deliver/feishu.py`)

- 自定义机器人 webhook,`msg_type=text`
- `FEISHU_SECRET` 存在时按飞书算法签名(HMAC-SHA256,`{timestamp}\n{secret}` 为 key)
- **始终先把简报存 `data/briefs/<run_date>.md`**(本地兜底);配了 `FEISHU_WEBHOOK` 才额外推送
- Telegram/邮件后续再加

## 运行

```bash
# 仓库根目录;先确保 data/observations.csv 已由数据平面生成
PYTHONPATH=py python3 -m newsletter.brief
PYTHONPATH=py python3 -m unittest newsletter.tests.test_brief -v   # 离线单测
```

环境变量(均可选,见 `.env.example`):`ANTHROPIC_API_KEY`、`ANTHROPIC_MODEL`、
`FEISHU_WEBHOOK`、`FEISHU_SECRET`。

## 优雅降级

- 无 `ANTHROPIC_API_KEY`(或 LLM 调用异常)→ 只产出事实层简报,并在正文标注「配置后自动生成 AI 层」
- 无 `FEISHU_WEBHOOK` → 跳过推送,本地 md 即交付物
- 无数据 → 退出码 1,提示先跑数据平面

## 待办 / 后续

- [ ] 用真实 `ANTHROPIC_API_KEY` 跑出完整四层简报
- [ ] 配飞书机器人(webhook + 可选签名)跑通推送
- [ ] M2:假设追踪日志(记录昨天假设今天是否成立)
- [ ] 飞书 text → 富文本卡片(lark_md)
- [ ] 引入 SQLite 接缝替代直接读 CSV
