// Mock pre-aggregated timeline rollups — produced upstream, one set per granularity.
// The DAY granularity is rendered straight from BRIEFS; these are the longer
// "statement" stubs (month / quarter / half / year). Front-end does no aggregation
// (N6): it only renders whichever JSON the granularity tab points at.
// stat.d: 'up' | 'down' | 'flat' tints the value with the up/down/ink color.

export const PERIODS = {
  month: [
    { id: '2026-06', label: '六月', sub: '2026 · 06-01 → 06-16', tone: 'risk-off', acc: 71,
      headline: 'FOMC 鹰派暂停定调全月:点阵图上修,曲线倒挂走深,美元与 10Y 齐升。',
      stats: [ { k: 'US10Y', v: '4.49% ▲', d: 'up' }, { k: 'VIX 均', v: '15.1', d: 'flat' }, { k: 'DXY', v: '104.9 ▲', d: 'up' }, { k: '命中率', v: '71%', d: 'flat' } ] },
    { id: '2026-05', label: '五月', sub: '2026 · 全月', tone: 'risk-on', acc: 74,
      headline: '通胀降温叙事主导:收益率回落,风险偏好修复,黄金创新高。',
      stats: [ { k: 'US10Y', v: '4.27% ▼', d: 'down' }, { k: 'VIX 均', v: '13.9', d: 'flat' }, { k: 'GOLD', v: '2,455 ▲', d: 'up' }, { k: '命中率', v: '74%', d: 'flat' } ] },
    { id: '2026-04', label: '四月', sub: '2026 · 全月', tone: 'neutral', acc: 66,
      headline: '区间震荡:数据互有强弱,曲线在 -40bp 附近反复。',
      stats: [ { k: 'US10Y', v: '4.41% ~', d: 'flat' }, { k: 'VIX 均', v: '15.6', d: 'flat' }, { k: 'DXY', v: '104.5 ~', d: 'flat' }, { k: '命中率', v: '66%', d: 'flat' } ] },
    { id: '2026-03', label: '三月', sub: '2026 · 全月', tone: 'risk-off', acc: 63,
      headline: '关税与通胀双重扰动,避险升温,VIX 一度上探 20。',
      stats: [ { k: 'US10Y', v: '4.52% ▲', d: 'up' }, { k: 'VIX 均', v: '17.2', d: 'up' }, { k: 'GOLD', v: '2,380 ▲', d: 'up' }, { k: '命中率', v: '63%', d: 'flat' } ] },
    { id: '2026-02', label: '二月', sub: '2026 · 全月', tone: 'risk-on', acc: 70,
      headline: '降息预期升温,美元转弱,成长股领涨。',
      stats: [ { k: 'US10Y', v: '4.33% ▼', d: 'down' }, { k: 'VIX 均', v: '14.4', d: 'flat' }, { k: 'DXY', v: '103.6 ▼', d: 'down' }, { k: '命中率', v: '70%', d: 'flat' } ] },
    { id: '2026-01', label: '一月', sub: '2026 · 全月', tone: 'neutral', acc: 68,
      headline: '年初定调:政策不确定性下的谨慎乐观,曲线维持倒挂。',
      stats: [ { k: 'US10Y', v: '4.45% ~', d: 'flat' }, { k: 'VIX 均', v: '15.0', d: 'flat' }, { k: 'DXY', v: '104.2 ~', d: 'flat' }, { k: '命中率', v: '68%', d: 'flat' } ] },
  ],
  quarter: [
    { id: '2026-Q2', label: '第二季度', sub: '2026 · 04 → 06', tone: 'risk-off', acc: 70,
      headline: '从通胀降温到 FOMC 鹰派暂停:风险偏好先扬后抑,曲线倒挂主导。',
      stats: [ { k: 'US10Y', v: '4.49% ▲', d: 'up' }, { k: 'VIX 均', v: '14.9', d: 'flat' }, { k: 'GOLD', v: '2,410 ▲', d: 'up' }, { k: '命中率', v: '70%', d: 'flat' } ] },
    { id: '2026-Q1', label: '第一季度', sub: '2026 · 01 → 03', tone: 'neutral', acc: 67,
      headline: '政策路径反复定价:关税扰动与降息预期拉锯,整体区间运行。',
      stats: [ { k: 'US10Y', v: '4.52% ▲', d: 'up' }, { k: 'VIX 均', v: '15.5', d: 'flat' }, { k: 'DXY', v: '104.4 ~', d: 'flat' }, { k: '命中率', v: '67%', d: 'flat' } ] },
    { id: '2025-Q4', label: '第四季度', sub: '2025 · 10 → 12', tone: 'risk-on', acc: 72,
      headline: '年末降息落地,曲线陡峭化,风险资产收复失地。',
      stats: [ { k: 'US10Y', v: '4.18% ▼', d: 'down' }, { k: 'VIX 均', v: '13.6', d: 'flat' }, { k: 'GOLD', v: '2,340 ▲', d: 'up' }, { k: '命中率', v: '72%', d: 'flat' } ] },
  ],
  half: [
    { id: '2026-H1', label: '上半年', sub: '2026 · 01 → 06', tone: 'neutral', acc: 69,
      headline: '通胀去通胀路径的反复:市场在「更高更久」与「提前降息」间反复定价。',
      stats: [ { k: 'US10Y', v: '4.49% ▲', d: 'up' }, { k: 'VIX 均', v: '15.2', d: 'flat' }, { k: 'GOLD', v: '2,410 ▲', d: 'up' }, { k: '命中率', v: '69%', d: 'flat' } ] },
    { id: '2025-H2', label: '下半年', sub: '2025 · 07 → 12', tone: 'risk-on', acc: 71,
      headline: '紧缩周期尾声:政策转向预期升温,收益率见顶回落。',
      stats: [ { k: 'US10Y', v: '4.18% ▼', d: 'down' }, { k: 'VIX 均', v: '14.1', d: 'flat' }, { k: 'DXY', v: '103.9 ▼', d: 'down' }, { k: '命中率', v: '71%', d: 'flat' } ] },
  ],
  year: [
    { id: '2026', label: '2026 年', sub: '至今 · 01 → 06', tone: 'neutral', acc: 69,
      headline: '主题是「政策路径的反复定价」:降息节奏成为全年宏观叙事的中枢。',
      stats: [ { k: 'US10Y', v: '4.49%', d: 'up' }, { k: 'VIX 均', v: '15.2', d: 'flat' }, { k: 'GOLD', v: '2,410', d: 'up' }, { k: '命中率', v: '69%', d: 'flat' } ] },
    { id: '2025', label: '2025 年', sub: '全年', tone: 'risk-on', acc: 70,
      headline: '从加息尾声到首次降息:全年宏观由紧缩转向宽松预期。',
      stats: [ { k: 'US10Y', v: '4.18%', d: 'down' }, { k: 'VIX 均', v: '14.6', d: 'flat' }, { k: 'GOLD', v: '2,340', d: 'up' }, { k: '命中率', v: '70%', d: 'flat' } ] },
  ],
};
