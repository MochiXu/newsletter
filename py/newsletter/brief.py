"""M1/M2 智能平面入口:读数据 → 四层简报 + 假设复盘 + 新闻分类 → 存 md + 推飞书。

用法(仓库根目录):
    PYTHONPATH=py python3 -m newsletter.brief

环境变量:
- LLM provider(任一即可,见 providers.py / .env.example):
    ANTHROPIC_API_KEY / OPENAI_API_KEY / MINIMAX_API_KEY / ...;
    LLM_PROVIDER 显式选择,缺省按存在的 key 自动探测。都没有则仅产出事实层 + 原始新闻。
- FEISHU_WEBHOOK / FEISHU_SECRET :可选,配了才推飞书(否则仅存本地 md)
- NEWS_DISABLED :设为非空则跳过新闻抓取(离线/调试用)
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from . import hypotheses as hyp
from . import news as news_mod
from .data import load_latest
from .deliver.feishu import push_text
from .llm import generate_brief
from .render import data_table, render_markdown, render_text

# py/newsletter/brief.py -> 仓库根目录
REPO = Path(__file__).resolve().parents[2]
DATA_CSV = REPO / "data" / "observations.csv"
BRIEFS_DIR = REPO / "data" / "briefs"
HYP_CSV = REPO / "data" / "hypotheses.csv"
LINKAGE = Path(__file__).resolve().parent / "framework" / "linkage_map.md"


def _merge_news(items, classified):
    """把原始新闻条目与(可能的)分类结果按顺序合并成渲染用 dict 列表。"""
    out = []
    for i, it in enumerate(items):
        d = {"source": it.source, "title": it.title, "link": it.link}
        if classified and i < len(classified):
            c = classified[i]
            d["category"] = c.get("category")
            d["summary"] = c.get("summary")
            d["affected_assets"] = c.get("affected_assets")
            d["note"] = c.get("note")
        out.append(d)
    return out


def main() -> int:
    obs = load_latest(DATA_CSV)
    if not obs:
        print(f"无数据:{DATA_CSV} 为空或不存在,请先跑数据平面(cargo run)。", file=sys.stderr)
        return 1
    run_date = obs[0].run_date
    data_block = data_table(obs, with_note=True)
    linkage = LINKAGE.read_text(encoding="utf-8") if LINKAGE.exists() else ""

    # 1) 四层简报
    try:
        brief = generate_brief(data_block, linkage)
    except Exception as e:
        print(f"⚠️ LLM 生成失败,退回事实层:{e}", file=sys.stderr)
        brief = None
    if brief is None:
        print("ℹ️ 未配置任何 LLM provider(或调用失败):仅产出事实层简报。", file=sys.stderr)

    # 2) 假设追踪:先复盘历史 open 假设,再登记今天的新假设
    hyp_rows = hyp.load(HYP_CSV)
    try:
        open_hyps = hyp.open_items(hyp_rows)
        reviews = hyp.review(open_hyps, data_block)
        hyp.apply_reviews(open_hyps, reviews, run_date)
        if reviews:
            print(f"✓ 复盘了 {len(reviews)} 条历史假设。")
    except Exception as e:
        print(f"⚠️ 假设复盘失败,跳过:{e}", file=sys.stderr)
    if brief and brief.get("hypotheses"):
        hyp.record_new(hyp_rows, run_date, brief["hypotheses"])
    hyp.save(HYP_CSV, hyp_rows)

    # 3) 新闻抓取 + 分类
    news_items, classified = [], None
    if not os.environ.get("NEWS_DISABLED"):
        try:
            news_items = news_mod.fetch_news()
            classified = news_mod.classify(news_items)
            print(f"✓ 抓取 {len(news_items)} 条新闻" + ("(已分类)" if classified else "(未分类:无 LLM)"))
        except Exception as e:
            print(f"⚠️ 新闻抓取/分类失败,跳过:{e}", file=sys.stderr)
    news = _merge_news(news_items, classified)

    # 4) 渲染 + 存本地 md(git-as-database)+ 推飞书
    md = render_markdown(run_date, obs, brief, news=news, hyp_rows=hyp_rows)
    BRIEFS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = BRIEFS_DIR / f"{run_date}.md"
    out_path.write_text(md, encoding="utf-8")
    print(f"简报已保存:{out_path.relative_to(REPO)}")

    try:
        pushed = push_text(render_text(run_date, obs, brief, news=news, hyp_rows=hyp_rows))
        print("已推送飞书。" if pushed else "未配置 FEISHU_WEBHOOK,跳过推送(已存本地 md)。")
    except Exception as e:
        print(f"⚠️ 飞书推送失败(已存本地 md):{e}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
