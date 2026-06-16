//! 运行配置:一次性从环境变量读出,集中校验,避免散落在各处的 `env::var`。

use std::path::PathBuf;

use crate::source::MAX_STALENESS_DAYS;

/// 数据平面一次运行的配置。
pub struct Config {
    /// FRED API key。**环境变量缺失**(未 set)→ None → `run()` 报 `MissingApiKey`(硬错误)。
    /// 注:**set 了但为空串**(如 CI secret 未配置)不在此被过滤掉——故意与旧版一致:空/无效 key
    /// 会让 FRED 全部失败、进而触发「Yahoo 降级」路径照常产出数据,而非硬中断(见 `lib::run`)。
    pub fred_api_key: Option<String>,
    /// 数据落地目录(CSV + markdown 快照)。
    pub data_dir: PathBuf,
    /// 新鲜度阈值:最新观测距今超过该天数则视为陈旧、计入失败。
    pub max_staleness_days: i64,
    /// 是否运行在 GitHub Actions(决定是否输出 `::warning::` 注解)。
    pub github_actions: bool,
}

impl Config {
    /// 从环境变量构造(均有合理默认值)。
    pub fn from_env() -> Config {
        Config {
            // 只区分「未 set」(None → 硬错误)与「set」(Some,含空串 → 走 FRED→Yahoo 降级);
            // 不过滤空串,以保持旧版「空/无效 key 降级到 Yahoo」的行为。
            fred_api_key: std::env::var("FRED_API_KEY").ok(),
            data_dir: PathBuf::from("data"),
            max_staleness_days: MAX_STALENESS_DAYS,
            github_actions: std::env::var("GITHUB_ACTIONS").is_ok(),
        }
    }
}
