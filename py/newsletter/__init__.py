"""newsletter:AI 宏观投研助手(智能平面,纯 Python)。

数据管线(强制分层,代码算特征 → LLM 只解释):
    catalog/sources → store(parquet) → features/regime → llm → render → pipeline

入口:`python -m newsletter`(见 __main__)。
"""

__version__ = "2.0.0"
