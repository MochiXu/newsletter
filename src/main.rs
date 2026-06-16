//! 数据平面二进制入口(bin "fetch")。
//!
//! 职责仅限:初始化日志、加载 .env、读 Config、调 `newsletter::run`、按需输出 GitHub Actions
//! 注解、决定退出码。编排逻辑都在 `lib.rs` 的 `run`。
//!
//! 用法:把 key 放进 .env(见 .env.example,已 gitignore),然后 `cargo run --release`;
//! 或临时 `FRED_API_KEY=xxxx cargo run --release`。日志级别用 `RUST_LOG` 覆盖(默认 info)。

use newsletter::Config;

fn main() {
    // 加载 .env(若存在);缺失也无妨,真实环境变量优先(CI 走 Secrets 注入)。
    dotenvy::dotenv().ok();
    env_logger::Builder::from_env(env_logger::Env::default().default_filter_or("info"))
        .format_timestamp_secs()
        .init();

    let cfg = Config::from_env();
    match newsletter::run(&cfg) {
        Ok(report) => {
            // GitHub Actions 注解走 stdout(workflow-command 协议),与 env_logger 的 stderr 分离;
            // 不路由进 log,以免被级别/时间戳前缀破坏。
            if cfg.github_actions && !report.failures.is_empty() {
                println!(
                    "::warning::{} series failed or stale: {}",
                    report.failures.len(),
                    report.failures.join(", "),
                );
            }
        }
        Err(e) => {
            log::error!("fatal: {e}");
            std::process::exit(1);
        }
    }
}
