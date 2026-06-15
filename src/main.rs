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
use chrono::Local;

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
        store::append_csv(data_dir, &records).context("写 CSV 失败")?;
    }
    store::write_markdown_snapshot(data_dir, &run_date, &records, &failures)
        .context("写 markdown 快照失败")?;

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
