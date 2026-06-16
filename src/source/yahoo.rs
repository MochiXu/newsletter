//! Yahoo Finance chart API 的免鉴权信息源(FRED 给不了的指标 + FRED 整体不可用时的回退)。
//!
//! 用 `v8/finance/chart/{symbol}` 的 `meta.regularMarketPrice/Time` 取最新价。
//! Yahoo 是非官方接口且按 IP 限流(429);故带浏览器 UA、请求间留礼貌间隔、对 429/瞬时
//! 错误做线性退避重试。重试逻辑完全封在本源内部,runner 看不到。无 api_key,仍调
//! `.without_url()` 保持对称。

use std::thread::sleep;
use std::time::Duration;

use reqwest::blocking::Client;

use crate::catalog::SeriesSpec;
use crate::error::{Error, Failure, Result};
use crate::model::Observation;
use crate::source::{Source, SourceData};

const POLITE_DELAY: Duration = Duration::from_millis(1300);
const MAX_ATTEMPTS: u32 = 4;

/// Yahoo 信息源,持有一个带浏览器 UA 的 blocking client。
pub struct YahooSource {
    http: Client,
}

impl YahooSource {
    pub fn new() -> Result<Self> {
        let http = Client::builder()
            .user_agent(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 \
                 (KHTML, like Gecko) Chrome/120 Safari/537.36",
            )
            .timeout(Duration::from_secs(25))
            .build()
            .map_err(Error::HttpClient)?;
        Ok(Self { http })
    }

    /// 取某 Yahoo 符号最新价;Yahoo 会按 IP 限流(429),故请求间留间隔并对失败做退避重试。
    fn fetch_one(&self, spec: &SeriesSpec) -> Result<Observation> {
        let url = format!("https://query1.finance.yahoo.com/v8/finance/chart/{}", spec.id);
        let mut last = String::new();
        for attempt in 0u32..MAX_ATTEMPTS {
            // 礼貌间隔 + 线性退避(首次也等,避免与上一序列的请求挤在一起触发限流)。
            sleep(POLITE_DELAY * (attempt + 1));
            let resp = match self
                .http
                .get(&url)
                .query(&[("interval", "1d"), ("range", "5d")])
                .send()
                .map_err(|e| e.without_url())
            {
                Ok(r) => r,
                Err(e) => {
                    last = e.to_string();
                    log::debug!("yahoo {} attempt {}/{MAX_ATTEMPTS} send failed: {last}", spec.id, attempt + 1);
                    continue;
                }
            };
            let status = resp.status();
            // text() 失败视为本序列的硬性请求失败(与旧实现一致:不再重试该序列)。
            let body = resp
                .text()
                // SECURITY: without_url() before constructing Error(Yahoo 无 key,仍保持对称)。
                .map_err(|e| Error::Http { series: spec.id.to_string(), source: e.without_url() })?;
            if !status.is_success() {
                last = format!("HTTP {status}"); // 含 429 限流
                log::debug!("yahoo {} attempt {}/{MAX_ATTEMPTS}: {last}", spec.id, attempt + 1);
                continue;
            }
            match parse_chart(&body, spec.id, spec.scale) {
                Ok(obs) => return Ok(obs),
                Err(e) => {
                    last = e.to_string();
                    log::debug!("yahoo {} attempt {}/{MAX_ATTEMPTS} parse failed: {last}", spec.id, attempt + 1);
                    continue;
                }
            }
        }
        Err(Error::RetriesExhausted { series: spec.id.to_string(), last })
    }
}

impl Source for YahooSource {
    fn name(&self) -> &'static str {
        "Yahoo"
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

/// 从 Yahoo chart JSON 的 meta 段取最新价与日期(纯函数,便于离线单测)。
fn parse_chart(body: &str, symbol: &str, scale: f64) -> Result<Observation> {
    let mkerr = |detail: String| Error::Parse { source_name: "Yahoo", series: symbol.to_string(), detail };
    let v: serde_json::Value =
        serde_json::from_str(body).map_err(|e| mkerr(e.to_string()))?;
    let meta = &v["chart"]["result"][0]["meta"];
    let price = meta["regularMarketPrice"]
        .as_f64()
        .ok_or_else(|| mkerr("missing regularMarketPrice".to_string()))?;
    let ts = meta["regularMarketTime"]
        .as_i64()
        .ok_or_else(|| mkerr("missing regularMarketTime".to_string()))?;
    let date = chrono::DateTime::from_timestamp(ts, 0)
        .ok_or_else(|| mkerr("invalid regularMarketTime".to_string()))?
        .format("%Y-%m-%d")
        .to_string();
    // 缩放后四舍五入到 4 位,避免浮点尾差(如收益率类 ×0.1)。
    let value = ((price * scale) * 10_000.0).round() / 10_000.0;
    Ok(Observation { date, value })
}

#[cfg(test)]
mod tests {
    use super::*;

    const SAMPLE: &str = r#"{"chart":{"result":[{"meta":{"regularMarketPrice":99.683,"regularMarketTime":1781555303,"symbol":"DX-Y.NYB"}}]}}"#;

    #[test]
    fn parses_and_scales() {
        let obs = parse_chart(SAMPLE, "DX-Y.NYB", 1.0).unwrap();
        assert!((obs.value - 99.683).abs() < 1e-9, "got {}", obs.value);
        assert!(obs.date.starts_with("20"));
        // scale 生效:×0.1。
        let scaled = parse_chart(SAMPLE, "x", 0.1).unwrap();
        assert!((scaled.value - 9.9683).abs() < 1e-9, "got {}", scaled.value);
    }

    #[test]
    fn errors_without_price() {
        let body = r#"{"chart":{"result":[{"meta":{}}]}}"#;
        assert!(parse_chart(body, "X", 1.0).is_err());
    }
}
