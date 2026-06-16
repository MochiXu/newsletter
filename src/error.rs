//! 数据平面的统一错误类型(`thiserror`,取代 anyhow)。
//!
//! 设计:**单一 `Error` 枚举**,软/硬之分由「在哪里出现」决定,而非另立类型——
//! - 软错误(单序列失败):在 source 内部构造、立刻渲染进 [`Failure`],run 继续,不向上冒泡;
//! - 硬错误(缺配置 / 全部失败 / IO):经 `?` 从 `run()` 冒出,导致非零退出。
//!
//! 安全不变量:这里**故意不**为 `reqwest::Error` 实现 `#[from]`。`Error::Http` 的唯一
//! 构造方式是 `Error::Http { source: e.without_url(), .. }`,因此 `?` 无法把仍含 api_key
//! URL 的原始 reqwest 错误偷渡进来——保证 api_key 不进日志 / 提交回仓库的快照 / CI 日志。

use thiserror::Error;

/// 数据平面的统一结果类型。
pub type Result<T> = std::result::Result<T, Error>;

#[derive(Debug, Error)]
pub enum Error {
    // ── 硬错误:中断本次运行,非零退出 ──────────────────────────────
    #[error(
        "missing FRED_API_KEY: set it in .env or export it \
         (https://fred.stlouisfed.org/docs/api/api_key.html)"
    )]
    MissingApiKey,

    #[error("failed to build HTTP client: {0}")]
    HttpClient(#[source] reqwest::Error),

    #[error("storage error at {path}: {source}")]
    Storage {
        path: String,
        #[source]
        source: std::io::Error,
    },

    #[error("all sources failed; nothing fetched — check FRED_API_KEY and network")]
    Empty,

    // ── 软错误:单序列级别;在 source 内构造、渲染进 Failure.message,不向上冒泡 ──
    // 注:source 字段一律先经 .without_url() 再构造(见上方安全不变量)。
    #[error("HTTP request failed for {series}: {source}")]
    Http {
        series: String,
        #[source]
        source: reqwest::Error,
    },

    #[error("HTTP {status} for {series}: {body}")]
    HttpStatus {
        status: u16,
        series: String,
        body: String,
    },

    #[error("failed to parse {source_name} response for {series}: {detail}")]
    Parse {
        source_name: &'static str,
        series: String,
        detail: String,
    },

    #[error("no valid observation for {series}")]
    NoObservation { series: String },

    #[error("retries exhausted for {series}: {last}")]
    RetriesExhausted { series: String, last: String },

    #[error("stale data for {series}: latest obs {obs_date} is {age} days old (threshold {threshold})")]
    Stale {
        series: String,
        obs_date: String,
        age: i64,
        threshold: i64,
    },
}

/// 一条单序列失败记录(替代旧的 `(String, String)` 元组)。
///
/// 喂给 markdown 快照的「抓取失败」小节,以及 GitHub Actions 的 `::warning::` 注解。
#[derive(Debug, Clone)]
pub struct Failure {
    pub series_id: String,
    pub message: String,
}

impl Failure {
    /// 从一个序列 id 与任意错误构造(错误经 Display 渲染为英文消息)。
    pub fn new(series_id: impl Into<String>, err: &Error) -> Self {
        Self {
            series_id: series_id.into(),
            message: err.to_string(),
        }
    }
}
