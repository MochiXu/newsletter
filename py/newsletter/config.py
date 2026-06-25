"""集中配置:密钥、路径、特征窗口。

设计:
- 密钥从 `.env` 读(`load_dotenv` 先注入 `os.environ`,再由 `Settings` 类型化读取)。
  保留 `load_dotenv` 是因为多模型 provider 层(`llm.providers`)按存在的 key 动态探测,
  仍直接读 `os.environ`;两条路径共用同一份 `.env`。
- 路径集中在 `Paths`,从仓库根推导;特征窗口集中在 `WINDOWS`,便于统一调参。

密钥仅存 `.env`(已 gitignore),绝不入库/打印。
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, ConfigDict

# py/newsletter/config.py -> 仓库根
REPO_ROOT = Path(__file__).resolve().parents[2]


def load_dotenv(path: Path | None = None) -> int:
    """把 `.env` 里的 `KEY=VALUE` 注入 `os.environ`(不覆盖已存在的,让 shell 能盖过文件)。

    故意做得很小:认 `KEY=VALUE`(可带 `export ` 前缀、去成对引号),不解析行内注释
    (key 不含空格/`#`)。返回新加载的条数。
    """
    path = path or (REPO_ROOT / ".env")
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
        key, val = (s.strip() for s in line.split("=", 1))
        if len(val) >= 2 and val[0] == val[-1] and val[0] in ("'", '"'):
            val = val[1:-1]
        if key and key not in os.environ:
            os.environ[key] = val
            loaded += 1
    return loaded


@dataclass(frozen=True)
class Paths:
    """仓库内所有数据路径(从仓库根推导)。"""

    root: Path

    @property
    def data(self) -> Path:
        return self.root / "data"

    @property
    def raw_latest(self) -> Path:
        """当前全量快照(全历史),每日重拉覆盖。tracked。"""
        return self.data / "raw" / "latest"

    @property
    def raw_history(self) -> Path:
        """每日归档的全量快照(point-in-time 档案)。gitignored。"""
        return self.data / "raw" / "history"

    @property
    def features(self) -> Path:
        """报告当天的特征快照(排错/审计用)。gitignored。"""
        return self.data / "features"

    @property
    def briefs(self) -> Path:
        return self.data / "briefs"

    @property
    def briefs_json(self) -> Path:
        return self.data / "briefs.json"

    @property
    def predictions_csv(self) -> Path:
        return self.data / "predictions.csv"

    @property
    def scorecard_json(self) -> Path:
        """评估层产出:技能 vs 基线 + 校准 + Brier(前向)。前端命中率页未来读。"""
        return self.data / "scorecard.json"

    @property
    def scorecard_md(self) -> Path:
        return self.data / "scorecard.md"

    @property
    def news_cache(self) -> Path:
        return self.data / "news_cache"

    @property
    def news(self) -> Path:
        """新闻语料库:article-level parquet(按月分区)。v1.8。"""
        return self.data / "news"

    @property
    def linkage_map(self) -> Path:
        return Path(__file__).resolve().parent / "framework" / "linkage_map.md"


PATHS = Paths(REPO_ROOT)


@dataclass(frozen=True)
class FeatureWindows:
    """技术特征的滚动窗口(交易日)。集中在此便于统一调参。"""

    returns: tuple[int, ...] = (5, 20, 60, 120)
    changes: tuple[int, ...] = (5, 20, 60)  # 利率类:bp 变化量
    ma: tuple[int, ...] = (20, 60, 120, 200)
    vol: tuple[int, ...] = (20, 60)
    drawdown: tuple[int, ...] = (60, 252)
    zscore: int = 252
    corr: int = 60
    range_pct: int = 252  # 52 周区间百分位


WINDOWS = FeatureWindows()


class Settings(BaseModel):
    """运行期配置:活跃使用的密钥与开关(类型化)。

    多模型 provider 的其余可选 key(ANTHROPIC/OPENAI/...)由 `llm.providers` 直接从
    `os.environ` 探测,不在此重复声明。
    """

    model_config = ConfigDict(frozen=True)

    fred_api_key: str | None = None
    twelvedata_api_key: str | None = None
    tiingo_api_token: str | None = None
    feishu_webhook: str | None = None
    feishu_secret: str | None = None
    news_disabled: bool = False

    @classmethod
    def load(cls, dotenv: bool = True) -> "Settings":
        """加载配置:先把 `.env` 注入 `os.environ`,再读取。"""
        if dotenv:
            load_dotenv()
        return cls(
            fred_api_key=os.environ.get("FRED_API_KEY") or None,
            twelvedata_api_key=os.environ.get("TWELVEDATA_API_KEY") or None,
            tiingo_api_token=os.environ.get("TIINGO_API_TOKEN") or None,
            feishu_webhook=os.environ.get("FEISHU_WEBHOOK") or None,
            feishu_secret=os.environ.get("FEISHU_SECRET") or None,
            news_disabled=bool(os.environ.get("NEWS_DISABLED")),
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """进程级单例(首次调用时加载 `.env`)。"""
    return Settings.load()
