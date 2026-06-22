import type { Hypothesis, Impact } from '../../types'
import { ASSET_CN, dirInfo, HORIZON_CN, PRED_DIR } from '../../lib/format'
import { Card, SectionHead } from '../../components/Card'

function LayerHead({ label, zh, color }: { label: string; zh: string; color: string }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 7, margin: '15px 0 7px' }}>
      <span style={{ width: 8, height: 8, borderRadius: 2, background: color }} />
      <span style={{ fontFamily: 'var(--mono)', fontSize: 9.5, letterSpacing: '1.2px', color: 'var(--ink2)' }}>
        {label}
      </span>
      <span style={{ fontSize: 11, color: 'var(--ink)', fontWeight: 600 }}>{zh}</span>
    </div>
  )
}

function Bullet({ mark, markColor, text }: { mark: string; markColor: string; text: string }) {
  return (
    <div style={{ display: 'flex', gap: 8, fontSize: 12.5, lineHeight: 1.55, color: 'var(--ink)', marginBottom: 5 }}>
      <span style={{ color: markColor, flex: '0 0 auto', fontFamily: 'var(--mono)' }}>{mark}</span>
      <span style={{ textWrap: 'pretty' }}>{text}</span>
    </div>
  )
}

function PredictionCard({ h }: { h: Hypothesis }) {
  const d = PRED_DIR[h.direction]
  return (
    <div style={{ background: 'var(--paper2)', borderRadius: 5, padding: '10px 11px', marginBottom: 7 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap', marginBottom: 6 }}>
        <span style={{ fontSize: 12.5, fontWeight: 700, color: 'var(--ink)' }}>{ASSET_CN[h.asset] ?? h.asset}</span>
        <span style={{ fontFamily: 'var(--mono)', fontSize: 12.5, fontWeight: 700, color: d.col }}>
          {d.ch} {d.lab}
        </span>
        <span
          style={{
            fontFamily: 'var(--mono)',
            fontSize: 9.5,
            color: 'var(--ink2)',
            border: '1px solid var(--hair)',
            borderRadius: 3,
            padding: '1px 6px',
          }}
        >
          {HORIZON_CN[h.horizon]}
        </span>
        {h.confidence > 0 && (
          <span style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 6 }}>
            <span style={{ fontFamily: 'var(--mono)', fontSize: 9.5, color: 'var(--ink2)' }}>
              信心 {Math.round(h.confidence * 100)}%
            </span>
            <span style={{ width: 42, height: 4, borderRadius: 3, background: 'var(--hair)', overflow: 'hidden' }}>
              <span
                style={{ display: 'block', height: '100%', width: `${Math.round(h.confidence * 100)}%`, background: d.col }}
              />
            </span>
          </span>
        )}
      </div>
      <div style={{ fontSize: 12.5, lineHeight: 1.5, color: 'var(--ink)', fontWeight: 500, textWrap: 'pretty' }}>
        {h.ifThen}
      </div>
      <div style={{ fontSize: 10.5, lineHeight: 1.45, color: 'var(--ink2)', marginTop: 5, display: 'flex', gap: 6 }}>
        <span style={{ fontFamily: 'var(--mono)', color: 'var(--down)', flex: '0 0 auto' }}>✕ 失效</span>
        <span style={{ textWrap: 'pretty' }}>{h.invalidation}</span>
      </div>
      {h.keyFactors.length > 0 && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5, marginTop: 7 }}>
          {h.keyFactors.map((f, i) => (
            <span
              key={i}
              style={{
                fontSize: 9.5,
                color: 'var(--ink2)',
                background: 'var(--paper)',
                border: '1px solid var(--hair)',
                borderRadius: 3,
                padding: '2px 6px',
              }}
            >
              {f}
            </span>
          ))}
        </div>
      )}
    </div>
  )
}

/** AI BRIEF 四层:FACTS / INTERPRETATION / HYPOTHESIS(预测卡) / IMPACT。 */
export default function AiBrief({
  facts,
  reads,
  hypotheses,
  impacts,
}: {
  facts: string[]
  reads: string[]
  hypotheses: Hypothesis[]
  impacts: Impact[]
}) {
  return (
    <Card>
      <SectionHead label="AI BRIEF" zh="四层简报" margin="0 0 4px" />

      <LayerHead label="FACTS" zh="事实层" color="var(--ink2)" />
      {facts.map((f, i) => (
        <Bullet key={i} mark="›" markColor="var(--ink2)" text={f} />
      ))}

      <LayerHead label="INTERPRETATION" zh="解读层" color="var(--accent)" />
      {reads.map((r, i) => (
        <Bullet key={i} mark="—" markColor="var(--accent)" text={r} />
      ))}

      <LayerHead label="HYPOTHESIS" zh="假设层 · 预测" color="var(--blue)" />
      {hypotheses.map((h, i) => (
        <PredictionCard key={i} h={h} />
      ))}

      <LayerHead label="IMPACT" zh="影响层" color="var(--up)" />
      {impacts.map((im, i) => {
        const di = dirInfo(im.dir)
        return (
          <div
            key={i}
            style={{ display: 'flex', alignItems: 'baseline', gap: 8, fontSize: 12, lineHeight: 1.5, marginBottom: 5 }}
          >
            <span
              style={{ fontFamily: 'var(--mono)', fontSize: 12, color: di.col, flex: '0 0 auto', width: 12, textAlign: 'center' }}
            >
              {di.ch}
            </span>
            <span style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--ink)', flex: '0 0 auto' }}>
              {im.asset}
            </span>
            <span style={{ color: 'var(--ink2)', textWrap: 'pretty' }}>{im.watch}</span>
          </div>
        )
      })}
    </Card>
  )
}
