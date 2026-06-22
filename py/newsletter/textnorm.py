"""确定性中英文排版规范化(纯函数,落库前对所有展示文本统一过一遍)。

规则(与 llm/style.TEXT_STYLE 对齐,但这里是确定性兜底,不依赖 LLM 是否遵守):
1. 全角标点 → 英文半角;全角 +−%= → 半角;各类引号 → 英文单引号(双引号会破坏 JSON)。
2. 盘古之白:中日韩字符 ↔ 半角字母/数字(含前导正负号)边界补一个空格;
   绝不拆开 9bp / 0.27% / 2s10s / MA200 这类本身是字母数字的词。
3. 句读标点 . , ; : ! ? 后补空格;但数字内分隔符 `\\d[.,]\\d`(小数点/千分位)不动。
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
# 句读标点补空格:数字内的 . , (\d[.,]\d) 保留;其余 . , ; : ! ? 后补空格
_PUNCT_SPACE = re.compile(r"(?<=\d)([.,])(?=\d)|([.,;:!?])(?=\S)")


def _punct_space(m: re.Match) -> str:
    if m.group(1) is not None:  # 数字内分隔符:原样
        return m.group(1)
    return m.group(2) + " "  # 句读标点:补空格


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
