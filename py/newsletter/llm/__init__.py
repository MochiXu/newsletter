"""LLM 层:多模型 provider + 四层 schema + 特征化 prompt。

强制分层:数字由代码(features/regime)算好,LLM 只解释。
"""

from .providers import select_provider, select_providers
from .schema import BRIEF_SCHEMA, BRIEF_TOOL, SYSTEM
from .service import generate_brief, generate_briefs

__all__ = [
    "select_provider",
    "select_providers",
    "generate_brief",
    "generate_briefs",
    "BRIEF_SCHEMA",
    "BRIEF_TOOL",
    "SYSTEM",
]
