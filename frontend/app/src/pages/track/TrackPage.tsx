import type { CSSProperties } from 'react'
import type { CalibBucket, LaneScore, Scorecard, ScoreCell, TrackMode } from '../../types'
import { ASSET_CN, HORIZON_CN, modelLabel } from '../../lib/format'

// ── 小工具 ───────────────────────────────────────────────────────────────
const pct = (x: number | null | undefined) => (x == null ? '—' : `${Math.round(x * 100)}%`)
const signpct = (x: number | null | undefined) => (x == null ? '—' : `${x >= 0 ? '+' : ''}${Math.round(x * 100)}%`)
const skillCol = (x: number | null | undefined) =>
  x == null ? 'var(--ink2)' : x > 0.001 ? 'var(--up)' : x < -0.001 ? 'var(--down)' : 'var(--ink2)'

/** lane id → 人读:'deepseek·B'→'Claude·B';'_factor'→'代码因子模型'。 */
function laneLabel(lane: string): string {
  if (lane === '_factor') return '代码因子模型'
  const [m, arm] = lane.split('·')
  return modelLabel(m) + (arm ? `·${arm}` : '')
}

function EmptyState() {
  return (
    <div className="mb-card mb-punch" style={{ padding: '40px 32px', textAlign: 'center' }}>
      <div style={{ fontFamily: 'var(--mono)', fontSize: 30, fontWeight: 600, color: 'var(--ink2)' }}>—— %</div>
      <div style={{ fontFamily: 'var(--mono)', fontSize: 13, color: 'var(--ink)', marginTop: 14 }}>scorecard 未生成</div>
      <div style={{ fontSize: 12.5, color: 'var(--ink2)', lineHeight: 1.8, marginTop: 12, maxWidth: 560, margin: '12px auto 0' }}>
        命中率需要后端评估层(evaluate.py)对已结算预测打分产出 data/scorecard.json,目前尚未生成。
        <br />
        真实打分跑出来前,这里不显示任何命中率数字。
      </div>
    </div>
  )
}

const metaCard: CSSProperties = { background: 'var(--paper2)', borderRadius: 8, padding: '12px 14px' }

/** 单元格(资产×horizon)技能行:命中 − 最强基线,绿正/红负。 */
function CellRow({ asset, hz, c }: { asset: string; hz: string; c: ScoreCell }) {
  const best = Math.max(...[c.driftBaseline, c.momentumBaseline, c.factorBaseline].filter((v): v is number => v != null), 0)
  const w = Math.min(50, Math.abs((c.skill ?? 0) * 100) * 1.6) // 技能条半宽(±最多 50%)
  const pos = (c.skill ?? 0) >= 0
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '3px 0', fontSize: 11, flexWrap: 'wrap' }}>
      <span style={{ minWidth: 86, color: 'var(--ink)' }}>
        {ASSET_CN[asset] ?? asset} <span style={{ color: 'var(--ink2)', fontFamily: 'var(--mono)', fontSize: 9.5 }}>{HORIZON_CN[hz as keyof typeof HORIZON_CN] ?? hz}</span>
      </span>
      <span style={{ fontFamily: 'var(--mono)', fontSize: 9.5, color: 'var(--ink2)', minWidth: 150 }}>
        命中 {pct(c.hit)} vs 基线 {pct(best || null)}
      </span>
      {/* 居中发散技能条 */}
      <span style={{ flex: 1, minWidth: 80, position: 'relative', height: 12 }}>
        <span style={{ position: 'absolute', left: '50%', top: 0, bottom: 0, width: 1, background: 'var(--hair)' }} />
        <span
          style={{
            position: 'absolute',
            top: 3,
            height: 6,
            borderRadius: 3,
            background: skillCol(c.skill),
            ...(pos ? { left: '50%', width: `${w}%` } : { right: '50%', width: `${w}%` }),
          }}
        />
      </span>
      <span style={{ fontFamily: 'var(--mono)', fontSize: 10, color: skillCol(c.skill), fontWeight: 700, minWidth: 46, textAlign: 'right' }}>
        {signpct(c.skill)}
      </span>
      <span style={{ fontFamily: 'var(--mono)', fontSize: 9, color: 'var(--ink2)', minWidth: 28, textAlign: 'right' }}>n{c.n}</span>
    </div>
  )
}

