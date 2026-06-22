"""CLI 入口:生成每日宏观简报。

用法(仓库根):
    PYTHONPATH=py python -m newsletter                 # 今天
    PYTHONPATH=py python -m newsletter --date 2026-06-18
    PYTHONPATH=py python -m newsletter --no-news        # 不带新闻(如历史回填)
"""

from __future__ import annotations

import argparse
import logging
import sys

from .pipeline import run


def main() -> int:
    ap = argparse.ArgumentParser(prog="newsletter", description="生成每日宏观简报(四层 + 技术特征)")
    ap.add_argument("--date", default=None, help="目标日期 YYYY-MM-DD(默认今天)")
    ap.add_argument("--no-news", action="store_true", help="不抓新闻(历史回填用)")
    ap.add_argument("--history-years", type=int, default=12, help="拉取历史年数(默认 12,够算 MA200/z252)")
    ap.add_argument("-v", "--verbose", action="store_true", help="DEBUG 日志")
    args = ap.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )

    try:
        brief = run(
            target_date=args.date,
            history_years=args.history_years,
            news_mode="none" if args.no_news else "live",
        )
    except Exception as e:  # noqa: BLE001
        print(f"失败:{e}", file=sys.stderr)
        return 1

    pv = brief.views.get(brief.models[0]) if brief.models else None
    tone = pv.tone.value if pv else "neutral"
    headline = pv.headline if pv else ""
    print(f"完成:{brief.date} · 模型 {'+'.join(brief.models) or 'offline'} · tone={tone} · {headline[:60]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
