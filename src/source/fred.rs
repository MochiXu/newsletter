//! FRED 信息源(https://fred.stlouisfed.org/docs/api/)。
//!
//! 对每个 spec 取「最近若干条里最新的非缺失观测值」。
//! 安全:`.send()`/`.text()` 出错时立即 `.without_url()`,把含 api_key 的 URL 从 reqwest
//! 错误里剥离——再据此构造 `Error::Http`。由于 `error.rs` 不为 reqwest::Error 实现 `#[from]`,
//! 这是唯一构造路径,api_key 无论用 {e}/{e:#}/{e:?} 都不会泄漏到日志或提交回仓库的快照。

use reqwest::blocking::Client;
use serde::Deserialize;

use crate::catalog::SeriesSpec;
use crate::error::{Error, Failure, Result};
use crate::model::Observation;
use crate::source::{Source, SourceData};

const FRED_BASE: &str = "https://api.stlouisfed.org/fred";

#[derive(Deserialize)]
struct ObservationsResponse {
    observations: Vec<RawObservation>,
}

#[derive(Deserialize)]
struct RawObservation {
    date: String,
    value: String,
}

/// FRED 信息源,持有 api_key 与一个 blocking HTTP client。
pub struct FredSource {
    api_key: String,
    http: Client,
}

impl FredSource {
    pub fn new(api_key: String) -> Result<Self> {
        let http = Client::builder()
            .user_agent("newsletter-m0/0.1 (data-plane)")
            .timeout(std::time::Duration::from_secs(30))
            .build()
            .map_err(Error::HttpClient)?;
        Ok(Self { api_key, http })
    }

    /// 取某序列最近若干条里最新的非缺失观测值。
    ///
    /// limit 取较大值(40)以越过长假/发布滞后造成的连续缺失;否则若最近几条恰好全为 "."
    /// 会被误判为「无有效观测」。
    fn fetch_one(&self, spec: &SeriesSpec) -> Result<Observation> {
        let url = format!("{FRED_BASE}/series/observations");
        let resp = self
            .http
            .get(&url)
            .query(&[
                ("series_id", spec.id),
                ("api_key", self.api_key.as_str()),
                ("file_type", "json"),
                ("sort_order", "desc"),
                ("limit", "40"),
            ])
            .send()
            // SECURITY: without_url() before constructing Error — keeps api_key out of logs/snapshots/CI.
            .map_err(|e| Error::Http { series: spec.id.to_string(), source: e.without_url() })?;

        let status = resp.status();
        // 只读 text 而非 error_for_status():FRED 把错误原因放在 body(不含 api_key)。
        let body = resp
            .text()
            // SECURITY: without_url() before constructing Error.
            .map_err(|e| Error::Http { series: spec.id.to_string(), source: e.without_url() })?;
        if !status.is_success() {
            return Err(Error::HttpStatus { status: status.as_u16(), series: spec.id.to_string(), body });
        }
        parse_latest(&body, spec.id)
    }
}

impl Source for FredSource {
    fn name(&self) -> &'static str {
        "FRED"
    }

    fn fetch(&self, specs: &'static [SeriesSpec]) -> SourceData {
        let mut data = SourceData::new();
        for spec in specs {
            match self.fetch_one(spec) {
                Ok(obs) => data.ok.push((spec, obs)),
                Err(e) => data.failures.push(Failure::new(spec.id, &e)),
            }
        }
        data
    }
}

/// 从 FRED 的 observations JSON 里挑出最新一条可解析为数字的观测值。
///
/// FRED 用 "." 表示缺失;调用方按 sort_order=desc 请求,所以第一条有效的即最新。
/// 纯函数,便于离线单测(不依赖网络)。
fn parse_latest(body: &str, series_id: &str) -> Result<Observation> {
    let parsed: ObservationsResponse =
        serde_json::from_str(body).map_err(|e| Error::Parse {
            source_name: "FRED",
            series: series_id.to_string(),
            detail: e.to_string(),
        })?;
    for raw in parsed.observations {
        if raw.value == "." {
            continue;
        }
        if let Ok(value) = raw.value.parse::<f64>() {
            return Ok(Observation { date: raw.date, value });
        }
    }
    Err(Error::NoObservation { series: series_id.to_string() })
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

    /// 安全回归:用 connection-refused 的本地地址造一个真实 reqwest::Error(离线、确定),
    /// 它内嵌含 api_key 的 URL;断言 without_url() 后构造的 Error::Http 无论 Display 还是
    /// Debug 都**不含 api_key**(值与 `api_key=` 查询参数)。守住「api_key 绝不进日志/快照」
    /// 这条核心不变量。
    ///
    /// 注:api_key 只存在于 URL 的 query string 里,without_url() 会把整个 URL(含 query)剥离。
    /// 低层 connect 错误可能在 Debug 里留下它尝试连接的 host:port(此处 127.0.0.1:1),但那只是
    /// 主机地址、不含 query——真实场景下即公开的 api.stlouisfed.org,不构成泄漏。故只断言 key 不泄漏。
    #[test]
    fn http_error_strips_api_key() {
        let secret = "SUPERSECRETKEY123";
        let client = Client::builder()
            .timeout(std::time::Duration::from_secs(2))
            .build()
            .unwrap();
        // 127.0.0.1:1 几乎必然 connection-refused;reqwest 错误会带含 key 的 URL。
        let raw = client
            .get("http://127.0.0.1:1/fred/series/observations")
            .query(&[("api_key", secret)])
            .send()
            .expect_err("connection to 127.0.0.1:1 should fail");
        let leaky = raw.to_string(); // without_url() 之前:URL(含 key)在 Display 里
        assert!(leaky.contains(secret), "前提自检:剥离前应当含 key,否则测试无意义");

        let e = Error::Http { series: "DGS10".into(), source: raw.without_url() };
        let rendered = format!("{e} || {e:#} || {e:?}");
        assert!(!rendered.contains(secret), "api_key value leaked: {rendered}");
        assert!(!rendered.contains("api_key"), "api_key query param leaked: {rendered}");
    }
}