function Calibration({ buckets }: { buckets: CalibBucket[] }) {
  const has = buckets.some((b) => b.n > 0)
  if (!has) return null
  return (
    <div style={{ marginTop: 8 }}>
      <div style={{ fontFamily: 'var(--mono)', fontSize: 9, color: 'var(--ink2)', marginBottom: 3 }}>信心校准(自报 → 实际)</div>
      <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', fontFamily: 'var(--mono)', fontSize: 10 }}>
        {buckets.map((b, i) =>
          b.n > 0 ? (
            <span key={i} style={{ color: 'var(--ink2)' }}>
              [{b.lo}-{b.hi}) <span style={{ color: 'var(--ink)' }}>报{pct(b.stated)}</span>→
              <span style={{ color: (b.realized ?? 0) + 0.05 < (b.stated ?? 0) ? 'var(--down)' : 'var(--ink)' }}>实{pct(b.realized)}</span>
              <span style={{ fontSize: 8.5 }}> n{b.n}</span>
            </span>
          ) : null,
        )}
      </div>
    </div>
  )
}

function LaneCard({ lane, s }: { lane: string; s: LaneScore }) {
  const ov = s.overall
  return (
    <div className="mb-card mb-punch" style={{ padding: '14px 16px' }}>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, flexWrap: 'wrap', marginBottom: 10 }}>
        <span style={{ fontFamily: 'var(--mono)', fontSize: 13, fontWeight: 700, color: 'var(--ink)' }}>{laneLabel(lane)}</span>
        <span style={{ fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--ink2)' }}>
          总体命中 <span style={{ color: 'var(--ink)' }}>{pct(ov.hit)}</span> · Brier {ov.brier ?? '—'}
          (基线 {ov.brierBaseline ?? '—'}) · n{ov.n}
        </span>
      </div>
      {Object.entries(s.byAsset).map(([asset, hzs]) =>
        Object.entries(hzs).map(([hz, c]) => <CellRow key={`${asset}-${hz}`} asset={asset} hz={hz} c={c} />),
      )}
      <Calibration buckets={s.calibration} />
    </div>
  )
}

