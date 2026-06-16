//! M0 存储:git-as-database。
//!
//! 为什么不用 SQLite:M0 跑在 GitHub Actions 的临时 runner 上,SQLite 文件不跨运行持久化。
//! 把数据以 CSV/markdown 提交回仓库,等于用 git 当数据库——零基建、天然有历史、diff 可读。
//! SQLite 接缝待后续(需要查询历史时)再引入。
//!
//! - data/observations.csv :机器可读,按 run_date 幂等写入,git diff 友好
//! - data/snapshots/<run_date>.md :人类可读的当日快照

use std::collections::HashSet;
use std::fs;
use std::path::Path;

use crate::error::{Error, Failure, Result};
use crate::model::Record;

const CSV_HEADER: &str = "run_date,series_id,label,obs_date,value,unit,source,note";

/// 把 io 错误包成带路径的 `Error::Storage`。
fn storage_err(path: &Path) -> impl Fn(std::io::Error) -> Error + '_ {
    move |source| Error::Storage { path: path.display().to_string(), source }
}

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

/// 把任意错误文本压成安全的单行 markdown 片段(去换行、转义反引号/管道、截断)。
fn sanitize_inline(s: &str) -> String {
    let one_line: String = s
        .chars()
        .map(|c| if c == '\n' || c == '\r' { ' ' } else { c })
        .collect();
    let cleaned = one_line.replace('`', "'").replace('|', "/");
    let trimmed = cleaned.trim();
    if trimmed.chars().count() > 300 {
        let head: String = trimmed.chars().take(300).collect();
        format!("{head}…")
    } else {
        trimmed.to_string()
    }
}

/// 幂等写入 <data_dir>/observations.csv(按 run_date 去重)。
///
/// 读改写:保留表头 + 历史行,但丢弃与本次相同 run_date 的旧行后再写入,这样同一天重跑不会
/// 产生重复行;文件缺失或为空时也会正确写出表头。
pub fn upsert_csv(data_dir: &Path, records: &[Record]) -> Result<()> {
    fs::create_dir_all(data_dir).map_err(storage_err(data_dir))?;
    let csv_path = data_dir.join("observations.csv");

    // 本轮要写入的 run_date 集合。
    let incoming: HashSet<&str> = records.iter().map(|r| r.run_date.as_str()).collect();

    // 读取已有数据行(跳过表头与空行),丢弃 run_date 命中本轮的旧行。
    let mut kept: Vec<String> = Vec::new();
    if let Ok(content) = fs::read_to_string(&csv_path) {
        for line in content.lines().skip(1) {
            if line.is_empty() {
                continue;
            }
            let run_date = line.split(',').next().unwrap_or("");
            if !incoming.contains(run_date) {
                kept.push(line.to_string());
            }
        }
    }

    // 重写:表头 + 保留行 + 本轮新行。
    let mut out = String::new();
    out.push_str(CSV_HEADER);
    out.push('\n');
    for line in &kept {
        out.push_str(line);
        out.push('\n');
    }
    for r in records {
        out.push_str(&csv_row(r));
        out.push('\n');
    }
    fs::write(&csv_path, &out).map_err(storage_err(&csv_path))?;
    Ok(())
}

/// 写当天的 markdown 快照(覆盖式:同一天重跑会刷新当日文件)。
pub fn write_markdown_snapshot(
    data_dir: &Path,
    run_date: &str,
    records: &[Record],
    failures: &[Failure],
) -> Result<()> {
    let snap_dir = data_dir.join("snapshots");
    fs::create_dir_all(&snap_dir).map_err(storage_err(&snap_dir))?;
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
        for f in failures {
            out.push_str(&format!("- `{}`: {}\n", f.series_id, sanitize_inline(&f.message)));
        }
    }
    let mut sources: Vec<&str> = records.iter().map(|r| r.source.as_str()).collect();
    sources.sort_unstable();
    sources.dedup();
    let src = if sources.is_empty() { "—".to_string() } else { sources.join(", ") };
    out.push_str(&format!("\n_来源:{src}。run_date={run_date}。_\n"));

    fs::write(&path, out).map_err(storage_err(&path))?;
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

    #[test]
    fn csv_row_has_eight_fields() {
        assert_eq!(csv_row(&sample_record()).split(',').count(), 8);
    }

    #[test]
    fn sanitize_collapses_and_truncates() {
        let clean = sanitize_inline("line1\nline2 `code` | pipe");
        assert!(!clean.contains('\n'));
        assert!(!clean.contains('`'));
        assert!(!clean.contains('|'));
        assert!(sanitize_inline(&"x".repeat(500)).chars().count() <= 301);
    }

    /// 成功路径 + 幂等:写出带表头与数据行的 CSV/markdown,同 run_date 重写不产生重复。
    #[test]
    fn writes_csv_markdown_and_is_idempotent() {
        let dir = std::env::temp_dir().join(format!("nl_store_test_{}", std::process::id()));
        let _ = fs::remove_dir_all(&dir);
        let recs = vec![sample_record()];

        upsert_csv(&dir, &recs).unwrap();
        write_markdown_snapshot(&dir, "2026-06-16", &recs, &[]).unwrap();

        let csv = fs::read_to_string(dir.join("observations.csv")).unwrap();
        assert!(csv.starts_with(CSV_HEADER), "首行应为表头");
        assert!(csv.contains("DGS10") && csv.contains("4.23"));

        let md = fs::read_to_string(dir.join("snapshots/2026-06-16.md")).unwrap();
        assert!(md.contains("10Y Treasury") && md.contains("4.23"));
        assert!(!md.contains("## 抓取失败"), "无失败时不应有失败小节");

        // 同 run_date 再写一次:幂等——表头与数据行都不重复。
        upsert_csv(&dir, &recs).unwrap();
        let csv2 = fs::read_to_string(dir.join("observations.csv")).unwrap();
        assert_eq!(csv2.matches(CSV_HEADER).count(), 1, "表头不应重复");
        let data_rows = csv2.lines().skip(1).filter(|l| !l.is_empty()).count();
        assert_eq!(data_rows, 1, "同一天重跑不应产生重复行");

        let _ = fs::remove_dir_all(&dir);
    }
}
