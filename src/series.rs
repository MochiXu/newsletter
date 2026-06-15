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
    Series { id: "DTWEXBGS", label: "USD Index (Broad)", unit: "index", note: "贸易加权美元,FRED 可靠;真 DXY 见 Yahoo 补充" },
];

/// Yahoo Finance 免鉴权源。口径未必与 FRED 完全一致(如 DX-Y.NYB 是 ICE 窄口径
/// DXY≈99,≠ FRED 广义美元 DTWEXBGS≈120;GC=F 是 COMEX 期货),故以各自符号与
/// 标签**独立记录**,不与 FRED 行混用口径。
pub struct YahooSeries {
    pub symbol: &'static str,
    pub label: &'static str,
    /// 单位换算系数(留作收益率类换算;Yahoo ^TNX 现报 % 本身,用 1.0)。
    pub scale: f64,
    pub unit: &'static str,
    pub note: &'static str,
}

/// FRED 提供不了的指标,**每次都补**:真 DXY 与黄金(FRED 伦敦金价序列已下架)。
pub const YAHOO_SUPPLEMENT: &[YahooSeries] = &[
    YahooSeries { symbol: "DX-Y.NYB", label: "USD Index (DXY, ICE)", scale: 1.0, unit: "index", note: "窄口径 DXY,用户口径" },
    YahooSeries { symbol: "GC=F", label: "Gold (COMEX front)", scale: 1.0, unit: "USD/oz", note: "FRED 伦敦金价序列已下架,改用期货" },
];

/// FRED 整体不可用(缺 key/key 无效)时,用 Yahoo 顶上 FRED 那部分(利率/波动/股指)。
pub const YAHOO_DEGRADED: &[YahooSeries] = &[
    YahooSeries { symbol: "^GSPC", label: "S&P 500", scale: 1.0, unit: "index", note: "" },
    YahooSeries { symbol: "^VIX", label: "VIX", scale: 1.0, unit: "index", note: "" },
    YahooSeries { symbol: "^TNX", label: "10Y Treasury", scale: 1.0, unit: "%", note: "Yahoo ^TNX 现报收益率本身(%)" },
];
