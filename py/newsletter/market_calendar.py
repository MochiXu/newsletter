"""美股(NYSE)交易日历:周末 + 法定节假日判定。

- 周末:用 `weekday()` 算(确定性,无需维护)。
- 节假日:维护 NYSE 全天休市日表,**每年核对更新**(含因周末顺延的 observed 日)。
  来源:https://www.nyse.com/markets/hours-calendars
- **数据缺失不在此判定** —— "交易日但无观测"(no_data)由 pipeline 结合数据帧判定,本模块只看日历。
- 半日市(感恩节次日 / 平安夜等)当前仍按交易日处理(数据存在);未来要细分再加。
"""

from __future__ import annotations

import datetime

# NYSE 全天休市日(ISO YYYY-MM-DD)。**每年更新**:新增下一年、核对 observed 顺延日。
NYSE_HOLIDAYS: frozenset[str] = frozenset({
    # 2025
    "2025-01-01", "2025-01-20", "2025-02-17", "2025-04-18", "2025-05-26",
    "2025-06-19", "2025-07-04", "2025-09-01", "2025-11-27", "2025-12-25",
    # 2026
    "2026-01-01", "2026-01-19", "2026-02-16", "2026-04-03", "2026-05-25",
    "2026-06-19", "2026-07-03", "2026-09-07", "2026-11-26", "2026-12-25",
    # 2027
    "2027-01-01", "2027-01-18", "2027-02-15", "2027-03-26", "2027-05-31",
    "2027-06-18", "2027-07-05", "2027-09-06", "2027-11-25", "2027-12-24",
})


def _date(date_str: str) -> datetime.date:
    y, m, d = (int(x) for x in date_str.split("-"))
    return datetime.date(y, m, d)


def is_weekend(date_str: str) -> bool:
    return _date(date_str).weekday() >= 5


def is_holiday(date_str: str) -> bool:
    return date_str in NYSE_HOLIDAYS


def nontrading_reason(date_str: str) -> str | None:
    """非交易日原因:'weekend' / 'holiday';否则(工作日且非节假日)→ None。

    注意:返回 None **不保证有数据** —— 可能是 no_data(交易日但数据缺失/未发布),
    需 pipeline 结合数据帧再判。
    """
    if is_weekend(date_str):
        return "weekend"
    if is_holiday(date_str):
        return "holiday"
    return None


def iter_days(start: str, end: str) -> list[str]:
    """[start, end] 闭区间内**每个日历日**的 ISO 字符串(升序)。end < start 返回空。"""
    s, e = _date(start), _date(end)
    if e < s:
        return []
    out: list[str] = []
    cur = s
    while cur <= e:
        out.append(cur.isoformat())
        cur += datetime.timedelta(days=1)
    return out
