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
