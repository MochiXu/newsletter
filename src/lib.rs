//! newsletter 数据平面:抓取核心宏观数据,落地为 CSV + markdown 快照(git-as-database)。
//!
//! 分层(见 docs/data-plane.md):
//! - `error`  —— 统一错误类型(thiserror)
//! - `config` —— 运行配置(env)
//! - `model`  —— 数据 schema(Observation / Record)
//! - `catalog` —— 要抓取的序列定义(常量)
//! - `source` —— 信息源抽象(Source trait)+ FRED / Yahoo 实现 + 新鲜度校验
//! - `store`  —— 存储(CSV upsert + markdown 快照)
//! - 本文件   —— 编排(`run` + runner `collect_from`)

mod catalog;
mod config;
mod error;
mod model;
mod source;
mod store;

pub use config::Config;
pub use error::{Error, Failure, Result};

use chrono::Local;

use crate::catalog::SeriesSpec;
use crate::model::Record;
use crate::source::fred::FredSource;
use crate::source::yahoo::YahooSource;
use crate::source::{Source, staleness_days};

/// 一次运行的结果摘要(给 `main` 决定 CI 注解与退出码)。
pub struct RunReport {
    /// 成功落库的记录条数。
    pub ok: usize,
    /// 失败/陈旧的序列 id 列表。
    pub failures: Vec<String>,
}

/// 编排一次抓取:FRED 核心 → Yahoo 补充(必抓)→ FRED 全空时 Yahoo 降级顶上 → 落库。
pub fn run(cfg: &Config) -> Result<RunReport> {
    let run_date = Local::now().format("%Y-%m-%d").to_string();
    log::info!("data plane run starting (run_date={run_date})");

    let mut records: Vec<Record> = Vec::new();
    let mut failures: Vec<Failure> = Vec::new();

    // Phase 1:FRED 核心(需要 key;缺失是硬错误 MissingApiKey)。
    let api_key = cfg.fred_api_key.clone().ok_or(Error::MissingApiKey)?;
    let fred = FredSource::new(api_key)?;
    collect_from(&fred, catalog::FRED_CORE, cfg, &run_date, &mut records, &mut failures);
    let fred_count = records.len();
    if fred_count == 0 {
        // key 无效时 FRED 全失败——抑制这批噪声,改用下方 Yahoo 顶上核心指标。
        log::warn!("FRED returned no data (check FRED_API_KEY); falling back to Yahoo for core indicators");
        failures.clear();
    }

    // Phase 2:Yahoo 补充(FRED 给不了的真 DXY/黄金)每次都抓;FRED 全空时再抓降级集。
    let yahoo = YahooSource::new()?;
    collect_from(&yahoo, catalog::YAHOO_SUPPLEMENT, cfg, &run_date, &mut records, &mut failures);
    if fred_count == 0 {
        collect_from(&yahoo, catalog::YAHOO_DEGRADED, cfg, &run_date, &mut records, &mut failures);
    }

    // 落库:CSV 仅在非空时写;markdown 快照始终写(便于看到失败原因)。
    if !records.is_empty() {
        store::upsert_csv(&cfg.data_dir, &records)?;
    }
    store::write_markdown_snapshot(&cfg.data_dir, &run_date, &records, &failures)?;

    let report = RunReport {
        ok: records.len(),
        failures: failures.iter().map(|f| f.series_id.clone()).collect(),
    };
    log::info!(
        "done: {} ok / {} failed -> {}/observations.csv, {}/snapshots/{run_date}.md",
        report.ok,
        report.failures.len(),
        cfg.data_dir.display(),
        cfg.data_dir.display(),
    );

    // 全部失败 → 硬错误,非零退出,便于 CI 报警。
    if records.is_empty() {
        return Err(Error::Empty);
    }
    Ok(report)
}

/// runner:跑一个源、应用新鲜度校验、组装 Record、合并失败。新鲜度只在这里做一次,
/// 所有源都经此流过,故新增源即白拿该校验。
fn collect_from(
    src: &dyn Source,
    specs: &'static [SeriesSpec],
    cfg: &Config,
    run_date: &str,
    records: &mut Vec<Record>,
    failures: &mut Vec<Failure>,
) {
    let data = src.fetch(specs);
    for f in data.failures {
        log::warn!("{} [{}]: {}", f.series_id, src.name(), f.message);
        failures.push(f);
    }
    for (spec, obs) in data.ok {
        match staleness_days(run_date, &obs.date) {
            Some(age) if age > cfg.max_staleness_days => {
                let e = Error::Stale {
                    series: spec.id.to_string(),
                    obs_date: obs.date.clone(),
                    age,
                    threshold: cfg.max_staleness_days,
                };
                log::warn!("{} [{}]: {e}", spec.label, src.name());
                failures.push(Failure::new(spec.id, &e));
            }
            _ => {
                log::info!(
                    "fetched {} = {} {} ({}) [{}]",
                    spec.label,
                    obs.value,
                    spec.unit,
                    obs.date,
                    src.name(),
                );
                records.push(Record::new(src.name(), spec, obs, run_date));
            }
        }
    }
}
