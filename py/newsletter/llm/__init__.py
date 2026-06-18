"""LLM 层:多模型 provider + 四层 schema + 特征化 prompt。

强制分层:数字由代码(features/regime)算好,LLM 只解释。
"""

from .providers import select_provider
from .schema import BRIEF_SCHEMA, BRIEF_TOOL, SYSTEM
from .service import generate_brief

__all__ = ["select_provider", "generate_brief", "BRIEF_SCHEMA", "BRIEF_TOOL", "SYSTEM"]
