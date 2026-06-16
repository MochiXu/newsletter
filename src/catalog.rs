//! 要抓取的序列/符号定义(纯常量数据,无行为)。
//!
//! FRED 与 Yahoo 统一为一个 [`SeriesSpec`]:FRED 行的 `scale` 恒为 1.0(被 FRED source 忽略),
//! Yahoo 行用 `scale` 做单位换算(如某些收益率符号)。口径差异见各 `note`。

/// 一个待抓取序列的定义。
pub struct SeriesSpec {
    /// 源内标识:FRED 的 series_id(如 "DGS10"),或 Yahoo 的 symbol(如 "DX-Y.NYB")。
    pub id: &'static str,
    /// 人类可读标签。
    pub label: &'static str,
    /// 单位。
    pub unit: &'static str,
    /// 备注(口径/来源说明),可为空串。
    pub note: &'static str,
    /// 单位换算系数(Yahoo 收益率类用;FRED 与多数 Yahoo 符号为 1.0)。
    pub scale: f64,
}

/// M0 核心数据集:利率、利差、波动率、广义美元 —— 全部来自 FRED(权威、稳定)。
pub const FRED_CORE: &[SeriesSpec] = &[
    SeriesSpec { id: "DGS10", label: "10Y Treasury", unit: "%", note: "", scale: 1.0 },
    SeriesSpec { id: "DGS2", label: "2Y Treasury", unit: "%", note: "", scale: 1.0 },
    SeriesSpec { id: "T10Y2Y", label: "2s10s Spread", unit: "%", note: "10Y 减 2Y", scale: 1.0 },
    SeriesSpec { id: "VIXCLS", label: "VIX", unit: "index", note: "", scale: 1.0 },
    SeriesSpec {
        id: "DTWEXBGS",
        label: "USD Index (Broad)",
        unit: "index",
        note: "贸易加权美元,FRED 可靠;真 DXY 见 Yahoo 补充",
        scale: 1.0,
    },
];

/// FRED 提供不了的指标,**每次都补**:真 DXY 与黄金(FRED 伦敦金价序列已下架)。
/// 口径与 FRED 不同(DX-Y.NYB 是 ICE 窄口径 DXY,GC=F 是 COMEX 期货),以各自符号独立记录。
pub const YAHOO_SUPPLEMENT: &[SeriesSpec] = &[
    SeriesSpec { id: "DX-Y.NYB", label: "USD Index (DXY, ICE)", unit: "index", note: "窄口径 DXY,用户口径", scale: 1.0 },
    SeriesSpec { id: "GC=F", label: "Gold (COMEX front)", unit: "USD/oz", note: "FRED 伦敦金价序列已下架,改用期货", scale: 1.0 },
];

/// FRED 整体不可用(key 无效)时,用 Yahoo 顶上 FRED 那部分(利率/波动/股指)。
pub const YAHOO_DEGRADED: &[SeriesSpec] = &[
    SeriesSpec { id: "^GSPC", label: "S&P 500", unit: "index", note: "", scale: 1.0 },
    SeriesSpec { id: "^VIX", label: "VIX", unit: "index", note: "", scale: 1.0 },
    SeriesSpec { id: "^TNX", label: "10Y Treasury", unit: "%", note: "Yahoo ^TNX 现报收益率本身(%)", scale: 1.0 },
];
