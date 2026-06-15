//! Yahoo Finance chart API 的免鉴权客户端(FRED 整体不可用时的回退源)。
//!
//! 用 `v8/finance/chart/{symbol}` 的 `meta.regularMarketPrice/Time` 取最新价。
//! Yahoo 是非官方接口且按 IP 限流(429);因此本客户端:带浏览器 UA、请求间留
//! 礼貌间隔、对 429/瞬时错误做退避重试。仅作回退;主源仍是 FRED(口径权威、稳定)。

use anyhow::{Context, Result, bail};
use std::thread::sleep;
use std::time::Duration;

pub struct YahooClient {
    http: reqwest::blocking::Client,
}

pub struct Quote {
    pub date: String,
    pub value: f64,
}

const POLITE_DELAY: Duration = Duration::from_millis(1300);

impl YahooClient {
    pub fn new() -> Result<Self> {
        let http = reqwest::blocking::Client::builder()
            .user_agent(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 \
                 (KHTML, like Gecko) Chrome/120 Safari/537.36",
            )
            .timeout(Duration::from_secs(25))
            .build()
            .context("构建 Yahoo HTTP client 失败")?;
        Ok(Self { http })
    }

    /// 取某 Yahoo 符号最新价;scale 用于单位换算(如 ^TNX 收益率为真实值 ×10,需 ×0.1)。
    /// Yahoo 会按 IP 限流(429),故请求间留间隔并对失败做退避重试。
    pub fn latest(&self, symbol: &str, scale: f64) -> Result<Quote> {
        let url = format!("https://query1.finance.yahoo.com/v8/finance/chart/{symbol}");
        let mut last_err = String::new();
        for attempt in 0u32..4 {
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
                    last_err = e.to_string();
                    continue;
                }
            };
            let status = resp.status();
            let body = resp
                .text()
                .map_err(|e| e.without_url())
                .with_context(|| format!("读取 Yahoo 响应失败:{symbol}"))?;
            if !status.is_success() {
                last_err = format!("HTTP {status}"); // 含 429 限流
                continue;
            }
            match parse_chart(&body, symbol, scale) {
                Ok(q) => return Ok(q),
                Err(e) => {
                    last_err = e.to_string();
                    continue;
                }
            }
        }
        bail!("Yahoo 取 {symbol} 失败(重试耗尽):{last_err}")
    }
}

/// 从 Yahoo chart JSON 的 meta 段取最新价与日期(纯函数,便于离线单测)。
fn parse_chart(body: &str, symbol: &str, scale: f64) -> Result<Quote> {
    let v: serde_json::Value =
        serde_json::from_str(body).with_context(|| format!("解析 Yahoo JSON 失败:{symbol}"))?;
    let meta = &v["chart"]["result"][0]["meta"];
    let price = meta["regularMarketPrice"]
        .as_f64()
        .with_context(|| format!("Yahoo 无 regularMarketPrice:{symbol}"))?;
    let ts = meta["regularMarketTime"]
        .as_i64()
        .with_context(|| format!("Yahoo 无 regularMarketTime:{symbol}"))?;
    let date = chrono::DateTime::from_timestamp(ts, 0)
        .with_context(|| format!("Yahoo 时间戳非法:{symbol}"))?
        .format("%Y-%m-%d")
        .to_string();
    // 缩放后四舍五入到 4 位,避免浮点尾差(如 ^TNX×0.1)。
    let value = ((price * scale) * 10_000.0).round() / 10_000.0;
    Ok(Quote { date, value })
}

#[cfg(test)]
mod tests {
    use super::*;

    const SAMPLE: &str = r#"{"chart":{"result":[{"meta":{"regularMarketPrice":99.683,"regularMarketTime":1781555303,"symbol":"DX-Y.NYB"}}]}}"#;

    #[test]
    fn parses_and_scales() {
        let q = parse_chart(SAMPLE, "DX-Y.NYB", 1.0).unwrap();
        assert!((q.value - 99.683).abs() < 1e-9, "得到 {}", q.value);
        assert!(q.date.starts_with("20"));
        // scale 生效:×0.1。
        let scaled = parse_chart(SAMPLE, "x", 0.1).unwrap();
        assert!((scaled.value - 9.9683).abs() < 1e-9, "得到 {}", scaled.value);
    }

    #[test]
    fn errors_without_price() {
        let body = r#"{"chart":{"result":[{"meta":{}}]}}"#;
        assert!(parse_chart(body, "X", 1.0).is_err());
    }
}
