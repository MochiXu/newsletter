"""最小 .env 加载器(纯标准库)。

Rust 数据平面用 `dotenvy` 自动读 `.env`;Python 智能平面是纯 stdlib,没有等价机制,
于是 `.env` 里的 LLM key 对 Python 进程不可见(见 providers.select_provider)。本模块补上
这一步,行为与 dotenvy 对齐:**已存在于环境的变量不覆盖**(让 shell 能盖过文件)。

故意做得很小:只认 `KEY=VALUE`(可带 `export ` 前缀、可去成对引号),不解析行内注释
(API key 不含空格/`#`,避免误伤值)。
"""

from __future__ import annotations

import os
from pathlib import Path


def load_dotenv(path: Path) -> int:
    """把 `path` 里的变量加载进 os.environ(不覆盖已有)。返回新加载的条数。"""
    if not path.exists():
        return 0
    loaded = 0
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].lstrip()
        if "=" not in line:
            continue
        key, val = line.split("=", 1)
        key, val = key.strip(), val.strip()
        if len(val) >= 2 and val[0] == val[-1] and val[0] in ("'", '"'):
            val = val[1:-1]
        if key and key not in os.environ:
            os.environ[key] = val
            loaded += 1
    return loaded
