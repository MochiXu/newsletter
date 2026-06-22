"""确定性中英文排版规范化(纯函数,落库前对所有展示文本统一过一遍)。

规则(与 llm/style.TEXT_STYLE 对齐,但这里是确定性兜底,不依赖 LLM 是否遵守):
1. 全角标点 → 英文半角;全角 +−%= → 半角;各类引号 → 英文单引号(双引号会破坏 JSON)。
2. 盘古之白:中日韩字符 ↔ 半角字母/数字(含前导正负号)边界补一个空格;
   绝不拆开 9bp / 0.27% / 2s10s / MA200 这类本身是字母数字的词。
3. 句读标点 . , ; : ! ? 后补空格;但小数点 `\\d.\\d` 与千分位 `\\d,\\d{3}`(逗号后恰好 3 位数字组)不动
   ——故子句逗号 `119.51,20 日` 会补成 `119.51, 20 日`,真千分位 `7,500` 保留。
"""

from __future__ import annotations

import re

# 全角标点 / 全角运算符 / 各类引号 → ASCII(双引号统一收敛成单引号)
_PUNCT = str.maketrans(
    {
        "。": ".", "，": ",", "；": ";", "：": ":", "！": "!", "？": "?",
        "（": "(", "）": ")", "、": ",", "％": "%", "＋": "+", "－": "-", "−": "-", "＝": "=",
        "“": "'", "”": "'", "‘": "'", "’": "'", "「": "'", "」": "'", "『": "'", "』": "'", '"': "'",
    }
)

_CJK = r"一-鿿㐀-䶿"
# CJK 后紧跟(可带前导正负号的)字母/数字 → 加空格
_CJK_ALNUM = re.compile(rf"([{_CJK}])([+\-][0-9A-Za-z]|[0-9A-Za-z])")
# 字母/数字/%/) 后紧跟 CJK → 加空格
_ALNUM_CJK = re.compile(rf"([0-9A-Za-z%)\]])([{_CJK}])")
# 句读标点补空格,但保留数字内分隔符:
#   - 小数点 \d.\d 一律保留;
#   - 千分位逗号仅当「逗号后恰好跟一个 3 位数字组」时保留(7,500 保留;119.51,20 日 的逗号当子句分隔补空格)。
# 其余 . , ; : ! ? 后补一个空格。
_PUNCT_SPACE = re.compile(
    r"(?P<dec>(?<=\d)\.(?=\d))"
    r"|(?P<ksep>(?<=\d),(?=\d{3}(?!\d)))"
    r"|(?P<punct>[.,;:!?])(?=\S)"
)


def _punct_space(m: re.Match) -> str:
    if m.group("punct") is not None:  # 句读标点:补空格
        return m.group("punct") + " "
    return m.group(0)  # 小数点 / 千分位:原样保留


def normalize_text(s: str) -> str:
    """规范化一段展示文本。空/非字符串安全返回。幂等。"""
    if not s or not isinstance(s, str):
        return s or ""
    s = s.translate(_PUNCT)
    s = _CJK_ALNUM.sub(r"\1 \2", s)
    s = _ALNUM_CJK.sub(r"\1 \2", s)
    s = _PUNCT_SPACE.sub(_punct_space, s)
    s = re.sub(r"[ \t]{2,}", " ", s)
    return s.strip()
