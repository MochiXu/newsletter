//! FRED API 客户端(https://fred.stlouisfed.org/docs/api/)。
//!
//! 只读「某序列最新一条非缺失观测值」。
//! 注意:错误信息里**不包含 api_key**(避免泄漏到日志/提交的快照)。

use anyhow::{Context, Result, bail};
use serde::Deserialize;

const FRED_BASE: &str = "https://api.stlouisfed.org/fred";

/// 一条观测值。
#[derive(Debug, Clone, PartialEq)]
pub struct Observation {
    pub date: String,
    pub value: f64,
}

#[derive(Deserialize)]
struct ObservationsResponse {
    observations: Vec<RawObservation>,
}

#[derive(Deserialize)]
struct RawObservation {
    date: String,
    value: String,
}

/// 从 FRED 的 observations JSON 里挑出最新一条可解析为数字的观测值。
///
/// FRED 用 "." 表示缺失;调用方按 sort_order=desc 请求,所以第一条有效的即最新。
/// 这是一个纯函数,便于离线单测(不依赖网络)。
fn parse_latest(body: &str, series_id: &str) -> Result<Observation> {
    let parsed: ObservationsResponse =
        serde_json::from_str(body).with_context(|| format!("解析 FRED 响应失败:{series_id}"))?;
    for raw in parsed.observations {
        if raw.value == "." {
            continue;
        }
        if let Ok(value) = raw.value.parse::<f64>() {
            return Ok(Observation { date: raw.date, value });
        }
    }
    bail!("序列 {series_id} 最近无有效观测值")
}

/// FRED 客户端,持有 api_key 和一个 blocking HTTP client。
pub struct FredClient {
    api_key: String,
    http: reqwest::blocking::Client,
}

impl FredClient {
    pub fn new(api_key: String) -> Result<Self> {
        let http = reqwest::blocking::Client::builder()
            .user_agent("newsletter-m0/0.1 (data-plane)")
            .timeout(std::time::Duration::from_secs(30))
            .build()
            .context("构建 HTTP client 失败")?;
        Ok(Self { api_key, http })
    }

    /// 取某序列最新的非缺失观测值。
    pub fn latest_observation(&self, series_id: &str) -> Result<Observation> {
        let url = format!("{FRED_BASE}/series/observations");
        let resp = self
            .http
            .get(&url)
            .query(&[
                ("series_id", series_id),
                ("api_key", self.api_key.as_str()),
                ("file_type", "json"),
                ("sort_order", "desc"),
                ("limit", "10"),
            ])
            .send()
            .with_context(|| format!("请求 FRED 失败:{series_id}"))?;

        let status = resp.status();
        // 故意只读 text 而非 resp.error_for_status():FRED 把错误原因放在 body,
        // 且 body 不含 api_key,适合展示。
        let body = resp
            .text()
            .with_context(|| format!("读取 FRED 响应体失败:{series_id}"))?;
        if !status.is_success() {
            bail!("FRED 返回 {status}({series_id}):{body}");
        }
        parse_latest(&body, series_id)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    const SAMPLE: &str = r#"{"observations":[
        {"date":"2026-06-16","value":"."},
        {"date":"2026-06-15","value":"4.23"},
        {"date":"2026-06-12","value":"4.20"}
    ]}"#;

    #[test]
    fn picks_latest_non_missing() {
        let obs = parse_latest(SAMPLE, "DGS10").unwrap();
        assert_eq!(obs.date, "2026-06-15");
        assert_eq!(obs.value, 4.23);
    }

    #[test]
    fn errors_when_all_missing() {
        let body = r#"{"observations":[{"date":"2026-06-16","value":"."}]}"#;
        assert!(parse_latest(body, "X").is_err());
    }

    #[test]
    fn errors_on_garbage_json() {
        assert!(parse_latest("not json", "X").is_err());
    }
}
