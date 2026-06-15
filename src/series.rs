//! 核心宏观数据序列定义(M0:全部走 FRED,单一数据源 + 单一鉴权)。
//!
//! DXY 与 Gold 在 M0 用 FRED 的代理序列,口径与交易所盘口略有差异;
//! 待 M1/M2 再用 Stooq/Yahoo 精修。见 docs/data-plane.md。

/// 一个要抓取的 FRED 序列。
pub struct Series {
    /// FRED series_id,例如 "DGS10"。
    pub id: &'static str,
    /// 人类可读标签。
    pub label: &'static str,
    /// 单位。
    pub unit: &'static str,
    /// 备注(例如代理口径说明),可为空串。
    pub note: &'static str,
}

/// M0 核心数据集:利率、利差、波动率、美元、黄金 —— 全部来自 FRED。
pub const CORE_SERIES: &[Series] = &[
    Series { id: "DGS10", label: "10Y Treasury", unit: "%", note: "" },
    Series { id: "DGS2", label: "2Y Treasury", unit: "%", note: "" },
    Series { id: "T10Y2Y", label: "2s10s Spread", unit: "%", note: "10Y 减 2Y" },
    Series { id: "VIXCLS", label: "VIX", unit: "index", note: "" },
    Series { id: "DTWEXBGS", label: "USD Index (Broad)", unit: "index", note: "DXY 代理:贸易加权美元,口径不同" },
    Series { id: "GOLDAMGBD228NLBM", label: "Gold (London AM fix)", unit: "USD/oz", note: "" },
];

/// FRED 整体不可用时(如缺 key/key 无效)的免鉴权回退源(Yahoo Finance)。
///
/// 注意:这些是 Yahoo 各自的工具,口径未必与上面的 FRED 序列完全一致——例如
/// DX-Y.NYB 是 ICE 窄口径 DXY(≈99),≠ FRED 的广义美元指数 DTWEXBGS(≈120);
/// GC=F 是 COMEX 期货,≠ 伦敦定盘。故以各自符号与标签**独立记录**,不与 FRED 行混用。
pub struct YahooSeries {
    pub symbol: &'static str,
    pub label: &'static str,
    /// 单位换算系数(如 ^TNX 收益率为真实值 ×10,需 ×0.1)。
    pub scale: f64,
    pub unit: &'static str,
    pub note: &'static str,
}

pub const YAHOO_FALLBACK: &[YahooSeries] = &[
    YahooSeries { symbol: "^GSPC", label: "S&P 500", scale: 1.0, unit: "index", note: "" },
    YahooSeries { symbol: "^VIX", label: "VIX", scale: 1.0, unit: "index", note: "" },
    YahooSeries { symbol: "^TNX", label: "10Y Treasury", scale: 1.0, unit: "%", note: "Yahoo ^TNX 现报收益率本身(%)" },
    YahooSeries { symbol: "DX-Y.NYB", label: "USD Index (DXY, ICE)", scale: 1.0, unit: "index", note: "窄口径 DXY,≠FRED 广义美元" },
    YahooSeries { symbol: "GC=F", label: "Gold (COMEX front)", scale: 1.0, unit: "USD/oz", note: "期货,≠伦敦定盘" },
];