/** 命中率页:读 scorecard.json,展示 A/B 对比 + 技能 + 校准;backfill 醒目重标。 */
export default function TrackPage({ scorecard }: { mode: TrackMode; scorecard: Scorecard | null }) {
  const wrap: CSSProperties = { marginTop: 26, maxWidth: 1040, marginLeft: 'auto', marginRight: 'auto' }
  if (!scorecard || !Object.keys(scorecard.models).length) {
    return (
      <div style={wrap}>
        <EmptyState />
      </div>
    )
  }

  const models = scorecard.models
  const lanes = Object.keys(models).sort()
  // A/B 对比:基础模型(非 _factor)各取 ·A / ·B
  const bases = [...new Set(lanes.filter((l) => l !== '_factor' && l.includes('·')).map((l) => l.split('·')[0]))]
  const isBackfill = scorecard.source !== 'forward'

  return (
    <div style={wrap}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', gap: 16, marginBottom: 16, flexWrap: 'wrap' }}>
        <div>
          <span style={{ fontFamily: 'var(--mono)', fontSize: 10, letterSpacing: '1.6px', color: 'var(--ink2)' }}>TRACK RECORD</span>
          <span style={{ fontSize: 13, color: 'var(--ink2)', marginLeft: 8 }}>预测评估 · 截至 {scorecard.asOf || '—'}</span>
        </div>
        <span
          style={{
            fontFamily: 'var(--mono)', fontSize: 10, padding: '3px 9px', borderRadius: 6,
            background: isBackfill ? 'var(--down-bg, rgba(200,60,60,.12))' : 'var(--paper2)',
            color: isBackfill ? 'var(--down)' : 'var(--ink2)', border: '1px solid var(--faint)',
          }}
        >
          source = {scorecard.source}
        </span>
      </div>

      {/* 诚实红线:backfill 醒目警告 */}
      {isBackfill && (
        <div
          className="mb-card"
          style={{ padding: '12px 15px', marginBottom: 16, borderLeft: '3px solid var(--down)', borderRadius: 4 }}
        >
          <div style={{ fontSize: 12.5, color: 'var(--down)', fontWeight: 700, marginBottom: 4 }}>⚠ 回填数据(backfill),含模型记忆污染,仅供参考</div>
          <div style={{ fontSize: 11.5, color: 'var(--ink2)', lineHeight: 1.7 }}>
            这些预测由历史回放生成:LLM 跑历史某天时,其知识里可能已"记得"那天之后发生了什么,
            会让命中率虚高——尤其加新闻的 B 臂。<b style={{ color: 'var(--ink)' }}>不能据此判定"新闻有用"</b>。
            真实裁决要靠上线后 cron <b style={{ color: 'var(--ink)' }}>前向(forward)</b>逐日积累的干净数据。
          </div>
        </div>
      )}

      {/* A/B 对比:加新闻 vs 不加新闻 */}
      {bases.length > 0 && (
        <div style={metaCard}>
          <div style={{ fontFamily: 'var(--mono)', fontSize: 10, letterSpacing: '1px', color: 'var(--ink2)', marginBottom: 8 }}>
            A/B 消融 · 加新闻(B) vs 纯价格(A)
          </div>
          {bases.map((m) => {
            const a = models[`${m}·A`]
            const b = models[`${m}·B`]
            const ah = a?.overall.hit ?? null
            const bh = b?.overall.hit ?? null
            const delta = ah != null && bh != null ? bh - ah : null
            return (
              <div key={m} style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '4px 0', fontSize: 11.5, flexWrap: 'wrap' }}>
                <span style={{ minWidth: 64, fontWeight: 600, color: 'var(--ink)' }}>{modelLabel(m)}</span>
                <span style={{ fontFamily: 'var(--mono)', fontSize: 10.5, color: 'var(--ink2)' }}>
                  A 命中 {pct(ah)}(n{a?.overall.n ?? 0}) → B 命中 <span style={{ color: 'var(--ink)' }}>{pct(bh)}</span>(n{b?.overall.n ?? 0})
                </span>
                <span style={{ fontFamily: 'var(--mono)', fontSize: 10.5, fontWeight: 700, color: skillCol(delta) }}>
                  Δ {signpct(delta)}
                </span>
                <span style={{ fontFamily: 'var(--mono)', fontSize: 9.5, color: 'var(--ink2)' }}>
                  Brier A {a?.overall.brier ?? '—'} / B {b?.overall.brier ?? '—'}
                </span>
              </div>
            )
          })}
          <div style={{ fontSize: 10.5, color: 'var(--ink2)', lineHeight: 1.6, marginTop: 8 }}>
            技能(命中 − 最强基线)分资产看下方各卡;只有「<b style={{ color: 'var(--ink)' }}>前向</b> + 区间不含 0 + Brier 不变差」才算新闻真有用。
          </div>
        </div>
      )}

      {/* 各 lane 明细(技能 + 校准) */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 14, marginTop: 14 }}>
        {lanes.map((l) => (
          <LaneCard key={l} lane={l} s={models[l]} />
        ))}
      </div>

      <div style={{ fontSize: 11, color: 'var(--ink2)', lineHeight: 1.7, marginTop: 16, textAlign: 'center' }}>
        月 / 季 / 年区间聚合 + 日历 heatmap + 前向/回填分屏 + bootstrap 置信区间 留 V2。
      </div>
    </div>
  )
}
