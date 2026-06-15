//! M0 存储:git-as-database。
//!
//! 为什么不用 SQLite:M0 跑在 GitHub Actions 的临时 runner 上,SQLite 文件不跨
//! 运行持久化。把数据以 CSV/markdown 提交回仓库,等于用 git 当数据库——零基建、
//! 天然有历史、diff 可读。SQLite 接缝待 M1(Python 进场需要查询历史)再引入。
//!
//! - data/observations.csv :机器可读,append-only,git diff 友好
//! - data/snapshots/<run_date>.md :人类可读的当日快照

use anyhow::{Context, Result};
use std::fs;
use std::io::Write;
use std::path::Path;

/// 一条最终落库记录。
pub struct Record {
    pub run_date: String,
    pub series_id: String,
    pub label: String,
    pub obs_date: String,
    pub value: f64,
    pub unit: String,
    pub source: String,
    pub note: String,
}

const CSV_HEADER: &str = "run_date,series_id,label,obs_date,value,unit,source,note";

/// 对字段做最小 CSV 转义(含逗号/引号/换行时加引号)。
fn csv_field(s: &str) -> String {
    if s.contains(',') || s.contains('"') || s.contains('\n') {
        format!("\"{}\"", s.replace('"', "\"\""))
    } else {
        s.to_string()
    }
}

fn csv_row(r: &Record) -> String {
    format!(
        "{},{},{},{},{},{},{},{}",
        csv_field(&r.run_date),
        csv_field(&r.series_id),
        csv_field(&r.label),
        csv_field(&r.obs_date),
        r.value,
        csv_field(&r.unit),
        csv_field(&r.source),
        csv_field(&r.note),
    )
}

/// 追加写 <data_dir>/observations.csv;文件不存在时先写表头。
pub fn append_csv(data_dir: &Path, records: &[Record]) -> Result<()> {
    fs::create_dir_all(data_dir).with_context(|| format!("创建 {} 失败", data_dir.display()))?;
    let csv_path = data_dir.join("observations.csv");
    let exists = csv_path.exists();
    let mut file = fs::OpenOptions::new()
        .create(true)
        .append(true)
        .open(&csv_path)
        .with_context(|| format!("打开 {} 失败", csv_path.display()))?;
    if !exists {
        writeln!(file, "{CSV_HEADER}")?;
    }
    for r in records {
        writeln!(file, "{}", csv_row(r))?;
    }
    Ok(())
}

/// 写当天的 markdown 快照(覆盖式:同一天重跑会刷新当日文件)。
pub fn write_markdown_snapshot(
    data_dir: &Path,
    run_date: &str,
    records: &[Record],
    failures: &[(String, String)],
) -> Result<()> {
    let snap_dir = data_dir.join("snapshots");
    fs::create_dir_all(&snap_dir).with_context(|| format!("创建 {} 失败", snap_dir.display()))?;
    let path = snap_dir.join(format!("{run_date}.md"));

    let mut out = String::new();
    out.push_str(&format!("# 宏观数据快照 · {run_date}\n\n"));
    out.push_str("> 由 newsletter 数据平面(M0)自动生成。仅为事实记录,不构成投资建议。\n\n");
    out.push_str("| 指标 | 值 | 单位 | 观测日 | 序列 | 备注 |\n");
    out.push_str("|---|---:|---|---|---|---|\n");
    for r in records {
        out.push_str(&format!(
            "| {} | {} | {} | {} | `{}` | {} |\n",
            r.label, r.value, r.unit, r.obs_date, r.series_id, r.note
        ));
    }
    if !failures.is_empty() {
        out.push_str("\n## 抓取失败\n\n");
        for (id, err) in failures {
            out.push_str(&format!("- `{id}`: {err}\n"));
        }
    }
    out.push_str(&format!("\n_来源:FRED。run_date={run_date}。_\n"));

    fs::write(&path, out).with_context(|| format!("写 {} 失败", path.display()))?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn escapes_commas_and_quotes() {
        assert_eq!(csv_field("plain"), "plain");
        assert_eq!(csv_field("a,b"), "\"a,b\"");
        assert_eq!(csv_field("a\"b"), "\"a\"\"b\"");
    }

    #[test]
    fn csv_row_has_eight_fields() {
        let r = sample_record();
        assert_eq!(csv_row(&r).split(',').count(), 8);
    }

    fn sample_record() -> Record {
        Record {
            run_date: "2026-06-16".into(),
            series_id: "DGS10".into(),
            label: "10Y Treasury".into(),
            obs_date: "2026-06-15".into(),
            value: 4.23,
            unit: "%".into(),
            source: "FRED".into(),
            note: "".into(),
        }
    }

    /// 成功路径:写出 CSV(含表头)+ 带数据行的 markdown,且重复追加不重复表头。
    #[test]
    fn writes_csv_header_rows_and_markdown() {
        let dir = std::env::temp_dir().join(format!("nl_store_test_{}", std::process::id()));
        let _ = fs::remove_dir_all(&dir);
        let recs = vec![sample_record()];

        append_csv(&dir, &recs).unwrap();
        write_markdown_snapshot(&dir, "2026-06-16", &recs, &[]).unwrap();

        let csv = fs::read_to_string(dir.join("observations.csv")).unwrap();
        assert!(csv.starts_with(CSV_HEADER), "首行应为表头");
        assert!(csv.contains("DGS10"));
        assert!(csv.contains("4.23"));

        let md = fs::read_to_string(dir.join("snapshots/2026-06-16.md")).unwrap();
        assert!(md.contains("10Y Treasury"));
        assert!(md.contains("4.23"));
        assert!(!md.contains("## 抓取失败"), "无失败时不应有失败小节");

        // 再追加一次:表头只出现一次。
        append_csv(&dir, &recs).unwrap();
        let csv2 = fs::read_to_string(dir.join("observations.csv")).unwrap();
        assert_eq!(csv2.matches(CSV_HEADER).count(), 1, "表头不应重复");

        let _ = fs::remove_dir_all(&dir);
    }
}
