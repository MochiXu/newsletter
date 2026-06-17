"""把 data/briefs/<date>.json 重新聚合成 data/briefs.json(全量、按日期倒序、重算刊号)。

平时聚合文件由 brief.py 在每日流程里增量维护;此脚本用于一次性重建,或在手工修过
单日 JSON 后刷新聚合。纯标准库,无第三方依赖。

用法(仓库根目录):
    PYTHONPATH=py python3 -m newsletter.export_json
"""

from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
BRIEFS_DIR = REPO / "data" / "briefs"
BRIEFS_JSON = REPO / "data" / "briefs.json"


def rebuild(briefs_dir: Path, model: str = "offline") -> dict:
    """扫描 briefs_dir 下所有 <date>.json,聚合成展示平面契约 {model, generatedAt, briefs}。"""
    by_date: dict = {}
    for p in sorted(briefs_dir.glob("*.json")):
        try:
            b = json.loads(p.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            continue
        if isinstance(b, dict) and b.get("date"):
            by_date[b["date"]] = b
    dates_asc = sorted(by_date)
    for i, d in enumerate(dates_asc, 1):  # 刊号 = 年代序(最早=1)
        by_date[d]["issue"] = i
    briefs_desc = [by_date[d] for d in reversed(dates_asc)]
    return {
        "model": model,
        "generatedAt": dates_asc[-1] if dates_asc else "",
        "briefs": briefs_desc,
    }


def main() -> int:
    out = rebuild(BRIEFS_DIR)
    BRIEFS_JSON.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"重建 {BRIEFS_JSON.relative_to(REPO)}:{len(out['briefs'])} 天")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
