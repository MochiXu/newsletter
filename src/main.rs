//! M0 数据平面入口:从 FRED 抓取核心宏观数据,落地为 CSV + markdown 快照。
//!
//! 用法:
//!   把 key 放进 .env(见 .env.example,已 gitignore),然后:
//!     cargo run --release
//!   或临时:
//!     FRED_API_KEY=xxxx cargo run --release

mod fred;
mod series;
mod store;

use anyhow::{Context, Result};
use chrono::{Local, NaiveDate};

/// 日频序列若最新观测距 run_date 超过此天数,视为陈旧(疑似停更/长时间中断),
/// 计入失败而非静默当作「今日最新」。14 天可容纳长假 + 发布滞后。
const MAX_STALENESS_DAYS: i64 = 14;

/// 最新观测日距 run_date 的天数;任一日期无法解析时返回 None(跳过校验)。
fn staleness_days(run_date: &str, obs_date: &str) -> Option<i64> {
    let run = NaiveDate::parse_from_str(run_date, "%Y-%m-%d").ok()?;
    let obs = NaiveDate::parse_from_str(obs_date, "%Y-%m-%d").ok()?;
    Some((run - obs).num_days())
}

fn main() -> Result<()> {
    // 加载 .env(若存在);缺失也无妨,环境变量优先。
    dotenvy::dotenv().ok();

    let api_key = std::env::var("FRED_API_KEY").context(
        "缺少环境变量 FRED_API_KEY。把 key 放进 .env(见 .env.example)或导出该变量。\n\
         申请:https://fred.stlouisfed.org/docs/api/api_key.html",
    )?;

    let client = fred::FredClient::new(api_key)?;
    let run_date = Local::now().format("%Y-%m-%d").to_string();

    let mut records = Vec::new();
    let mut failures: Vec<(String, String)> = Vec::new();

    println!("== 抓取核心宏观数据 (run_date={run_date}) ==");
    for s in series::CORE_SERIES {
        match client.latest_observation(s.id) {
            Ok(obs) => {
                // 新鲜度防线:停更/长中断的序列不应把旧值静默当「今日最新」。
                if let Some(age) = staleness_days(&run_date, &obs.date)
                    && age > MAX_STALENESS_DAYS
                {
                    let msg = format!(
                        "数据陈旧:最新观测 {} 距今 {age} 天(阈值 {MAX_STALENESS_DAYS}),疑似序列停更",
                        obs.date
                    );
                    eprintln!("  ⚠ {:<24} {msg}", s.label);
                    failures.push((s.id.to_string(), msg));
                    continue;
                }
                println!("  ✓ {:<24} {:>10}  {:<7} ({})", s.label, obs.value, s.unit, obs.date);
                records.push(store::Record {
                    run_date: run_date.clone(),
                    series_id: s.id.to_string(),
                    label: s.label.to_string(),
                    obs_date: obs.date,
                    value: obs.value,
                    unit: s.unit.to_string(),
                    source: "FRED".to_string(),
                    note: s.note.to_string(),
                });
            }
            Err(e) => {
                eprintln!("  ✗ {:<24} 失败: {e}", s.label);
                failures.push((s.id.to_string(), e.to_string()));
            }
        }
    }

    let data_dir = std::path::Path::new("data");
    if !records.is_empty() {
        store::upsert_csv(data_dir, &records).context("写 CSV 失败")?;
    }
    store::write_markdown_snapshot(data_dir, &run_date, &records, &failures)
        .context("写 markdown 快照失败")?;

    if !failures.is_empty() {
        let ids: Vec<&str> = failures.iter().map(|(id, _)| id.as_str()).collect();
        eprintln!("⚠️ {} 个序列失败/陈旧:{}", failures.len(), ids.join(", "));
        // 在 GitHub Actions 里冒泡成 warning 注解(本地不打印这行)。
        if std::env::var("GITHUB_ACTIONS").is_ok() {
            println!("::warning::{} 个序列抓取失败或陈旧:{}", failures.len(), ids.join(", "));
        }
    }

    println!(
        "\n完成:{} 成功 / {} 失败。CSV -> data/observations.csv  快照 -> data/snapshots/{run_date}.md",
        records.len(),
        failures.len(),
    );

    // 全部失败 → 非零退出,便于 CI 报警(通常意味着 FRED_API_KEY 无效)。
    if records.is_empty() {
        anyhow::bail!("所有序列均抓取失败 —— 多半是 FRED_API_KEY 无效或网络不通");
    }
    Ok(())
}
