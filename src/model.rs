//! 数据 schema 层:抓取到的观测值,以及落库的记录(CSV 接缝)。无任何 I/O。

use crate::catalog::SeriesSpec;

/// 一条观测值(某序列某日的取值)。各 source 抓取后产出的原始形态。
#[derive(Debug, Clone, PartialEq)]
pub struct Observation {
    pub date: String,
    pub value: f64,
}

/// 一条最终落库记录。字段顺序 == `observations.csv` 的列,是两半之间的稳定接缝,**勿改**。
#[derive(Debug, Clone, PartialEq)]
pub struct Record {
    pub run_date: String,
    pub series_id: String,
    pub label: String,
    pub obs_date: String,
    pub value: f64,
    pub unit: String,
    pub source: String,
    pub note: String,
}

impl Record {
    /// 由 source 名、序列定义、观测值与 run_date 组装一条记录。
    pub fn new(source: &str, spec: &SeriesSpec, obs: Observation, run_date: &str) -> Record {
        Record {
            run_date: run_date.to_string(),
            series_id: spec.id.to_string(),
            label: spec.label.to_string(),
            obs_date: obs.date,
            value: obs.value,
            unit: spec.unit.to_string(),
            source: source.to_string(),
            note: spec.note.to_string(),
        }
    }
}
