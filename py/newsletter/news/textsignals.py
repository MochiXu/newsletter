"""新闻文本信号(v1.8 P3)—— **代码算**的可复现特征(不靠 LLM,免主观/免成本)。

业内/学术 grounded(见 v1.8 §5 / §11):
- **EPU**(Baker-Bloom-Davis Economic Policy Uncertainty):文中同时含 经济 ∧ 政策 ∧ 不确定 三类词 → 政策不确定。
- **GPR**(Caldara-Iacoviello Geopolitical Risk):地缘风险词计数。
- **鹰鸽语调**(Fedspeak):鹰派词 vs 鸽派词的净倾向。
- **事件分类**:货币/财政/地缘/能源/通胀/就业/贸易 关键词标记。

全部基于英文正文/标题的小写匹配;返回 0~1 密度或 -1..1 倾向。纯函数,易离线测。
"""

from __future__ import annotations

import re

# ── 词表(小写;\b 词界)。可随效果增删,稳定后再细化为加权词典。──────────────
_ECON = re.compile(r"\b(econom\w*|gdp|growth|recession|inflation|unemploy\w*|market\w*)\b", re.I)
_POLICY = re.compile(r"\b(fed|federal reserve|policy|regulat\w*|congress|white house|tariff|fiscal|legislat\w*|central bank|treasury)\b", re.I)
_UNCERT = re.compile(r"\b(uncertain\w*|risk\w*|unclear|unpredictab\w*|volatil\w*|ambigu\w*|doubt\w*)\b", re.I)

_GPR = re.compile(
    r"\b(war|warfare|conflict|military|geopolit\w*|sanction\w*|tension\w*|attack\w*|invasion|missile|"
    r"terror\w*|coup|nuclear|troops|ceasefire|opec|embargo)\b", re.I,
)

_HAWK = re.compile(r"\b(hike|hikes|hiking|raise rates|tighten\w*|restrictive|hawkish|higher for longer|rate increase|combat inflation)\b", re.I)
_DOVE = re.compile(r"\b(rate cut|cuts|cutting|ease|easing|dovish|accommodat\w*|stimulus|pause|lower rates|rate reduction)\b", re.I)

# 事件分类(键 = 事件类型;值 = 正则)。扩展自旧 _EVENT_PATTERNS。
EVENT_PATTERNS: dict[str, re.Pattern] = {
    "monetary": re.compile(r"\bfomc\b|federal reserve|fed (meeting|decision|rate|chair)|powell|rate decision|dot plot|interest rate", re.I),
    "fiscal": re.compile(r"\b(fiscal|budget|deficit|debt ceiling|treasury|spending bill|stimulus|tax)\b", re.I),
    "inflation": re.compile(r"\bcpi\b|inflation (data|report|print)|consumer price|\bpce\b|core inflation", re.I),
    "jobs": re.compile(r"nonfarm|non-farm|payroll|jobs report|unemployment|jobless|labou?r market", re.I),
    "geopolitical": _GPR,
    "energy": re.compile(r"\b(oil|crude|brent|wti|opec|natural gas|energy price\w*|gasoline)\b", re.I),
    "trade": re.compile(r"\b(tariff\w*|trade war|trade deal|export\w*|import\w*|sanction\w*)\b", re.I),
}

_WORD = re.compile(r"\b\w+\b")


def _count(pat: re.Pattern, text: str) -> int:
    return len(pat.findall(text or ""))


def _density(pat: re.Pattern, text: str, words: int) -> float:
    """每千词命中数(密度,长度无关)。"""
    return (_count(pat, text) / words * 1000.0) if words else 0.0


def word_count(text: str) -> int:
    return len(_WORD.findall(text or ""))


def epu_score(text: str) -> float:
    """EPU 标志:含 经济 ∧ 政策 ∧ 不确定 三类词 → 1.0,否则 0.0(文章级)。"""
    return 1.0 if (_ECON.search(text or "") and _POLICY.search(text or "") and _UNCERT.search(text or "")) else 0.0


def uncertainty_density(text: str) -> float:
    """不确定性词密度(每千词)—— 比 EPU 标志更连续。"""
    return _density(_UNCERT, text, word_count(text))


def gpr_density(text: str) -> float:
    """地缘风险词密度(每千词)。"""
    return _density(_GPR, text, word_count(text))


def hawkish_dovish(text: str) -> float | None:
    """鹰鸽净倾向 = (鹰 − 鸽) / (鹰 + 鸽) ∈ [-1, 1];都没命中 → None(无信号)。"""
    h, d = _count(_HAWK, text), _count(_DOVE, text)
    return (h - d) / (h + d) if (h + d) else None


def event_types(text: str) -> list[str]:
    """命中的事件类型列表(去重、稳定序)。"""
    t = text or ""
    return [k for k, pat in EVENT_PATTERNS.items() if pat.search(t)]
