//! 信息源抽象:FRED、Yahoo(及未来 CFTC / RSS / FedWatch / A股)都实现同一个 [`Source`]。
//!
//! 关键取舍——**批量粒度**:`fetch` 接收一组 spec、一次性返回该源能给出的全部观测,而非
//! 「一次一序列」。FRED 内部对每个 spec 各发一次请求;但 CFTC 是「一次 GET 返回多行」、
//! RSS 是「按 feed 抓取」,只有批量粒度才能容纳它们而不产生 N 次冗余请求——由源自己决定发几次请求。
//!
//! 同时,源只返回**原始观测 + 软失败**,不做新鲜度校验、不组装 `Record`:那些横切逻辑统一
//! 由 `lib::run` 的 runner(`collect_from`)负责,故新增一个源即可白拿新鲜度校验,且没有任何
//! 源去重复这段逻辑。

use crate::catalog::SeriesSpec;
use crate::error::Failure;
use crate::model::Observation;

pub mod fred;
pub mod yahoo;

/// 新鲜度阈值:日频序列若最新观测距 run_date 超过此天数,视为陈旧(疑似停更/长中断),
/// 计入失败而非静默当「今日最新」。14 天可容纳长假 + 发布滞后。
pub const MAX_STALENESS_DAYS: i64 = 14;

/// 一个信息源能提供的产出:成功的 (序列定义, 观测值) 对,以及软失败列表。
pub struct SourceData {
    pub ok: Vec<(&'static SeriesSpec, Observation)>,
    pub failures: Vec<Failure>,
}

impl SourceData {
    pub fn new() -> Self {
        SourceData { ok: Vec::new(), failures: Vec::new() }
    }
}

impl Default for SourceData {
    fn default() -> Self {
        Self::new()
    }
}

/// 一个信息源。新增数据源 = 新建一个文件 + 实现该 trait + 在 catalog 加一张 spec 表 +
/// 在 `run()` 的计划里加一行。trait、错误枚举、新鲜度校验、存储均不需改动。
///
/// 异步迁移友好(未来序列变多时):trait **签名**层面已就绪——`fetch` 只借用 `&self` 与
/// `specs`、返回 owned `SourceData`、无引用逃逸,故改成 `async fn` 无需反转签名,runner 的顺序
/// 调用可改 `join_all`。注意这只是签名层面:各源**实现体**仍需把 `reqwest::blocking` +
/// `std::thread::sleep` 换成 async reqwest + `tokio::time::sleep`、并在 `main` 起 runtime——
/// 不是纯机械改动。
pub trait Source {
    /// 稳定标识,写入 `Record.source`,如 "FRED"、"Yahoo"。
    fn name(&self) -> &'static str;

    /// 抓取给定 spec 的原始观测。成功的进 `ok`,单序列失败进 `failures`(软失败,不中断)。
    /// 不做新鲜度校验、不组装 Record——交给 runner。
    fn fetch(&self, specs: &'static [SeriesSpec]) -> SourceData;
}

/// 最新观测日距 run_date 的天数;任一日期无法解析时返回 None(跳过校验)。
pub fn staleness_days(run_date: &str, obs_date: &str) -> Option<i64> {
    let run = chrono::NaiveDate::parse_from_str(run_date, "%Y-%m-%d").ok()?;
    let obs = chrono::NaiveDate::parse_from_str(obs_date, "%Y-%m-%d").ok()?;
    Some((run - obs).num_days())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn staleness_basic() {
        assert_eq!(staleness_days("2026-06-16", "2026-06-15"), Some(1));
        assert_eq!(staleness_days("2026-06-16", "2026-06-16"), Some(0));
        assert_eq!(staleness_days("2026-06-16", "2026-05-01"), Some(46));
    }

    #[test]
    fn staleness_unparseable_is_none() {
        assert_eq!(staleness_days("bad", "2026-06-15"), None);
        assert_eq!(staleness_days("2026-06-16", "n/a"), None);
    }
}
