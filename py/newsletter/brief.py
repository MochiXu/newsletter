"""M1 智能平面入口:读数据 → 调 Claude 生成四层简报 → 渲染 → 存 md + 推飞书。

用法(仓库根目录):
    PYTHONPATH=py python3 -m newsletter.brief

环境变量:
- ANTHROPIC_API_KEY :生成 AI 解读/假设/影响层;缺失则仅产出事实层
- ANTHROPIC_MODEL   :可选,默认 claude-sonnet-4-6
- FEISHU_WEBHOOK    :可选,配了才推飞书(否则仅存本地 md)
- FEISHU_SECRET     :可选,飞书签名校验
"""

from __future__ import annotations

import sys
from pathlib import Path

from .data import load_latest
from .deliver.feishu import push_text
from .llm import generate_brief
from .render import data_table, render_markdown, render_text

# py/newsletter/brief.py -> 仓库根目录
REPO = Path(__file__).resolve().parents[2]
DATA_CSV = REPO / "data" / "observations.csv"
BRIEFS_DIR = REPO / "data" / "briefs"
LINKAGE = Path(__file__).resolve().parent / "framework" / "linkage_map.md"


def main() -> int:
    obs = load_latest(DATA_CSV)
    if not obs:
        print(f"无数据:{DATA_CSV} 为空或不存在,请先跑数据平面(cargo run)。", file=sys.stderr)
        return 1
    run_date = obs[0].run_date

    linkage = LINKAGE.read_text(encoding="utf-8") if LINKAGE.exists() else ""
    try:
        brief = generate_brief(data_table(obs, with_note=True), linkage)
    except Exception as e:  # 网络/鉴权/解析失败都退回事实层,不让简报整体失败
        print(f"⚠️ LLM 生成失败,退回事实层:{e}", file=sys.stderr)
        brief = None
    if brief is None:
        print("ℹ️ 未配置 ANTHROPIC_API_KEY(或 LLM 失败):仅产出事实层简报。", file=sys.stderr)

    # 始终先存本地 md(git-as-database;也是飞书不可用时的兜底)。
    md = render_markdown(run_date, obs, brief)
    BRIEFS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = BRIEFS_DIR / f"{run_date}.md"
    out_path.write_text(md, encoding="utf-8")
    print(f"简报已保存:{out_path.relative_to(REPO)}")

    # 再尝试推飞书(未配置 webhook 则跳过)。
    try:
        pushed = push_text(render_text(run_date, obs, brief))
        print("已推送飞书。" if pushed else "未配置 FEISHU_WEBHOOK,跳过推送(已存本地 md)。")
    except Exception as e:
        print(f"⚠️ 飞书推送失败(已存本地 md):{e}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
