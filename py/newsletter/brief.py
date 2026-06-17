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

import json
import os
import sys
from pathlib import Path

from . import hypotheses as hyp
from . import news as news_mod
from .config import load_dotenv
from .data import load_all, load_latest
from .deliver.feishu import push_text
from .llm import generate_brief
from .providers import select_provider
from .render import data_table, render_json, render_markdown, render_text

# py/newsletter/brief.py -> 仓库根目录
REPO = Path(__file__).resolve().parents[2]
DATA_CSV = REPO / "data" / "observations.csv"
BRIEFS_DIR = REPO / "data" / "briefs"
BRIEFS_JSON = REPO / "data" / "briefs.json"
HYP_CSV = REPO / "data" / "hypotheses.csv"
LINKAGE = Path(__file__).resolve().parent / "framework" / "linkage_map.md"

# provider 内部名 -> 页脚展示名(小票签名 GEN <model>)。
_MODEL_DISPLAY = {
    "anthropic": "Claude",
    "openai": "OpenAI",
    "deepseek": "DeepSeek",
    "minimax": "MiniMax",
    "moonshot": "Moonshot",
    "zhipu": "Zhipu",
    "openai-compat": "LLM",
}


def _model_name() -> str:
    """当前活跃 provider 的展示名;无 provider 时记 offline。"""
    p = select_provider()
    if p is None:
        return "offline"
    return _MODEL_DISPLAY.get(getattr(p, "name", ""), getattr(p, "name", "LLM"))


def _write_json_outputs(run_date, obs, history, brief, news, hyp_rows, model) -> int:
    """写展示平面 JSON:单日 data/briefs/<date>.json + 增量维护聚合 data/briefs.json。

    聚合文件按日期 upsert(同日重跑覆盖),倒序排列,并按年代序重算 issue(最早=第 1 刊)。
    返回聚合后的天数。
    """
    today = render_json(run_date, obs, history, brief, news=news, hyp_rows=hyp_rows)

    by_date: dict = {}
    if BRIEFS_JSON.exists():
        try:
            data = json.loads(BRIEFS_JSON.read_text(encoding="utf-8"))
            for b in data.get("briefs", []):
                if isinstance(b, dict) and b.get("date"):
                    by_date[b["date"]] = b
        except (ValueError, OSError):
            by_date = {}
    by_date[run_date] = today

    dates_asc = sorted(by_date)
    for i, d in enumerate(dates_asc, 1):  # 刊号 = 年代序(最早=1),与日期对齐、可重算
        by_date[d]["issue"] = i
    briefs_desc = [by_date[d] for d in reversed(dates_asc)]
    out = {"model": model, "generatedAt": dates_asc[-1], "briefs": briefs_desc}

    BRIEFS_DIR.mkdir(parents=True, exist_ok=True)
    (BRIEFS_DIR / f"{run_date}.json").write_text(
        json.dumps(by_date[run_date], ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    BRIEFS_JSON.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return len(briefs_desc)


def _merge_news(items, classified):
    """把分类结果贴回原始新闻:优先按模型回填的 index(从 1 开始)对齐,标题作兜底。

    index 对齐对「LLM 把英文标题翻译/改写成中文」免疫(标题对齐会因此零匹配,全退化为未
    分类);且因 index 由模型显式回填、非位置推断,漏条/乱序也不会张冠李戴。两者都对不上的
    条目保持未分类。
    """
    by_index, by_title = {}, {}
    for c in classified or []:
        if not isinstance(c, dict):
            continue
        try:
            idx = int(c.get("index"))
        except (TypeError, ValueError):
            idx = None
        if idx is not None and 1 <= idx <= len(items):
            by_index.setdefault(idx, c)
        t = (c.get("title") or "").strip().lower()
        if t:
            by_title.setdefault(t, c)
    out = []
    for i, it in enumerate(items):
        d = {"source": it.source, "title": it.title, "link": it.link}
        c = by_index.get(i + 1) or by_title.get(it.title.strip().lower())
        if c:
            d["category"] = c.get("category")
            d["summary"] = c.get("summary")
            d["affected_assets"] = c.get("affected_assets")
            d["note"] = c.get("note")
        out.append(d)
    return out


def main() -> int:
    # 先加载 .env(Python 侧不像 Rust 有 dotenvy),让 .env 里的 LLM/飞书 key 对本进程可见。
    load_dotenv(REPO / ".env")

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
        # 只复盘「往日」的 open 假设(DESIGN:次日起复盘)——今日刚生成的假设不拿今天的
        # 数据自我验证(循环论证);也让同日重跑不会把当天假设提前判定。
        open_hyps = [h for h in hyp.open_items(hyp_rows) if h.get("created_date") != run_date]
        reviews = hyp.review(open_hyps, data_block)
        hyp.apply_reviews(open_hyps, reviews, run_date)
        if reviews:
            print(f"✓ 复盘了 {len(reviews)} 条历史假设。")
        if brief and brief.get("hypotheses"):
            hyp.record_new(hyp_rows, run_date, brief["hypotheses"])
        hyp.save(HYP_CSV, hyp_rows)
    except Exception as e:
        print(f"⚠️ 假设追踪失败,跳过:{e}", file=sys.stderr)

    # 3) 新闻抓取 + 分类
    news_items, classified = [], None
    if not os.environ.get("NEWS_DISABLED"):
        try:
            news_items = news_mod.fetch_news()
            classified = news_mod.classify(news_items)
            if classified is None:
                tag = "(未分类:无 LLM provider)"
            elif not classified:
                tag = "(LLM 未给出分类)"
            else:
                tag = "(已分类)"
            print(f"✓ 抓取 {len(news_items)} 条新闻{tag}")
        except Exception as e:
            print(f"⚠️ 新闻抓取/分类失败,跳过:{e}", file=sys.stderr)
    news = _merge_news(news_items, classified)

    # 4) 渲染 + 存本地 md(git-as-database)+ 推飞书
    md = render_markdown(run_date, obs, brief, news=news, hyp_rows=hyp_rows)
    BRIEFS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = BRIEFS_DIR / f"{run_date}.md"
    out_path.write_text(md, encoding="utf-8")
    print(f"简报已保存:{out_path.relative_to(REPO)}")

    # 5) 导出展示平面 JSON(供前端小票阅读器消费;失败不影响简报本体)
    try:
        history = load_all(DATA_CSV)
        days = _write_json_outputs(run_date, obs, history, brief, news, hyp_rows, _model_name())
        print(f"已导出 data/briefs.json(共 {days} 天)。")
    except Exception as e:
        print(f"⚠️ 导出 briefs.json 失败(已存简报):{e}", file=sys.stderr)

    try:
        pushed = push_text(render_text(run_date, obs, brief, news=news, hyp_rows=hyp_rows))
        print("已推送飞书。" if pushed else "未配置 FEISHU_WEBHOOK,跳过推送(已存本地 md)。")
    except Exception as e:
        print(f"⚠️ 飞书推送失败(已存本地 md):{e}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
