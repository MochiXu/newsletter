"""CLI 入口:生成每日宏观简报。

用法(仓库根):
    PYTHONPATH=py python -m newsletter                       # 今天(live:最新新闻 + RSS)
    PYTHONPATH=py python -m newsletter --date 2026-06-18      # 历史单日:新闻自动走 backfill 时间窗(防先知)
    PYTHONPATH=py python -m newsletter --start 2026-06-01     # 区间重生成:06-01 → 最新有数据日
    PYTHONPATH=py python -m newsletter --start 2026-06-01 --end 2026-06-20  # 指定区间
    PYTHONPATH=py python -m newsletter --no-news             # 完全不带新闻(任意模式)

非交易日(周末/节假日)与无数据日也会产出一份**空 brief**(session=closed/no_data),
供前端展示休市/数据未就绪界面。
"""

from __future__ import annotations

import argparse
import logging
import sys

from .pipeline import run, run_range


def main() -> int:
    ap = argparse.ArgumentParser(prog="newsletter", description="生成宏观简报(四层 + 技术特征)")
    ap.add_argument("--date", default=None, help="目标日期 YYYY-MM-DD(默认今天;单日模式)")
    ap.add_argument("--start", default=None, help="区间起始 YYYY-MM-DD(给定即进入区间重生成模式)")
    ap.add_argument("--end", default=None, help="区间结束 YYYY-MM-DD(默认=最新有数据日;仅区间模式)")
    ap.add_argument("--no-news", action="store_true", help="不抓新闻(历史回填用)")
    ap.add_argument("--history-years", type=int, default=12, help="拉取历史年数(默认 12,够算 MA200/z252)")
    ap.add_argument("-v", "--verbose", action="store_true", help="DEBUG 日志")
    args = ap.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    news_mode = "none" if args.no_news else "live"

    try:
        if args.start:  # 区间重生成模式
            counts = run_range(
                args.start, args.end, history_years=args.history_years, news_mode=news_mode
            )
            print(
                f"区间完成:{counts['days']} 天 · 交易 {counts['trading']} · "
                f"休市 {counts['closed']} · 无数据 {counts['no_data']}"
            )
            return 0
        brief = run(target_date=args.date, history_years=args.history_years, news_mode=news_mode)
    except Exception as e:  # noqa: BLE001
        print(f"失败:{e}", file=sys.stderr)
        return 1

    if brief.session != "trading":  # 单日落在休市/无数据
        print(f"完成:{brief.date} · {brief.weekday} · {brief.session}"
              + (f"/{brief.closed_reason}" if brief.closed_reason else ""))
        return 0
    pv = brief.views.get(brief.models[0]) if brief.models else None
    tone = pv.tone.value if pv else "neutral"
    headline = pv.headline if pv else ""
    print(f"完成:{brief.date} · 模型 {'+'.join(brief.models) or 'offline'} · tone={tone} · {headline[:60]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
