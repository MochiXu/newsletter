"""生成四层简报:provider + schema + 特征化 prompt → 经 pydantic 校验的 LLMBrief。

无任何已配置 provider 时返回 None,调用方走「仅事实层 + 特征」降级。
"""

from __future__ import annotations

from ..models import LLMBrief
from .prompt import build_user
from .providers import select_provider
from .schema import BRIEF_SCHEMA, BRIEF_TOOL, SYSTEM


def generate_brief(feature_block: str, linkage_map: str) -> LLMBrief | None:
    """据特征块 + 传导图生成四层简报;未配置 provider 返回 None。"""
    provider = select_provider()
    if provider is None:
        return None
    user = build_user(feature_block, linkage_map)
    raw = provider.call_structured(SYSTEM, user, BRIEF_TOOL, "输出四层结构的每日宏观简报", BRIEF_SCHEMA)
    return LLMBrief.model_validate(raw)
